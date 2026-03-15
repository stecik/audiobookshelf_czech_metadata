from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class SourceBook(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str
    source_id: str = ""
    title: str
    detail_url: str
    subtitle: str | None = None
    authors: list[str] = Field(default_factory=list)
    narrators: list[str] = Field(default_factory=list)
    publishers: list[str] = Field(default_factory=list)
    published_year: str | None = None
    description: str | None = None
    cover_url: str | None = None
    genres: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    language: str | None = None
    duration_minutes: int | None = None
    detail_loaded: bool = False


class AudiobookshelfSeries(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    sequence: str | None = None


class AudiobookshelfMatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    subtitle: str | None = None
    author: str | None = None
    narrator: str | None = None
    publisher: str | None = None
    publishedYear: str | None = None
    description: str | None = None
    cover: str | None = None
    isbn: str | None = None
    asin: str | None = None
    genres: list[str] | None = None
    tags: list[str] | None = None
    series: list[AudiobookshelfSeries] | None = None
    language: str | None = None
    duration: int | None = None


class SearchResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    matches: list[AudiobookshelfMatch] = Field(default_factory=list)


class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str = "ok"
