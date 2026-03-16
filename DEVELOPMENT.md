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
