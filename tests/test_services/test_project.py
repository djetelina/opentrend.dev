import uuid

import pytest
from unittest.mock import AsyncMock, MagicMock

from opentrend.services.project import ProjectService

_TEST_USER_ID = uuid.uuid4()


@pytest.fixture()
def mock_session() -> AsyncMock:
    session = AsyncMock()
    session.add = MagicMock()
    session.delete = MagicMock()
    return session


@pytest.mark.asyncio
async def test_create_project(mock_session: AsyncMock) -> None:
    service = ProjectService(mock_session)
    project = await service.create(
        user_id=_TEST_USER_ID,
        github_repo="encode/httpx",
        display_name="httpx",
        description="A next-generation HTTP client",
        package_mappings=[{"source": "pypi", "package_name": "httpx"}],
    )

    assert project.github_repo == "encode/httpx"
    assert project.display_name == "httpx"
    assert project.user_id == _TEST_USER_ID
    assert len(project.package_mappings) == 1
    assert project.package_mappings[0].source == "pypi"
    mock_session.add.assert_called_once_with(project)
    mock_session.commit.assert_awaited_once()
