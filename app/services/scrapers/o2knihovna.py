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
    normalize_title,
    normalize_whitespace,
    parse_duration_to_minutes,
    to_absolute_url,
    unique_preserving_order,
)


@dataclass(frozen=True)
class O2KnihovnaSelectors:
    search_result_items: str = "#snippet--itemsList .list-item"
    search_title_link: str = "a[href^='/audioknihy/']"
    search_title: str = ".list-item__title"
    search_cover: str = ".list-item__icon"
    detail_title: str = ".detail--audiobook h1"
    detail_author_links: str = ".detail--audiobook .subtitle a"
    detail_cover: str = ".detail__cover img"
    detail_genre_links: str = "#tags .tags__in"
    detail_metadata: str = ".textPart > p"
    detail_visible_narrator_links: str = ".textPart > p a[href*='/audioknihy/interpret/']"
    detail_visible_publisher_links: str = ".textPart > p a[href*='/audioknihy/vydavatel/']"
    detail_description: str = ".collapse__content"
    detail_description_paragraphs: str = ".collapse__content p"
    meta_description: str = "meta[name='description'], meta[property='og:description']"


class O2KnihovnaScraper(BaseMetadataScraper):
    source_name = "o2knihovna"

    BASE_URL = "https://www.o2knihovna.cz"
    SEARCH_URL = f"{BASE_URL}/audioknihy/hledani"
    DETAIL_URL_RE = re.compile(r"/audioknihy/(?P<source_id>ab\d-[^/?#]+)", re.IGNORECASE)
    METADATA_FIELD_RE = re.compile(
        r"(?P<label>Délka|Interpret|Vydavatel|Vydáno|Jazyk|Typ souboru|Velikost):\s*"
        r"(?P<value>.*?)(?=(?:Délka|Interpret|Vydavatel|Vydáno|Jazyk|Typ souboru|Velikost):|$)",
        re.DOTALL,
    )
    NARRATOR_SENTENCE_RE = re.compile(r"\bČt(?:e|ou)\s+(?P<names>[^.?!]+)", re.IGNORECASE)

    def __init__(self, *, http_client: HttpClient) -> None:
        self._http_client = http_client
        self._selectors = O2KnihovnaSelectors()

    async def search(self, query: str, author: str | None = None) -> list[SourceBook]:
        del author
        html = await self._http_client.get_text(
            self.SEARCH_URL,
            params={"q": normalize_whitespace(query) or ""},
        )
        return self.parse_search_results(html)

    async def enrich(self, item: SourceBook) -> SourceBook:
        html = await self._http_client.get_text(item.detail_url)
        return self.parse_detail_page(html, partial=item)

    def parse_search_results(self, html: str) -> list[SourceBook]:
        tree = HTMLParser(html)
        books: list[SourceBook] = []

        for item in tree.css(self._selectors.search_result_items):
            title_link = item.css_first(self._selectors.search_title_link)
            title = normalize_title(self._text(item.css_first(self._selectors.search_title)))
            detail_url = to_absolute_url(self.BASE_URL, self._attr(title_link, "href"))
            source_id = self._extract_source_id(detail_url)
            cover_url = to_absolute_url(
                self.BASE_URL,
                self._attr(item.css_first(self._selectors.search_cover), "src"),
            )
            if source_id is None or title is None or detail_url is None:
                continue

            books.append(
                SourceBook(
                    source=self.source_name,
                    source_id=source_id,
                    title=title,
                    detail_url=detail_url,
                    cover_url=cover_url,
                    detail_loaded=False,
                )
            )

        return books

    def parse_detail_page(self, html: str, *, partial: SourceBook | None = None) -> SourceBook:
        tree = HTMLParser(html)
        metadata = self._parse_metadata_fields(self._text(tree.css_first(self._selectors.detail_metadata)))
        description_paragraphs = self._texts(tree.css(self._selectors.detail_description_paragraphs))
        description = normalize_whitespace(" ".join(description_paragraphs)) or self._attr(
            tree.css_first(self._selectors.meta_description),
            "content",
        )
        visible_narrators = self._texts(tree.css(self._selectors.detail_visible_narrator_links))
        narrators = unique_preserving_order(
            [
                *visible_narrators,
                *self._split_people(metadata.get("Interpret")),
                *self._parse_narrators_from_paragraphs(description_paragraphs),
            ]
        )
        publishers = self._texts(tree.css(self._selectors.detail_visible_publisher_links)) or self._split_people(
            metadata.get("Vydavatel")
        )
        genres = self._texts(tree.css(self._selectors.detail_genre_links))
        language = map_language_to_code(metadata.get("Jazyk"))
        duration_minutes = parse_duration_to_minutes(metadata.get("Délka"))
        published_year = extract_year(metadata.get("Vydáno"))
        title = normalize_title(self._text(tree.css_first(self._selectors.detail_title)))
        authors = self._texts(tree.css(self._selectors.detail_author_links))
        cover_url = to_absolute_url(
            self.BASE_URL,
            self._attr(tree.css_first(self._selectors.detail_cover), "src"),
        )

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

    def _parse_metadata_fields(self, value: str | None) -> dict[str, str]:
        normalized = normalize_whitespace(value)
        if normalized is None:
            return {}
        return {
            match.group("label"): normalize_whitespace(match.group("value")) or ""
            for match in self.METADATA_FIELD_RE.finditer(normalized)
        }

    def _extract_source_id(self, detail_url: str | None) -> str | None:
        normalized = normalize_whitespace(detail_url)
        if normalized is None:
            return None
        match = self.DETAIL_URL_RE.search(normalized)
        if match is None:
            return None
        return match.group("source_id")

    def _parse_narrators_from_paragraphs(self, paragraphs: list[str]) -> list[str]:
        if not paragraphs:
            return []
        match = self.NARRATOR_SENTENCE_RE.search(" ".join(paragraphs[-2:]))
        if match is None:
            return []
        return self._split_people(match.group("names"))

    def _split_people(self, value: str | None) -> list[str]:
        normalized = normalize_whitespace(value)
        if normalized is None:
            return []
        working = re.sub(r"\s+a\s+", ", ", normalized)
        return unique_preserving_order(part.strip() for part in working.split(","))

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
