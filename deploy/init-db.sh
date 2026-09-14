#!/bin/sh
set -eu
# Runs only on a fresh PostgreSQL volume; passwords are psql variables, not SQL interpolation.
psql --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" --set ON_ERROR_STOP=1 --set app_password="$APP_DB_PASSWORD" <<'SQL'
CREATE ROLE cq_app LOGIN PASSWORD :'app_password';
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT CONNECT ON DATABASE clutchquant TO cq_app;
GRANT USAGE ON SCHEMA public TO cq_app;
ALTER DEFAULT PRIVILEGES FOR ROLE cq_owner IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO cq_app;
ALTER DEFAULT PRIVILEGES FOR ROLE cq_owner IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO cq_app;
SQL
