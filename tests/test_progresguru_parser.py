from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from app.services.scrapers.progresguru import ProgresGuruScraper


FIXTURES_DIR = Path(__file__).parent / "fixtures"


class DummyHttpClient:
    async def get_json(self, *args, **kwargs) -> dict[str, Any]:
        raise AssertionError("Network access is not expected in parser tests")


class RecordingHttpClient:
    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self._responses = responses
        self.calls: list[dict[str, Any]] = []

    async def get_json(self, url: str, *args, **kwargs) -> dict[str, Any]:
        self.calls.append(
            {
                "url": url,
                "params": kwargs.get("params"),
            }
        )
        return self._responses.pop(0)


def load_fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))


def build_scraper() -> ProgresGuruScraper:
    return ProgresGuruScraper(http_client=DummyHttpClient())  # type: ignore[arg-type]


def test_parse_search_response_fixture_extracts_match() -> None:
    payload = load_fixture("progresguru_api_search_okamzita.json")

    results = build_scraper().parse_search_response(payload)

    assert len(results) == 1
    assert results[0].source_id == "okamzita-pomoc-proti-uzkosti-hanson-mckay"
    assert results[0].title == "Okamžitá pomoc proti úzkosti"
    assert results[0].authors == ["Rick Hanson"]
    assert results[0].narrators == ["Miroslav Černý"]
    assert results[0].published_year == "2025"
    assert results[0].genres == ["Psychologie"]
    assert results[0].tags == ["Novinky"]
    assert (
        results[0].detail_url
        == "https://progresguru.cz/audioknihy/okamzita-pomoc-proti-uzkosti-hanson-mckay"
    )


def test_parse_detail_response_fixture_extracts_enriched_metadata() -> None:
    search_payload = load_fixture("progresguru_api_search_okamzita.json")
    detail_payload = load_fixture("progresguru_api_detail_okamzita_pomoc_proti_uzkosti.json")
    scraper = build_scraper()
    partial = scraper.parse_search_response(search_payload)[0]

    enriched = scraper.parse_detail_response(detail_payload, partial=partial)

    assert enriched.title == "Okamžitá pomoc proti úzkosti"
    assert enriched.subtitle == "Jak nalézt klid právě teď a jak se postavit obavám a úzkostem"
    assert enriched.authors == ["Rick Hanson", "Matthew McKay"]
    assert enriched.narrators == ["Miroslav Černý"]
    assert enriched.publishers == ["Tympanum"]
    assert enriched.published_year == "2025"
    assert enriched.language == "cs"
    assert enriched.duration_minutes == 199
    assert enriched.genres == ["Psychologie"]
    assert enriched.tags == ["Novinky"]
    assert enriched.description is not None
    assert "Čtyřicet nejjednodušších a nejefektivnějších technik" in enriched.description
    assert (
        enriched.cover_url
        == "https://api.progresguru.cz/images/cover/1755521750_okamzita-pomoc-pri-uzkosti-hanson-mckay-audiokniha-progresgurur..jpg"
    )
    assert enriched.detail_loaded is True


def test_search_falls_back_to_title_only_when_combined_query_returns_no_results() -> None:
    http_client = RecordingHttpClient(
        responses=[
            {"audiobooks": [], "last_valid_page": 0, "total": 0},
            load_fixture("progresguru_api_search_okamzita.json"),
        ]
    )
    scraper = ProgresGuruScraper(http_client=http_client)  # type: ignore[arg-type]

    results = asyncio.run(scraper.search(query="Okamžitá pomoc proti úzkosti", author="Matthew McKay"))

    assert len(results) == 1
    assert http_client.calls == [
        {
            "url": scraper.SEARCH_URL,
            "params": {"search": "Okamžitá pomoc proti úzkosti Matthew McKay", "page": 1},
        },
        {
            "url": scraper.SEARCH_URL,
            "params": {"search": "Okamžitá pomoc proti úzkosti", "page": 1},
        },
    ]
