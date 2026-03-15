from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from selectolax.parser import HTMLParser, Node

from app.clients.http import HttpClient
from app.models import SourceBook
from app.services.scrapers.base import BaseMetadataScraper
from app.utils.text import (
    extract_year,
    map_language_to_code,
    normalize_match_text,
    normalize_title,
    normalize_whitespace,
    parse_duration_to_minutes,
    strip_audiobook_prefix,
    to_absolute_url,
    unique_preserving_order,
)


@dataclass(frozen=True)
class AlbatrosMediaSelectors:
    search_result_items: str = ".product-list .p-l__item"
    search_title_link: str = ".p-l-i__title a"
    search_author_links: str = ".p-l-i__authors a.author"
    search_cover: str = ".figure__inner img"
    search_quote: str = ".p-l-i__back q"
    search_product_payload: str = ".action-control[data-component='AddToCart']"
    detail_title: str = ".product-top__header h1"
    detail_author_links: str = ".product__author a.author"
    detail_cover: str = ".product__cover img"
    detail_description: str = ".p-i__long-anotation .p__text"
    detail_short_description: str = ".product__descriptions .cms-text"
    detail_quote: str = ".product__descriptions q"
    detail_params: str = ".product__param"


class AlbatrosMediaScraper(BaseMetadataScraper):
    source_name = "albatrosmedia"

    BASE_URL = "https://www.albatrosmedia.cz"
    SEARCH_URL = f"{BASE_URL}/hledani/"
    PRODUCT_ID_RE = re.compile(r"/tituly/(?P<product_id>\d+)/", re.IGNORECASE)

    def __init__(self, *, http_client: HttpClient) -> None:
        self._http_client = http_client
        self._selectors = AlbatrosMediaSelectors()

    async def search(self, query: str, author: str | None = None) -> list[SourceBook]:
        search_query = normalize_whitespace(query) or ""
        html = await self._http_client.get_text(self.SEARCH_URL, params={"Text": search_query})
        return self.parse_search_results(html)

    async def enrich(self, item: SourceBook) -> SourceBook:
        html = await self._http_client.get_text(item.detail_url)
        return self.parse_detail_page(html, partial=item)

    def parse_search_results(self, html: str) -> list[SourceBook]:
        tree = HTMLParser(html)
        books: list[SourceBook] = []

        for item in tree.css(self._selectors.search_result_items):
            title_link = item.css_first(self._selectors.search_title_link)
            raw_title = self._text(title_link)
            detail_url = to_absolute_url(self.BASE_URL, self._attr(title_link, "href"))
            if not self._looks_like_audiobook(raw_title, detail_url):
                continue

            product_payload = self._decode_product_payload(item.css_first(self._selectors.search_product_payload))
            title = self._clean_title(raw_title)
            source_id = self._payload_int(product_payload, "productId") or self._extract_product_id(detail_url)
            if source_id is None or title is None or detail_url is None:
                continue

            cover_url = to_absolute_url(
                self.BASE_URL,
                self._attr(item.css_first(self._selectors.search_cover), "data-src")
                or self._attr(item.css_first(self._selectors.search_cover), "src"),
            )
            authors = self._texts(item.css(self._selectors.search_author_links))
            description = self._text(item.css_first(self._selectors.search_quote))

            brand_name = self._payload_nested_string(product_payload, "brandName")
            books.append(
                SourceBook(
                    source=self.source_name,
                    source_id=source_id,
                    title=title,
                    detail_url=detail_url,
                    authors=authors,
                    publishers=[brand_name] if brand_name else [],
                    description=description,
                    cover_url=cover_url,
                    language="cs",
                    detail_loaded=False,
                )
            )

        return books

    def parse_detail_page(self, html: str, *, partial: SourceBook | None = None) -> SourceBook:
        tree = HTMLParser(html)
        params = self._parse_params(tree)

        title = self._clean_title(self._text(tree.css_first(self._selectors.detail_title)))
        authors = self._texts(tree.css(self._selectors.detail_author_links))
        cover_url = to_absolute_url(
            self.BASE_URL,
            self._attr(tree.css_first(self._selectors.detail_cover), "data-src")
            or self._attr(tree.css_first(self._selectors.detail_cover), "src"),
        )
        description = (
            self._text(tree.css_first(self._selectors.detail_description))
            or self._text(tree.css_first(self._selectors.detail_short_description))
        )
        quote = self._text(tree.css_first(self._selectors.detail_quote))
        genres = params.get("Žánr", [])
        narrators = params.get("Interpret", [])
        publishers = params.get("Nakladatelství", [])
        language = map_language_to_code(self._first(params.get("Jazyk"))) or "cs"
        published_year = extract_year(self._first(params.get("Datum vydání")))
        duration_minutes = parse_duration_to_minutes(self._first(params.get("Délka")))
        if partial is not None:
            return partial.model_copy(
                update={
                    "title": title or partial.title,
                    "authors": authors or partial.authors,
                    "narrators": narrators,
                    "publishers": publishers or partial.publishers,
                    "published_year": published_year or partial.published_year,
                    "description": description or quote or partial.description,
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
            title=title or "",
            detail_url="",
            authors=authors,
            narrators=narrators,
            publishers=publishers,
            published_year=published_year,
            description=description or quote,
            cover_url=cover_url,
            genres=genres,
            language=language,
            duration_minutes=duration_minutes,
            detail_loaded=True,
        )

    def _looks_like_audiobook(self, title: str | None, detail_url: str | None) -> bool:
        normalized_title = normalize_match_text(title)
        normalized_url = normalize_match_text(detail_url)
        return (
            "audiokniha" in normalized_title
            or "audioknih" in normalized_title
            or "audio pro deti" in normalized_title
            or "audiokniha" in normalized_url
        )

    def _clean_title(self, value: str | None) -> str | None:
        normalized = normalize_title(value)
        if normalized is None:
            return None
        cleaned = normalized.replace("(audiokniha)", "").strip()
        return strip_audiobook_prefix(cleaned)

    def _decode_product_payload(self, node: Node | None) -> dict[str, Any] | None:
        raw_value = self._attr(node, "data-component-args")
        if raw_value is None:
            return None
        try:
            payload = json.loads(raw_value)
        except json.JSONDecodeError:
            return None
        if not isinstance(payload, dict):
            return None
        return payload

    def _parse_params(self, tree: HTMLParser) -> dict[str, list[str]]:
        params: dict[str, list[str]] = {}

        for node in tree.css(self._selectors.detail_params):
            spans = node.css("span")
            if len(spans) < 2:
                continue
            label = self._text(spans[0])
            if label is None:
                continue

            values = self._texts(spans[1].css("a"))
            if not values:
                values = self._texts(spans[1].css("span"))
            if not values:
                value = self._text(spans[1])
                values = [value] if value else []

            if values:
                params[label] = values

        return params

    def _payload_int(self, payload: dict[str, Any] | None, key: str) -> str | None:
        if payload is None:
            return None
        value = payload.get(key)
        if isinstance(value, bool) or value is None:
            return None
        if isinstance(value, int):
            return str(value)
        normalized = normalize_whitespace(str(value))
        return normalized

    def _payload_nested_string(self, payload: dict[str, Any] | None, key: str) -> str | None:
        if payload is None:
            return None
        return normalize_whitespace(str(payload.get(key))) if payload.get(key) is not None else None

    def _extract_product_id(self, detail_url: str | None) -> str | None:
        normalized = normalize_whitespace(detail_url)
        if normalized is None:
            return None
        match = self.PRODUCT_ID_RE.search(normalized)
        if match is None:
            return None
        return match.group("product_id")

    def _texts(self, nodes: list[Node]) -> list[str]:
        return unique_preserving_order(self._text(node) for node in nodes)

    def _text(self, node: Node | None) -> str | None:
        if node is None:
            return None
        try:
            text = node.text(separator=" ", strip=True)
        except TypeError:
            text = node.text()
        return normalize_whitespace(text)

    def _attr(self, node: Node | None, name: str) -> str | None:
        if node is None:
            return None
        return normalize_whitespace(node.attributes.get(name))

    def _first(self, values: list[str] | None) -> str | None:
        if not values:
            return None
        return values[0]
