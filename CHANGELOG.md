# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.8] - 2026-04-10

### Added

- Prometheus business metrics: user count, project count, package mappings (total + per registry), snapshot counts per table, and user-project distribution gauges on `/metrics`
- Business metrics refresh cached for 5 minutes via `cachetools.TTLCache`

## [0.1.7] - 2026-04-09

### Changed

- Collector resilience: connection retries with backoff on all HTTP clients, GitHub stats backoff (2/5/10/15s), scheduled collections retry failed collectors after 5/10 min
- Distro collector timeout increased to 120s for slow APIs (Launchpad)

### Fixed

- NuGet collector and discovery returning 404 — search API moved to azuresearch-usnc.nuget.org

## [0.1.6] - 2026-04-07

### Added

- Show GitHub as an implicit (always-on) package in the discovery results when adding a project
- Top nav links: "my projects" (logged-in) and "leaderboard" with active page highlighting
- Vertical separator between logo and nav links for visual grouping
- Logged-out nav shows dimmed "my projects" placeholder to prevent layout shift
- Cache-busting version query string on CSS and favicon static assets

### Changed

- Add-project page: renamed "discover packages" button to "continue"
- Add-project info panel: added Go, Maven, NuGet, Packagist to registries list
- Add-project info panel: updated distro source count from 25+ to 30+

### Fixed

- Package collectors (PyPI, npm, etc.) skipped entirely when GitHub token is missing — now only GitHub/traffic collectors require a token
- Chart dots (showSymbol) missing on issues, pull requests, and release cadence charts
- User-Agent version hardcoded as 0.1.0 — now derived from package metadata

## [0.1.5] - 2026-04-07

### Fixed

- Logfmt key_order using wrong key names (`log_level`/`logger_name` → `level`/`logger`)

## [0.1.4] - 2026-04-07

### Added

- Landing page for logged-out visitors: intro text, leaderboard preview, and link to public demo dashboard
- Public project dashboards with toggle in project edit form
- Leaderboard preview on landing page (top 5 projects by reach, linked to GitHub)
- Space Grotesk font for body text (IBM Plex Mono remains for nav/stats/code)
- GitHub repo link in footer and about page

### Changed

- Logging output switched from JSON to logfmt with fixed key order
- Discovery errors log a one-line warning instead of full traceback
- Badge markdown links to homepage instead of private project detail
- Footer links styled with visible color instead of default browser blue

### Fixed

- Guides sidebar left-alignment and desktop/mobile visibility
- GitHub snapshot insert failing with NOT NULL violation when search API returns no data
- Discovery `except` clause using comma syntax instead of tuple (only caught first exception type)

## [0.1.3] - 2026-04-07

### Fixed

- Mobile responsiveness across all pages (dashboard, leaderboard, guides, nav, footer)
- Dev-login route queries by `github_id` instead of `github_username`
- Discovery concurrent session bug: each task gets its own niquests `AsyncSession`
- `Cache-Control: no-store` now actually set on HTML/redirect responses

## [0.1.2] - 2026-04-07

### Fixed

- Browser showing stale HTML after login/logout (added `Cache-Control: no-store` to HTML responses)
- Discovery and GitHub dependents collector using `follow_redirects` instead of `allow_redirects` (niquests API)
- Post-login redirect defaulting to `/projects` instead of `/`
- Unnecessary `uv run` overhead on container startup

## [0.1.1] - 2026-04-07

### Fixed

- OAuth redirect URI building as `http://` behind reverse proxy (added `--proxy-headers` to uvicorn)

## [0.1.0] - 2026-04-07

Initial release.
