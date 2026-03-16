from __future__ import annotations

import asyncio
from pathlib import Path

from app.services.scrapers.rozhlas import RozhlasScraper


FIXTURES_DIR = Path(__file__).parent / "fixtures"


class DummyHttpClient:
    async def get_text(self, *args, **kwargs) -> str:
        raise AssertionError("Network access is not expected in parser tests")


class RecordingHttpClient:
    def __init__(self, *, responses_by_query: dict[str, str]) -> None:
        self._responses_by_query = responses_by_query
        self.calls: list[tuple[str, dict[str, str | int | float | None] | None]] = []

    async def get_text(self, url: str, *, params=None) -> str:
        self.calls.append((url, params))
        query = (params or {}).get("combine")
        if query not in self._responses_by_query:
            raise AssertionError(f"Unexpected query: {query}")
        return self._responses_by_query[query]


def build_scraper(http_client=None) -> RozhlasScraper:
    return RozhlasScraper(http_client=http_client or DummyHttpClient())  # type: ignore[arg-type]


def test_parse_search_results_fixture_extracts_expected_items() -> None:
    html = (FIXTURES_DIR / "rozhlas_hry_a_cetba_listing.html").read_text(encoding="utf-8")

    results = build_scraper().parse_search_results(html)

    assert len(results) == 3

    beckett = results[0]
    assert beckett.source_id == "9602424"
    assert beckett.title == "Povídky Samuela Becketta, Maeve Binchyové, Williama Trevora, Edny O'Brienové a dalších autorů"
    assert beckett.authors == []
    assert beckett.duration_minutes is None
    assert beckett.detail_url == "https://vltava.rozhlas.cz/povidky-samuela-becketta-maeve-binchyove-williama-trevora-edny-obrienove-a-9602424"

    cinovy_vojacek = results[1]
    assert cinovy_vojacek.source_id == "8446539"
    assert cinovy_vojacek.authors == ["Hans Christian Andersen"]
    assert cinovy_vojacek.genres == ["Pohádka"]
    assert cinovy_vojacek.duration_minutes == 48
    assert cinovy_vojacek.cover_url == "https://temata.rozhlas.cz/sites/default/files/images/cinovy-vojacek.jpg"

    skorapka = results[2]
    assert skorapka.source_id == "9602125"
    assert skorapka.title == "Skořápka. Ivan Trojan, David Novotný a Bára Poláková v komické krimi parafrázi Hamleta"
    assert skorapka.authors == ["Ian McEwan"]
    assert skorapka.genres == ["Komedie"]
    assert skorapka.duration_minutes == 65


def test_parse_detail_page_fixture_extracts_audio_article_metadata() -> None:
    search_html = (FIXTURES_DIR / "rozhlas_hry_a_cetba_listing.html").read_text(encoding="utf-8")
    detail_html = (FIXTURES_DIR / "rozhlas_detail_cinovy_vojacek.html").read_text(encoding="utf-8")
    scraper = build_scraper()
    partial = scraper.parse_search_results(search_html)[1]

    enriched = scraper.parse_detail_page(detail_html, partial=partial)

    assert enriched.title == "Cínový vojáček a tanečnice. Andersenova pohádka s Lindou Rybovou a Ivanem Trojanem"
    assert enriched.authors == ["Hans Christian Andersen"]
    assert enriched.narrators == ["Klára Sedláčková - Oltová", "Linda Rybová", "Ivan Trojan"]
    assert enriched.publishers == ["Český rozhlas"]
    assert enriched.published_year == "2002"
    assert enriched.cover_url == "https://junior.rozhlas.cz/sites/default/files/poster-cinovy-vojacek.jpg"
    assert enriched.description == (
        "Pusťte si pohádku o veliké lásce, ale i podlosti a zradě. "
        "Dvě zamilované hračky musí čelit velkým nástrahám a krutému světu."
    )
    assert enriched.genres == ["Pohádka", "Pro děti"]
    assert enriched.language == "cs"
    assert enriched.duration_minutes == 48
    assert enriched.detail_loaded is True


def test_parse_detail_page_fixture_extracts_serial_metadata() -> None:
    search_html = (FIXTURES_DIR / "rozhlas_hry_a_cetba_listing.html").read_text(encoding="utf-8")
    detail_html = (FIXTURES_DIR / "rozhlas_detail_beckett.html").read_text(encoding="utf-8")
    scraper = build_scraper()
    partial = scraper.parse_search_results(search_html)[0]

    enriched = scraper.parse_detail_page(detail_html, partial=partial)

    assert enriched.title == "Povídky Samuela Becketta, Maeve Binchyové, Williama Trevora, Edny O'Brienové a dalších autorů"
    assert enriched.authors == ["Frank O'Connor", "Maeve Binchy", "Samuel Beckett", "Oscar Wilde"]
    assert enriched.narrators == [
        "Jaromír Meduna",
        "Dana Černá",
        "Norbert Lichý",
        "Jaroslav Kuneš",
        "Eva Jelínková",
        "Pavel Kunert",
        "Erik Pardus",
    ]
    assert enriched.publishers == ["Český rozhlas"]
    assert enriched.published_year == "2026"
    assert enriched.cover_url == "https://vltava.rozhlas.cz/sites/default/files/poster-beckett.jpg"
    assert enriched.description.startswith("Den svatého Patrika")
    assert enriched.genres == ["Četba", "Literatura"]
    assert enriched.language == "cs"
    assert enriched.duration_minutes == 169
    assert enriched.detail_loaded is True


def test_search_falls_back_to_query_only_when_combined_query_has_no_results() -> None:
    listing_html = (FIXTURES_DIR / "rozhlas_hry_a_cetba_listing.html").read_text(encoding="utf-8")
    empty_html = "<section id='b008d'><div class='view-empty'>empty</div></section>"
    http_client = RecordingHttpClient(
        responses_by_query={
            "Skořápka Ian McEwan": empty_html,
            "Skořápka": listing_html,
        }
    )
    scraper = build_scraper(http_client=http_client)

    results = asyncio.run(scraper.search(query="Skořápka", author="Ian McEwan"))

    assert [call[1] for call in http_client.calls] == [
        {"combine": "Skořápka Ian McEwan"},
        {"combine": "Skořápka"},
    ]
    assert any(book.source_id == "9602125" for book in results)
