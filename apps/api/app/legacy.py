"""Persistence compatibility only; never use these identifiers as display branding.

Existing databases and immutable artifact buckets are not renamed by deployment.
See docs/rebrand-compatibility.md before changing any value.
"""
LOCAL_DATABASE_URL = "postgresql+psycopg://clutchquant:clutchquant_local@localhost:5432/clutchquant"
ARTIFACT_BUCKET = "clutchquant-artifacts"
