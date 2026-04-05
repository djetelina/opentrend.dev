# OpenTrend

Open source project metrics dashboard.

## Stack

- **Python 3.14**, Litestar (async), SQLAlchemy async, Jinja2 + HTMX, Apache ECharts
- **PostgreSQL** (plain, no extensions)
- **uv** for package management, **pytest** for tests, **ruff** for linting/formatting
- **prek** for pre-commit hooks (ruff + pytest)
- **Docker Compose** for local dev, **GHCR** container images for production

## Running

```bash
cp .env.example .env  # edit with your keys
docker compose up --build
# or locally: uv run litestar --app opentrend.app:create_app run
```

Authentication requires GitHub OAuth.

In development, `src/` is mounted into the container — the app runs with `debug=True` which enables the reloader, so all code changes (Python, templates, static) are live without rebuilding. A container rebuild is only needed for dependency changes.

## Structure

- `src/opentrend/` — app code
  - `app.py` — Litestar app factory with lifespan (migrations + scheduler)
  - `collectors/` — one per source (PyPI, npm, crates.io, RubyGems, Go, Maven, NuGet, Packagist, AUR, Chocolatey, distros), all use `upsert_package_snapshot` from `base.py`
  - `scheduler/jobs.py` — APScheduler, staggered by project ID hash
  - `routes/` — home, auth, projects CRUD, dashboard
  - `services/` — project CRUD, dashboard queries, package discovery
  - `templates/` — Jinja2 with HTMX
- `alembic/` — migrations (sync engine in env.py to avoid async-in-async)
- `tests/` — mirrors src structure

## Docker Compose

- The compose service is called `opentrend`, not `app`. Use `docker compose exec opentrend ...`.
- PostgreSQL is the `postgres` service. Access via `docker compose exec postgres psql -U opentrend opentrend`.
- A container rebuild (`docker compose up --build`) is needed for dependency or Dockerfile changes. Code changes hot-reload in dev.
- Alembic commands that need the DB must run inside the container or with `DATABASE_URL` pointing at compose postgres.

## Key Patterns

- Collectors write snapshots, web reads them. No coupling.
- Snapshot tables use unique constraints (e.g. `(project_id, date)` or `(package_mapping_id, date)`) — collectors must upsert.
- Litestar form data uses `form.getall()` not `getlist()`.
- Dashboard URLs use repo slugs: `/p/{owner}/{repo}`
- Debug mode is controlled by the `DEBUG` env var (default: off). Set `DEBUG=true` for development.
- The `/data` page (`templates/data.html`) documents all collected data, reach score formula, and API limitations. **It must stay in sync** — any new data source, collector, metric, or removal must be reflected on this page.
- All JS/font assets are vendored in `static/vendor/` — no external CDNs. Tailwind CSS is built with the standalone CLI (`tailwindcss` binary) and output to `static/css/tailwind.css`. The Dockerfile downloads the CLI and builds during image creation. After changing templates with new Tailwind classes, rebuild CSS locally: `./tailwindcss -i src/opentrend/static/css/tailwind-input.css -o src/opentrend/static/css/tailwind.css --minify`
- CSP is set to `'self'` only (plus `avatars.githubusercontent.com` for img-src). Adding external resources requires updating CSP in `app.py`.
- Litestar CSRF validates via `x-csrftoken` header (HTMX) or `_csrf_token` form field (regular forms). Both must be present for their respective use cases. CSRF cookie name is `csrftoken`.

## CI/CD

- **PRs and main pushes**: lint (ruff check + format) → test (pytest)
- **Releases**: push a `v*` tag → lint → test → build container → push to GHCR
- **Versioning**: manual — bump `version` in `pyproject.toml`, update `CHANGELOG.md` (keepachangelog format), then `git tag v{version}`
- **Dependabot**: weekly updates for pip, docker, and github-actions
