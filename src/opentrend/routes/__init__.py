import re
import uuid

from litestar.connection import Request
from litestar.exceptions import NotAuthorizedException, NotFoundException
from litestar.handlers import BaseRouteHandler
from litestar.response import Redirect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from opentrend.models.project import Project
from opentrend.models.user import User

_SAFE_PATH_RE = re.compile(r"^/[a-zA-Z0-9_./-]*$")


def safe_redirect_url(url: str, fallback: str = "/projects") -> str:
    """Validate that a URL is a safe relative path."""
    if (
        url
        and _SAFE_PATH_RE.match(url)
        and not url.startswith("//")
        and ".." not in url
    ):
        return url
    return fallback


def login_redirect(request: Request) -> Redirect:
    return_url = safe_redirect_url(request.url.path)
    return Redirect(f"/auth/login?return_url={return_url}")


async def provide_user(request: Request, db_session: AsyncSession) -> User | None:
    """Dependency: resolve the current user from the session cookie."""
    user_id = request.session.get("user_id")
    if user_id is None:
        return None
    try:
        uid = uuid.UUID(str(user_id))
    except ValueError, AttributeError:
        request.session.clear()
        return None
    result = await db_session.execute(select(User).where(User.id == uid))
    return result.scalar_one_or_none()


async def provide_owned_project(
    user: User, db_session: AsyncSession, project_id: uuid.UUID
) -> Project:
    """Dependency: load a project by ID and verify the current user owns it."""
    from opentrend.services.project import ProjectService

    project = await ProjectService(db_session).get_by_id(project_id)
    if project is None or project.user_id != user.id:
        raise NotFoundException("Project not found")
    return project


async def require_login(request: Request, _: BaseRouteHandler) -> None:
    """Guard: redirect to login if no session user."""
    if "user_id" not in request.session:
        raise NotAuthorizedException()


def parse_extra_packages(form) -> list[dict]:
    """Parse extra package mapping rows from form dropdowns."""
    sources = form.getall("extra_source[]")
    names = form.getall("extra_name[]")
    taps = form.getall("extra_tap[]")

    # Pad taps to match sources length so zip doesn't silently truncate
    taps_padded = taps + [""] * (len(sources) - len(taps))

    package_mappings = []
    for source, name, tap in zip(sources, names, taps_padded):
        source = source.strip()
        name = name.strip()
        if not source or not name:
            continue
        if source == "homebrew_tap" and tap.strip():
            name = f"{tap.strip()}/{name}"
        package_mappings.append({"source": source, "package_name": name})
    return package_mappings
