from __future__ import annotations

from app.models import SourceBook
from app.services.provider import score_candidate


def build_candidate(title: str, authors: list[str], language: str = "cs") -> SourceBook:
    return SourceBook(
        source="audiolibrix_cs",
        title=title,
        detail_url=f"https://example.test/{title}",
        authors=authors,
        language=language,
    )


def test_exact_title_match_beats_partial_title_match() -> None:
    exact = build_candidate("Šikmý kostel", ["Karin Lednická"])
    partial = build_candidate("Šikmý kostel 2", ["Karin Lednická"])

    assert score_candidate(exact, query="Šikmý kostel") > score_candidate(
        partial,
        query="Šikmý kostel",
    )


def test_author_match_boosts_score() -> None:
    matching_author = build_candidate("Šikmý kostel", ["Karin Lednická"])
    different_author = build_candidate("Šikmý kostel", ["Někdo Jiný"])

    assert score_candidate(
        matching_author,
        query="Šikmý kostel",
        author="Karin Lednická",
    ) > score_candidate(
        different_author,
        query="Šikmý kostel",
        author="Karin Lednická",
    )
