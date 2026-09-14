"""Isolated production-stack drill. Requires Docker; never uses application data.

Builds release images unless --skip-build is supplied. All test state belongs to a
UUID Compose project; cleanup removes only that project's containers/volumes.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-build", action="store_true")
    args = parser.parse_args()
    project = "cqdeploytest" + uuid4().hex[:12]
    env = dict(os.environ, COMPOSE_PROJECT_NAME=project, RELEASE_TAG="deployment-test",
               POSTGRES_PASSWORD=uuid4().hex, APP_DB_PASSWORD=uuid4().hex,
               CADDY_SITE="http://caddy", ACME_EMAIL="test@example.invalid",
               DATA_DIR="/unused-test-path")
    with tempfile.TemporaryDirectory(prefix="cqdeploy-") as temporary:
        override = Path(temporary)/"override.yaml"
        override.write_text("""services:
  db:
    healthcheck:
      interval: 2s
    volumes: !override
      - testdb:/var/lib/postgresql/data
      - ./deploy/init-db.sh:/docker-entrypoint-initdb.d/10-clutchquant.sh:ro
  api:
    volumes: !override [testartifacts:/data/artifacts:ro]
    healthcheck:
      interval: 2s
  web:
    healthcheck:
      interval: 2s
  worker:
    volumes: !override [testartifacts:/data/artifacts]
    command: [python, -u, -m, app.pipeline, --no-collect, --interval-seconds, '60']
    healthcheck:
      disable: true
  caddy:
    ports: !override ['127.0.0.1::80']
    volumes: !override
      - ./deploy/Caddyfile:/etc/caddy/Caddyfile:ro
      - testcaddy:/data
volumes:
  testdb:
  testartifacts:
  testcaddy:
""",encoding="utf-8")
        base = ["docker","compose","-p",project,"-f",str(ROOT/"compose.production.yaml"),"-f",str(override)]

        def run(*command, check=True, data=None):
            result = subprocess.run(base+list(command),cwd=ROOT,env=env,input=data,
                                    stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            if check and result.returncode:
                raise RuntimeError(result.stderr.decode(errors="replace")[-4000:])
            return result

        try:
            run("config","--quiet")
            if not args.skip_build:
                print("Building production images",flush=True)
                run("build","api","web")
            run("up","-d","--wait","db")
            run("run","--rm","migrate")
            run("run","--rm","migrate","python","-m","alembic","check")
            # Application role can read/write rows, but cannot own/alter schema.
            run("run","--rm","--no-deps","worker","python","-c",
                "from app.database import engine; from sqlalchemy import text; "
                "c=engine.connect(); assert c.scalar(text('SELECT count(*) FROM forecasts'))==0; "
                "assert not c.scalar(text(\"SELECT has_schema_privilege(current_user,'public','CREATE')\"))")
            run("run","--rm","--no-deps","worker","python","-m","app.pipeline","--once","--demo-cycle","--no-collect")
            health = run("run","--rm","--no-deps","worker","python","-m","app.pipeline","--health",check=False)
            assert health.returncode == 1, "A smoke-only run must not imply healthy collection"
            run("up","-d","--wait","api","web","caddy")
            run("exec","-T","web","node","-e",
                "(async()=>{for(const p of ['/api/v1/ready','/api/v1/research/prospective','/']){"
                "const r=await fetch('http://caddy'+p);if(!r.ok)throw Error(p+' '+r.status)}"
                "const r=await fetch('http://caddy/api/v1/forecasts',{method:'POST'});"
                "if(r.status!==405)throw Error('Public write gate failed: '+r.status);"
                "const redir=await fetch('http://api:8000/api/v1/forecasts/',{redirect:'manual',headers:{'x-forwarded-proto':'https'}});"
                "if(redir.headers.get('location')!=='https://api:8000/api/v1/forecasts')throw Error('Proxy scheme lost: '+redir.status+' '+redir.headers.get('location'))"
                "})().catch(e=>{console.error(e);process.exit(1)})")
            run("exec","-T","caddy","caddy","validate","--config","/etc/caddy/Caddyfile")
            run("up","-d","worker")
            def await_runs(minimum):
                for _ in range(30):
                    count = run("exec","-T","db","psql","-U","cq_owner","-d","clutchquant","-Atc","SELECT count(*) FROM pipeline_runs").stdout.strip()
                    if int(count) >= minimum:
                        return count
                    time.sleep(1)
                raise RuntimeError("Worker cycle did not complete within 30 seconds")
            await_runs(2)
            run("restart","worker")
            await_runs(3)
            run("stop","worker")
            count = run("exec","-T","db","psql","-U","cq_owner","-d","clutchquant","-Atc","SELECT count(*) FROM pipeline_runs").stdout.strip()
            assert int(count) >= 3, "Worker did not recover across restart"
            dump = run("exec","-T","db","pg_dump","-U","cq_owner","-d","clutchquant","-Fc","--no-owner","--no-acl").stdout
            archive = run("run","--rm","--no-deps","--entrypoint","tar","worker","-C","/data/artifacts","-cf","-",".").stdout
            assert len(archive)>1024
            run("run","--rm","--no-deps","--entrypoint","mkdir","worker","/data/artifacts/restore")
            run("run","--rm","--no-deps","--entrypoint","tar","worker","-C","/data/artifacts/restore","-xf","-",data=archive)
            run("run","--rm","--no-deps","-e","ARTIFACT_ROOT=/data/artifacts/restore","worker","python","-c",
                "from app.database import SessionLocal; from app.models import PipelineRun; "
                "from app.artifacts import read_json; from sqlalchemy import select; "
                "db=SessionLocal(); r=db.scalar(select(PipelineRun).where(PipelineRun.report_sha256.is_not(None))); "
                "assert read_json('reports',r.report_sha256)['protocol']=='verified-prospective-v1'")
            run("exec","-T","db","createdb","-U","cq_owner","cq_restore")
            run("exec","-T","db","pg_restore","-U","cq_owner","-d","cq_restore","--no-owner","--no-acl","--exit-on-error",data=dump)
            restored = run("exec","-T","db","psql","-U","cq_owner","-d","cq_restore","-Atc","SELECT count(*) FROM pipeline_runs").stdout.strip()
            assert count == restored
            # Persisted DB and artifact volumes survive service recreation.
            run("up","-d","--force-recreate","--wait","db","api")
            run("exec","-T","api","python","-c",
                "from app.database import SessionLocal; from app.models import PipelineRun; "
                "from app.artifacts import read_json; from sqlalchemy import select; "
                "db=SessionLocal(); r=db.scalar(select(PipelineRun).where(PipelineRun.report_sha256.is_not(None))); "
                "assert read_json('reports',r.report_sha256)['protocol']=='verified-prospective-v1'")
            print(json.dumps({"status":"PASS","project":project,"checks":["migrations","app role",
                "HTTP proxy","readiness","public write gate","worker restart","honest health",
                "database restore","artifact restore","artifact persistence"],"pipeline_runs":int(count)}),flush=True)
        finally:
            run("down","--volumes","--remove-orphans",check=True)


if __name__ == "__main__":
    main()
