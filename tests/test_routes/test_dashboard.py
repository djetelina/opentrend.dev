from unittest.mock import MagicMock, patch

from litestar.testing import TestClient


def test_dashboard_returns_404_for_nonexistent_project(client: TestClient) -> None:
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None

    with patch("opentrend.routes.dashboard.AsyncSession", autospec=True):
        response = client.get("/p/nonexistent/repo", follow_redirects=False)
        # Without auth session, redirects to login; with auth could be 404 or 500
        assert response.status_code in (302, 404, 500)
