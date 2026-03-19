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

Build the static OpenAPI docs site:

```bash
uv run python scripts/build_openapi.py
```

## Configuration Reference

Application settings:

```env
APP_HOST=0.0.0.0
APP_PORT=8000
LOG_LEVEL=INFO
REQUEST_TIMEOUT_SECONDS=20
SCRAPER_TIMEOUT_SECONDS=8
AUDIOBOOKSHELF_AUTH_TOKEN=
SCRAPER_USER_AGENT=
```

`REQUEST_TIMEOUT_SECONDS` is the timeout for a single outbound HTTP request. `SCRAPER_TIMEOUT_SECONDS` is the overall timeout for one scraper search or one detail-enrichment task.

## OpenAPI Docs

The API exposes the standard FastAPI OpenAPI endpoints at runtime:

- `GET /openapi.json`
- `GET /docs`

To generate the static Swagger site for GitHub Pages:

```bash
uv run python scripts/build_openapi.py
```

This writes:

- `docs/openapi.json`
- `docs/index.html`
- `docs/.nojekyll`

The generated `docs/index.html` loads `./openapi.json` with Swagger UI from a CDN, so it can be published directly from the repository `docs/` directory on GitHub Pages without hardcoding the repo name.

## How Audiobookshelf Uses It

Audiobookshelf sends a search request to the provider with a required `query` and an optional `author`. The provider looks up the source site, ranks results, and returns them as `{"matches": [...]}` so ABS can populate book metadata.

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
"matches": [
        {
            "title": "1984",
            "author": "George Orwell",
            "narrator": "David Novotný",
            "publisher": "OneHotBook",
            "publishedYear": "2021",
            "description": "„Svoboda je svoboda říkat, že dvě a dvě jsou čtyři. Pokud je toto zaručeno, všechno ostatní už vyplyne samo.“ Ve zbídačelém Londýně na území superstátu Oceánie se v dubnu 1984 úředník Ministerstva pravdy Winston Smith přiměje vzepřít. Už se mu zajídají pěstěná stádnost i technika normopsychu , využívané coby hráz proti občanskému vzdoru. Pochyby začne potají svěřovat deníku i přesto, že každý pohyb v téhle chmurné zemi monitorují telestěny Velkého bratra. Krutovláda jedné Strany navíc s Winstonovým přispěním z dějin cíleně vymazává veškeré vzpomínky na dobu před Revolucí, neboť hodlá pomocí znetvořeného jazyka zvaného neolekt obyvatelstvo opanovat na těle, v duchu i v srdci – ryzí, nezměrnou, totalitní mocí. Zbývá aspoň jiskřička naděje na svobodu? Nicméně i Winstonova láska k Julii a krimistyk s ní představují protestní akt, takže za oběma asi brzy spadne klec. A pak…? Pak už jen drtivé vyústění znamenitě propracované antiutopie o nelidském režimu, která téměř tři čtvrtě století vévodí svému literárnímu žánru. Vizionářský román v roce 1984 zfilmoval režisér Michael Radford s Johnem Hurtem v hlavní roli a s hudbou od skupiny Eurythmics. Snímek byl vyhlášen nejlepším britským filmem sezony. „Útlak osobitosti, jaký zažil Winston, trvá ve stále nových formách: s tím, jak se na nás valí zprávy a jak se hned popírají, překrucují, přepisují. Orwella by to rozhodně nepřekvapilo, avšak dopad toho všeho vystihl nejlíp on.“ – The New York Times (2017)",
            "cover": "https://onehotbook.cz/cdn/shop/files/George_Orwell_1984_audio_OneHotBook_ctverectextura.jpg?v=1763901069",
            "genres": [
                "Moderní klasika",
                "Sci-fi",
                "Sci-fi a fantasy",
                "Světová literatura"
            ],
            "language": "cs"
        }
]
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
