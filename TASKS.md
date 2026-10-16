# Tasks

## Completed design
- [x] Product, domain, capacity assumptions, and non-goals approved.
- [x] Modular API/worker architecture and recovery approved.
- [x] Research protocol, dashboard workflow, and UI direction approved.
- [x] Testing, safety, operations, and documentation scope approved.
- [x] Initial specification and decision log written.

## M1 Foundation
- [x] Initialize Git and monorepo workspaces.
- [x] Verify all runtimes: Python 3.12, Node/npm, Docker Desktop and Compose verified.
- [x] Pin dependencies and create lockfiles.
- [x] Add API/web/worker entrypoints and database migration skeleton.
- [x] Add Compose, volumes, environment validation, health checks.
- [x] Configure Ruff, Python typing, ESLint, TypeScript, Husky, and CI.
- [x] Verify native API/frontend startup and missing-database health behavior.
- [x] Verify full Compose boot and real PostgreSQL migration/heartbeat integration.

M1 runtime gate passed locally: container builds, migrations, and all long-running Compose services healthy. CI has not remotely executed.

## M2 Documents
- [x] Upload validation and local blob storage.
- [x] PostgreSQL jobs, leases, heartbeats, bounded retries, checkpoints.
- [x] Supported text extraction, canonical sections, source mappings.
- [x] Immutable corpus publication and document inspection UI.
- [x] Verify duplicate publication prevention and restart recovery.

Real PostgreSQL migration, locking, retry, immutability, and checkpoint tests pass. A labeled live development document was uploaded/extracted/published in Compose; its manifest and source evidence survived database/API/worker restart.

## M3 Datasets
- [x] Draft editor, evidence groups, review status, split assignment.
- [x] Atomic JSONL import/export and publication validation.
- [x] Version isolation and evidence lineage checks.

M3 real database tests verify publication/export/import round trips, review gates, source spans, immutable snapshots, optimistic conflicts, duplicates, and split leakage. Browser fixtures verify curation/publication, Unicode annotation selection, fresh-review requirements, accessibility, and responsive layout. Live Docker UI saves and edits candidate evidence annotations; malformed JSONL reports its physical line and commits nothing. The live fixture was subsequently explicitly reviewed by the project owner and published during M4; it remains separate from the research benchmark.

## M4 Baselines
- [x] Fixed-token/section chunks with canonical span lineage and a pinned tokenizer.
- [x] Durable lexical index variants, immutable publication, retries, and lexical inspection UI.
- [x] Rank-order token-budget packing with retained/truncated/omitted source traces.
- [x] Independently checked evidence-group recall and passage precision core.
- [x] Compatible embedding storage, sentence-transformer indexing, and exact dense retrieval.
- [x] Generation adapter, run manifest, cancellation and result persistence.
- [x] Connect evidence scoring to saved question results and complete the question trace UI.

M4 gate passed: actual pinned local CPU runs from the owner-reviewed published development fixture persist complete inputs, raw answers/prompts/usage, ranked and delivered source traces, retrieval precision/recall/context recall, errors, timings, and unavailable answer metrics. Runs cancel durably; real PostgreSQL tests verify interrupted recovery, retained checkpoints, stale ownership, result uniqueness, concurrent submissions and immutable lineage. An actual browser starts a run and opens gold source evidence at desktop/mobile widths. Two completed actual runs and one queued cancellation are exactly unchanged after database/API/worker restart. Full Python suite: 128 passed/no skips on rag_test; after the final summary-query optimization, all 10 run integration tests passed again. Sixteen Chromium tests, Ruff/mypy, ESLint/TypeScript, Linux production builds and full Compose health pass. No research benchmark or answer-quality conclusion has been produced.

## M5 Research
- [x] Hybrid RRF and cross-encoder reranking.
- [x] Versioned answer rubrics, judge adapter, human review.
- [x] Paired comparisons, bootstrap summaries, timing/cost accounting.

## M6 Dashboard
- [x] Comparison charts/tables and topic/difficulty filtering.
- [x] Failure explorer, exports, labeled read-only demo.
- [x] Rendered UI/accessibility/responsive verification.

## M7 Benchmark and delivery
- [ ] Select numbered PostgreSQL release and record corpus provenance/license.
- [ ] Curate 150 reviewed questions, freeze grouped split, publish dataset card.
- [ ] Run controlled experiments and export evidence-backed report.
- [ ] Verify backup/restore, operations guide, and final handoff.

## Git checkpoint tooling
- [x] Fix initial-commit hook failure for ESLint-ignored next-env.d.ts; staged ESLint keeps zero-warning enforcement for checked source files. Actual lint-staged run passed all 20 frontend and 52 Python files.

## M5 retrieval slice - 2026-10-15
Implemented the first M5 vertical slice: saved experiments select index baseline, hybrid RRF, or hybrid RRF plus a pinned local CPU cross-encoder. Both search arms use one immutable dense index's chunk universe; rank fusion deduplicates within each arm, uses equal weights and stable ordinal/ID ties. Frozen settings include candidate depth, RRF constant, fusion contract and reranker artifact/runtime pins. Candidate checkpoints survive interruption/failure; incomplete reranking never becomes a final retrieval score. The frontend separates arm ranks/RRF/logits/final selection and retains original candidate source inspection. M5 is still in progress: versioned answer rubrics/judge/human review and paired/bootstrap/timing/cost summaries remain next.

Full PostgreSQL suite: 142 passed/no skips; 18 Chromium tests pass. Native actual model preparation validates six artifact hashes, joint pair scoring works, and actual paired-token overflow rejects without truncation. Docker builds/startup pass. Actual frozen development-fixture hybrid and reranked runs complete with both ranks and local model metadata saved. These one-question software runs are not a research comparison or answer-quality result. Current migration head remains 0007_experiment_runs; existing JSON manifests/traces hold the added configuration without changing old snapshots.

M5 slice final verification: three actual Docker development runs (one created through the real browser) complete and preserve complete manifests/rankings/logits/answers/checkpoints through database/API/worker restart. All prior M4 raw records are exactly unchanged across the upgrade/restart. Inspected mobile rendering exposed table wrapping; corrected local horizontal scrolling and reran all 18 Chromium tests, including keyboard scroll and header readability. Remaining M5 tasks are still unchecked.


## M5 answer-evaluation slice - 2026-10-15
Implemented immutable answer-evidence-v1 rubrics with required-fact coverage/contradiction, delivered-evidence claim support, supporting inline citations, and exact-marker abstention decision accuracy. PostgreSQL migration 0008_answer_evaluations adds independent append-only human reviews and durable leased judge jobs. Frozen inputs bind result/run hashes, delivered text, rubric/model/prompt/artifact/runtime/source/lock identity. Idempotent submissions preserve ambiguous retries; stale leases, shutdown, runtime mismatch, exhausted retries, malformed/truncated judge output and terminal immutability are checked. Existing saved runs/results are not rewritten.

Saved answer UI supports explicit fact/claim assessments, reviewer/rationale, review attestation, retained review history, local model estimates and disagreement. Separate run summaries select the latest record per answer/source and expose eligible/without-answer, applicable/scored/error/unavailable counts; unknown claim applicability remains unknown. Descriptive observation means are not paired research statistics. Local CPU self-judge is opt-in and uncalibrated; no paid provider is used. The actual development-fixture judge returned invalid rubric JSON and was correctly recorded as failed with raw output/usage and unavailable metrics; no human answer judgment or benchmark score was fabricated. Paired/bootstrap and controlled timing/cost accounting remain the last M5 task.

M5 answer slice final verification: 164 Python tests/no skips/warnings; 19 Chromium tests on production Docker; Ruff/format/mypy/ESLint/TypeScript pass. All services healthy at schema 0008. All prior 6 runs/5 results/5 attempts and the one real failed judge record remain exactly unchanged after database/API/worker restart. Actual desktop/mobile failed-judge and empty-review views inspected; no live human answer labels submitted. The paired/bootstrap/timing/cost task remains unchecked.


## M5 comparison/accounting slice - 2026-10-15
M5 implementation is complete. 0009_comparisons adds independently leased, immutable paired-analysis snapshots/reports. API freezes run projections and latest explicit human/model evaluation IDs/metrics before queuing the sixth worker queue. Reports disclose controls, partial-run/scoring exclusions, planned/applicable/scored/error/unavailable counts, question means after repeat averaging, and seeded 95% percentile cluster bootstrap over split_group. Fewer than two groups yields no interval. Strict controls/incomplete scoring block inference; exploratory override is persistent, excludes missing repeats and mismatched question/scoring revisions, and never mixes scoring policies into one interval. No automatic winner or benchmark accuracy is claimed.

Observed p50/p95 use available final stage timers and disclosed linear sample quantiles. Attempt usage is deduplicated from retained attempts, includes all recorded judge calls (including failed structured output), and exposes potentially unobserved inference. Run/queue windows, completion rates and runtime metadata are retained. New experiments can record operator cold/warm cache declarations with required notes; these are not automatically verified. New index builds record pre-publication build duration; old values remain unavailable. Local energy/hardware cost/pricing remain unavailable, not zero. No paid provider or new research labels. Remaining work starts at M6: charts, filters, failure explorer, complete exports and read-only demo; M7 still needs the actual curated benchmark and delivery checks.

Final M5 comparison checks:180 Python tests/no skips/warnings;22 Chromium tests plus3 final focused comparisons checks; Ruff/format/mypy/ESLint/TypeScript pass. Two actual development-only comparisons complete; singleton intervals and unreviewed answer quality remain unavailable. Both complete reports and all earlier runs/results/attempts/failed judge survive database/API/worker restart unchanged. No benchmark result or paid provider. M6 remains unchecked.

## M6 dashboard completion - 2026-10-15
M6 software is complete: immutable topic/difficulty subgroups, accessible paired/latency charts with coverage tables, failure explorer and exact answer/source links, durable checksummed evidence ZIPs with retained reload/download state, and an offline read-only synthetic demo. Selected timing samples and full-run accounting remain distinct; unavailable scores never become zero. M7 remains unchecked and requires real corpus acquisition, owner-reviewed benchmark labels, controlled experiments and delivery/restore checks.

Final full Python suite: **186 passed, no skips or warnings**, against real disposable PostgreSQL rag_test, including migration round trip through 0010_exports. Six new M6 integration tests cover frozen subgroup selection/timing coverage, diagnostics/source lineage, archive contents and hashes, pending-assessment non-backfill, idempotency conflict, terminal source guards, stale/expired/shutdown leases, capacity failures and immutable evidence. Full production browser suite: **25 Chromium tests passed**, including offline zero-API demo, filter/trace workflows, accessible missing-score charts, export ambiguous-retry/reload recovery, axe checks and responsive layouts at 375/768/1024px. Rendered actual charts and synthetic mobile demo/diagnostics were visually inspected.

Ruff lint/format (112 files), strict mypy (89 source files), ESLint and both TypeScript projects pass. Matching Python/migrate/frontend Linux production images start successfully; db/api/worker/web are healthy at 0010_exports. Final logs: ignored artifacts/m6-final-pytest.txt and m6-final-browser.txt.

Actual filtered comparison **494d1f73-beb8-4602-8347-dfab5fe7e037** uses hybrid run6d4ea27a-4ce5-4f73-8cbb-fcd39a6e9336 vs browser reranked run642285ff-ec0c-4915-a581-d32687cb08c4, model source, topic transactions and difficulty medium. One question/group means no interval; retrieval delta0 and unreviewed answer quality remain unavailable. The existing failed judge stays an error. Actual browser diagnosis follows that judge-error signal to exact result829269bb-6b2d-4558-8a8b-d92d60352756 and canonical source. No new inference or human review was submitted.

Completed export **353f8611-b7b2-46cb-8a92-a2bc6428376f** downloads through the Next.js proxy after reload and service restart: 209614 compressed bytes, 709782 uncompressed bytes, 65 files (64 independently hashed entries plus checksums.json), SHA-256 **3abd40df9b822aa5b8c68a277098979a93434a3dbd38b5f011ed5a0004e6b664**. All entry hashes and the frozen export-manifest digest match. Historical changed code is explicitly unavailable in provenance/availability.json; this archive does not claim a complete historical runtime or include original binaries/model weights.

Exact SQL snapshots show all6 runs/5 results/5 attempts/1 failed judge/3 comparisons/1 export unchanged after database/API/worker restart; all pre-M6 rows are also identical. Evidence: ignored artifacts/m6-prior-before.json, m6-{before,after}-restart.json, m6-persistence-verification.json, m6-live-{browser,comparison,export}.json, m6-live-comparison.zip and final screenshots. Preserve these files, .env and all named/native caches and volumes. No benchmark findings, paid provider, remote CI, public deployment, performance guarantee or complete backup/restore is claimed.

## CI portability fix - 2026-10-16
Inspected actual failed GitHub logs for runs38744323560 (3091827),38737446756 (6ede367),38433992444 (257fb84) and38423981904 (ab83409). All four Python jobs fail in mypy on Windows-only subprocess.CREATE_NO_WINDOW references; the latest fails in extraction, embedding, generation, reranking and judge launchers. The existing os.name conditional expression did not exclude the unavailable symbol from Linux type checking.

Added rag_core/processes.py with a sys.platform statement guard recognized by mypy and reused it in all five launchers. Windows retains CREATE_NO_WINDOW; other platforms return0. Removed the now-unused jobs.py os import. CI explicitly checks both --platform linux and --platform win32. Upgraded checkout/setup-node from v4 to v5, verified both v5 action manifests declare node24, and pinned all three jobs to ubuntu-24.04 to avoid the moving ubuntu-latest image notice. Application Node24.14.0 and existing lockfiles are unchanged.

Verification after the final fix: Ruff passes,113 Python files already formatted; strict mypy passes for both Linux and Windows targets (90 source files each);135 non-integration tests pass,51 integration tests deselected; CI YAML/runner assertions and git diff --check pass. Docker engine was unavailable during this correction, so database integration/Compose checks were not rerun; prior M6 checks remain historical. No new GitHub workflow execution, commit or push was performed. All prior M5/M6 uncommitted work is preserved. Historical failed runs retain their old commit; a push containing the correction is needed to verify a new remote run. Do not rerun old commits expecting this local fix to apply.
