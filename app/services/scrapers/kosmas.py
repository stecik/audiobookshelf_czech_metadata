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
    normalize_title,
    normalize_whitespace,
    parse_duration_to_minutes,
    to_absolute_url,
    unique_preserving_order,
)


@dataclass(frozen=True)
class KosmasSelectors:
    search_result_items: str = "#fulltext_articles .grid-item"
    search_title_link: str = ".g-item__title a"
    search_author_links: str = ".g-item__authors a"
    search_cover: str = ".g-item__figure img.img__cover"
    search_description: str = ".article__popup-perex"
    detail_title: str = "h1.product__title"
    detail_people: str = ".product__authors"
    detail_cover: str = "#detailCover"
    detail_description: str = ".product__annotation .toggle-text"
    detail_biblio: str = "dl.product__biblio"


@dataclass(frozen=True)
class KosmasProductMetadata:
    publisher: str | None = None
    genres: tuple[str, ...] = ()


class KosmasScraper(BaseMetadataScraper):
    source_name = "kosmas"

    BASE_URL = "https://www.kosmas.cz"
    SEARCH_URL = f"{BASE_URL}/audioknihy/"

    PRODUCT_ID_RE = re.compile(r"/knihy/(?P<product_id>\d+)/", re.IGNORECASE)
    SEARCH_ITEMS_RE = re.compile(
        r'event:\s*"view_item_list"\s*,\s*ecommerce:\s*\{"items":(?P<items>\[.*?\])\}',
        re.DOTALL,
    )
    DETAIL_ITEMS_RE = re.compile(r"window\.ga4items\s*=\s*(?P<items>\[.*?\]);", re.DOTALL)

    def __init__(self, *, http_client: HttpClient) -> None:
        self._http_client = http_client
        self._selectors = KosmasSelectors()

    async def search(self, query: str, author: str | None = None) -> list[SourceBook]:
        # Live inspection on 2026-03-15 showed that adding the author into the
        # Kosmas query can worsen ranking for exact title matches, so we search
        # by title only and let the provider-level ranking apply author boosts.
        search_query = normalize_whitespace(query) or ""
        html = await self._http_client.get_text(
            self.SEARCH_URL,
            params={"sortBy": "relevance", "query": search_query},
        )
        return self.parse_search_results(html)

    async def enrich(self, item: SourceBook) -> SourceBook:
        html = await self._http_client.get_text(item.detail_url)
        return self.parse_detail_page(html, partial=item)

    def parse_search_results(self, html: str) -> list[SourceBook]:
        metadata_by_id = self._parse_search_metadata(html)
        tree = HTMLParser(html)
        books: list[SourceBook] = []

        for item in tree.css(self._selectors.search_result_items):
            title_link = item.css_first(self._selectors.search_title_link)
            detail_url = to_absolute_url(self.BASE_URL, self._attr(title_link, "href"))
            title = normalize_title(self._text(title_link))
            source_id = self._extract_product_id(detail_url)
            if detail_url is None or title is None or source_id is None:
                continue

            cover_node = item.css_first(self._selectors.search_cover)
            metadata = metadata_by_id.get(source_id)
            publisher = (
                metadata.publisher
                if metadata is not None
                else self._extract_search_publisher(cover_node)
            )

            books.append(
                SourceBook(
                    source=self.source_name,
                    source_id=source_id,
                    title=title,
                    detail_url=detail_url,
                    authors=self._texts(item.css(self._selectors.search_author_links)),
                    publishers=[publisher] if publisher else [],
                    description=self._text(item.css_first(self._selectors.search_description)),
                    cover_url=to_absolute_url(
                        self.BASE_URL,
                        self._attr(cover_node, "src") or self._attr(cover_node, "data-lazy"),
                    ),
                    genres=list(metadata.genres) if metadata is not None else [],
                    detail_loaded=False,
                )
            )

        return books

    def parse_detail_page(self, html: str, *, partial: SourceBook | None = None) -> SourceBook:
        tree = HTMLParser(html)
        bibliographic_data = self._parse_definition_list(tree.css_first(self._selectors.detail_biblio))
        people = self._extract_people(tree)

        title = normalize_title(self._text(tree.css_first(self._selectors.detail_title)))
        authors = people.get("authors") or bibliographic_data.get("Autor") or (partial.authors if partial else [])
        narrators = (
            people.get("narrators")
            or bibliographic_data.get("Interpret")
            or (partial.narrators if partial else [])
        )
        publishers = bibliographic_data.get("Nakladatel") or (partial.publishers if partial else [])
        description = self._extract_detail_description(tree) or (partial.description if partial else None)
        cover_url = to_absolute_url(
            self.BASE_URL,
            self._attr(tree.css_first(self._selectors.detail_cover), "src"),
        )
        genres = self._parse_detail_genres(html) or (partial.genres if partial else [])
        language = map_language_to_code(self._first(bibliographic_data.get("Jazyk")))
        published_year = extract_year(self._first(bibliographic_data.get("Rok vydání")))
        duration_minutes = parse_duration_to_minutes(self._first(bibliographic_data.get("Popis")))

        if partial is not None:
            return partial.model_copy(
                update={
                    "title": title or partial.title,
                    "authors": authors or partial.authors,
                    "narrators": narrators,
                    "publishers": publishers or partial.publishers,
                    "published_year": published_year or partial.published_year,
                    "description": description or partial.description,
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
            description=description,
            cover_url=cover_url,
            genres=genres,
            language=language,
            duration_minutes=duration_minutes,
            detail_loaded=True,
        )

    def _parse_search_metadata(self, html: str) -> dict[str, KosmasProductMetadata]:
        items = self._load_items_from_regex(self.SEARCH_ITEMS_RE, html)
        metadata_by_id: dict[str, KosmasProductMetadata] = {}

        for item in items:
            source_id = self._string(item.get("item_id"))
            if source_id is None:
                continue

            metadata_by_id[source_id] = KosmasProductMetadata(
                publisher=self._string(item.get("item_brand")),
                genres=tuple(self._extract_categories(item)),
            )

        return metadata_by_id

    def _parse_detail_genres(self, html: str) -> list[str]:
        items = self._load_items_from_regex(self.DETAIL_ITEMS_RE, html)
        if not items:
            return []
        return self._extract_categories(items[0])

    def _load_items_from_regex(self, pattern: re.Pattern[str], html: str) -> list[dict[str, Any]]:
        match = pattern.search(html)
        if match is None:
            return []

        try:
            payload = json.loads(match.group("items"))
        except json.JSONDecodeError:
            return []
        if not isinstance(payload, list):
            return []

        return [item for item in payload if isinstance(item, dict)]

    def _extract_categories(self, payload: dict[str, Any]) -> list[str]:
        return unique_preserving_order([
            self._string(payload.get("item_category")),
            self._string(payload.get("item_category2")),
            self._string(payload.get("item_category3")),
            self._string(payload.get("item_category4")),
            self._string(payload.get("item_category5")),
        ])

    def _parse_definition_list(self, node: Node | None) -> dict[str, list[str]]:
        parsed: dict[str, list[str]] = {}
        if node is None:
            return parsed

        current_label: str | None = None
        child = node.child
        while child is not None:
            if child.tag == "dt":
                current_label = (self._text(child) or "").rstrip(":")
            elif child.tag == "dd" and current_label:
                values = self._texts(child.css("a"))
                text_value = self._text(child)
                if values:
                    parsed[current_label] = values
                elif text_value:
                    parsed[current_label] = [text_value]
            child = child.next

        return parsed

    def _extract_people(self, tree: HTMLParser) -> dict[str, list[str]]:
        people: dict[str, list[str]] = {"authors": [], "narrators": []}

        for node in tree.css(self._selectors.detail_people):
            values = self._texts(node.css("a"))
            if not values:
                continue

            full_text = self._text(node)
            if full_text and full_text.startswith("Interpret"):
                people["narrators"] = values
            elif not people["authors"]:
                people["authors"] = values

        return people

    def _extract_detail_description(self, tree: HTMLParser) -> str | None:
        node = tree.css_first(self._selectors.detail_description)
        if node is None:
            return None
        return normalize_whitespace(node.attributes.get("data-holder")) or self._text(node)

    def _extract_search_publisher(self, node: Node | None) -> str | None:
        title_value = self._attr(node, "title")
        if title_value is None or "/" not in title_value:
            return None
        publisher = title_value.rsplit("/", 1)[-1]
        return normalize_whitespace(publisher.split("(", 1)[0])

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

    def _string(self, value: object) -> str | None:
        if value is None:
            return None
        return normalize_whitespace(str(value))
