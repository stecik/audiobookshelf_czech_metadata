from __future__ import annotations

import os

from pydantic import BaseModel, Field, field_validator

DEFAULT_USER_AGENT = (
    "audiolibrix-abs-provider/0.1.0 "
    "(+https://www.audiolibrix.com/cs; https://audioteka.com/cz/; https://www.kosmas.cz/audioknihy/; "
    "https://www.luxor.cz/c/10726/audioknihy; "
    "https://www.kanopa.cz/; https://onehotbook.cz/; https://www.albatrosmedia.cz/; https://progresguru.cz/; "
    "https://www.palmknihy.cz/; https://www.o2knihovna.cz/audioknihy/; https://naposlech.cz/; "
    "https://temata.rozhlas.cz/hry-a-cetba; https://www.knihydobrovsky.cz/audioknihy; "
    "https://www.megaknihy.cz/tema/1/32787-audioknihy; https://www.radioteka.cz/; "
    "https://www.alza.cz/media/audioknihy/18854370.htm)"
)


class Settings(BaseModel):
    app_host: str = "0.0.0.0"
    app_port: int = Field(default=8000, ge=1, le=65535)
    log_level: str = "INFO"
    request_timeout_seconds: float = Field(default=20.0, gt=0)
    scraper_timeout_seconds: float = Field(default=8.0, gt=0)
    audiobookshelf_auth_token: str | None = None
    scraper_user_agent: str = DEFAULT_USER_AGENT
    detail_enrichment_limit: int = Field(default=5, ge=1, le=10)
    enable_alza: bool = True
    enable_audiolibrix: bool = True
    enable_audioteka: bool = True
    enable_databazeknih: bool = False
    enable_kanopa: bool = True
    enable_knihydobrovsky: bool = True
    enable_kosmas: bool = True
    enable_luxor: bool = True
    enable_megaknihy: bool = True
    enable_naposlech: bool = True
    enable_onehotbook: bool = True
    enable_o2knihovna: bool = True
    enable_albatrosmedia: bool = True
    enable_palmknihy: bool = True
    enable_progresguru: bool = True
    enable_radioteka: bool = True
    enable_rozhlas: bool = True

    @field_validator("log_level", mode="before")
    @classmethod
    def normalize_log_level(cls, value: object) -> str:
        return str(value or "INFO").upper()

    @field_validator("audiobookshelf_auth_token", mode="before")
    @classmethod
    def normalize_optional_token(cls, value: object) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            app_host=os.getenv("APP_HOST", "0.0.0.0"),
            app_port=os.getenv("APP_PORT", "8000"),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            request_timeout_seconds=os.getenv("REQUEST_TIMEOUT_SECONDS", "20"),
            scraper_timeout_seconds=os.getenv("SCRAPER_TIMEOUT_SECONDS", "8"),
            audiobookshelf_auth_token=os.getenv("AUDIOBOOKSHELF_AUTH_TOKEN"),
            scraper_user_agent=os.getenv("SCRAPER_USER_AGENT", DEFAULT_USER_AGENT),
            enable_alza=os.getenv("ENABLE_ALZA", "true"),
            enable_audiolibrix=os.getenv("ENABLE_AUDIOLIBRIX", "true"),
            enable_audioteka=os.getenv("ENABLE_AUDIOTEKA", "true"),
            enable_databazeknih=os.getenv("ENABLE_DATABAZEKNIH", "false"),
            enable_kanopa=os.getenv("ENABLE_KANOPA", "true"),
            enable_knihydobrovsky=os.getenv("ENABLE_KNIHYDOBROVSKY", "true"),
            enable_kosmas=os.getenv("ENABLE_KOSMAS", "true"),
            enable_luxor=os.getenv("ENABLE_LUXOR", "true"),
            enable_megaknihy=os.getenv("ENABLE_MEGAKNIHY", "true"),
            enable_naposlech=os.getenv("ENABLE_NAPOSLECH", "true"),
            enable_onehotbook=os.getenv("ENABLE_ONEHOTBOOK", "true"),
            enable_o2knihovna=os.getenv("ENABLE_O2KNIHOVNA", "true"),
            enable_albatrosmedia=os.getenv("ENABLE_ALBATROSMEDIA", "true"),
            enable_palmknihy=os.getenv("ENABLE_PALMKNIHY", "true"),
            enable_progresguru=os.getenv("ENABLE_PROGRESGURU", "true"),
            enable_radioteka=os.getenv("ENABLE_RADIOTEKA", "true"),
            enable_rozhlas=os.getenv("ENABLE_ROZHLAS", "true"),
        )
