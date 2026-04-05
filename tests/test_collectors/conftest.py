import json as json_mod

import pytest
import niquests


@pytest.fixture()
def mock_response():
    """Helper to build niquests.Response objects for testing."""

    def _make(
        status_code: int = 200, json_data: dict | list | None = None
    ) -> niquests.Response:
        resp = niquests.Response()
        resp.status_code = status_code
        if json_data is not None:
            resp._content = json_mod.dumps(json_data).encode()
            resp.headers["Content-Type"] = "application/json"
        return resp

    return _make
