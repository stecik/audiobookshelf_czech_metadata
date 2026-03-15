from __future__ import annotations

import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from app.clients.http import HttpClient
from app.config import Settings
from app.models import HealthResponse
from app.routers.search import router as search_router
from app.services.normalizers.audiobookshelf import AudiobookshelfNormalizer
from app.services.provider import MetadataProviderService
from app.services.scrapers.audiolibrix import AudiolibrixScraper
from app.utils.logging import configure_logging


logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    settings = Settings.from_env()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        http_client = HttpClient(
            timeout_seconds=settings.request_timeout_seconds,
            user_agent=settings.scraper_user_agent,
        )
        provider_service = MetadataProviderService(
            scrapers=[AudiolibrixScraper(http_client=http_client)],
            normalizer=AudiobookshelfNormalizer(),
            detail_enrichment_limit=settings.detail_enrichment_limit,
        )

        app.state.settings = settings
        app.state.http_client = http_client
        app.state.provider_service = provider_service

        yield

        await http_client.aclose()

    app = FastAPI(
        title="Audiolibrix Audiobookshelf Metadata Provider",
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

    @app.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        return HealthResponse(status="ok")

    app.include_router(search_router)
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
