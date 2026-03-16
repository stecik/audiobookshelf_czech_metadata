from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from app.models import SourceBook
from app.services.scrapers.naposlech import NaposlechScraper


FIXTURES_DIR = Path(__file__).parent / "fixtures"


class DummyHttpClient:
    async def get_json(self, *args, **kwargs) -> object:
        raise AssertionError("Network access is not expected in parser tests")

    async def get_text(self, *args, **kwargs) -> str:
        raise AssertionError("Network access is not expected in parser tests")


class RecordingHttpClient:
    def __init__(self) -> None:
        self.last_url: str | None = None
        self.last_params: dict[str, Any] | None = None

    async def get_json(self, url: str, *args, **kwargs) -> object:
        self.last_url = url
        self.last_params = kwargs.get("params")
        return []


def build_scraper() -> NaposlechScraper:
    return NaposlechScraper(http_client=DummyHttpClient())  # type: ignore[arg-type]


def test_parse_search_results_fixture_extracts_api_matches() -> None:
    payload = json.loads((FIXTURES_DIR / "naposlech_search_1984.json").read_text(encoding="utf-8"))

    results = build_scraper().parse_search_results(payload)

    assert len(results) == 3
    assert results[0].source_id == "107223"
    assert results[0].title == "1984"
    assert results[0].detail_url == "https://naposlech.cz/audiokniha/1984-4-2/"
    assert (
        results[0].description
        == "Ve zbídačelém Londýně na území superstátu Oceánie se v dubnu 1984 úředník Ministerstva pravdy Winston Smith přiměje vzepřít."
    )
    assert results[0].detail_loaded is False


def test_parse_detail_page_fixture_extracts_enriched_metadata() -> None:
    html = (FIXTURES_DIR / "naposlech_detail_1984.html").read_text(encoding="utf-8")
    partial = SourceBook(
        source="naposlech",
        source_id="107223",
        title="1984",
        detail_url="https://naposlech.cz/audiokniha/1984-4-2/",
        description="Ve zbídačelém Londýně...",
    )

    enriched = build_scraper().parse_detail_page(html, partial=partial)

    assert enriched.title == "1984"
    assert enriched.authors == ["George Orwell"]
    assert enriched.narrators == ["Vasil Fridrich"]
    assert enriched.publishers == ["Tympanum"]
    assert enriched.published_year == "2021"
    assert enriched.cover_url == "https://naposlech.cz/wp-content/uploads/2024/09/8681.jpg"
    assert enriched.genres == ["Klasika", "Novely a povídky", "Společenská próza"]
    assert enriched.duration_minutes == 714
    assert enriched.description is not None
    assert "text: Tympanum" not in enriched.description
    assert enriched.description.startswith("Naděje na změnu se mu naskytne")
    assert enriched.detail_loaded is True


def test_search_uses_title_only_for_upstream_query_when_author_is_provided() -> None:
    http_client = RecordingHttpClient()
    scraper = NaposlechScraper(http_client=http_client)  # type: ignore[arg-type]

    results = asyncio.run(scraper.search(query=" 1984 ", author="George Orwell"))

    assert results == []
    assert http_client.last_url == scraper.SEARCH_URL
    assert http_client.last_params == {"search": "1984", "per_page": scraper.SEARCH_PAGE_SIZE}
