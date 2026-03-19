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
    match_confidence: float | None = None
    detail_loaded: bool = False


class AudiobookshelfSeries(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(description="Series name.")
    sequence: str | None = Field(default=None, description="Series sequence or volume label.")


class AudiobookshelfMatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(description="Primary title of the matched book or audiobook.")
    subtitle: str | None = Field(default=None, description="Subtitle when explicitly exposed by the source.")
    author: str | None = Field(default=None, description="Author list rendered as a comma-separated string.")
    narrator: str | None = Field(default=None, description="Narrator list rendered as a comma-separated string.")
    publisher: str | None = Field(default=None, description="Publisher or imprint.")
    publishedYear: str | None = Field(default=None, description="Publication or release year as a string.")
    description: str | None = Field(default=None, description="Book or audiobook description.")
    cover: str | None = Field(default=None, description="Absolute URL to the cover image.")
    isbn: str | None = Field(default=None, description="ISBN when explicitly available from the source.")
    asin: str | None = Field(default=None, description="ASIN when explicitly available from the source.")
    genres: list[str] | None = Field(default=None, description="Genre names extracted from the source.")
    tags: list[str] | None = Field(default=None, description="Additional tags extracted from the source.")
    series: list[AudiobookshelfSeries] | None = Field(default=None, description="Series metadata when available.")
    language: str | None = Field(default=None, description="Language code, typically `cs`.")
    duration: int | None = Field(default=None, description="Runtime in minutes.")
    matchConfidence: float | None = Field(
        default=None,
        description="Match confidence score between 0 and 1, used by Audiobookshelf for certainty badges.",
    )


class SearchResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    matches: list[AudiobookshelfMatch] = Field(
        default_factory=list,
        description="Ordered list of normalized matches returned to Audiobookshelf.",
    )


class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str = Field(default="ok", description="Simple health indicator.")
