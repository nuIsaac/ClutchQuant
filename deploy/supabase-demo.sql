-- Run as project postgres AFTER Alembic, in a dedicated demo project.
-- Passwords are deliberately absent. Assign LOGIN/passwords separately in a
-- private administrator session; never paste credentials into tracked files.
DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'cq_demo_api') THEN
    CREATE ROLE cq_demo_api NOLOGIN;
  END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'cq_demo_worker') THEN
    CREATE ROLE cq_demo_worker NOLOGIN;
  END IF;
END $$;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO cq_demo_api, cq_demo_worker;
DO $$
DECLARE tab text;
BEGIN
  FOREACH tab IN ARRAY ARRAY['teams','players','matches','match_maps',
    'player_map_stats','forecasts','match_observations','model_runs',
    'pipeline_runs','alembic_version'] LOOP
    EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', tab);
    EXECUTE format('REVOKE ALL ON public.%I FROM PUBLIC', tab);
    IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'anon') THEN
      EXECUTE format('REVOKE ALL ON public.%I FROM anon', tab);
    END IF;
    IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'authenticated') THEN
      EXECUTE format('REVOKE ALL ON public.%I FROM authenticated', tab);
    END IF;
    EXECUTE format('GRANT SELECT ON public.%I TO cq_demo_api', tab);
    EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON public.%I TO cq_demo_worker', tab);
    EXECUTE format('DROP POLICY IF EXISTS cq_demo_read ON public.%I', tab);
    EXECUTE format('CREATE POLICY cq_demo_read ON public.%I FOR SELECT TO cq_demo_api USING (true)', tab);
    EXECUTE format('DROP POLICY IF EXISTS cq_demo_write ON public.%I', tab);
    EXECUTE format('CREATE POLICY cq_demo_write ON public.%I TO cq_demo_worker USING (true) WITH CHECK (true)', tab);
  END LOOP;
END $$;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO cq_demo_worker;
REVOKE INSERT, UPDATE, DELETE ON public.alembic_version FROM cq_demo_worker;
