from __future__ import annotations

import re
from dataclasses import dataclass

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
class AudiolibrixSelectors:
    search_result_items: str = ".alx-audiobook-list-grid .alx-audiobook-list-item"
    result_title_link: str = "h2 a.audiobook-link"
    result_cover: str = "figure img"
    result_authors: str = "dd.alx-author.mb-0 a"
    result_narrators: str = "dd.alx-author.small a"
    detail_title: str = "h1[itemprop='name']"
    detail_cover: str = ".alx-audiobook-thumbnail img"
    detail_lead: str = "p.lead"
    detail_metadata: str = "dl.alx-metadata"
    detail_cards: str = "article.card"
    card_title: str = "h2.card-title"
    card_body: str = ".card-body"


class AudiolibrixScraper(BaseMetadataScraper):
    source_name = "audiolibrix"

    BASE_URL = "https://www.audiolibrix.com"
    STOREFRONT_URL = f"{BASE_URL}/cs"
    SEARCH_URL = f"{STOREFRONT_URL}/Search/Results"
    BOOK_ID_RE = re.compile(r"/Book/(?P<book_id>\d+)/", re.IGNORECASE)

    def __init__(self, *, http_client: HttpClient) -> None:
        self._http_client = http_client
        self._selectors = AudiolibrixSelectors()

    async def search(self, query: str, author: str | None = None) -> list[SourceBook]:
        api_results = await self._search_via_internal_api(query=query, author=author)
        if api_results is not None:
            return api_results

        search_query = self._compose_search_query(query=query, author=author)
        html = await self._http_client.get_text(self.SEARCH_URL, params={"query": search_query})
        return self.parse_search_results(html)

    async def enrich(self, item: SourceBook) -> SourceBook:
        html = await self._http_client.get_text(item.detail_url)
        return self.parse_detail_page(html, partial=item)

    async def _search_via_internal_api(
        self,
        *,
        query: str,
        author: str | None,
    ) -> list[SourceBook] | None:
        # The live site exposes `search-results-info` counts in markup, but inspection on
        # 2026-03-15 did not reveal a stable JSON endpoint for book results.
        return None

    def parse_search_results(self, html: str) -> list[SourceBook]:
        tree = HTMLParser(html)
        books: list[SourceBook] = []

        for item in tree.css(self._selectors.search_result_items):
            title_link = item.css_first(self._selectors.result_title_link)
            if title_link is None:
                continue

            detail_url = to_absolute_url(self.BASE_URL, self._attr(title_link, "href"))
            title = normalize_title(self._text(title_link))
            source_id = self._attr(title_link, "data-book-id") or self._extract_book_id(detail_url)
            if detail_url is None or title is None or source_id is None:
                continue

            authors = self._texts(item.css(self._selectors.result_authors))
            narrators = self._texts(item.css(self._selectors.result_narrators))
            cover_node = item.css_first(self._selectors.result_cover)
            cover_url = to_absolute_url(self.BASE_URL, self._attr(cover_node, "src"))

            books.append(
                SourceBook(
                    source=self.source_name,
                    source_id=source_id,
                    title=title,
                    detail_url=detail_url,
                    authors=authors,
                    narrators=narrators,
                    cover_url=cover_url,
                    language=self._infer_language_hint(title=title, detail_url=detail_url),
                    detail_loaded=False,
                )
            )

        return books

    def parse_detail_page(self, html: str, *, partial: SourceBook | None = None) -> SourceBook:
        tree = HTMLParser(html)
        metadata = self._parse_definition_list(tree.css_first(self._selectors.detail_metadata))

        detail_title = strip_audiobook_prefix(self._text(tree.css_first(self._selectors.detail_title)))
        title = partial.title if partial is not None else (detail_title or "")
        if not title and detail_title:
            title = detail_title

        cover_node = tree.css_first(self._selectors.detail_cover)
        cover_url = to_absolute_url(self.BASE_URL, self._attr(cover_node, "src"))

        description = self._extract_annotation(tree) or self._text(tree.css_first(self._selectors.detail_lead))
        authors = metadata.get("Autor") or metadata.get("Autori") or (partial.authors if partial else [])
        narrators = metadata.get("Interpret") or metadata.get("Interpreti") or (partial.narrators if partial else [])
        publishers = metadata.get("Vydavatelé") or metadata.get("Vydavatel") or []
        language = map_language_to_code(self._first(metadata.get("_language_values")))
        genres = metadata.get("Žánr") or metadata.get("Žánry") or []
        published_year = extract_year(self._first(metadata.get("_publisher_texts")))
        duration_minutes = parse_duration_to_minutes(self._first(metadata.get("_duration_values")))

        if partial is not None:
            return partial.model_copy(
                update={
                    "title": title or partial.title,
                    "authors": authors or partial.authors,
                    "narrators": narrators or partial.narrators,
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

    def _compose_search_query(self, *, query: str, author: str | None) -> str:
        cleaned_query = normalize_whitespace(query) or ""
        cleaned_author = normalize_whitespace(author)
        if cleaned_author is None:
            return cleaned_query
        if normalize_match_text(cleaned_author) in normalize_match_text(cleaned_query):
            return cleaned_query
        return f"{cleaned_query} {cleaned_author}"

    def _parse_definition_list(self, node: Node | None) -> dict[str, list[str]]:
        parsed: dict[str, list[str]] = {}
        if node is None:
            return parsed

        current_label: str | None = None
        child = node.child
        while child is not None:
            if child.tag == "dt":
                current_label = (normalize_whitespace(self._text(child)) or "").rstrip(":")
            elif child.tag == "dd" and current_label:
                values = self._texts(child.css("a"))
                text_value = normalize_whitespace(self._text(child))
                if current_label.lower().startswith("jazyk"):
                    parsed["_language_values"] = [text_value] if text_value else []
                if current_label.lower().startswith("vydavat"):
                    parsed["_publisher_texts"] = [text_value] if text_value else []
                if current_label.lower().startswith("délka"):
                    parsed["_duration_values"] = [text_value] if text_value else []

                if values:
                    parsed[current_label] = values
                elif text_value:
                    parsed[current_label] = [text_value]

            child = child.next

        return parsed

    def _extract_annotation(self, tree: HTMLParser) -> str | None:
        for card in tree.css(self._selectors.detail_cards):
            title = normalize_whitespace(self._text(card.css_first(self._selectors.card_title)))
            if title != "Anotace":
                continue
            body = card.css_first(self._selectors.card_body)
            return normalize_whitespace(self._text(body))
        return None

    def _infer_language_hint(self, *, title: str, detail_url: str) -> str | None:
        normalized_title = normalize_match_text(title)
        normalized_url = normalize_match_text(detail_url)
        if "( en )" in f" {normalized_title} " or " audiobook " in f" {normalized_url} ":
            return "en"
        return None

    def _extract_book_id(self, detail_url: str | None) -> str | None:
        normalized = normalize_whitespace(detail_url)
        if not normalized:
            return None
        match = self.BOOK_ID_RE.search(normalized)
        if match is None:
            return None
        return match.group("book_id")

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
