"""Idempotent observation receipts and append-only pipeline run receipts."""
from alembic import op
import sqlalchemy as sa

revision = "b72c904e1a36"
down_revision = "a21d7b643f90"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("match_observations", sa.Column("evidence_key", sa.String(64), nullable=True))
    op.create_unique_constraint("uq_match_observations_evidence_key", "match_observations", ["evidence_key"])
    op.create_table("pipeline_runs",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("report_sha256", sa.String(64), nullable=True),
        sa.Column("details", sa.JSON(), nullable=False))
    op.create_index("ix_pipeline_runs_started_at", "pipeline_runs", ["started_at"])
    op.execute("CREATE TRIGGER cq_append_only BEFORE UPDATE OR DELETE ON pipeline_runs "
               "FOR EACH ROW EXECUTE FUNCTION cq_reject_history_mutation()")


def downgrade():
    op.drop_table("pipeline_runs")
    op.drop_constraint("uq_match_observations_evidence_key", "match_observations", type_="unique")
    op.drop_column("match_observations", "evidence_key")
