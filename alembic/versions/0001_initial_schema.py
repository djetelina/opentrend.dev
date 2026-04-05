"""Initial schema — consolidated from 13 migrations

Revision ID: 0001
Revises: (none)
Create Date: 2026-04-06
"""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── users ──
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("github_id", sa.BigInteger(), nullable=False, unique=True),
        sa.Column("github_username", sa.String(255), nullable=False),
        sa.Column("avatar_url", sa.String(500), nullable=False),
        sa.Column("github_access_token", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_users_github_id", "users", ["github_id"])

    # ── projects ──
    op.create_table(
        "projects",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("github_repo", sa.String(255), nullable=False, unique=True),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("description", sa.String(1000), nullable=False, server_default=""),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_projects_user_id", "projects", ["user_id"])

    # ── package_mappings ──
    op.create_table(
        "package_mappings",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "project_id",
            sa.Uuid(),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("package_name", sa.String(255), nullable=False),
        sa.UniqueConstraint("project_id", "source", "package_name"),
    )
    op.create_index(
        "ix_package_mappings_project_id", "package_mappings", ["project_id"]
    )

    # ── github_snapshots ──
    op.create_table(
        "github_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "project_id",
            sa.Uuid(),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("stars", sa.Integer(), nullable=False),
        sa.Column("forks", sa.Integer(), nullable=False),
        sa.Column("open_issues", sa.Integer(), nullable=False),
        sa.Column("closed_issues", sa.Integer(), nullable=False),
        sa.Column("open_prs", sa.Integer(), nullable=False),
        sa.Column("closed_prs", sa.Integer(), nullable=False),
        sa.Column("contributors", sa.Integer(), nullable=False),
        sa.Column("commits_total", sa.Integer(), nullable=False),
        sa.Column("latest_release_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("latest_release_tag", sa.String(100), nullable=True),
        sa.Column("release_count", sa.Integer(), nullable=False),
        sa.Column("watchers", sa.Integer(), nullable=False),
        sa.Column("license", sa.String(100), nullable=True),
        sa.Column("weekly_commits", sa.Text(), nullable=True),
        sa.Column("weekly_code_frequency", sa.Text(), nullable=True),
        sa.Column("weekly_owner_commits", sa.Text(), nullable=True),
        sa.Column("weekly_all_commits", sa.Text(), nullable=True),
        sa.Column("community_health", sa.Integer(), nullable=True),
        sa.Column("reach_score", sa.Integer(), nullable=True),
        sa.Column("dependents_repos", sa.Integer(), nullable=True),
        sa.Column("dependents_packages", sa.Integer(), nullable=True),
        sa.UniqueConstraint("project_id", "date"),
    )
    op.create_index(
        "ix_github_snapshots_project_id", "github_snapshots", ["project_id"]
    )

    # ── package_snapshots ──
    op.create_table(
        "package_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "package_mapping_id",
            sa.Integer(),
            sa.ForeignKey("package_mappings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("downloads_daily", sa.Integer(), nullable=True),
        sa.Column("downloads_weekly", sa.Integer(), nullable=True),
        sa.Column("downloads_monthly", sa.Integer(), nullable=True),
        sa.Column("latest_version", sa.String(100), nullable=True),
        sa.Column("version_count", sa.Integer(), nullable=True),
        sa.Column("popularity", sa.Float(), nullable=True),
        sa.Column("votes", sa.Integer(), nullable=True),
        sa.Column("downloads_total", sa.Integer(), nullable=True),
        sa.Column("dependents_count", sa.Integer(), nullable=True),
        sa.UniqueConstraint("package_mapping_id", "date"),
    )
    op.create_index(
        "ix_package_snapshots_package_mapping_id",
        "package_snapshots",
        ["package_mapping_id"],
    )

    # ── release_download_snapshots ──
    op.create_table(
        "release_download_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "project_id",
            sa.Uuid(),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("release_tag", sa.String(100), nullable=False),
        sa.Column("asset_name", sa.String(255), nullable=False),
        sa.Column("download_count", sa.Integer(), nullable=False),
        sa.UniqueConstraint("project_id", "date", "release_tag", "asset_name"),
    )
    op.create_index(
        "ix_release_download_snapshots_project_id",
        "release_download_snapshots",
        ["project_id"],
    )

    # ── traffic_snapshots ──
    op.create_table(
        "traffic_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "project_id",
            sa.Uuid(),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("clones", sa.Integer(), nullable=False),
        sa.Column("unique_clones", sa.Integer(), nullable=False),
        sa.Column("views", sa.Integer(), nullable=False),
        sa.Column("unique_views", sa.Integer(), nullable=False),
        sa.UniqueConstraint("project_id", "date"),
    )
    op.create_index(
        "ix_traffic_snapshots_project_id", "traffic_snapshots", ["project_id"]
    )

    # ── traffic_referrer_snapshots ──
    op.create_table(
        "traffic_referrer_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "project_id",
            sa.Uuid(),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("referrer", sa.String(255), nullable=False),
        sa.Column("views", sa.Integer(), nullable=False),
        sa.Column("unique_visitors", sa.Integer(), nullable=False),
        sa.UniqueConstraint("project_id", "date", "referrer"),
    )
    op.create_index(
        "ix_traffic_referrer_snapshots_project_id",
        "traffic_referrer_snapshots",
        ["project_id"],
    )


def downgrade() -> None:
    op.drop_table("traffic_referrer_snapshots")
    op.drop_table("traffic_snapshots")
    op.drop_table("release_download_snapshots")
    op.drop_table("package_snapshots")
    op.drop_table("github_snapshots")
    op.drop_table("package_mappings")
    op.drop_table("projects")
    op.drop_table("users")
