from __future__ import annotations

import re
from datetime import datetime, UTC
from typing import Any

from selectolax.parser import HTMLParser

from app.clients.http import HttpClient
from app.models import SourceBook
from app.services.scrapers.base import BaseMetadataScraper
from app.utils.text import (
    extract_year,
    normalize_match_text,
    normalize_title,
    normalize_whitespace,
    to_absolute_url,
    unique_preserving_order,
)


class ProgresGuruScraper(BaseMetadataScraper):
    source_name = "progresguru"

    BASE_URL = "https://progresguru.cz"
    SEARCH_URL = f"{BASE_URL}/api/audiobooks"
    DETAIL_URL_TEMPLATE = f"{SEARCH_URL}/{{slug}}"
    DETAIL_PAGE_URL_TEMPLATE = f"{BASE_URL}/audioknihy/{{slug}}"

    IMAGE_ALT_SUFFIX = " | ProgresGuru"
    TAG_LABELS: tuple[tuple[str, str], ...] = (
        ("new_book", "Novinky"),
        ("best_seller", "Bestsellery"),
        ("convenient_set", "Výhodné sety"),
        ("has_discount", "V akci"),
        ("preparing", "Připravujeme"),
        ("free_book", "Zdarma"),
    )
    AUTHOR_SEGMENT_RE = re.compile(r"^(?:Audiokniha\s+)?(?P<title>.+?)\s+-\s+(?P<author_part>.+)$")

    def __init__(self, *, http_client: HttpClient) -> None:
        self._http_client = http_client

    async def search(self, query: str, author: str | None = None) -> list[SourceBook]:
        search_term = self._compose_search_term(query=query, author=author)
        payload = await self._fetch_search_payload(search_term)
        books = self.parse_search_response(payload)
        if books or author is None:
            return books

        fallback_query = normalize_whitespace(query) or ""
        fallback_payload = await self._fetch_search_payload(fallback_query)
        return self.parse_search_response(fallback_payload)

    async def enrich(self, item: SourceBook) -> SourceBook:
        payload = await self._http_client.get_json(self.DETAIL_URL_TEMPLATE.format(slug=item.source_id))
        return self.parse_detail_response(payload, partial=item)

    def parse_search_response(self, payload: dict[str, Any]) -> list[SourceBook]:
        items = payload.get("audiobooks", [])
        if not isinstance(items, list):
            return []

        books: list[SourceBook] = []
        for item in items:
            if not isinstance(item, dict):
                continue

            book = self._book_from_search_item(item)
            if book is not None:
                books.append(book)

        return books

    def parse_detail_response(self, payload: dict[str, Any], *, partial: SourceBook | None = None) -> SourceBook:
        audiobook = payload.get("audiobook")
        if not isinstance(audiobook, dict):
            if partial is not None:
                return partial
            return SourceBook(
                source=self.source_name,
                title="",
                detail_url="",
                detail_loaded=False,
            )

        title = normalize_title(self._string(audiobook.get("name"))) or (partial.title if partial else "")
        subtitle = normalize_title(self._string(audiobook.get("name_sub"))) or (partial.subtitle if partial else None)
        authors = self._names_from_people(audiobook.get("authors")) or (partial.authors if partial else [])
        narrators = self._names_from_people(audiobook.get("interprets")) or (partial.narrators if partial else [])
        publishers = self._publisher_name(audiobook.get("publisher"))
        published_year = self._year_from_timestamp(audiobook.get("publish_date")) or (
            partial.published_year if partial else None
        )
        description = self._html_to_text(self._string(audiobook.get("description"))) or (
            partial.description if partial else None
        )
        cover_url = to_absolute_url(self.BASE_URL, self._string(audiobook.get("image"))) or (
            partial.cover_url if partial else None
        )
        genres = self._genres_from_categories(audiobook.get("categories")) or (partial.genres if partial else [])
        language = self._string(audiobook.get("lang")) or (partial.language if partial else None)
        duration_minutes = self._coerce_int(audiobook.get("length"))
        tags = self._tags_from_flags(audiobook.get("tags")) or (partial.tags if partial else [])

        if partial is not None:
            return partial.model_copy(
                update={
                    "title": title or partial.title,
                    "subtitle": subtitle,
                    "authors": authors or partial.authors,
                    "narrators": narrators or partial.narrators,
                    "publishers": publishers or partial.publishers,
                    "published_year": published_year,
                    "description": description,
                    "cover_url": cover_url or partial.cover_url,
                    "genres": genres or partial.genres,
                    "tags": tags or partial.tags,
                    "language": language or partial.language,
                    "duration_minutes": duration_minutes,
                    "detail_loaded": True,
                }
            )

        return SourceBook(
            source=self.source_name,
            source_id=self._string(audiobook.get("slug")) or "",
            title=title,
            detail_url=to_absolute_url(
                self.BASE_URL,
                f"/audioknihy/{self._string(audiobook.get('slug'))}" if self._string(audiobook.get("slug")) else None,
            )
            or "",
            subtitle=subtitle,
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

    async def _fetch_search_payload(self, search_term: str) -> dict[str, Any]:
        payload = await self._http_client.get_json(
            self.SEARCH_URL,
            params={"search": search_term, "page": 1},
        )
        return payload if isinstance(payload, dict) else {}

    def _compose_search_term(self, *, query: str, author: str | None) -> str:
        cleaned_query = normalize_whitespace(query) or ""
        cleaned_author = normalize_whitespace(author)
        if cleaned_author is None:
            return cleaned_query
        if normalize_match_text(cleaned_author) in normalize_match_text(cleaned_query):
            return cleaned_query
        return f"{cleaned_query} {cleaned_author}"

    def _book_from_search_item(self, item: dict[str, Any]) -> SourceBook | None:
        slug = self._string(item.get("slug"))
        title = normalize_title(self._string(item.get("name")))
        detail_url = to_absolute_url(
            self.BASE_URL,
            f"/audioknihy/{slug}" if slug else None,
        )
        if slug is None or title is None or detail_url is None:
            return None

        primary_author = self._name_from_person(item.get("author"))
        narrators = unique_preserving_order([self._name_from_person(item.get("interpret"))])
        authors_from_alt = self._authors_from_image_alt(
            image_alt=self._string(item.get("image_alt")),
            title=title,
            narrators=narrators,
        )
        authors = unique_preserving_order([primary_author, *authors_from_alt])
        genres = self._genre_from_category(item.get("category"))
        tags = self._tags_from_flags(item.get("tags"))
        published_year = self._year_from_timestamp(item.get("publish_date"))
        cover_url = to_absolute_url(self.BASE_URL, self._string(item.get("image")))
        language = self._string(item.get("lang"))

        return SourceBook(
            source=self.source_name,
            source_id=slug,
            title=title,
            detail_url=detail_url,
            authors=authors,
            narrators=narrators,
            published_year=published_year,
            cover_url=cover_url,
            genres=genres,
            tags=tags,
            language=language,
            detail_loaded=False,
        )

    def _authors_from_image_alt(self, *, image_alt: str | None, title: str, narrators: list[str]) -> list[str]:
        normalized_alt = normalize_whitespace(image_alt)
        normalized_title = normalize_title(title)
        if normalized_alt is None or normalized_title is None:
            return []

        working = normalized_alt.removesuffix(self.IMAGE_ALT_SUFFIX)
        match = self.AUTHOR_SEGMENT_RE.match(working)
        if match is None or normalize_match_text(match.group("title")) != normalize_match_text(normalized_title):
            return []

        author_part = normalize_whitespace(match.group("author_part"))
        if author_part is None:
            return []

        if narrators:
            narrator_suffix = f" ({', '.join(narrators)})"
            if author_part.endswith(narrator_suffix):
                author_part = normalize_whitespace(author_part[: -len(narrator_suffix)])

        if author_part is None or " (" in author_part:
            author_part = normalize_whitespace(author_part.rsplit(" (", 1)[0] if author_part else None)

        authors = unique_preserving_order(part.strip() for part in author_part.split(","))
        if not authors or all(self._is_abbreviated_name(author) for author in authors):
            return []
        return authors

    def _is_abbreviated_name(self, value: str) -> bool:
        normalized = normalize_whitespace(value)
        if normalized is None:
            return False
        parts = normalized.split()
        return bool(parts) and parts[0].endswith(".") and len(parts[0]) <= 2

    def _genre_from_category(self, value: object) -> list[str]:
        if not isinstance(value, dict):
            return []
        return unique_preserving_order([self._string(value.get("name"))])

    def _genres_from_categories(self, value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        return unique_preserving_order(
            self._string(item.get("name")) for item in value if isinstance(item, dict)
        )

    def _tags_from_flags(self, value: object) -> list[str]:
        if not isinstance(value, dict):
            return []
        tags: list[str] = []
        for key, label in self.TAG_LABELS:
            if value.get(key):
                tags.append(label)
        return tags

    def _names_from_people(self, value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        return unique_preserving_order(self._name_from_person(item) for item in value)

    def _publisher_name(self, value: object) -> list[str]:
        return unique_preserving_order([self._name_from_person(value)])

    def _name_from_person(self, value: object) -> str | None:
        if not isinstance(value, dict):
            return None
        name = self._string(value.get("name"))
        if name is not None:
            return name
        forename = self._string(value.get("forename"))
        surname = self._string(value.get("surname"))
        if forename and surname:
            return f"{forename} {surname}"
        return forename or surname

    def _year_from_timestamp(self, value: object) -> str | None:
        timestamp = self._coerce_int(value)
        if timestamp is None:
            return extract_year(self._string(value))
        try:
            return str(datetime.fromtimestamp(timestamp, tz=UTC).year)
        except (OverflowError, OSError, ValueError):
            return None

    def _html_to_text(self, html_fragment: str | None) -> str | None:
        normalized = normalize_whitespace(html_fragment)
        if normalized is None:
            return None
        fragment = HTMLParser(f"<div>{normalized}</div>")
        try:
            text = fragment.text(separator=" ", strip=True)
        except TypeError:
            text = fragment.text()
        return normalize_whitespace(text)

    def _coerce_int(self, value: object) -> int | None:
        if isinstance(value, bool) or value is None:
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        normalized = self._string(value)
        if normalized is None:
            return None
        try:
            return int(normalized)
        except ValueError:
            return None

    def _string(self, value: object) -> str | None:
        if value is None:
            return None
        return normalize_whitespace(str(value))
