from opentrend import USER_AGENT

GITHUB_API = "https://api.github.com"

GITHUB_HEADERS_BASE: dict[str, str] = {
    "User-Agent": USER_AGENT,
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}


def github_headers(token: str) -> dict[str, str]:
    """Standard headers for authenticated GitHub API requests."""
    return {**GITHUB_HEADERS_BASE, "Authorization": f"Bearer {token}"}
