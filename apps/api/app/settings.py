"""Environment configuration shared by API, jobs, and migrations."""

import os
from pathlib import Path

APP_ENV = os.getenv("APP_ENV", "development")
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    if APP_ENV != "development":
        raise RuntimeError("DATABASE_URL must be set outside development")
    DATABASE_URL = "postgresql+psycopg://clutchquant:clutchquant_local@localhost:5432/clutchquant"

ARTIFACT_ROOT = Path(os.getenv(
    "ARTIFACT_ROOT", str(Path(__file__).resolve().parents[1] / "artifacts")
)).resolve()
HUMAN_FORECAST_TOKEN = os.getenv("HUMAN_FORECAST_TOKEN")
ARTIFACT_BACKEND = os.getenv("ARTIFACT_BACKEND", "local")
SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
SUPABASE_ARTIFACT_BUCKET = os.getenv("SUPABASE_ARTIFACT_BUCKET", "clutchquant-artifacts")
ARTIFACT_READ_ONLY = os.getenv("ARTIFACT_READ_ONLY", "false").lower() == "true"
if ARTIFACT_BACKEND not in {"local", "supabase"}:
    raise RuntimeError("ARTIFACT_BACKEND must be local or supabase")
if ARTIFACT_BACKEND == "supabase" and (not SUPABASE_URL.startswith("https://") or not SUPABASE_SERVICE_ROLE_KEY):
    raise RuntimeError("Supabase artifact storage requires an HTTPS URL and server-only service role key")
