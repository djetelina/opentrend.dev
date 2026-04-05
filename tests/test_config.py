import pytest

from opentrend.config import Settings


def test_settings_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/opentrend"
    )
    monkeypatch.setenv("SECRET_KEY", "test-secret")
    monkeypatch.setenv("ENCRYPTION_KEY", "test-encryption-key")
    monkeypatch.setenv("GITHUB_CLIENT_ID", "ghid")
    monkeypatch.setenv("GITHUB_CLIENT_SECRET", "ghsecret")

    settings = Settings.from_env()

    assert settings.database_url == "postgresql+asyncpg://user:pass@localhost/opentrend"
    assert settings.secret_key == "test-secret"
    assert settings.encryption_key == "test-encryption-key"
    assert settings.github_client_id == "ghid"
    assert settings.github_client_secret == "ghsecret"


def test_settings_missing_required_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("SECRET_KEY", raising=False)

    with pytest.raises(ValueError, match="DATABASE_URL"):
        Settings.from_env()
