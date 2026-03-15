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
