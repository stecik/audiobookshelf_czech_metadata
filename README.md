# Czech Audiobook Metadata Provider

FastAPI service that implements the Audiobookshelf custom metadata provider contract for Czech audiobook storefronts:

- [Alza Audioknihy](https://www.alza.cz/media/audioknihy/18854370.htm) (currently not working)
- [Albatros Media Audioknihy](https://www.albatrosmedia.cz/edice/36467691/audioknihy/)
- [Audiolibrix Czech](https://www.audiolibrix.com/cs)
- [Audioteka Czech](https://audioteka.com/cz/)
- [Kanopa](https://www.kanopa.cz/)
- [Knihy Dobrovský Audioknihy](https://www.knihydobrovsky.cz/audioknihy)
- [Kosmas Audioknihy](https://www.kosmas.cz/audioknihy/)
- [Luxor Audioknihy](https://www.luxor.cz/c/10726/audioknihy)
- [Megaknihy Audioknihy](https://www.megaknihy.cz/tema/1/32787-audioknihy?p=1)
- [Naposlech](https://naposlech.cz/)
- [OneHotBook](https://onehotbook.cz/)
- [O2 Knihovna Audioknihy](https://www.o2knihovna.cz/audioknihy/)
- [Palmknihy Audioknihy](https://www.palmknihy.cz/edice/audioknihy/audioknihy)
- [ProgresGuru Audioknihy](https://progresguru.cz/audioknihy)
- [Radioteka](https://www.radioteka.cz/)
- [Rozhlas Hry a audioknihy](https://temata.rozhlas.cz/hry-a-cetba)

It exposes:

- `GET /health`
- `GET /search?query=...&author=...`
- `GET /alza/health` and `GET /alza/search?...`
- `GET /albatrosmedia/health` and `GET /albatrosmedia/search?...`
- `GET /audiolibrix/health` and `GET /audiolibrix/search?...`
- `GET /audioteka/health` and `GET /audioteka/search?...`
- `GET /kanopa/health` and `GET /kanopa/search?...`
- `GET /knihydobrovsky/health` and `GET /knihydobrovsky/search?...`
- `GET /kosmas/health` and `GET /kosmas/search?...`
- `GET /luxor/health` and `GET /luxor/search?...`
- `GET /megaknihy/health` and `GET /megaknihy/search?...`
- `GET /naposlech/health` and `GET /naposlech/search?...`
- `GET /onehotbook/health` and `GET /onehotbook/search?...`
- `GET /o2knihovna/health` and `GET /o2knihovna/search?...`
- `GET /palmknihy/health` and `GET /palmknihy/search?...`
- `GET /progresguru/health` and `GET /progresguru/search?...`
- `GET /radioteka/health` and `GET /radioteka/search?...`
- `GET /rozhlas/health` and `GET /rozhlas/search?...`

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

## Runtime Configuration

Application settings:

```env
APP_HOST=0.0.0.0
APP_PORT=8000
LOG_LEVEL=INFO
REQUEST_TIMEOUT_SECONDS=20
SCRAPER_TIMEOUT_SECONDS=8
AUDIOBOOKSHELF_AUTH_TOKEN=
SCRAPER_USER_AGENT=
ENABLE_ALZA=false
ENABLE_ALBATROSMEDIA=true
ENABLE_AUDIOLIBRIX=true
ENABLE_AUDIOTEKA=true
ENABLE_KANOPA=true
ENABLE_KNIHYDOBROVSKY=true
ENABLE_KOSMAS=true
ENABLE_LUXOR=true
ENABLE_MEGAKNIHY=true
ENABLE_NAPOSLECH=true
ENABLE_ONEHOTBOOK=true
ENABLE_O2KNIHOVNA=true
ENABLE_PALMKNIHY=true
ENABLE_PROGRESGURU=true
ENABLE_RADIOTEKA=true
ENABLE_ROZHLAS=true
```

If `AUDIOBOOKSHELF_AUTH_TOKEN` is set, Audiobookshelf must send the same value in the `AUTHORIZATION` header. This provider also accepts `Bearer <token>`.

## Audiobookshelf metadata timeout

- ABS has max metadata timeout set to 10s
- The longer `REQUEST_TIMEOUT_SECONDS` and `SCRAPER_TIMEOUT_SECONDS` the more accurate but slower results you get
- if you see no results, lower the timeout (do not go above 8s)

`REQUEST_TIMEOUT_SECONDS` controls the timeout of a single upstream HTTP request. `SCRAPER_TIMEOUT_SECONDS` controls the total time budget for one scraper search or detail-enrichment task. If one scraper exceeds that limit, its results are skipped and the remaining scrapers still complete normally. If every scraper times out, the API returns an empty `matches` list instead of failing the request.

All sources are enabled by default. Set any `ENABLE_*` flag to `false` to skip that storefront entirely. ALZA is currently not working

When a source is disabled, it is excluded from the global `/search` results and its source-specific endpoint is not registered.

## Audiobookshelf Setup

Audiobookshelf expects the provider base URL, not `/search`.

1. In Audiobookshelf, open `Settings -> Metadata Tools -> Custom Metadata Providers -> Add`.
2. Set Media Type to `Book`.
3. Use one of these URLs:

- ABS running locally on the same machine as the provider: `http://localhost:8000`
- ABS running in Docker on the same Docker network as the provider: `http://provider:8000`

**Use `localhost` or `provider`**

- Alza-only provider: `http://localhost:8000/alza`
- Albatros Media-only provider: `http://localhost:8000/albatrosmedia`
- Audiolibrix-only provider: `http://localhost:8000/audiolibrix`
- Audioteka-only provider: `http://localhost:8000/audioteka`
- Kanopa-only provider: `http://localhost:8000/kanopa`
- Knihy Dobrovsky-only provider: `http://localhost:8000/knihydobrovsky`
- Kosmas-only provider: `http://localhost:8000/kosmas`
- Luxor-only provider: `http://localhost:8000/luxor`
- Megaknihy-only provider: `http://localhost:8000/megaknihy`
- Naposlech-only provider: `http://localhost:8000/naposlech`
- OneHotBook-only provider: `http://localhost:8000/onehotbook`
- O2 Knihovna-only provider: `http://localhost:8000/o2knihovna`
- Palmknihy-only provider: `http://localhost:8000/palmknihy`
- ProgresGuru-only provider: `http://localhost:8000/progresguru`
- Radioteka-only provider: `http://localhost:8000/radioteka`
- Rozhlas-only provider: `http://localhost:8000/rozhlas`

1. Leave Authorization Header Value blank unless `AUDIOBOOKSHELF_AUTH_TOKEN` is set.
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

Alza only:

```bash
curl "http://localhost:8000/alza/search?query=1984&author=George%20Orwell"
```

Audioteka only:

```bash
curl "http://localhost:8000/audioteka/search?query=1984&author=George%20Orwell"
```

Kanopa only:

```bash
curl "http://localhost:8000/kanopa/search?query=Hypot%C3%A9za%20zla&author=Donato%20Carrisi"
```

Knihy Dobrovsky only:

```bash
curl "http://localhost:8000/knihydobrovsky/search?query=1984&author=George%20Orwell"
```

Kosmas only:

```bash
curl "http://localhost:8000/kosmas/search?query=1984&author=George%20Orwell"
```

Luxor only:

```bash
curl "http://localhost:8000/luxor/search?query=1984&author=George%20Orwell"
```

Megaknihy only:

```bash
curl "http://localhost:8000/megaknihy/search?query=%C5%A0ikm%C3%BD%20kostel&author=Karin%20Lednick%C3%A1"
```

Naposlech only:

```bash
curl "http://localhost:8000/naposlech/search?query=1984&author=George%20Orwell"
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

O2 Knihovna only:

```bash
curl "http://localhost:8000/o2knihovna/search?query=1984&author=George%20Orwell"
```

Radioteka only:

```bash
curl "http://localhost:8000/radioteka/search?query=1984&author=George%20Orwell"
```

Rozhlas only:

```bash
curl "http://localhost:8000/rozhlas/search?query=Sko%C5%99%C3%A1pka&author=Ian%20McEwan"
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

## References

- [Custom Metadata Providers guide](https://www.audiobookshelf.org/guides/custom-metadata-providers/)
- [Custom provider OpenAPI specification](https://github.com/advplyr/audiobookshelf/blob/master/custom-metadata-provider-specification.yaml)
