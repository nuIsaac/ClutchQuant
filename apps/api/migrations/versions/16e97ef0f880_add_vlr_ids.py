"""add vlr ids

Revision ID: 16e97ef0f880
Revises: cb0a8dc8d020
Create Date: 2026-08-28 17:58:34.365856

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "16e97ef0f880"
down_revision: Union[str, Sequence[str], None] = "cb0a8dc8d020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "players",
        sa.Column("vlr_id", sa.Integer(), nullable=True),
    )
    op.create_unique_constraint(
        "uq_players_vlr_id",
        "players",
        ["vlr_id"],
    )

    op.add_column(
        "teams",
        sa.Column("vlr_id", sa.Integer(), nullable=True),
    )
    op.create_unique_constraint(
        "uq_teams_vlr_id",
        "teams",
        ["vlr_id"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        "uq_teams_vlr_id",
        "teams",
        type_="unique",
    )
    op.drop_column("teams", "vlr_id")

    op.drop_constraint(
        "uq_players_vlr_id",
        "players",
        type_="unique",
    )
    op.drop_column("players", "vlr_id")