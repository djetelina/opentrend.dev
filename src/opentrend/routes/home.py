import json
import uuid

from xml.sax.saxutils import escape as xml_escape

from litestar import Controller, MediaType, get
from litestar.connection import Request
from litestar.exceptions import NotFoundException
from litestar.response import Response, Template
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from opentrend.models.project import PackageMapping, Project
from opentrend.models.snapshot import GithubSnapshot
from opentrend.models.user import User
from opentrend.services.dashboard import DashboardService
from opentrend.services.project import ProjectService


def _format_number(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}k"
    return str(n)


_ROBOTS_TXT = """\
User-agent: *
Allow: /$
Allow: /about
Allow: /data
Allow: /guides
Disallow: /
"""


class HomeController(Controller):
    path = "/"

    @get("/health", name="health")
    async def health(self) -> dict:
        return {"status": "ok"}

    @get("/robots.txt", name="robots", media_type=MediaType.TEXT)
    async def robots(self) -> str:
        return _ROBOTS_TXT

    @get(
        "/badge/{owner:str}/{repo:str}/reach.svg",
        name="badge",
        media_type="image/svg+xml",
    )
    async def badge(self, db_session: AsyncSession, owner: str, repo: str) -> Response:
        github_repo = f"{owner}/{repo}"
        result = await db_session.execute(
            select(Project).where(Project.github_repo == github_repo)
        )
        project = result.scalar_one_or_none()
        if project is None:
            raise NotFoundException("Project not found")

        result = await db_session.execute(
            select(GithubSnapshot.reach_score)
            .where(
                GithubSnapshot.project_id == project.id,
                GithubSnapshot.reach_score.is_not(None),
            )
            .order_by(desc(GithubSnapshot.date))
            .limit(1)
        )
        row = result.scalar_one_or_none()
        value = _format_number(row) if row is not None else "?"

        label = xml_escape("opentrend.dev")
        value = xml_escape(value)
        label_width = len(label) * 6.5 + 10
        value_width = len(value) * 6.5 + 10
        total_width = label_width + value_width

        svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{total_width}" height="20" role="img" aria-label="{label}: {value}">
  <title>{label}: {value}</title>
  <linearGradient id="s" x2="0" y2="100%">
    <stop offset="0" stop-color="#bbb" stop-opacity=".1"/>
    <stop offset="1" stop-opacity=".1"/>
  </linearGradient>
  <clipPath id="r"><rect width="{total_width}" height="20" rx="3" fill="#fff"/></clipPath>
  <g clip-path="url(#r)">
    <rect width="{label_width}" height="20" fill="#555"/>
    <rect x="{label_width}" width="{value_width}" height="20" fill="#14b8a6"/>
    <rect width="{total_width}" height="20" fill="url(#s)"/>
  </g>
  <g fill="#fff" text-anchor="middle" font-family="Verdana,Geneva,DejaVu Sans,sans-serif" text-rendering="geometricPrecision" font-size="11">
    <text aria-hidden="true" x="{label_width / 2}" y="15" fill="#010101" fill-opacity=".3">{label}</text>
    <text x="{label_width / 2}" y="14">{label}</text>
    <text aria-hidden="true" x="{label_width + value_width / 2}" y="15" fill="#010101" fill-opacity=".3">{value}</text>
    <text x="{label_width + value_width / 2}" y="14">{value}</text>
  </g>
</svg>'''

        return Response(
            content=svg,
            media_type="image/svg+xml",
            headers={
                "Cache-Control": "max-age=3600, s-maxage=3600",
                "X-Content-Type-Options": "nosniff",
                "Content-Disposition": "inline",
            },
        )

    @get("/about", name="about")
    async def about(self, user: User | None) -> Template:
        return Template(template_name="about.html", context={"user": user})

    @get("/data", name="data")
    async def data_page(self, user: User | None) -> Template:
        return Template(template_name="data.html", context={"user": user})

    @get("/leaderboard", name="leaderboard")
    async def leaderboard(
        self, request: Request, user: User | None, db_session: AsyncSession
    ) -> Template:
        try:
            page = int(request.query_params.get("page", "1"))
        except ValueError, TypeError:
            page = 1
        per_page = 50
        if page < 1:
            page = 1

        # Latest github snapshot per project via window function
        latest = (
            select(
                GithubSnapshot.project_id,
                GithubSnapshot.reach_score,
                func.row_number()
                .over(
                    partition_by=GithubSnapshot.project_id,
                    order_by=desc(GithubSnapshot.date),
                )
                .label("rn"),
            )
            .where(GithubSnapshot.reach_score.is_not(None))
            .subquery()
        )

        base = (
            select(
                Project.id.label("project_id"),
                Project.display_name,
                Project.github_repo,
                latest.c.reach_score,
            )
            .join(latest, Project.id == latest.c.project_id)
            .where(latest.c.rn == 1)
            .where(latest.c.reach_score > 0)
        )

        # Total count
        count_stmt = select(func.count()).select_from(base.subquery())
        total = (await db_session.execute(count_stmt)).scalar_one()
        total_pages = max(1, (total + per_page - 1) // per_page)
        if page > total_pages:
            page = total_pages

        # Paginated results
        offset = (page - 1) * per_page
        stmt = base.order_by(desc(latest.c.reach_score)).offset(offset).limit(per_page)
        rows = (await db_session.execute(stmt)).all()
        project_ids = [r.project_id for r in rows]

        # Batch-fetch reach history for sparklines
        reach_history: dict[uuid.UUID, list[int]] = {pid: [] for pid in project_ids}
        if project_ids:
            hist_stmt = (
                select(
                    GithubSnapshot.project_id,
                    GithubSnapshot.reach_score,
                )
                .where(GithubSnapshot.project_id.in_(project_ids))
                .where(GithubSnapshot.reach_score.is_not(None))
                .order_by(GithubSnapshot.project_id, GithubSnapshot.date)
            )
            for h in await db_session.execute(hist_stmt):
                reach_history[h.project_id].append(h.reach_score)

        # Batch-fetch package sources per project
        sources_by_project: dict[uuid.UUID, list[str]] = {
            pid: [] for pid in project_ids
        }
        if project_ids:
            src_stmt = (
                select(
                    PackageMapping.project_id,
                    PackageMapping.source,
                )
                .where(PackageMapping.project_id.in_(project_ids))
                .distinct()
            )
            for s in await db_session.execute(src_stmt):
                sources_by_project[s.project_id].append(s.source)

        entries = [
            {
                "rank": offset + i + 1,
                "display_name": r.display_name,
                "github_repo": r.github_repo,
                "reach": r.reach_score,
                "reach_history": json.dumps(reach_history.get(r.project_id, [])),
                "sources": sources_by_project.get(r.project_id, []),
            }
            for i, r in enumerate(rows)
        ]

        return Template(
            template_name="leaderboard.html",
            context={
                "entries": entries,
                "user": user,
                "page": page,
                "total_pages": total_pages,
                "total": total,
            },
        )

    @get("/", name="home")
    async def home(self, user: User | None, db_session: AsyncSession) -> Template:
        project_data = []

        if user:
            service = ProjectService(db_session)
            projects = await service.get_by_user(user.id)
            if projects:
                dashboard = DashboardService(db_session)
                pids = [p.id for p in projects]
                gh_by_project = await dashboard.get_github_snapshots_batch(pids)
                pkg_by_project = await dashboard.get_latest_package_snapshots_batch(
                    pids
                )

                for project in projects:
                    gh_snapshots = gh_by_project.get(project.id, [])
                    latest_gh = gh_snapshots[-1] if gh_snapshots else None
                    latest_pkg = pkg_by_project.get(project.id, {})
                    matrix = DashboardService.format_packaging_matrix(
                        project.package_mappings,
                        latest_pkg,
                        latest_gh.latest_release_tag if latest_gh else None,
                    )
                    total_downloads = DashboardService.compute_total_downloads(matrix)
                    reach = (latest_gh.reach_score or 0) if latest_gh else 0
                    reach_history = [
                        s.reach_score for s in gh_snapshots if s.reach_score is not None
                    ]
                    project_data.append(
                        {
                            "project": project,
                            "reach": reach,
                            "reach_history": json.dumps(reach_history),
                            "stars": _format_number(latest_gh.stars)
                            if latest_gh
                            else "0",
                            "sources": sum(1 for r in matrix if r.get("version")),
                            "downloads": _format_number(total_downloads),
                        }
                    )

                project_data.sort(key=lambda x: x["reach"], reverse=True)

        # Leaderboard preview for logged-out landing page
        leaderboard_entries = []
        if not user:
            latest = (
                select(
                    GithubSnapshot.project_id,
                    GithubSnapshot.reach_score,
                    func.row_number()
                    .over(
                        partition_by=GithubSnapshot.project_id,
                        order_by=desc(GithubSnapshot.date),
                    )
                    .label("rn"),
                )
                .where(GithubSnapshot.reach_score.is_not(None))
                .subquery()
            )
            stmt = (
                select(
                    Project.display_name,
                    Project.github_repo,
                    latest.c.reach_score,
                    Project.id.label("project_id"),
                )
                .join(latest, Project.id == latest.c.project_id)
                .where(latest.c.rn == 1)
                .where(latest.c.reach_score > 0)
                .order_by(desc(latest.c.reach_score))
                .limit(5)
            )
            rows = (await db_session.execute(stmt)).all()
            project_ids = [r.project_id for r in rows]

            reach_history: dict[uuid.UUID, list[int]] = {pid: [] for pid in project_ids}
            if project_ids:
                hist_stmt = (
                    select(GithubSnapshot.project_id, GithubSnapshot.reach_score)
                    .where(GithubSnapshot.project_id.in_(project_ids))
                    .where(GithubSnapshot.reach_score.is_not(None))
                    .order_by(GithubSnapshot.project_id, GithubSnapshot.date)
                )
                for h in await db_session.execute(hist_stmt):
                    reach_history[h.project_id].append(h.reach_score)

            leaderboard_entries = [
                {
                    "rank": i + 1,
                    "display_name": r.display_name,
                    "github_repo": r.github_repo,
                    "reach": r.reach_score,
                    "reach_history": json.dumps(reach_history.get(r.project_id, [])),
                }
                for i, r in enumerate(rows)
            ]

        return Template(
            template_name="home.html",
            context={
                "project_data": project_data,
                "user": user,
                "leaderboard_entries": leaderboard_entries,
            },
        )
