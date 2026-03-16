from __future__ import annotations

import asyncio
import logging
from collections.abc import Sequence
from dataclasses import dataclass

from app.clients.http import UpstreamFetchError
from app.models import SearchResponse, SourceBook
from app.services.normalizers.audiobookshelf import AudiobookshelfNormalizer
from app.services.scrapers.base import BaseMetadataScraper
from app.utils.text import normalize_match_text

logger = logging.getLogger(__name__)
MINIMUM_RELEVANCE_SCORE = 60.0
RELEVANCE_SCORE_WINDOW = 20.0
MINIMUM_TITLE_TOKEN_COVERAGE = 0.5
SCRAPER_TIMEOUT_REASON = "scraper timed out"


class UpstreamUnavailableError(Exception):
    """Raised when the upstream source cannot be reached."""


@dataclass(frozen=True)
class BookMatchSignals:
    book: SourceBook
    score: float
    title_exact: bool
    title_contains_query: bool
    query_contains_title: bool
    title_token_coverage: float
    author_match: bool

    @property
    def title_is_strong(self) -> bool:
        return (
            self.title_exact
            or self.title_contains_query
            or self.query_contains_title
            or self.title_token_coverage >= 1.0
        )

    @property
    def title_has_signal(self) -> bool:
        return (
            self.title_contains_query
            or self.query_contains_title
            or self.title_token_coverage >= MINIMUM_TITLE_TOKEN_COVERAGE
        )


def score_book_result(
    book: SourceBook, *, query: str, author: str | None = None
) -> float:
    normalized_query = normalize_match_text(query)
    normalized_title = normalize_match_text(book.title)
    compact_query = _compact_match_text(normalized_query)
    compact_title = _compact_match_text(normalized_title)

    score = 0.0
    if _texts_equivalent(normalized_title, normalized_query):
        score += 100.0
    elif _text_contains(normalized_title, normalized_query) or _text_contains(
        compact_title, compact_query
    ):
        score += 65.0
    else:
        query_tokens = _split_match_tokens(normalized_query)
        title_tokens = _split_match_tokens(normalized_title)
        overlap = _token_overlap_count(query_tokens, title_tokens)
        score += overlap * 8.0

    if author:
        normalized_author = normalize_match_text(author)
        normalized_authors = normalize_match_text(" ".join(book.authors))
        if normalized_authors == normalized_author:
            score += 30.0
        elif normalized_author and normalized_author in normalized_authors:
            score += 20.0

    if book.language == "cs":
        score += 15.0
    elif book.language is None:
        score += 5.0
    elif book.language == "sk":
        score += 2.0

    return score


def score_candidate(
    book: SourceBook, *, query: str, author: str | None = None
) -> float:
    return score_book_result(book, query=query, author=author)


def build_book_match_signals(
    book: SourceBook, *, query: str, author: str | None = None
) -> BookMatchSignals:
    normalized_query = normalize_match_text(query)
    normalized_title = normalize_match_text(book.title)
    compact_query = _compact_match_text(normalized_query)
    compact_title = _compact_match_text(normalized_title)
    query_tokens = _split_match_tokens(normalized_query)
    title_tokens = _split_match_tokens(normalized_title)

    author_match = False
    if author:
        normalized_author = normalize_match_text(author)
        normalized_authors = normalize_match_text(" ".join(book.authors))
        author_tokens = _split_match_tokens(normalized_author)
        candidate_author_tokens = _split_match_tokens(normalized_authors)
        author_match = bool(normalized_author) and (
            normalized_authors == normalized_author
            or normalized_author in normalized_authors
            or _token_coverage(author_tokens, candidate_author_tokens) >= 1.0
        )

    return BookMatchSignals(
        book=book,
        score=score_book_result(book, query=query, author=author),
        title_exact=_texts_equivalent(normalized_title, normalized_query),
        title_contains_query=(
            _text_contains(normalized_title, normalized_query)
            or _text_contains(compact_title, compact_query)
        ),
        query_contains_title=(
            _text_contains(normalized_query, normalized_title)
            or _text_contains(compact_query, compact_title)
        ),
        title_token_coverage=_token_coverage(query_tokens, title_tokens),
        author_match=author_match,
    )


def filter_book_results(
    books: Sequence[SourceBook], *, query: str, author: str | None = None
) -> list[SourceBook]:
    if not books:
        return []

    signals = [
        build_book_match_signals(book, query=query, author=author) for book in books
    ]

    strong_title_author_matches = [
        signal.book
        for signal in signals
        if signal.author_match and signal.title_is_strong
    ]
    if strong_title_author_matches:
        exact_title_author_matches = [
            signal.book
            for signal in signals
            if signal.title_exact and signal.author_match
        ]
        if exact_title_author_matches:
            return exact_title_author_matches
        return strong_title_author_matches

    exact_title_matches = [signal.book for signal in signals if signal.title_exact]
    if exact_title_matches:
        return exact_title_matches

    best_score = max(signal.score for signal in signals)
    score_cutoff = max(MINIMUM_RELEVANCE_SCORE, best_score - RELEVANCE_SCORE_WINDOW)

    filtered_by_score = [
        signal.book
        for signal in signals
        if signal.score >= score_cutoff and signal.title_has_signal
    ]
    if filtered_by_score:
        return filtered_by_score

    fallback_matches = [signal.book for signal in signals if signal.title_has_signal]
    if fallback_matches:
        return fallback_matches

    return list(books)


def sort_book_results(
    books: Sequence[SourceBook], *, query: str, author: str | None = None
) -> list[SourceBook]:
    return sorted(
        books,
        key=lambda book: (
            score_book_result(book, query=query, author=author),
            normalize_match_text(" ".join(book.authors)),
            normalize_match_text(book.title),
        ),
        reverse=True,
    )


def _split_match_tokens(value: str) -> list[str]:
    return [token for token in value.split(" ") if token]


def _compact_match_text(value: str) -> str:
    return value.replace(" ", "")


def _texts_equivalent(left: str, right: str) -> bool:
    return (
        bool(left)
        and bool(right)
        and (left == right or _compact_match_text(left) == _compact_match_text(right))
    )


def _text_contains(container: str, candidate: str) -> bool:
    return bool(container) and bool(candidate) and candidate in container


def _token_overlap_count(
    query_tokens: Sequence[str], candidate_tokens: Sequence[str]
) -> int:
    candidate_token_set = {token for token in candidate_tokens if token}
    return len([token for token in query_tokens if token in candidate_token_set])


def _token_coverage(
    query_tokens: Sequence[str], candidate_tokens: Sequence[str]
) -> float:
    if not query_tokens:
        return 0.0
    overlap = _token_overlap_count(query_tokens, candidate_tokens)
    return overlap / len(query_tokens)


class MetadataProviderService:
    def __init__(
        self,
        *,
        scrapers: Sequence[BaseMetadataScraper],
        normalizer: AudiobookshelfNormalizer,
        detail_enrichment_limit: int = 5,
        scraper_timeout_seconds: float = 8.0,
    ) -> None:
        self._scrapers = list(scrapers)
        self._scrapers_by_name = {scraper.source_name: scraper for scraper in scrapers}
        self._normalizer = normalizer
        self._detail_enrichment_limit = detail_enrichment_limit
        self._scraper_timeout_seconds = scraper_timeout_seconds

    async def search(self, *, query: str, author: str | None = None) -> SearchResponse:
        aggregated: list[SourceBook] = []
        failures: list[UpstreamFetchError] = []

        results = await asyncio.gather(
            *(
                self._search_with_timeout(scraper, query=query, author=author)
                for scraper in self._scrapers
            ),
            return_exceptions=True,
        )

        for scraper, result in zip(self._scrapers, results, strict=True):
            if isinstance(result, UpstreamFetchError):
                failures.append(result)
                logger.warning(
                    "provider.search_failed",
                    extra={
                        "scraper": scraper.source_name,
                        "url": result.url,
                        "timeout_seconds": result.timeout_seconds,
                        "reason": result.reason,
                    },
                )
                continue

            if isinstance(result, Exception):
                raise result

            aggregated.extend(result)

        if (
            not aggregated
            and failures
            and not self._all_failures_are_scraper_timeouts(failures)
        ):
            raise UpstreamUnavailableError("upstream source unavailable")

        ranked = sort_book_results(aggregated, query=query, author=author)
        filtered = filter_book_results(ranked, query=query, author=author)
        enriched = await self._enrich_top_results(filtered)
        deduplicated = self._deduplicate(enriched)
        sorted_results = sort_book_results(deduplicated, query=query, author=author)
        filtered_results = filter_book_results(
            sorted_results, query=query, author=author
        )

        logger.info(
            "provider.search_complete",
            extra={
                "query": query,
                "author_provided": bool(author),
                "matches": len(filtered_results),
            },
        )

        return self._normalizer.normalize_many(filtered_results)

    async def _search_with_timeout(
        self,
        scraper: BaseMetadataScraper,
        *,
        query: str,
        author: str | None,
    ) -> list[SourceBook]:
        try:
            return await asyncio.wait_for(
                scraper.search(query=query, author=author),
                timeout=self._scraper_timeout_seconds,
            )
        except asyncio.TimeoutError as exc:
            raise self._build_timeout_error(
                scraper_name=scraper.source_name,
                operation="search",
            ) from exc

    async def _enrich_top_results(
        self, books: Sequence[SourceBook]
    ) -> list[SourceBook]:
        async def enrich_one(index: int, book: SourceBook) -> SourceBook:
            if (
                index >= self._detail_enrichment_limit
                or not self._needs_detail_enrichment(book)
            ):
                return book

            scraper = self._scrapers_by_name.get(book.source)
            if scraper is None:
                return book

            try:
                return await asyncio.wait_for(
                    scraper.enrich(book),
                    timeout=self._scraper_timeout_seconds,
                )
            except asyncio.TimeoutError:
                timeout_error = self._build_timeout_error(
                    scraper_name=book.source,
                    operation="detail_enrichment",
                    url=book.detail_url,
                )
                logger.warning(
                    "provider.detail_enrichment_failed",
                    extra={
                        "scraper": book.source,
                        "url": timeout_error.url,
                        "timeout_seconds": timeout_error.timeout_seconds,
                        "reason": timeout_error.reason,
                    },
                )
                return book
            except UpstreamFetchError as exc:
                logger.warning(
                    "provider.detail_enrichment_failed",
                    extra={
                        "scraper": book.source,
                        "url": exc.url,
                        "timeout_seconds": exc.timeout_seconds,
                        "reason": exc.reason,
                    },
                )
                return book

        return list(
            await asyncio.gather(
                *(enrich_one(index, book) for index, book in enumerate(books))
            )
        )

    def _needs_detail_enrichment(self, book: SourceBook) -> bool:
        return any(
            [
                not book.description,
                not book.publishers,
                not book.published_year,
                not book.genres,
                not book.language,
                book.duration_minutes is None,
            ]
        )

    def _deduplicate(self, books: Sequence[SourceBook]) -> list[SourceBook]:
        deduplicated: dict[tuple[str, str], SourceBook] = {}
        for book in books:
            deduplicated[(book.source, book.source_id)] = book
        return list(deduplicated.values())

    def _build_timeout_error(
        self,
        *,
        scraper_name: str,
        operation: str,
        url: str | None = None,
    ) -> UpstreamFetchError:
        return UpstreamFetchError(
            url=url or f"scraper://{scraper_name}/{operation}",
            reason=SCRAPER_TIMEOUT_REASON,
            timeout_seconds=self._scraper_timeout_seconds,
        )

    def _all_failures_are_scraper_timeouts(
        self, failures: Sequence[UpstreamFetchError]
    ) -> bool:
        return bool(failures) and all(
            failure.reason == SCRAPER_TIMEOUT_REASON for failure in failures
        )
