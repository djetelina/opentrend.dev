from litestar.testing import TestClient


def test_packaging_guide_returns_200(client: TestClient) -> None:
    response = client.get("/guides/packaging/aur")
    assert response.status_code == 200
    assert "AUR" in response.text


def test_packaging_guide_not_found(client: TestClient) -> None:
    response = client.get("/guides/packaging/nonexistent")
    assert response.status_code == 404


def test_packaging_guide_with_back_url(client: TestClient) -> None:
    response = client.get("/guides/packaging/aur?from=/p/owner/repo")
    assert response.status_code == 200
