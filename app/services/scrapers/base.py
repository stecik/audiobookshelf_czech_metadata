from __future__ import annotations

from abc import ABC, abstractmethod

from app.models import SourceBook


class BaseMetadataScraper(ABC):
    source_name: str

    @abstractmethod
    async def search(self, query: str, author: str | None = None) -> list[SourceBook]:
        raise NotImplementedError

    async def enrich(self, item: SourceBook) -> SourceBook:
        return item
