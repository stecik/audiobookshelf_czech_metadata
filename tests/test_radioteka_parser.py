from __future__ import annotations

from pathlib import Path

from app.services.scrapers.radioteka import RadiotekaScraper


FIXTURES_DIR = Path(__file__).parent / "fixtures"


class DummyHttpClient:
    async def get_text(self, *args, **kwargs) -> str:
        raise AssertionError("Network access is not expected in parser tests")


def build_scraper() -> RadiotekaScraper:
    return RadiotekaScraper(http_client=DummyHttpClient())  # type: ignore[arg-type]


def test_parse_search_results_fixture_extracts_audiobook_cards() -> None:
    html = (FIXTURES_DIR / "radioteka_search_1984.html").read_text(encoding="utf-8")

    results = build_scraper().parse_search_results(html)

    assert len(results) == 10
    assert results[0].source_id == "655568"
    assert results[0].title == "1984"
    assert results[0].publishers == ["Publixing"]
    assert results[0].genres == ["Klasická literatura"]
    assert results[0].cover_url == (
        "https://www.radioteka.cz/im/bup/192/0/abooks/image/000/655/568/"
        "50603740320401_1_001001_imp_cover.jpg"
    )
    assert results[0].detail_url == "https://www.radioteka.cz/detail/croslovo-655568-1984"


def test_parse_detail_page_fixture_extracts_enriched_metadata() -> None:
    search_html = (FIXTURES_DIR / "radioteka_search_1984.html").read_text(encoding="utf-8")
    detail_html = (FIXTURES_DIR / "radioteka_detail_1984.html").read_text(encoding="utf-8")
    scraper = build_scraper()
    partial = scraper.parse_search_results(search_html)[0]

    enriched = scraper.parse_detail_page(detail_html, partial=partial)

    assert enriched.title == "1984"
    assert enriched.authors == ["George Orwell"]
    assert enriched.narrators == ["Ivo Gogál"]
    assert enriched.publishers == ["Publixing"]
    assert enriched.published_year == "2021"
    assert enriched.duration_minutes == 706
    assert enriched.genres == ["Klasická literatura"]
    assert enriched.cover_url == "https://storage.bookup.cz/abooks/image/000/655/568/50603740320401_1_001001_imp_cover.jpg"
    assert enriched.description is not None
    assert "komunistickej diktatúry" in enriched.description
