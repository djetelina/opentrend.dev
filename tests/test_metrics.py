from opentrend.metrics import (
    instrumented_client,
)


def test_instrumented_client_preserves_kwargs() -> None:
    """Verify that extra kwargs like headers are passed through."""
    session = instrumented_client(
        headers={"User-Agent": "test"},
    )
    assert session.headers["User-Agent"] == "test"


def test_instrumented_client_has_metrics_hooks() -> None:
    """Verify that metrics hooks are registered on the session."""
    session = instrumented_client()
    assert len(session.hooks["pre_request"]) > 0
    assert len(session.hooks["response"]) > 0
