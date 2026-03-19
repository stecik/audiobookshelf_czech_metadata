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
    normalize_match_text,
    normalize_title,
    normalize_whitespace,
    parse_duration_to_minutes,
    to_absolute_url,
    unique_preserving_order,
)


@dataclass(frozen=True)
class RozhlasSelectors:
    search_result_items: str = ".b-008d__list > .b-008d__list-item"
    search_title_link: str = ".b-008d__subblock--content h3 a"
    search_description: str = ".b-008d__subblock--content p"
    search_meta_rows: str = ".b-008d__meta-line"
    search_tag_labels: str = ".b-008d__block--image .tag span"
    search_picture_sources: str = ".b-008d__block--image picture source"
    search_picture_image: str = ".b-008d__block--image picture img"
    detail_title: str = "h1.page-type--serial, h1.article-type, h1.event-title, h1"
    detail_player: str = ".mujRozhlasPlayer"
    detail_perex: str = ".field.field-perex"
    detail_credit_rows: str = ".asset.a-002 .a-002__row"
    detail_meta_description: str = "meta[name='description']"
    detail_meta_image: str = "meta[property='og:image']"
    detail_meta_language: str = "meta[http-equiv='content-language']"
    detail_meta_publisher: str = "meta[property='article:publisher']"


@dataclass(frozen=True)
class RozhlasCreditInfo:
    authors: list[str]
    narrators: list[str]
    years: list[str]


class RozhlasScraper(BaseMetadataScraper):
    source_name = "rozhlas"

    BASE_URL = "https://temata.rozhlas.cz"
    SEARCH_URL = f"{BASE_URL}/hry-a-cetba"
    DEFAULT_PUBLISHER = "Český rozhlas"

    DATA_LAYER_RE = re.compile(r"dataLayer\s*=\s*(?P<payload>\[.*?\])\s*;", re.S)
    SOURCE_ID_RE = re.compile(r"-(?P<source_id>\d+)(?:[/?#]|$)")
    TITLE_AUTHOR_PREFIX_RE = re.compile(r"^(?P<author>[^:]{3,120}):\s*(?P<title>.+)$")
    LABEL_VALUE_RE = re.compile(r"^(?P<label>[^:]+):\s*(?P<value>.*)$")

    PERFORMANCE_LABELS = {
        "cte",
        "hraji",
        "interpret",
        "interpretuje",
        "ucinkuje",
        "ucinkuji",
    }
    NOISE_TAGS = {"vsechny dily"}
    NOISE_PEOPLE = {"a dalsi", "aj", "aj.", "dalsi"}

    def __init__(self, *, http_client: HttpClient) -> None:
        self._http_client = http_client
        self._selectors = RozhlasSelectors()

    async def search(self, query: str, author: str | None = None) -> list[SourceBook]:
        cleaned_query = normalize_whitespace(query) or ""
        composed_query = self._compose_search_query(query=query, author=author)
        if not author or composed_query == cleaned_query:
            return await self._search_books(composed_query)

        return await self._prefer_primary_results(
            primary=lambda: self._search_books(composed_query),
            fallback=lambda: self._search_books(cleaned_query),
        )

    async def enrich(self, item: SourceBook) -> SourceBook:
        html = await self._http_client.get_text(item.detail_url)
        return self.parse_detail_page(html, partial=item)

    def parse_search_results(self, html: str) -> list[SourceBook]:
        tree = HTMLParser(html)
        books: list[SourceBook] = []

        for item in tree.css(self._selectors.search_result_items):
            title_link = item.css_first(self._selectors.search_title_link)
            raw_title = self._text(title_link)
            detail_url = to_absolute_url(self.BASE_URL, self._attr(title_link, "href"))
            source_id = self._extract_source_id(detail_url)
            if raw_title is None or detail_url is None or source_id is None:
                continue

            meta = self._parse_meta_rows(item.css(self._selectors.search_meta_rows))
            authors = self._split_people(meta.get("Autor"))
            title = normalize_title(raw_title)
            if authors:
                title = self._clean_title(title, authors=authors)
            else:
                inferred_author, inferred_title = self._infer_author_prefix(raw_title)
                if inferred_author is not None:
                    authors = [inferred_author]
                    title = inferred_title
            if title is None:
                continue

            books.append(
                SourceBook(
                    source=self.source_name,
                    source_id=source_id,
                    title=title,
                    detail_url=detail_url,
                    authors=authors,
                    publishers=[self.DEFAULT_PUBLISHER],
                    description=self._text(
                        item.css_first(self._selectors.search_description)
                    ),
                    cover_url=self._picture_url(item),
                    genres=self._search_tags(item),
                    language="cs",
                    duration_minutes=parse_duration_to_minutes(meta.get("Délka audia")),
                    detail_loaded=False,
                )
            )

        return books

    async def _search_books(self, search_term: str) -> list[SourceBook]:
        html = await self._http_client.get_text(
            self.SEARCH_URL, params={"combine": search_term}
        )
        return self.parse_search_results(html)

    def parse_detail_page(
        self, html: str, *, partial: SourceBook | None = None
    ) -> SourceBook:
        tree = HTMLParser(html)
        data_layer = self._extract_data_layer_payload(html)
        player_payload = self._decode_player_payload(
            tree.css_first(self._selectors.detail_player)
        )
        credit_info = self._extract_credit_info(tree)

        authors = list(partial.authors) if partial is not None else []
        if not authors:
            authors = credit_info.authors or self._authors_from_data_layer(data_layer)

        raw_title = self._text(tree.css_first(self._selectors.detail_title))
        title = self._clean_title(raw_title, authors=authors)
        if title is None:
            title = partial.title if partial is not None else ""

        narrators = credit_info.narrators
        publishers = [
            self._normalize_publisher(
                self._meta_content(tree, self._selectors.detail_meta_publisher)
            )
        ]
        publishers = [publisher for publisher in publishers if publisher is not None]
        if not publishers and partial is not None:
            publishers = partial.publishers
        if not publishers:
            publishers = [self.DEFAULT_PUBLISHER]

        genres = unique_preserving_order(
            [
                *(partial.genres if partial is not None else []),
                *self._genres_from_data_layer(data_layer),
            ]
        )
        description = (
            self._text(tree.css_first(self._selectors.detail_perex))
            or self._meta_content(tree, self._selectors.detail_meta_description)
            or (partial.description if partial is not None else None)
        )
        cover_url = (
            self._cover_from_player_payload(player_payload)
            or self._meta_content(tree, self._selectors.detail_meta_image)
            or (partial.cover_url if partial is not None else None)
        )
        published_year = self._resolve_published_year(credit_info.years, data_layer)
        duration_minutes = self._duration_from_player_payload(player_payload)
        language = normalize_match_text(
            self._meta_content(tree, self._selectors.detail_meta_language)
        )
        language_code = "cs" if language in {"cs", "cestina"} or not language else None

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
                    "genres": genres,
                    "language": language_code or partial.language or "cs",
                    "duration_minutes": duration_minutes or partial.duration_minutes,
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
            language=language_code or "cs",
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

    def _extract_data_layer_payload(self, html: str) -> dict[str, Any] | None:
        match = self.DATA_LAYER_RE.search(html)
        if match is None:
            return None
        try:
            payload = json.loads(match.group("payload"))
        except json.JSONDecodeError:
            return None
        if not isinstance(payload, list) or not payload:
            return None
        first = payload[0]
        if not isinstance(first, dict):
            return None
        return first

    def _decode_player_payload(self, node: Node | None) -> dict[str, Any] | None:
        raw_payload = self._attr(node, "data-player")
        if raw_payload is None:
            return None
        try:
            payload = json.loads(raw_payload)
        except json.JSONDecodeError:
            return None
        if not isinstance(payload, dict):
            return None
        return payload

    def _parse_meta_rows(self, rows: list[Node]) -> dict[str, str]:
        values: dict[str, str] = {}
        for row in rows:
            label = self._text(row.css_first(".b-008d__meta-label"))
            value = self._text(row.css_first(".b-008d__meta-value"))
            if label is None or value is None:
                continue
            values[label] = value
        return values

    def _search_tags(self, item: Node) -> list[str]:
        return unique_preserving_order(
            tag
            for tag in (
                self._text(node) for node in item.css(self._selectors.search_tag_labels)
            )
            if normalize_match_text(tag) not in self.NOISE_TAGS
        )

    def _picture_url(self, item: Node) -> str | None:
        for source in item.css(self._selectors.search_picture_sources):
            url = self._srcset_url(
                self._attr(source, "data-srcset") or self._attr(source, "srcset")
            )
            if url is not None:
                return to_absolute_url(self.BASE_URL, url)

        image = item.css_first(self._selectors.search_picture_image)
        return to_absolute_url(
            self.BASE_URL,
            self._srcset_url(
                self._attr(image, "data-srcset") or self._attr(image, "srcset")
            )
            or self._attr(image, "data-src")
            or self._attr(image, "src"),
        )

    def _srcset_url(self, value: str | None) -> str | None:
        normalized = normalize_whitespace(value)
        if normalized is None:
            return None
        return normalized.split(" ", 1)[0]

    def _extract_source_id(self, detail_url: str | None) -> str | None:
        normalized = normalize_whitespace(detail_url)
        if normalized is None:
            return None
        match = self.SOURCE_ID_RE.search(normalized)
        if match is None:
            return None
        return match.group("source_id")

    def _infer_author_prefix(
        self, raw_title: str | None
    ) -> tuple[str | None, str | None]:
        normalized = normalize_title(raw_title)
        if normalized is None:
            return None, None

        match = self.TITLE_AUTHOR_PREFIX_RE.match(normalized)
        if match is None:
            return None, normalized

        author = normalize_whitespace(match.group("author"))
        title = normalize_title(match.group("title"))
        if author is None or title is None or not self._looks_like_person_name(author):
            return None, normalized
        return author, title

    def _clean_title(self, raw_title: str | None, *, authors: list[str]) -> str | None:
        normalized = normalize_title(raw_title)
        if normalized is None:
            return None

        match = self.TITLE_AUTHOR_PREFIX_RE.match(normalized)
        if match is None:
            return normalized

        author_prefix = normalize_whitespace(match.group("author"))
        stripped_title = normalize_title(match.group("title"))
        if author_prefix is None or stripped_title is None:
            return normalized

        known_authors = {normalize_match_text(author) for author in authors}
        if normalize_match_text(author_prefix) in known_authors:
            return stripped_title
        return normalized

    def _looks_like_person_name(self, value: str) -> bool:
        tokens = [token.strip(".,") for token in value.split(" ") if token]
        if len(tokens) < 2 or len(tokens) > 5:
            return False
        if any(any(character.isdigit() for character in token) for token in tokens):
            return False
        return all(token[:1].isupper() for token in tokens if token)

    def _extract_credit_info(self, tree: HTMLParser) -> RozhlasCreditInfo:
        authors: list[str] = []
        narrators: list[str] = []
        years: list[str] = []

        for row in tree.css(self._selectors.detail_credit_rows):
            for strong in row.css("strong"):
                author = self._author_from_credit_heading(self._text(strong))
                if author is not None:
                    authors.append(author)

            lines = self._lines(row)
            for index, line in enumerate(lines):
                label, value = self._extract_label_value(line)
                if label is None:
                    continue
                if (
                    value is None
                    and index + 1 < len(lines)
                    and not self._has_label(lines[index + 1])
                ):
                    value = lines[index + 1]
                if value is None:
                    continue

                normalized_label = normalize_match_text(label)
                if normalized_label in self.PERFORMANCE_LABELS:
                    narrators.extend(self._split_people(value))
                elif normalized_label == "natoceno":
                    year = extract_year(value)
                    if year is not None:
                        years.append(year)

        return RozhlasCreditInfo(
            authors=unique_preserving_order(authors),
            narrators=unique_preserving_order(narrators),
            years=unique_preserving_order(years),
        )

    def _author_from_credit_heading(self, value: str | None) -> str | None:
        normalized = normalize_title(value)
        if normalized is None:
            return None
        match = self.TITLE_AUTHOR_PREFIX_RE.match(normalized)
        if match is None:
            return None
        author = normalize_whitespace(match.group("author"))
        title = normalize_whitespace(match.group("title"))
        if author is None or title is None or not self._looks_like_person_name(author):
            return None
        return author

    def _extract_label_value(self, line: str) -> tuple[str | None, str | None]:
        match = self.LABEL_VALUE_RE.match(line)
        if match is None:
            return None, None
        label = normalize_whitespace(match.group("label"))
        value = normalize_whitespace(match.group("value"))
        return label, value

    def _has_label(self, line: str) -> bool:
        label, _ = self._extract_label_value(line)
        return label is not None

    def _authors_from_data_layer(self, data_layer: dict[str, Any] | None) -> list[str]:
        if data_layer is None:
            return []
        if (
            normalize_match_text(self._string(data_layer.get("entityBundle")))
            == "serial"
        ):
            return []
        return unique_preserving_order([self._string(data_layer.get("contentAuthor"))])

    def _genres_from_data_layer(self, data_layer: dict[str, Any] | None) -> list[str]:
        if data_layer is None:
            return []

        genres: list[str] = []
        genres.extend(self._dict_values(data_layer.get("format")))
        genres.extend(self._dict_values(data_layer.get("theme")))
        custom_label = self._string(data_layer.get("customLabel"))
        if custom_label is not None:
            genres.append(custom_label)
        return unique_preserving_order(genres)

    def _resolve_published_year(
        self,
        years: list[str],
        data_layer: dict[str, Any] | None,
    ) -> str | None:
        unique_years = unique_preserving_order(years)
        if len(unique_years) == 1:
            return unique_years[0]
        if data_layer is None:
            return None
        return extract_year(
            self._string(data_layer.get("pDateStart"))
            or self._string(data_layer.get("contentCreationDateGMT"))
            or self._string(data_layer.get("airedDate"))
        )

    def _duration_from_player_payload(
        self, player_payload: dict[str, Any] | None
    ) -> int | None:
        if player_payload is None:
            return None
        data = player_payload.get("data")
        if not isinstance(data, dict):
            return None
        playlist = data.get("playlist")
        if not isinstance(playlist, list):
            return None

        total_seconds = 0
        for item in playlist:
            if not isinstance(item, dict):
                continue
            duration = item.get("duration")
            if isinstance(duration, int):
                total_seconds += duration

        if total_seconds <= 0:
            return None
        return max(1, total_seconds // 60)

    def _cover_from_player_payload(
        self, player_payload: dict[str, Any] | None
    ) -> str | None:
        if player_payload is None:
            return None
        data = player_payload.get("data")
        if not isinstance(data, dict):
            return None
        poster = data.get("poster")
        if not isinstance(poster, dict):
            return None
        return to_absolute_url(self.BASE_URL, self._string(poster.get("src")))

    def _normalize_publisher(self, value: str | None) -> str | None:
        normalized = normalize_whitespace(value)
        if normalized is None:
            return None
        if "Český rozhlas" in normalized or "Czech Radio" in normalized:
            return self.DEFAULT_PUBLISHER
        return normalized

    def _meta_content(self, tree: HTMLParser, selector: str) -> str | None:
        node = tree.css_first(selector)
        if node is None:
            return None
        return normalize_whitespace(node.attributes.get("content"))

    def _dict_values(self, value: object) -> list[str]:
        if not isinstance(value, dict):
            return []
        return unique_preserving_order(
            self._string(item_value) for item_value in value.values()
        )

    def _split_people(self, value: str | None) -> list[str]:
        normalized = normalize_whitespace(value)
        if normalized is None:
            return []

        parts = re.split(r"\s*,\s*|\s*;\s*|\s+a\s+", normalized)
        return unique_preserving_order(
            part
            for part in parts
            if normalize_match_text(part) not in self.NOISE_PEOPLE
        )

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
            if (normalized := normalize_whitespace(raw_line)) is not None
        ]

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

    def _string(self, value: object) -> str | None:
        if value is None:
            return None
        return normalize_whitespace(str(value))
