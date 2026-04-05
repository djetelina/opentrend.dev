"""Shared TypedDict definitions for structured data flowing between services, routes, and templates."""

from datetime import date
from typing import TypedDict


class TimeSeriesPoint(TypedDict):
    date: str
    value: int | float | None


class NamedSeries(TypedDict):
    name: str
    data: list[TimeSeriesPoint]


class PackagingMatrixRow(TypedDict):
    source: str
    package_name: str
    version: str | None
    freshness: str
    votes: int | None
    popularity: float | None
    downloads_daily: int | None
    downloads_weekly: int | None
    downloads_monthly: int | None
    downloads_total: int | None
    dependents_count: int | None


class GithubDeltas(TypedDict, total=False):
    stars_delta: int
    forks_delta: int
    issues_delta: int


class ReleaseAsset(TypedDict):
    asset_name: str
    download_count: int


class ReleaseSummary(TypedDict):
    release_tag: str
    date: date
    total_downloads: int
    assets: list[ReleaseAsset]


class ReferrerAggregate(TypedDict):
    referrer: str
    views: int
    unique_visitors: int


class PackageSnapshotData(TypedDict, total=False):
    """Valid keyword arguments for upsert_package_snapshot."""

    downloads_daily: int | None
    downloads_weekly: int | None
    downloads_monthly: int | None
    latest_version: str | None
    version_count: int | None
    popularity: float | None
    votes: int | None
    downloads_total: int | None
    dependents_count: int | None
