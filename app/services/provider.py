from __future__ import annotations

import logging
from collections.abc import Sequence

from app.clients.http import UpstreamFetchError
from app.models import SearchResponse, SourceBook
from app.services.normalizers.audiobookshelf import AudiobookshelfNormalizer
from app.services.scrapers.base import BaseMetadataScraper
from app.utils.text import normalize_match_text


logger = logging.getLogger(__name__)


class UpstreamUnavailableError(Exception):
    """Raised when the upstream source cannot be reached."""


def score_book_result(book: SourceBook, *, query: str, author: str | None = None) -> float:
    normalized_query = normalize_match_text(query)
    normalized_title = normalize_match_text(book.title)

    score = 0.0
    if normalized_title == normalized_query:
        score += 100.0
    elif normalized_query and normalized_query in normalized_title:
        score += 65.0
    else:
        query_tokens = [token for token in normalized_query.split(" ") if token]
        title_tokens = set(token for token in normalized_title.split(" ") if token)
        overlap = len([token for token in query_tokens if token in title_tokens])
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


def score_candidate(book: SourceBook, *, query: str, author: str | None = None) -> float:
    return score_book_result(book, query=query, author=author)


def sort_book_results(books: Sequence[SourceBook], *, query: str, author: str | None = None) -> list[SourceBook]:
    return sorted(
        books,
        key=lambda book: (
            score_book_result(book, query=query, author=author),
            normalize_match_text(" ".join(book.authors)),
            normalize_match_text(book.title),
        ),
        reverse=True,
    )


class MetadataProviderService:
    def __init__(
        self,
        *,
        scrapers: Sequence[BaseMetadataScraper],
        normalizer: AudiobookshelfNormalizer,
        detail_enrichment_limit: int = 5,
    ) -> None:
        self._scrapers = list(scrapers)
        self._scrapers_by_name = {scraper.source_name: scraper for scraper in scrapers}
        self._normalizer = normalizer
        self._detail_enrichment_limit = detail_enrichment_limit

    async def search(self, *, query: str, author: str | None = None) -> SearchResponse:
        aggregated: list[SourceBook] = []
        failures: list[UpstreamFetchError] = []

        for scraper in self._scrapers:
            try:
                aggregated.extend(await scraper.search(query=query, author=author))
            except UpstreamFetchError as exc:
                failures.append(exc)
                logger.warning(
                    "provider.search_failed",
                    extra={
                        "scraper": scraper.source_name,
                        "url": exc.url,
                        "timeout_seconds": exc.timeout_seconds,
                        "reason": exc.reason,
                    },
                )

        if not aggregated and failures:
            raise UpstreamUnavailableError("upstream source unavailable")

        ranked = sort_book_results(aggregated, query=query, author=author)
        enriched = await self._enrich_top_results(ranked)
        deduplicated = self._deduplicate(enriched)
        sorted_results = sort_book_results(deduplicated, query=query, author=author)

        logger.info(
            "provider.search_complete",
            extra={"query": query, "author_provided": bool(author), "matches": len(sorted_results)},
        )

        return self._normalizer.normalize_many(sorted_results)

    async def _enrich_top_results(self, books: Sequence[SourceBook]) -> list[SourceBook]:
        enriched_books: list[SourceBook] = []

        for index, book in enumerate(books):
            if index >= self._detail_enrichment_limit or not self._needs_detail_enrichment(book):
                enriched_books.append(book)
                continue

            scraper = self._scrapers_by_name.get(book.source)
            if scraper is None:
                enriched_books.append(book)
                continue

            try:
                enriched_books.append(await scraper.enrich(book))
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
                enriched_books.append(book)

        return enriched_books

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
