from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable

from app.models import SourceBook


class BaseMetadataScraper(ABC):
    source_name: str

    @abstractmethod
    async def search(self, query: str, author: str | None = None) -> list[SourceBook]:
        raise NotImplementedError

    async def enrich(self, item: SourceBook) -> SourceBook:
        return item

    async def _prefer_primary_results(
        self,
        *,
        primary: Callable[[], Awaitable[list[SourceBook]]],
        fallback: Callable[[], Awaitable[list[SourceBook]]] | None = None,
    ) -> list[SourceBook]:
        primary_task = asyncio.create_task(primary())
        if fallback is None:
            return await primary_task

        fallback_task = asyncio.create_task(fallback())
        try:
            primary_results = await primary_task
        except Exception:
            await self._cancel_task(fallback_task)
            raise

        if primary_results:
            await self._cancel_task(fallback_task)
            return primary_results

        return await fallback_task

    async def _cancel_task(self, task: asyncio.Task[list[SourceBook]]) -> None:
        if task.done():
            return
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
