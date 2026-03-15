from __future__ import annotations

import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from app.clients.http import HttpClient
from app.config import Settings
from app.routers.search import (
    create_provider_router,
    provider_service_dependencies,
    router as search_router,
)
from app.services.normalizers.audiobookshelf import AudiobookshelfNormalizer
from app.services.provider import MetadataProviderService
from app.services.scrapers.albatrosmedia import AlbatrosMediaScraper
from app.services.scrapers.kosmas import KosmasScraper
from app.services.scrapers.audioteka import AudiotekaScraper
from app.services.scrapers.audiolibrix import AudiolibrixScraper
from app.services.scrapers.base import BaseMetadataScraper
from app.services.scrapers.onehotbook import OneHotBookScraper
from app.services.scrapers.palmknihy import PalmknihyScraper
from app.services.scrapers.progresguru import ProgresGuruScraper
from app.utils.logging import configure_logging


logger = logging.getLogger(__name__)


def build_scrapers(*, settings: Settings, http_client: HttpClient) -> dict[str, BaseMetadataScraper]:
    scrapers: dict[str, BaseMetadataScraper] = {}

    if settings.enable_albatrosmedia:
        scrapers["albatrosmedia"] = AlbatrosMediaScraper(http_client=http_client)
    if settings.enable_audiolibrix:
        scrapers["audiolibrix"] = AudiolibrixScraper(http_client=http_client)
    if settings.enable_audioteka:
        scrapers["audioteka"] = AudiotekaScraper(http_client=http_client)
    if settings.enable_kosmas:
        scrapers["kosmas"] = KosmasScraper(http_client=http_client)
    if settings.enable_onehotbook:
        scrapers["onehotbook"] = OneHotBookScraper(http_client=http_client)
    if settings.enable_palmknihy:
        scrapers["palmknihy"] = PalmknihyScraper(http_client=http_client)
    if settings.enable_progresguru:
        scrapers["progresguru"] = ProgresGuruScraper(http_client=http_client)

    return scrapers


def build_provider_service(
    *,
    scrapers: list[BaseMetadataScraper],
    detail_enrichment_limit: int,
) -> MetadataProviderService:
    return MetadataProviderService(
        scrapers=scrapers,
        normalizer=AudiobookshelfNormalizer(),
        detail_enrichment_limit=detail_enrichment_limit,
    )


def create_app() -> FastAPI:
    settings = Settings.from_env()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        http_client = HttpClient(
            timeout_seconds=settings.request_timeout_seconds,
            user_agent=settings.scraper_user_agent,
        )
        scrapers = build_scrapers(settings=settings, http_client=http_client)
        provider_service = build_provider_service(
            scrapers=list(scrapers.values()),
            detail_enrichment_limit=settings.detail_enrichment_limit,
        )

        app.state.settings = settings
        app.state.http_client = http_client
        app.state.provider_service = provider_service
        for source_name, scraper in scrapers.items():
            setattr(
                app.state,
                f"provider_service_{source_name}",
                build_provider_service(
                    scrapers=[scraper],
                    detail_enrichment_limit=settings.detail_enrichment_limit,
                ),
            )

        yield

        await http_client.aclose()

    app = FastAPI(
        title="Czech Audiobookshelf Metadata Provider",
        version="0.1.0",
        lifespan=lifespan,
    )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled.exception", exc_info=exc)
        return JSONResponse(status_code=500, content={"error": "internal server error"})

    app.include_router(search_router)
    for source_name, dependency in provider_service_dependencies.items():
        if not getattr(settings, f"enable_{source_name}", False):
            continue
        app.include_router(
            create_provider_router(
                provider_dependency=dependency,
                provider_name=source_name,
            ),
            prefix=f"/{source_name}",
        )
    return app


app = create_app()


if __name__ == "__main__":
    runtime_settings = Settings.from_env()
    uvicorn.run(
        "app.main:app",
        host=runtime_settings.app_host,
        port=runtime_settings.app_port,
        reload=False,
    )
