from fastapi import FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from app.database import engine
from pathlib import Path
from alembic.config import Config
from alembic.script import ScriptDirectory

from app.routers import forecasts, matches, research, live, sources


app = FastAPI(
    title="ClutchQuant API",
    version="0.1.0",
)

app.include_router(matches.router)
app.include_router(forecasts.router)
app.include_router(research.router)
app.include_router(live.router)
app.include_router(sources.router)


@app.get("/health")
@app.get("/api/v1/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "clutchquant-api",
        "version": "0.1.0",
    }


@app.get("/ready")
@app.get("/api/v1/ready")
def readiness():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            revision = connection.scalar(text("SELECT version_num FROM alembic_version"))
        expected_head = ScriptDirectory.from_config(Config(str(Path(__file__).resolve().parents[1]/"alembic.ini"))).get_current_head()
        if revision != expected_head:
            return JSONResponse(status_code=503, content={"status": "starting", "database": "migrations_required"}, headers={"Retry-After": "5"})
    except SQLAlchemyError as error:
        return JSONResponse(status_code=503, content={"status": "starting", "database": "unavailable"}, headers={"Retry-After": "5"})
    return {"status":"ready","database":"connected","revision":revision}
