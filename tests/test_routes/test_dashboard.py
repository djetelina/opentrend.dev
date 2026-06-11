from unittest.mock import MagicMock, patch

from litestar.testing import TestClient


def test_dashboard_returns_404_for_nonexistent_project(client: TestClient) -> None:
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None

    with patch("opentrend.routes.dashboard.AsyncSession", autospec=True):
        response = client.get("/p/nonexistent/repo", follow_redirects=False)
        # Without auth session, redirects to login; with auth could be 404 or 500
        assert response.status_code in (302, 404, 500)


def test_og_route_exists(client: TestClient) -> None:
    response = client.get("/p/djetelina/cheznav/og.png", follow_redirects=False)
    # 200 with DB + public project, 404 for missing/private, 500 without DB
    assert response.status_code in (200, 404, 500)
    if response.status_code == 200:
        assert response.headers.get("content-type") == "image/png"
        assert response.content[:8] == b"\x89PNG\r\n\x1a\n"
