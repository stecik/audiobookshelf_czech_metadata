from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request

from app.config import Settings
from app.models import SearchResponse
from app.services.provider import MetadataProviderService, UpstreamUnavailableError


logger = logging.getLogger(__name__)
router = APIRouter()


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_provider_service(request: Request) -> MetadataProviderService:
    return request.app.state.provider_service


def _authorization_matches(*, expected: str, provided: str | None) -> bool:
    if provided is None:
        return False
    candidates = {expected}
    if not expected.lower().startswith("bearer "):
        candidates.add(f"Bearer {expected}")
    return provided.strip() in candidates


async def require_shared_token(
    settings: Annotated[Settings, Depends(get_settings)],
    authorization: Annotated[str | None, Header()] = None,
) -> None:
    if settings.audiobookshelf_auth_token is None:
        return
    if _authorization_matches(expected=settings.audiobookshelf_auth_token, provided=authorization):
        return
    raise HTTPException(status_code=401, detail="unauthorized")


@router.get(
    "/search",
    response_model=SearchResponse,
    response_model_exclude_none=True,
    dependencies=[Depends(require_shared_token)],
)
async def search(
    query: Annotated[str, Query(min_length=1, description="Audiobookshelf search query")],
    author: Annotated[str | None, Query(description="Optional author filter")] = None,
    provider_service: Annotated[MetadataProviderService, Depends(get_provider_service)] = None,
) -> SearchResponse:
    cleaned_query = query.strip()
    cleaned_author = author.strip() if author else None
    if not cleaned_query:
        raise HTTPException(status_code=422, detail="query must not be blank")

    logger.info(
        "search.request",
        extra={"query": cleaned_query, "author_provided": bool(cleaned_author)},
    )

    try:
        return await provider_service.search(query=cleaned_query, author=cleaned_author)
    except UpstreamUnavailableError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
