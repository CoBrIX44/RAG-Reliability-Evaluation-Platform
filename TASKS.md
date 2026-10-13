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
- [ ] Hybrid RRF and cross-encoder reranking.
- [ ] Versioned answer rubrics, judge adapter, human review.
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
