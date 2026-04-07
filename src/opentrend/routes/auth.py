import logging
import secrets

from litestar import Controller, get, post
from litestar.connection import Request
from litestar.response import Redirect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from opentrend.auth.github import (
    OAuthError,
    build_authorize_url,
    exchange_code,
    fetch_user,
)
from opentrend.config import Settings
from opentrend.crypto import encrypt_token
from opentrend.models.user import User
from opentrend.routes import safe_redirect_url

logger = logging.getLogger(__name__)


class AuthController(Controller):
    path = "/auth"

    @get("/login", name="auth:login")
    async def login(self, request: Request, settings: Settings) -> Redirect:
        return_url = request.query_params.get("return_url", "/")
        request.session["return_url"] = safe_redirect_url(return_url)
        state = secrets.token_urlsafe(32)
        request.session["oauth_state"] = state
        redirect_uri = str(
            request.url.with_replacements(path="/auth/callback", query="")
        )
        url = build_authorize_url(settings.github_client_id, redirect_uri, state)
        return Redirect(url)

    @get("/callback", name="auth:callback")
    async def callback(
        self, request: Request, settings: Settings, db_session: AsyncSession, code: str
    ) -> Redirect:
        # Verify OAuth state
        state = request.query_params.get("state", "")
        expected_state = request.session.pop("oauth_state", None)
        if not expected_state or state != expected_state:
            return Redirect("/")

        try:
            access_token = await exchange_code(
                settings.github_client_id, settings.github_client_secret, code
            )
            gh_user = await fetch_user(access_token)
        except OAuthError as exc:
            logger.warning("OAuth rejected: %s", exc)
            request.session["flash_error"] = "GitHub login failed. Please try again."
            return Redirect("/")
        except Exception:
            logger.exception("OAuth token exchange or user fetch failed")
            request.session["flash_error"] = (
                "Login failed due to a server error. Please try again."
            )
            return Redirect("/")

        result = await db_session.execute(
            select(User).where(User.github_id == gh_user["github_id"])
        )
        user = result.scalar_one_or_none()

        encrypted_token = encrypt_token(access_token, settings.encryption_key)

        if user is None:
            user = User(
                github_id=gh_user["github_id"],
                github_username=gh_user["github_username"],
                avatar_url=gh_user["avatar_url"],
                github_access_token=encrypted_token,
            )
            db_session.add(user)
        else:
            user.github_username = gh_user["github_username"]
            user.avatar_url = gh_user["avatar_url"]
            user.github_access_token = encrypted_token

        await db_session.commit()
        request.session["user_id"] = str(user.id)

        return_url = safe_redirect_url(request.session.pop("return_url", "/projects"))
        return Redirect(return_url)

    @post("/logout", name="auth:logout")
    async def logout(self, request: Request) -> Redirect:
        request.session.clear()
        return Redirect("/")

    @get("/dev-login", name="auth:dev_login")
    async def dev_login(
        self,
        request: Request,
        user: User | None,
        db_session: AsyncSession,
        settings: Settings,
    ) -> Redirect:
        if not settings.debug:
            return Redirect("/")

        if user:
            return Redirect("/")

        result = await db_session.execute(select(User).where(User.github_id == 0))
        user = result.scalar_one_or_none()
        if user is None:
            user = User(
                github_id=0,
                github_username="__dev__",
                avatar_url="",
            )
            db_session.add(user)
            await db_session.commit()

        request.session["user_id"] = str(user.id)
        return Redirect("/")

    @post("/delete-account", name="auth:delete_account")
    async def delete_account(
        self, request: Request, db_session: AsyncSession, data: dict
    ) -> Redirect:
        user_id = request.session.get("user_id")
        if not user_id:
            return Redirect("/")

        confirmation = data.get("confirmation", "")
        if confirmation != "DELETE":
            return Redirect("/projects")

        result = await db_session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user:
            await db_session.delete(user)
            await db_session.commit()

        request.session.clear()
        return Redirect("/")
