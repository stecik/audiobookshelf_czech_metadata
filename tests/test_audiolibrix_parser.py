from __future__ import annotations

from pathlib import Path

from app.services.scrapers.audiolibrix import AudiolibrixScraper


FIXTURES_DIR = Path(__file__).parent / "fixtures"


class DummyHttpClient:
    async def get_text(self, *args, **kwargs) -> str:
        raise AssertionError("Network access is not expected in parser tests")


def build_scraper() -> AudiolibrixScraper:
    return AudiolibrixScraper(http_client=DummyHttpClient())  # type: ignore[arg-type]


def test_parse_search_results_fixture_extracts_cards() -> None:
    html = (FIXTURES_DIR / "audiolibrix_search_1984.html").read_text(encoding="utf-8")

    results = build_scraper().parse_search_results(html)

    assert len(results) == 64
    assert results[0].source_id == "144"
    assert results[0].title == "1984"
    assert results[0].authors == ["George Orwell"]
    assert results[0].narrators == ["Jiří Ornest"]
    assert results[0].cover_url is not None
    assert results[0].detail_url.endswith("/cs/Directory/Book/144/Audiokniha-1984-George-Orwell")


def test_parse_detail_page_fixture_extracts_enriched_metadata() -> None:
    search_html = (FIXTURES_DIR / "audiolibrix_search_1984.html").read_text(encoding="utf-8")
    detail_html = (FIXTURES_DIR / "audiolibrix_detail_1984.html").read_text(encoding="utf-8")
    scraper = build_scraper()
    partial = next(book for book in scraper.parse_search_results(search_html) if book.source_id == "8471")

    enriched = scraper.parse_detail_page(detail_html, partial=partial)

    assert enriched.title == "1984"
    assert enriched.publishers == ["Publixing", "SLOVART"]
    assert enriched.published_year == "2021"
    assert enriched.language == "sk"
    assert enriched.duration_minutes == 706
    assert enriched.genres == ["Klasika"]
    assert enriched.description is not None
    assert "Nové vydanie románu 1984" in enriched.description
