"""Add provenance without inventing availability for existing records.

Revision ID: a21d7b643f90
Revises: f0a4c2d8e613
"""

from alembic import op
import sqlalchemy as sa

revision = "a21d7b643f90"
down_revision = "f0a4c2d8e613"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "match_observations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("match_id", sa.Integer(), sa.ForeignKey("matches.id"), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("raw_sha256", sa.String(64), nullable=False),
        sa.Column("source_url", sa.String(1000), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
    )
    op.create_index("ix_match_observations_match_id", "match_observations", ["match_id"])
    op.create_table(
        "model_runs",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("source_key", sa.String(150), nullable=False),
        sa.Column("dataset_sha256", sa.String(64), nullable=False),
        sa.Column("configuration", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.add_column("forecasts", sa.Column("model_run_id", sa.String(64), nullable=True))
    op.create_foreign_key("fk_forecasts_model_run", "forecasts", "model_runs", ["model_run_id"], ["id"])
    op.execute("""CREATE FUNCTION cq_reject_history_mutation() RETURNS trigger
    LANGUAGE plpgsql AS $$ BEGIN
      RAISE EXCEPTION 'Historical records are append-only';
    END $$""")
    for table in ("forecasts", "match_observations", "model_runs"):
        op.execute(f"CREATE TRIGGER cq_append_only BEFORE UPDATE OR DELETE ON {table} "
                   "FOR EACH ROW EXECUTE FUNCTION cq_reject_history_mutation()")


def downgrade():
    for table in ("forecasts", "match_observations", "model_runs"):
        op.execute(f"DROP TRIGGER cq_append_only ON {table}")
    op.execute("DROP FUNCTION cq_reject_history_mutation()")
    op.drop_constraint("fk_forecasts_model_run", "forecasts", type_="foreignkey")
    op.drop_column("forecasts", "model_run_id")
    op.drop_table("model_runs")
    op.drop_index("ix_match_observations_match_id", table_name="match_observations")
    op.drop_table("match_observations")
