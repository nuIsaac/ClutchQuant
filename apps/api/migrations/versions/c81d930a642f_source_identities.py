"""Add source mappings without changing canonical IDs or availability evidence."""
from alembic import op
import sqlalchemy as sa

revision = "c81d930a642f"
down_revision = "b72c904e1a36"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("team_source_identities",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("team_id", sa.Integer(), sa.ForeignKey("teams.id"), nullable=False),
        sa.Column("source", sa.String(30), nullable=False),
        sa.Column("external_id", sa.String(100), nullable=False),
        sa.Column("external_name", sa.String(100), nullable=False),
        sa.UniqueConstraint("source", "external_id", name="uq_team_source_external"))
    op.create_index("ix_team_source_identities_team_id", "team_source_identities", ["team_id"])
    op.create_table("team_aliases",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("team_id", sa.Integer(), sa.ForeignKey("teams.id"), nullable=False),
        sa.Column("source", sa.String(30), nullable=False),
        sa.Column("alias", sa.String(100), nullable=False),
        sa.Column("normalized_alias", sa.String(100), nullable=False),
        sa.UniqueConstraint("team_id", "source", "normalized_alias", name="uq_team_alias"))
    op.create_index("ix_team_aliases_normalized_alias", "team_aliases", ["normalized_alias"])
    op.create_table("match_sources",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("match_id", sa.Integer(), sa.ForeignKey("matches.id"), nullable=False),
        sa.Column("source", sa.String(30), nullable=False),
        sa.Column("external_id", sa.String(100), nullable=False),
        sa.Column("source_url", sa.String(1000), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True)),
        sa.Column("last_seen_at", sa.DateTime(timezone=True)),
        sa.Column("last_synced_at", sa.DateTime(timezone=True)),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.UniqueConstraint("source", "external_id", name="uq_match_source_external"))
    op.create_index("ix_match_sources_match_id", "match_sources", ["match_id"])
    op.create_table("source_issues",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("issue_key", sa.String(64), nullable=False, unique=True),
        sa.Column("source", sa.String(30), nullable=False),
        sa.Column("external_id", sa.String(100), nullable=False),
        sa.Column("match_id", sa.Integer(), sa.ForeignKey("matches.id")),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True)))
    op.create_index("ix_source_issues_kind", "source_issues", ["kind"])
    op.execute("""INSERT INTO team_source_identities (team_id, source, external_id, external_name)
                  SELECT id, 'vlr', CAST(vlr_id AS VARCHAR), name FROM teams WHERE vlr_id IS NOT NULL""")
    op.execute("""INSERT INTO match_sources (match_id, source, external_id, source_url, details)
                  SELECT id, 'vlr', CAST(vlr_id AS VARCHAR),
                         'https://www.vlr.gg/' || CAST(vlr_id AS VARCHAR),
                         '{"legacy": true}'::json FROM matches WHERE vlr_id IS NOT NULL""")

    # Supabase may grant new public tables to anon/authenticated by default.
    # Secure new tables atomically with creation; reuse existing roles only.
    op.execute("""
    DO $$
    DECLARE tab text; role_name text; ns text := current_schema();
    BEGIN
      FOREACH tab IN ARRAY ARRAY['team_source_identities','team_aliases','match_sources','source_issues'] LOOP
        EXECUTE format('ALTER TABLE %I.%I ENABLE ROW LEVEL SECURITY', ns, tab);
        EXECUTE format('REVOKE ALL ON %I.%I FROM PUBLIC', ns, tab);
        FOREACH role_name IN ARRAY ARRAY['anon','authenticated'] LOOP
          IF EXISTS (SELECT FROM pg_roles WHERE rolname = role_name) THEN
            EXECUTE format('REVOKE ALL ON %I.%I FROM %I', ns, tab, role_name);
          END IF;
        END LOOP;
        IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'cq_demo_api') THEN
          EXECUTE format('GRANT SELECT ON %I.%I TO cq_demo_api', ns, tab);
          EXECUTE format('CREATE POLICY cq_demo_read ON %I.%I FOR SELECT TO cq_demo_api USING (true)', ns, tab);
        END IF;
        IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'cq_app') THEN
          EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON %I.%I TO cq_app', ns, tab);
          EXECUTE format('CREATE POLICY cq_app_write ON %I.%I TO cq_app USING (true) WITH CHECK (true)', ns, tab);
          EXECUTE format('GRANT USAGE, SELECT ON SEQUENCE %I.%I TO cq_app', ns, tab || '_id_seq');
        END IF;
        IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'cq_demo_worker') THEN
          EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON %I.%I TO cq_demo_worker', ns, tab);
          EXECUTE format('CREATE POLICY cq_demo_write ON %I.%I TO cq_demo_worker USING (true) WITH CHECK (true)', ns, tab);
          EXECUTE format('GRANT USAGE, SELECT ON SEQUENCE %I.%I TO cq_demo_worker', ns, tab || '_id_seq');
        END IF;
      END LOOP;
    END $$;
    """)


def downgrade():
    # Export these provenance tables before an intentional downgrade.
    for name in ("source_issues", "match_sources", "team_aliases", "team_source_identities"):
        op.drop_table(name)
