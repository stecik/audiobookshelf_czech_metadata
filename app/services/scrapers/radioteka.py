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
class RadiotekaSelectors:
    search_items: str = "article.item"
    search_title_link: str = ".item__tit a"
    search_image_link: str = ".item__img a"
    search_cover: str = ".item__img img"
    search_add_to_cart: str = ".item__addcart.add-to-cart"
    detail_title: str = "h1.detail__tit"
    detail_description: str = ".detail-center-col .detail__desc"
    detail_info_blocks: str = "dl.detail__info"
    detail_cover: str = ".detail-left-col img"
    detail_og_image: str = "meta[name='og:image']"
    detail_meta_description: str = "meta[name='description']"


class RadiotekaScraper(BaseMetadataScraper):
    source_name = "radioteka"

    BASE_URL = "https://www.radioteka.cz"
    SEARCH_URL = f"{BASE_URL}/hledani"
    GENERIC_GENRES = {
        "audiokniha cetba",
        "cd",
        "dalsi nabidka",
        "flac",
        "mluvene slovo",
        "mp3",
        "novinky",
        "radiokarta",
        "radioteka",
        "radioservis",
    }
    AUTHOR_LABELS = ("Autor knihy", "Autor")
    NARRATOR_LABELS = ("Interpret slova", "Interpret", "Čte")
    PUBLISHER_LABELS = ("Vydavatel",)
    YEAR_LABELS = ("Rok vydání",)
    DURATION_LABELS = ("Celková délka",)

    def __init__(self, *, http_client: HttpClient) -> None:
        self._http_client = http_client
        self._selectors = RadiotekaSelectors()

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

        for item in tree.css(self._selectors.search_items):
            metadata = self._attributes(item.css_first(self._selectors.search_add_to_cart))
            if metadata.get("data-provider") != "croslovo":
                continue

            source_id = metadata.get("data-ident")
            title = normalize_title(
                self._text(item.css_first(self._selectors.search_title_link))
                or metadata.get("data-title")
            )
            title_link = item.css_first(self._selectors.search_title_link)
            image_link = item.css_first(self._selectors.search_image_link)
            detail_url = to_absolute_url(
                self.BASE_URL,
                self._attr(title_link, "href") or self._attr(image_link, "href"),
            )
            if source_id is None or title is None or detail_url is None:
                continue

            cover_node = item.css_first(self._selectors.search_cover)
            cover_url = to_absolute_url(
                self.BASE_URL,
                self._attr(cover_node, "data-src") or self._attr(cover_node, "src"),
            )
            publisher = normalize_whitespace(metadata.get("data-brand"))
            genres = self._filter_genres(
                self._split_categories(metadata.get("data-categories")),
                publisher=publisher,
            )

            books.append(
                SourceBook(
                    source=self.source_name,
                    source_id=source_id,
                    title=title,
                    detail_url=detail_url,
                    publishers=[publisher] if publisher else [],
                    cover_url=cover_url,
                    genres=genres,
                    detail_loaded=False,
                )
            )

        return books

    def parse_detail_page(self, html: str, *, partial: SourceBook | None = None) -> SourceBook:
        tree = HTMLParser(html)
        info = self._parse_detail_info(tree)
        title = normalize_title(self._text(tree.css_first(self._selectors.detail_title)))
        description = (
            self._text(tree.css_first(self._selectors.detail_description))
            or self._meta_content(tree, self._selectors.detail_meta_description)
        )
        cover_node = tree.css_first(self._selectors.detail_cover)
        cover_url = (
            self._meta_content(tree, self._selectors.detail_og_image)
            or to_absolute_url(
                self.BASE_URL,
                self._attr(cover_node, "data-src") or self._attr(cover_node, "src"),
            )
        )
        authors = self._detail_values(info, self.AUTHOR_LABELS)
        narrators = self._detail_values(info, self.NARRATOR_LABELS)
        publishers = self._detail_values(info, self.PUBLISHER_LABELS)
        published_year = extract_year(self._detail_value(info, self.YEAR_LABELS))
        duration_minutes = parse_duration_to_minutes(self._detail_value(info, self.DURATION_LABELS))

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
                    "genres": partial.genres,
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
            duration_minutes=duration_minutes,
            detail_loaded=True,
        )

    def _parse_detail_info(self, tree: HTMLParser) -> dict[str, list[str]]:
        values: dict[str, list[str]] = {}

        for block in tree.css(self._selectors.detail_info_blocks):
            labels = [self._text(node) for node in block.css("dt")]
            item_values = [self._text(node) for node in block.css("dd")]
            for label, raw_value in zip(labels, item_values, strict=False):
                if label is None or raw_value is None:
                    continue
                values.setdefault(label, []).append(raw_value)

        return {
            key: unique_preserving_order(item_values)
            for key, item_values in values.items()
        }

    def _split_categories(self, value: str | None) -> list[str]:
        normalized = normalize_whitespace(value)
        if normalized is None:
            return []
        return unique_preserving_order(part.strip() for part in normalized.split(","))

    def _filter_genres(self, values: list[str], *, publisher: str | None) -> list[str]:
        publisher_key = normalize_match_text(publisher)
        genres: list[str] = []
        for value in values:
            normalized_value = normalize_match_text(value)
            if normalized_value in self.GENERIC_GENRES:
                continue
            if publisher_key and normalized_value == publisher_key:
                continue
            genres.append(value)
        return genres

    def _detail_value(self, info: dict[str, list[str]], labels: tuple[str, ...]) -> str | None:
        values = self._detail_values(info, labels)
        if not values:
            return None
        return values[0]

    def _detail_values(self, info: dict[str, list[str]], labels: tuple[str, ...]) -> list[str]:
        for label in labels:
            values = info.get(label)
            if values:
                return values
        return []

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

    def _meta_content(self, tree: HTMLParser, selector: str) -> str | None:
        node = tree.css_first(selector)
        if node is None:
            return None
        return normalize_whitespace(node.attributes.get("content"))
