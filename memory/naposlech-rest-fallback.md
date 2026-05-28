# Naposlech REST fallback

- 2026-05-28: Live `https://naposlech.cz/wp-json/wp/v2/audiokniha?search=1984&per_page=10` returns `401` with `{"code":"rest_forbidden","message":"REST API restricted","data":{"status":401}}`.
- Server-rendered search `https://naposlech.cz/?s=1984` still returns result cards in `.uael-post-wrapper`.
- Search page contains mixed content; scraper should keep only cards whose title/detail link includes `/audiokniha/`.
- Current fallback parses title, detail URL, cover, excerpt, genres, and `uael-post-*` ID when present.
