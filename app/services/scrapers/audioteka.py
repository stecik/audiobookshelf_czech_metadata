from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from selectolax.parser import HTMLParser

from app.clients.http import HttpClient
from app.models import SourceBook
from app.services.scrapers.base import BaseMetadataScraper
from app.utils.text import (
    extract_year,
    map_language_to_code,
    normalize_match_text,
    normalize_title,
    normalize_whitespace,
    to_absolute_url,
    unique_preserving_order,
)


@dataclass(frozen=True)
class AudiotekaSelectors:
    detail_meta_description: str = "meta[name='description']"


class AudiotekaScraper(BaseMetadataScraper):
    source_name = "audioteka"

    BASE_URL = "https://audioteka.com"
    STOREFRONT_URL = f"{BASE_URL}/cz"
    SEARCH_URL = f"{STOREFRONT_URL}/vyhledavani/"

    SEARCH_PRODUCTS_RE = re.compile(r'\\"products\\":(?P<payload>\{.*?\})\s*,\\"phrase\\":', re.S)
    DETAIL_AUDIOBOOK_RE = re.compile(r'\\"audiobook\\":(?P<payload>\{\\"name\\":.*?\})\s*,\\"currency\\":', re.S)
    DETAIL_REFERENCE_RE_TEMPLATE = (
        r'{reference}:T[0-9a-z]+,\"]\)\s*</script>\s*<script>\s*'
        r'self\.__next_f\.push\(\[1,"(?P<value>.*?)"\]\)\s*</script>'
    )

    def __init__(self, *, http_client: HttpClient) -> None:
        self._http_client = http_client
        self._selectors = AudiotekaSelectors()

    async def search(self, query: str, author: str | None = None) -> list[SourceBook]:
        phrase = self._compose_search_phrase(query=query, author=author)
        html = await self._http_client.get_text(self.SEARCH_URL, params={"phrase": phrase})
        return self.parse_search_results(html)

    async def enrich(self, item: SourceBook) -> SourceBook:
        html = await self._http_client.get_text(item.detail_url)
        return self.parse_detail_page(html, partial=item)

    def parse_search_results(self, html: str) -> list[SourceBook]:
        payload = self._extract_search_payload(html)
        if payload is None:
            return []

        books: list[SourceBook] = []
        products = payload.get("_embedded", {}).get("app:product", [])
        if not isinstance(products, list):
            return books

        for product in products:
            if not isinstance(product, dict):
                continue

            source_id = self._string(product.get("id")) or self._string(product.get("reference_id"))
            slug = self._string(product.get("slug"))
            title = normalize_title(self._string(product.get("name")))
            detail_url = to_absolute_url(self.BASE_URL, f"/cz/audiokniha/{slug}/" if slug else None)
            if source_id is None or title is None or detail_url is None:
                continue

            cover_url = to_absolute_url(self.BASE_URL, self._string(product.get("image_url")))
            authors = self._split_people(self._string(product.get("description")))

            books.append(
                SourceBook(
                    source=self.source_name,
                    source_id=source_id,
                    title=title,
                    detail_url=detail_url,
                    authors=authors,
                    cover_url=cover_url,
                    detail_loaded=False,
                )
            )

        return books

    def parse_detail_page(self, html: str, *, partial: SourceBook | None = None) -> SourceBook:
        tree = HTMLParser(html)
        audiobook = self._extract_detail_payload(html)

        title = partial.title if partial is not None else ""
        authors = partial.authors if partial is not None else []
        cover_url = partial.cover_url if partial is not None else None
        narrators: list[str] = []
        publishers: list[str] = []
        genres: list[str] = []
        published_year: str | None = None
        language: str | None = None
        duration_minutes: int | None = None
        description = self._meta_content(tree, self._selectors.detail_meta_description)

        if audiobook is not None:
            title = normalize_title(self._string(audiobook.get("name"))) or title
            authors = self._embedded_names(audiobook, "app:author") or authors
            narrators = self._embedded_names(audiobook, "app:lector")
            publishers = self._embedded_names(audiobook, "app:publisher")
            genres = self._embedded_names(audiobook, "app:category")
            cover_url = to_absolute_url(self.BASE_URL, self._string(audiobook.get("image_url"))) or cover_url
            published_year = extract_year(
                self._string(audiobook.get("external_published_at"))
                or self._string(audiobook.get("published_at"))
                or self._string(audiobook.get("created_at"))
            )
            language = map_language_to_code(self._string(audiobook.get("content_language")))
            duration_minutes = self._coerce_int(audiobook.get("duration")) or self._duration_from_tracks_ms(
                audiobook.get("tracks_duration_in_ms")
            )

            description = (
                self._resolve_reference(html, audiobook.get("description"))
                or self._html_to_text(self._resolve_reference(html, audiobook.get("description_html")))
                or description
            )

        if partial is not None:
            return partial.model_copy(
                update={
                    "title": title or partial.title,
                    "authors": authors or partial.authors,
                    "narrators": narrators,
                    "publishers": publishers,
                    "published_year": published_year,
                    "description": description,
                    "cover_url": cover_url or partial.cover_url,
                    "genres": genres,
                    "language": language or partial.language,
                    "duration_minutes": duration_minutes,
                    "detail_loaded": True,
                }
            )

        return SourceBook(
            source=self.source_name,
            source_id="unknown",
            title=title,
            detail_url="",
            authors=authors,
            narrators=narrators,
            publishers=publishers,
            published_year=published_year,
            description=description,
            cover_url=cover_url,
            genres=genres,
            language=language,
            duration_minutes=duration_minutes,
            detail_loaded=True,
        )

    def _compose_search_phrase(self, *, query: str, author: str | None) -> str:
        cleaned_query = normalize_whitespace(query) or ""
        cleaned_author = normalize_whitespace(author)
        if cleaned_author is None:
            return cleaned_query
        if normalize_match_text(cleaned_author) in normalize_match_text(cleaned_query):
            return cleaned_query
        return f"{cleaned_query} {cleaned_author}"

    def _extract_search_payload(self, html: str) -> dict[str, Any] | None:
        match = self.SEARCH_PRODUCTS_RE.search(html)
        if match is None:
            return None
        return self._decode_embedded_json(match.group("payload"))

    def _extract_detail_payload(self, html: str) -> dict[str, Any] | None:
        match = self.DETAIL_AUDIOBOOK_RE.search(html)
        if match is None:
            return None
        return self._decode_embedded_json(match.group("payload"))

    def _decode_embedded_json(self, payload: str) -> dict[str, Any] | None:
        try:
            decoded = json.loads(f'"{payload}"')
            value = json.loads(decoded)
        except json.JSONDecodeError:
            try:
                value = json.loads(payload)
            except json.JSONDecodeError:
                return None

        if not isinstance(value, dict):
            return None
        return value

    def _resolve_reference(self, html: str, raw_reference: object) -> str | None:
        reference = self._string(raw_reference)
        if reference is None:
            return None
        if not reference.startswith("$"):
            return reference

        pattern = re.compile(
            self.DETAIL_REFERENCE_RE_TEMPLATE.format(reference=re.escape(reference[1:])),
            re.S,
        )
        match = pattern.search(html)
        if match is None:
            return None
        return self._decode_js_string(match.group("value"))

    def _decode_js_string(self, value: str) -> str | None:
        try:
            return normalize_whitespace(json.loads(f'"{value}"'))
        except json.JSONDecodeError:
            return normalize_whitespace(value)

    def _embedded_names(self, audiobook: dict[str, Any], relation: str) -> list[str]:
        embedded = audiobook.get("_embedded", {})
        if not isinstance(embedded, dict):
            return []
        items = embedded.get(relation, [])
        if not isinstance(items, list):
            return []
        return unique_preserving_order(
            item.get("name") for item in items if isinstance(item, dict)
        )

    def _split_people(self, value: str | None) -> list[str]:
        if value is None:
            return []
        return unique_preserving_order(part.strip() for part in value.split(","))

    def _meta_content(self, tree: HTMLParser, selector: str) -> str | None:
        node = tree.css_first(selector)
        if node is None:
            return None
        return normalize_whitespace(node.attributes.get("content"))

    def _html_to_text(self, html_fragment: str | None) -> str | None:
        normalized = normalize_whitespace(html_fragment)
        if normalized is None:
            return None
        fragment = HTMLParser(f"<div>{normalized}</div>")
        try:
            text = fragment.text(separator=" ", strip=True)
        except TypeError:
            text = fragment.text()
        return normalize_whitespace(text)

    def _duration_from_tracks_ms(self, value: object) -> int | None:
        tracks_duration_ms = self._coerce_int(value)
        if tracks_duration_ms is None:
            return None
        return max(1, round(tracks_duration_ms / 60000))

    def _coerce_int(self, value: object) -> int | None:
        if isinstance(value, bool) or value is None:
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        normalized = self._string(value)
        if normalized is None:
            return None
        try:
            return int(normalized)
        except ValueError:
            return None

    def _string(self, value: object) -> str | None:
        if value is None:
            return None
        return normalize_whitespace(str(value))
