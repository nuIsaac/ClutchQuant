# ClutchQuant engineering rules

- Preserve raw data, unknown identities, and historical forecast/model versions.
- Elo v1 in `app/research/elo.py` is frozen (1500, K=32, scale=400).
- No result/feature may enter a prediction until supported availability evidence
  precedes prediction time. Scheduled start is not result availability.
- Never invent historical ingestion/availability times or promote a model from
  assumption-based or synthetic performance. Label blocked evaluation explicitly.
- Use chronological validation, disjoint tuning/holdout periods, and probability
  metrics alongside accuracy. Keep candidate sets small and documented.
- Preserve the user's API_URL environment configuration.
- Run backend tests, frontend tests/lint/typecheck/build for relevant changes.
- Use the API virtual environment in `apps/api/.venv` locally. PostgreSQL tests
  require TEST_DATABASE_URL and must isolate changes from application tables.
- Do not push, purchase infrastructure, or silently change environment targets.
