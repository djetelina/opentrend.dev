# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] - 2026-06-11

### Added

- Dynamic `sitemap.xml` listing public pages, packaging guides, and public project dashboards (with last-snapshot `lastmod`); `robots.txt` is now generated, advertises the sitemap, and allows public content to be crawled
- SEO meta tags on every page: description, canonical URL, Open Graph, and Twitter Card
- Dynamic Open Graph / social card images - per-project cards at `/p/{owner}/{repo}/og.png` (public projects only, rendered with Pillow) and a default card at `/og.png`
- Reach-score breakdown on project dashboards: a "?" next to the reach number opens a popup itemizing each scoring component's point contribution (zero contributions hidden)
- Time-range selector on project dashboards (30d / 90d / 180d / 1y), including a new 180d preset
- `BASE_URL` setting for canonical/OG/sitemap absolute links (defaults to `https://opentrend.dev`)

### Changed

- Featured example dashboard on the landing page switched from tofuref to cheznav
- Reach score: the `dependents` term now uses square-root scaling (`sqrt(dependents) × 18`) instead of `log1p(dependents) × 40`, so heavily-depended-on libraries keep scaling up instead of flattening after the first few dependents (apply retroactively with `scripts/backfill_reach.py`)
- Project dashboard time-series charts use a time x-axis instead of a category axis, so gaps between collection dates render proportionally (weekly and release charts unchanged)

### Fixed

- Project dashboard hero and KPIs (reach, stars, packaging) no longer vanish on shorter time ranges when a project hasn't been scanned within the window - current stats now always reflect the latest snapshot, independent of the selected chart window
- GitHub collection no longer crashes with `AttributeError` when the contributor stats API returns `"author": null` for deleted or anonymous accounts
- Top navigation no longer clips the login/account control on narrow mobile screens - the wordmark collapses to the logo mark below the `sm` breakpoint

## [0.1.11] - 2026-04-12

### Changed

- Release download snapshots now only collect assets from the 100 most recent releases instead of all releases, and get total release count cheaply from the Link header - reduces API calls from up to 50 paginated requests to 2
- Daily cleanup job prunes release download snapshots older than 90 days (cumulative counters make older snapshots redundant)
- Project collection schedules now spread across all 1,440 minute-slots per day instead of only 24 hour-slots, reducing rate-limit pressure on upstream APIs
- Catch-up logic on startup: projects whose scheduled slot already passed today without a snapshot are queued immediately, preventing skipped days after deploys
- Collection failures log at warning level with "will retry" on non-final attempts; full stack trace only on the final attempt
- Silenced urllib3 retry warnings for transient connection errors (FD racing) that are handled automatically

## [0.1.10] - 2026-04-12

### Fixed

- Sparkline SVG not spanning full card width
- Homebrew custom tap links on project detail pointed to `user/tap` instead of `user/homebrew-tap`
- Packaging matrix row links could cover the entire screen on mobile due to unreliable `position: relative` on `<tr>` elements

### Removed

- Leaderboard link from footer

## [0.1.9] - 2026-04-10

### Fixed

- `/metrics` endpoint crashing with `AttributeError: 'Request' has no attribute 'scalar'` - Litestar's `before_request` hook doesn't support dependency injection, so the controller now uses a proper `@get()` handler with DI

## [0.1.8] - 2026-04-10

### Added

- Prometheus business metrics: user count, project count, package mappings (total + per registry), snapshot counts per table, and user-project distribution gauges on `/metrics`
- Business metrics refresh cached for 5 minutes via `cachetools.TTLCache`

## [0.1.7] - 2026-04-09

### Changed

- Collector resilience: connection retries with backoff on all HTTP clients, GitHub stats backoff (2/5/10/15s), scheduled collections retry failed collectors after 5/10 min
- Distro collector timeout increased to 120s for slow APIs (Launchpad)

### Fixed

- NuGet collector and discovery returning 404 - search API moved to azuresearch-usnc.nuget.org

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

- Package collectors (PyPI, npm, etc.) skipped entirely when GitHub token is missing - now only GitHub/traffic collectors require a token
- Chart dots (showSymbol) missing on issues, pull requests, and release cadence charts
- User-Agent version hardcoded as 0.1.0 - now derived from package metadata

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
