import pytest
from litestar.testing import TestClient

from opentrend.app import create_app
from opentrend.config import Settings


@pytest.fixture()
def settings() -> Settings:
    return Settings(
        database_url="postgresql+asyncpg://test:test@localhost/test",
        secret_key="0123456789abcdef0123456789abcdef",
        encryption_key="test-encryption-key-0123456789ab",
        github_client_id="test-client-id",
        github_client_secret="test-client-secret",
    )


@pytest.fixture()
def client(settings: Settings) -> TestClient:
    with TestClient(app=create_app(settings=settings, run_migrations=False)) as c:
        yield c
