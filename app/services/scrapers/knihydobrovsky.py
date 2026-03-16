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
    to_absolute_url,
    unique_preserving_order,
)


@dataclass(frozen=True)
class KnihyDobrovskySelectors:
    search_result_items: str = "li[data-cy='productPreviewList']"
    search_title: str = "h3.title .name"
    search_author_names: str = ".content .author-name"
    search_cover: str = "h3.title img"
    search_language_icon: str = ".product-language__inner > span"
    detail_title: str = "h1 [itemprop='name']"
    detail_people_groups: str = ".annot.with-cols .author .group"
    detail_cover: str = ".imgs__inner .img-big img"
    detail_description: str = "#popis [itemprop='description']"
    detail_info_blocks: str = ".box-book-info .item dl"
    detail_sidebar_blocks: str = ".box-params > dl"
    detail_ld_json: str = "script[type='application/ld+json']"


class KnihyDobrovskyScraper(BaseMetadataScraper):
    source_name = "knihydobrovsky"

    BASE_URL = "https://www.knihydobrovsky.cz"
    SEARCH_URL = f"{BASE_URL}/vyhledavani"
    PRODUCT_ID_RE = re.compile(r"-(?P<product_id>\d+)(?:[/?#]|$)")
    GENERIC_GENRES = {"audiokniha", "audioknihy"}

    def __init__(self, *, http_client: HttpClient) -> None:
        self._http_client = http_client
        self._selectors = KnihyDobrovskySelectors()

    async def search(self, query: str, author: str | None = None) -> list[SourceBook]:
        del author
        html = await self._http_client.get_text(
            self.SEARCH_URL,
            params={"search": normalize_whitespace(query) or ""},
        )
        return self.parse_search_results(html)

    async def enrich(self, item: SourceBook) -> SourceBook:
        html = await self._http_client.get_text(item.detail_url)
        return self.parse_detail_page(html, partial=item)

    def parse_search_results(self, html: str) -> list[SourceBook]:
        tree = HTMLParser(html)
        books: list[SourceBook] = []

        for item in tree.css(self._selectors.search_result_items):
            title_link = self._find_search_title_link(item)
            detail_url = to_absolute_url(self.BASE_URL, self._attr(title_link, "href"))
            if not self._looks_like_audiobook(detail_url):
                continue

            source_id = self._extract_product_id(detail_url)
            title = normalize_title(self._text(item.css_first(self._selectors.search_title)))
            if source_id is None or title is None or detail_url is None:
                continue

            books.append(
                SourceBook(
                    source=self.source_name,
                    source_id=source_id,
                    title=title,
                    detail_url=detail_url,
                    authors=self._texts(item.css(self._selectors.search_author_names)),
                    cover_url=self._image_url(item.css_first(self._selectors.search_cover)),
                    language=self._language_from_icon(item.css_first(self._selectors.search_language_icon)),
                    detail_loaded=False,
                )
            )

        return books

    def parse_detail_page(self, html: str, *, partial: SourceBook | None = None) -> SourceBook:
        tree = HTMLParser(html)
        ld_product = self._extract_product_ld_json(tree)
        detail_info = self._parse_definition_lists(tree.css(self._selectors.detail_info_blocks))
        sidebar_info = self._parse_definition_lists(tree.css(self._selectors.detail_sidebar_blocks))
        people = self._extract_people(tree)

        title = normalize_title(self._text(tree.css_first(self._selectors.detail_title)))
        authors = people.get("autor") or (partial.authors if partial else [])
        narrators = (
            people.get("interpret")
            or sidebar_info.get("interpreti")
            or (partial.narrators if partial else [])
        )
        publishers = detail_info.get("Nakladatel") or self._single_value_list(self._ld_brand(ld_product))
        published_year = extract_year(self._first(detail_info.get("datum vydání")))
        description = (
            self._ld_string(ld_product, "description")
            or self._text(tree.css_first(self._selectors.detail_description))
            or (partial.description if partial else None)
        )
        cover_url = self._ld_image(ld_product) or self._image_url(tree.css_first(self._selectors.detail_cover))
        genres = self._filter_genres(
            sidebar_info.get("kategorie") or self._split_category_path(self._ld_offer_category(ld_product))
        )
        tags = sidebar_info.get("Témata") or (partial.tags if partial else [])
        language = map_language_to_code(self._first(detail_info.get("jazyk"))) or (partial.language if partial else None)
        duration_minutes = parse_duration_to_minutes(self._first(detail_info.get("Délka")))

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
                    "tags": tags,
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
            tags=tags,
            language=language,
            duration_minutes=duration_minutes,
            detail_loaded=True,
        )

    def _find_search_title_link(self, item: Node) -> Node | None:
        for link in item.css("h3.title > a"):
            if link.css_first(".name") is not None:
                return link
        return item.css_first("h3.title .img.shadow a")

    def _parse_definition_lists(self, nodes: list[Node]) -> dict[str, list[str]]:
        parsed: dict[str, list[str]] = {}

        for node in nodes:
            current_label: str | None = None
            child = node.child
            while child is not None:
                if child.tag == "dt":
                    current_label = self._text(child)
                elif child.tag == "dd" and current_label:
                    values = self._texts(child.css("a"))
                    text_value = self._text(child)
                    parsed[current_label] = values or ([text_value] if text_value else [])
                child = child.next

        return {key: value for key, value in parsed.items() if value}

    def _extract_people(self, tree: HTMLParser) -> dict[str, list[str]]:
        people: dict[str, list[str]] = {}

        for group in tree.css(self._selectors.detail_people_groups):
            label = normalize_match_text(self._text(group.css_first("span")))
            links = self._texts(group.css("a"))
            if not label or not links:
                continue
            people[label] = unique_preserving_order([*people.get(label, []), *links])

        return people

    def _extract_product_ld_json(self, tree: HTMLParser) -> dict[str, Any] | None:
        for script in tree.css(self._selectors.detail_ld_json):
            raw_value = self._text(script)
            if raw_value is None:
                continue
            try:
                payload = json.loads(raw_value)
            except json.JSONDecodeError:
                continue

            if isinstance(payload, dict) and self._ld_type(payload) == "Product":
                return payload

        return None

    def _ld_type(self, payload: dict[str, Any]) -> str | None:
        raw_type = payload.get("@type")
        if isinstance(raw_type, str):
            return normalize_whitespace(raw_type)
        return None

    def _ld_string(self, payload: dict[str, Any] | None, key: str) -> str | None:
        if payload is None:
            return None
        value = payload.get(key)
        if value is None:
            return None
        return normalize_whitespace(str(value))

    def _ld_brand(self, payload: dict[str, Any] | None) -> str | None:
        if payload is None:
            return None

        brand = payload.get("brand")
        if isinstance(brand, dict):
            name = brand.get("name")
            return normalize_whitespace(str(name)) if name is not None else None
        if brand is None:
            return None
        return normalize_whitespace(str(brand))

    def _ld_offer_category(self, payload: dict[str, Any] | None) -> str | None:
        if payload is None:
            return None

        offers = payload.get("offers")
        if not isinstance(offers, dict):
            return None
        category = offers.get("category")
        return normalize_whitespace(str(category)) if category is not None else None

    def _ld_image(self, payload: dict[str, Any] | None) -> str | None:
        if payload is None:
            return None

        image = payload.get("image")
        if isinstance(image, list) and image:
            return to_absolute_url(self.BASE_URL, normalize_whitespace(str(image[0])))
        if image is None:
            return None
        return to_absolute_url(self.BASE_URL, normalize_whitespace(str(image)))

    def _split_category_path(self, value: str | None) -> list[str]:
        normalized = normalize_whitespace(value)
        if normalized is None:
            return []
        return unique_preserving_order(part.strip() for part in normalized.split("/"))

    def _filter_genres(self, values: list[str] | None) -> list[str]:
        if not values:
            return []
        return [
            value
            for value in unique_preserving_order(values)
            if normalize_match_text(value) not in self.GENERIC_GENRES
        ]

    def _single_value_list(self, value: str | None) -> list[str]:
        normalized = normalize_whitespace(value)
        return [normalized] if normalized else []

    def _image_url(self, node: Node | None) -> str | None:
        source = self._attr(node, "srcset") or self._attr(node, "src")
        if source is None:
            return None
        first_candidate = source.split(",", 1)[0].strip().split(" ", 1)[0]
        return to_absolute_url(self.BASE_URL, first_candidate)

    def _language_from_icon(self, node: Node | None) -> str | None:
        class_name = self._attr(node, "class")
        normalized = normalize_match_text(class_name)
        if "ico sk" in normalized:
            return "sk"
        if "ico en" in normalized:
            return "en"
        if "ico cs" in normalized or "ico cz" in normalized:
            return "cs"
        return None

    def _looks_like_audiobook(self, detail_url: str | None) -> bool:
        normalized = (normalize_whitespace(detail_url) or "").lower()
        return "/audiokniha" in normalized

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
