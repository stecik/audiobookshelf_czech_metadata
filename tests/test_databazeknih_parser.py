from __future__ import annotations

from pathlib import Path

from app.services.scrapers.databazeknih import DatabazeKnihScraper


FIXTURES_DIR = Path(__file__).parent / "fixtures"


class DummyHttpClient:
    async def get_text(self, *args, **kwargs) -> str:
        raise AssertionError("Network access is not expected in parser tests")


def build_scraper() -> DatabazeKnihScraper:
    return DatabazeKnihScraper(http_client=DummyHttpClient())  # type: ignore[arg-type]


def test_parse_search_results_extracts_books() -> None:
    html = (FIXTURES_DIR / "databazeknih_search_1984.html").read_text(encoding="utf-8")

    results = build_scraper().parse_search_results(html)

    assert len(results) == 2
    assert results[0].source_id == "283"
    assert results[0].title == "1984"
    assert results[0].authors == ["George Orwell"]
    assert results[0].published_year == "2003"
    assert results[0].cover_url == "https://www.databazeknih.cz/img/books/28_/283/1984.png"
    assert results[0].language == "cs"


def test_parse_detail_page_enriches_search_result() -> None:
    search_html = (FIXTURES_DIR / "databazeknih_search_1984.html").read_text(encoding="utf-8")
    detail_html = (FIXTURES_DIR / "databazeknih_detail_1984.html").read_text(encoding="utf-8")
    scraper = build_scraper()
    partial = scraper.parse_search_results(search_html)[0]

    enriched = scraper.parse_detail_page(detail_html, partial=partial)

    assert enriched.title == "1984"
    assert enriched.authors == ["George Orwell"]
    assert enriched.publishers == ["Levné knihy"]
    assert enriched.published_year == "2003"
    assert enriched.language == "cs"
    assert enriched.cover_url == "https://www.databazeknih.cz/img/books/28_/283/1984.png"
    assert enriched.genres == ["Literatura světová", "Romány", "Sci-fi"]
    assert enriched.description is not None
    assert "Velký bratr tě sleduje" in enriched.description
    assert "... celý text" not in enriched.description
    assert enriched.detail_loaded is True
