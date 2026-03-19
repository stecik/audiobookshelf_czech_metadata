from __future__ import annotations

import re
from dataclasses import dataclass
from html import unescape

from selectolax.parser import HTMLParser, Node

from app.clients.http import HttpClient, UpstreamFetchError
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
class AlzaPatterns:
    product_href: re.Pattern[str] = re.compile(
        r"(?P<href>/media/[^\"'#?\s>]+-d(?P<product_id>\d+)\.htm(?:\?[^\"'#\s<]*)?)",
        re.IGNORECASE,
    )
    order_code: re.Pattern[str] = re.compile(
        r"Objedn[aá]vac[ií]\s+k[oó]d:\s*(?P<code>[A-Z0-9]+)",
        re.IGNORECASE,
    )
    author_segment: re.Pattern[str] = re.compile(
        r"(?:^|[,-]\s*)autor\s+(?P<value>.+?)(?=(?:,\s*čte\b)|(?:,\s*\d)|$)",
        re.IGNORECASE,
    )
    narrator_segment: re.Pattern[str] = re.compile(
        r"(?:^|[,-]\s*)čte\s+(?P<value>.+?)(?=(?:,\s*\d)|$)",
        re.IGNORECASE,
    )
    leading_medium: re.Pattern[str] = re.compile(
        r"^Audiokniha(?:\s+(?:MP3|na\s+CD|ke\s+stažení))?\s*",
        re.IGNORECASE,
    )
    title_suffix: re.Pattern[str] = re.compile(
        r"\s*[|\-]\s*Audiokniha(?:\s+MP3|\s+na\s+CD|\s+ke\s+stažení)?(?:\s+na\s+Alza\.cz)?\s*$",
        re.IGNORECASE,
    )
    title_author_suffix: re.Pattern[str] = re.compile(
        r"\s*-\s*(?P<author>[^|]+?)\s*[|]\s*Audiokniha",
        re.IGNORECASE,
    )
    price_like: re.Pattern[str] = re.compile(r"^\d[\d\s]*,-$")


class AlzaScraper(BaseMetadataScraper):
    source_name = "alza"

    BASE_URL = "https://www.alza.cz"
    MOBILE_BASE_URL = "https://m.alza.cz"
    SEARCH_URL = f"{BASE_URL}/search.htm"
    MOBILE_SEARCH_URL = f"{MOBILE_BASE_URL}/search.htm"
    REQUEST_HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36"
        ),
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;q=0.9,"
            "image/avif,image/webp,*/*;q=0.8"
        ),
        "Accept-Language": "cs-CZ,cs;q=0.9,en;q=0.6",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
    }

    def __init__(self, *, http_client: HttpClient) -> None:
        self._http_client = http_client
        self._patterns = AlzaPatterns()

    async def search(self, query: str, author: str | None = None) -> list[SourceBook]:
        search_query = self._compose_search_query(query=query, author=author)

        for search_url in [self.SEARCH_URL, self.MOBILE_SEARCH_URL]:
            html = await self._http_client.get_text(
                search_url,
                params={"exps": search_query},
                extra_headers=self.REQUEST_HEADERS,
            )
            if self._looks_like_challenge_page(html):
                continue

            results = self.parse_search_results(html)
            if results:
                return results

        raise UpstreamFetchError(
            url=self.SEARCH_URL,
            reason="alza returned an anti-bot challenge page",
            timeout_seconds=self._http_client.timeout_seconds,
        )

    async def enrich(self, item: SourceBook) -> SourceBook:
        attempted_urls = [item.detail_url, self._to_mobile_detail_url(item.detail_url)]

        for detail_url in unique_preserving_order(attempted_urls):
            html = await self._http_client.get_text(detail_url, extra_headers=self.REQUEST_HEADERS)
            if self._looks_like_challenge_page(html):
                continue

            enriched = self.parse_detail_page(html, partial=item)
            if self._detail_has_signal(enriched):
                return enriched
            item = enriched

        raise UpstreamFetchError(
            url=item.detail_url,
            reason="alza returned an anti-bot challenge page",
            timeout_seconds=self._http_client.timeout_seconds,
        )

    def parse_search_results(self, html: str) -> list[SourceBook]:
        tree = HTMLParser(html)
        books: list[SourceBook] = []
        seen_urls: set[str] = set()

        for anchor in tree.css("a"):
            detail_url = self._normalize_detail_url(self._attr(anchor, "href"))
            title = self._clean_title(self._text(anchor))
            if detail_url is None or title is None or detail_url in seen_urls:
                continue

            container = self._find_product_container(anchor)
            if container is None:
                continue

            block_lines = self._lines(container)
            metadata_line = self._search_metadata_line(block_lines)
            if metadata_line is None:
                continue

            authors, narrators, description, duration_minutes = self._parse_card_metadata(metadata_line)
            source_id = self._extract_product_id(detail_url) or self._extract_order_code(" ".join(block_lines))
            if source_id is None:
                continue

            books.append(
                SourceBook(
                    source=self.source_name,
                    source_id=source_id,
                    title=title,
                    detail_url=detail_url,
                    authors=authors,
                    narrators=narrators,
                    description=description,
                    duration_minutes=duration_minutes,
                    detail_loaded=False,
                )
            )
            seen_urls.add(detail_url)

        return books

    def parse_detail_page(self, html: str, *, partial: SourceBook | None = None) -> SourceBook:
        tree = HTMLParser(html)
        lines = self._lines(tree.body or tree.html)

        title = self._clean_title(self._text(tree.css_first("h1"))) or self._title_from_meta(tree)
        authors = self._extract_people(lines, labels=["Autor"])
        narrators = self._extract_people(lines, labels=["Interpret", "Čte"])
        publisher = self._extract_publisher(lines)
        language = (
            map_language_to_code(self._value_for_label(lines, "Jazyk"))
            or map_language_to_code(self._first_matching_line(lines, "česky"))
        )
        published_year = extract_year(self._value_for_label(lines, "Rok vydání"))
        duration_minutes = parse_duration_to_minutes(
            self._value_for_label(lines, "Délka") or self._first_matching_line(lines, "hod")
        )
        genres = self._extract_genres(lines)
        description = self._meta_description(tree) or self._extract_description(
            tree,
            lines,
            title=title,
        )
        cover_url = self._meta_content(tree, "meta[property='og:image']") or self._meta_content(
            tree,
            "meta[name='og:image']",
        )

        update = {
            "title": title or (partial.title if partial else ""),
            "authors": authors or (partial.authors if partial else []),
            "narrators": narrators or (partial.narrators if partial else []),
            "publishers": [publisher] if publisher else (partial.publishers if partial else []),
            "published_year": published_year or (partial.published_year if partial else None),
            "description": description or (partial.description if partial else None),
            "cover_url": cover_url or (partial.cover_url if partial else None),
            "genres": genres or (partial.genres if partial else []),
            "language": language or (partial.language if partial else None),
            "duration_minutes": duration_minutes or (partial.duration_minutes if partial else None),
            "detail_loaded": True,
        }

        if partial is not None:
            return partial.model_copy(update=update)

        return SourceBook(
            source=self.source_name,
            source_id=self._extract_product_id(self._canonical_url_from_meta(tree)) or "unknown",
            title=update["title"],
            detail_url=self._canonical_url_from_meta(tree) or "",
            authors=update["authors"],
            narrators=update["narrators"],
            publishers=update["publishers"],
            published_year=update["published_year"],
            description=update["description"],
            cover_url=update["cover_url"],
            genres=update["genres"],
            language=update["language"],
            duration_minutes=update["duration_minutes"],
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

    def _find_product_container(self, node: Node) -> Node | None:
        current: Node | None = node

        while current is not None:
            product_urls = {
                detail_url
                for anchor in current.css("a")
                for detail_url in [self._normalize_detail_url(self._attr(anchor, "href"))]
                if detail_url is not None
            }
            block_lines = self._lines(current)
            if len(product_urls) == 1 and self._search_metadata_line(block_lines) is not None:
                return current
            current = current.parent

        return None

    def _search_metadata_line(self, lines: list[str]) -> str | None:
        for line in lines:
            normalized = normalize_whitespace(line)
            if normalized is None:
                continue
            if normalized.lower().startswith("audiokniha"):
                return normalized
        return None

    def _parse_card_metadata(self, line: str) -> tuple[list[str], list[str], str | None, int | None]:
        normalized = normalize_whitespace(line) or ""
        details = self._patterns.leading_medium.sub("", normalized).lstrip("- ").strip()

        description: str | None = None
        if " - autor " in details.lower():
            marker_index = details.lower().index(" - autor ")
            description = normalize_whitespace(details[:marker_index])
            details = normalize_whitespace(details[marker_index + 3 :]) or details

        authors_value = self._matched_value(self._patterns.author_segment, details)
        narrators_value = self._matched_value(self._patterns.narrator_segment, details)

        if authors_value is None and narrators_value is not None and ", čte" in details.lower():
            authors_value = normalize_whitespace(details.split(", čte", 1)[0])

        authors = self._split_people(authors_value)
        narrators = self._split_people(narrators_value)
        duration_minutes = parse_duration_to_minutes(details)
        return authors, narrators, description, duration_minutes

    def _extract_people(self, lines: list[str], *, labels: list[str]) -> list[str]:
        values = unique_preserving_order(self._value_for_label(lines, label) for label in labels)
        if not values:
            return []
        return unique_preserving_order(
            part
            for value in values
            for part in self._split_people(value)
        )

    def _extract_publisher(self, lines: list[str]) -> str | None:
        for line in lines:
            normalized = normalize_whitespace(line)
            if normalized is None:
                continue
            if normalized.startswith("Vše od "):
                return normalize_whitespace(normalized.removeprefix("Vše od "))

        manufacturer_index = self._index_of(lines, "Informace o výrobci")
        if manufacturer_index is None or manufacturer_index + 1 >= len(lines):
            return None

        manufacturer_line = normalize_whitespace(lines[manufacturer_index + 1])
        if manufacturer_line is None:
            return None
        return normalize_whitespace(manufacturer_line.split(",", 1)[0])

    def _extract_genres(self, lines: list[str]) -> list[str]:
        raw_categories = self._value_for_label(lines, "Kategorie")
        if raw_categories is None:
            return []

        genres = unique_preserving_order(segment.strip() for segment in re.split(r",|»", raw_categories))
        return [genre for genre in genres if normalize_match_text(genre) != "audioknihy"]

    def _extract_description(self, tree: HTMLParser, lines: list[str], *, title: str | None) -> str | None:
        paragraphs = self._description_paragraphs(tree)
        paragraph_candidates = [
            paragraph
            for paragraph in paragraphs
            if self._is_description_line(paragraph)
        ]
        if paragraph_candidates:
            return normalize_whitespace(" ".join(paragraph_candidates))

        if title is None:
            return None

        title_index = self._index_of(lines, title)
        if title_index is None:
            return None

        description_lines: list[str] = []
        stop_markers = {
            "Parametry a specifikace",
            "Historie cen",
            "Informace o výrobci",
            "Další nabídky",
            "Související kategorie",
            "Zobrazit další",
        }
        for line in lines[title_index + 1 :]:
            normalized = normalize_whitespace(line)
            if normalized is None:
                continue
            if normalized in stop_markers:
                break
            if not self._is_description_line(normalized):
                continue
            description_lines.append(normalized)

        if not description_lines:
            return None

        return normalize_whitespace(" ".join(description_lines))

    def _meta_description(self, tree: HTMLParser) -> str | None:
        candidates = [
            self._meta_content(tree, "meta[property='og:description']"),
            self._meta_content(tree, "meta[name='og:description']"),
            self._meta_content(tree, "meta[property='twitter:description']"),
            self._meta_content(tree, "meta[name='twitter:description']"),
        ]
        for candidate in candidates:
            if self._is_description_line(candidate):
                return candidate
        return None

    def _description_paragraphs(self, tree: HTMLParser) -> list[str]:
        selectors = (
            "#descriptionContent p",
            "#descriptionContent li",
            ".popis__content p",
            ".popis__content li",
            "#description p",
            "#description li",
        )
        return unique_preserving_order(
            self._text(node)
            for selector in selectors
            for node in tree.css(selector)
        )

    def _value_for_label(self, lines: list[str], label: str) -> str | None:
        normalized_label = normalize_match_text(label)
        known_labels = {
            normalize_match_text(value)
            for value in [
                "Autor",
                "Interpret",
                "Čte",
                "Jazyk",
                "Délka",
                "Rok vydání",
                "Kategorie",
            ]
        }

        for index, line in enumerate(lines):
            normalized_line = normalize_whitespace(line)
            if normalized_line is None:
                continue
            match_text = normalize_match_text(normalized_line)
            if match_text.startswith(f"{normalized_label} "):
                return normalize_whitespace(normalized_line[len(label) :].lstrip(" :"))
            if match_text == normalized_label and index + 1 < len(lines):
                next_line = normalize_whitespace(lines[index + 1])
                if next_line is None or normalize_match_text(next_line) in known_labels:
                    continue
                return next_line

        return None

    def _title_from_meta(self, tree: HTMLParser) -> str | None:
        raw_title = (
            self._meta_content(tree, "meta[property='og:title']")
            or self._meta_content(tree, "meta[name='og:title']")
            or self._text(tree.css_first("title"))
        )
        normalized = normalize_whitespace(raw_title)
        if normalized is None:
            return None

        title = self._patterns.title_suffix.sub("", normalized)
        title = self._patterns.title_author_suffix.sub("", title)
        return self._clean_title(title)

    def _canonical_url_from_meta(self, tree: HTMLParser) -> str | None:
        return self._meta_content(tree, "meta[property='og:url']") or self._meta_content(
            tree,
            "link[rel='canonical']",
            attr="href",
        )

    def _meta_content(self, tree: HTMLParser, selector: str, *, attr: str = "content") -> str | None:
        value = self._attr(tree.css_first(selector), attr)
        if value is None:
            return None
        return normalize_whitespace(unescape(value))

    def _normalize_detail_url(self, href: str | None) -> str | None:
        normalized_href = normalize_whitespace(href)
        if normalized_href is None:
            return None
        match = self._patterns.product_href.search(normalized_href)
        if match is None:
            return None
        return to_absolute_url(self.BASE_URL, match.group("href"))

    def _extract_product_id(self, detail_url: str | None) -> str | None:
        normalized_url = normalize_whitespace(detail_url)
        if normalized_url is None:
            return None
        match = self._patterns.product_href.search(normalized_url)
        if match is None:
            return None
        return match.group("product_id")

    def _extract_order_code(self, text: str) -> str | None:
        match = self._patterns.order_code.search(text)
        if match is None:
            return None
        return normalize_whitespace(match.group("code"))

    def _clean_title(self, value: str | None) -> str | None:
        normalized = normalize_title(value)
        if normalized is None:
            return None
        cleaned = self._patterns.title_suffix.sub("", normalized)
        cleaned = self._patterns.title_author_suffix.sub("", cleaned)
        return normalize_title(cleaned)

    def _to_mobile_detail_url(self, detail_url: str) -> str | None:
        normalized_url = normalize_whitespace(detail_url)
        if normalized_url is None:
            return None
        return normalized_url.replace(self.BASE_URL, self.MOBILE_BASE_URL, 1)

    def _looks_like_challenge_page(self, html: str) -> bool:
        normalized = html.lower()
        return (
            "just a moment..." in normalized
            or "enable javascript and cookies to continue" in normalized
            or "_cf_chl_opt" in normalized
        )

    def _detail_has_signal(self, item: SourceBook) -> bool:
        return any(
            [
                bool(item.description),
                bool(item.publishers),
                bool(item.genres),
                bool(item.cover_url),
                bool(item.language),
                item.duration_minutes is not None,
            ]
        )

    def _split_people(self, value: str | None) -> list[str]:
        normalized = normalize_whitespace(value)
        if normalized is None:
            return []
        normalized = re.sub(r"\s+\d+\s*(?:hod|min).*$", "", normalized, flags=re.IGNORECASE)
        return unique_preserving_order(
            part.strip()
            for part in re.split(r"\s*,\s*|\s+a\s+", normalized)
        )

    def _matched_value(self, pattern: re.Pattern[str], text: str) -> str | None:
        match = pattern.search(text)
        if match is None:
            return None
        return normalize_whitespace(match.group("value"))

    def _first_matching_line(self, lines: list[str], needle: str) -> str | None:
        normalized_needle = normalize_match_text(needle)
        for line in lines:
            normalized = normalize_whitespace(line)
            if normalized is None:
                continue
            if normalized_needle in normalize_match_text(normalized):
                return normalized
        return None

    def _index_of(self, lines: list[str], needle: str) -> int | None:
        normalized_needle = normalize_match_text(needle)
        for index, line in enumerate(lines):
            if normalize_match_text(line) == normalized_needle:
                return index
        return None

    def _is_description_line(self, value: str | None) -> bool:
        normalized = normalize_whitespace(value)
        if normalized is None:
            return False
        if len(normalized) < 50:
            return False
        if normalized.startswith(("{", "[")):
            return False
        if self._patterns.price_like.match(normalized):
            return False
        normalized_match = normalize_match_text(normalized)
        if "cookies" in normalized_match:
            return False
        if '"@context"' in normalized or "schema.org" in normalized:
            return False

        blocked_prefixes = (
            "Autor",
            "Interpret",
            "Čte",
            "Jazyk",
            "Délka",
            "Rok vydání",
            "Kategorie",
            "Vše od ",
            "Poslechněte si",
            "Koupit",
            "Do košíku",
            "Na objednávku",
            "Sdílet",
            "Informace o výrobci",
        )
        return not normalized.startswith(blocked_prefixes)

    def _lines(self, node: Node | None) -> list[str]:
        if node is None:
            return []
        try:
            text = node.text(separator="\n", strip=True)
        except TypeError:
            text = node.text()

        lines: list[str] = []
        for raw_line in text.replace("\r", "").split("\n"):
            normalized = normalize_whitespace(raw_line)
            if normalized is not None:
                lines.append(normalized)
        return lines

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
