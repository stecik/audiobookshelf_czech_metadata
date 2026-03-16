# AGENTS.md

## Goal

Build a **Python + FastAPI custom metadata provider** for **Audiobookshelf** that scrapes Czech storefronts starting with:

- `https://www.audiolibrix.com/cs`
- `https://audioteka.com/cz/`

The codebase must keep source-specific logic isolated so adding more sources later is straightforward.

## Agent memory

Keep persistent working memory under `memory/`.

- Store notes only as Markdown files.
- Use `memory/` for live site inspection notes, implementation decisions, parser findings, and follow-up items.
- When repo-level workflow rules change, reflect them in `AGENTS.md`.

## Product context

Audiobookshelf supports **custom metadata providers** via an external HTTP API. The provider is added in Audiobookshelf under **Metadata Tools** and ABS calls the provider's `/search` endpoint. ABS documentation states that custom providers were added in **server version 2.8.0+** and points to an OpenAPI spec for the request/response contract.

The relevant API shape from the Audiobookshelf spec is:

- `GET /search`
- query param `query` is required
- query param `author` is optional
- success response contains `{"matches": [...]}`
- each match can include fields like `title`, `subtitle`, `author`, `narrator`, `publisher`, `publishedYear`, `description`, `cover`, `isbn`, `asin`, `genres`, `tags`, `series`, `language`, `duration` (duration is in minutes)

## Non-goals for v1

- No browser automation unless absolutely necessary.
- No database.
- No caching layer unless it is tiny and fileless.
- No support for detail pages beyond what is needed to produce good metadata.
- No support for every possible Audiobookshelf field if the sources do not expose it.

## Required stack

- Python 3.12+
- FastAPI
- httpx
- selectolax
- pydantic
- uv for Python package management and running commands
- Docker + Docker Compose

Use `uv`, not `pip`, for the project workflow. Reference: Astral uv docs.

## Repository shape

Use this exact or very similar layout:

```text
.
├─ app/
│  ├─ main.py
│  ├─ config.py
│  ├─ models.py
│  ├─ routers/
│  │  └─ search.py
│  ├─ services/
│  │  ├─ provider.py
│  │  ├─ scrapers/
│  │  │  ├─ base.py
│  │  │  ├─ audioteka.py
│  │  │  └─ audiolibrix.py
│  │  └─ normalizers/
│  │     └─ audiobookshelf.py
│  ├─ clients/
│  │  └─ http.py
│  └─ utils/
│     ├─ text.py
│     └─ logging.py
├─ tests/
│  ├─ test_search_api.py
│  ├─ test_audioteka_parser.py
│  ├─ test_audiolibrix_parser.py
│  └─ fixtures/
├─ Dockerfile
├─ docker-compose.yml
├─ pyproject.toml
├─ README.md
├─ .env.example
└─ AGENTS.md
```

## Architectural rules

1. **Separate transport, scraping, and normalization.**
   - FastAPI route handles HTTP concerns.
   - Provider service orchestrates search.
   - Source scraper knows how to fetch and parse one storefront.
   - Normalizer maps source data into ABS response schema.

2. **Design for multiple future sources.**
   - Introduce a scraper interface or abstract base class.
   - The provider service should work with a list/registry of scrapers.
   - Source-specific code must stay in `services/scrapers/`.

3. **Be resilient to partial metadata.**
   - Return only fields confidently extracted.
   - Never invent ISBN/ASIN/series values.
   - Missing fields should be omitted or `null` in internal structures, then excluded from JSON where appropriate.

4. **Prefer deterministic HTML parsing.**
   - First attempt should use server-rendered HTML.
   - Only introduce a JS-rendering fallback if parsing proves impossible.

5. **Keep it production-usable.**
   - Timeouts
   - sensible user-agent
   - structured logging
   - clear error handling
   - health endpoint

## Functional requirements

Implement these endpoints:

### `GET /health`

Returns a simple health payload.

Example:

```json
{"status": "ok"}
```

### `GET /search`

Audiobookshelf-compatible search endpoint.

Inputs:

- `query` required
- `author` optional

Behavior:

- Search all configured sources using `query` and optionally `author`
- Parse result listings from the site
- If result cards do not contain enough metadata, optionally follow detail links for top matches only
- Normalize into ABS `matches`
- Return JSON matching the ABS spec

Example response shape:

```json
{
  "matches": [
    {
      "title": "Example title",
      "author": "Example author",
      "narrator": "Example narrator",
      "publisher": "Example publisher",
      "publishedYear": "2024",
      "description": "...",
      "cover": "https://...",
      "genres": ["Detektivky"],
      "language": "cs"
    }
  ]
}
```

## Search strategy for sources

You must inspect each target site and implement the simplest reliable strategy.

Preferred order:

1. If a source exposes a stable internal API for search results, prefer that.
2. Otherwise find whether the site has a query URL or search form usable with plain HTTP GET.
3. If the landing page includes links to search results or exposes query params, use those.
4. If the site requires a search POST, implement it with `httpx`.
5. If results are rendered client-side only, document that clearly and add a fallback strategy.

Important:

- Start from the storefront homepages, but do not hardcode the whole implementation around only one page template if you can avoid it.
- Keep URL building isolated in the scraper.
- Normalize relative URLs to absolute URLs.

Current known entrypoints:

- Audiolibrix: `https://www.audiolibrix.com/cs/Search/Results?query=...`
- Audioteka: `https://audioteka.com/cz/vyhledavani/?phrase=...`

## Matching and ranking

Implement a simple ranking strategy:

- exact title match boosted highest
- title substring match next
- author match boosts score when `author` is supplied
- Czech language entries preferred if distinguishable

Return results ordered by score descending.

## Data mapping rules

Map source fields carefully.

### Safe mappings

- page title -> `title`
- subtitle if explicitly present -> `subtitle`
- author(s) -> `author` as a comma-separated string if multiple
- narrator(s) -> `narrator`
- publisher -> `publisher`
- release year -> `publishedYear` as string
- description/blurb -> `description`
- cover image URL -> `cover`
- categories/genres -> `genres`
- `cs` -> `language`
- duration only if clearly present and parsable to minutes -> `duration`

### Do not guess

- `isbn`
- `asin`
- `series` / `sequence`

Only populate those if explicitly available and unambiguous.

## Parsing quality bar

- Handle Czech diacritics correctly.
- Normalize whitespace.
- Strip marketing fluff like badge text only if it pollutes fields.
- Preserve useful punctuation inside titles/subtitles.

Example:

```text
Input:  "  Šikmý kostel  :  románová kronika  "
Output: "Šikmý kostel: románová kronika"
```

## Config

Support configuration via environment variables:

- `APP_HOST=0.0.0.0`
- `APP_PORT=8000`
- `LOG_LEVEL=INFO`
- `REQUEST_TIMEOUT_SECONDS=20`
- `AUDIOBOOKSHELF_AUTH_TOKEN=` optional shared token
- `SCRAPER_USER_AGENT=` custom UA string

If `AUDIOBOOKSHELF_AUTH_TOKEN` is set, validate incoming `AUTHORIZATION` header because the ABS spec defines API key auth via the `AUTHORIZATION` header. citeturn629975view0

## Docker requirements

Provide:

### Dockerfile

- small Python base image
- install uv
- install deps from `pyproject.toml`
- run FastAPI app with a production-friendly command

### docker-compose.yml

Must include one service for the provider.
Use port `8000:8000` by default.
Add env file support.

Example developer UX:

```bash
docker compose up --build
```

## Local developer UX

The repo must work locally without Docker too.

Document commands using `uv`:

```bash
uv sync
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
uv run pytest
```

## Testing requirements

Create tests.

Minimum:

1. API test for `/health`
2. API test for `/search` with mocked scraper/service
3. Parser tests using saved HTML fixtures from Audiolibrix pages if possible
4. Ranking test for title/author scoring logic

Do not depend on live network in tests.

## Observability

- Log inbound search requests at info level without leaking secrets.
- Log upstream fetch failures with URL and timeout context.
- Return clean JSON errors.

Example:

```json
{"error": "upstream source unavailable"}
```

## Documentation requirements

Write a `README.md` that includes:

- what this provider is
- ABS compatibility
- how to run locally with `uv`
- how to run with Docker Compose
- how to add it in Audiobookshelf
- example `/search` request
- example response
- known limitations
- how to add a second scraper later

## Code quality rules

- Type hints everywhere practical.
- Prefer small functions.
- Avoid giant parser methods.
- Use pydantic models for response contracts.
- No dead code.
- No hidden magic constants.
- Centralize selectors used for HTML parsing.
- Avoid unnecessary side effects
- OOP design

## Delivery checklist

Before finishing, ensure the generated project includes:

- working FastAPI app
- ABS-compatible `/search`
- health endpoint
- Dockerfile
- docker-compose.yml
- pyproject.toml using uv workflow
- tests
- README
- extensible scraper architecture

## Notes to the coding agent

When implementing a scraper, actively inspect the live HTML structure or embedded payloads of the target source and adapt selectors accordingly. If the site structure prevents reliable scraping with static requests, document the issue in the README and isolate any fallback path behind a clean abstraction rather than scattering special cases through the code.

## Changelog, README and sematic versioning

- <https://keepachangelog.com/en/1.1.0/>
- <https://semver.org/>
- README.md - how to run, project info for humans

## Audiobookshelf

- <https://github.com/advplyr/audiobookshelf>

## Async code

- write async code - so the scrappers run in parallel, not sequentially
