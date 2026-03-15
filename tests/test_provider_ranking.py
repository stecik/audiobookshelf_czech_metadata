from __future__ import annotations

from app.models import SourceBook
from app.services.provider import score_book_result, sort_book_results


def make_book(
    *,
    source_id: str,
    title: str,
    authors: list[str],
    language: str | None,
) -> SourceBook:
    return SourceBook(
        source="audiolibrix",
        source_id=source_id,
        title=title,
        detail_url=f"https://www.audiolibrix.com/cs/Directory/Book/{source_id}/mock",
        authors=authors,
        language=language,
    )


def test_ranking_prefers_exact_title_author_and_czech_language() -> None:
    exact_czech = make_book(
        source_id="1",
        title="1984",
        authors=["George Orwell"],
        language="cs",
    )
    exact_slovak = make_book(
        source_id="2",
        title="1984",
        authors=["George Orwell"],
        language="sk",
    )
    substring_czech = make_book(
        source_id="3",
        title="Máj (1984)",
        authors=["Karel Hynek Mácha"],
        language="cs",
    )

    ordered = sort_book_results(
        [substring_czech, exact_slovak, exact_czech],
        query="1984",
        author="George Orwell",
    )

    assert ordered[0].source_id == "1"
    assert ordered[1].source_id == "2"
    assert score_book_result(exact_czech, query="1984", author="George Orwell") > score_book_result(
        exact_slovak,
        query="1984",
        author="George Orwell",
    )
