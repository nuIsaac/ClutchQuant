# Archived alternative: self-hosted VM

**Superseded as the deployment target by the [$0 demo guide](free-demo.md).**
The paid provider examples below are historical planning, not instructions to
purchase infrastructure. These files remain useful for isolated recovery drills.

Prepared from clean checkpoint `7d9a399`. No infrastructure/account was created.
No model, forecast definition, application migration, or evaluation rule changed.

## Recommendation and cost (checked 2026-09-14)

Use **DigitalOcean Basic Regular Droplet, 2 vCPU / 4 GiB RAM / 80 GiB SSD**, Ubuntu
24.04 LTS x86-64, NYC3 if available. Run PostgreSQL 17, FastAPI, Next.js, one persistent
worker, and Caddy 2 through `compose.production.yaml`. Use DigitalOcean DNS with
your existing registrar and DigitalOcean Spaces Standard for off-host backups.
Four GiB is an initial capacity choice, not a measured production traffic guarantee.
Build images locally/CI and transfer them to avoid build memory competing with jobs.

| Option | Estimated monthly cost before tax/domain/overages | Setup and persistence | Scaling later |
| --- | --- | --- | --- |
| Recommended DigitalOcean VM + Spaces | $24 VM + $5 Spaces = **$29**; optional weekly VM backups add $4.80 | Moderate Linux administration; all services and worker share disk; self-managed Postgres; one Compose release | Resize VM first; move DB to managed Postgres and artifacts to object storage before splitting services |
| Render managed services | Planning allowance **$50–80+**, subject to current plan quote | Easier HTTPS/OS operations; paid persistent worker and managed Postgres; separate API/worker disks cannot share files, so storage adapter work is required | Independent service scaling after shared object-storage integration |

DigitalOcean publishes [$24 for 4 GiB/2 vCPU/80 GiB](https://www.digitalocean.com/pricing/droplets),
[$5 Spaces Standard](https://docs.digitalocean.com/products/spaces/details/pricing/),
and [weekly backups at 20%](https://www.digitalocean.com/pricing/backups).
The expected base is $29, or $33.80 with weekly VM backups. Add a domain budget
allowance of roughly $12–24/year (actual registrar/TLD quote required), taxes and
storage/traffic growth. VM snapshots supplement, not replace, paired logical backups.

Render's [official comparison](https://render.com/articles/render-vs-railway) lists
$7 Starter and $25 Standard compute. A planning configuration is two $7 web services,
a $25 worker, database, and object storage; verify the [current quote](https://render.com/pricing).
Its [disk limitations](https://render.com/docs/disks) make it a less direct fit today.
This comparison is an estimate, not a reserved price or evidence that small tiers
will meet future workloads. No free sleeping tier is recommended for collection.

## Topology

```text
Internet HTTPS :443 -> Caddy -> Next.js :3000
                           -> FastAPI :8000 (/api/v1/*, reads only)
Next.js -> FastAPI -> PostgreSQL :5432 (private Compose network)
Worker -> VLR HTTPS + PostgreSQL + /srv/clutchquant/artifacts (read/write)
API -> /srv/clutchquant/artifacts (read-only)
Daily stopped-writer backup -> private Spaces bucket
```

Only ports 80/443 are published by Compose. Permit SSH only from your admin IP in
the DigitalOcean Cloud Firewall. PostgreSQL/API/web/worker have no host bindings.
Docker-published ports can bypass UFW; use the provider firewall as the outer
boundary and follow [Docker's Ubuntu guidance](https://docs.docker.com/engine/install/ubuntu/).
This is a single failure domain with maintenance downtime, not a high-availability
cluster. The tradeoff is appropriate for an initial low-traffic public application.
Uvicorn trusts forwarded headers on this private network so redirects retain HTTPS.
Do not publish the API port or attach untrusted containers to that network.

## Accounts and configuration you supply

- DigitalOcean account/payment method, SSH public key and selected region.
- Owned domain and registrar/DNS access; an ACME contact email.
- Private Spaces bucket, scoped access key/secret, endpoint and an rclone remote
  named `spaces`. These backup credentials belong only to the backup operator.
- Git access only if cloning a private repository; otherwise transfer a reviewed
  release archive and Docker image tarballs. No registry account is required.

Copy `deploy/.env.example` to `deploy/.env.production` and protect it with mode 600.
Set `COMPOSE_PROJECT_NAME`, `RELEASE_TAG` (reviewed Git SHA), `CADDY_SITE` (bare domain,
not http://), `ACME_EMAIL`, `DATA_DIR=/srv/clutchquant`, and two different passwords
`POSTGRES_PASSWORD` / `APP_DB_PASSWORD`. Generate each with `openssl rand -hex 32`.
Optional worker settings default to 300 seconds after each cycle and one page.
The wrapper rejects placeholder passwords/release tags and makes the file authoritative.
Do not publish resolved `docker compose config` output; use `config --quiet`.

Compose supplies APP_ENV=production, internal DATABASE_URL, ARTIFACT_ROOT and API_URL.
Human writes are disabled both at Caddy and API. No NEXT_PUBLIC secret is used.
The existing development API_URL work is unchanged. Docker administrators can inspect
container environments: restrict host/docker membership and encrypt off-host backups
if your backup policy requires it. Never commit the real env/rclone config.

## Exact deployment order

1. **Review and checkpoint this change.** Run tests and `python deploy/smoke.py`.
   Record the release Git SHA and image IDs/digests. Build on a compatible x86-64
   Docker host: set the reviewed env file, then `sh deploy/compose.sh build api web`.
   Transfer images with `docker save`/`docker load`, or build on the target during
   maintenance. Keep the previous images; do not reuse a release tag for new bytes.
   Infrastructure base images have pinned major versions; record their resolved
   digests and update deliberately, with the smoke drill, rather than unattended pulls.
2. **You provision** the VM, private backup bucket, SSH access and Cloud Firewall.
   Install Docker Engine/Compose from the official Ubuntu repository, enable Docker
   at boot, enable OS security updates and clock synchronization. Put the release
   at `/opt/clutchquant`. This preparation does not execute those paid actions.
3. Create persistent directories before startup:

   ```sh
   sudo mkdir -p /srv/clutchquant/postgres /srv/clutchquant/artifacts /srv/clutchquant/caddy
   sudo chown 10001:10001 /srv/clutchquant/artifacts
   sudo chmod 750 /srv/clutchquant/artifacts
   cd /opt/clutchquant
   chmod 600 deploy/.env.production
   sh deploy/compose.sh config --quiet
   sh deploy/compose.sh up -d --wait db
   ```

4. **Transfer the existing database and complete artifact hierarchy together.**
   Stop the local collector and all other writers first. Take a custom-format
   PostgreSQL 17 dump with `--no-owner --no-acl`; archive all artifacts, not just
   reports, and record SHA-256 checksums. Copy securely to the target. Never run
   the local collector and production collector against diverging copies as though
   they were one authoritative history. Keep the original intact for recovery.
5. On the **fresh, empty target application database**, restore before migrations:

   ```sh
   # Verify transferred checksums and inspect trusted archive contents first.
   sha256sum -c SHA256SUMS
   sh deploy/compose.sh exec -T db pg_restore -U cq_owner -d clutchquant --no-owner --no-acl --exit-on-error < database.dump
   sudo tar -xf artifacts.tar -C /srv/clutchquant/artifacts
   sudo chown -R 10001:10001 /srv/clutchquant/artifacts
   ```

   Confirm the resolved extraction directory is the new target before extracting.
   Do not restore over an existing populated database or overwrite another artifact
   tree. Existing schema data must be imported before `upgrade head`, not after it.
6. Verify target and revision, then migrate once using the owner role:

   ```sh
   sh deploy/compose.sh exec -T db psql -U cq_owner -d clutchquant -c 'SELECT current_database(), current_user, current_schema();'
   sh deploy/compose.sh run --rm migrate python -m alembic current
   sh deploy/compose.sh run --rm migrate python -m alembic heads
   # Review pending migration SQL; take a paired backup before upgrades.
   sh deploy/compose.sh run --rm migrate
   sh deploy/compose.sh run --rm migrate python -m alembic check
   ```

   Current expected head is `b72c904e1a36`; this deployment work adds no migration.
   `cq_owner` owns schema; runtime `cq_app` cannot create schema objects. Default
   grants cover tables/sequences created/restored by cq_owner. Do not restore
   another role's ownership/ACLs. Database passwords in the env file only initialize
   a fresh volume: rotating them later requires explicit PostgreSQL role changes.
7. Start private application services, inspect readiness, and run one controlled
   source-backed cycle **after the local worker has stopped**:

   ```sh
   sh deploy/compose.sh up -d --wait api web
   sh deploy/compose.sh exec -T api python -c "from app.main import readiness; print(readiness())"
   sh deploy/compose.sh run --rm --no-deps worker python -u -m app.pipeline --once --pages 1
   sh deploy/compose.sh run --rm --no-deps worker python -m app.pipeline --health
   sh deploy/compose.sh up -d worker
   ```

   Verify restored run artifacts, old forecast counts and newly captured observations.
   Stop on unexpected identity/schema/evidence failures. Do not repair by regenerating
   old forecasts. Source egress or anti-bot behavior from the target IP remains a
   deployment check; local success cannot prove that IP will be accepted.
8. Set the DNS A record to the VM (AAAA only if IPv6 is configured), then start
   `sh deploy/compose.sh up -d caddy`. Caddy obtains/renews certificates after DNS
   and ports are reachable; see [automatic HTTPS](https://caddyserver.com/docs/automatic-https).
   Verify the actual domain in a browser and `curl --fail https://YOUR_DOMAIN/api/v1/ready`.
   Check the history UI and read-only write rejection. No real certificate was
   requested during local tests, so public TLS remains unverified until this step.
9. Configure backups/monitoring below and perform a restore drill before launch.
   Confirm worker health after a full cycle and a controlled VM reboot. Keep one
   authoritative collector; retire the local worker only after successful cutover.

## Backups and recovery

For a paired manual backup, stop ALL writers (the public stack is read-only):

```sh
sh deploy/compose.sh stop worker
mkdir -p deploy/backups
sh deploy/backup.sh "$(pwd)/deploy/backups"
# Copy the completed timestamp directory off-host; verify SHA256SUMS there.
sh deploy/compose.sh up -d worker
```

The script refuses a running Compose worker, writes dump/archive/checksums plus
image/revision evidence, and never deletes prior backups. It cannot detect a manual
collector outside Compose; operators must stop those too. Raw snapshots and database
references must be recovered as a pair. A backup on the same VM is not disaster recovery.

For daily off-host operation configure rclone's `spaces` remote for the selected
private Spaces endpoint/bucket. Edit the service example's destination, copy it to
`/etc/systemd/system/clutchquant-backup.service`, and install the timer alongside it.
Run the service manually and verify remote objects/restore before enabling
`systemctl enable --now clutchquant-backup.timer`. Root's rclone config must be 600.
The job stops the worker, backs up, copies/checks remote bytes, then resumes it.
On failure it intentionally leaves the worker stopped; alert and investigate.
No remote copy, timer installation or credential configuration was performed here.

Set and document retention (initial suggestion: 7 daily/4 weekly copies) after
measuring artifact growth. There is no automatic pruning; never delete the only
restorable copy. Daily backups imply up to 24 hours of loss after total host loss;
choose more frequent backups if that is unacceptable. Recovery time depends on
archive size and operator response and is not yet an SLA.

Restore to **new directories and a new empty database/project**, verify checksums,
restore dump+artifacts, migrate if needed, and verify provenance/readiness before
switching DNS. Test this monthly. The local smoke drill restores a dump to a separate
database and checks persistent artifacts after container recreation. It cannot
verify your future off-site credentials or actual restore throughput.

For a code-only rollback with the same schema head, stop worker, select the previous
release tag and matching release checkout, then recreate api/web/worker. Caddy may
serve brief 502s during replacement; no zero-downtime promise. If schema versions
differ, do not blindly downgrade: readiness correctly rejects mismatches. Review a
forward fix or an explicitly approved paired restore, preserving later observations
before any destructive recovery. Never run `down -v` against production.

## Health, logs and operations

`sh deploy/compose.sh ps`, `logs --tail 100 api worker caddy`, and `docker stats`
provide local status. Logs use bounded Docker local rotation (10 MiB × 5 per service);
Caddy emits JSON access logs. API readiness checks DB/head; web health checks render;
worker health requires a recent successful collection cycle. Health commands do
not expose database passwords. A Docker unhealthy flag does **not** itself restart
a live process; `unless-stopped` handles exits/reboots. Investigate before restart.

Configure DigitalOcean host metrics/alerts and an independent HTTPS monitor after
account creation. Alert on disk >80%, sustained memory pressure, API failure,
worker failed/stale >15 minutes, backup/timer failures, and missing source coverage.
The worker has a 1 GiB memory ceiling and ten-minute graceful stop allowance. The
stack budget fits below 4 GiB, but Docker/OS/build overhead still matters. A one-page
cycle is bounded and sequential, uses DB advisory locking, and resumes safely after
restart. Long source outages can exceed the window: inspect and perform a reviewed
bounded catch-up, preserving real observation timestamps. Artifact history grows
continuously; monitor it rather than silently pruning reproducibility evidence.

The existing local worker was observed running healthy; the deployment drill uses
no-collection cycles in an isolated DB to test restart/permissions without duplicating
live collection. A real target-host collection cycle, TLS/DNS, reboot and off-host
restore remain explicit go-live gates. No modeling milestone was started.
