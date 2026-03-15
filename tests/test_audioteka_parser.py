from __future__ import annotations

from pathlib import Path

from app.services.scrapers.audioteka import AudiotekaScraper


FIXTURES_DIR = Path(__file__).parent / "fixtures"


class DummyHttpClient:
    async def get_text(self, *args, **kwargs) -> str:
        raise AssertionError("Network access is not expected in parser tests")


def build_scraper() -> AudiotekaScraper:
    return AudiotekaScraper(http_client=DummyHttpClient())  # type: ignore[arg-type]


def test_parse_search_results_fixture_extracts_products() -> None:
    html = (FIXTURES_DIR / "audioteka_search_1984.html").read_text(encoding="utf-8")

    results = build_scraper().parse_search_results(html)

    assert len(results) == 2
    assert results[0].source_id == "b2b746c3-2271-4ff4-a272-f075eb382593"
    assert results[0].title == "1984"
    assert results[0].authors == ["George Orwell"]
    assert results[0].cover_url == "https://atkcdn.audioteka.com/cc/b2/1984-audiostory/68.jpg"
    assert results[0].detail_url.endswith("/cz/audiokniha/1984-audiostory/")


def test_parse_detail_page_fixture_extracts_enriched_metadata() -> None:
    search_html = (FIXTURES_DIR / "audioteka_search_1984.html").read_text(encoding="utf-8")
    detail_html = (FIXTURES_DIR / "audioteka_detail_1984.html").read_text(encoding="utf-8")
    scraper = build_scraper()
    partial = scraper.parse_search_results(search_html)[0]

    enriched = scraper.parse_detail_page(detail_html, partial=partial)

    assert enriched.title == "1984"
    assert enriched.authors == ["George Orwell"]
    assert enriched.narrators == ["Jan Vondráček", "Jaromír Meduna", "Jitka Moučková"]
    assert enriched.publishers == ["Audiostory"]
    assert enriched.published_year == "2021"
    assert enriched.language == "cs"
    assert enriched.duration_minutes == 711
    assert enriched.genres == ["Klasická díla", "Zahraniční literatura"]
    assert enriched.description is not None
    assert "literární klasiku George Orwella" in enriched.description
