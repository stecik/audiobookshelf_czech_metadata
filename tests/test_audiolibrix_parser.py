from __future__ import annotations

from pathlib import Path

from app.models import SourceBook
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


def test_parse_detail_page_excludes_collapsed_narrator_toggle_label() -> None:
    html = """
    <html>
      <body>
        <h1 itemprop="name">Audiokniha Zapomenutá vražda</h1>
        <dl class="alx-metadata">
          <dt>Interpreti:</dt>
          <dd>
            <a href="/cs/Directory/Narrator/25/ruzena-merunkova">Růžena Merunková</a>,
            <a href="/cs/Directory/Narrator/587/jitka-jezkova">Jitka Ježková</a>,
            <a class="d-block small alx-collapse-exit" data-toggle="collapse" href="#more-narrators">další interpreti (1)</a>
            <div id="more-narrators" class="collapse">
              <a href="/cs/Directory/Narrator/1879/jan-meduna">Jan Meduna</a>
            </div>
          </dd>
          <dt>Vydavatel:</dt>
          <dd><a href="/cs/Directory/Publisher/42/vysehrad">Vyšehrad</a></dd>
          <dt>Žánr:</dt>
          <dd><a href="/cs/Directory/Books/4/detektivky">Detektivky</a></dd>
          <dt>Jazyk:</dt>
          <dd>čeština</dd>
          <dt>Délka:</dt>
          <dd>6h 8m</dd>
        </dl>
        <article class="card">
          <h2 class="card-title">Anotace</h2>
          <div class="card-body">Ukázková anotace.</div>
        </article>
      </body>
    </html>
    """
    partial = SourceBook(
        source="audiolibrix",
        source_id="5456",
        title="Zapomenutá vražda",
        detail_url="https://www.audiolibrix.com/cs/Directory/Book/5456/Audiokniha-Zapomenuta-vrazda-Agatha-Christie",
        authors=["Agatha Christie"],
    )

    enriched = build_scraper().parse_detail_page(html, partial=partial)

    assert enriched.narrators == ["Růžena Merunková", "Jitka Ježková", "Jan Meduna"]
