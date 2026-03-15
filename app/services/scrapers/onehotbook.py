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
    comma_join,
    extract_year,
    normalize_match_text,
    normalize_title,
    normalize_whitespace,
    parse_duration_to_minutes,
    to_absolute_url,
    unique_preserving_order,
)


@dataclass(frozen=True)
class OneHotBookSelectors:
    search_result_items: str = ".product-grid-item"
    search_title_link: str = ".product-name a"
    search_card_json: str = ".quick_shop .json.hide"
    search_cover: str = ".featured-image.front"
    detail_title: str = "h1[itemprop='name']"
    detail_cover: str = "#product-featured-image"
    detail_people: str = "#product-info .author"
    detail_description: str = ".short-description"
    detail_tabs: str = ".product-simple-tab .tab-pane"


class OneHotBookScraper(BaseMetadataScraper):
    source_name = "onehotbook"

    BASE_URL = "https://onehotbook.cz"
    SEARCH_URL = f"{BASE_URL}/search"

    AUTHOR_TAG_PREFIX = "Autor_"
    NARRATOR_TAG_PREFIX = "Interpret_"
    GENRE_TAG_PREFIX = "Žánr_"
    LABEL_VALUE_RE = re.compile(r"^(?P<label>[^:]+):\s*(?P<value>.+)$")
    TITLE_AUTHOR_SUFFIX_RE = re.compile(r"^(?P<title>.+?)\s*\((?P<author>.+)\)$")

    def __init__(self, *, http_client: HttpClient) -> None:
        self._http_client = http_client
        self._selectors = OneHotBookSelectors()

    async def search(self, query: str, author: str | None = None) -> list[SourceBook]:
        search_query = self._compose_search_query(query=query, author=author)
        html = await self._http_client.get_text(
            self.SEARCH_URL,
            params={"q": search_query, "type": "product"},
        )
        return self.parse_search_results(html)

    async def enrich(self, item: SourceBook) -> SourceBook:
        html = await self._http_client.get_text(item.detail_url)
        return self.parse_detail_page(html, partial=item)

    def parse_search_results(self, html: str) -> list[SourceBook]:
        tree = HTMLParser(html)
        books: list[SourceBook] = []

        for item in tree.css(self._selectors.search_result_items):
            payload_node = item.css_first(self._selectors.search_card_json)
            product_payload = self._decode_product_payload(self._text(payload_node))
            if product_payload is None:
                continue

            book = self._book_from_product_payload(product_payload, fallback_node=item)
            if book is not None:
                books.append(book)

        return books

    def parse_detail_page(self, html: str, *, partial: SourceBook | None = None) -> SourceBook:
        tree = HTMLParser(html)
        people = self._extract_people(tree)
        spec_values = self._extract_specifications(tree)

        detail_title = self._clean_title(
            self._text(tree.css_first(self._selectors.detail_title)),
            people.get("authors") or (partial.authors if partial else []),
        )
        description = self._text(tree.css_first(self._selectors.detail_description))
        cover_url = to_absolute_url(self.BASE_URL, self._attr(tree.css_first(self._selectors.detail_cover), "src"))
        published_year = extract_year(spec_values.get("Datum vydání"))
        duration_minutes = parse_duration_to_minutes(spec_values.get("Délka nahrávky"))

        if partial is not None:
            return partial.model_copy(
                update={
                    "title": detail_title or partial.title,
                    "authors": people.get("authors") or partial.authors,
                    "narrators": people.get("narrators") or partial.narrators,
                    "publishers": partial.publishers,
                    "published_year": published_year or partial.published_year,
                    "description": description or partial.description,
                    "cover_url": cover_url or partial.cover_url,
                    "genres": partial.genres,
                    "language": partial.language or "cs",
                    "duration_minutes": duration_minutes,
                    "detail_loaded": True,
                }
            )

        return SourceBook(
            source=self.source_name,
            source_id="unknown",
            title=detail_title or "",
            detail_url="",
            authors=people.get("authors", []),
            narrators=people.get("narrators", []),
            publishers=[],
            published_year=published_year,
            description=description,
            cover_url=cover_url,
            genres=[],
            language="cs",
            duration_minutes=duration_minutes,
            detail_loaded=True,
        )

    def _compose_search_query(self, *, query: str, author: str | None) -> str:
        cleaned_query = normalize_whitespace(query) or ""
        cleaned_author = normalize_whitespace(author)
        if cleaned_author is None:
            return cleaned_query
        if normalize_match_text(cleaned_author) in normalize_match_text(cleaned_query):
            return cleaned_query
        return f"{cleaned_query} {cleaned_author}"

    def _book_from_product_payload(
        self,
        payload: dict[str, Any],
        *,
        fallback_node: Node | None = None,
    ) -> SourceBook | None:
        source_id = self._string(payload.get("id"))
        handle = self._string(payload.get("handle"))
        tagged_values = self._parse_tag_groups(payload.get("tags"))

        raw_title = normalize_title(self._string(payload.get("title")))
        authors = tagged_values["authors"]
        title = self._clean_title(raw_title, authors)
        detail_url = to_absolute_url(self.BASE_URL, f"/products/{handle}" if handle else None)
        if fallback_node is not None and detail_url is None:
            title_link = fallback_node.css_first(self._selectors.search_title_link)
            detail_url = to_absolute_url(self.BASE_URL, self._attr(title_link, "href"))

        cover_url = to_absolute_url(
            self.BASE_URL,
            self._string(payload.get("featured_image")) or self._first(self._list_strings(payload.get("images"))),
        )
        if fallback_node is not None and cover_url is None:
            cover_url = to_absolute_url(
                self.BASE_URL,
                self._attr(fallback_node.css_first(self._selectors.search_cover), "src"),
            )

        if source_id is None or title is None or detail_url is None:
            return None

        description = self._html_to_text(
            self._string(payload.get("description")) or self._string(payload.get("content"))
        )
        published_year = extract_year(
            self._string(payload.get("published_at")) or self._string(payload.get("created_at"))
        )
        publisher = self._normalize_publisher(self._string(payload.get("vendor")))

        return SourceBook(
            source=self.source_name,
            source_id=source_id,
            title=title,
            detail_url=detail_url,
            authors=authors,
            narrators=tagged_values["narrators"],
            publishers=[publisher] if publisher else [],
            published_year=published_year,
            description=description,
            cover_url=cover_url,
            genres=tagged_values["genres"],
            language="cs",
            detail_loaded=False,
        )

    def _decode_product_payload(self, raw_payload: str | None) -> dict[str, Any] | None:
        normalized = normalize_whitespace(raw_payload)
        if normalized is None:
            return None
        try:
            value = json.loads(normalized)
        except json.JSONDecodeError:
            return None
        if not isinstance(value, dict):
            return None
        return value

    def _parse_tag_groups(self, raw_tags: object) -> dict[str, list[str]]:
        tags = self._list_strings(raw_tags)
        return {
            "authors": unique_preserving_order(
                self._strip_tag_prefix(tag, self.AUTHOR_TAG_PREFIX) for tag in tags
            ),
            "narrators": unique_preserving_order(
                self._strip_tag_prefix(tag, self.NARRATOR_TAG_PREFIX) for tag in tags
            ),
            "genres": unique_preserving_order(
                self._strip_tag_prefix(tag, self.GENRE_TAG_PREFIX) for tag in tags
            ),
        }

    def _strip_tag_prefix(self, value: str, prefix: str) -> str | None:
        normalized = normalize_whitespace(value)
        if normalized is None or not normalized.startswith(prefix):
            return None
        return normalize_whitespace(normalized[len(prefix) :])

    def _extract_people(self, tree: HTMLParser) -> dict[str, list[str]]:
        people: dict[str, list[str]] = {"authors": [], "narrators": []}

        for node in tree.css(self._selectors.detail_people):
            full_text = self._text(node)
            if full_text is None:
                continue

            label = normalize_match_text(full_text.split(":", 1)[0])
            values = unique_preserving_order(self._text(link) for link in node.css("a"))
            if label.startswith("autor"):
                people["authors"] = values
            elif label.startswith("interpret"):
                people["narrators"] = values

        return people

    def _extract_specifications(self, tree: HTMLParser) -> dict[str, str]:
        values: dict[str, str] = {}

        for tab in tree.css(self._selectors.detail_tabs):
            for line in self._lines(tab):
                match = self.LABEL_VALUE_RE.match(line)
                if match is None:
                    continue
                label = normalize_whitespace(match.group("label"))
                value = normalize_whitespace(match.group("value"))
                if label is None or value is None:
                    continue
                values[label] = value

        return values

    def _clean_title(self, raw_title: str | None, authors: list[str]) -> str | None:
        normalized_title = normalize_title(raw_title)
        if normalized_title is None:
            return None

        match = self.TITLE_AUTHOR_SUFFIX_RE.match(normalized_title)
        if match is None or not authors:
            return normalized_title

        author_suffix = normalize_match_text(match.group("author"))
        known_author_values = {
            normalize_match_text(author)
            for author in [*authors, comma_join(authors)]
            if author is not None
        }
        if author_suffix in known_author_values:
            return normalize_title(match.group("title"))
        return normalized_title

    def _normalize_publisher(self, value: str | None) -> str | None:
        normalized = normalize_whitespace(value)
        if normalized is None:
            return None
        if normalize_match_text(normalized) == "onehotbook":
            return "OneHotBook"
        return normalized

    def _html_to_text(self, html_fragment: str | None) -> str | None:
        normalized = normalize_whitespace(html_fragment)
        if normalized is None:
            return None
        fragment = HTMLParser(f"<div>{normalized}</div>")
        return self._text(fragment.body)

    def _lines(self, node: Node | None) -> list[str]:
        if node is None:
            return []
        try:
            text = node.text(separator="\n", strip=True)
        except TypeError:
            text = node.text()

        lines: list[str] = []
        for line in text.replace("\r", "").split("\n"):
            normalized = normalize_whitespace(line)
            if normalized is not None:
                lines.append(normalized)
        return lines

    def _list_strings(self, value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        return unique_preserving_order(self._string(item) for item in value)

    def _first(self, values: list[str]) -> str | None:
        if not values:
            return None
        return values[0]

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

    def _string(self, value: object) -> str | None:
        if value is None:
            return None
        return normalize_whitespace(str(value))
