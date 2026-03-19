from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from app.services.scrapers.alza import AlzaScraper


FIXTURES_DIR = Path(__file__).parent / "fixtures"


class DummyHttpClient:
    async def get_text(self, *args, **kwargs) -> str:
        raise AssertionError("Network access is not expected in parser tests")


class RecordingHttpClient:
    def __init__(self) -> None:
        self.last_url: str | None = None
        self.last_params: dict[str, Any] | None = None
        self.last_extra_headers: dict[str, str] | None = None

    async def get_text(self, url: str, *args, **kwargs) -> str:
        self.last_url = url
        self.last_params = kwargs.get("params")
        self.last_extra_headers = kwargs.get("extra_headers")
        return ""

    @property
    def timeout_seconds(self) -> float:
        return 1.0


def build_scraper() -> AlzaScraper:
    return AlzaScraper(http_client=DummyHttpClient())  # type: ignore[arg-type]


def test_parse_search_results_fixture_extracts_alza_products() -> None:
    html = (FIXTURES_DIR / "alza_search_1984.html").read_text(encoding="utf-8")

    results = build_scraper().parse_search_results(html)

    assert len(results) == 2
    assert results[0].source_id == "403933"
    assert results[0].title == "1984"
    assert results[0].authors == ["George Orwell"]
    assert results[0].narrators == ["Jaromír Meduna", "Jitka Moučková", "Jan Vondráček"]
    assert results[0].description == "Dystopický román"
    assert results[0].duration_minutes == 711
    assert results[0].detail_url == "https://www.alza.cz/media/1984-d403933.htm"


def test_parse_detail_page_fixture_extracts_enriched_metadata() -> None:
    search_html = (FIXTURES_DIR / "alza_search_1984.html").read_text(encoding="utf-8")
    detail_html = (FIXTURES_DIR / "alza_detail_1984.html").read_text(encoding="utf-8")
    scraper = build_scraper()
    partial = scraper.parse_search_results(search_html)[0]

    enriched = scraper.parse_detail_page(detail_html, partial=partial)

    assert enriched.title == "1984"
    assert enriched.authors == ["George Orwell"]
    assert enriched.narrators == ["Veronika Freimanová", "Martin Stránský"]
    assert enriched.publishers == ["Radioservis"]
    assert enriched.published_year == "2021"
    assert enriched.language == "cs"
    assert enriched.duration_minutes == 715
    assert enriched.genres == ["Klasická díla", "Zahraniční literatura"]
    assert enriched.cover_url == "https://cdn.alza.cz/ImgW.ashx?fd=f3&cd=AK1C638"
    assert enriched.description is not None
    assert "Velký bratr" in enriched.description
    assert enriched.detail_loaded is True


def test_parse_detail_page_prefers_open_graph_description_over_noisy_content() -> None:
    html = """
    <html lang="cs">
      <head>
        <meta property="og:url" content="https://www.alza.cz/media/1984-d6308258.htm" />
        <meta name="og:description" content="Antiutopický román George Orwella 1984 v novém audioknižním zpracování&nbsp;Byl jasný, studený dubnový den." />
      </head>
      <body>
        <main>
          <h1>1984</h1>
          <div id="description">
            <div class="popis__content" id="descriptionContent"></div>
          </div>
          <p>{"@context":"https://schema.org","description":"json noise"}</p>
          <p>AudioStory s.r.o., 16000 Praha 6, info@example.cz</p>
        </main>
      </body>
    </html>
    """

    parsed = build_scraper().parse_detail_page(html)

    assert (
        parsed.description
        == "Antiutopický román George Orwella 1984 v novém audioknižním zpracování Byl jasný, studený dubnový den."
    )


def test_search_uses_compound_upstream_query_when_author_is_provided() -> None:
    http_client = RecordingHttpClient()
    scraper = AlzaScraper(http_client=http_client)  # type: ignore[arg-type]

    try:
        asyncio.run(scraper.search(query="1984", author="George Orwell"))
    except Exception:
        pass

    assert http_client.last_url == scraper.MOBILE_SEARCH_URL
    assert http_client.last_params == {"exps": "1984 George Orwell"}
    assert http_client.last_extra_headers is not None
    assert http_client.last_extra_headers["User-Agent"].startswith("Mozilla/5.0")
