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

M3 real database tests verify publication/export/import round trips, review gates, source spans, immutable snapshots, optimistic conflicts, duplicates, and split leakage. Browser fixtures verify curation/publication, Unicode annotation selection, fresh-review requirements, accessibility, and responsive layout. Live Docker UI saves and edits candidate evidence annotations; malformed JSONL reports its physical line and commits nothing. The live candidate remains unreviewed, unpublished, and labeled as a development fixture.

## M4 Baselines
- [x] Fixed-token/section chunks with canonical span lineage and a pinned tokenizer.
- [x] Durable lexical index variants, immutable publication, retries, and lexical inspection UI.
- [x] Rank-order token-budget packing with retained/truncated/omitted source traces.
- [x] Independently checked evidence-group recall and passage precision core.
- [x] Compatible embedding storage, sentence-transformer indexing, and exact dense retrieval.
- [ ] Generation adapter, run manifest, cancellation and result persistence.
- [ ] Connect evidence scoring to saved question results and complete the question trace UI.

M4 is in progress. Lexical inspection is a usable vertical slice, not a saved experiment. A live labeled development corpus was indexed/searched with the actual pinned MiniLM tokenizer; context truncation and original source inspection are exposed. Dataset labels remain unreviewed/unpublished. Local dense embedding inference and queued exact retrieval are implemented; measured answer runs remain pending. Dense slice verification: 109 Python tests on real rag_test, 13 Chromium tests, lint/type checks, actual local model build/query/source inspection, and unchanged dense metadata/results after database/API/worker restart.

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
