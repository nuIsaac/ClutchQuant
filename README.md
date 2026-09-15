# ClutchQuant

Valorant forecasting and model evaluation platform.

**[View live demo →](https://clutch-quant.vercel.app)**

ClutchQuant estimates match win probabilities from historical Valorant results and
versioned models. Current research previews are separate from frozen forecasts used
for prospective evaluation.

## What it does

- Shows current Elo probabilities for upcoming matches, grouped by event.
- Collects schedules and results from VLR.
- Saves prospective forecasts before matches start and never overwrites them.
- Scores verified outcomes with accuracy, Brier score and log loss.
- Keeps raw evidence, dataset hashes and model-run records for auditing.

## Why I built it

I've competed at a high level in Valorant, reached the top 25 on the NA leaderboard,
led teams and spent a lot of time analyzing matches. ClutchQuant started as a way
to turn that experience into something measurable, while building the data pipeline
and forecasting tools behind it.

## Architecture

```text
VLR → Python collection → Supabase Postgres + private evidence storage
                              ↓
                    GitHub Actions: freeze and score
                              ↓
Historical research snapshot → FastAPI / Render → Next.js / Vercel
```

`apps/api` contains ingestion, models, migrations, evaluation and the API.
`apps/web` contains the frontend. GitHub Actions runs the prospective cycle every
three hours at minute 17 UTC; the local worker can run continuously.

## Model

Elo v1 uses a 1500 starting rating, K=32 and a 400-point scale.

The **current research model** replays a versioned snapshot of roughly 30,000
completed, decisive series, merged with current database results. Teams are matched
by VLR ID. Tied results are excluded; unseen teams start at 1500.

**Prospective forecasts** use evidence available before they are frozen. Their saved
probabilities and provenance do not change when the research model updates. Only
these forecasts contribute to prospective accuracy, Brier score and log loss.

Most historical results lack original availability evidence. Research previews do
not claim that their inputs or probabilities were known before those matches.
Experimental models exist in the research code but have not been promoted.

See the [preview design](docs/decisions/004-current-research-preview.md) and
[observation-time evaluation rules](docs/decisions/002-observation-time-research.md).

## Data pipeline

Each collection saves the raw response and a timestamped observation. The scheduled
cycle syncs upcoming matches, freezes eligible forecasts, collects completed results
and scores saved forecasts. Dataset and model-run hashes link predictions to their
inputs. Database constraints and an advisory lock protect against duplicate and
overlapping runs.

## Tech stack

Next.js, React, TypeScript, Tailwind · Python, FastAPI, SQLAlchemy, Alembic ·
PostgreSQL · Docker · GitHub Actions

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

The [live demo](https://clutch-quant.vercel.app) uses Vercel Hobby, Render Free,
Supabase Free Postgres/private Storage and scheduled GitHub Actions. Credentials
live in provider settings and repository secrets, not source control.

See [deployment setup and free-tier limits](docs/free-demo.md). Render can sleep;
the first request may need a retry. Scheduled collection can be delayed or miss
matches, and storage and runner quotas still apply.

## Current status

The public demo is live. The prospective pipeline is collecting data, but its
verified sample is still small. Evaluation remains preliminary; the historical
research dataset is not a substitute for prospective results.
