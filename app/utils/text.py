from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable, Sequence
from urllib.parse import urljoin


WHITESPACE_RE = re.compile(r"\s+")
COLON_SPACING_RE = re.compile(r"\s*:\s*")
TITLE_PREFIX_RE = re.compile(r"^(audiokniha|audiobook|hoerebuch|hörbuch)\s+", re.IGNORECASE)
NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")
YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")
HOUR_MINUTE_RE = re.compile(r"(?P<hours>\d+)\s*:\s*(?P<minutes>\d+)\s*h", re.IGNORECASE)
MINUTE_RE = re.compile(r"(?P<minutes>\d+)\s*(min|minut|minuty|minutes?)\b", re.IGNORECASE)
ISO_8601_DURATION_RE = re.compile(r"^PT(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?$", re.IGNORECASE)


def normalize_whitespace(text: str | None) -> str | None:
    if text is None:
        return None
    collapsed = WHITESPACE_RE.sub(" ", text.replace("\xa0", " ")).strip()
    return collapsed or None


def normalize_title(text: str | None) -> str | None:
    normalized = normalize_whitespace(text)
    if normalized is None:
        return None
    return COLON_SPACING_RE.sub(": ", normalized)


def strip_audiobook_prefix(text: str | None) -> str | None:
    normalized = normalize_title(text)
    if normalized is None:
        return None
    stripped = TITLE_PREFIX_RE.sub("", normalized)
    return stripped or normalized


def to_absolute_url(base_url: str, href: str | None) -> str | None:
    normalized = normalize_whitespace(href)
    if normalized is None:
        return None
    return urljoin(base_url, normalized)


def unique_preserving_order(values: Iterable[str | None]) -> list[str]:
    seen: set[str] = set()
    unique_values: list[str] = []
    for value in values:
        normalized = normalize_whitespace(value)
        if normalized is None:
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        unique_values.append(normalized)
    return unique_values


def comma_join(values: Sequence[str]) -> str | None:
    cleaned = unique_preserving_order(values)
    if not cleaned:
        return None
    return ", ".join(cleaned)


def normalize_match_text(text: str | None) -> str:
    normalized = normalize_whitespace(text) or ""
    decomposed = unicodedata.normalize("NFKD", normalized)
    ascii_text = "".join(character for character in decomposed if not unicodedata.combining(character))
    return NON_ALNUM_RE.sub(" ", ascii_text.lower()).strip()


def parse_duration_to_minutes(text: str | None) -> int | None:
    normalized = normalize_whitespace(text)
    if normalized is None:
        return None

    hour_match = HOUR_MINUTE_RE.search(normalized)
    if hour_match:
        hours = int(hour_match.group("hours"))
        minutes = int(hour_match.group("minutes"))
        return (hours * 60) + minutes

    minute_match = MINUTE_RE.search(normalized)
    if minute_match:
        return int(minute_match.group("minutes"))

    iso_duration_match = ISO_8601_DURATION_RE.search(normalized)
    if iso_duration_match:
        hours = int(iso_duration_match.group("hours") or 0)
        minutes = int(iso_duration_match.group("minutes") or 0)
        return (hours * 60) + minutes

    return None


def extract_year(text: str | None) -> str | None:
    normalized = normalize_whitespace(text)
    if normalized is None:
        return None
    match = YEAR_RE.search(normalized)
    if match is None:
        return None
    return match.group(0)


def map_language_to_code(text: str | None) -> str | None:
    normalized = normalize_match_text(text)
    if not normalized:
        return None
    if "cestina" in normalized or "cesky" in normalized or normalized in {"cs", "cz"}:
        return "cs"
    if "slovensky" in normalized or "slovencina" in normalized or normalized == "sk":
        return "sk"
    if "english" in normalized or "anglicky" in normalized or normalized == "en":
        return "en"
    if "deutsch" in normalized or "nemecky" in normalized or normalized == "de":
        return "de"
    return None
