from __future__ import annotations

from dataclasses import dataclass

from selectolax.parser import HTMLParser, Node

from app.clients.http import HttpClient
from app.models import SourceBook
from app.services.scrapers.base import BaseMetadataScraper
from app.utils.text import (
    extract_year,
    normalize_match_text,
    normalize_title,
    normalize_whitespace,
    parse_duration_to_minutes,
    to_absolute_url,
    unique_preserving_order,
)


@dataclass(frozen=True)
class KanopaSelectors:
    search_result_items: str = "#products .p[data-micro='product']"
    search_title_link: str = "a.name[data-micro='url']"
    search_cover: str = "a.image img"
    search_flags: str = ".flags .flag"
    detail_title: str = ".p-detail-inner-header h1"
    detail_cover: str = ".p-main-image img"
    detail_description: str = "#description .basic-description"
    detail_flags: str = ".p-detail-info .flags .flag"
    detail_parameter_rows: str = ".extended-description .detail-parameters tr"


class KanopaScraper(BaseMetadataScraper):
    source_name = "kanopa"

    BASE_URL = "https://www.kanopa.cz"
    SEARCH_URL = f"{BASE_URL}/vyhledavani/"
    EXCLUDED_TAGS = {"mp3", "mp4", "cd"}

    def __init__(self, *, http_client: HttpClient) -> None:
        self._http_client = http_client
        self._selectors = KanopaSelectors()

    async def search(self, query: str, author: str | None = None) -> list[SourceBook]:
        search_term = self._compose_search_term(query=query, author=author)
        fallback_query = normalize_whitespace(query) or ""
        if author is None or search_term == fallback_query:
            return await self._search_books(search_term)

        return await self._prefer_primary_results(
            primary=lambda: self._search_books(search_term),
            fallback=lambda: self._search_books(fallback_query),
        )

    async def enrich(self, item: SourceBook) -> SourceBook:
        html = await self._http_client.get_text(item.detail_url)
        return self.parse_detail_page(html, partial=item)

    def parse_search_results(self, html: str) -> list[SourceBook]:
        tree = HTMLParser(html)
        books: list[SourceBook] = []

        for item in tree.css(self._selectors.search_result_items):
            source_id = self._attr(item, "data-micro-product-id")
            title_link = item.css_first(self._selectors.search_title_link)
            title = normalize_title(self._text(title_link))
            detail_url = to_absolute_url(self.BASE_URL, self._attr(title_link, "href"))
            if source_id is None or title is None or detail_url is None:
                continue

            cover_node = item.css_first(self._selectors.search_cover)
            cover_url = to_absolute_url(
                self.BASE_URL,
                self._attr(cover_node, "data-micro-image")
                or self._attr(cover_node, "data-src")
                or self._attr(cover_node, "src"),
            )

            books.append(
                SourceBook(
                    source=self.source_name,
                    source_id=source_id,
                    title=title,
                    detail_url=detail_url,
                    cover_url=cover_url,
                    tags=self._filter_tags(self._texts(item.css(self._selectors.search_flags))),
                    detail_loaded=False,
                )
            )

        return books

    async def _search_books(self, search_term: str) -> list[SourceBook]:
        html = await self._fetch_search_page(search_term)
        return self.parse_search_results(html)

    def parse_detail_page(self, html: str, *, partial: SourceBook | None = None) -> SourceBook:
        tree = HTMLParser(html)
        parameters = self._parse_detail_parameters(tree)

        title = normalize_title(self._text(tree.css_first(self._selectors.detail_title))) or (
            partial.title if partial else ""
        )
        cover_node = tree.css_first(self._selectors.detail_cover)
        cover_url = to_absolute_url(
            self.BASE_URL,
            self._attr(cover_node, "src") or self._attr(cover_node, "data-src"),
        ) or (partial.cover_url if partial else None)
        description = self._text(tree.css_first(self._selectors.detail_description)) or (
            partial.description if partial else None
        )
        authors = self._split_list_value(parameters.get("Autor")) or (partial.authors if partial else [])
        narrators = self._split_list_value(parameters.get("Interpret")) or (
            partial.narrators if partial else []
        )
        publishers = self._split_list_value(parameters.get("Vydavatel")) or (
            partial.publishers if partial else []
        )
        genres = self._split_list_value(parameters.get("Žánr")) or (partial.genres if partial else [])
        published_year = self._published_year_from_parameters(parameters) or (
            partial.published_year if partial else None
        )
        duration_minutes = parse_duration_to_minutes(parameters.get("Délka"))
        tags = self._filter_tags(self._texts(tree.css(self._selectors.detail_flags))) or (
            partial.tags if partial else []
        )

        if partial is not None:
            return partial.model_copy(
                update={
                    "title": title or partial.title,
                    "authors": authors or partial.authors,
                    "narrators": narrators or partial.narrators,
                    "publishers": publishers or partial.publishers,
                    "published_year": published_year,
                    "description": description,
                    "cover_url": cover_url or partial.cover_url,
                    "genres": genres or partial.genres,
                    "tags": tags or partial.tags,
                    "duration_minutes": duration_minutes,
                    "detail_loaded": True,
                }
            )

        return SourceBook(
            source=self.source_name,
            title=title,
            source_id="",
            detail_url="",
            authors=authors,
            narrators=narrators,
            publishers=publishers,
            published_year=published_year,
            description=description,
            cover_url=cover_url,
            genres=genres,
            tags=tags,
            duration_minutes=duration_minutes,
            detail_loaded=True,
        )

    async def _fetch_search_page(self, search_term: str) -> str:
        return await self._http_client.get_text(
            self.SEARCH_URL,
            params={"string": search_term},
        )

    def _compose_search_term(self, *, query: str, author: str | None) -> str:
        cleaned_query = normalize_whitespace(query) or ""
        cleaned_author = normalize_whitespace(author)
        if cleaned_author is None:
            return cleaned_query
        if normalize_match_text(cleaned_author) in normalize_match_text(cleaned_query):
            return cleaned_query
        return f"{cleaned_query} {cleaned_author}"

    def _parse_detail_parameters(self, tree: HTMLParser) -> dict[str, str]:
        parameters: dict[str, str] = {}

        for row in tree.css(self._selectors.detail_parameter_rows):
            label = self._text(row.css_first(".row-header-label")) or self._text(row.css_first("th"))
            value = self._text(row.css_first("td"))
            if label is None or value is None:
                continue
            normalized_label = normalize_whitespace(label.rstrip(": ").strip())
            if normalized_label is None:
                continue
            parameters[normalized_label] = value

        return parameters

    def _published_year_from_parameters(self, parameters: dict[str, str]) -> str | None:
        for key in ("Rok vydání", "Datum vydání", "Vydáno"):
            year = extract_year(parameters.get(key))
            if year is not None:
                return year
        return None

    def _split_list_value(self, value: str | None) -> list[str]:
        normalized = normalize_whitespace(value)
        if normalized is None:
            return []
        return unique_preserving_order(part.strip() for part in normalized.split(","))

    def _filter_tags(self, values: list[str]) -> list[str]:
        filtered: list[str] = []
        for value in values:
            if normalize_match_text(value) in self.EXCLUDED_TAGS:
                continue
            filtered.append(value)
        return unique_preserving_order(filtered)

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
