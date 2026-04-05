from opentrend.auth.github import build_authorize_url


def test_build_authorize_url() -> None:
    url = build_authorize_url(
        client_id="test-id",
        redirect_uri="http://localhost/callback",
        state="test-state",
    )
    assert "client_id=test-id" in url
    assert "redirect_uri=http%3A%2F%2Flocalhost%2Fcallback" in url
    assert "github.com/login/oauth/authorize" in url
    assert "state=test-state" in url
    assert "public_repo" in url
