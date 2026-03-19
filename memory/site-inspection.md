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

# Luxor Site Inspection

Date: 2026-03-16

## Confirmed search path

- The public `https://www.luxor.cz/c/10726/audioknihy` route is an Angular shell and is not useful on its own for static scraping.
- The Luxor storefront uses the first-party `https://www.luxor.cz/api/luigis/search` endpoint for search, with the request encoded as URL-escaped base64 of UTF-8 JSON under the `params` query key.
- Live inspection confirmed the request serializer is effectively `encodeURIComponent(base64(JSON.stringify(payload)))`.

## Search payload structure

- Search results live at `payload.products.products`, with the useful product data in each item's first `variants[0]` object.
- Audiobook download variants use product type `017`, and audiobook CD variants use `022`.
- Adding assortment filters `31` (`Audioknihy ke stažení`) and `20` (`Audioknihy na CD`) reduces search noise substantially while keeping the expected audiobook matches for `1984`.
- The search payload already exposes title, subtitle, producer name, author list, fallback `staticAuthor`, annotation text, image path, `seoUrl`, category breadcrumbs, nearest category, and occasional `releaseDate`.

## Supporting startup config

- Luxor's startup config from `GET /api/lang?dcb=https%3A%2F%2Fwww.luxor.cz` exposes `ImageServer=https://img.luxor.cz`.
- Cover thumbnails work via paths like `https://img.luxor.cz/suggest/222/351/<imagePath>`.

## Detail-page reliability

- Live detail URLs such as `https://www.luxor.cz/v/1963003/1984` currently return only the Angular shell HTML from static requests.
- The inspected shell response did not include stable server-rendered title, narrator, duration, or structured product JSON.
- Current Luxor implementation should therefore stay conservative and rely on the search payload instead of attempting fragile detail-page enrichment.

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

# Megaknihy Site Inspection

Date: 2026-03-16

## Confirmed search path

- The public storefront search form submits a GET request to `https://www.megaknihy.cz/vyhledavani`.
- The working search parameters are `orderby=position`, `orderway=desc`, and `search_query=<title>`.
- Live inspection showed that title-only upstream queries are more predictable than mixing author text into the Megaknihy search string, so author matching is left to provider-layer ranking.

## Search result structure

- Search results are server-rendered under `#product_list > li.ajax_block_product`.
- Result title links render in `h2 a[title]`, and the `title` attribute avoids storefront prefixes such as `E-kniha:`.
- Product IDs are available on the wishlist control via `data-product-id`.
- Search pages also embed a `var gtm = {...}` analytics payload containing product IDs, category names, author arrays, and the `manufacturer` value.
- Megaknihy search is not audiobook-only, so audiobook filtering needs multiple signals. The current scraper keeps results when at least one strong audio signal is present, such as:
  - detail URLs under `/audioknihy/`
  - `CD / DVD` ribbons on the result card
  - audio-oriented title markers like `audiokniha`, `CDmp3`, or `Čte ...`
  - embedded analytics categories such as `Audioknihy`, `Zvukové`, or `Mluvené slovo`
- Ebook ribbons such as `E-kniha` are explicitly excluded.

## Detail page structure

- Detail pages are server-rendered and include a `Product` JSON-LD block with `sku`, `image`, `name`, and rich HTML `description`.
- The static detail table under `#product_details li` exposes `Výrobce`, `Rok vydání`, `Jazyk`, `Vazba`, and `EAN`.
- Product tags render in `#product-tags-cont .product-tag` and provide usable genre hints after filtering out generic media tags plus author, publisher, and title tags.
- Narrator data is not consistently exposed in a dedicated field, but some titles explicitly include narrator text inside the title, for example `(Čte Lukáš Hlavica)`.

## Reliability notes

- Because search is global storefront search, exact title queries perform best and reduce noise from print books, ebooks, and other media.
- Detail pages provide reliable description, cover, publisher-like manufacturer, language, and publish-year data, but duration is not consistently exposed on the inspected page, so the scraper leaves it unset when absent.

# Naposlech Site Inspection

Date: 2026-03-16

## Confirmed search path

- The homepage advertises a `SearchAction` target of `https://naposlech.cz/?s={search_term_string}`.
- The cleaner implementation path is the WordPress REST endpoint `https://naposlech.cz/wp-json/wp/v2/audiokniha?search=...&per_page=10`, which returns only audiobook-profile entries for the custom `audiokniha` post type.
- Live inspection showed that title-only upstream queries are the safest default. Author names are exposed reliably on detail pages, not in the API search payload.

## Search result structure

- REST search results are JSON arrays of `audiokniha` objects with `id`, `link`, `title.rendered`, `excerpt.rendered`, `featured_media`, and `zanr-audioknih`.
- The API avoids the HTML search page's mixed result set of audiobook profiles, articles, topics, and other content types.
- Search result descriptions can be taken from `excerpt.rendered`, which is already short and audiobook-specific.

## Detail page structure

- Detail pages are server-rendered and do not require JavaScript execution.
- Title selector: `h1.elementor-heading-title`
- Cover selector: `.elementor-widget-theme-post-featured-image img`, with `meta[property='og:image']` as a fallback.
- Long description selector: `.elementor-widget-theme-post-content .elementor-widget-container`
- Rich metadata rows render in `.npslch-columns .pair` blocks.
- Confirmed labels on the live `1984` page: `Délka`, `Autor`, `Interpret`, `Rok vydání`, `Vydavatel`, and `Žánry audioknih`.

## Reliability notes

- The REST search payload does not expose author, narrator, publisher, duration, or audiobook release year as first-class fields.
- Those fields are reliably available on the detail page, so the current implementation is API-first for discovery and detail-page HTML parsing for enrichment.
- The long description block includes a trailing `text: <publisher>` attribution that should be stripped from the returned description while still allowing it to serve as a conservative publisher fallback when the dedicated metadata field is absent.

# Kanopa Site Inspection

Date: 2026-03-16

## Confirmed search path

- The public storefront search form submits a GET request to `https://www.kanopa.cz/vyhledavani/?string=...`.
- Live inspection confirmed that combined title-plus-author queries such as `Hypotéza zla Donato Carrisi` still return the expected product match.

## Search result structure

- Search results are server-rendered Shoptet product cards under `#products .p[data-micro="product"]`.
- Result title links render as `a.name[data-micro="url"]`.
- Product IDs are available on the card wrapper via `data-micro-product-id`.
- Covers can be read from the result image `data-micro-image` attribute.
- Search cards expose visual flags such as `Tip` and `MP3`, but do not expose author or narrator metadata.

## Detail page structure

- Detail pages are server-rendered and do not require JavaScript execution.
- Title selector: `.p-detail-inner-header h1`
- Long description selector: `#description .basic-description`
- Cover selector: `.p-main-image img`
- Extended metadata rows render under `.extended-description .detail-parameters tr`.
- Confirmed labels on the live `Hypotéza zla` page: `Autor`, `Délka`, `Interpret`, `Série`, `Žánr`, `ISBN`, `Překlad`, and `Vydavatel`.

## Reliability notes

- The inspected detail page did not expose an explicit publish-year field, so the current scraper only maps a year when a detail row such as `Rok vydání` or `Datum vydání` is present.
- Because search cards lack author metadata, upstream author filtering is best-effort and final author-aware ranking improves after detail enrichment.

# Radioteka Site Inspection

Date: 2026-03-16

## Confirmed search path

- The public storefront search form submits a GET request to `https://www.radioteka.cz/hledani?q=...`.
- Search responses are server-rendered HTML grouped by content type such as `Mluvené slovo` and `Noty`.

## Search result structure

- Audiobook cards render as `article.item` blocks.
- Audiobook matches are reliably identifiable by the add-to-cart control having `data-provider="croslovo"`.
- Search cards expose stable `data-ident`, `data-title`, `data-brand`, and `data-categories` attributes on the add-to-cart button.
- Title and detail link are available under `.item__tit a`, and cover images use `.item__img img` with `data-src`.

## Detail page structure

- Detail pages are server-rendered and do not require JavaScript execution.
- Title selector: `h1.detail__tit`
- Description selector: `.detail-center-col .detail__desc`
- Metadata is stored in repeated `dl.detail__info` blocks containing labels for `Rok vydání`, `Vydavatel`, `Celková délka`, `Autor knihy`, and `Interpret slova`.
- Cover images are available in `meta[name='og:image']` and as a fallback under `.detail-left-col img`.

## Reliability notes

- Search cards do not consistently expose author names, so the scraper keeps the upstream query title-only and relies on detail enrichment for top-ranked exact-title matches.
- Duration is exposed as `HH:MM:SS`, which required a shared parser improvement to normalize the value into minutes.

# Knihy Dobrovsky Site Inspection

Date: 2026-03-16

## Confirmed search path

- The public storefront search form submits a GET request to `https://www.knihydobrovsky.cz/vyhledavani?search=...`.
- Search responses are server-rendered HTML and do not require JavaScript execution.

## Search result structure

- Result cards render as `li[data-cy="productPreviewList"]`.
- Global search mixes print books, ebooks, and audiobooks, so audiobook filtering is required.
- Audiobook detail URLs use `/audiokniha...` paths such as `/audiokniha-mp3/1984-343519887`.
- Card title selector: `h3.title .name`
- Card author selector: `.content .author-name`
- Card cover selector: `h3.title img`
- Non-Czech variants can show a language icon under `.product-language__inner`, for example `ico-sk`.

## Detail page structure

- Title selector: `h1 [itemprop="name"]`
- Primary author / narrator groups render in `.annot.with-cols .author .group`.
- Product parameters render in static HTML under `.box-book-info .item dl`.
- Sidebar metadata render in `.box-params > dl`, including `kategorie`, `Témata`, and `interpreti`.
- Useful labels confirmed on a live audiobook page: `Nakladatel`, `datum vydání`, `jazyk`, and `Délka`.
- Detail pages also embed a `Product` JSON-LD block with cover image, long description, publisher brand, and category path.

## Reliability notes

- Search is storefront-wide rather than audiobook-only, so the scraper should keep only `/audiokniha` detail URLs.
- `data-productinfo` on result cards looks JavaScript-like rather than strict JSON, so DOM parsing is the safer first-choice implementation path for this source.

# Rozhlas Site Inspection

Date: 2026-03-16

## Confirmed search path

- The topic page `https://temata.rozhlas.cz/hry-a-cetba` exposes a server-rendered GET filter on the same URL.
- The query input uses the `combine` parameter, for example `https://temata.rozhlas.cz/hry-a-cetba?combine=skořápka`.
- Live checks showed that some title-plus-author combinations can over-filter to zero results, so the scraper falls back to title-only upstream search when a combined query misses.

## Search result structure

- Result cards render under `.b-008d__list > .b-008d__list-item`.
- Card titles live in `.b-008d__subblock--content h3 a`, teaser text in `.b-008d__subblock--content p`, and metadata rows in `.b-008d__meta-line`.
- Search cards expose either `Délka audia`, `Autor`, or `Počet epizod`.
- Genre-like badges render as `.b-008d__block--image .tag span`.
- Covers are exposed through `picture source[data-srcset]`, while the `img` element is usually just a lazy-load placeholder.

## Detail page structure

- Detail pages live on multiple Czech Radio station subdomains such as `junior.rozhlas.cz`, `vltava.rozhlas.cz`, and `dvojka.rozhlas.cz`.
- Pages expose a shared embedded `mujRozhlasPlayer` payload in `div.mujRozhlasPlayer[data-player]`.
- The player payload contains poster artwork and a `playlist` array with per-episode durations, which works for both single-audio pages and multi-episode serial pages.
- Credits are stored in a shared Drupal block under `.asset.a-002 .a-002__row`, where performer names and production years can be parsed from label/value lines.
- Multi-work serial pages often expose author headings inside the credits block as `<strong>Author: Title</strong>`.

## Reliability notes

- Detail-page `dataLayer` is useful for bundle/type detection and genre hints, but `contentAuthor` is not always the literary author. On serial pages it can instead represent an editor or preparer, so author extraction must stay conservative.
- Multi-work serial pages can contain mixed production years, so the scraper uses a single `publishedYear` only when the page is unambiguous or falls back to the page publication year.

# Alza Site Inspection

Date: 2026-03-16

## Confirmed entry points

- Category landing page: `https://www.alza.cz/media/audioknihy/18854370.htm`
- Storefront search route: `https://www.alza.cz/search.htm?exps=...`
- Mobile fallback route: `https://m.alza.cz/search.htm?exps=...`

## Search result structure

- Product detail URLs use `/media/<slug>-d<id>.htm`.
- Search and category result cards expose audiobook summary text in human-readable lines such as `Audiokniha MP3 - autor ...`, sometimes with an extra description segment before `autor`.
- Order codes render as `Objednací kód: ...`, which is useful as a fallback identifier if the detail id is missing.
- A text-first parser is safer here than brittle CSS selectors because Alza reuses generic product-search markup.

## Detail page structure

- Detail pages expose enough metadata through generic HTML primitives to avoid source-specific selectors:
  - `<h1>` for the title
  - Open Graph tags for canonical URL and cover image
  - visible labeled fields such as `Autor`, `Čte`, `Interpret`, `Jazyk`, `Rok vydání`, `Délka`, and `Kategorie`
  - publisher hints through `Vše od <publisher>` or the `Informace o výrobci` block

## Reliability notes

- Raw HTTP requests from this development environment currently receive a Cloudflare `Just a moment...` challenge on both desktop and mobile hosts.
- The implementation therefore detects challenge pages explicitly, logs them as upstream unavailability, and keeps the parser text-oriented so the source can still work in environments where Alza allows the requests through.

# Databaze knih Site Inspection

Date: 2026-03-19

## Confirmed search path

- The homepage search form submits a GET request to `/search` with the `q` parameter.
- Book-only search works through `https://www.databazeknih.cz/search?in=books&q=...`.
- Live inspection showed that title-only upstream queries are more reliable than mixing title and author text, so author filtering should stay in provider-layer ranking.

## Search result structure

- Result cards render server-side as `p.new` blocks.
- Book links are exposed as `a.new[type='book']`.
- Search metadata is available in `span.pozn`, usually as `YEAR, Author`.
- Covers are available under `picture img`.

## Detail page structure

- Detail pages live under `/prehled-knihy/<slug>-<id>`.
- Title selector: `h1.oddown_five`, but the heading includes a trailing `přehled` label that must be stripped.
- Author links render in `.orangeBoxLight .author a`.
- Description selector: `#bdetail_rest p.new2.odtop`.
- Genre links render under `.detail_description a.genre`.
- Publisher and publish year are available inside `.detail_description`.
- Pages also expose a JSON-LD `Book` payload with `name`, `author`, `publisher`, `description`, `image`, and `inLanguage`.

## Reliability notes

- Databaze knih is not an audiobook storefront. It is best treated as a metadata fallback source for custom audiobooks that have no official audiobook listing.
- Because the site is books-only, the source defaults to disabled in global `/search` but remains available through `/databazeknih/search`.
