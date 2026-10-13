# Deployment and operations

Status: Docker Desktop/Compose builds, migrations, all service health checks, live ingestion, and restart persistence verified locally. Database integration and container-backed dataset UI checks pass. CI has not remotely executed.

## Run the local workspace
Prerequisites: Node 24, npm, uv, Python 3.12 (provisioned by uv), and Docker with Compose for the full environment. Copy .env.example to .env only if .env does not exist; preserve existing settings. Run `uv sync --frozen` and `npm ci` (npm.cmd on Windows if required).

Native development, each command in its own terminal from the root:
```powershell
uv run uvicorn rag_api.main:app --reload --host 127.0.0.1 --port 8000
npm.cmd run dev
```
Dashboard: http://127.0.0.1:3000. OpenAPI: http://127.0.0.1:8000/docs. Without a database the shell reports unavailable services; liveness returns 200 and readiness returns 503. Native production preview: `npm run build`, then `npm run start`, with the API running separately without --reload.

With Docker installed/running and .env prepared:
```powershell
docker compose config --quiet
docker compose up --build
```
`docker compose ps` and `docker compose logs` inspect services. `docker compose down` stops them while retaining named volumes. Docker builds use standalone Next.js output and non-root app users.

To use native PostgreSQL, provision a pgvector-enabled server and the role/database matching DATABASE_URL, then `uv run alembic upgrade head`. Alternatively run `docker compose up -d db` while keeping API/web native. `uv run rag-worker` processes document ingestion and maintains service/job heartbeats; `--check` returns database/schema readiness; `--once` processes at most one eligible job. Experiment handlers remain planned.

Container DB hostname is db; native default is 127.0.0.1. API_PORT/WEB_PORT/POSTGRES_PORT configure Compose mappings; native ports use launch flags. INTERNAL_API_URL stays server-side: native default http://127.0.0.1:8000, Compose http://api:8000. Next.js does not load the root .env natively; set `$env:INTERNAL_API_URL='http://127.0.0.1:8001'` before web launch for a custom API port.

The sample password is development-only. If changed, update native DATABASE_URL; URL-encode URI-reserved characters and adjust Compose's interpolated URL accordingly. No weights are downloaded or external inference performed in this release.

## Local topology
Compose services: web, API, worker, PostgreSQL with pgvector. Bind exposed ports to loopback by default. Named database/artifact/model-cache volumes preserve state. Run migrations explicitly before dependent services become ready. Readiness verifies database connectivity and schema version, not merely a live process.

Configure environment values from .env.example after settings validation is implemented. The application must refuse unsafe/missing required configuration and avoid logging secrets. Pin container versions and dependency locks. Distinguish local development hostnames from Compose service DNS names in the final instructions.

## Models and hardware
Determine supported Python and model dependencies before choosing runtime images. Record CPU/GPU, memory, model-cache disk space, document volume, and concurrency. Download weights only for explicitly selected models; record model revisions and licenses. Dashboard demo does not require inference credentials.

## Recovery
The ingestion worker reconnects after database outages. Queued jobs persist independently of API processes. Expired running jobs can be reclaimed with a new lease token; stale owners cannot checkpoint or commit evidence. Checkpointed extraction can resume without reparsing. Automatic retries are bounded by JOB_MAX_ATTEMPTS; exhausted jobs become failed. The Documents screen provides explicit retries for failed jobs. Published versions and their evidence are immutable in PostgreSQL. These database guarantees pass against a real disposable PostgreSQL/pgvector database. Per-question experiment recovery is later work.

Completed originals may remain unreferenced if a database commit has an unknown outcome. They are retained to avoid deleting a successfully committed document's original; orphan collection and draft deletion are deferred. Failed originals and checkpoints also remain in artifact storage. Keep storage under local access controls. Linux extraction processes cap address space at 1 GiB; native Windows has a wall-clock timeout and document-size limits without an OS memory cap.

## Backup and restore
Back up PostgreSQL and artifact storage as one consistent application snapshot; coordinate writes or use a documented snapshot procedure. Retain manifest hashes and encryption/access controls appropriate to local documents. Verify restore into a clean environment, reapply compatible migrations, and check corpus/run lineage plus blob existence. Never describe an untested backup as verified.

Backup/restore has not been exercised. Document persistence is implemented; experiment/run persistence is planned.

## Remote hosting gate
Before binding to a public interface: authentication/authorization, TLS, secure cookies where applicable, restricted CORS, protected uploads/downloads, quotas, secret management, logging policy, backups, and retention/deletion controls. The initial local trust model does not protect a shared public workspace.

## Release checklist
Required checks pass; migration tested; demo labeled; schema and environment docs match code; health checks verified; backup/restore exercised; runtime/model/licensing metadata recorded; no secrets or private corpus data committed. Update this document with actual verified run commands in M1.

## Local dense runtime
Preserve the named models volume: dense indexes require the same pinned model/tokenizer/config artifacts for query inference. The first dense build needs outbound access to the public Hugging Face snapshot; queries load offline. Dense defaults are EMBEDDING_THREADS=2, EMBEDDING_BATCH_SIZE=16, MAX_DENSE_CHUNKS=10000, MODEL_TIMEOUT_SECONDS=120. Compose worker memory/CPU limits are 4 GiB/four CPUs; native processes retain time/input/thread bounds but do not enforce that container memory cap. Artifact hashes/runtime metadata stay in index manifests and preview results. A failed build/query can be explicitly retried after correcting local cache/configuration.
