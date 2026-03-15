from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from app.models import SourceBook
from app.services.scrapers.palmknihy import PalmknihyScraper


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


def build_scraper() -> PalmknihyScraper:
    return PalmknihyScraper(http_client=DummyHttpClient())  # type: ignore[arg-type]


def test_parse_search_results_fixture_extracts_audiobook_only_match() -> None:
    html = (FIXTURES_DIR / "palmknihy_search_praskle_zrcadlo.html").read_text(encoding="utf-8")

    results = build_scraper().parse_search_results(html)

    assert len(results) == 1
    assert results[0].source_id == "362311"
    assert results[0].title == "Prasklé zrcadlo"
    assert results[0].authors == ["Agatha Christie"]
    assert results[0].publishers == ["Voxi"]
    assert results[0].published_year == "2022"
    assert results[0].genres == ["Krimi, detektivky"]
    assert results[0].language == "cs"
    assert results[0].detail_url == "https://www.palmknihy.cz/audiokniha/praskle-zrcadlo-362311"
    assert results[0].detail_loaded is False


def test_parse_detail_page_fixture_extracts_enriched_metadata_without_description() -> None:
    html = (FIXTURES_DIR / "palmknihy_detail_v_hotelu_bertram.html").read_text(encoding="utf-8")
    partial = SourceBook(
        source="palmknihy",
        source_id="404717",
        title="V hotelu Bertram",
        detail_url="https://www.palmknihy.cz/audiokniha/v-hotelu-bertram-404717",
        authors=["Agatha Christie"],
    )

    enriched = build_scraper().parse_detail_page(html, partial=partial)

    assert enriched.title == "V hotelu Bertram"
    assert enriched.authors == ["Agatha Christie"]
    assert enriched.publishers == ["Voxi"]
    assert enriched.published_year == "2024"
    assert enriched.genres == [
        "Krimi, detektivky",
        "Česká a světová beletrie",
        "Světová literatura",
        "Detektivky, thrillery a horory",
        "Beletrie",
    ]
    assert enriched.language == "cs"
    assert enriched.duration_minutes == 485
    assert enriched.description is None
    assert enriched.detail_loaded is True


def test_search_uses_title_only_for_upstream_query_when_author_is_provided() -> None:
    http_client = RecordingHttpClient()
    scraper = PalmknihyScraper(http_client=http_client)  # type: ignore[arg-type]

    results = asyncio.run(scraper.search(query="  Prasklé   zrcadlo ", author="Agatha Christie"))

    assert results == []
    assert http_client.last_url == scraper.SEARCH_URL
    assert http_client.last_params == {"query": "Prasklé zrcadlo"}
