# Rozhlas API fallback

Date: 2026-05-01

The legacy topic page `https://temata.rozhlas.cz/hry-a-cetba?combine=...` can return an empty Drupal view for titles that still exist in the modern archive. Example: `Skořápka` no longer appears on the legacy topic listing, while `https://api.mujrozhlas.cz/search` returns the episode with remote Drupal id `9602125`.

Implementation note: keep the legacy topic page as the primary source because it still has good curated listing metadata for some terms. If it returns no cards, query `https://api.mujrozhlas.cz/search` with `filter[fulltext][eq]` and `page[limit]`.
