from urllib.parse import urlencode

import niquests

from opentrend.github_utils import GITHUB_API

GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USER_URL = f"{GITHUB_API}/user"


def build_authorize_url(client_id: str, redirect_uri: str, state: str) -> str:
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": "read:user public_repo",
        "state": state,
    }
    return f"{GITHUB_AUTHORIZE_URL}?{urlencode(params)}"


class OAuthError(Exception):
    """GitHub returned an error response during token exchange."""


async def exchange_code(client_id: str, client_secret: str, code: str) -> str:
    async with niquests.AsyncSession() as client:
        resp = await client.post(
            GITHUB_TOKEN_URL,
            json={"client_id": client_id, "client_secret": client_secret, "code": code},
            headers={"Accept": "application/json"},
        )
        resp.raise_for_status()
        data = resp.json()
        if "error" in data:
            raise OAuthError(f"{data['error']}: {data.get('error_description', '')}")
        return data["access_token"]


async def fetch_user(access_token: str) -> dict:
    async with niquests.AsyncSession() as client:
        resp = await client.get(
            GITHUB_USER_URL,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
            },
        )
        resp.raise_for_status()
        data = resp.json()
        return {
            "github_id": data["id"],
            "github_username": data["login"],
            "avatar_url": data["avatar_url"],
        }
