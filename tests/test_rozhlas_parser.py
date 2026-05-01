from __future__ import annotations

import asyncio
from pathlib import Path

from app.services.scrapers.rozhlas import RozhlasScraper


FIXTURES_DIR = Path(__file__).parent / "fixtures"


class DummyHttpClient:
    async def get_text(self, *args, **kwargs) -> str:
        raise AssertionError("Network access is not expected in parser tests")


class RecordingHttpClient:
    def __init__(
        self,
        *,
        responses_by_query: dict[str, str],
        json_responses_by_query: dict[str, object] | None = None,
    ) -> None:
        self._responses_by_query = responses_by_query
        self._json_responses_by_query = json_responses_by_query or {}
        self.calls: list[
            tuple[str, str, dict[str, str | int | float | None] | None]
        ] = []

    async def get_text(self, url: str, *, params=None) -> str:
        self.calls.append(("text", url, params))
        query = (params or {}).get("combine")
        if query not in self._responses_by_query:
            raise AssertionError(f"Unexpected query: {query}")
        return self._responses_by_query[query]

    async def get_json(self, url: str, *, params=None) -> object:
        self.calls.append(("json", url, params))
        query = (params or {}).get("filter[fulltext][eq]")
        if query not in self._json_responses_by_query:
            raise AssertionError(f"Unexpected API query: {query}")
        return self._json_responses_by_query[query]


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
        },
        json_responses_by_query={"Skořápka Ian McEwan": {"data": []}},
    )
    scraper = build_scraper(http_client=http_client)

    results = asyncio.run(scraper.search(query="Skořápka", author="Ian McEwan"))

    assert [call[2] for call in http_client.calls] == [
        {"combine": "Skořápka Ian McEwan"},
        {
            "filter[fulltext][eq]": "Skořápka Ian McEwan",
            "page[limit]": scraper.API_PAGE_SIZE,
        },
        {"combine": "Skořápka"},
    ]
    assert any(book.source_id == "9602125" for book in results)


def test_search_uses_mujrozhlas_api_when_legacy_topic_has_no_results() -> None:
    empty_html = "<section id='b008d'><div class='view-empty'>empty</div></section>"
    api_payload = {
        "data": [
            {
                "id": "a202e915-fadc-3522-b660-7f306ab6c036",
                "type": "episode",
                "relationships": {
                    "genres": {
                        "data": [
                            {"attributes": {"title": "Světová literatura"}},
                        ]
                    }
                },
                "extraData": {
                    "categories": {
                        "data": [
                            {"attributes": {"title": "Hra", "type": "format"}},
                            {"attributes": {"title": "Literatura", "type": "topic"}},
                        ]
                    },
                    "remote": {"source": "drupal", "id": "9602125"},
                },
                "attributes": {
                    "title": "Ian McEwan: Skořápka. Ivan Trojan, David Novotný a Bára Poláková v komické krimi parafrázi Hamleta",
                    "description": (
                        "<p>Rozhlasová adaptace novely.</p>"
                        "Osoby a obsazení: Ivan Trojan (plod), Barbora Poláková (Trudy)<br>"
                        "Premiéra: 24. 11. 2020"
                    ),
                    "asset": {
                        "url": "https://portal.rozhlas.cz/sites/default/files/images/skorapka.jpg"
                    },
                    "audioLinks": [{"duration": 3900}],
                    "since": "2026-03-15T20:00:00+01:00",
                },
            }
        ]
    }
    http_client = RecordingHttpClient(
        responses_by_query={"Skořápka": empty_html},
        json_responses_by_query={"Skořápka": api_payload},
    )
    scraper = build_scraper(http_client=http_client)

    results = asyncio.run(scraper.search(query="Skořápka"))

    assert len(results) == 1
    result = results[0]
    assert result.source_id == "9602125"
    assert result.title == "Skořápka. Ivan Trojan, David Novotný a Bára Poláková v komické krimi parafrázi Hamleta"
    assert result.authors == ["Ian McEwan"]
    assert result.narrators == ["Ivan Trojan (plod)", "Barbora Poláková (Trudy)"]
    assert result.publishers == ["Český rozhlas"]
    assert result.published_year == "2026"
    assert result.cover_url == "https://portal.rozhlas.cz/sites/default/files/images/skorapka.jpg"
    assert result.genres == ["Světová literatura", "Hra", "Literatura"]
    assert result.duration_minutes == 65
    assert result.detail_loaded is True
