# Audiolibrix Site Inspection

Date: 2026-03-15

## Confirmed search path

- Homepage search form submits a plain GET request to `/cs/Search/Results`.
- Example working query: `/cs/Search/Results?query=1984`

## Search result structure

- Audiobook results render as static HTML inside `.alx-audiobook-list-grid`.
- Each result card is an `article.alx-audiobook-list-item`.
- Title link selector: `h2 a.audiobook-link`
- Author links selector: `dd.alx-author.mb-0 a`
- Narrator links selector: `dd.alx-author.small a`
- Cover selector: `figure img`
- Detail URLs use `/cs/Directory/Book/<id>/...`

## Detail page structure

- Title selector: `h1[itemprop="name"]`
- Metadata definition list: `dl.alx-metadata`
- Annotation card title: `Anotace`
- Annotation body selector: `article.card .card-body`
- Language, publisher, year, genre, and duration are present in the definition list for detail enrichment.

## Internal API check

- The page exposes a `search-results-info` JSON script with counts only.
- The live JS bundle did not reveal a stable internal JSON endpoint for full book result payloads.
- Current implementation remains HTML-first with the scraper abstraction kept ready for a future API path.

# Audioteka Site Inspection

Date: 2026-03-15

## Confirmed search path

- The public search route resolves to `https://audioteka.com/cz/vyhledavani/?phrase=...`.
- The frontend route manifest exposes `/cz/search/...`, which is localized to `/cz/vyhledavani/...`.
- Combined title-and-author phrases still return useful results.

## Search result structure

- The response is server-rendered HTML from Next.js.
- Search result data is embedded in the page's flight payload under an escaped `products` object.
- Each product entry includes at least `id`, `name`, `image_url`, `description` (author string), and `slug`.
- Result detail URLs use `/cz/audiokniha/<slug>/`.

## Detail page structure

- Audiobook detail pages embed an escaped `audiobook` object in the Next.js flight payload.
- The embedded audiobook payload explicitly includes `name`, `published_at`, `duration`, `tracks_duration_in_ms`, `content_language`, and embedded author, narrator, publisher, and category lists.
- Long descriptions are referenced via `$27` / `$28`-style tokens, with the actual strings pushed in subsequent script tags.

## Internal API check

- The site exposes stable public detail links and embedded structured payloads in HTML.
- No separate public JSON search endpoint was required for v1 because the search page already returns the needed data in a static response.

# OneHotBook Site Inspection

Date: 2026-03-15

## Confirmed search path

- The public product search route resolves to `https://onehotbook.cz/search?q=...&type=product`.
- Search results render server-side and include one product card per match.

## Search result structure

- Result cards render as `.product-grid-item`.
- Each card includes a hidden `.quick_shop .json.hide` node containing Shopify product JSON.
- The embedded product payload includes `id`, `title`, `handle`, `description`, `published_at`, `vendor`, `tags`, `featured_image`, and `images`.
- Author, narrator, and genre values are encoded in product tags such as `Autor_*`, `Interpret_*`, and `Žánr_*`.

## Detail page structure

- Product detail pages expose explicit metadata in static HTML.
- Title selector: `h1[itemprop="name"]`
- Author and narrator blocks render under `#product-info .author`.
- Description block selector: `.short-description`
- Specification tab content includes `Délka nahrávky` and `Datum vydání`.
- Example detail page for `1984` includes richer narrator data than the search payload, so detail enrichment is worthwhile for top-ranked matches.

## Internal API check

- Shopify predictive search is enabled on the storefront, but the public search page already returns the complete embedded product payload needed for reliable parsing.
- A separate JSON search endpoint was not required for this implementation.
