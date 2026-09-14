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
