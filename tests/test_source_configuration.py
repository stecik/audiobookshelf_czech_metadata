from __future__ import annotations

import asyncio

from app.clients.http import HttpClient
from app.config import Settings
from app.main import build_scrapers


def test_settings_enable_all_sources_by_default(monkeypatch) -> None:
    monkeypatch.delenv("ENABLE_AUDIOLIBRIX", raising=False)
    monkeypatch.delenv("ENABLE_AUDIOTEKA", raising=False)
    monkeypatch.delenv("ENABLE_ONEHOTBOOK", raising=False)

    settings = Settings.from_env()

    assert settings.enable_audiolibrix is True
    assert settings.enable_audioteka is True
    assert settings.enable_onehotbook is True


def test_build_scrapers_respects_source_flags() -> None:
    http_client = HttpClient(timeout_seconds=1.0, user_agent="tests")
    settings = Settings(
        enable_audiolibrix=False,
        enable_audioteka=True,
        enable_onehotbook=False,
    )

    try:
        scrapers = build_scrapers(settings=settings, http_client=http_client)
    finally:
        asyncio.run(http_client.aclose())

    assert list(scrapers) == ["audioteka"]
    assert scrapers["audioteka"].source_name == "audioteka"
