from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request

from app.config import Settings
from app.models import HealthResponse, SearchResponse
from app.services.provider import MetadataProviderService, UpstreamUnavailableError


logger = logging.getLogger(__name__)


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def make_provider_service_dependency(state_key: str):
    def get_provider_service(request: Request) -> MetadataProviderService:
        return getattr(request.app.state, state_key)

    return get_provider_service


get_provider_service = make_provider_service_dependency("provider_service")
provider_service_dependencies = {
    "alza": make_provider_service_dependency("provider_service_alza"),
    "albatrosmedia": make_provider_service_dependency("provider_service_albatrosmedia"),
    "audiolibrix": make_provider_service_dependency("provider_service_audiolibrix"),
    "audioteka": make_provider_service_dependency("provider_service_audioteka"),
    "databazeknih": make_provider_service_dependency("provider_service_databazeknih"),
    "kanopa": make_provider_service_dependency("provider_service_kanopa"),
    "knihydobrovsky": make_provider_service_dependency("provider_service_knihydobrovsky"),
    "kosmas": make_provider_service_dependency("provider_service_kosmas"),
    "luxor": make_provider_service_dependency("provider_service_luxor"),
    "megaknihy": make_provider_service_dependency("provider_service_megaknihy"),
    "naposlech": make_provider_service_dependency("provider_service_naposlech"),
    "onehotbook": make_provider_service_dependency("provider_service_onehotbook"),
    "o2knihovna": make_provider_service_dependency("provider_service_o2knihovna"),
    "palmknihy": make_provider_service_dependency("provider_service_palmknihy"),
    "progresguru": make_provider_service_dependency("provider_service_progresguru"),
    "radioteka": make_provider_service_dependency("provider_service_radioteka"),
    "rozhlas": make_provider_service_dependency("provider_service_rozhlas"),
}


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


def create_provider_router(
    *,
    provider_dependency,
    provider_name: str,
) -> APIRouter:
    router = APIRouter()

    @router.get("/health", response_model=HealthResponse, name=f"{provider_name}_health")
    async def health() -> HealthResponse:
        return HealthResponse(status="ok")

    @router.get(
        "/search",
        response_model=SearchResponse,
        response_model_exclude_none=True,
        dependencies=[Depends(require_shared_token)],
        name=f"{provider_name}_search",
    )
    async def search(
        query: Annotated[str, Query(min_length=1, description="Audiobookshelf search query")],
        author: Annotated[str | None, Query(description="Optional author filter")] = None,
        provider_service: MetadataProviderService = Depends(provider_dependency),
    ) -> SearchResponse:
        cleaned_query = query.strip()
        cleaned_author = author.strip() if author else None
        if not cleaned_query:
            raise HTTPException(status_code=422, detail="query must not be blank")

        logger.info(
            "search.request",
            extra={
                "provider": provider_name,
                "query": cleaned_query,
                "author_provided": bool(cleaned_author),
            },
        )

        try:
            return await provider_service.search(query=cleaned_query, author=cleaned_author)
        except UpstreamUnavailableError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    return router


router = create_provider_router(
    provider_dependency=get_provider_service,
    provider_name="global",
)
