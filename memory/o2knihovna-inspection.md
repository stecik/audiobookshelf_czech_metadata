# O2 Knihovna inspection

Date: 2026-03-16

## Search

- Homepage search toolbar submits `GET /hledani?q=...&typeId=2`.
- The audiobook-only results page resolves to `GET /audioknihy/hledani?q=...`.
- Search result cards are server-rendered under `#snippet--itemsList .list-item`.
- Each card exposes a detail URL, title, and cover image.

## Detail page

- Detail pages are server-rendered at `/audioknihy/<id>`.
- Stable selectors observed:
  - title: `.detail--audiobook h1`
  - author links: `.detail--audiobook .subtitle a`
  - genres: `#tags .tags__in`
  - metadata line: `.textPart > p`
  - long description: `.collapse__content`
  - cover image: `.detail__cover img`
- Metadata line includes `Délka`, `Interpret`, `Vydavatel`, `Vydáno`, and `Jazyk`.

## Notes

- The full search results page does not show author names directly.
- The AJAX autocomplete response does show author names, but only for a short preview list.
- Some detail pages visibly link only the first narrator even when the summary text ends with a clearer `Čte ...` sentence that lists the full cast.
- Safe implementation chosen:
  - use `/audioknihy/hledani` for server-rendered discovery
  - enrich shortlisted matches from detail pages
  - only add extra narrators when the summary text explicitly uses `Čte` or `Čtou`
