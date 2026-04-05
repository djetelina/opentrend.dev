from litestar.testing import TestClient


def test_login_redirects_to_github(client: TestClient) -> None:
    response = client.get("/auth/login", follow_redirects=False)
    assert response.status_code in (301, 302, 303, 307)
    location = response.headers.get("location", "")
    assert "github.com" in location
    assert "state=" in location


def test_logout_rejects_get(client: TestClient) -> None:
    response = client.get("/auth/logout", follow_redirects=False)
    assert response.status_code == 405


def _csrf_post(client: TestClient, url: str, **kwargs) -> object:
    """POST with CSRF token from cookie."""
    client.get("/")  # seed CSRF cookie
    token = client.cookies.get("csrftoken", "")
    headers = kwargs.pop("headers", {})
    headers["x-csrftoken"] = token
    headers["cookie"] = f"csrftoken={token}"
    return client.post(url, headers=headers, **kwargs)


def test_logout_post_redirects(client: TestClient) -> None:
    response = _csrf_post(client, "/auth/logout", follow_redirects=False)
    assert response.status_code in (301, 302, 303, 307)


def test_dev_login_disabled_in_production(client: TestClient) -> None:
    """Dev-login should redirect to / when debug is off (test settings have debug=False)."""
    response = client.get("/auth/dev-login", follow_redirects=False)
    assert response.status_code in (301, 302, 303, 307)
    assert response.headers.get("location", "").rstrip("/") in ("", "/")


def test_delete_account_requires_csrf(client: TestClient) -> None:
    response = client.post(
        "/auth/delete-account",
        json={"confirmation": "DELETE"},
        follow_redirects=False,
    )
    assert response.status_code == 403  # CSRF rejected


def test_delete_account_without_session_redirects_home(client: TestClient) -> None:
    response = _csrf_post(
        client,
        "/auth/delete-account",
        content=b'{"confirmation": "DELETE"}',
        follow_redirects=False,
    )
    assert response.status_code in (301, 302, 303, 307)
    location = response.headers.get("location", "")
    assert location == "/" or location.endswith("/")
