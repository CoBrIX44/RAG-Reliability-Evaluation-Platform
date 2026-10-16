# Deployment and operations

Status: M1-M4 Docker builds/migration/service health, real ingestion/dataset/retrieval/local generation and saved-run restart persistence are verified locally. CI has not remotely executed; benchmark, public hosting and backup/restore remain unverified.

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

To use native PostgreSQL, provision a pgvector-enabled server and the role/database matching DATABASE_URL, then `uv run alembic upgrade head`. Alternatively run `docker compose up -d db` while keeping API/web native. `uv run rag-worker` processes document ingestion and maintains service/job heartbeats; `--check` returns database/schema readiness; `--once` processes at most one eligible job. The same worker processes saved retrieval/generation runs.

Container DB hostname is db; native default is 127.0.0.1. API_PORT/WEB_PORT/POSTGRES_PORT configure Compose mappings; native ports use launch flags. INTERNAL_API_URL stays server-side: native default http://127.0.0.1:8000, Compose http://api:8000. Next.js does not load the root .env natively; set `$env:INTERNAL_API_URL='http://127.0.0.1:8001'` before web launch for a custom API port.

The sample password is development-only. If changed, update native DATABASE_URL; URL-encode URI-reserved characters and adjust Compose's interpolated URL accordingly. Pinned public embedding/answer weights are prepared when explicitly used; M4 makes no paid provider calls.

## Local topology
Compose services: web, API, worker, PostgreSQL with pgvector. Bind exposed ports to loopback by default. Named database/artifact/model-cache volumes preserve state. Run migrations explicitly before dependent services become ready. Readiness verifies database connectivity and schema version, not merely a live process.

Configure environment values from .env.example after settings validation is implemented. The application must refuse unsafe/missing required configuration and avoid logging secrets. Pin container versions and dependency locks. Distinguish local development hostnames from Compose service DNS names in the final instructions.

## Models and hardware
Determine supported Python and model dependencies before choosing runtime images. Record CPU/GPU, memory, model-cache disk space, document volume, and concurrency. Download weights only for explicitly selected models; record model revisions and licenses. Dashboard demo does not require inference credentials.

## Recovery
The ingestion worker reconnects after database outages. Queued jobs persist independently of API processes. Expired running jobs can be reclaimed with a new lease token; stale owners cannot checkpoint or commit evidence. Checkpointed extraction can resume without reparsing. Automatic retries are bounded by JOB_MAX_ATTEMPTS; exhausted jobs become failed. The Documents screen provides explicit retries for failed jobs. Published versions and their evidence are immutable in PostgreSQL. These database guarantees pass against a real disposable PostgreSQL/pgvector database. Saved runs reclaim expired ownership and skip already committed question-repeat observations.

Completed originals may remain unreferenced if a database commit has an unknown outcome. They are retained to avoid deleting a successfully committed document's original; orphan collection and draft deletion are deferred. Failed originals and checkpoints also remain in artifact storage. Keep storage under local access controls. Linux extraction processes cap address space at 1 GiB; native Windows has a wall-clock timeout and document-size limits without an OS memory cap.

## Backup and restore
Back up PostgreSQL and artifact storage as one consistent application snapshot; coordinate writes or use a documented snapshot procedure. Retain manifest hashes and encryption/access controls appropriate to local documents. Verify restore into a clean environment, reapply compatible migrations, and check corpus/run lineage plus blob existence. Never describe an untested backup as verified.

Backup/restore has not been exercised. Document and experiment/result persistence are implemented; a full backup/restore is still unverified.

## Remote hosting gate
Before binding to a public interface: authentication/authorization, TLS, secure cookies where applicable, restricted CORS, protected uploads/downloads, quotas, secret management, logging policy, backups, and retention/deletion controls. The initial local trust model does not protect a shared public workspace.

## Release checklist
Required checks pass; migration tested; demo labeled; schema and environment docs match code; health checks verified; backup/restore exercised; runtime/model/licensing metadata recorded; no secrets or private corpus data committed. Update this document with actual verified run commands in M1.

## Local dense runtime
Preserve the named models volume: dense indexes require the same pinned model/tokenizer/config artifacts for query inference. The first dense build needs outbound access to the public Hugging Face snapshot; queries load offline. Dense defaults are EMBEDDING_THREADS=2, EMBEDDING_BATCH_SIZE=16, MAX_DENSE_CHUNKS=10000, MODEL_TIMEOUT_SECONDS=120. Compose worker memory/CPU limits are 4 GiB/four CPUs; native processes retain time/input/thread bounds but do not enforce that container memory cap. Artifact hashes/runtime metadata stay in index manifests and preview results. A failed build/query can be explicitly retried after correcting local cache/configuration.

## Local answer runtime and run recovery
LOCAL_GENERATION_ENABLED=true explicitly enables the fixed pinned Qwen2.5 0.5B CPU baseline. GENERATION_THREADS defaults to 2 (1..8); GENERATION_TIMEOUT_SECONDS defaults to 300 (1..1800). A cold public model download may need a larger timeout on slow connections; change the setting before creating the run, then restart both API/worker so frozen execution settings match. Preserve the models volume. Inference uses offline safetensors/config/tokenizer files with fixed artifact hashes, never trust_remote_code or Hub tokens. Native/Docker caches are separate.

SOURCE_REVISION defaults to unrecorded: set a truthful revision for research execution. Manifests also freeze hashes of core/API/worker/migration source and both lockfiles. Resume requires matching hashes, Python/platform, model contract, threads and timeout. Do not change code/configuration on an active measured run and expect a silent resume. Restore its matching environment or start a distinct new run. A terminal failure cannot be reset; a new submission key records a separate execution.

One worker rotates four durable queues. Leases default to 120 seconds, regular health heartbeats to 20 seconds; run heartbeats/cancellation polling are at most two seconds. Observed cancellation stops local children and preserves results. Model work holds no long-lived SQL transaction. Interrupted attempts remain inspectable, with final result uniqueness under recovery. Worker preparation downloads can fail before any question starts; expose that run error rather than infer missing usage/cost.

## Hybrid/cross-encoder runtime
A ready dense index supports index baseline, hybrid RRF and hybrid plus reranking without rebuilding or mutating its chunks. Reranked runs prepare the pinned public cross-encoder snapshot in the persistent models volume, then load offline for inference. Both native and Docker cache preparation/hash validation are verified. RERANKER_THREADS defaults to 2 (1..8), RERANKER_BATCH_SIZE to 8 (1..16), RERANKER_TIMEOUT_SECONDS to 120 (1..1800). These settings, along with embedding and generation settings, now participate in frozen execution identity. API and worker must match before submitting/resuming; old terminal runs remain readable. No new migration or dependency lock change is required.

Keep the worker's four-CPU/4-GiB bounds and never run a worker against rag_test. Cache preparation can fail before question execution; question-time reranking errors retain candidate checkpoints. Model IDs/revisions remain fixed by code; environment model-selection placeholders are reserved. Stage timings include child/model startup and do not by themselves establish controlled warm-cache performance or comparative quality.


## Answer-evaluation upgrade
Migration head is now 0008_answer_evaluations. Build all Python services including the separate migrate image: `docker compose build api worker migrate web`, then `docker compose up -d`. Stale migrate images leave new API/worker readiness at schema_mismatch; rebuilding only api/worker is insufficient. Preserve named volumes. `.env.example` keeps LOCAL_JUDGE_ENABLED=false; enable only for optional uncalibrated local model estimates, with matching API/worker source and settings. The judge uses cached pinned Qwen weights offline, generation thread/timeout bounds, 4096 input/768 output tokens and no tools/paid provider. Human review needs PostgreSQL but not the judge. Never reset immutable runs/evaluations after an upgrade; use a new key for a new execution. Unknown local compute cost remains unavailable.


## Paired-comparison upgrade
Migration head is 0009_comparisons. Build api, worker, migrate and web together, then start Compose; preserve all named volumes and existing immutable data. Worker now rotates six durable queues, including bounded bootstrap analysis. `.env` currently declares 3091827-dirty for new submissions; older saved manifests retain their original identities. No new dependency/provider credential is required. Keep API/worker execution identity matched for analysis/recovery. Cached model weights, source uploads and published snapshots are unchanged. Comparison snapshots/reports survive restarts; new reviews require a new comparison key to enter a report. Operator cold/warm cache notes do not automatically manage OS/model caches, and unknown local cost stays unavailable.

## M6 upgrade and evidence artifacts
Rebuild api, worker, migrate and web together, then run docker compose up -d. Readiness requires 0010_exports; keep API/worker execution identities and settings matched. Preserve all named PostgreSQL, artifact and model volumes. Do not use down -v or prune for an upgrade.

MAX_EXPORT_BYTES defaults to 209715200 (200 MiB uncompressed) and is bounded to 1 GiB; archives are also capped at 20,000 entries. Matching API/worker caps are frozen into jobs. Oversized jobs fail visibly without publishing partial output. ZIP generation belongs to the worker, with retries and stale-lease fencing; downloads stream from the retained artifact volume.

Verify the downloaded ZIP SHA-256 against output.sha256 and each entry against checksums.json. Bundles include potentially private raw prompts, answers and full canonical corpus/index evidence; retain them locally under the existing trusted-workspace policy. They omit uploaded binaries/model weights. provenance/availability.json lists missing or changed historical code instead of substituting current bytes. Service restart persistence is verified; complete backup/restore and controlled performance measurements remain M7.
