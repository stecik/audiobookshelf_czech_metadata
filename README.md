# Audiolibrix Metadata Provider

`audiolibrix_scraper` is a runnable FastAPI service that implements the Audiobookshelf custom metadata provider contract for the Czech Audiolibrix storefront at [audiolibrix.com/cs](https://www.audiolibrix.com/cs).

Audiobookshelf 2.8.0+ can call external metadata providers over HTTP. This project exposes:

- `GET /health`
- `GET /search?query=...&author=...`

The `/search` response follows the Audiobookshelf shape:

```json
{
  "matches": [
    {
      "title": "1984",
      "author": "George Orwell"
    }
  ]
}
```

## Features

- FastAPI API compatible with Audiobookshelf custom providers
- Static scraping with `httpx` and `selectolax`
- Clear separation between transport, scraping, ranking, and ABS normalization
- Optional shared-token auth via the `AUTHORIZATION` header
- Structured JSON logging and clean JSON errors
- Docker Compose support plus a local `uv` workflow
- Fixture-based tests with no live network dependency

## How Audiobookshelf Uses It

At a high level, Audiobookshelf sends a search request to the provider with a required `query` and an optional `author`. The provider looks up the source site, ranks results, and returns them as `{"matches": [...]}` so ABS can populate book metadata.

This service uses Audiolibrix's public Czech search form at:

```text
https://www.audiolibrix.com/cs/Search/Results?query=...
```

As of March 15, 2026, the site exposes server-rendered search result cards and a small `search-results-info` JSON block with counts, but no stable internal JSON endpoint for full book results was identified. The implementation therefore uses HTML parsing as the primary strategy and keeps the scraper isolated so a future internal API can be plugged in cleanly if Audiolibrix exposes one later.

## Project Layout

```text
app/
  main.py
  config.py
  models.py
  routers/search.py
  services/provider.py
  services/scrapers/base.py
  services/scrapers/audiolibrix.py
  services/normalizers/audiobookshelf.py
  clients/http.py
  utils/text.py
  utils/logging.py
tests/
memory/
Dockerfile
docker-compose.yml
pyproject.toml
.env.example
```

## Local Development With `uv`

Optional: copy the example environment file if you want to override defaults.

```bash
cp .env.example .env
```

Install dependencies:

```bash
uv sync
```

Run the API locally:

```bash
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Run the tests:

```bash
uv run pytest
```

## Docker Compose

Start the service with:

```bash
docker compose up --build
```

The API will be available at:

```text
http://localhost:8000
```

`docker-compose.yml` includes sane defaults, and Docker Compose will also read a local `.env` file if you create one from `.env.example`.

## Environment Variables

Supported configuration:

```env
APP_HOST=0.0.0.0
APP_PORT=8000
LOG_LEVEL=INFO
REQUEST_TIMEOUT_SECONDS=20
AUDIOBOOKSHELF_AUTH_TOKEN=
SCRAPER_USER_AGENT=
```

If `AUDIOBOOKSHELF_AUTH_TOKEN` is set, requests must include an `AUTHORIZATION` header that matches it. For convenience, the server also accepts `Bearer <token>` when the configured value is the raw token.

## API Examples

Health check:

```bash
curl http://localhost:8000/health
```

Search:

```bash
curl "http://localhost:8000/search?query=1984&author=George%20Orwell"
```

Search with auth:

```bash
curl \
  -H "AUTHORIZATION: your-shared-token" \
  "http://localhost:8000/search?query=1984"
```

Example response:

```json
{
  "matches": [
    {
      "title": "1984",
      "author": "George Orwell",
      "narrator": "Ivo Gogál",
      "publisher": "Publixing, SLOVART",
      "publishedYear": "2021",
      "cover": "https://www.audiolibrix.com/...",
      "genres": ["Klasika"],
      "language": "sk",
      "duration": 706
    }
  ]
}
```

## Adding It In Audiobookshelf

1. Start this service locally or with Docker Compose.
2. In Audiobookshelf, open `Settings -> Metadata Tools`.
3. Add a custom metadata provider that points to this service.
4. If your ABS version asks for a base provider URL, use `http://<host>:8000`.
5. If your ABS version asks for the explicit endpoint, use `http://<host>:8000/search`.
6. If you configured `AUDIOBOOKSHELF_AUTH_TOKEN`, enter the same value so Audiobookshelf sends it in the `AUTHORIZATION` header.

## Implementation Notes

- The scraper searches Audiolibrix with a plain GET request.
- Search result cards provide title, author, narrator, cover, and detail links.
- The provider enriches only the top-ranked candidates with detail-page requests to pull publisher, published year, description, genres, language, and duration.
- Ranking prefers exact title matches, then substring/token overlap, then author matches, and finally Czech-language entries when language is distinguishable.
- The implementation intentionally does not fabricate `isbn`, `asin`, or `series` fields.

## Limitations

- Only the Audiolibrix Czech storefront is supported in v1.
- Audiolibrix search results can still include Slovak and English editions; the ranker prefers Czech entries only when the language can be inferred or extracted.
- Detail enrichment is limited to the top results to keep upstream traffic modest.
- If Audiolibrix changes its HTML structure, selector updates may be required.

## Adding Another Source Later

The codebase is structured so adding another source is small and localized:

1. Create a new scraper class in `app/services/scrapers/` implementing `BaseMetadataScraper`.
2. Keep source-specific fetching and parsing inside that scraper.
3. Return internal `SourceBook` models from the scraper.
4. Register the scraper in `app/main.py` when constructing `MetadataProviderService`.
5. Reuse the shared ranking and the Audiobookshelf normalizer unless the new source needs different behavior.
