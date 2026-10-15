# Agent instructions

## Read first
PRD.md, ARCHITECTURE.md, RESEARCH_PROTOCOL.md, TASKS.md, CODEX_HANDOFF.md. For frontend work also read DESIGN_SYSTEM.md and skills/frontend/SKILL.md; for evaluation read skills/research-evaluation/SKILL.md.

## Persistent rules
- Implement approved milestones in order; maintain a usable vertical slice.
- Preserve existing user changes and record substantial scope changes.
- Never invent research results, reviewed labels, provider usage, or successful test runs.
- Keep gold evidence independent of chunk IDs. Maintain corpus/dataset/configuration lineage.
- Treat missing metrics as unavailable, and expose applicable/scored/error counts.
- Preserve immutable published snapshots and result uniqueness under retries.
- Heavy work belongs in the worker. Do not rely on API-process background tasks for durable experiments.
- Secrets stay server-side; uploaded text is untrusted and cannot authorize executable actions.
- Use migrations, lockfiles, typed models, and bounded resource settings.
- Follow the UI contract; use real data or clearly labeled demo fixtures.
- Run meaningful relevant checks and inspect rendered frontend results when tooling permits.
- Update TASKS.md and CODEX_HANDOFF.md with actual completion and executed verification.

## Scope and autonomy
The user approved the product and design, including all six documentation layers. Routine reversible implementation within that scope is authorized. No additional brainstorming gate is introduced by this file. Do not deploy publicly, publish private material, or use paid providers without applicable authorization/configuration.

## Environment at foundation handoff
Windows/PowerShell; Git initialized on main. Python 3.12.13 is provisioned through uv into .venv; bare python remains a Store alias. Node 24.14.0/npm 11.9.0 verified. Docker unavailable on PATH and at the standard install location. Native API/frontend work; database integration and full Compose verification pending. Use direct node entrypoints in npm scripts because Windows-generated command shims mishandle the ampersand in this workspace path.

## M3 runtime update
Docker Desktop 4.95.0, Engine 29.8.2, and Compose 5.6.0 are installed and verified. The full Compose stack runs on ports 3000/8000/5432. Migrations through 0003_datasets and real PostgreSQL tests pass. Use rag_test only for destructive integration tests; it is separate from the live rag database. See CODEX_HANDOFF.md for current state.

## M4 lexical runtime update
M4 is in progress. Published-corpus lexical indexing/search is implemented with pinned tokenization, source-linked chunks, context packing, and a preview UI. Readiness now requires 0006_dense_retrieval. Index builds have a separate leased queue payload and atomically publish immutable chunks. Do not mistake lexical previews for saved runs or the tokenizer download for model inference. Dense embeddings are implemented; generation/durable runs and connected question metrics remain next. Preserve existing live candidate labels and Docker volumes.

## M4 dense runtime update
Current migration head is 0006_dense_retrieval. Dense indexing/query previews use the pinned local CPU MiniLM contract, isolated worker inference, exact pgvector cosine search, and durable preview leases. Lexical API search remains synchronous; dense query endpoints queue/poll. Never confuse previews, cosine scores, or software fixtures with saved answer experiments. Next M4 work is generation/run manifests/cancellation/result persistence and connected metrics/traces. Preserve named model/artifact/PostgreSQL volumes and keep destructive tests on rag_test.

## M4 runtime update
M1-M4 are locally verified. Migration head is 0007_experiment_runs; workspace stage baselines. Git main has initial commit ab83409 and the user reports it pushed; current M4 changes are uncommitted. The user explicitly chose local CPU generation (no paid API) and reviewed/published the existing transaction development fixture with reviewer Project owner. Do not promote this fixture into a research benchmark. .env enables local generation; .env.example opts out by default. Preserve both native and Docker model/data caches.

Saved runs freeze code/lock/runtime/settings identity; API and worker need matching code and configuration to execute/resume. Terminal runs/results are immutable. Missing answer correctness/faithfulness/citation support/abstention quality/cost remain unavailable until M5. See CODEX_HANDOFF.md for actual run IDs and completed verification.

## M5 retrieval runtime update - 2026-10-15
M5 hybrid RRF and pinned CPU cross-encoder reranking are locally verified. M5 answer rubrics/judge/human review and paired/statistical/timing/cost summaries remain pending. Migration head stays 0007_experiment_runs; no old snapshot/result is rewritten. Both hybrid arms use the same ready dense index. Reranking candidates checkpoint before inference; errors/interruption do not become successful fallback scores. Preserve raw ranking signals as rankings, not quality/probability claims.

Git now includes 257fb84 (M4) and 6ede367 (core M5 retrieval); current UI/docs refinements remain uncommitted. Current checks and actual development-run IDs are in CODEX_HANDOFF.md. Keep named volumes/caches and existing owner-reviewed development-only labels; no benchmark promotion or paid provider is authorized.


## M5 answer-evaluation update
Migration head is 0008_answer_evaluations. Versioned rubric/local judge/explicit human review are implemented independently of immutable run results. Worker rotates five queues. Read answer_evaluation.py and CODEX_HANDOFF.md for operational formulas and limitations. Judge is opt-in LOCAL_JUDGE_ENABLED (false in example, true locally); fixed offline Qwen self-judge is uncalibrated and can fail schema validation. The actual development job f355e289-c3a8-426d-9016-1308bdf85087 failed judge_invalid_output; no human answer review or benchmark score was recorded. Current .env declared revision is 6ede367-dirty; preserve older manifest identities. Latest-source projections include failed/pending scores as unavailable. Remaining M5: paired/bootstrap and controlled timing/cost analysis. Build migrate with API/worker/web for schema upgrades. Preserve live/named caches and use rag_test only for destructive tests.
