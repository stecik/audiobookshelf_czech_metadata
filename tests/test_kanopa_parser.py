from __future__ import annotations

import asyncio
from pathlib import Path

from app.services.scrapers.kanopa import KanopaScraper


FIXTURES_DIR = Path(__file__).parent / "fixtures"
EMPTY_SEARCH_HTML = "<html><body><div id='products'></div></body></html>"


class DummyHttpClient:
    async def get_text(self, *args, **kwargs) -> str:
        raise AssertionError("Network access is not expected in parser tests")


class RecordingHttpClient:
    def __init__(self, responses: list[str]) -> None:
        self._responses = responses
        self.calls: list[dict[str, object]] = []

    async def get_text(self, url: str, *args, **kwargs) -> str:
        self.calls.append(
            {
                "url": url,
                "params": kwargs.get("params"),
            }
        )
        return self._responses.pop(0)


def load_fixture(name: str) -> str:
    return (FIXTURES_DIR / name).read_text(encoding="utf-8")


def build_scraper() -> KanopaScraper:
    return KanopaScraper(http_client=DummyHttpClient())  # type: ignore[arg-type]


def test_parse_search_results_fixture_extracts_matches() -> None:
    html = load_fixture("kanopa_search_hypoteza_zla.html")

    results = build_scraper().parse_search_results(html)

    assert len(results) == 2
    assert results[0].source_id == "587"
    assert results[0].title == "Hypotéza zla"
    assert results[0].detail_url == "https://www.kanopa.cz/hypoteza-zla/"
    assert results[0].tags == ["Tip"]
    assert results[0].cover_url is not None
    assert "587_hypotezazla-2000x2000-nahledovka--1.jpg" in results[0].cover_url


def test_parse_detail_page_fixture_extracts_enriched_metadata() -> None:
    search_html = load_fixture("kanopa_search_hypoteza_zla.html")
    detail_html = load_fixture("kanopa_detail_hypoteza_zla.html")
    scraper = build_scraper()
    partial = scraper.parse_search_results(search_html)[0]

    enriched = scraper.parse_detail_page(detail_html, partial=partial)

    assert enriched.title == "Hypotéza zla"
    assert enriched.authors == ["Donato Carrisi"]
    assert enriched.narrators == ["Jan Šťastný"]
    assert enriched.publishers == ["KANOPA"]
    assert enriched.duration_minutes == 849
    assert enriched.genres == ["Detektivky", "Thrillery"]
    assert enriched.tags == ["Tip"]
    assert enriched.description is not None
    assert "napínavým pokračováním série o Miele Vasquezové" in enriched.description
    assert enriched.cover_url is not None
    assert "587_hypotezazla-2000x2000-nahledovka--1.jpg" in enriched.cover_url
    assert enriched.detail_loaded is True


def test_search_falls_back_to_title_only_when_combined_query_returns_no_results() -> None:
    http_client = RecordingHttpClient(
        responses=[
            EMPTY_SEARCH_HTML,
            load_fixture("kanopa_search_hypoteza_zla.html"),
        ]
    )
    scraper = KanopaScraper(http_client=http_client)  # type: ignore[arg-type]

    results = asyncio.run(scraper.search(query="Hypotéza zla", author="Donato Carrisi"))

    assert len(results) == 2
    assert results[0].title == "Hypotéza zla"
    assert http_client.calls == [
        {
            "url": scraper.SEARCH_URL,
            "params": {"string": "Hypotéza zla Donato Carrisi"},
        },
        {
            "url": scraper.SEARCH_URL,
            "params": {"string": "Hypotéza zla"},
        },
    ]
