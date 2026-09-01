from fastapi import FastAPI

from app.routers import forecasts, matches


app = FastAPI(
    title="ClutchQuant API",
    version="0.1.0",
)

app.include_router(matches.router)
app.include_router(forecasts.router)


@app.get("/api/v1/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "clutchquant-api",
        "version": "0.1.0",
    }