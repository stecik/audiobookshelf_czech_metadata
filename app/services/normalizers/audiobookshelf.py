from __future__ import annotations

from app.models import AudiobookshelfMatch, SearchResponse, SourceBook
from app.utils.text import comma_join


class AudiobookshelfNormalizer:
    def normalize(self, book: SourceBook) -> AudiobookshelfMatch:
        return AudiobookshelfMatch(
            title=book.title,
            subtitle=book.subtitle,
            author=comma_join(book.authors),
            narrator=comma_join(book.narrators),
            publisher=comma_join(book.publishers),
            publishedYear=book.published_year,
            description=book.description,
            cover=book.cover_url,
            genres=book.genres or None,
            tags=book.tags or None,
            language=book.language,
            duration=book.duration_minutes,
            matchConfidence=book.match_confidence,
        )

    def normalize_many(self, books: list[SourceBook]) -> SearchResponse:
        return SearchResponse(matches=[self.normalize(book) for book in books])
