# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Show GitHub as an implicit (always-on) package in the discovery results when adding a project

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
