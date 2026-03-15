# Czech Audiobook Metadata Provider

FastAPI service that implements the Audiobookshelf custom metadata provider contract for Czech audiobook storefronts:

- [Audiolibrix Czech](https://www.audiolibrix.com/cs)
- [Audioteka Czech](https://audioteka.com/cz/)
- [OneHotBook](https://onehotbook.cz/)

## To be added

- <https://www.albatrosmedia.cz/edice/36467691/audioknihy/>
- <https://progresguru.cz/audioknihy>
- <https://www.kanopa.cz/?srsltid=AfmBOooE7C6n0UFleN04MZB8ro91guZpiepF4U6InyCRCkaRq-VtStmR>
- <https://www.luxor.cz/c/10726/audioknihy>
- <https://naposlech.cz/>
- <https://www.megaknihy.cz/tema/1/32787-audioknihy?p=1>
- <https://temata.rozhlas.cz/hry-a-cetba>
- <https://www.radioteka.cz/?srsltid=AfmBOoqEj_Jk27x9zrrXBohlAbX-gbV1JE42Q3cVflU3Z9V9wYN_SvCq>
- <https://www.o2knihovna.cz/audioknihy/>
- <https://www.alza.cz/media/audioknihy/18854370.htm>
- <https://www.knihydobrovsky.cz/audioknihy>
- <https://www.palmknihy.cz/edice/audioknihy/audioknihy>
- <https://www.kosmas.cz/audioknihy/>

It exposes:

- `GET /health`
- `GET /search?query=...&author=...`
- `GET /audiolibrix/health` and `GET /audiolibrix/search?...`
- `GET /audioteka/health` and `GET /audioteka/search?...`
- `GET /onehotbook/health` and `GET /onehotbook/search?...`

Audiobookshelf 2.8.0+ can call external metadata providers over HTTP. This service searches configured sources, ranks matches, normalizes the result into the ABS `{"matches": [...]}` shape, and returns it to Audiobookshelf.

For project structure, tests, and implementation notes, see [DEVELOPMENT.md](DEVELOPMENT.md).

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

- Audiolibrix uses `https://www.audiolibrix.com/cs/Search/Results?query=...` and returns server-rendered result cards.
- Audioteka uses `https://audioteka.com/cz/vyhledavani/?phrase=...` and returns server-rendered HTML with embedded search payloads.
- Audioteka detail pages embed structured audiobook payloads plus referenced long descriptions, so no browser automation is required.
- OneHotBook uses `https://onehotbook.cz/search?q=...&type=product` and returns server-rendered result cards with embedded Shopify product JSON.
- OneHotBook detail pages expose richer narrator and specification metadata in static HTML, including duration and release date.

## Runtime Configuration

Application settings:

```env
APP_HOST=0.0.0.0
APP_PORT=8000
LOG_LEVEL=INFO
REQUEST_TIMEOUT_SECONDS=20
AUDIOBOOKSHELF_AUTH_TOKEN=
SCRAPER_USER_AGENT=
ENABLE_AUDIOLIBRIX=true
ENABLE_AUDIOTEKA=true
ENABLE_ONEHOTBOOK=true
```

If `AUDIOBOOKSHELF_AUTH_TOKEN` is set, Audiobookshelf must send the same value in the `AUTHORIZATION` header. This provider also accepts `Bearer <token>`.

All sources are enabled by default. Set any `ENABLE_*` flag to `false` to skip that storefront entirely.

When a source is disabled, it is excluded from the global `/search` results and its source-specific endpoint is not registered.

Optional shared-network override:

```env
SHARED_DOCKER_NETWORK=audiobookshelf_shared
```

`SHARED_DOCKER_NETWORK` is used only by `docker-compose.shared-network.yml`.

## Audiobookshelf Setup

Audiobookshelf expects the provider base URL, not `/search`.

1. In Audiobookshelf, open `Settings -> Metadata Tools -> Custom Metadata Providers -> Add`.
2. Set `Typ média` / Media Type to `Book`.
3. Use one of these URLs:

- ABS running locally on the same machine as the provider: `http://localhost:8000`
- ABS running in Docker on the same Docker network as the provider: `http://provider:8000`
- Audiolibrix-only provider: `http://localhost:8000/audiolibrix`
- Audioteka-only provider: `http://localhost:8000/audioteka`
- OneHotBook-only provider: `http://localhost:8000/onehotbook`

1. Leave `Hodnota autorizačního headeru` / Authorization Header Value blank unless `AUDIOBOOKSHELF_AUTH_TOKEN` is set.
2. Save the provider and run a metadata search/refresh on a book or audiobook.

If you want separate selectors in Audiobookshelf for each store, add multiple custom providers pointing at the source-specific base URLs above. ABS will call `/search` under whichever base URL you configure.

## Separate Compose Projects

If Audiobookshelf and this provider run from separate Compose projects, attach both stacks to the same external Docker network and use `http://provider:8000` in ABS.

1. Create a shared network once:

```bash
docker network create audiobookshelf_shared
```

If your Audiobookshelf stack already created a network such as `audiobookshelf_default`, you can reuse that instead by setting `SHARED_DOCKER_NETWORK=audiobookshelf_default`.

1. Start this provider with the shared-network override:

```bash
docker compose -f docker-compose.yml -f docker-compose.shared-network.yml up -d --build
```

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

- Audiolibrix Czech, Audioteka Czech, and OneHotBook are supported right now.
- Audiolibrix still relies on HTML parsing because no stable full search JSON endpoint was identified.
- Audioteka search and detail parsing relies on embedded Next.js payloads, so payload-shape changes may require updates.
- OneHotBook search parsing relies on embedded Shopify product JSON inside server-rendered result cards, and detail enrichment relies on the current product/specification page layout.
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
