from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import httpx


logger = logging.getLogger(__name__)


class UpstreamFetchError(Exception):
    def __init__(self, *, url: str, reason: str, timeout_seconds: float) -> None:
        super().__init__(reason)
        self.url = url
        self.reason = reason
        self.timeout_seconds = timeout_seconds


class HttpClient:
    def __init__(self, *, timeout_seconds: float, user_agent: str) -> None:
        self._timeout_seconds = timeout_seconds
        self._client = httpx.AsyncClient(
            timeout=timeout_seconds,
            follow_redirects=True,
            headers={
                "User-Agent": user_agent,
                "Accept-Language": "cs-CZ,cs;q=0.9,en;q=0.6",
            },
        )

    @property
    def timeout_seconds(self) -> float:
        return self._timeout_seconds

    async def get_text(
        self,
        url: str,
        *,
        params: Mapping[str, str | int | float | None] | None = None,
        extra_headers: Mapping[str, str] | None = None,
    ) -> str:
        response = await self._request(url, params=params, extra_headers=extra_headers)
        return response.text

    async def get_json(
        self,
        url: str,
        *,
        params: Mapping[str, str | int | float | None] | None = None,
        extra_headers: Mapping[str, str] | None = None,
    ) -> Any:
        response = await self._request(
            url,
            params=params,
            extra_headers={
                "Accept": "application/json",
                **(dict(extra_headers) if extra_headers is not None else {}),
            },
        )
        return response.json()

    async def _request(
        self,
        url: str,
        *,
        params: Mapping[str, str | int | float | None] | None = None,
        extra_headers: Mapping[str, str] | None = None,
    ) -> httpx.Response:
        filtered_params = {key: value for key, value in (params or {}).items() if value is not None}
        try:
            response = await self._client.get(url, params=filtered_params, headers=extra_headers)
            response.raise_for_status()
            return response
        except httpx.TimeoutException as exc:
            logger.warning(
                "upstream.fetch_timeout",
                extra={"url": url, "timeout_seconds": self._timeout_seconds},
            )
            raise UpstreamFetchError(
                url=url,
                reason="request timed out",
                timeout_seconds=self._timeout_seconds,
            ) from exc
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "upstream.fetch_http_error",
                extra={
                    "url": url,
                    "timeout_seconds": self._timeout_seconds,
                    "status_code": exc.response.status_code,
                },
            )
            raise UpstreamFetchError(
                url=url,
                reason=f"upstream returned HTTP {exc.response.status_code}",
                timeout_seconds=self._timeout_seconds,
            ) from exc
        except httpx.HTTPError as exc:
            logger.warning(
                "upstream.fetch_error",
                extra={"url": url, "timeout_seconds": self._timeout_seconds},
            )
            raise UpstreamFetchError(
                url=url,
                reason="request failed",
                timeout_seconds=self._timeout_seconds,
            ) from exc

    async def aclose(self) -> None:
        await self._client.aclose()
