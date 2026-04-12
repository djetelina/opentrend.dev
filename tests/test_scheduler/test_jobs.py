import uuid

from opentrend.scheduler.jobs import compute_collection_time


def _uuid(n: int) -> uuid.UUID:
    return uuid.UUID(int=n)


def test_compute_collection_time_deterministic() -> None:
    pid = _uuid(1)
    assert compute_collection_time(pid) == compute_collection_time(pid)


def test_compute_collection_time_in_range() -> None:
    for i in range(1, 100):
        hour, minute = compute_collection_time(_uuid(i))
        assert 0 <= hour < 24
        assert 0 <= minute < 60


def test_compute_collection_time_distributes() -> None:
    times = {compute_collection_time(_uuid(i)) for i in range(1, 50)}
    # With 49 projects spread across 1440 minute-slots, most should be unique
    assert len(times) >= 30
