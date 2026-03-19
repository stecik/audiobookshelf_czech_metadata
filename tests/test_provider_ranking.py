from __future__ import annotations

import asyncio

from app.models import SourceBook
from app.services.normalizers.audiobookshelf import AudiobookshelfNormalizer
from app.services.provider import (
    MetadataProviderService,
    calculate_match_confidence,
    filter_book_results,
    score_book_result,
    sort_book_results,
)
from app.services.scrapers.base import BaseMetadataScraper


def make_book(
    *,
    source_id: str,
    title: str,
    authors: list[str],
    language: str | None,
) -> SourceBook:
    return SourceBook(
        source="audiolibrix",
        source_id=source_id,
        title=title,
        detail_url=f"https://www.audiolibrix.com/cs/Directory/Book/{source_id}/mock",
        authors=authors,
        language=language,
    )


def test_ranking_prefers_exact_title_author_and_czech_language() -> None:
    exact_czech = make_book(
        source_id="1",
        title="1984",
        authors=["George Orwell"],
        language="cs",
    )
    exact_slovak = make_book(
        source_id="2",
        title="1984",
        authors=["George Orwell"],
        language="sk",
    )
    substring_czech = make_book(
        source_id="3",
        title="Máj (1984)",
        authors=["Karel Hynek Mácha"],
        language="cs",
    )

    ordered = sort_book_results(
        [substring_czech, exact_slovak, exact_czech],
        query="1984",
        author="George Orwell",
    )

    assert ordered[0].source_id == "1"
    assert ordered[1].source_id == "2"
    assert score_book_result(
        exact_czech, query="1984", author="George Orwell"
    ) > score_book_result(
        exact_slovak,
        query="1984",
        author="George Orwell",
    )


def test_filter_book_results_keeps_only_exact_title_author_matches() -> None:
    exact_audiolibrix = make_book(
        source_id="1",
        title="Zabíjení",
        authors=["Štěpán Kopřiva"],
        language="cs",
    )
    exact_audioteka = make_book(
        source_id="2",
        title="Zabíjení",
        authors=["Štěpán Kopřiva"],
        language="cs",
    ).model_copy(update={"source": "audioteka"})
    broad_match = make_book(
        source_id="3",
        title="Kdo dává pokyny k zabíjení civilistů na Ukrajině?",
        authors=["Andrea Procházková", "Erik Tabery"],
        language="cs",
    ).model_copy(update={"source": "audioteka"})
    low_relevance = make_book(
        source_id="4",
        title="DNA",
        authors=["Yrsa Sigurðardóttir"],
        language="cs",
    )

    filtered = filter_book_results(
        [exact_audiolibrix, exact_audioteka, broad_match, low_relevance],
        query="zabíjení",
        author="štěpán kopřiva",
    )

    assert [(book.source, book.source_id) for book in filtered] == [
        ("audiolibrix", "1"),
        ("audioteka", "2"),
    ]


def test_filter_book_results_uses_author_to_drop_same_query_noise_without_exact_title() -> (
    None
):
    correct = make_book(
        source_id="1",
        title="Rytíř sedmi království",
        authors=["George R. R. Martin"],
        language="cs",
    )
    same_author_noise = make_book(
        source_id="2",
        title="Hra o trůny",
        authors=["George R. R. Martin"],
        language="cs",
    )
    same_topic_noise = make_book(
        source_id="3",
        title="Sedm smrtí Evelyn Hardcastlové",
        authors=["Stuart Turton"],
        language="cs",
    )

    filtered = filter_book_results(
        [correct, same_author_noise, same_topic_noise],
        query="sedmi království",
        author="george r r martin",
    )

    assert [book.source_id for book in filtered] == ["1"]


def test_filter_book_results_prefers_author_matched_prefixed_title_over_wrong_exact_title() -> (
    None
):
    wrong_exact_title = make_book(
        source_id="1",
        title="Volný pád",
        authors=["Ali Hazelwood"],
        language="cs",
    )
    correct_prefixed_title = make_book(
        source_id="2",
        title="Jack Reacher: Volný pád",
        authors=["Lee Child"],
        language="cs",
    )
    same_author_noise = make_book(
        source_id="3",
        title="Jack Reacher: Zásah",
        authors=["Lee Child"],
        language="cs",
    )

    filtered = filter_book_results(
        [wrong_exact_title, correct_prefixed_title, same_author_noise],
        query="Volný pád",
        author="Lee Child",
    )

    assert [book.source_id for book in filtered] == ["2"]


def test_filter_book_results_treats_hyphenated_and_compact_titles_as_equivalent() -> (
    None
):
    wrong_same_author = make_book(
        source_id="1",
        title="Vznešený dům",
        authors=["James Clavell"],
        language="cs",
    )
    correct_hyphenated = make_book(
        source_id="2",
        title="Tchaj-pan",
        authors=["James Clavell"],
        language="cs",
    )

    filtered = filter_book_results(
        [wrong_same_author, correct_hyphenated],
        query="Tchajpan",
        author="James Clavell",
    )

    assert [book.source_id for book in filtered] == ["2"]


def test_calculate_match_confidence_prefers_exact_title_author_matches() -> None:
    exact = make_book(
        source_id="1",
        title="1984",
        authors=["George Orwell"],
        language="cs",
    )
    broad = make_book(
        source_id="2",
        title="1984: rozbor a historické souvislosti",
        authors=["Jiný autor"],
        language="cs",
    )

    exact_confidence = calculate_match_confidence(
        exact,
        query="1984",
        author="George Orwell",
    )
    broad_confidence = calculate_match_confidence(
        broad,
        query="1984",
        author="George Orwell",
    )

    assert exact_confidence == 1.0
    assert broad_confidence < exact_confidence
    assert broad_confidence >= 0.0


class StaticScraper(BaseMetadataScraper):
    def __init__(self, source_name: str, books: list[SourceBook]) -> None:
        self.source_name = source_name
        self._books = books

    async def search(self, query: str, author: str | None = None) -> list[SourceBook]:
        return self._books


class SlowScraper(BaseMetadataScraper):
    def __init__(self, source_name: str, *, delay_seconds: float) -> None:
        self.source_name = source_name
        self._delay_seconds = delay_seconds

    async def search(self, query: str, author: str | None = None) -> list[SourceBook]:
        await asyncio.sleep(self._delay_seconds)
        return []


def test_provider_service_returns_filtered_matches_only() -> None:
    service = MetadataProviderService(
        scrapers=[
            StaticScraper(
                "audiolibrix",
                [
                    make_book(
                        source_id="1",
                        title="Zabíjení",
                        authors=["Štěpán Kopřiva"],
                        language="cs",
                    ),
                    make_book(
                        source_id="2",
                        title="DNA",
                        authors=["Yrsa Sigurðardóttir"],
                        language="cs",
                    ),
                ],
            ),
            StaticScraper(
                "audioteka",
                [
                    make_book(
                        source_id="3",
                        title="Zabíjení",
                        authors=["Štěpán Kopřiva"],
                        language="cs",
                    ).model_copy(update={"source": "audioteka"}),
                    make_book(
                        source_id="4",
                        title="Kdo dává pokyny k zabíjení civilistů na Ukrajině?",
                        authors=["Andrea Procházková", "Erik Tabery"],
                        language="cs",
                    ).model_copy(update={"source": "audioteka"}),
                ],
            ),
        ],
        normalizer=AudiobookshelfNormalizer(),
        detail_enrichment_limit=1,
    )

    response = asyncio.run(service.search(query="zabíjení", author="štěpán kopřiva"))

    assert [match.title for match in response.matches] == ["Zabíjení", "Zabíjení"]
    assert {match.author for match in response.matches} == {"Štěpán Kopřiva"}
    assert all(match.matchConfidence == 1.0 for match in response.matches)


def test_provider_service_ignores_slow_scraper_and_returns_fast_results() -> None:
    fast_book = make_book(
        source_id="1",
        title="1984",
        authors=["George Orwell"],
        language="cs",
    )

    service = MetadataProviderService(
        scrapers=[
            SlowScraper("slow", delay_seconds=0.05),
            StaticScraper("audiolibrix", [fast_book]),
        ],
        normalizer=AudiobookshelfNormalizer(),
        detail_enrichment_limit=1,
        scraper_timeout_seconds=0.01,
    )

    response = asyncio.run(service.search(query="1984", author="George Orwell"))

    assert [match.title for match in response.matches] == ["1984"]
    assert [match.author for match in response.matches] == ["George Orwell"]
    assert response.matches[0].matchConfidence == 1.0


def test_provider_service_returns_empty_matches_when_all_scrapers_time_out() -> None:
    service = MetadataProviderService(
        scrapers=[SlowScraper("slow", delay_seconds=0.05)],
        normalizer=AudiobookshelfNormalizer(),
        detail_enrichment_limit=1,
        scraper_timeout_seconds=0.01,
    )

    response = asyncio.run(service.search(query="1984", author="George Orwell"))

    assert response.matches == []
