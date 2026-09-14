"""Allow different VLR teams to share a display name.

Revision ID: f0a4c2d8e613
Revises: eaf7597a5438

Team identity remains unique by VLR ID. Existing rows are preserved.
Downgrade restores the original PostgreSQL constraint and fails if duplicate
names have since been ingested; resolve those records explicitly before
downgrading. This migration never deletes or merges teams automatically.
"""

from alembic import op


revision = "f0a4c2d8e613"
down_revision = "eaf7597a5438"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # PostgreSQL assigned this name to the unnamed unique constraint in
    # 6ee2c4c7ed2b_create_teams_table.py.
    op.drop_constraint("teams_name_key", "teams", type_="unique")


def downgrade() -> None:
    op.create_unique_constraint("teams_name_key", "teams", ["name"])
