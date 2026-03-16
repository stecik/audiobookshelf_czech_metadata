from __future__ import annotations

import asyncio

from app.clients.http import HttpClient
from app.config import Settings
from app.main import build_scrapers


def test_settings_enable_all_sources_by_default(monkeypatch) -> None:
    monkeypatch.delenv("ENABLE_ALZA", raising=False)
    monkeypatch.delenv("ENABLE_ALBATROSMEDIA", raising=False)
    monkeypatch.delenv("ENABLE_AUDIOLIBRIX", raising=False)
    monkeypatch.delenv("ENABLE_AUDIOTEKA", raising=False)
    monkeypatch.delenv("ENABLE_KANOPA", raising=False)
    monkeypatch.delenv("ENABLE_KNIHYDOBROVSKY", raising=False)
    monkeypatch.delenv("ENABLE_KOSMAS", raising=False)
    monkeypatch.delenv("ENABLE_LUXOR", raising=False)
    monkeypatch.delenv("ENABLE_MEGAKNIHY", raising=False)
    monkeypatch.delenv("ENABLE_NAPOSLECH", raising=False)
    monkeypatch.delenv("ENABLE_ONEHOTBOOK", raising=False)
    monkeypatch.delenv("ENABLE_O2KNIHOVNA", raising=False)
    monkeypatch.delenv("ENABLE_PALMKNIHY", raising=False)
    monkeypatch.delenv("ENABLE_PROGRESGURU", raising=False)
    monkeypatch.delenv("ENABLE_RADIOTEKA", raising=False)
    monkeypatch.delenv("ENABLE_ROZHLAS", raising=False)

    settings = Settings.from_env()

    assert settings.enable_alza is True
    assert settings.enable_albatrosmedia is True
    assert settings.enable_audiolibrix is True
    assert settings.enable_audioteka is True
    assert settings.enable_kanopa is True
    assert settings.enable_knihydobrovsky is True
    assert settings.enable_kosmas is True
    assert settings.enable_luxor is True
    assert settings.enable_megaknihy is True
    assert settings.enable_naposlech is True
    assert settings.enable_onehotbook is True
    assert settings.enable_o2knihovna is True
    assert settings.enable_palmknihy is True
    assert settings.enable_progresguru is True
    assert settings.enable_radioteka is True
    assert settings.enable_rozhlas is True


def test_build_scrapers_respects_source_flags() -> None:
    http_client = HttpClient(timeout_seconds=1.0, user_agent="tests")
    settings = Settings(
        enable_alza=False,
        enable_albatrosmedia=False,
        enable_audiolibrix=False,
        enable_audioteka=False,
        enable_kanopa=False,
        enable_knihydobrovsky=True,
        enable_kosmas=False,
        enable_luxor=False,
        enable_megaknihy=False,
        enable_naposlech=False,
        enable_onehotbook=False,
        enable_o2knihovna=False,
        enable_palmknihy=False,
        enable_progresguru=False,
        enable_radioteka=False,
        enable_rozhlas=False,
    )

    try:
        scrapers = build_scrapers(settings=settings, http_client=http_client)
    finally:
        asyncio.run(http_client.aclose())

    assert list(scrapers) == ["knihydobrovsky"]
    assert scrapers["knihydobrovsky"].source_name == "knihydobrovsky"


def test_build_scrapers_can_enable_rozhlas_only() -> None:
    http_client = HttpClient(timeout_seconds=1.0, user_agent="tests")
    settings = Settings(
        enable_alza=False,
        enable_albatrosmedia=False,
        enable_audiolibrix=False,
        enable_audioteka=False,
        enable_kanopa=False,
        enable_knihydobrovsky=False,
        enable_kosmas=False,
        enable_luxor=False,
        enable_megaknihy=False,
        enable_naposlech=False,
        enable_onehotbook=False,
        enable_o2knihovna=False,
        enable_palmknihy=False,
        enable_progresguru=False,
        enable_radioteka=False,
        enable_rozhlas=True,
    )

    try:
        scrapers = build_scrapers(settings=settings, http_client=http_client)
    finally:
        asyncio.run(http_client.aclose())

    assert list(scrapers) == ["rozhlas"]
    assert scrapers["rozhlas"].source_name == "rozhlas"


def test_build_scrapers_can_enable_alza_only() -> None:
    http_client = HttpClient(timeout_seconds=1.0, user_agent="tests")
    settings = Settings(
        enable_alza=True,
        enable_albatrosmedia=False,
        enable_audiolibrix=False,
        enable_audioteka=False,
        enable_kanopa=False,
        enable_knihydobrovsky=False,
        enable_kosmas=False,
        enable_luxor=False,
        enable_megaknihy=False,
        enable_naposlech=False,
        enable_onehotbook=False,
        enable_o2knihovna=False,
        enable_palmknihy=False,
        enable_progresguru=False,
        enable_radioteka=False,
        enable_rozhlas=False,
    )

    try:
        scrapers = build_scrapers(settings=settings, http_client=http_client)
    finally:
        asyncio.run(http_client.aclose())

    assert list(scrapers) == ["alza"]
    assert scrapers["alza"].source_name == "alza"
