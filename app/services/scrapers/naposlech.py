from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from selectolax.parser import HTMLParser, Node

from app.clients.http import HttpClient, UpstreamFetchError
from app.models import SourceBook
from app.services.scrapers.base import BaseMetadataScraper
from app.utils.text import (
    extract_year,
    map_language_to_code,
    normalize_title,
    normalize_whitespace,
    parse_duration_to_minutes,
    unique_preserving_order,
)


@dataclass(frozen=True)
class NaposlechSelectors:
    search_cards: str = ".uael-post-wrapper"
    search_title: str = ".uael-post__title a"
    search_thumbnail: str = ".uael-post__thumbnail img"
    search_excerpt: str = ".uael-post__excerpt"
    search_genres: str = ".uael-post__terms a"
    search_read_more: str = ".uael-post__read-more"
    detail_title: str = "h1.elementor-heading-title"
    detail_cover: str = ".elementor-widget-theme-post-featured-image img"
    detail_description: str = ".elementor-widget-theme-post-content .elementor-widget-container"
    detail_pairs: str = ".npslch-columns .pair"
    detail_value: str = ".value"
    detail_value_links: str = ".value a"
    meta_og_image: str = "meta[property='og:image']"


class NaposlechScraper(BaseMetadataScraper):
    source_name = "naposlech"

    BASE_URL = "https://naposlech.cz"
    SEARCH_URL = f"{BASE_URL}/wp-json/wp/v2/audiokniha"
    SEARCH_PAGE_URL = BASE_URL
    SEARCH_PAGE_SIZE = 10
    ATTRIBUTION_RE = re.compile(r"\btext:\s*(?P<publisher>.+)$", re.IGNORECASE)
    MISSING_VALUE_MARKERS = {"-", "–"}

    def __init__(self, *, http_client: HttpClient) -> None:
        self._http_client = http_client
        self._selectors = NaposlechSelectors()

    async def search(self, query: str, author: str | None = None) -> list[SourceBook]:
        del author
        cleaned_query = normalize_whitespace(query) or ""
        try:
            payload = await self._http_client.get_json(
                self.SEARCH_URL,
                params={
                    "search": cleaned_query,
                    "per_page": self.SEARCH_PAGE_SIZE,
                },
            )
            return self.parse_search_results(payload)
        except UpstreamFetchError:
            html = await self._http_client.get_text(
                self.SEARCH_PAGE_URL,
                params={"s": cleaned_query},
            )
            return self.parse_search_page(html)

    async def enrich(self, item: SourceBook) -> SourceBook:
        html = await self._http_client.get_text(item.detail_url)
        return self.parse_detail_page(html, partial=item)

    def parse_search_results(self, payload: object) -> list[SourceBook]:
        items = self._coerce_search_items(payload)
        books: list[SourceBook] = []

        for item in items:
            if self._string(item.get("type")) not in {None, "audiokniha"}:
                continue

            source_id = self._string(item.get("id"))
            title = normalize_title(self._rendered_text(item.get("title")))
            detail_url = self._string(item.get("link"))
            if source_id is None or title is None or detail_url is None:
                continue

            books.append(
                SourceBook(
                    source=self.source_name,
                    source_id=source_id,
                    title=title,
                    detail_url=detail_url,
                    description=(
                        self._clean_description(self._rendered_text(item.get("excerpt")))
                        or self._clean_description(self._rendered_text(item.get("content")))
                    ),
                    detail_loaded=False,
                )
            )

        return books

    def parse_search_page(self, html: str) -> list[SourceBook]:
        tree = HTMLParser(html)
        books: list[SourceBook] = []
        seen_urls: set[str] = set()

        for card in tree.css(self._selectors.search_cards):
            title_link = card.css_first(self._selectors.search_title)
            detail_url = self._attr(title_link, "href")
            if detail_url is None or "/audiokniha/" not in detail_url:
                continue

            detail_url = self._absolute_url(detail_url)
            if detail_url in seen_urls:
                continue

            title = normalize_title(self._text(title_link))
            if title is None:
                continue

            read_more = card.css_first(self._selectors.search_read_more)
            source_id = self._source_id_from_read_more(read_more) or self._source_id_from_url(
                detail_url
            )
            cover_node = card.css_first(self._selectors.search_thumbnail)
            description = self._clean_description(
                self._text(card.css_first(self._selectors.search_excerpt))
            )
            genres = self._texts(card.css(self._selectors.search_genres))

            books.append(
                SourceBook(
                    source=self.source_name,
                    source_id=source_id,
                    title=title,
                    detail_url=detail_url,
                    description=description,
                    cover_url=self._absolute_url(self._attr(cover_node, "src")),
                    genres=genres,
                    detail_loaded=False,
                )
            )
            seen_urls.add(detail_url)
            if len(books) >= self.SEARCH_PAGE_SIZE:
                break

        return books

    def parse_detail_page(self, html: str, *, partial: SourceBook | None = None) -> SourceBook:
        tree = HTMLParser(html)
        pairs = self._parse_detail_pairs(tree)

        title = normalize_title(self._text(tree.css_first(self._selectors.detail_title)))
        cover_node = tree.css_first(self._selectors.detail_cover)
        cover_url = self._attr(cover_node, "src") or self._meta_content(tree, self._selectors.meta_og_image)
        raw_description = self._text(tree.css_first(self._selectors.detail_description))
        description = self._clean_description(raw_description)
        authors = self._values_for_labels(pairs, "Autor", "Autoři")
        narrators = self._values_for_labels(pairs, "Interpret", "Interpreti")
        publishers = self._values_for_labels(pairs, "Vydavatel", "Nakladatelství")
        if not publishers:
            attribution_publisher = self._publisher_from_attribution(raw_description)
            if attribution_publisher is not None:
                publishers = [attribution_publisher]
        genres = self._values_for_labels(pairs, "Žánry audioknih", "Žánr")
        published_year = extract_year(self._first(self._values_for_labels(pairs, "Rok vydání")))
        language = map_language_to_code(self._first(self._values_for_labels(pairs, "Jazyk")))
        duration_minutes = parse_duration_to_minutes(self._first(self._values_for_labels(pairs, "Délka")))

        if partial is not None:
            return partial.model_copy(
                update={
                    "title": title or partial.title,
                    "authors": authors or partial.authors,
                    "narrators": narrators or partial.narrators,
                    "publishers": publishers or partial.publishers,
                    "published_year": published_year or partial.published_year,
                    "description": description or partial.description,
                    "cover_url": cover_url or partial.cover_url,
                    "genres": genres or partial.genres,
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

    def _coerce_search_items(self, payload: object) -> list[dict[str, Any]]:
        raw_items = payload
        if isinstance(payload, str):
            try:
                raw_items = json.loads(payload)
            except json.JSONDecodeError:
                return []

        if not isinstance(raw_items, list):
            return []

        return [item for item in raw_items if isinstance(item, dict)]

    def _parse_detail_pairs(self, tree: HTMLParser) -> dict[str, list[str]]:
        values: dict[str, list[str]] = {}

        for pair in tree.css(self._selectors.detail_pairs):
            label = self._attr(pair, "data-name") or self._text(pair.css_first("label"))
            value_node = pair.css_first(self._selectors.detail_value)
            if label is None or value_node is None:
                continue

            linked_values = self._texts(value_node.css(self._selectors.detail_value_links))
            if linked_values:
                values[label] = linked_values
                continue

            raw_value = self._text(value_node)
            if raw_value is None or raw_value in self.MISSING_VALUE_MARKERS:
                continue
            values[label] = [raw_value]

        return values

    def _values_for_labels(self, pairs: dict[str, list[str]], *labels: str) -> list[str]:
        for label in labels:
            values = pairs.get(label)
            if values:
                return values
        return []

    def _rendered_text(self, value: object) -> str | None:
        if not isinstance(value, dict):
            return None
        rendered = self._string(value.get("rendered"))
        if rendered is None:
            return None
        fragment = HTMLParser(f"<div>{rendered}</div>")
        try:
            text = fragment.text(separator=" ", strip=True)
        except TypeError:
            text = fragment.text()
        return normalize_whitespace(text)

    def _publisher_from_attribution(self, description: str | None) -> str | None:
        normalized = normalize_whitespace(description)
        if normalized is None:
            return None
        match = self.ATTRIBUTION_RE.search(normalized)
        if match is None:
            return None
        return normalize_whitespace(match.group("publisher"))

    def _clean_description(self, text: str | None) -> str | None:
        normalized = normalize_whitespace(text)
        if normalized is None:
            return None

        without_attribution = self.ATTRIBUTION_RE.sub("", normalized).strip(" -,:;")
        return normalize_whitespace(without_attribution)

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
        return self._string(node.attributes.get(name))

    def _meta_content(self, tree: HTMLParser, selector: str) -> str | None:
        node = tree.css_first(selector)
        if node is None:
            return None
        return self._attr(node, "content")

    def _source_id_from_read_more(self, node: Node | None) -> str | None:
        labelled_by = self._attr(node, "aria-labelledby")
        if labelled_by is None:
            return None
        match = re.search(r"uael-post-(\d+)", labelled_by)
        if match is None:
            return None
        return match.group(1)

    def _source_id_from_url(self, url: str) -> str:
        return url.rstrip("/").rsplit("/", 1)[-1]

    def _absolute_url(self, url: str | None) -> str | None:
        if url is None:
            return None
        if url.startswith("//"):
            return f"https:{url}"
        if url.startswith("/"):
            return f"{self.BASE_URL}{url}"
        return url

    def _string(self, value: object) -> str | None:
        if value is None:
            return None
        return normalize_whitespace(str(value))

    def _first(self, values: list[str]) -> str | None:
        if not values:
            return None
        return values[0]
