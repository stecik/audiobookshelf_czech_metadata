# Czech Audiobook Metadata Provider

FastAPI service that implements the Audiobookshelf custom metadata provider contract for Czech audiobook storefronts:

- [Albatros Media Audioknihy](https://www.albatrosmedia.cz/edice/36467691/audioknihy/)
- [Audiolibrix Czech](https://www.audiolibrix.com/cs)
- [Audioteka Czech](https://audioteka.com/cz/)
- [Kosmas Audioknihy](https://www.kosmas.cz/audioknihy/)
- [OneHotBook](https://onehotbook.cz/)
- [Palmknihy Audioknihy](https://www.palmknihy.cz/edice/audioknihy/audioknihy)
- [ProgresGuru Audioknihy](https://progresguru.cz/audioknihy)

## To be added

- <https://www.kanopa.cz/?srsltid=AfmBOooE7C6n0UFleN04MZB8ro91guZpiepF4U6InyCRCkaRq-VtStmR>
- <https://www.luxor.cz/c/10726/audioknihy>
- <https://naposlech.cz/>
- <https://www.megaknihy.cz/tema/1/32787-audioknihy?p=1>
- <https://temata.rozhlas.cz/hry-a-cetba>
- <https://www.radioteka.cz/?srsltid=AfmBOoqEj_Jk27x9zrrXBohlAbX-gbV1JE42Q3cVflU3Z9V9wYN_SvCq>
- <https://www.o2knihovna.cz/audioknihy/>
- <https://www.alza.cz/media/audioknihy/18854370.htm>
- <https://www.knihydobrovsky.cz/audioknihy>

It exposes:

- `GET /health`
- `GET /search?query=...&author=...`
- `GET /albatrosmedia/health` and `GET /albatrosmedia/search?...`
- `GET /audiolibrix/health` and `GET /audiolibrix/search?...`
- `GET /audioteka/health` and `GET /audioteka/search?...`
- `GET /kosmas/health` and `GET /kosmas/search?...`
- `GET /onehotbook/health` and `GET /onehotbook/search?...`
- `GET /palmknihy/health` and `GET /palmknihy/search?...`
- `GET /progresguru/health` and `GET /progresguru/search?...`

Audiobookshelf 2.8.0+ can call external metadata providers over HTTP. This service searches configured sources, ranks matches, normalizes the result into the ABS `{"matches": [...]}` shape, and returns it to Audiobookshelf.

For project structure, tests, and implementation notes, see [DEVELOPMENT.md](DEVELOPMENT.md).

Run the API locally:

```bash
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Run the tests:

```bash
uv run pytest
```

## Deploy With Docker Compose

Optional: create a local environment file before starting the service.

```bash
cp .env.example .env
```

Start the provider:

```bash
docker compose up -d --build
```

The API will be available at:

```text
http://localhost:8000
```

Quick health check:

```bash
curl http://localhost:8000/health
```

## Source Strategy

As of March 15, 2026:

- Albatros Media uses `https://www.albatrosmedia.cz/hledani/?Text=...` and returns server-rendered result cards with embedded per-product metadata in `data-component-args`.
- Albatros Media detail pages expose narrator, duration, language, genre, and publish date in the static `Detailní informace` section.
- Audiolibrix uses `https://www.audiolibrix.com/cs/Search/Results?query=...` and returns server-rendered result cards.
- Audioteka uses `https://audioteka.com/cz/vyhledavani/?phrase=...` and returns server-rendered HTML with embedded search payloads.
- Audioteka detail pages embed structured audiobook payloads plus referenced long descriptions, so no browser automation is required.
- Kosmas uses `https://www.kosmas.cz/hledej/?query=...&Filters.ArticleTypeIds=3593,14074` and returns server-rendered audiobook result cards.
- Kosmas detail pages expose bibliographic metadata and full annotation text in static HTML, while category metadata is available in embedded analytics payloads.
- OneHotBook uses `https://onehotbook.cz/search?q=...&type=product` and returns server-rendered result cards with embedded Shopify product JSON.
- OneHotBook detail pages expose richer narrator and specification metadata in static HTML, including duration and release date.
- Palmknihy uses `https://www.palmknihy.cz/vyhledavani$a885-search?query=...` and returns server-rendered result cards where audiobook matches can be filtered via `item-type="audiobook"`.
- Palmknihy detail pages expose publisher, genres, language, duration, and publish year in static HTML. The description block looked inconsistent on at least one live audiobook page, so description enrichment is intentionally conservative for this source.
- ProgresGuru uses the storefront JSON API at `https://progresguru.cz/api/audiobooks?search=...&page=1`.
- ProgresGuru detail enrichment uses `https://progresguru.cz/api/audiobooks/<slug>` for subtitle, duration, publisher, full author list, narrator list, description, and publish date.

## Runtime Configuration

Application settings:

```env
APP_HOST=0.0.0.0
APP_PORT=8000
LOG_LEVEL=INFO
REQUEST_TIMEOUT_SECONDS=20
AUDIOBOOKSHELF_AUTH_TOKEN=
SCRAPER_USER_AGENT=
ENABLE_ALBATROSMEDIA=true
ENABLE_AUDIOLIBRIX=true
ENABLE_AUDIOTEKA=true
ENABLE_KOSMAS=true
ENABLE_ONEHOTBOOK=true
ENABLE_PALMKNIHY=true
ENABLE_PROGRESGURU=true
```

If `AUDIOBOOKSHELF_AUTH_TOKEN` is set, Audiobookshelf must send the same value in the `AUTHORIZATION` header. This provider also accepts `Bearer <token>`.

All sources are enabled by default. Set any `ENABLE_*` flag to `false` to skip that storefront entirely.

When a source is disabled, it is excluded from the global `/search` results and its source-specific endpoint is not registered.

## Audiobookshelf Setup

Audiobookshelf expects the provider base URL, not `/search`.

1. In Audiobookshelf, open `Settings -> Metadata Tools -> Custom Metadata Providers -> Add`.
2. Set `Typ média` / Media Type to `Book`.
3. Use one of these URLs:

- ABS running locally on the same machine as the provider: `http://localhost:8000`
- ABS running in Docker on the same Docker network as the provider: `http://provider:8000`
- Albatros Media-only provider: `http://localhost:8000/albatrosmedia`
- Audiolibrix-only provider: `http://localhost:8000/audiolibrix`
- Audioteka-only provider: `http://localhost:8000/audioteka`
- Kosmas-only provider: `http://localhost:8000/kosmas`
- OneHotBook-only provider: `http://localhost:8000/onehotbook`
- Palmknihy-only provider: `http://localhost:8000/palmknihy`
- ProgresGuru-only provider: `http://localhost:8000/progresguru`

1. Leave `Hodnota autorizačního headeru` / Authorization Header Value blank unless `AUDIOBOOKSHELF_AUTH_TOKEN` is set.
2. Save the provider and run a metadata search/refresh on a book or audiobook.

If you want separate selectors in Audiobookshelf for each store, add multiple custom providers pointing at the source-specific base URLs above. ABS will call `/search` under whichever base URL you configure.

## Separate Compose Projects

If Audiobookshelf and this provider run from separate Compose projects, attach both stacks to the same external Docker network and use `http://provider:8000` in ABS.

1. Attach the Audiobookshelf stack to the same external network:

```yaml
services:
  audiobookshelf:
    image: ghcr.io/advplyr/audiobookshelf:latest
    container_name: audiobookshelf
    ports:
      - 13378:80
    volumes:
      - /mnt/books/Audioknihy:/audiobooks
      - /opt/audiobookshelf/config:/config
      - /opt/audiobookshelf/metadata:/metadata
    environment:
      - TZ=Europe/Prague
    restart: unless-stopped
    networks:
      - abs_shared

networks:
  abs_shared:
    external: true
    name: audiobookshelf_shared
```

1. In Audiobookshelf, set the provider URL to:

```text
http://provider:8000
```

## Verification

Health check:

```bash
curl http://localhost:8000/health
```

Search:

```bash
curl "http://localhost:8000/search?query=1984&author=George%20Orwell"
```

Audioteka only:

```bash
curl "http://localhost:8000/audioteka/search?query=1984&author=George%20Orwell"
```

Kosmas only:

```bash
curl "http://localhost:8000/kosmas/search?query=1984&author=George%20Orwell"
```

Albatros Media only:

```bash
curl "http://localhost:8000/albatrosmedia/search?query=Podzimn%C3%AD%20d%C4%9Bsy&author=Agatha%20Christie"
```

ProgresGuru only:

```bash
curl "http://localhost:8000/progresguru/search?query=Okam%C5%BEit%C3%A1%20pomoc%20proti%20%C3%BAzkosti&author=Matthew%20McKay"
```

Palmknihy only:

```bash
curl "http://localhost:8000/palmknihy/search?query=Praskl%C3%A9%20zrcadlo&author=Agatha%20Christie"
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
      "narrator": "Jan Vondráček, Jaromír Meduna, Jitka Moučková",
      "publisher": "Audiostory",
      "publishedYear": "2021",
      "description": "Audiokniha 1984 obsahuje literární klasiku George Orwella.",
      "cover": "https://atkcdn.audioteka.com/cc/b2/1984-audiostory/68.jpg",
      "genres": ["Klasická díla", "Zahraniční literatura"],
      "language": "cs",
      "duration": 711
    }
  ]
}
```

## Known Limitations

- Albatros Media Audioknihy, Audiolibrix Czech, Audioteka Czech, Kosmas Audioknihy, OneHotBook, Palmknihy Audioknihy, and ProgresGuru Audioknihy are supported right now.
- Albatros Media search is global storefront search, so the scraper applies audiobook-only filtering heuristics to drop obvious non-audiobook matches.
- Audiolibrix still relies on HTML parsing because no stable full search JSON endpoint was identified.
- Audioteka search and detail parsing relies on embedded Next.js payloads, so payload-shape changes may require updates.
- Kosmas search works best when the upstream request contains the title only, so the scraper intentionally keeps author matching in the provider-layer ranking instead of the Kosmas query string.
- Kosmas currently exposes misleading canonical `audioknihy/?query=...` URLs, but the reliable working search response comes from the filtered `/hledej/` route that the scraper uses.
- OneHotBook search parsing relies on embedded Shopify product JSON inside server-rendered result cards, and detail enrichment relies on the current product/specification page layout.
- Palmknihy description enrichment is intentionally disabled for now because live inspection found at least one audiobook detail page with a mismatched description block and mismatched JSON-LD description.
- ProgresGuru relies on first-party storefront JSON endpoints under `/api/audiobooks`, and some multi-author titles only expose the full author list after detail enrichment.
- Detail enrichment is limited to the top-ranked candidates to keep upstream traffic modest.

## Adding Another Source

The codebase is structured so another source can be added in a small, isolated change:

1. Create a new scraper in `app/services/scrapers/`.
2. Return internal `SourceBook` models from that scraper.
3. Register it in `app/main.py`.
4. Reuse the shared ranking and Audiobookshelf normalizer unless the new source needs different behavior.

## References

- [Custom Metadata Providers guide](https://www.audiobookshelf.org/guides/custom-metadata-providers/)
- [Custom provider OpenAPI specification](https://github.com/advplyr/audiobookshelf/blob/master/custom-metadata-provider-specification.yaml)
