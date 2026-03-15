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

# Albatros Media Site Inspection

Date: 2026-03-15

## Confirmed search path

- The public search route resolves to `https://www.albatrosmedia.cz/hledani/?Text=...`.
- Search result pages are server-rendered HTML and do not require JavaScript execution.

## Search result structure

- Search result cards render under `.product-list .p-l__item`.
- Result title selector: `.p-l-i__title a`
- Result author links selector: `.p-l-i__authors a.author`
- Result cover selector: `.figure__inner img`
- Each result card includes a `data-component-args` JSON blob on the add-to-cart control with `productId`, `productName`, author data, brand name, category name, and EAN.
- Global search is not audiobook-only, so audiobook filtering is required. Current implementation keeps entries whose title or slug clearly indicates `audiokniha`.

## Detail page structure

- Title selector: `.product-top__header h1`
- Author links selector: `.product__author a.author`
- Long description selector: `.p-i__long-anotation .p__text`
- Detail rows render as `.product__param` blocks with label/value pairs.
- Useful labels confirmed on `Podzimní děsy (audiokniha)`: `Žánr`, `Interpret`, `Délka`, `Jazyk`, `EAN`, `Datum vydání`, `Nakladatelství`, `Edice`.

## Internal API check

- No public JSON search endpoint was required because the server-rendered search page already exposes the fields needed for matching and routing to detail pages.
- Detail enrichment is still needed to obtain narrator and duration metadata.

# Kosmas Site Inspection

Date: 2026-03-15

## Confirmed search path

- The reliable audiobook search route is `https://www.kosmas.cz/hledej/?query=...&Filters.ArticleTypeIds=3593,14074`.
- The direct `https://www.kosmas.cz/audioknihy/?sortBy=relevance&query=...` URL currently shows a query-looking URL but can return generic catalog items instead of actual search results.
- Live inspection showed that combining title and author in the upstream query can degrade exact-title relevance, so the scraper should send the title only and let provider-level ranking apply the author boost.

## Search result structure

- Search results render server-side under `#fulltext_articles .grid-item`.
- Result title selector: `.g-item__title a`
- Result author selector: `.g-item__authors a`
- Result cover selector: `.g-item__figure img.img__cover`
- Result teaser selector: `.article__popup-perex`
- Search pages also embed GA4 `view_item_list` payloads containing `item_id`, `item_brand`, and category fields that can be mapped to publisher and genres.

## Detail page structure

- Title selector: `h1.product__title`
- Author / narrator blocks render in repeated `.product__authors` sections.
- Full annotation text is stored in `.product__annotation .toggle-text[data-holder]`.
- Bibliographic data renders in static HTML under `dl.product__biblio`.
- `Popis` includes format, duration, and language in one string such as `1× CD MP3, délka 11 hod. 45 min., česky`.
- Detail pages also embed `window.ga4items` with category fields usable as genre hints.

## Internal API check

- No public JSON search API was required for v1 because the audiobook search page is server-rendered and already contains the needed result data.
- No browser automation is required for the current Kosmas implementation.

# ProgresGuru Site Inspection

Date: 2026-03-15

## Confirmed search path

- The Nuxt route bundle for `/audioknihy` calls `GET /api/audiobooks` with query params taken from the storefront URL.
- The public search parameter is `search`, for example `/api/audiobooks?search=okamžitá&page=1`.
- The storefront also supports filter params like `authors`, `categories`, `interprets`, `publishers`, `sortBy`, `tag`, and `lang`, but only `search` was needed for this scraper.

## Search result structure

- Search responses are JSON with top-level `audiobooks`, `last_valid_page`, and `total`.
- Each audiobook result includes `id`, `slug`, `name`, `publish_date`, `lang`, `image`, `image_alt`, `category`, `tags`, `author`, and `interpret`.
- The search payload usually exposes only one `author` and one `interpret` object directly, so multi-author titles are completed during detail enrichment.

## Detail response structure

- The Nuxt detail route bundle calls `GET /api/type/<slug>` and then `GET /api/audiobooks/<slug>` for audiobook items.
- Detail responses expose a full `audiobook` object with `name`, `name_sub`, `length`, `description`, `publish_date`, `image`, `categories`, `tags`, `publisher`, `authors`, and `interprets`.
- `length` is already in minutes and can be mapped directly to the ABS duration field.

## Internal API check

- The storefront uses first-party JSON endpoints instead of requiring HTML scraping for this source.
- `GET /api/structured-data/product/<slug>` also exists, but the audiobook detail endpoint already exposes the richer metadata we need for v1.

# Palmknihy Site Inspection

Date: 2026-03-15

## Confirmed search path

- The public storefront search form submits a GET request to `https://www.palmknihy.cz/vyhledavani$a885-search?query=...`.
- Search result pages are server-rendered HTML and expose audiobook items without JavaScript execution.

## Search result structure

- Result cards render under `#js-catalog-products-listing .selling-card`.
- Audiobook matches are safely identifiable with `item-type="audiobook"`, which lets the scraper drop same-title ebook and print matches.
- Each audiobook card includes a `.gtm-data` node with stable `data-item-id`, `data-author`, `data-book-language`, `data-publisher`, `data-year-published`, and category fields.
- Title links point directly to `/audiokniha/<slug>-<id>` detail pages.

## Detail page structure

- Title selector: `h1[data-cy="detail-title"]`
- Author links selector: `.product-detail__authors [info-type='author']`
- Parameter rows render under `.product-detail__parameters > li`.
- Useful detail labels confirmed on live audiobook pages: `Nakladatel`, `Kategorie`, `Jazyk`, `Délka`, `Ean mp3`, and `ISBN`.
- Publish year is available in the static `.shop__extensions` block.

## Reliability notes

- Live inspection showed one audiobook detail page whose description block and JSON-LD description appeared to belong to a different title.
- The current implementation therefore enriches Palmknihy results with publisher, genres, language, duration, and publish year, but intentionally leaves `description` unset until a more reliable source is identified.
