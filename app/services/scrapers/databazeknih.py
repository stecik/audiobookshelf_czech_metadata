from __future__ import annotations

import json
import re
from dataclasses import dataclass
from html import unescape
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
    to_absolute_url,
    unique_preserving_order,
)


@dataclass(frozen=True)
class DatabazeKnihSelectors:
    search_result_items: str = "p.new"
    search_result_link: str = "a.new[type='book']"
    search_result_cover: str = "picture img"
    search_result_meta: str = "span.pozn"
    detail_title: str = "h1.oddown_five"
    detail_authors: str = ".orangeBoxLight .author a"
    detail_cover: str = "img.coverOnDetail"
    detail_description: str = "#bdetail_rest p.new2.odtop"
    detail_genres: str = ".detail_description a.genre"
    detail_meta: str = ".detail_description"
    detail_publisher_links: str = ".detail_description a[href^='/nakladatelstvi/']"
    ld_json_scripts: str = "script[type='application/ld+json']"


class DatabazeKnihScraper(BaseMetadataScraper):
    source_name = "databazeknih"

    BASE_URL = "https://www.databazeknih.cz"
    SEARCH_URL = f"{BASE_URL}/search"
    DETAIL_ID_RE = re.compile(r"-(?P<book_id>\d+)(?:$|[?#])")
    SEARCH_META_RE = re.compile(r"^(?P<year>\d{4})\s*,\s*(?P<authors>.+)$")
    TRAILING_NOTE_RE = re.compile(r"\s*\([^)]*\)\s*$")
    DESCRIPTION_SUFFIX_RE = re.compile(r"\s*\.\.\.\s*cel[ýy]\s+text\s*$", re.IGNORECASE)
    DETAIL_HEADING_SUFFIX_RE = re.compile(r"\s+přehled\s*$", re.IGNORECASE)

    def __init__(self, *, http_client: HttpClient) -> None:
        self._http_client = http_client
        self._selectors = DatabazeKnihSelectors()

    async def search(self, query: str, author: str | None = None) -> list[SourceBook]:
        # Live inspection on 2026-03-19 showed that adding the author into the
        # Databaze knih query often pushes the exact title below related books.
        search_query = normalize_whitespace(query) or ""
        html = await self._http_client.get_text(
            self.SEARCH_URL,
            params={"in": "books", "q": search_query, "lang": "cz"},
        )
        return self.parse_search_results(html)

    async def enrich(self, item: SourceBook) -> SourceBook:
        html = await self._http_client.get_text(item.detail_url)
        return self.parse_detail_page(html, partial=item)

    def parse_search_results(self, html: str) -> list[SourceBook]:
        tree = HTMLParser(html)
        books: list[SourceBook] = []

        for item in tree.css(self._selectors.search_result_items):
            title_link = item.css_first(self._selectors.search_result_link)
            detail_url = to_absolute_url(self.BASE_URL, self._attr(title_link, "href"))
            title = normalize_title(self._text(title_link))
            source_id = self._extract_book_id(detail_url)
            if detail_url is None or title is None or source_id is None:
                continue

            published_year, authors = self._parse_search_meta(
                self._text(item.css_first(self._selectors.search_result_meta))
            )

            books.append(
                SourceBook(
                    source=self.source_name,
                    source_id=source_id,
                    title=title,
                    detail_url=detail_url,
                    authors=authors,
                    published_year=published_year,
                    cover_url=to_absolute_url(
                        self.BASE_URL,
                        self._attr(item.css_first(self._selectors.search_result_cover), "src"),
                    ),
                    language="cs",
                    detail_loaded=False,
                )
            )

        return books

    def parse_detail_page(self, html: str, *, partial: SourceBook | None = None) -> SourceBook:
        tree = HTMLParser(html)
        payload = self._extract_book_payload(tree)

        title = (
            self._extract_detail_title(tree)
            or self._string(payload.get("name"))
        )
        authors = self._texts(tree.css(self._selectors.detail_authors)) or self._authors_from_payload(payload)
        publishers = self._texts(tree.css(self._selectors.detail_publisher_links)) or self._publishers_from_payload(
            payload
        )
        cover_url = (
            self._meta_content(tree, "meta[property='og:image']")
            or to_absolute_url(
                self.BASE_URL,
                self._attr(tree.css_first(self._selectors.detail_cover), "src"),
            )
        )
        description = self._extract_detail_description(tree) or self._string(payload.get("description"))
        genres = self._texts(tree.css(self._selectors.detail_genres))
        language = self._extract_language(tree, payload)
        published_year = self._extract_published_year(tree)

        update = {
            "title": title or (partial.title if partial else ""),
            "authors": authors or (partial.authors if partial else []),
            "publishers": publishers or (partial.publishers if partial else []),
            "published_year": published_year or (partial.published_year if partial else None),
            "description": description or (partial.description if partial else None),
            "cover_url": cover_url or (partial.cover_url if partial else None),
            "genres": genres or (partial.genres if partial else []),
            "language": language or (partial.language if partial else None),
            "detail_loaded": True,
        }

        if partial is not None:
            return partial.model_copy(update=update)

        return SourceBook(
            source=self.source_name,
            source_id=self._extract_book_id(self._meta_content(tree, "meta[property='og:url']")) or "unknown",
            title=update["title"],
            detail_url=self._meta_content(tree, "meta[property='og:url']") or "",
            authors=update["authors"],
            publishers=update["publishers"],
            published_year=update["published_year"],
            description=update["description"],
            cover_url=update["cover_url"],
            genres=update["genres"],
            language=update["language"],
            detail_loaded=True,
        )

    def _parse_search_meta(self, value: str | None) -> tuple[str | None, list[str]]:
        normalized = normalize_whitespace(value)
        if normalized is None:
            return None, []

        match = self.SEARCH_META_RE.match(normalized)
        if match is None:
            return extract_year(normalized), self._split_people(normalized)

        return match.group("year"), self._split_people(match.group("authors"))

    def _extract_detail_description(self, tree: HTMLParser) -> str | None:
        description = self._text(tree.css_first(self._selectors.detail_description))
        if description is None:
            return None
        cleaned = self.DESCRIPTION_SUFFIX_RE.sub("", description)
        return normalize_whitespace(cleaned)

    def _extract_detail_title(self, tree: HTMLParser) -> str | None:
        title = self._text(tree.css_first(self._selectors.detail_title))
        if title is None:
            return None
        cleaned = self.DETAIL_HEADING_SUFFIX_RE.sub("", title)
        return normalize_title(cleaned)

    def _extract_published_year(self, tree: HTMLParser) -> str | None:
        lines = self._lines(tree.css_first(self._selectors.detail_meta))
        for index, line in enumerate(lines):
            if line != "Vydáno:":
                continue
            for candidate in lines[index + 1 : index + 3]:
                year = extract_year(candidate)
                if year is not None:
                    return year
        return None

    def _extract_language(self, tree: HTMLParser, payload: dict[str, Any]) -> str | None:
        return (
            map_language_to_code(self._string(payload.get("inLanguage")))
            or map_language_to_code(self._attr(tree.css_first("html"), "lang"))
            or "cs"
        )

    def _extract_book_payload(self, tree: HTMLParser) -> dict[str, Any]:
        for node in tree.css(self._selectors.ld_json_scripts):
            text = node.text()
            if text is None:
                continue
            try:
                payload = json.loads(unescape(text))
            except json.JSONDecodeError:
                continue
            book_payload = self._find_book_payload(payload)
            if book_payload is not None:
                return book_payload
        return {}

    def _find_book_payload(self, payload: object) -> dict[str, Any] | None:
        if isinstance(payload, dict):
            payload_type = payload.get("@type")
            if payload_type == "Book":
                return payload
            if isinstance(payload.get("@graph"), list):
                for item in payload["@graph"]:
                    book_payload = self._find_book_payload(item)
                    if book_payload is not None:
                        return book_payload
            return None
        if isinstance(payload, list):
            for item in payload:
                book_payload = self._find_book_payload(item)
                if book_payload is not None:
                    return book_payload
        return None

    def _authors_from_payload(self, payload: dict[str, Any]) -> list[str]:
        authors = payload.get("author")
        if isinstance(authors, dict):
            return self._split_people(self._string(authors.get("name")))
        if isinstance(authors, list):
            return unique_preserving_order(
                self._string(author.get("name"))
                for author in authors
                if isinstance(author, dict)
            )
        return []

    def _publishers_from_payload(self, payload: dict[str, Any]) -> list[str]:
        publishers = payload.get("publisher")
        if isinstance(publishers, dict):
            return unique_preserving_order([self._string(publishers.get("name"))])
        if isinstance(publishers, list):
            return unique_preserving_order(
                self._string(publisher.get("name"))
                for publisher in publishers
                if isinstance(publisher, dict)
            )
        return []

    def _extract_book_id(self, detail_url: str | None) -> str | None:
        normalized = normalize_whitespace(detail_url)
        if normalized is None:
            return None
        match = self.DETAIL_ID_RE.search(normalized)
        if match is None:
            return None
        return match.group("book_id")

    def _split_people(self, value: str | None) -> list[str]:
        normalized = normalize_whitespace(value)
        if normalized is None:
            return []
        parts = re.split(r"\s*,\s*|\s+a\s+", normalized)
        return unique_preserving_order(self._clean_person(part) for part in parts)

    def _clean_person(self, value: str | None) -> str | None:
        normalized = normalize_whitespace(value)
        if normalized is None:
            return None
        cleaned = self.TRAILING_NOTE_RE.sub("", normalized)
        return normalize_whitespace(cleaned)

    def _lines(self, node: Node | None) -> list[str]:
        if node is None:
            return []
        try:
            text = node.text(separator="\n", strip=True)
        except TypeError:
            text = node.text()
        return [
            normalized
            for raw_line in text.replace("\r", "").split("\n")
            for normalized in [normalize_whitespace(raw_line)]
            if normalized is not None
        ]

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

    def _meta_content(self, tree: HTMLParser, selector: str) -> str | None:
        value = self._attr(tree.css_first(selector), "content")
        if value is None:
            return None
        return normalize_whitespace(unescape(value))

    def _string(self, value: object) -> str | None:
        if value is None:
            return None
        return normalize_whitespace(str(value))
