# ClutchQuant

Valorant match probabilities, before and during play.

**[View live demo →](https://clutch-quant.vercel.app)**

ClutchQuant turns Valorant match history and game state into win probabilities.
It shows pre-match Elo estimates and score-conditioned live estimates when VLR
supplies a valid live state.

## What it does

- Pre-match probabilities, team ratings and tournament filters.
- Live map and series probabilities from actual source scores.
- VLR ingestion, normalized match storage and leakage-aware model evaluation.

## Why I built it

I've competed at a high level in Valorant, reached the top 25 on the NA leaderboard,
led teams and spent a lot of time analyzing matches. ClutchQuant started as a way
to turn that experience into something measurable, while building the data pipeline
and forecasting tools behind it.

## Architecture

```text
VLR → Python collection → Supabase Postgres + private evidence storage
                              ↓
                    Scheduled collection / models
                              ↓
Historical research snapshot → FastAPI / Render → Next.js / Vercel
```

`apps/api` contains ingestion, models, migrations, evaluation and the API.
`apps/web` contains the frontend.

## Models

**Pre-match:** Elo v1, with a 1500 starting rating, K=32 and a 400-point scale.
A versioned snapshot of roughly 30,000 decisive series is merged with current
results. Teams use VLR identities; unknown teams keep the starting prior.

**Live:** a dynamic-programming model computes the chance of winning the current
map, then the series. It handles first-to-13 regulation, two-round overtime wins
and BO1/BO3/BO5. Winning a round changes the probability according to the score
and remaining paths to victory, rather than adding a fixed percentage.

Per-round strength is inferred by inverting the pre-match series prior. A diagnostic
fit on 591 historical maps is documented, but not promoted as a validated live
model. Economy, map-specific strength and measured side advantages are not modeled.
Historical availability is incomplete; backtest diagnostics are not live validation.

See the [live model design](docs/decisions/005-live-probability.md) and
[research snapshot design](docs/decisions/004-current-research-preview.md).

## Data pipeline

Python collectors ingest VLR into PostgreSQL through SQLAlchemy. Alembic manages
the schema. GitHub Actions runs scheduled collection every three hours at minute
17 UTC; the local worker can run continuously. Raw evidence lives in private
Supabase Storage. Internal evaluation records remain immutable.

The live API uses a separate read-only source cache: 30-second refreshes while
matches are active, five minutes when idle, and up to four active matches per
refresh. Missing round scores are labeled; source failures do not become fake
live probabilities. Refreshes happen only while the API is being requested.

## Stack

Next.js, React, TypeScript, Tailwind; Python, FastAPI, SQLAlchemy, Alembic;
PostgreSQL, Docker, GitHub Actions. Offline research uses scikit-learn.

## Running locally

Requires Python 3.12, Node 24 and Docker. These commands use PowerShell.

```powershell
# Repository root: start local PostgreSQL
docker compose up -d

cd apps/api
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements-dev.txt -c requirements.lock
# Development defaults target the database in compose.yaml.
# Set DATABASE_URL explicitly if using another database.
.venv/Scripts/python.exe -m alembic current
.venv/Scripts/python.exe -m alembic upgrade head
.venv/Scripts/python.exe -m uvicorn app.main:app --reload
```

In another terminal:

```powershell
cd apps/web
npm ci
npm run dev
```

Open `http://localhost:3000`. The frontend defaults to the local API at
`http://127.0.0.1:8000/api/v1`; override `API_URL` in `apps/web/.env.local` if needed.
The bundled snapshot supplies research history. Upcoming matches require ingestion:
from `apps/api`, run `.venv/Scripts/python.exe -m app.pipeline --once --demo-cycle --pages 1`.
Never point a development command at the live database by accident.

For worker operation, tests and evidence storage, see the [runbook](docs/runbook.md).

## Deployment

Hosting uses Vercel Hobby, Render Free,
Supabase Free Postgres/private Storage and scheduled GitHub Actions. Credentials
live in provider settings and repository secrets, not source control.

See [deployment setup and free-tier limits](docs/free-demo.md). Render can sleep;
the first request may need a retry. Scheduled collection can be delayed or miss
matches, and storage and runner quotas still apply. Live round coverage depends on VLR;
the integration is not a low-latency official data feed.
