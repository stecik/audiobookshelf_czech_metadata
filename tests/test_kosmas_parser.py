from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from app.services.scrapers.kosmas import KosmasScraper


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


def build_scraper() -> KosmasScraper:
    return KosmasScraper(http_client=DummyHttpClient())  # type: ignore[arg-type]


def test_parse_search_results_fixture_extracts_first_exact_match() -> None:
    html = (FIXTURES_DIR / "kosmas_search_1984.html").read_text(encoding="utf-8")

    results = build_scraper().parse_search_results(html)

    assert len(results) == 20
    assert results[0].source_id == "294615"
    assert results[0].title == "1984"
    assert results[0].authors == ["George Orwell"]
    assert results[0].publishers == ["Tympanum"]
    assert results[0].genres == ["beletrie", "světová"]
    assert results[0].cover_url == "https://obalky.kosmas.cz/ArticleCovers/294/615_base.jpg"
    assert results[0].detail_url == "https://www.kosmas.cz/knihy/294615/1984/"
    assert results[0].description is not None
    assert "distopického žánru" in results[0].description


def test_parse_detail_page_fixture_extracts_enriched_metadata() -> None:
    search_html = (FIXTURES_DIR / "kosmas_search_1984.html").read_text(encoding="utf-8")
    detail_html = (FIXTURES_DIR / "kosmas_detail_1984.html").read_text(encoding="utf-8")
    scraper = build_scraper()
    partial = scraper.parse_search_results(search_html)[0]

    enriched = scraper.parse_detail_page(detail_html, partial=partial)

    assert enriched.title == "1984"
    assert enriched.authors == ["George Orwell"]
    assert enriched.narrators == ["Vasil Fridrich"]
    assert enriched.publishers == ["Tympanum"]
    assert enriched.published_year == "2021"
    assert enriched.language == "cs"
    assert enriched.duration_minutes == 705
    assert enriched.genres == ["beletrie", "světová"]
    assert enriched.cover_url == "https://obalky.kosmas.cz/ArticleCovers/294/615_bg.jpg"
    assert enriched.description is not None
    assert "Winston Smith" in enriched.description
    assert enriched.detail_loaded is True


def test_search_uses_title_only_for_upstream_query_when_author_is_provided() -> None:
    http_client = RecordingHttpClient()
    scraper = KosmasScraper(http_client=http_client)  # type: ignore[arg-type]

    results = asyncio.run(scraper.search(query="  1984  ", author="George Orwell"))

    assert results == []
    assert http_client.last_url == scraper.SEARCH_URL
    assert http_client.last_params == {"sortBy": "relevance", "query": "1984"}
