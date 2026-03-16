from __future__ import annotations

import asyncio
import base64
import json
from pathlib import Path
from typing import Any
from urllib.parse import unquote

from app.services.scrapers.luxor import LuxorScraper


FIXTURES_DIR = Path(__file__).parent / "fixtures"


class DummyHttpClient:
    async def get_json(self, *args, **kwargs) -> dict[str, Any]:
        raise AssertionError("Network access is not expected in parser tests")


class RecordingHttpClient:
    def __init__(self, payloads: list[dict[str, Any]]) -> None:
        self._payloads = payloads
        self.calls: list[tuple[str, dict[str, Any] | None]] = []

    async def get_json(self, url: str, *args, **kwargs) -> dict[str, Any]:
        params = kwargs.get("params")
        self.calls.append((url, params))
        if self._payloads:
            return self._payloads.pop(0)
        return {}


def build_scraper() -> LuxorScraper:
    return LuxorScraper(http_client=DummyHttpClient())  # type: ignore[arg-type]


def decode_request_param(value: str) -> dict[str, Any]:
    raw_payload = base64.b64decode(unquote(value)).decode("utf-8")
    decoded = json.loads(raw_payload)
    assert isinstance(decoded, dict)
    return decoded


def test_parse_search_response_fixture_filters_to_audiobooks() -> None:
    payload = json.loads((FIXTURES_DIR / "luxor_search_1984.json").read_text(encoding="utf-8"))

    results = build_scraper().parse_search_response(payload)
    onehotbook = next(book for book in results if book.source_id == "1963003")
    radioservis = next(book for book in results if book.source_id == "2106420")

    assert len(results) == 6
    assert onehotbook.title == "1984"
    assert onehotbook.authors == ["George Orwell"]
    assert onehotbook.publishers == ["OneHotBook"]
    assert onehotbook.description is not None
    assert "Winston Smith" in onehotbook.description
    assert onehotbook.cover_url == "https://img.luxor.cz/suggest/222/351/produkty/AK638255.jpg"
    assert onehotbook.detail_url == "https://www.luxor.cz/v/1963003/1984"
    assert onehotbook.genres == ["Fantasy a sci-fi"]
    assert onehotbook.language is None

    assert radioservis.authors[:2] == ["Petr Švehla", "Pavel Belšan"]
    assert radioservis.publishers == ["Radioservis a.s."]


def test_search_retries_with_title_only_when_author_phrase_returns_no_results() -> None:
    http_client = RecordingHttpClient(payloads=[{}, {}])
    scraper = LuxorScraper(http_client=http_client)  # type: ignore[arg-type]

    results = asyncio.run(scraper.search(query=" 1984 ", author="George Orwell"))

    assert results == []
    assert len(http_client.calls) == 2
    assert http_client.calls[0][0] == scraper.SEARCH_URL
    assert http_client.calls[1][0] == scraper.SEARCH_URL

    first_request = decode_request_param(http_client.calls[0][1]["params"])
    second_request = decode_request_param(http_client.calls[1][1]["params"])

    assert first_request["phrase"] == "1984"
    assert first_request["authorPhrase"] == "George Orwell"
    assert first_request["assortmants"] == [31, 20]
    assert first_request["catalogBase"] == 5
    assert "%" not in http_client.calls[0][1]["params"]

    assert second_request["phrase"] == "1984"
    assert second_request["authorPhrase"] is None
    assert second_request["assortmants"] == [31, 20]
