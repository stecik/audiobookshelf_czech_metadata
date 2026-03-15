from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from app.services.scrapers.albatrosmedia import AlbatrosMediaScraper


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


def build_scraper() -> AlbatrosMediaScraper:
    return AlbatrosMediaScraper(http_client=DummyHttpClient())  # type: ignore[arg-type]


def test_parse_search_results_fixture_extracts_audiobook_card() -> None:
    html = (FIXTURES_DIR / "albatrosmedia_search_podzimni_desy.html").read_text(encoding="utf-8")

    results = build_scraper().parse_search_results(html)

    assert len(results) == 1
    assert results[0].source_id == "88162947"
    assert results[0].title == "Podzimní děsy"
    assert results[0].authors == ["Agatha Christie"]
    assert results[0].publishers == ["Voxi"]
    assert results[0].language == "cs"
    assert results[0].description == "Zločiny sychravých dnů a nocí"
    assert results[0].detail_url == "https://www.albatrosmedia.cz/tituly/88162947/podzimni-desy-audiokniha/"


def test_parse_detail_page_fixture_extracts_enriched_metadata() -> None:
    search_html = (FIXTURES_DIR / "albatrosmedia_search_podzimni_desy.html").read_text(encoding="utf-8")
    detail_html = (FIXTURES_DIR / "albatrosmedia_detail_podzimni_desy.html").read_text(encoding="utf-8")
    scraper = build_scraper()
    partial = scraper.parse_search_results(search_html)[0]

    enriched = scraper.parse_detail_page(detail_html, partial=partial)

    assert enriched.title == "Podzimní děsy"
    assert enriched.authors == ["Agatha Christie"]
    assert enriched.narrators == [
        "Růžena Merunková",
        "Aleš Procházka",
        "Jaromír Meduna",
        "Vojtěch Hájek",
        "Andrea Elsnerová",
        "Otakar Brousek ml.",
        "Saša Rašilov",
        "Petr Neskusil",
        "Dagmar Čárová",
        "Klára Suchá",
    ]
    assert enriched.publishers == ["Voxi"]
    assert enriched.published_year == "2025"
    assert enriched.language == "cs"
    assert enriched.duration_minutes == 582
    assert enriched.genres == ["detektivka"]
    assert enriched.description is not None
    assert "dvanácti zapeklitých případů" in enriched.description
    assert enriched.detail_loaded is True


def test_search_uses_title_only_for_upstream_query_when_author_is_provided() -> None:
    http_client = RecordingHttpClient()
    scraper = AlbatrosMediaScraper(http_client=http_client)  # type: ignore[arg-type]

    results = asyncio.run(scraper.search(query="  Podzimní   děsy ", author="Agatha Christie"))

    assert results == []
    assert http_client.last_url == scraper.SEARCH_URL
    assert http_client.last_params == {"Text": "Podzimní děsy"}
