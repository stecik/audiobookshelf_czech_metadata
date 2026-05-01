from __future__ import annotations

import asyncio
from pathlib import Path

from app.services.scrapers.audioteka import AudiotekaScraper


FIXTURES_DIR = Path(__file__).parent / "fixtures"
EMPTY_SEARCH_RESULTS_HTML = """
<script>
self.__next_f.push([1,"7:[[\\\"$\\\",\\\"$L26\\\",null,{\\\"products\\\":{\\\"page\\\":1,\\\"limit\\\":30,\\\"pages\\\":0,\\\"total\\\":0,\\\"sort\\\":\\\"\\\",\\\"order\\\":\\\"\\\",\\\"_embedded\\\":{\\\"app:product\\\":[]}},\\\"phrase\\\":\\\"Maigretův zloděj\\\"}]]"])
</script>
"""
UNAVAILABLE_DETAIL_HTML = """
<html>
  <head>
    <meta
      name="description"
      content="Maigretův zloděj - detektivní případ komisaře Maigreta z pera Georgese Simenona."
    />
  </head>
  <body>
    <script>
      self.__next_f.push([1,"x \\"audiobook\\":{\\"name\\":\\"Maigretův zloděj\\",\\"id\\":\\"maigret-123\\",\\"image_url\\":\\"https://atkcdn.audioteka.com/cc/97/maigretuv-zlodej/19.jpg\\",\\"published_at\\":\\"2011-01-01\\",\\"content_language\\":\\"čeština\\",\\"duration\\":63,\\"description\\":\\"Maigretův zloděj - detektivní případ komisaře Maigreta z pera Georgese Simenona.\\",\\"_embedded\\":{\\"app:author\\":[{\\"name\\":\\"Georges Simenon\\"}],\\"app:lector\\":[{\\"name\\":\\"Jan Libíček\\"}],\\"app:publisher\\":[{\\"name\\":\\"Radioservis\\"}],\\"app:category\\":[{\\"name\\":\\"Detektivky, thrillery\\"}]}},\\"currency\\":\\"CZK\\" y"])
    </script>
  </body>
</html>
"""


class DummyHttpClient:
    async def get_text(self, *args, **kwargs) -> str:
        raise AssertionError("Network access is not expected in parser tests")


class FallbackHttpClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []

    async def get_text(self, url: str, *args, **kwargs) -> str:
        self.calls.append((url, kwargs.get("params")))
        if "vyhledavani" in url:
            return EMPTY_SEARCH_RESULTS_HTML
        if url.endswith("/cz/audiokniha/maigretuv-zlodej/"):
            return UNAVAILABLE_DETAIL_HTML
        raise AssertionError(f"Unexpected URL {url}")


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


def test_search_falls_back_to_guessed_unavailable_detail_page() -> None:
    http_client = FallbackHttpClient()
    scraper = AudiotekaScraper(http_client=http_client)  # type: ignore[arg-type]

    results = asyncio.run(scraper.search(query="Maigretův zloděj", author="Georges Simenon"))

    assert len(results) == 1
    assert results[0].source_id == "maigret-123"
    assert results[0].title == "Maigretův zloděj"
    assert results[0].authors == ["Georges Simenon"]
    assert results[0].narrators == ["Jan Libíček"]
    assert results[0].publishers == ["Radioservis"]
    assert results[0].language == "cs"
    assert results[0].duration_minutes == 63
    assert results[0].detail_url == "https://audioteka.com/cz/audiokniha/maigretuv-zlodej/"
    assert results[0].detail_loaded is True
