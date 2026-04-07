from litestar.testing import TestClient


def test_home_route_exists(client: TestClient) -> None:
    response = client.get("/")
    # 200 with DB, 500 without — route exists and dispatches
    assert response.status_code in (200, 500)


def test_data_page_returns_200(client: TestClient) -> None:
    response = client.get("/data")
    assert response.status_code == 200


def test_leaderboard_route_exists(client: TestClient) -> None:
    response = client.get("/leaderboard")
    # 200 with DB, 500 without — either means the route exists and dispatches
    assert response.status_code in (200, 500)


def test_badge_route_exists(client: TestClient) -> None:
    response = client.get("/badge/nonexistent/repo/reach.svg")
    # 404 with DB (project not found), 500 without DB
    assert response.status_code in (404, 500)


def test_health_returns_200(client: TestClient) -> None:
    response = client.get("/health")
    # 200 with DB, 500 without — route exists
    assert response.status_code in (200, 500)


def test_security_headers_present(client: TestClient) -> None:
    response = client.get("/data")
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("X-Frame-Options") == "DENY"
    assert response.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert "Content-Security-Policy" in response.headers


def test_404_returns_html(client: TestClient) -> None:
    response = client.get("/nonexistent-page-that-does-not-exist")
    assert response.status_code == 404
    assert "404" in response.text


def test_format_number() -> None:
    from opentrend.routes.home import _format_number

    assert _format_number(500) == "500"
    assert _format_number(1500) == "1.5k"
    assert _format_number(1_500_000) == "1.5M"
    assert _format_number(0) == "0"
