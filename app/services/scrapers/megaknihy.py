from __future__ import annotations

import json
import re
from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit

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
    to_absolute_url,
    unique_preserving_order,
)


@dataclass(frozen=True)
class MegaknihySelectors:
    search_result_items: str = "#product_list > li.ajax_block_product"
    search_title_link: str = "h2 a[title]"
    search_author_nodes: str = ".product-author"
    search_cover: str = ".image-block img"
    search_ribbons: str = ".ribbons .ribbon"
    search_source_id: str = ".add-to-library"
    detail_author_links: str = ".product-author a[itemprop='author'], .product-author [itemprop='author']"
    detail_cover: str = "img[itemprop='image']"
    detail_detail_items: str = "#product_details li"
    detail_description: str = "#rich-description .rich-product-description"
    detail_tag_spans: str = "#product-tags-cont .product-tag span"
    detail_json_ld: str = "script[type='application/ld+json']"


@dataclass(frozen=True)
class MegaknihySearchMetadata:
    authors: list[str]
    categories: list[str]
    publisher: str | None


class MegaknihyScraper(BaseMetadataScraper):
    source_name = "megaknihy"

    BASE_URL = "https://www.megaknihy.cz"
    SEARCH_URL = f"{BASE_URL}/vyhledavani"

    SEARCH_ANALYTICS_RE = re.compile(r"var gtm = (?P<payload>\{.*?\});\s*</script>", re.S)
    SOURCE_ID_RE = re.compile(r"/(?P<id>\d+)-[^/?#]+\.html", re.IGNORECASE)
    NARRATOR_IN_TITLE_RE = re.compile(r"\((?:čte|čtou)\s+(?P<narrators>[^)]+)\)", re.IGNORECASE)
    AUDIOBOOK_TITLE_RE = re.compile(
        r"\baudioknih(?:a|ovna|y)\b|\bcd(?:\s|-)?mp3\b|\b\d+\s*cd\b|\bčte\b",
        re.IGNORECASE,
    )

    AUDIOBOOK_CATEGORY_MARKERS = {
        "audioknihy",
        "mluvene slovo",
        "zvukove",
    }
    NEGATIVE_RIBBON_MARKERS = {
        "e kniha",
    }
    GENERIC_SEARCH_CATEGORIES = {
        "knihy",
        "audioknihy",
        "ostatni",
        "media",
        "cd",
        "dvd",
    }
    GENERIC_DETAIL_TAGS = {
        "audioknihy",
        "cd audio kniha",
        "mluvene slovo",
        "namluvena literatura",
    }
    UNKNOWN_AUTHOR_MARKERS = {
        "autor neuveden",
        "neuveden",
    }

    def __init__(self, *, http_client: HttpClient) -> None:
        self._http_client = http_client
        self._selectors = MegaknihySelectors()

    async def search(self, query: str, author: str | None = None) -> list[SourceBook]:
        del author
        html = await self._http_client.get_text(
            self.SEARCH_URL,
            params={
                "orderby": "position",
                "orderway": "desc",
                "search_query": normalize_whitespace(query) or "",
            },
        )
        return self.parse_search_results(html)

    async def enrich(self, item: SourceBook) -> SourceBook:
        html = await self._http_client.get_text(item.detail_url)
        return self.parse_detail_page(html, partial=item)

    def parse_search_results(self, html: str) -> list[SourceBook]:
        tree = HTMLParser(html)
        analytics = self._extract_search_metadata(html)
        books: list[SourceBook] = []

        for item in tree.css(self._selectors.search_result_items):
            title_link = item.css_first(self._selectors.search_title_link)
            raw_title = self._attr(title_link, "title") or self._text(title_link)
            detail_url = self._canonicalize_url(self._attr(title_link, "href"))
            source_id = (
                self._attr(item.css_first(self._selectors.search_source_id), "data-product-id")
                or self._source_id_from_url(detail_url)
            )
            if raw_title is None or detail_url is None or source_id is None:
                continue

            metadata = analytics.get(source_id)
            ribbons = self._texts(item.css(self._selectors.search_ribbons))
            if not self._is_audiobook_result(
                raw_title=raw_title,
                detail_url=detail_url,
                ribbons=ribbons,
                categories=metadata.categories if metadata else [],
            ):
                continue

            cleaned_title = self._clean_title(raw_title)
            authors = self._people_from_values(self._texts(item.css(self._selectors.search_author_nodes)))
            if not authors and metadata is not None:
                authors = metadata.authors

            publishers = [metadata.publisher] if metadata and metadata.publisher else []
            genres = self._filter_search_categories(metadata.categories if metadata else [])
            cover_url = to_absolute_url(self.BASE_URL, self._image_url(item.css_first(self._selectors.search_cover)))

            books.append(
                SourceBook(
                    source=self.source_name,
                    source_id=source_id,
                    title=cleaned_title or raw_title,
                    detail_url=detail_url,
                    authors=authors,
                    narrators=self._extract_narrators(raw_title),
                    publishers=publishers,
                    cover_url=cover_url,
                    genres=genres,
                    detail_loaded=False,
                )
            )

        return books

    def parse_detail_page(self, html: str, *, partial: SourceBook | None = None) -> SourceBook:
        tree = HTMLParser(html)
        product = self._extract_product_payload(tree)
        details = self._parse_detail_items(tree)

        raw_title = self._string(product.get("name")) if product else None
        title = self._clean_title(raw_title) or (partial.title if partial is not None else "")
        authors = self._people_from_values(self._texts(tree.css(self._selectors.detail_author_links)))
        narrators = self._extract_narrators(raw_title)
        publishers = self._optional_list(details.get("Výrobce"))
        published_year = extract_year(details.get("Rok vydání"))
        language = map_language_to_code(details.get("Jazyk"))
        cover_url = to_absolute_url(
            self.BASE_URL,
            self._string(product.get("image")) if product else self._image_url(tree.css_first(self._selectors.detail_cover)),
        )
        description = self._html_to_text(self._string(product.get("description"))) or self._text(
            tree.css_first(self._selectors.detail_description)
        )
        genres = self._filter_detail_tags(
            self._texts(tree.css(self._selectors.detail_tag_spans)),
            title=title,
            authors=authors or (partial.authors if partial is not None else []),
            publishers=publishers or (partial.publishers if partial is not None else []),
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
                    "detail_loaded": True,
                }
            )

        return SourceBook(
            source=self.source_name,
            source_id=self._string(product.get("sku")) or "unknown" if product else "unknown",
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
            detail_loaded=True,
        )

    def _extract_search_metadata(self, html: str) -> dict[str, MegaknihySearchMetadata]:
        match = self.SEARCH_ANALYTICS_RE.search(html)
        if match is None:
            return {}

        try:
            payload = json.loads(match.group("payload"))
        except json.JSONDecodeError:
            return {}

        events = payload.get("events", {})
        if not isinstance(events, dict):
            return {}

        gtm = events.get("GTM", {})
        if not isinstance(gtm, dict):
            return {}

        products = gtm.get("viewItemList", {}).get("products")
        if not isinstance(products, list):
            products = gtm.get("viewSearchResults", {}).get("products")
        if not isinstance(products, list):
            return {}

        metadata: dict[str, MegaknihySearchMetadata] = {}
        for product in products:
            if not isinstance(product, dict):
                continue

            source_id = self._string(product.get("id"))
            if source_id is None:
                continue

            raw_categories = product.get("category", [])
            categories: list[str] = []
            if isinstance(raw_categories, list):
                categories = unique_preserving_order(
                    category.get("name")
                    for category in raw_categories
                    if isinstance(category, dict)
                )

            raw_authors = product.get("author", [])
            authors = self._people_from_values(raw_authors if isinstance(raw_authors, list) else [])

            metadata[source_id] = MegaknihySearchMetadata(
                authors=authors,
                categories=categories,
                publisher=self._string(product.get("manufacturer")),
            )

        return metadata

    def _extract_product_payload(self, tree: HTMLParser) -> dict[str, object] | None:
        node = tree.css_first(self._selectors.detail_json_ld)
        if node is None:
            return None
        raw_payload = self._text(node)
        if raw_payload is None:
            return None

        try:
            payload = json.loads(raw_payload)
        except json.JSONDecodeError:
            return None

        if isinstance(payload, list):
            for item in payload:
                if isinstance(item, dict) and self._string(item.get("@type")) == "Product":
                    return item
            return None

        if isinstance(payload, dict):
            return payload
        return None

    def _parse_detail_items(self, tree: HTMLParser) -> dict[str, str]:
        values: dict[str, str] = {}

        for item in tree.css(self._selectors.detail_detail_items):
            label_node = item.css_first("span")
            label = self._text(label_node)
            text = self._text(item)
            if label is None or text is None:
                continue

            normalized_label = normalize_whitespace(label.rstrip(":"))
            if normalized_label is None:
                continue

            value = normalize_whitespace(text.removeprefix(label).lstrip(": "))
            if value is None:
                continue

            values[normalized_label] = value

        return values

    def _is_audiobook_result(
        self,
        *,
        raw_title: str,
        detail_url: str,
        ribbons: list[str],
        categories: list[str],
    ) -> bool:
        normalized_ribbons = {normalize_match_text(ribbon) for ribbon in ribbons}
        normalized_categories = {normalize_match_text(category) for category in categories}

        if normalized_ribbons & self.NEGATIVE_RIBBON_MARKERS:
            return False
        if "/audioknihy/" in detail_url.lower():
            return True
        if normalized_categories & self.AUDIOBOOK_CATEGORY_MARKERS:
            return True
        if "cd dvd" in normalized_ribbons:
            return True
        return self.AUDIOBOOK_TITLE_RE.search(raw_title) is not None

    def _clean_title(self, raw_title: str | None) -> str | None:
        title = normalize_title(raw_title)
        if title is None:
            return None

        title = re.sub(r"^E-kniha:\s*", "", title, flags=re.IGNORECASE)
        title = self.NARRATOR_IN_TITLE_RE.sub("", title)
        title = re.sub(r"\s*[-+]\s*(?:\d+\s*)?CD(?:\s|-)?MP3\s*$", "", title, flags=re.IGNORECASE)
        title = re.sub(r"\s*[-+]\s*(?:\d+\s*)?CD\s*$", "", title, flags=re.IGNORECASE)
        title = re.sub(r"\s+CD(?:\s|-)?MP3\s*$", "", title, flags=re.IGNORECASE)
        title = re.sub(r"\s*[-+]\s*audiokniha(?:\s+pro\s+d[ěe]ti)?\s*$", "", title, flags=re.IGNORECASE)
        title = re.sub(r"\s*[-+]\s*audioknihovna\s*$", "", title, flags=re.IGNORECASE)

        return normalize_title(title) or normalize_title(raw_title)

    def _extract_narrators(self, raw_title: str | None) -> list[str]:
        normalized_title = normalize_title(raw_title)
        if normalized_title is None:
            return []

        match = self.NARRATOR_IN_TITLE_RE.search(normalized_title)
        if match is None:
            return []

        return self._people_from_values(re.split(r"\s*,\s*|\s+a\s+", match.group("narrators")))

    def _filter_search_categories(self, categories: list[str]) -> list[str]:
        filtered: list[str] = []
        for category in unique_preserving_order(categories):
            if normalize_match_text(category) in self.GENERIC_SEARCH_CATEGORIES:
                continue
            filtered.append(category)
        return filtered

    def _filter_detail_tags(
        self,
        tags: list[str],
        *,
        title: str,
        authors: list[str],
        publishers: list[str],
    ) -> list[str]:
        excluded_exact = {
            normalize_match_text(title),
            *(normalize_match_text(author) for author in authors),
            *(normalize_match_text(publisher) for publisher in publishers),
            *self.GENERIC_DETAIL_TAGS,
        }
        excluded_contains = [
            normalize_match_text(value)
            for value in [title, *authors, *publishers]
            if normalize_match_text(value)
        ]

        filtered: list[str] = []
        for tag in unique_preserving_order(tags):
            normalized_tag = normalize_match_text(tag)
            if normalized_tag in excluded_exact:
                continue
            if any(excluded in normalized_tag for excluded in excluded_contains):
                continue
            filtered.append(tag)
        return filtered

    def _people_from_values(self, values: list[object]) -> list[str]:
        people: list[str] = []
        for value in values:
            normalized = self._string(value)
            if normalized is None:
                continue
            parts = [part.strip() for part in normalized.split(",")]
            for part in parts:
                if normalize_match_text(part) in self.UNKNOWN_AUTHOR_MARKERS:
                    continue
                people.append(part)
        return unique_preserving_order(people)

    def _canonicalize_url(self, href: str | None) -> str | None:
        url = to_absolute_url(self.BASE_URL, href)
        if url is None:
            return None
        parsed = urlsplit(url)
        return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))

    def _source_id_from_url(self, detail_url: str | None) -> str | None:
        if detail_url is None:
            return None
        match = self.SOURCE_ID_RE.search(detail_url)
        if match is None:
            return None
        return match.group("id")

    def _image_url(self, node: Node | None) -> str | None:
        if node is None:
            return None
        src = self._attr(node, "src")
        if src is not None:
            return src
        srcset = self._attr(node, "srcset")
        if srcset is None:
            return None
        first_candidate = srcset.split(",")[0].strip()
        if not first_candidate:
            return None
        return first_candidate.split(" ")[0]

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

    def _optional_list(self, value: str | None) -> list[str]:
        normalized = normalize_whitespace(value)
        if normalized is None:
            return []
        return [normalized]

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

    def _string(self, value: object) -> str | None:
        if value is None:
            return None
        return normalize_whitespace(str(value))
