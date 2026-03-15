from __future__ import annotations

import os

from pydantic import BaseModel, Field, field_validator


DEFAULT_USER_AGENT = (
    "audiolibrix-abs-provider/0.1.0 "
    "(+https://www.audiolibrix.com/cs; https://audioteka.com/cz/; https://www.kosmas.cz/audioknihy/; "
    "https://onehotbook.cz/; https://www.albatrosmedia.cz/; https://progresguru.cz/; https://www.palmknihy.cz/)"
)


class Settings(BaseModel):
    app_host: str = "0.0.0.0"
    app_port: int = Field(default=8000, ge=1, le=65535)
    log_level: str = "INFO"
    request_timeout_seconds: float = Field(default=20.0, gt=0)
    audiobookshelf_auth_token: str | None = None
    scraper_user_agent: str = DEFAULT_USER_AGENT
    detail_enrichment_limit: int = Field(default=5, ge=1, le=10)
    enable_audiolibrix: bool = True
    enable_audioteka: bool = True
    enable_kosmas: bool = True
    enable_onehotbook: bool = True
    enable_albatrosmedia: bool = True
    enable_palmknihy: bool = True
    enable_progresguru: bool = True

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
            audiobookshelf_auth_token=os.getenv("AUDIOBOOKSHELF_AUTH_TOKEN"),
            scraper_user_agent=os.getenv("SCRAPER_USER_AGENT", DEFAULT_USER_AGENT),
            enable_audiolibrix=os.getenv("ENABLE_AUDIOLIBRIX", "true"),
            enable_audioteka=os.getenv("ENABLE_AUDIOTEKA", "true"),
            enable_kosmas=os.getenv("ENABLE_KOSMAS", "true"),
            enable_onehotbook=os.getenv("ENABLE_ONEHOTBOOK", "true"),
            enable_albatrosmedia=os.getenv("ENABLE_ALBATROSMEDIA", "true"),
            enable_palmknihy=os.getenv("ENABLE_PALMKNIHY", "true"),
            enable_progresguru=os.getenv("ENABLE_PROGRESGURU", "true"),
        )
