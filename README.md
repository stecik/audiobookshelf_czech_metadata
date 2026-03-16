# Czech Audiobook Metadata Provider

FastAPI service that implements the Audiobookshelf custom metadata provider contract for Czech audiobook storefronts:

- [Alza Audioknihy](https://www.alza.cz/media/audioknihy/18854370.htm)
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

## Source Strategy

As of March 16, 2026:

- Alza uses the storefront search route `https://www.alza.cz/search.htm?exps=...` with a mobile fallback at `https://m.alza.cz/search.htm?exps=...`.
- Alza result pages are parsed conservatively via product-detail URLs plus nearby audiobook summary text, because the storefront can return generic product-search markup rather than a clean audiobook-only listing API.
- Alza detail enrichment reads generic `<h1>` / Open Graph metadata plus visible labeled fields such as `Autor`, `Čte`, `Jazyk`, `Rok vydání`, `Délka`, and `Kategorie`.
- Albatros Media uses `https://www.albatrosmedia.cz/hledani/?Text=...` and returns server-rendered result cards with embedded per-product metadata in `data-component-args`.
- Albatros Media detail pages expose narrator, duration, language, genre, and publish date in the static `Detailní informace` section.
- Audiolibrix uses `https://www.audiolibrix.com/cs/Search/Results?query=...` and returns server-rendered result cards.
- Audioteka uses `https://audioteka.com/cz/vyhledavani/?phrase=...` and returns server-rendered HTML with embedded search payloads.
- Audioteka detail pages embed structured audiobook payloads plus referenced long descriptions, so no browser automation is required.
- Kanopa uses `https://www.kanopa.cz/vyhledavani/?string=...` and returns server-rendered Shoptet product cards.
- Kanopa detail pages expose author, narrator, publisher, genres, duration, and long description in static HTML.
- Knihy Dobrovsky uses `https://www.knihydobrovsky.cz/vyhledavani?search=...` and returns server-rendered storefront search results.
- Knihy Dobrovsky search is global storefront search, so the scraper keeps only audiobook detail URLs under `/audiokniha...`.
- Knihy Dobrovsky detail pages expose author, interprets, publisher, publish date, language, duration, categories, and tags in static HTML, with cover and long description available in JSON-LD.
- Kosmas uses `https://www.kosmas.cz/hledej/?query=...&Filters.ArticleTypeIds=3593,14074` and returns server-rendered audiobook result cards.
- Kosmas detail pages expose bibliographic metadata and full annotation text in static HTML, while category metadata is available in embedded analytics payloads.
- Luxor uses the internal `https://www.luxor.cz/api/luigis/search` endpoint, which accepts a UTF-8 JSON request encoded as URL-escaped base64 in the `params` query parameter.
- Luxor search stays scoped to audiobook formats via assortment filters `31` and `20`, and the payload already exposes title, author, publisher, annotation, cover image path, and category metadata.
- Luxor detail pages currently render as an Angular shell without stable server-rendered metadata, so the Luxor scraper intentionally remains search-payload-only for now.
- Megaknihy uses `https://www.megaknihy.cz/vyhledavani?orderby=position&orderway=desc&search_query=...` and returns server-rendered catalog cards.
- Megaknihy search is global storefront search, so the scraper keeps only audiobook-like results using URL, ribbon, title, and embedded analytics-category signals before detail enrichment.
- Naposlech uses the WordPress REST endpoint `https://naposlech.cz/wp-json/wp/v2/audiokniha?search=...&per_page=10`, which returns audiobook-profile results without mixing in articles or topic pages.
- Naposlech detail enrichment uses server-rendered metadata columns on `/audiokniha/...` pages for author, narrator, publisher, genres, duration, cover, and audiobook release year.
- OneHotBook uses `https://onehotbook.cz/search?q=...&type=product` and returns server-rendered result cards with embedded Shopify product JSON.
- OneHotBook detail pages expose richer narrator and specification metadata in static HTML, including duration and release date.
- O2 Knihovna uses `https://www.o2knihovna.cz/audioknihy/hledani?q=...` and returns server-rendered audiobook result cards.
- O2 Knihovna detail pages expose title, author, genres, duration, narrator, publisher, publish year, language, and description in static HTML. Extra narrator names are only added when the summary text explicitly uses a `Čte ...` sentence.
- Palmknihy uses `https://www.palmknihy.cz/vyhledavani$a885-search?query=...` and returns server-rendered result cards where audiobook matches can be filtered via `item-type="audiobook"`.
- Palmknihy detail pages expose publisher, genres, language, duration, and publish year in static HTML. The description block looked inconsistent on at least one live audiobook page, so description enrichment is intentionally conservative for this source.
- ProgresGuru uses the storefront JSON API at `https://progresguru.cz/api/audiobooks?search=...&page=1`.
- ProgresGuru detail enrichment uses `https://progresguru.cz/api/audiobooks/<slug>` for subtitle, duration, publisher, full author list, narrator list, description, and publish date.
- Radioteka uses `https://www.radioteka.cz/hledani?q=...` and returns server-rendered search sections grouped by content type.
- Radioteka audiobook matches can be isolated via `data-provider="croslovo"`, and detail pages expose author, narrator, publisher, year, duration, and description in static HTML.
- Rozhlas uses the public topic page `https://temata.rozhlas.cz/hry-a-cetba` with GET filtering via the `combine` parameter.
- Rozhlas result cards are server-rendered HTML and expose title, teaser, cover, optional tag badges, and either `Délka audia` or `Počet epizod`.
- Rozhlas detail pages on Czech Radio station subdomains embed a `mujRozhlasPlayer` payload with playlist durations and expose performers / production years in shared Drupal credits blocks.

## Runtime Configuration

Application settings:

```env
APP_HOST=0.0.0.0
APP_PORT=8000
LOG_LEVEL=INFO
REQUEST_TIMEOUT_SECONDS=20
AUDIOBOOKSHELF_AUTH_TOKEN=
SCRAPER_USER_AGENT=
ENABLE_ALZA=true
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

All sources are enabled by default. Set any `ENABLE_*` flag to `false` to skip that storefront entirely.

When a source is disabled, it is excluded from the global `/search` results and its source-specific endpoint is not registered.

## Audiobookshelf Setup

Audiobookshelf expects the provider base URL, not `/search`.

1. In Audiobookshelf, open `Settings -> Metadata Tools -> Custom Metadata Providers -> Add`.
2. Set `Typ média` / Media Type to `Book`.
3. Use one of these URLs:

- ABS running locally on the same machine as the provider: `http://localhost:8000`
- ABS running in Docker on the same Docker network as the provider: `http://provider:8000`
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

## Known Limitations

- Alza Audioknihy, Albatros Media Audioknihy, Audiolibrix Czech, Audioteka Czech, Kanopa, Knihy Dobrovský Audioknihy, Kosmas Audioknihy, Luxor Audioknihy, Megaknihy Audioknihy, Naposlech, OneHotBook, O2 Knihovna Audioknihy, Palmknihy Audioknihy, ProgresGuru Audioknihy, Radioteka, and Rozhlas Hry a audioknihy are supported right now.
- Alza currently sits behind a Cloudflare anti-bot challenge from this development environment, so the scraper includes challenge detection and a mobile-host fallback, but live availability still depends on the network environment where the provider runs.
- Albatros Media search is global storefront search, so the scraper applies audiobook-only filtering heuristics to drop obvious non-audiobook matches.
- Audiolibrix still relies on HTML parsing because no stable full search JSON endpoint was identified.
- Audioteka search and detail parsing relies on embedded Next.js payloads, so payload-shape changes may require updates.
- Kanopa search cards do not expose author metadata, so author-aware ranking becomes more accurate after detail enrichment of the top matches.
- Knihy Dobrovsky search is global storefront search, so the scraper filters result cards down to audiobook detail URLs and depends on detail enrichment for publisher, narrator, duration, and long description.
- Kosmas search works best when the upstream request contains the title only, so the scraper intentionally keeps author matching in the provider-layer ranking instead of the Kosmas query string.
- Kosmas currently exposes misleading canonical `audioknihy/?query=...` URLs, but the reliable working search response comes from the filtered `/hledej/` route that the scraper uses.
- Luxor detail pages are currently client-rendered shells, so narrator, duration, language, and published year are only returned when Luxor's search payload exposes them. The scraper uses audiobook assortment filters plus product-type filtering to keep results scoped to audiobook formats.
- Megaknihy search is global storefront search and can return print books, ebooks, or other media for the same title, so the scraper uses conservative audiobook-only heuristics and benefits most from exact title queries.
- Naposlech search uses the dedicated `wp/v2/audiokniha` endpoint, but author, narrator, publisher, duration, and audiobook release year are exposed on the detail page rather than the search payload, so author-aware ranking gets more accurate after detail enrichment.
- OneHotBook search parsing relies on embedded Shopify product JSON inside server-rendered result cards, and detail enrichment relies on the current product/specification page layout.
- O2 Knihovna search cards do not show author or language directly, so author-sensitive ranking depends on detail enrichment for shortlisted matches.
- O2 Knihovna detail pages sometimes display only the first narrator as a dedicated link; additional narrators are only inferred when the summary text explicitly contains a `Čte ...` sentence.
- Palmknihy description enrichment is intentionally disabled for now because live inspection found at least one audiobook detail page with a mismatched description block and mismatched JSON-LD description.
- ProgresGuru relies on first-party storefront JSON endpoints under `/api/audiobooks`, and some multi-author titles only expose the full author list after detail enrichment.
- Radioteka search cards do not consistently expose author names, so author-aware ranking becomes more accurate after detail enrichment for the top exact-title candidates.
- Rozhlas detail pages mix single-audio articles and multi-work serial pages. The scraper therefore stays conservative when the page-level author or production year is ambiguous and falls back to title-only upstream search if a combined title+author query over-filters.
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
