from __future__ import annotations

from pathlib import Path

from app.services.scrapers.onehotbook import OneHotBookScraper


FIXTURES_DIR = Path(__file__).parent / "fixtures"


class DummyHttpClient:
    async def get_text(self, *args, **kwargs) -> str:
        raise AssertionError("Network access is not expected in parser tests")


def build_scraper() -> OneHotBookScraper:
    return OneHotBookScraper(http_client=DummyHttpClient())  # type: ignore[arg-type]


def test_parse_search_results_fixture_extracts_products() -> None:
    html = (FIXTURES_DIR / "onehotbook_search_1984.html").read_text(encoding="utf-8")

    results = build_scraper().parse_search_results(html)

    assert len(results) == 3
    assert results[0].source_id == "6225104404674"
    assert results[0].title == "1984"
    assert results[0].authors == ["George Orwell"]
    assert results[0].narrators == ["David Novotný"]
    assert results[0].publishers == ["OneHotBook"]
    assert results[0].published_year == "2021"
    assert results[0].genres == ["Moderní klasika", "Sci-fi", "Sci-fi a fantasy", "Světová literatura"]
    assert results[0].description is not None
    assert "Svoboda je svoboda říkat" in results[0].description
    assert results[0].detail_url == "https://onehotbook.cz/products/1984"


def test_parse_detail_page_fixture_extracts_enriched_metadata() -> None:
    search_html = (FIXTURES_DIR / "onehotbook_search_1984.html").read_text(encoding="utf-8")
    detail_html = (FIXTURES_DIR / "onehotbook_detail_1984.html").read_text(encoding="utf-8")
    scraper = build_scraper()
    partial = scraper.parse_search_results(search_html)[0]

    enriched = scraper.parse_detail_page(detail_html, partial=partial)

    assert enriched.title == "1984"
    assert enriched.authors == ["George Orwell"]
    assert enriched.narrators == ["David Novotný", "Zbyšek Horák"]
    assert enriched.publishers == ["OneHotBook"]
    assert enriched.published_year == "2021"
    assert enriched.language == "cs"
    assert enriched.duration_minutes == 661
    assert enriched.description is not None
    assert "Velkého bratra" in enriched.description
    assert enriched.detail_loaded is True
