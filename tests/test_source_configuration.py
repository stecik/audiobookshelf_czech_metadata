from __future__ import annotations

import asyncio

from app.clients.http import HttpClient
from app.config import Settings
from app.main import build_scrapers


def test_settings_enable_all_sources_by_default(monkeypatch) -> None:
    monkeypatch.delenv("ENABLE_ALBATROSMEDIA", raising=False)
    monkeypatch.delenv("ENABLE_AUDIOLIBRIX", raising=False)
    monkeypatch.delenv("ENABLE_AUDIOTEKA", raising=False)
    monkeypatch.delenv("ENABLE_KOSMAS", raising=False)
    monkeypatch.delenv("ENABLE_ONEHOTBOOK", raising=False)
    monkeypatch.delenv("ENABLE_PALMKNIHY", raising=False)
    monkeypatch.delenv("ENABLE_PROGRESGURU", raising=False)

    settings = Settings.from_env()

    assert settings.enable_albatrosmedia is True
    assert settings.enable_audiolibrix is True
    assert settings.enable_audioteka is True
    assert settings.enable_kosmas is True
    assert settings.enable_onehotbook is True
    assert settings.enable_palmknihy is True
    assert settings.enable_progresguru is True


def test_build_scrapers_respects_source_flags() -> None:
    http_client = HttpClient(timeout_seconds=1.0, user_agent="tests")
    settings = Settings(
        enable_albatrosmedia=False,
        enable_audiolibrix=False,
        enable_audioteka=False,
        enable_kosmas=False,
        enable_onehotbook=False,
        enable_palmknihy=True,
        enable_progresguru=False,
    )

    try:
        scrapers = build_scrapers(settings=settings, http_client=http_client)
    finally:
        asyncio.run(http_client.aclose())

    assert list(scrapers) == ["palmknihy"]
    assert scrapers["palmknihy"].source_name == "palmknihy"
