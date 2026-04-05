import uuid

from opentrend.scheduler.jobs import compute_collection_hour


def _uuid(n: int) -> uuid.UUID:
    return uuid.UUID(int=n)


def test_compute_collection_hour_deterministic() -> None:
    pid = _uuid(1)
    hour1 = compute_collection_hour(pid)
    hour2 = compute_collection_hour(pid)
    assert hour1 == hour2


def test_compute_collection_hour_in_range() -> None:
    for i in range(1, 100):
        hour = compute_collection_hour(_uuid(i))
        assert 0 <= hour < 24


def test_compute_collection_hour_distributes() -> None:
    hours = {compute_collection_hour(_uuid(i)) for i in range(1, 50)}
    # Should hit at least 10 different hours with 49 projects
    assert len(hours) >= 10
