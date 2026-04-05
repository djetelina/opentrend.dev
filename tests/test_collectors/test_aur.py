from opentrend.collectors.aur import AURCollector


def test_parse_aur_response() -> None:
    data = {
        "results": [
            {
                "Name": "python-httpx",
                "Version": "0.27.0-1",
                "NumVotes": 42,
                "Popularity": 3.14,
                "OutOfDate": None,
                "Maintainer": "somebody",
            }
        ]
    }
    collector = AURCollector()
    info = collector.parse_aur(data)
    assert info["version"] == "0.27.0-1"
    assert info["votes"] == 42
    assert info["popularity"] == 3.14
    assert info["out_of_date"] is False


def test_parse_aur_out_of_date() -> None:
    data = {
        "results": [
            {
                "Name": "python-httpx",
                "Version": "0.26.0-1",
                "NumVotes": 42,
                "Popularity": 3.14,
                "OutOfDate": 1700000000,
                "Maintainer": "somebody",
            }
        ]
    }
    collector = AURCollector()
    info = collector.parse_aur(data)
    assert info["out_of_date"] is True


def test_parse_aur_not_found() -> None:
    data = {"results": []}
    collector = AURCollector()
    assert collector.parse_aur(data) is None
