# RAG Reliability & Evaluation Platform

A research-oriented full-stack platform for uploading technical documents, building evidence-annotated datasets, running controlled RAG experiments, and investigating failures.

**Current status: the M4 local baseline pipeline is implemented.** Upload/publish corpora, curate reviewed datasets, build lexical/dense indexes, run pinned local CPU generation, and inspect saved retrieval scores and complete question traces. PostgreSQL queues preserve results through cancellation/recovery. Answer-quality evaluators, hybrid/reranking, comparisons and benchmark execution remain M5-M7.

First benchmark: a frozen PostgreSQL documentation release. Lexical/dense search and fixed-token/section chunking are implemented; hybrid and reranking remain planned. Metrics: retrieval precision/recall, correctness, faithfulness, citation support, abstention, latency, and cost.

## Reading order
1. PRD.md, USER_FLOWS.md, REQUIREMENTS.md — product and scope.
2. DESIGN_SYSTEM.md, ARCHITECTURE.md, API_SPEC.md, DATA_MODEL.md — design contracts.
3. RESEARCH_PROTOCOL.md, DATASET_CARD.md — experiment integrity.
4. IMPLEMENTATION_PLAN.md, TASKS.md, ACCEPTANCE_TESTS.md — delivery milestones.
5. AGENTS.md, skills/, CODEX_HANDOFF.md — persistent agent context.
6. TESTING.md, CONTRIBUTING.md, SECURITY.md — quality and safety.
7. DEPLOYMENT.md, DECISIONS.md, .env.example — operations and rationale.

## Run locally
Prerequisites: Node 24, npm, and uv. Python 3.12 is selected in .python-version; uv can provision it. Docker with Compose is required for the full database-backed environment. Windows: use npm.cmd if PowerShell blocks npm.ps1.

```powershell
Copy-Item .env.example .env
uv sync --frozen
npm.cmd ci
```

If .env already exists, preserve it and update settings as needed. Start the API and dashboard in separate terminals from the root:

```powershell
uv run uvicorn rag_api.main:app --reload --host 127.0.0.1 --port 8000
```

```powershell
npm.cmd run dev
```

Open http://127.0.0.1:3000 and API documentation at http://127.0.0.1:8000/docs. Without PostgreSQL, the shell works and reports unavailable database/worker services. The shell needs no model credentials; dense inspection downloads its pinned public local model. See DEPLOYMENT.md for database setup and production-mode commands.

For ingestion with a native API/frontend and Docker database, start these from the root:

```powershell
docker compose up -d db
uv run alembic upgrade head
uv run rag-worker
```

Keep the worker in its own terminal. In Documents, create a corpus, upload a file, wait for Ready, inspect the source text, then publish a version. Originals are retained; duplicate content in the same corpus reuses its document and job. Encrypted PDFs and scans requiring OCR fail explicitly. Extraction defaults: 50 MB uploads, 1,000 PDF pages, 2 million source characters, and a 60-second parser timeout. Linux parser processes also enforce a 1 GiB address-space limit; native Windows currently enforces the wall-clock and document limits.

With Docker available and .env prepared:

```powershell
docker compose up --build
```

Compose defines PostgreSQL/pgvector, a one-shot migration, API, worker, and web. Container builds and full startup are verified locally. Stop native API/web previews before using their same Compose ports. Named volumes retain the database and originals across restarts.

## Quality checks
```powershell
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest
npm.cmd run check
npm.cmd run build
node node_modules/@playwright/test/cli.js install chromium
npm.cmd run test:e2e
```

Database integration tests require a disposable database via TEST_DATABASE_URL; otherwise they explicitly skip. See TESTING.md. Husky runs staged lint/format checks. Dependencies are locked in uv.lock and package-lock.json.

## Stack
Python 3.12, FastAPI, PostgreSQL/pgvector, Next.js 16.4, React 19.3, Docker Compose. sentence-transformers and transformers use locked CPU dependencies. M4 answer generation uses the explicitly enabled pinned local model; paid adapters are not implemented. The labeled read-only demo remains planned for dashboard completion.

## Research claims
Local development-fixture runs have executed; no research benchmark or method superiority has been established. Model-judge metrics are estimates. The benchmark will publish actual provenance, controlled settings, evidence, uncertainty, and limitations.

## Curate a dataset
In Datasets, choose a published corpus and create a dataset. Use Development fixture for software checks; use Research dataset for owner-reviewed benchmark labels. Add question text, reference answer, required facts, and source annotations. You can select text or enter character offsets; whole-section selection supports keyboard use. Multiple passages can jointly support a fact, with alternatives when different evidence suffices.

Assign topic, difficulty, development/test split, and a split group. Explicitly record the reviewer after inspecting the answer and all evidence. Editing a saved answer/annotation clears the editor's review flag. Publish only after all questions pass validation; prior exports remain unchanged by later edits. JSONL import is atomic and reports line errors. Export JSONL downloads from each published version. See API_SPEC.md for the schema and source-span conventions.

The bundled authored development question was explicitly reviewed by the project owner and published as a one-question development fixture. It is not the PostgreSQL research benchmark.

## Inspect lexical retrieval
In Experiments, choose a published corpus and select section boundaries or fixed token windows. Fixed windows may cross sections within one document; section chunking splits oversized sections within their own boundaries. Set a token limit and smaller overlap, then build the index. The worker persists the job, downloads only a pinned tokenizer, and publishes all chunks atomically. Repeating the same configuration reuses the index; failed builds can be retried.

Select a ready index, enter document terms, and choose a context budget. The preview shows the top five matching passages, the exact delivered context, truncation/omission counts, and canonical source excerpts. Search uses PostgreSQL English full-text search and ts_rank_cd, not BM25. Lexical rank is not an accuracy score. Preview requests do not generate answers or save experiment results.

Tokenizer: sentence-transformers/all-MiniLM-L6-v2 at commit 1110a243fdf4706b3f48f1d95db1a4f5529b4d41, with tokenizer artifact SHA-256 and library version recorded in each index manifest. No model weights are downloaded by lexical builds. The context budget covers delivered document text and separators; saved generation uses the pinned answer tokenizer and separately bounds the complete chat prompt.

## Inspect dense retrieval
In Experiments, select Dense under Retrieval method, build a published corpus with a chunk limit at most 254 tokens, then inspect retrieval. The first build downloads the pinned public MiniLM safetensors snapshot; subsequent query inference uses the local cache. The worker embeds locally on CPU, persists normalized 384-dimensional vectors in pgvector, and queues query previews with retry/recovery. Inspect source spans and delivered context as with lexical retrieval. Cosine similarity is not a quality metric. No answer generation or paid provider is required.

Defaults: two inference threads, batch size 16, 10000 dense chunks, 5 million input characters per embedding batch, 120-second model subprocess timeout. Compose bounds the worker to four CPUs/4 GiB. Oversized text fails instead of silent model truncation; reduce chunk/query size or change explicit limits within supported bounds. Frozen manifests retain the model commit, artifact hashes, runtime, and library versions. Compare strategies using the same corpus and chunk configuration when drawing research conclusions.

## Run and inspect a baseline
Set LOCAL_GENERATION_ENABLED=true in the server-side .env, then rebuild/start the API and worker with matching code and settings. No paid API key is needed. The first run prepares the public Qwen2.5-0.5B-Instruct snapshot; model caches persist in the models volume. M4 accepts this fixed local CPU contract, not arbitrary model overrides. Defaults: two threads, 300-second child timeout, 1024 evidence tokens, 128 output tokens; full input limit 2048 tokens, evidence maximum 1536.

In Experiments, select a published reviewed dataset, a ready index from the same corpus, and its development/test split. Name the experiment and Start run. The worker generates fresh answers, scores original retrieval and delivered-context evidence independently, and saves each question-repeat observation. Open /runs/{id} for progress, cancellation, metric coverage, original/gold/delivered sources, prompts, token counts, raw answers, stage timings and attempts. Download the immutable input manifest from that page.

The model is small: it may hallucinate, omit citations, or refuse without the exact abstention marker. The platform exposes those outputs and leaves correctness/faithfulness/citation support/abstention quality unavailable. Local compute cost is also unavailable. Greedy repeats are fresh timing executions, not independent research questions. Individual generation times include hashing/loading; queue time and shared model preparation are outside question-stage timing. Run timestamps provide a broader execution window. Controlled latency/cost summaries arrive in M5.

Cancellation preserves completed observations. Worker recovery skips their unique keys and repeats interrupted work under a new lease. Terminal runs are immutable; create a fresh run for another execution. Set SOURCE_REVISION to the actual Git revision (include a dirty qualifier if appropriate) before measured runs; source-file/lock hashes are always captured. Worker/API code and runtime must match a frozen manifest to resume it.
