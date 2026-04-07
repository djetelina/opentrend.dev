import uuid
from datetime import date, datetime

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from opentrend.models.base import Base


class GithubSnapshot(Base):
    __tablename__ = "github_snapshots"
    __table_args__ = (UniqueConstraint("project_id", "date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    date: Mapped[date] = mapped_column(Date)
    stars: Mapped[int] = mapped_column(Integer)
    forks: Mapped[int] = mapped_column(Integer)
    open_issues: Mapped[int] = mapped_column(Integer)  # GitHub counts PRs as issues
    closed_issues: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    open_prs: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    closed_prs: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    contributors: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    commits_total: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    latest_release_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    latest_release_tag: Mapped[str | None] = mapped_column(String(100), nullable=True)
    release_count: Mapped[int] = mapped_column(Integer)
    watchers: Mapped[int] = mapped_column(Integer)
    license: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # GitHub stats API data (JSON arrays covering last 52 weeks)
    # Schema: list[{"week": int, "total": int}]
    weekly_commits: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Schema: list[[timestamp: int, additions: int, deletions: int]]
    weekly_code_frequency: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Schema: list[int] — commit counts per week for repo owner
    weekly_owner_commits: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Schema: list[int] — commit counts per week for all non-bot contributors
    weekly_all_commits: Mapped[str | None] = mapped_column(Text, nullable=True)
    community_health: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reach_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dependents_repos: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dependents_packages: Mapped[int | None] = mapped_column(Integer, nullable=True)


class PackageSnapshot(Base):
    __tablename__ = "package_snapshots"
    __table_args__ = (UniqueConstraint("package_mapping_id", "date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    package_mapping_id: Mapped[int] = mapped_column(
        ForeignKey("package_mappings.id", ondelete="CASCADE"), index=True
    )
    date: Mapped[date] = mapped_column(Date)
    downloads_daily: Mapped[int | None] = mapped_column(Integer, nullable=True)
    downloads_weekly: Mapped[int | None] = mapped_column(Integer, nullable=True)
    downloads_monthly: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latest_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    version_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    popularity: Mapped[float | None] = mapped_column(nullable=True)
    votes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    downloads_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dependents_count: Mapped[int | None] = mapped_column(Integer, nullable=True)


class ReleaseDownloadSnapshot(Base):
    __tablename__ = "release_download_snapshots"
    __table_args__ = (
        UniqueConstraint("project_id", "date", "release_tag", "asset_name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    date: Mapped[date] = mapped_column(Date)
    release_tag: Mapped[str] = mapped_column(String(100))
    asset_name: Mapped[str] = mapped_column(String(255))
    download_count: Mapped[int] = mapped_column(Integer)


class TrafficSnapshot(Base):
    __tablename__ = "traffic_snapshots"
    __table_args__ = (UniqueConstraint("project_id", "date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    date: Mapped[date] = mapped_column(Date)
    clones: Mapped[int] = mapped_column(Integer)
    unique_clones: Mapped[int] = mapped_column(Integer)
    views: Mapped[int] = mapped_column(Integer)
    unique_views: Mapped[int] = mapped_column(Integer)


class TrafficReferrerSnapshot(Base):
    __tablename__ = "traffic_referrer_snapshots"
    __table_args__ = (UniqueConstraint("project_id", "date", "referrer"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    date: Mapped[date] = mapped_column(Date)
    referrer: Mapped[str] = mapped_column(String(255))
    views: Mapped[int] = mapped_column(Integer)
    unique_visitors: Mapped[int] = mapped_column(Integer)
