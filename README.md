# OpenTrend

Open source project metrics dashboard - [opentrend.dev](https://opentrend.dev).

## Releasing

Versioning is manual. To cut a release:

1. Bump `version` in `pyproject.toml`.
2. Update `CHANGELOG.md` (keepachangelog format).
3. Tag and push: `git tag v<version> && git push origin v<version>`.

Pushing a `v*` tag triggers the release workflow: lint → test → build → push a
multi-arch (`linux/amd64` + `linux/arm64`) container image to
`ghcr.io/<owner>/<repo>`, tagged `<version>`, `<major>.<minor>`, and
`sha-<commit>`. That image is the deploy artifact. PRs and `main` pushes only
run lint + test - no image is built.

## Maintenance

### Reach backfill

`reach_score` is computed at collection time, so new snapshots always use the
current formula. After **changing the reach formula** (in `DashboardService`),
recompute it for all historical `github_snapshots`:

```bash
kubectl exec deploy/opentrend -- /app/.venv/bin/python scripts/backfill_reach.py
```

The script ships in the container image (`scripts/`), reuses
`DashboardService.compute_reach`, reads `DATABASE_URL` from the pod env, and
commits in batches. Requires a rebuilt image if `scripts/` changed.
