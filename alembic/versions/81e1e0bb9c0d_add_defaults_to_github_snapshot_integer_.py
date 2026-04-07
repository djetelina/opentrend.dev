"""add defaults to github snapshot integer columns

Revision ID: 81e1e0bb9c0d
Revises: d625d4d78acf
Create Date: 2026-04-07 11:49:41.370868

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "81e1e0bb9c0d"
down_revision: Union[str, Sequence[str], None] = "d625d4d78acf"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    for col in (
        "closed_issues",
        "open_prs",
        "closed_prs",
        "contributors",
        "commits_total",
    ):
        op.alter_column(
            "github_snapshots",
            col,
            server_default="0",
        )


def downgrade() -> None:
    """Downgrade schema."""
    for col in (
        "closed_issues",
        "open_prs",
        "closed_prs",
        "contributors",
        "commits_total",
    ):
        op.alter_column(
            "github_snapshots",
            col,
            server_default=None,
        )
