from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from app.services.scrapers.o2knihovna import O2KnihovnaScraper


FIXTURES_DIR = Path(__file__).parent / "fixtures"


class DummyHttpClient:
    async def get_text(self, *args, **kwargs) -> str:
        raise AssertionError("Network access is not expected in parser tests")


class RecordingHttpClient:
    def __init__(self) -> None:
        self.last_url: str | None = None
        self.last_params: dict[str, Any] | None = None

    async def get_text(self, url: str, *args, **kwargs) -> str:
        self.last_url = url
        self.last_params = kwargs.get("params")
        return ""


def build_scraper() -> O2KnihovnaScraper:
    return O2KnihovnaScraper(http_client=DummyHttpClient())  # type: ignore[arg-type]


def test_parse_search_results_fixture_extracts_audiobook_cards() -> None:
    html = (FIXTURES_DIR / "o2knihovna_search_1984.html").read_text(encoding="utf-8")

    results = build_scraper().parse_search_results(html)

    assert len(results) == 3
    assert results[0].source_id == "ab2-95976ae8-2f4e-4b37-8e3d-cfd91ce13aa8"
    assert results[0].title == "1984"
    assert (
        results[0].detail_url
        == "https://www.o2knihovna.cz/audioknihy/ab2-95976ae8-2f4e-4b37-8e3d-cfd91ce13aa8"
    )
    assert (
        results[0].cover_url
        == "https://www.o2knihovna.cz/generated/covers/97/ab2-95976ae8-2f4e-4b37-8e3d-cfd91ce13aa8-360-970e.jpg"
    )


def test_parse_detail_page_fixture_extracts_enriched_metadata() -> None:
    search_html = (FIXTURES_DIR / "o2knihovna_search_1984.html").read_text(encoding="utf-8")
    detail_html = (FIXTURES_DIR / "o2knihovna_detail_1984.html").read_text(encoding="utf-8")
    scraper = build_scraper()
    partial = scraper.parse_search_results(search_html)[2]

    enriched = scraper.parse_detail_page(detail_html, partial=partial)

    assert enriched.title == "1984"
    assert enriched.authors == ["George Orwell"]
    assert enriched.narrators == ["Jaromír Meduna", "Jitka Moučková", "Jan Vondráček"]
    assert enriched.publishers == ["Audiostory"]
    assert enriched.published_year == "2021"
    assert enriched.language == "cs"
    assert enriched.duration_minutes == 711
    assert enriched.genres == ["Zahraniční literatura", "Klasická díla", "Povinná četba"]
    assert enriched.description is not None
    assert "Byl jasný, studený dubnový den" in enriched.description
    assert enriched.detail_loaded is True


def test_search_uses_title_only_for_upstream_query_when_author_is_provided() -> None:
    http_client = RecordingHttpClient()
    scraper = O2KnihovnaScraper(http_client=http_client)  # type: ignore[arg-type]

    results = asyncio.run(scraper.search(query=" 1984 ", author="George Orwell"))

    assert results == []
    assert http_client.last_url == scraper.SEARCH_URL
    assert http_client.last_params == {"q": "1984"}
