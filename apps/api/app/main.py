from fastapi import FastAPI
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from app.database import engine
from pathlib import Path
from alembic.config import Config
from alembic.script import ScriptDirectory

from app.routers import forecasts, matches, research, live


app = FastAPI(
    title="ClutchQuant API",
    version="0.1.0",
)

app.include_router(matches.router)
app.include_router(forecasts.router)
app.include_router(research.router)
app.include_router(live.router)


@app.get("/api/v1/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "clutchquant-api",
        "version": "0.1.0",
    }


@app.get("/api/v1/ready")
def readiness():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            revision = connection.scalar(text("SELECT version_num FROM alembic_version"))
        expected_head = ScriptDirectory.from_config(Config(str(Path(__file__).resolve().parents[1]/"alembic.ini"))).get_current_head()
        if revision != expected_head:
            raise HTTPException(status_code=503,detail="Database migrations required.")
    except SQLAlchemyError as error:
        raise HTTPException(status_code=503,detail="Database unavailable.") from error
    return {"status":"ready","database":"connected","revision":revision}
