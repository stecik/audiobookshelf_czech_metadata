# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [v1.0.2] - 2026-03-19

### Added

- OpenAPI docs
- databazeknih endpoint
- monitoring action

### Fixed

- alza endpoint

### Changed

- ENABLE_ variables now only affect the global search

## [v1.0.1] - 2026-03-16

### Added

- Added `SCRAPER_TIMEOUT_SECONDS` environment configuration with a default of 8 seconds.
- Added provider-level timeout tests covering partial timeout and all-scrapers-time-out behavior.
- Postman collections.

### Changed

- Limited each scraper search and detail-enrichment task to a single configurable time budget so slow sources no longer block faster ones.
- Updated the runtime documentation in `README.md`, `DEVELOPMENT.md`, and `.env.example` to describe the scraper timeout behavior.

## [v1.0.0] - 2026-03-16

### Added

- Added source-specific provider endpoints alongside the global Audiobookshelf-compatible `/search` endpoint.
- Added support for additional Czech audiobook sources including OneHotBook, Albatros Media, Kosmas, Palmknihy, and ProgresGuru.
- Added parallel scraping execution to reduce end-to-end search latency.
- Added Docker build automation
