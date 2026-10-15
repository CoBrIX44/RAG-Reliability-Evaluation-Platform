# Testing

Status: M1-M4 checks pass locally, including real PostgreSQL retrieval/scoring/run persistence and Chromium workflows. Historical slice counts below record their execution dates; current verification is in the M4 saved-run section and CODEX_HANDOFF.md.

## Run current checks
After `uv sync --frozen` and `npm ci`, from the project root:

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

Use npm outside Windows. Playwright starts the dashboard or reuses an existing local server outside CI. Its service-status responses are intercepted for deterministic ready/error scenarios; these tests do not prove PostgreSQL integration. Native API-to-dashboard connectivity is checked separately.

Python tests cover config/secret safety, database-independent liveness, schema/vector readiness, sanitized errors, and heartbeat freshness. Browser tests cover navigation, capability limits, refresh recovery, mobile/keyboard access, reduced motion, overflow, accessibility scanning, and 404 behavior.

## Disposable database integration
The integration suite upgrades, downgrades, and re-upgrades its schema, then exercises uploads, duplicate jobs/publication, sealed evidence, later draft isolation, locked-job skipping, attempt exhaustion, stale-worker fencing, and checkpoint recovery. Do not use a valuable database or run a separate worker against this test database. Create rag_test in a pgvector-enabled local server, then:

```powershell
$env:TEST_DATABASE_URL = 'postgresql+psycopg://rag:rag_local_only@127.0.0.1:5432/rag_test'
uv run pytest -m integration
```

Without TEST_DATABASE_URL these tests explicitly skip. CI supplies an isolated database. `uv run alembic upgrade head --sql` checks SQL generation without executing it.

## Rendered review
With the dashboard running, `node scripts/inspect-ui.mjs` saves actual desktop/settings/mobile screens in ignored artifacts/. The document browser workflow also saves fixture-backed documents-desktop.png and documents-mobile.png. Inspect these plus keyboard/manual behavior. Charts/modals are later work.

Use pytest for unit/integration checks, real PostgreSQL/pgvector for SQL behavior, and Playwright for browser contracts. Versions are locked. Later component tests are added when meaningful interactions justify them.

## Upcoming valuable coverage
Metric fixtures must be hand-computed independently of the implementation. Test canonical span coverage, alternatives, duplicates, empty retrieval, unanswerable cases, and undefined faithfulness. Test token budgets and source lineage across chunking variants.

Integration tests cover migrations, incompatible vectors, immutable snapshots, atomic dataset imports, idempotent submissions, concurrent claims, expired leases, stale commits, recovery, and cancellation. Provider adapters use bounded test doubles in CI; live inference is opt-in and reports its cost/environment.

End-to-end: fixture upload → corpus publication → reviewed dataset → experiment → persisted results → comparison/export. Demo is clearly separated from measured execution.

Frontend checks include keyboard access, dialog focus, errors preserving form input, missing scores, chart table alternatives, responsive widths, reduced motion, and visual inspection. Accessibility automation supplements manual interaction review.

## Required quality checks
Python lint/format and typing; frontend/test-tool lint and TypeScript checks; relevant tests; core E2E at milestone/release boundaries. Husky runs staged lint/format; CI also checks typing, production build, real migrations, and Compose startup. Live inference remains opt-in and must not happen in ordinary CI.

## Evidence
Record executed commands, environment, pass/fail, skipped/live-provider checks, and limitations in CODEX_HANDOFF.md. Do not claim planned tests passed. Broaden testing only for new changes or unresolved concerns.

## Ingestion coverage
Unit tests cover PDF/HTML/Markdown/text, source lines, code formatting, heading hierarchy, Unicode normalization, corrupt/encrypted/scanned files, original/checkpoint integrity, parser subprocesses, upload limits including chunked requests, and partial-file cleanup. Browser fixture tests cover corpus creation, upload, evidence inspection, publication, input-preserving errors, desktop/mobile layout, and untrusted text rendered without HTML execution. Fixtures do not prove a running worker/database.

## M3 checks executed
Real PostgreSQL suite: 48 tests passed, no skips when TEST_DATABASE_URL targets disposable rag_test. Includes dataset export/import round trips, candidate/reviewer gates, unanswerable rules, duplicate/conflicting edits, atomic line errors, evidence bounds/lineage (including SQL tampering), split leakage, immutable manifests, and M1/M2 guarantees. Ten Chromium tests pass against the Docker production frontend; dataset publication/review interactions use labeled fixtures. Unicode selection and review invalidation, desktop/mobile overflow, and accessibility scans are covered.

Container builds/full health and live ingestion/restart persistence pass. A real Docker browser created/edited a labeled candidate dataset and verified malformed JSONL commits nothing. At that handoff it was unreviewed/unpublished; the project owner subsequently reviewed and published it during M4. The benchmark has no human-reviewed questions yet. Fixtures and tested product behavior are not research findings.

## M4 lexical slice checks
The current full Python suite passes 94 tests with real PostgreSQL/pgvector in disposable rag_test and no skips. New hand-computed checks cover both chunk strategies, Unicode lineage, overlap/duplicate coverage, joint alternatives, empty/unanswerable/unannotated cases, separate fact denominators, context clipping, separator accounting, token/config bounds, and tokenizer identity/truncation behavior. Index integration checks cover migration round trips, idempotent creation, lexical matching/empty results, SQL source guards, immutable ready indexes/chunks, locked/expired claims, stale owners, attempt exhaustion, retry, shutdown recovery, and atomic rollback.

Twelve Chromium checks passed against Docker production, including lexical build/search, truncation/source excerpts, failed-build retry, preserved input, untrusted text, accessibility, and responsive overflow. A real Docker browser indexed/searched the labeled live development corpus using the pinned public tokenizer. Native smoke checks also use that actual tokenizer with Unicode/fixed windows and a bounded packed context. These checks involve no model weights, inference, generated answers, or research claims. Screenshots and raw preview responses remain in ignored artifacts/.

The actual section index manifest and full lexical/context response remain identical after database/API/worker restart. A second real fixed-window index (12 tokens, overlap 2) published five chunks from the authored fixture. Live source excerpts render safely; updated desktop/mobile screenshots were inspected.

## M4 dense slice checks
Full Python suite: 109 passed, no skips against separate rag_test. Additional software fixtures verify finite/unit/384-dimensional vectors, pinned runtime/artifact contracts, batch capacity, subprocess timeout/shutdown cleanup and secret isolation, hand-computed exact cosine ranking, source/context lineage, duplicate preview requests, offline compatibility rejection, completed/vector immutability, locks/expired claims/stale owners, failed retry, and rollback of all chunks/vectors when embedding counts disagree. Tests use labeled synthetic vectors and do not download model weights.

Thirteen Chromium tests pass against the Docker production frontend. The dense fixture checks chunk capacity, queued query failure/retry with preserved input, cosine labels, accessibility, and 375px overflow. Ruff lint/format, mypy (52 files), root ESLint and both TypeScript projects pass. Native actual pinned-model smoke produced two 384-dimensional embeddings and rejected 255 content tokens without truncation. These are local software checks, not benchmark or answer-quality results.

Actual Docker browser verification also passes with the pinned CPU model: two fixture chunks/vectors, queued/completed query retrieval, packed 12-token context, canonical source inspection, and desktop/mobile rendering without overflow. Complete dense index and preview/result survive database/API/worker restart unchanged. At that dense-slice handoff the live dataset was candidate/unpublished and generation/saved runs were pending. Those M4 features and the explicit owner fixture review are now verified below; public deployment remains deferred.

## M4 saved-run verification - 2026-10-13
Full suite: 128 Python tests passed with no skips on separate real rag_test. Ten saved-run integration tests additionally reran successfully after the final summary-query optimization. They verify persisted synthetic answers/scores/traces, frozen split/revision isolation after draft edits, unavailable answer metrics, generation failure with retained retrieval, cancellation preserving earlier results/checkpoints, expired cancellation without more inference, interrupted recovery without duplicate results, stale fencing, attempt exhaustion, global key conflicts, concurrent submissions and locked-run skipping. All reviews/answers in these automated tests are explicitly synthetic software fixtures; ordinary tests download no model weights.

Generation units verify pinned model/prompt/abstention validation, syntactic citation classification, input limits, child timeout/shutdown cleanup and exclusion of provider/Hub secrets. Sixteen Chromium tests pass against the current Docker production build, including deep-linked partial results, safe HTML text/source spans, delivered-context loss, exact missing-score labels, keyboard/axe scans, form/key preservation after ambiguous failures and cooperative cancellation. Earlier browser runs against a stale/restarting container failed and were rerun on the stable current build; the final complete browser run passes.

Ruff lint/format, mypy (61 files), ESLint and both TypeScript projects pass. Linux builds/migration and all four long-running Compose services are healthy. Actual native answer-tokenizer overflow smoke rejects a 4000-code-point prompt before model loading. Actual Docker CPU generation was separately exercised twice using the Project owner-reviewed development_fixture version, once through Start run in the real browser. Complete raw records remain identical across database/API/worker restart; an actual queued cancellation also persists. Desktop/mobile captures were inspected; source evidence and 375/768/1024px overflow checks pass. A small model's imperfect output is not a scored correctness/faithfulness result. Controlled performance, research comparisons, benchmark curation, remote CI and backup/restore remain unverified.

## M5 retrieval slice - 2026-10-15
Full real PostgreSQL suite: 142 passed/no skips on rag_test. Fourteen added tests cover hand-computed equal-weight reciprocal ranks, per-arm duplicate removal, stable ties, conflicting chunk content, finite/count/token/model output checks, candidate/configuration bounds, child timeout/shutdown/secret isolation, real same-index lexical+dense fusion, deliberately harmful synthetic reranking with independent gold scoring, failed-reranker retained evidence/unavailable scores, interrupted reranking recovery, and rejection of lexical-only indexes. Ordinary tests use labeled synthetic vectors/logits/answers/reviews and download no model weights.

Eighteen Chromium tests pass on production Docker, including saved hybrid strategy/parameters, separate RRF/logit/quality labels, retained candidate text/source inspection, failure with unavailable final ranks, axe/keyboard behavior, and 375/768/1024px overflow. Native actual public model preparation verifies six pinned artifacts; actual joint-pair inference works and >512 paired tokens fails before model loading without truncation. Actual Docker runs complete for hybrid and hybrid_rerank against the already approved development fixture; this is software execution evidence, not a benchmark result or judged answer score.

Ruff/mypy and ESLint/TypeScript plus Linux builds/Compose startup pass. Current migration head remains 0007. Human review/judge metrics and paired/bootstrap/latency/cost analysis still require the remaining M5 work; no new reviewed benchmark label or method superiority is asserted.

Final M5 retrieval checks additionally verify all three actual new runs and all old M4 records remain exactly unchanged after database/API/worker restart. Actual browser Start run, candidate source inspection, and post-restart trace reopening pass. Mobile visual review found compressed ranking columns despite the initial no-overflow/axe tests; fixed with a readable minimum-width local scroll region and hint. All 18 Chromium tests reran successfully with keyboard horizontal-scroll and header-height assertions. Current artifacts retain the corrected actual mobile table.


## M5 answer-evaluation verification - 2026-10-15
Final full suite: **164 Python tests passed, no skips or warnings**, using the separate real PostgreSQL rag_test. Twenty-two new rubric/evaluation tests independently cover fact/claim denominators, contradiction, uncertain/missing/unknown citation support, no claims, answerable/unanswerable exact abstention, strict invalid outputs, secret isolation/timeout/shutdown cleanup, immutable named review/idempotency, successful synthetic judging, retained failed raw output, unavailable judge, stale leases/recovery/exhaustion, frozen runtime mismatch, SQL evidence-lineage rejection, latest-source coverage and disagreement exclusions. All automated judgments/reviewer labels are explicitly synthetic software fixtures; they are not human research annotations.

**19 Chromium tests passed** on the final production Docker build. The new review workflow verifies ambiguous response retry preserves inputs/key, model/human disagreement, disabled judge, explicit fact/claim/rationale/attestation, axe checks, and no overflow at 375/768/1024px. Rendered actual failed-judge state and the empty human review form were visually inspected on desktop/mobile. No live human answer review was submitted. The first browser run had one overly broad test selector matching Next's route announcer; it was narrowed and complete production tests reran successfully.

Ruff lint and formatting (98 files), strict mypy (75 files), root ESLint and both TypeScript projects pass. All Python services including migrate and the production frontend build/start successfully; db/api/worker/web are healthy. Initially an old migrate image left readiness at schema_mismatch; rebuilding migrate corrected it. The actual one-attempt local judge job f355e289-c3a8-426d-9016-1308bdf85087 finished judge_invalid_output, 374 input / 90 output tokens / eos, with original response/prompt/usage retained and quality scores unavailable. This honestly verifies a failure path, not model accuracy/calibration or benchmark quality.

Exact SQL snapshots verify all **6 prior runs, 5 saved results and 5 attempts** unchanged through migration/code upgrade and database/API/worker restart. The new model evaluation, including raw prompt/output/token usage and failure, is also exactly unchanged after restart. Coverage correctly exposes one judge error and no substitute score. Evidence is in ignored artifacts/m5-evaluation-original-records-{before,after-upgrade,after-restart}.json, m5-evaluation-records-{before,after}-restart.json, m5-evaluation-live-{submission,current,coverage,browser}.json, and actual/synthetic evaluation screenshots. Preserve these local artifacts/caches. No paid provider, fabricated human review, research result, remote CI, public deployment or complete backup/restore is claimed. Remaining M5: paired/bootstrap and controlled timing/cost analysis.
