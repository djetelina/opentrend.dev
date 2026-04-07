import asyncio
import logging
import re

from litestar import Controller, get, post
from litestar.connection import Request
from litestar.enums import RequestEncodingType
from litestar.params import Body
from litestar.response import Redirect, Template
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy.exc import IntegrityError

from opentrend.config import Settings
from opentrend.crypto import try_decrypt_token
from opentrend.models.project import Project
from opentrend.models.user import User
from opentrend.routes import parse_extra_packages, require_login
from opentrend.scheduler.jobs import collect_project, recalc_reach, register_project_job
from opentrend.services.dashboard import DashboardService
from opentrend.services.project import ProjectService
from opentrend.services.discovery import discover

logger = logging.getLogger(__name__)


def _make_collection_callback(app_state: dict, project_id):
    def _on_done(task: asyncio.Task) -> None:
        collecting = app_state.get("collecting_tasks", {})
        collecting.pop(project_id, None)
        if task.cancelled():
            return
        exc = task.exception()
        if exc is not None:
            logger.exception("Background collection failed: %s", exc, exc_info=exc)

    return _on_done


async def _fetch_user_repos(token: str, exclude: set[str] | None = None) -> list[dict]:
    from opentrend.github_utils import GITHUB_API, github_headers
    from opentrend.metrics import instrumented_client

    exclude = exclude or set()
    repos = []
    page = 1
    max_pages = 20
    headers = github_headers(token)
    async with instrumented_client(timeout=30) as client:
        while page <= max_pages:
            resp = await client.get(
                f"{GITHUB_API}/user/repos",
                params={
                    "per_page": "100",
                    "page": str(page),
                    "sort": "updated",
                    "affiliation": "owner,organization_member",
                },
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()
            if not data:
                break
            for r in data:
                if r.get("archived") or r.get("private"):
                    continue
                if not r.get("permissions", {}).get("admin"):
                    continue
                if r["full_name"] in exclude:
                    continue
                repos.append(
                    {
                        "full_name": r["full_name"],
                        "description": r.get("description") or "",
                        "stars": r["stargazers_count"],
                        "fork": r.get("fork", False),
                    }
                )
            if len(data) < 100:
                break
            page += 1
    repos.sort(key=lambda repo: (repo["fork"], -repo["stars"]))
    return repos


class ProjectController(Controller):
    path = "/projects"
    guards = [require_login]

    @get("/", name="projects:list")
    async def list_projects(self) -> Redirect:
        return Redirect("/")

    @get("/add", name="projects:add_form")
    async def add_form(self, user: User, settings: Settings) -> Template:
        return Template(
            template_name="projects/add.html",
            context={"user": user, "github_client_id": settings.github_client_id},
        )

    @get("/add/repos", name="projects:add_repos")
    async def add_repos(
        self, user: User, db_session: AsyncSession, settings: Settings
    ) -> Template:
        repos = []
        token = try_decrypt_token(user.github_access_token, settings.encryption_key)
        if token:
            try:
                service = ProjectService(db_session)
                existing = await service.get_by_user(user.id)
                managed = {p.github_repo for p in existing}
                repos = await _fetch_user_repos(token, exclude=managed)
            except Exception:
                logger.warning("Failed to fetch user repos", exc_info=True)

        return Template(
            template_name="components/repo_picker.html",
            context={"repos": repos},
        )

    @post("/add", name="projects:add_discover")
    async def add_discover(
        self,
        user: User,
        settings: Settings,
        data: dict = Body(media_type=RequestEncodingType.URL_ENCODED),
    ) -> Template | Redirect:
        github_repo = data.get("github_repo", "").strip()
        if not re.match(r"^[a-zA-Z0-9._-]+/[a-zA-Z0-9._-]+$", github_repo):
            return Redirect("/projects/add")
        project_name = github_repo.split("/")[-1]
        display_name = project_name
        description = ""

        gh_token = try_decrypt_token(user.github_access_token, settings.encryption_key)
        if gh_token:
            import niquests
            from opentrend.github_utils import GITHUB_API, github_headers

            try:
                async with niquests.AsyncSession() as client:
                    resp = await client.get(
                        f"{GITHUB_API}/repos/{github_repo}",
                        headers=github_headers(gh_token),
                    )
                    if resp.status_code == 200:
                        gh_data = resp.json()
                        description = gh_data.get("description") or ""
                        display_name = gh_data.get("name") or project_name
            except niquests.exceptions.RequestException, KeyError, ValueError:
                logger.warning(
                    "Failed to fetch repo info for %s", github_repo, exc_info=True
                )

        result = await discover(project_name, github_token=gh_token)

        return Template(
            template_name="projects/add_discover.html",
            context={
                "user": user,
                "github_repo": github_repo,
                "display_name": display_name,
                "description": description,
                "discovered": result.packages,
                "discovery_warnings": result.warnings,
            },
        )

    @post("/add/confirm", name="projects:add_confirm")
    async def add_confirm(
        self, request: Request, user: User, db_session: AsyncSession, settings: Settings
    ) -> Redirect:
        form = await request.form()

        github_repo = form.get("github_repo", "")
        if not re.match(r"^[a-zA-Z0-9._-]+/[a-zA-Z0-9._-]+$", github_repo):
            return Redirect("/projects/add")
        display_name = form.get("display_name", github_repo.split("/")[-1])
        description = form.get("description", "")

        package_mappings = []
        packages_raw = form.getall("packages") if "packages" in form else []
        for p in packages_raw:
            source, name = p.split(":", 1)
            package_mappings.append({"source": source, "package_name": name})

        package_mappings.extend(parse_extra_packages(form))

        service = ProjectService(db_session)
        project = await service.create(
            user_id=user.id,
            github_repo=github_repo,
            display_name=display_name,
            description=description,
            package_mappings=package_mappings,
        )

        session_factory = request.app.state.get("session_factory")
        if session_factory:
            task = asyncio.create_task(
                collect_project(session_factory, settings, project.id)
            )
            collecting = request.app.state.setdefault("collecting_tasks", {})
            collecting[project.id] = task
            task.add_done_callback(
                _make_collection_callback(request.app.state, project.id)
            )

        scheduler = request.app.state.get("scheduler")
        if scheduler and session_factory:
            register_project_job(scheduler, session_factory, settings, project.id)

        return Redirect(f"/projects/{project.id}/collecting")

    @get("/{project_id:uuid}/collecting", name="projects:collecting")
    async def collecting_page(
        self, request: Request, user: User, project: Project
    ) -> Template | Redirect:
        collecting = request.app.state.get("collecting_tasks", {})
        task = collecting.get(project.id)
        if task is None or task.done():
            collecting.pop(project.id, None)
            return Redirect(f"/p/{project.github_repo}")

        return Template(
            template_name="projects/collecting.html",
            context={"project": project, "user": user},
        )

    @get("/{project_id:uuid}/collecting/status", name="projects:collecting_status")
    async def collecting_status(
        self, request: Request, project: Project
    ) -> Template | Redirect:
        collecting = request.app.state.get("collecting_tasks", {})
        task = collecting.get(project.id)
        if task is None or task.done():
            collecting.pop(project.id, None)
            error = None
            if task is not None:
                try:
                    exc = task.exception()
                    if exc is not None:
                        error = str(exc)
                except asyncio.CancelledError, asyncio.InvalidStateError:
                    pass
            return Template(
                template_name="components/collecting_done.html",
                context={"project": project, "error": error},
            )

        return Template(
            template_name="components/collecting_progress.html",
            context={"project": project},
        )

    @get("/{project_id:uuid}/edit", name="projects:edit_form")
    async def edit_form(
        self, user: User, project: Project, db_session: AsyncSession
    ) -> Template:
        dashboard = DashboardService(db_session)
        latest_gh = await dashboard.get_latest_github_snapshot(project.id)
        latest_release_tag = latest_gh.latest_release_tag if latest_gh else None
        latest_pkg = await dashboard.get_latest_package_snapshots(project.id)
        matrix = DashboardService.format_packaging_matrix(
            project.package_mappings, latest_pkg, latest_release_tag
        )

        return Template(
            template_name="projects/edit.html",
            context={"project": project, "user": user, "matrix": matrix},
        )

    @get("/{project_id:uuid}/rediscover", name="projects:rediscover")
    async def rediscover(
        self, user: User, project: Project, settings: Settings
    ) -> Template:
        project_name = project.github_repo.split("/")[-1]
        gh_token = try_decrypt_token(user.github_access_token, settings.encryption_key)
        result = await discover(project_name, github_token=gh_token)

        existing = {(m.source, m.package_name) for m in project.package_mappings}
        new_packages = [
            p for p in result.packages if (p.source, p.package_name) not in existing
        ]

        return Template(
            template_name="components/rediscover_results.html",
            context={"new_packages": new_packages},
        )

    @post("/{project_id:uuid}/edit", name="projects:edit_save")
    async def edit_save(
        self, request: Request, project: Project, db_session: AsyncSession
    ) -> Redirect:
        form = await request.form()

        from opentrend.models.project import PackageMapping

        kept_keys: dict[tuple[str, str], str] = {}
        for p in form.getall("packages"):
            source, name = p.split(":", 1)
            kept_keys[(source, name.lower())] = name

        to_remove = [
            m
            for m in project.package_mappings
            if (m.source, m.package_name.lower()) not in kept_keys
        ]
        for m in to_remove:
            try:
                async with db_session.begin_nested():
                    project.package_mappings.remove(m)
                    await db_session.flush()
            except IntegrityError:
                logger.info(
                    "Keeping mapping %s:%s (id=%d) — has existing snapshots",
                    m.source,
                    m.package_name,
                    m.id,
                )

        existing_keys = {
            (m.source, m.package_name.lower()) for m in project.package_mappings
        }
        for key, original_name in kept_keys.items():
            if key not in existing_keys:
                project.package_mappings.append(
                    PackageMapping(source=key[0], package_name=original_name)
                )

        for m in parse_extra_packages(form):
            project.package_mappings.append(
                PackageMapping(source=m["source"], package_name=m["package_name"])
            )

        project.public = form.get("public") == "1"

        await db_session.commit()
        return Redirect(f"/p/{project.github_repo}")

    @post("/{project_id:uuid}/delete", name="projects:delete")
    async def delete_project(
        self, project: Project, db_session: AsyncSession
    ) -> Redirect:
        await ProjectService(db_session).delete(project)
        return Redirect("/projects")

    @post("/{project_id:uuid}/collect", name="projects:collect")
    async def trigger_collection(
        self, request: Request, project: Project, settings: Settings
    ) -> Redirect:
        project_id = project.id
        session_factory = request.app.state.get("session_factory")
        if session_factory:
            task = asyncio.create_task(
                collect_project(session_factory, settings, project_id)
            )
            collecting = request.app.state.setdefault("collecting_tasks", {})
            collecting[project_id] = task
            task.add_done_callback(
                _make_collection_callback(request.app.state, project_id)
            )

        return Redirect(f"/projects/{project_id}/collecting")

    @post("/recalc-reach", name="projects:recalc_reach")
    async def recalc_reach_scores(
        self, request: Request, user: User, db_session: AsyncSession
    ) -> Redirect:
        service = ProjectService(db_session)
        projects = await service.get_by_user(user.id)
        session_factory = request.app.state.get("session_factory")
        if session_factory:
            for project in projects:
                await recalc_reach(session_factory, project.id)

        return Redirect("/")
