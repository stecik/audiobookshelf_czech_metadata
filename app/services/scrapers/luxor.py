from __future__ import annotations

import base64
import json
from typing import Any

from app.clients.http import HttpClient
from app.models import SourceBook
from app.services.scrapers.base import BaseMetadataScraper
from app.utils.text import (
    extract_year,
    map_language_to_code,
    normalize_match_text,
    normalize_title,
    normalize_whitespace,
    to_absolute_url,
    unique_preserving_order,
)


class LuxorScraper(BaseMetadataScraper):
    source_name = "luxor"

    BASE_URL = "https://www.luxor.cz"
    SEARCH_URL = f"{BASE_URL}/api/luigis/search"
    IMAGE_URL_PREFIX = "https://img.luxor.cz/suggest/222/351/"

    AUDIOBOOK_ASSORTMENTS = (31, 20)
    AUDIOBOOK_PRODUCT_TYPES = frozenset({"017", "022"})
    CULTURE_ID = 34
    PAGE_INDEX = 1
    PAGE_SIZE = 24
    CATALOG_BASE_SEARCH = 5
    GENERIC_GENRES = {
        "audioknihy",
        "audioknihy ke stazeni",
        "audioknihy na cd",
    }

    def __init__(self, *, http_client: HttpClient) -> None:
        self._http_client = http_client

    async def search(self, query: str, author: str | None = None) -> list[SourceBook]:
        cleaned_query = normalize_whitespace(query) or ""
        if author is None:
            return await self._search_books(query=cleaned_query, author=None)

        return await self._prefer_primary_results(
            primary=lambda: self._search_books(query=cleaned_query, author=author),
            fallback=lambda: self._search_books(query=cleaned_query, author=None),
        )

    async def enrich(self, item: SourceBook) -> SourceBook:
        # Luxor detail pages are client-rendered shells, so the search payload is the reliable source for now.
        return item

    def parse_search_response(self, payload: dict[str, Any]) -> list[SourceBook]:
        products = payload.get("products", {})
        if not isinstance(products, dict):
            return []

        items = products.get("products", [])
        if not isinstance(items, list):
            return []

        books: list[SourceBook] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            book = self._book_from_product(item)
            if book is not None:
                books.append(book)

        return books

    async def _search_books(self, *, query: str, author: str | None) -> list[SourceBook]:
        payload = await self._fetch_search_payload(query=query, author=author)
        return self.parse_search_response(payload)

    async def _fetch_search_payload(self, *, query: str, author: str | None) -> dict[str, Any]:
        payload = await self._http_client.get_json(
            self.SEARCH_URL,
            params={"params": self._encode_request(self._build_search_request(query=query, author=author))},
        )
        return payload if isinstance(payload, dict) else {}

    def _build_search_request(self, *, query: str, author: str | None) -> dict[str, Any]:
        return {
            "phrase": normalize_whitespace(query) or "",
            "categoryId": None,
            "cultureId": self.CULTURE_ID,
            "pageIndex": self.PAGE_INDEX,
            "pageSize": self.PAGE_SIZE,
            "authorPhrase": normalize_whitespace(author),
            "producerPhrase": None,
            "priceRange": None,
            "orderByKeys": ["recommended_desc"],
            "producers": [],
            "flags": [],
            "fastFlags": [],
            "availabilities": [],
            "assortmants": list(self.AUDIOBOOK_ASSORTMENTS),
            "ratings": [],
            "recommendedAge": [],
            "authors": [],
            "series": [],
            "editions": [],
            "bindings": [],
            "languages": [],
            "storeId": None,
            "catalogBase": self.CATALOG_BASE_SEARCH,
            "howManyAssortments": 5,
            "howManyAuthors": 10,
            "howManyAvailabilities": 5,
            "howManyEditions": 5,
            "howManyFastFlags": 5,
            "howManyFlags": 5,
            "howManyProducers": 10,
            "howManySeries": 5,
            "howManyBindings": 5,
            "howManyLanguages": 5,
            "howManyRecommendedAge": 25,
        }

    def _book_from_product(self, product: dict[str, Any]) -> SourceBook | None:
        variant = self._first_variant(product)
        if variant is None or not self._is_audiobook_variant(variant):
            return None

        source_id = self._string(variant.get("id"))
        title = normalize_title(self._string(variant.get("name")))
        detail_url = self._detail_url(
            source_id=source_id,
            slug=self._string(variant.get("seoUrl")),
        )
        if source_id is None or title is None or detail_url is None:
            return None

        return SourceBook(
            source=self.source_name,
            source_id=source_id,
            title=title,
            detail_url=detail_url,
            subtitle=normalize_title(self._string(variant.get("subTitle"))),
            authors=self._authors_from_variant(variant),
            publishers=unique_preserving_order([self._string(variant.get("producerName"))]),
            published_year=extract_year(self._string(variant.get("releaseDate"))),
            description=self._string(variant.get("annotation")) or self._string(variant.get("description")),
            cover_url=self._cover_url_from_variant(variant),
            genres=self._genres_from_variant(variant),
            language=self._language_from_variant(variant),
            detail_loaded=False,
        )

    def _first_variant(self, product: dict[str, Any]) -> dict[str, Any] | None:
        variants = product.get("variants")
        if isinstance(variants, list):
            for variant in variants:
                if isinstance(variant, dict):
                    return variant
        if "codeProductTypes" in product and "id" in product:
            return product
        return None

    def _is_audiobook_variant(self, variant: dict[str, Any]) -> bool:
        product_types = {
            product_type
            for product_type in self._strings(variant.get("codeProductTypes"))
            if product_type in self.AUDIOBOOK_PRODUCT_TYPES
        }
        return bool(product_types)

    def _authors_from_variant(self, variant: dict[str, Any]) -> list[str]:
        authors = self._names_from_people(variant.get("authors"))
        if authors:
            return authors

        static_author = self._string(variant.get("staticAuthor"))
        if static_author is None:
            return []

        return unique_preserving_order(part.strip() for part in static_author.split(";"))

    def _names_from_people(self, value: object) -> list[str]:
        if not isinstance(value, list):
            return []

        return unique_preserving_order(
            self._string(item.get("name")) for item in value if isinstance(item, dict)
        )

    def _genres_from_variant(self, variant: dict[str, Any]) -> list[str]:
        genres: list[str | None] = []

        breadcrumbs = variant.get("productCategoryBreadcrumbInfo")
        if isinstance(breadcrumbs, list):
            genres.extend(
                self._string(item.get("displayName"))
                for item in breadcrumbs
                if isinstance(item, dict)
            )

        nearest_category = variant.get("nearestCategory")
        if isinstance(nearest_category, dict):
            genres.append(self._string(nearest_category.get("name")))

        return [
            genre
            for genre in unique_preserving_order(genres)
            if normalize_match_text(genre) not in self.GENERIC_GENRES
        ]

    def _language_from_variant(self, variant: dict[str, Any]) -> str | None:
        languages = variant.get("languages")
        if not isinstance(languages, list):
            return None

        for language in languages:
            if isinstance(language, dict):
                code = map_language_to_code(self._string(language.get("name")))
                if code is not None:
                    return code
            elif isinstance(language, str):
                code = map_language_to_code(language)
                if code is not None:
                    return code

        return None

    def _cover_url_from_variant(self, variant: dict[str, Any]) -> str | None:
        image_path = self._string(variant.get("imagePath"))
        if image_path is None:
            images = variant.get("images")
            if isinstance(images, list):
                for image in images:
                    if isinstance(image, dict):
                        image_path = self._string(image.get("path"))
                        if image_path is not None:
                            break

        return to_absolute_url(self.IMAGE_URL_PREFIX, image_path)

    def _detail_url(self, *, source_id: str | None, slug: str | None) -> str | None:
        if source_id is None:
            return None
        path = f"/v/{source_id}/{slug}" if slug else f"/v/{source_id}"
        return to_absolute_url(self.BASE_URL, path)

    def _encode_request(self, payload: dict[str, Any]) -> str:
        serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        return base64.b64encode(serialized.encode("utf-8")).decode("ascii")

    def _strings(self, value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        return unique_preserving_order(self._string(item) for item in value)

    def _string(self, value: object) -> str | None:
        if value is None:
            return None
        return normalize_whitespace(str(value))
