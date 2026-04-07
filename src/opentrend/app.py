import hashlib
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from litestar import Litestar, Request, Response
from litestar.response import Redirect, Template
from litestar.config.csrf import CSRFConfig
from litestar.contrib.jinja import JinjaTemplateEngine
from litestar.exceptions import HTTPException, NotAuthorizedException, NotFoundException
from litestar.middleware.session.client_side import CookieBackendConfig
from litestar.plugins.prometheus import PrometheusConfig, PrometheusController
from litestar.datastructures import CacheControlHeader
from litestar.static_files import create_static_files_router
from litestar.status_codes import HTTP_404_NOT_FOUND, HTTP_500_INTERNAL_SERVER_ERROR
from litestar.template import TemplateConfig
from sqlalchemy.ext.asyncio import AsyncSession

from opentrend import __version__
from opentrend.config import Settings
from opentrend.db import create_engine, create_session_factory
from opentrend.logging import setup_logging
from opentrend.routes import login_redirect, provide_owned_project, provide_user
from opentrend.routes.auth import AuthController
from opentrend.routes.dashboard import DashboardController
from opentrend.routes.guides import GuidesController
from opentrend.routes.home import HomeController
from opentrend.routes.projects import ProjectController


_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Content-Security-Policy": (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; "
        "font-src 'self'; "
        "img-src 'self' data: https://avatars.githubusercontent.com; "
        "connect-src 'self'"
    ),
}


def _add_security_headers(response: Response) -> Response:
    for key, value in _SECURITY_HEADERS.items():
        response.headers.setdefault(key, value)
    return response


def _error_response(request: Request, status_code: int, template: str) -> Response:
    engine = request.app.template_engine
    t = engine.get_template(template)
    body = t.render(user=None)
    return Response(content=body, status_code=status_code, media_type="text/html")


def _404_handler(request: Request, _exc: HTTPException) -> Response:
    return _error_response(request, HTTP_404_NOT_FOUND, "errors/404.html")


def _500_handler(request: Request, _exc: Exception) -> Response:
    return _error_response(request, HTTP_500_INTERNAL_SERVER_ERROR, "errors/500.html")


def _auth_required_handler(request: Request, _exc: NotAuthorizedException) -> Redirect:
    return login_redirect(request)


def create_app(
    settings: Settings | None = None, run_migrations: bool = True
) -> Litestar:
    if settings is None:
        settings = Settings.from_env()

    engine = create_engine(settings)
    session_factory = create_session_factory(engine)

    # Derive separate keys for CSRF and session to avoid shared-secret risk
    csrf_secret = hashlib.sha256(f"csrf:{settings.secret_key}".encode()).hexdigest()
    session_secret = hashlib.sha256(f"session:{settings.secret_key}".encode()).digest()

    @asynccontextmanager
    async def lifespan(litestar_app: Litestar) -> AsyncGenerator[None, None]:
        import asyncio
        import logging

        from alembic import command
        from alembic.config import Config as AlembicConfig
        from apscheduler.schedulers.asyncio import AsyncIOScheduler

        from opentrend.scheduler.jobs import schedule_daily_collections

        # Configure after uvicorn's logging init so we override its handlers
        setup_logging(settings.log_level)

        alembic_cfg = AlembicConfig("alembic.ini")
        try:
            await asyncio.to_thread(command.upgrade, alembic_cfg, "head")
        except Exception:
            logging.getLogger(__name__).critical(
                "Database migration failed — check DATABASE_URL and that PostgreSQL is reachable",
                exc_info=True,
            )
            raise

        scheduler = AsyncIOScheduler()
        await schedule_daily_collections(scheduler, session_factory, settings)
        scheduler.start()
        litestar_app.state["scheduler"] = scheduler
        yield
        scheduler.shutdown(wait=False)

    async def provide_db_session() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            yield session

    async def provide_settings() -> Settings:
        return settings

    static_router = create_static_files_router(
        path="/static",
        directories=[Path(__file__).parent / "static"],
        cache_control=CacheControlHeader(max_age=86400, public=True, s_maxage=604800),
    )

    prometheus_config = PrometheusConfig(app_name="opentrend", group_path=True)

    def after_request_handler(response: Response) -> Response:
        _add_security_headers(response)
        if not settings.debug:
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
            )
        # Prevent browser/CDN from serving stale HTML after auth state changes
        if isinstance(response, (Template, Redirect)):
            response.headers["Cache-Control"] = "no-store"
        return response

    app = Litestar(
        route_handlers=[
            HomeController,
            AuthController,
            ProjectController,
            DashboardController,
            GuidesController,
            PrometheusController,
            static_router,
        ],
        dependencies={
            "db_session": provide_db_session,
            "settings": provide_settings,
            "user": provide_user,
            "project": provide_owned_project,
        },
        csrf_config=CSRFConfig(
            secret=csrf_secret,
            cookie_httponly=False,  # HTMX needs to read CSRF cookie to set X-CSRFToken header
            cookie_secure=not settings.debug,
            safe_methods={"GET", "HEAD", "OPTIONS"},
            exclude=["/metrics"],
        ),
        middleware=[
            CookieBackendConfig(
                secret=session_secret,
                httponly=True,
                secure=not settings.debug,
                samesite="lax",
                max_age=60 * 60 * 24 * 7,  # 7 days
            ).middleware,
            prometheus_config.middleware,
        ],
        template_config=TemplateConfig(
            engine=JinjaTemplateEngine,
            directory=Path(__file__).parent / "templates",
        ),
        lifespan=[lifespan] if run_migrations else [],
        after_request=after_request_handler,
        exception_handlers={
            NotAuthorizedException: _auth_required_handler,
            NotFoundException: _404_handler,
            HTTP_500_INTERNAL_SERVER_ERROR: _500_handler,
        },
        debug=settings.debug,
    )
    app.state["session_factory"] = session_factory
    app.template_engine.engine.globals["asset_v"] = __version__
    return app
