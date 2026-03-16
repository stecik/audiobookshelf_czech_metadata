from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from app.services.scrapers.megaknihy import MegaknihyScraper


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


def build_scraper() -> MegaknihyScraper:
    return MegaknihyScraper(http_client=DummyHttpClient())  # type: ignore[arg-type]


def test_parse_search_results_fixture_extracts_audiobook_hits_only() -> None:
    html = (FIXTURES_DIR / "megaknihy_search_sikmy_kostel.html").read_text(encoding="utf-8")

    results = build_scraper().parse_search_results(html)

    assert [result.source_id for result in results] == ["513791", "25999450", "3152506", "404276"]
    assert results[0].title == "Šikmý kostel"
    assert results[0].authors == ["Karin Lednická"]
    assert results[0].publishers == ["OneHotBook"]
    assert results[0].detail_url == "https://www.megaknihy.cz/audioknihy/513791-sikmy-kostel.html"
    assert results[0].detail_loaded is False
    assert "3216906" not in [result.source_id for result in results]
    assert "3210426" not in [result.source_id for result in results]


def test_parse_detail_page_fixture_extracts_enriched_metadata() -> None:
    search_html = (FIXTURES_DIR / "megaknihy_search_sikmy_kostel.html").read_text(encoding="utf-8")
    detail_html = (FIXTURES_DIR / "megaknihy_detail_sikmy_kostel.html").read_text(encoding="utf-8")
    scraper = build_scraper()
    partial = scraper.parse_search_results(search_html)[0]

    enriched = scraper.parse_detail_page(detail_html, partial=partial)

    assert enriched.title == "Šikmý kostel"
    assert enriched.authors == ["Karin Lednická"]
    assert enriched.narrators == []
    assert enriched.publishers == ["OneHotBook"]
    assert enriched.published_year == "2020"
    assert enriched.language == "cs"
    assert enriched.cover_url == "https://img-cloud.megaknihy.cz/513791-large/3a8bfbee70832e3e5380e4a51cf08eb4/sikmy-kostel.jpg"
    assert enriched.genres == [
        "Historické",
        "Povídky, příběhy",
        "Románová kronika",
        "Historický příběh",
        "česká próza",
    ]
    assert enriched.description is not None
    assert "ztraceného města" in enriched.description
    assert enriched.detail_loaded is True


def test_search_uses_title_only_for_upstream_query_when_author_is_provided() -> None:
    http_client = RecordingHttpClient()
    scraper = MegaknihyScraper(http_client=http_client)  # type: ignore[arg-type]

    results = asyncio.run(scraper.search(query="  Šikmý   kostel ", author="Karin Lednická"))

    assert results == []
    assert http_client.last_url == scraper.SEARCH_URL
    assert http_client.last_params == {
        "orderby": "position",
        "orderway": "desc",
        "search_query": "Šikmý kostel",
    }
