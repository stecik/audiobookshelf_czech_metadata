# Development

This document covers local development, project structure, tests, and implementation details.

For deployment and Audiobookshelf setup, see [README.md](README.md).

## Project Layout

```text
app/
  main.py
  config.py
  models.py
  routers/search.py
  services/provider.py
  services/scrapers/base.py
  services/scrapers/audioteka.py
  services/scrapers/audiolibrix.py
  services/scrapers/kosmas.py
  services/normalizers/audiobookshelf.py
  clients/http.py
  utils/text.py
  utils/logging.py
tests/
memory/
Dockerfile
docker-compose.yml
docker-compose.shared-network.yml
pyproject.toml
.env.example
README.md
DEVELOPMENT.md
```

## Local Development With `uv`

Optional: create a local environment file before working locally.

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

## Configuration Reference

Application settings:

```env
APP_HOST=0.0.0.0
APP_PORT=8000
LOG_LEVEL=INFO
REQUEST_TIMEOUT_SECONDS=20
AUDIOBOOKSHELF_AUTH_TOKEN=
SCRAPER_USER_AGENT=
```

## How Audiobookshelf Uses It

Audiobookshelf sends a search request to the provider with a required `query` and an optional `author`. The provider looks up the source site, ranks results, and returns them as `{"matches": [...]}` so ABS can populate book metadata.

Current source strategies:

- Audiolibrix: `https://www.audiolibrix.com/cs/Search/Results?query=...`
- Audioteka: `https://audioteka.com/cz/vyhledavani/?phrase=...`
- Kosmas: `https://www.kosmas.cz/hledej/?query=...&Filters.ArticleTypeIds=3593,14074`
- Luxor: `https://www.luxor.cz/api/luigis/search?params=...` with UTF-8 JSON base64 request payloads and audiobook assortment filters `31` / `20`

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

## Implementation Notes

- Audiolibrix search uses a plain GET request and server-rendered result cards.
- Audioteka search uses the public `vyhledavani/?phrase=...` route and parses the embedded `products` payload from the server response.
- Audioteka detail enrichment parses the embedded `audiobook` payload and referenced description strings from the detail page response.
- Luxor search uses the first-party `api/luigis/search` endpoint and filters the payload down to audiobook product types (`017`, `022`) as a safeguard even though the request also sends audiobook assortment filters.
- Luxor detail pages currently render as Angular shells, so the current Luxor implementation intentionally keeps enrichment as a no-op and relies on the search payload for title, author, publisher, description, cover, and genre data.
- The provider enriches only the top-ranked candidates with detail-page requests to pull publisher, published year, description, genres, language, and duration.
- Ranking prefers exact title matches, then substring/token overlap, then author matches, and finally Czech-language entries when language is distinguishable.
- The implementation intentionally does not fabricate `isbn`, `asin`, or `series` fields.

As of March 15, 2026:

- Audiolibrix exposes server-rendered search result cards and a small `search-results-info` JSON block with counts, but no stable internal JSON endpoint for full book results was identified.
- Audioteka exposes a server-rendered search page with embedded `products` payloads and detail pages with embedded `audiobook` payloads.

## Testing

The test suite is fixture-based and does not depend on live network access.

Current coverage includes:

- `/health` API test
- `/search` API test with mocked provider behavior
- Audioteka parser fixture tests
- Audiolibrix parser fixture tests
- ranking tests

Run all tests with:

```bash
uv run pytest
```

## Adding Another Source Later

The codebase is structured so adding another source is small and localized:

1. Create a new scraper class in `app/services/scrapers/` implementing `BaseMetadataScraper`.
2. Keep source-specific fetching and parsing inside that scraper.
3. Return internal `SourceBook` models from the scraper.
4. Register the scraper in `app/main.py` when constructing `MetadataProviderService`.
5. Reuse the shared ranking and the Audiobookshelf normalizer unless the new source needs different behavior.
