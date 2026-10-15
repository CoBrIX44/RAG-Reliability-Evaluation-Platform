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
- [ ] Paired comparisons, bootstrap summaries, timing/cost accounting.

## M6 Dashboard
- [ ] Comparison charts/tables and topic/difficulty filtering.
- [ ] Failure explorer, exports, labeled read-only demo.
- [ ] Rendered UI/accessibility/responsive verification.

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
