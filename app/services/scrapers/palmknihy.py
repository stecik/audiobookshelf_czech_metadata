from __future__ import annotations

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
    to_absolute_url,
    unique_preserving_order,
)


@dataclass(frozen=True)
class PalmknihySelectors:
    search_result_items: str = "#js-catalog-products-listing .selling-card[item-type='audiobook']"
    search_metadata: str = ".gtm-data"
    search_title_link: str = ".selling-card__text > a[title]"
    search_title: str = ".selling-card__title"
    search_author_links: str = ".selling-card__authors a"
    search_cover: str = ".selling-card__image img"
    detail_title: str = "h1[data-cy='detail-title']"
    detail_author_links: str = ".product-detail__authors [info-type='author']"
    detail_cover: str = ".product-detail__picture img"
    detail_language: str = ".product-detail__info-item [info-type='language']"
    detail_year: str = ".shop__extensions"
    detail_parameter_items: str = ".product-detail__parameters > li"


class PalmknihyScraper(BaseMetadataScraper):
    source_name = "palmknihy"

    BASE_URL = "https://www.palmknihy.cz"
    SEARCH_URL = f"{BASE_URL}/vyhledavani$a885-search"
    GENERIC_GENRES = {"audiokniha", "audioknihy", "kniha", "knihy"}

    def __init__(self, *, http_client: HttpClient) -> None:
        self._http_client = http_client
        self._selectors = PalmknihySelectors()

    async def search(self, query: str, author: str | None = None) -> list[SourceBook]:
        del author
        html = await self._http_client.get_text(
            self.SEARCH_URL,
            params={"query": normalize_whitespace(query) or ""},
        )
        return self.parse_search_results(html)

    async def enrich(self, item: SourceBook) -> SourceBook:
        html = await self._http_client.get_text(item.detail_url)
        return self.parse_detail_page(html, partial=item)

    def parse_search_results(self, html: str) -> list[SourceBook]:
        tree = HTMLParser(html)
        books: list[SourceBook] = []

        for item in tree.css(self._selectors.search_result_items):
            metadata = self._attributes(item.css_first(self._selectors.search_metadata))
            source_id = metadata.get("data-item-id")
            title = normalize_title(
                self._text(item.css_first(self._selectors.search_title))
                or metadata.get("data-item-name")
            )
            detail_url = to_absolute_url(
                self.BASE_URL,
                self._attr(item.css_first(self._selectors.search_title_link), "href"),
            )
            if source_id is None or title is None or detail_url is None:
                continue

            cover_node = item.css_first(self._selectors.search_cover)
            cover_url = to_absolute_url(
                self.BASE_URL,
                self._attr(cover_node, "data-src") or self._attr(cover_node, "src"),
            )
            authors = self._split_people(metadata.get("data-author")) or self._texts(
                item.css(self._selectors.search_author_links)
            )
            publisher = normalize_whitespace(metadata.get("data-publisher"))
            published_year = extract_year(metadata.get("data-year-published"))
            language = map_language_to_code(metadata.get("data-book-language"))
            genres = self._filter_genres(
                [
                    metadata.get("data-item-category2"),
                    metadata.get("data-item-category"),
                ]
            )

            books.append(
                SourceBook(
                    source=self.source_name,
                    source_id=source_id,
                    title=title,
                    detail_url=detail_url,
                    authors=authors,
                    publishers=[publisher] if publisher else [],
                    published_year=published_year,
                    cover_url=cover_url,
                    genres=genres,
                    language=language,
                    detail_loaded=False,
                )
            )

        return books

    def parse_detail_page(self, html: str, *, partial: SourceBook | None = None) -> SourceBook:
        tree = HTMLParser(html)
        params = self._parse_detail_parameters(tree)
        title = normalize_title(self._text(tree.css_first(self._selectors.detail_title)))
        authors = self._texts(tree.css(self._selectors.detail_author_links))
        cover_node = tree.css_first(self._selectors.detail_cover)
        cover_url = to_absolute_url(
            self.BASE_URL,
            self._attr(cover_node, "data-src") or self._attr(cover_node, "src"),
        )
        publishers = params.get("Nakladatel", [])
        genres = self._filter_genres(params.get("Kategorie", []))
        language = (
            map_language_to_code(self._first(params.get("Jazyk")))
            or map_language_to_code(self._text(tree.css_first(self._selectors.detail_language)))
        )
        published_year = extract_year(self._text(tree.css_first(self._selectors.detail_year)))
        duration_minutes = parse_duration_to_minutes(self._first(params.get("Délka")))

        # Live inspection found at least one Palmknihy audiobook detail page whose
        # description belonged to a different title, so description enrichment is
        # intentionally left conservative until a more reliable source is identified.
        if partial is not None:
            return partial.model_copy(
                update={
                    "title": title or partial.title,
                    "authors": authors or partial.authors,
                    "publishers": publishers or partial.publishers,
                    "published_year": published_year or partial.published_year,
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
            publishers=publishers,
            published_year=published_year,
            cover_url=cover_url,
            genres=genres,
            language=language,
            duration_minutes=duration_minutes,
            detail_loaded=True,
        )

    def _parse_detail_parameters(self, tree: HTMLParser) -> dict[str, list[str]]:
        values: dict[str, list[str]] = {}

        for item in tree.css(self._selectors.detail_parameter_items):
            label = self._text(item.css_first("p"))
            if label is None:
                continue
            item_values = unique_preserving_order(
                self._text(node) for node in item.css(".product-detail__parameter-list li")
            )
            cleaned_values = [value for value in item_values if value != "|"]
            if cleaned_values:
                values[label] = cleaned_values

        return values

    def _split_people(self, value: str | None) -> list[str]:
        normalized = normalize_whitespace(value)
        if normalized is None:
            return []
        return unique_preserving_order(part.strip() for part in normalized.split(","))

    def _filter_genres(self, values: list[str | None]) -> list[str]:
        filtered: list[str] = []
        for value in unique_preserving_order(values):
            if normalize_match_text(value) in self.GENERIC_GENRES:
                continue
            filtered.append(value)
        return filtered

    def _texts(self, nodes: list[Node]) -> list[str]:
        return unique_preserving_order(self._text(node) for node in nodes)

    def _attributes(self, node: Node | None) -> dict[str, str]:
        if node is None:
            return {}
        return {
            key: value
            for key, raw_value in node.attributes.items()
            if (value := normalize_whitespace(raw_value)) is not None
        }

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
