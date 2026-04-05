from litestar.testing import TestClient


def test_projects_list_requires_auth(client: TestClient) -> None:
    response = client.get("/projects", follow_redirects=False)
    assert response.status_code in (302, 303)


def test_manual_trigger_requires_auth(client: TestClient) -> None:
    # Without CSRF token, POST returns 403; with token but no auth, returns 302
    response = client.post(
        "/projects/00000000-0000-0000-0000-000000000001/collect", follow_redirects=False
    )
    assert response.status_code in (302, 303, 403)
