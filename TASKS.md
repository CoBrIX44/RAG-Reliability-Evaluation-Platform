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
- [x] Select numbered PostgreSQL release and record corpus provenance/license.
- [x] Curate150 source-reviewed questions, freeze grouped split, publish dataset card (10 human/140 AI).
- [x] Run exploratory experiments and export an evidence-backed report (answer quality unvalidated).
- [x] Verify backup/restore, operations guide, and exploratory final handoff.

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

## M7 source/first-review slice - 2026-10-16
- [x] Acquire pinned PostgreSQL 18.0 subset, license, checksums, exclusions and published lineage.
- [x] Prepare/import10 source-linked unreviewed draft candidates and owner-facing review pack.
- [x] Verify repeat import, source linkage, honest UI and worker backlog/idle behavior.
- [ ] Obtain150 actual human-reviewed labels; audit groups/leakage and freeze split.
- [ ] Execute/export controlled benchmark and answer-review/calibration sample.
- [x] Verify isolated Docker database/artifact/model backup and restore.
- [ ] Complete benchmark report and final delivery.

M7 first-slice checks:192 Python tests passed with no skips/warnings on disposable real PostgreSQL rag_test, including4 new offline synthetic archive integrity/path/member-limit/idempotency tests and2 worker backlog/idle-poll tests. After the test import typing correction, all6 new tests passed again. Ruff and formatting pass (118 files), strict mypy passes for Linux and Windows targets (93 source files each), ESLint/both TypeScript projects pass. Matching api/worker/migrate and web production builds/startup pass; all four services healthy at schema 0010_exports.25 production Chromium tests pass. Actual research draft screen inspected at desktop/mobile, with honest publication/review badge and no375px page overflow; no browser mutation or review was submitted.

Actual API import/re-import resolves the same40-document corpus version 99d7fb4a-1d33-4417-b40e-7f36aa485c02 and10-candidate datasetaee91608-6a2b-4f6f-afa4-dcf4c10d0021 without duplicating membership. Import polling was interrupted by the planned API image restart; rerun completed via existing checksum/provenance guards. Candidate spans resolve uniquely within published revisions. Live state confirms zero reviews, all splits unassigned, zero published research dataset versions. All prior6 runs/5 results/5 attempts/1 failed judge/3 comparisons/1 export remain exactly unchanged after service recreation, and the earlier evidence ZIP bytes/checksums still match. No benchmark inference, human label, paid call or research conclusion was created. Evidence: ignored artifacts/m7-live-preparation.json, m7-final-pytest.txt, m7-final-browser.txt, m7-final-mypy-linux.txt, m7-verified-mypy-win32.txt and m7-candidates screenshots. Complete backup/restore is not yet verified.

## M7 backup/restore continuation - 2026-10-16
Implemented scripts/backup_workspace.py and rag_core/backup.py for private, checksummed Docker workspace snapshots and isolated restore rehearsal. Backup stops API/worker while capturing a custom PostgreSQL dump and artifact/model bytes, then restarts them in finally. It retains runtime.env privately, exact service-image archives, source/locks (including dirty files), and local research receipts. Internal model-cache symlinks become regular archived bytes; escaping links are rejected. Snapshot scope excludes rag_test and separate native caches. No live or named volume is deleted.

Actual backup data/backups/m7-20261016-01 completed:248 recorded files totaling4,175,852,875 bytes, plus the manifest/report. Restore used an internal network, unique disposable PostgreSQL container with1 GiB tmpfs, no host ports and no worker. The saved image archive loaded successfully, PostgreSQL custom dump restored transactionally, and all23 public tables matched complete frozen row counts/SHA-256 values.83 artifact files (2,388,669 bytes) and86 model-cache files (3,535,868,678 bytes) matched per-entry hashes. Restored API readiness passed;41 original document hashes,1 completed evidence-export download, all6 saved runs and3 comparisons verified. Temporary containers/network were removed only after ownership checks; restored files remain under ignored data/restore-checks for inspection. All four live services are healthy, and the previous6 runs/5 results/5 attempts/1 failed judge/3 comparisons/1 export remain exactly unchanged.

Final full Python suite:199 passed/no skips/warnings on disposable rag_test, including7 new synthetic backup integrity/path/inventory tests. Ruff/format pass (final formatter123 files), strict mypy passes for Linux and Windows targets (95 source files). No frontend code changed in this backup continuation; the prior25 Chromium pass remains the latest browser verification. No benchmark inference, new human review, research dataset publication, paid call, commit or push occurred. Backup files contain private configuration/data and stay ignored/local. Proof is data/backups/m7-20261016-01/restore-report.json (bound to backup-manifest.json hash), artifacts/m7-backup-{create,restore,pytest}.txt and m7-backup-mypy-{linux,win32}.txt. This verifies same-machine Docker restore, not offsite/machine-loss recovery or historical inference replay.

Prepared research/postgresql-18.0/EXPERIMENT_PLAN.json: a DRAFT, unexecuted8-cell proposal across fixed/section chunking and lexical/dense/hybrid/reranked retrieval, using240-token chunks/32 overlap, top-k5,1024 context tokens,128 output tokens and3 greedy repeats. All8 proposed cells validate against current IndexCreate/ExperimentCreate models. Dataset version remains null and auto_submit=false. Primary proposal is section/hybrid_rerank versus section/dense test-set correctness, with whole-group bootstrap and explicit assessment-source gates; secondary/exploratory comparisons and deterministic-repeat/failed-judge limitations are recorded. This is not a preregistered final test design or an executed benchmark.

M7 is still incomplete:10 authored candidates remain unreviewed/unassigned, with no published research dataset. Owner chose individual review in Datasets. Do not infer blanket review from “move forward.” Continue real annotation toward150 questions, group/leakage audit and split freeze before controlled experiment execution and final report. BACKUP_RESTORE.md now provides the exact backup/rehearsal/recovery scope and commands.

## M7 curation progress
- [x] Record explicit owner review of the original10 unchanged gold questions.
- [x] Save separately approved expected abstentions for both original unanswerable items.
- [x] Add20 source-linked candidate questions without modifying reviewed records.
- [x] Add/test read-only curation audit and receipt-based append workflow.
- [ ] Review the20 new candidates; expand toward150 reviewed questions before split freeze.

## M7 recorded review and second batch - 2026-10-16
The owner explicitly stated “ive reviewed them so lets continue to the next step.” Once Docker was restored, the live database still had all 10 original questions as candidates, with content exactly equal to the original batch receipt. Recorded that explicit attestation against those unchanged question/fact/evidence records as Project owner (existing session reviewer label), using revision-checked PATCH. This is a conversation-supplied gold-label review, not a claim that the owner had already saved review status in the UI. Local review-attestation-01.json retains the quote, scope, prior/content hashes, saved revisions and recording timestamps. No model-answer assessment was created.

Two original unanswerable items had blank reference fields. Requested review of new expected-abstention text; the owner explicitly approved “The provided corpus and question do not contain enough information to determine that” for both. Saved exactly that text with reviewed status and retained abstention-review-01.json. The first post-review audit now has no review/reference/evidence/duplicate gaps; its only blockers are unassigned splits and the 150-question target. Do not apply this approval to future candidates.

Added 20 authored candidates in candidates-batch-02.json to the SAME dataset aee91608-6a2b-4f6f-afa4-dcf4c10d0021. It retains the initial UI name PostgreSQL 18.0 benchmark candidates — batch 01; no replacement dataset was created. All 20 new records are candidate/unassigned/blank-reviewer. Existing 10 records remain byte-for-byte unchanged during append. Repeating the append command resolves its receipt and creates no duplicates, preserving later human edits. Four new questions require evidence from multiple documents; another uses multiple sections of one document. Evidence quotes are exact, whitespace-normalized matches mapped back to canonical Unicode code-point offsets, not chunk IDs.

Current draft:30 questions,10 reviewed/20 candidates,24 proposed answerable/6 proposed unanswerable,6 per topic,10 each easy/medium/hard; all30 splits unassigned, no published research version. Audit groups these into25 conservative components by declared group/shared source document/exact duplicates, and explicitly requires manual paraphrase/cross-reference and unanswerability checks. Current issues are20 missing new reviews,30 unassigned splits,1 sample-target gap. Group components are proposals, not an automatic split or proof of semantic independence. HTML navigation boilerplate remains in source-v1; record this as a retrieval limitation rather than rewriting the frozen corpus.

New read-only scripts/audit_benchmark.py validates the live draft against the frozen corpus and checks draft_revision before/after reading. It records full question snapshot/hash and separate issue counts; it never writes labels or splits. scripts/append_review_batch.py imports bounded batches through the existing atomic JSONL API, validates corpus/quote lineage, records a batch hash/UUID receipt, and refuses silent edits to existing content. See research README for commands. Original batch specifications remain historical candidate proposals; current review state is in PostgreSQL and explicit attestation receipts.

Final full suite:207 Python tests pass, no skips/warnings, on disposable real PostgreSQL rag_test. Eight new independent tests cover document-level split leakage across different sections, missing review/reference/span/target issues, normalized duplicate/foreign lineage rejection, manual-check disclosure, and exact Unicode offsets/ambiguous quote rejection. Ruff/format pass; strict mypy passes Linux and Windows targets (99 source files). Actual app inspection verifies the new three-fact/two-document savepoint candidate, rendered canonical quotes, unchecked review state and no375px page overflow; no browser submission was made. No frontend code changed this continuation; prior25 Chromium suite remains historical, with this additional actual read-only browser check. Evidence: data/research/postgresql-18.0/{review-attestation-01,abstention-review-01,review-batch-02,curation-audit-03,curation-audit-04}.json and ignored artifacts/m7-review-{pytest,mypy-linux,mypy-win32}.txt plus batch02 browser/screenshots.

M7 remains incomplete. Next review the20 Candidate items in the existing dataset, then author/review the remaining120 toward150 total. Do not freeze a10- or30-question research benchmark or run the planned test matrix prematurely. No new inference, quality-score claim, answer review, publication, commit or push occurred. The verified m7-20261016-01 backup predates these owner reviews/new candidates; take a fresh checkpoint backup before final experiment execution/delivery. Current operator/audit helpers postdate deployed images; rebuild matching services and a truthful revision before new benchmark runs.

## M7 AI-review continuation
- [x] Apply owner-authorized AI source review to20 candidates, with seven source/rubric corrections.
- [x] Preserve human/AI provenance in API, JSONL, frozen gold snapshots, audit and UI.
- [x] Build/verify all four frozen-corpus indexes and lexical/dense chunk-universe parity.
- [ ] Source-review120 additional questions, then audit/freeze groups and execute the benchmark.

## M7 owner-authorized AI source review and indexes - 2026-10-16
Owner explicitly instructed “you review yourself and then continue with next step.” Applied this as authorization for AI source review, not a human attestation. Research protocol now targets150 explicitly source-reviewed questions with disclosed reviewer provenance; the earlier150-human-review requirement is superseded for this owner-authorized workflow. Never claim these AI reviews are independent human validation. Existing10 owner-reviewed question rows are exactly unchanged.

Actually inspected all20 batch02 candidates against frozen canonical passages and context. Saved seven content/evidence corrections: clarify the unanswerable orders-count question assumes its table exists; replace generic savepoint-definition gold with the rollback action actually asked; add the expression-index definition as joint evidence and scope to non-null text; directly annotate index-only visibility obligations instead of generic MVCC evidence; reword two parameter-specific questions because source-v1 drops their definition-term names; add the missing VACUUM FULL compaction fact to its rubric. The 20 AI review records/rationales and before/after content are retained in data/research/postgresql-18.0/ai-source-review-02.json. This is same-assistant authorship and source review, not independent annotation or an application judge run. Four missing-instance-data questions remain unanswerable based on underdetermination; do not describe that as exhaustive semantic proof of corpus absence.

Added typed review_source=human|ai to QuestionInput JSON (default human for existing legacy records). No SQL migration or existing published-snapshot rewrite. Provenance survives immutable publication/JSONL export/import. The frontend preserves AI source on save, labels AI versus Human reviews, and leaves its human-attestation box unchecked for AI records. A user must explicitly check it and enter a reviewer to record a human review. The audit separately counts human_reviewed_count/ai_reviewed_count. Actual UI shows10 Human/20 AI reviews with correct unchecked human attestation and no375/768/1024px page overflow. Current30-question audit has only30 unassigned splits and the150-sample-target gap;26 conservative source components, still requiring relatedness/paraphrase audit. No research dataset has been published.

Prepared the four planned240-token/32-overlap indexes through the existing durable worker:
- fixed lexical e364f1f2-d3e0-45a3-bb54-2ba9beac0849:647 chunks
- fixed dense 3f2535e5-c20b-4d38-996f-870df84d294c:647 chunks
- section lexical d0374982-a5fa-45b9-9b82-e4df2550452c:2119 chunks
- section dense ad61d00a-4a17-4c35-a7ba-a4698bae5ad2:2119 chunks

Exact ordinal/text/token-count/canonical-span hashes match between lexical/dense indexes for each strategy. Hybrid/reranking reuse the appropriate dense index's chunk universe. Repeating scripts/prepare_benchmark_indexes.py resolves the same ready IDs; no duplicates or answer runs are submitted. Actual pinned local CPU embedding inference ran for these builds. No paid provider, answer generation, model-answer evaluation or comparison run was submitted. Index preparation and question source review are not benchmark accuracy results.

Final209 Python tests pass/no skips/warnings against disposable real PostgreSQL rag_test; new tests verify human/AI audit separation and AI provenance through publication/export/import. All26 production Chromium tests pass, including a new synthetic provenance flow proving an AI save remains AI until explicit human review is saved. Ruff/format, strict mypy Linux/Windows99 source files, ESLint and both TypeScript projects pass. Matching api/worker/migrate/web production images build/start; all four services healthy at0010_exports. An initial frontend build caught a Windows encoding mistake in this edit; corrected UTF-8/line endings and the final build passes. Actual source-review editor visually inspected. No new research-answer scores are claimed. All previous6 runs/5 results/5 attempts/1 failed judge/3 comparisons/1 export remain exactly unchanged and the older ZIP hash still matches.

Evidence: ignored artifacts/m7-ai-final-{pytest,mypy-linux,mypy-win32}.txt, m7-ai-review-browser.txt, m7-ai-review-editor{,-mobile}.png, m7-index-parity.json; data/research/postgresql-18.0/{ai-source-review-02,curation-audit-06,index-preparation}.json. Current source/gold/index work is uncommitted, SOURCE_REVISION863b267-dirty. The older verified backup predates these labels/indexes; refresh at the next completed curation checkpoint. No split freeze, dataset publication, research winner or final M7 completion. Next author/source-review the remaining120 questions under the authorized AI workflow, keep human/AI counts explicit, audit relatedness/groups, freeze the split, then execute the controlled plan and report its limitations. Do not ask the owner to manually review every new candidate again; do perform real source review for every AI-reviewed label.

## M7 frozen benchmark curation - 2026-10-16
This section supersedes historical30-question/unassigned status.
- [x] Author and individually AI-source-review120 additional questions; preserve existing gold.
- [x] Audit related-source families and negative contexts; freeze105/45 grouped split.
- [x] Publish immutable150-question version, retain exact human/AI provenance and export JSONL.
- [x] Preserve source-review timestamps for split-only edits; test human and AI cases.
- [ ] Measure/select development configurations before held-out test execution.
- [ ] Execute planned comparisons, assess answers honestly and write the controlled report.
- [ ] Refresh/verify this checkpoint backup and finish delivery verification.

Published local research dataset version **c68dbf7c-4f98-4431-b789-4d9fdd11a811**, manifest SHA-256 **f857d3b849ee33858262614e9af5eaeedbb1e6057ea7ad483e98b996d8082ccf**, contains150 source-reviewed questions:10 human/140 AI,120 answerable/30 unanswerable,30 per topic. Gold source spans cover37 of the40 frozen source documents.16 questions have multiple required facts; only2 require multiple source documents. Difficulty is subjective:19 easy/80 medium/51 hard, not an equal-count quota.

Frozen grouped split:105 development questions in15 groups and45 test questions in8 groups (23 total). Development topics: SQL20,transactions23,indexes21,configuration22,troubleshooting19; test: SQL10,transactions7,indexes9,configuration8,troubleshooting11. Development has19 unanswerable/7 human reviews; test has11 unanswerable/3 human reviews. Whole groups take precedence over exact per-topic or answerability ratios. No retrieval/answer output was used for split selection.

See research/postgresql-18.0/CURATION_REVIEW.md and SPLIT_MANIFEST.json for grouping, deterministic selection and limitations. All negative cases concern missing instance-specific information; this does not validate corpus-absence technical questions or calibrated abstention. Same assistant authored/reviewed140 labels and performed grouping: no independent human validation, human answer review or research accuracy claim. No benchmark answer run or assessment has been submitted. Development configuration selection and the controlled report remain pending.


User stopped work2026-10-16. Dataset curation/publication complete; new checkpoint02 backup created, isolated verification interrupted/unverified. Resume from CODEX_HANDOFF user stop checkpoint; no automatic continuation.


## M7 development preparation continuation
- [x] Prepare/validate eight development-only requests without inference submission.
- [x] Add deterministic retry keys, manifest receipts and status operator.
- [x] Add/test exact-image reuse and bounded restore commands.
- [ ] Recover Docker engine, finish checkpoint02 restore verification and rebuild matching Python images.
- [ ] Submit/inspect section/dense development baseline, then qualify remaining cells.

Latest offline suite172 passed;54 integration tests deliberately deselected while Docker recovery is pending. No benchmark answer run or score exists. See latest CODEX_HANDOFF for actual commands and owner restart status.


## M7 live execution checkpoint - 2026-10-16
- [x] Recover Docker and verify checkpoint02 restore with exact tables/files/API checks.
- [x] Rebuild matching Python services; pass full226-test database suite.
- [x] Submit/inspect development dense baseline and queue the other seven cells.
- [x] Verify all eight manifests select development only and retain retry identity.
- [ ] Finish840 planned development observations; inspect errors and lock final controls.
- [ ] Execute held-out matrix and valid explicit answer evaluation, then controlled report/export.
- [ ] Refresh post-experiment backup and complete delivery.

Campaign is running in the durable worker, not complete. See DEVELOPMENT_STATUS.md and uv run python -m scripts.prepare_development_runs status for live state. Preserve matching images/source identity while unfinished. No research accuracy finding or human answer review has been invented.

## M7 resumable completion work - 2026-10-16

- [x] Implement/test a single-process operator that checks complete development qualification before freezing and submitting unchanged held-out controls.
- [x] Implement retained keys/manifests, real unreviewed answer-case preparation, exploratory comparisons, checked worker exports, actual report and post-experiment restore orchestration.
- [x] Launch controller and verify live waiting_for_development state; baseline52/105 succeeds,0 fails at inspection.
- [x] Run239 Python tests against rag_test; Ruff/format139 files and Linux/Windows typing103 files pass.
- [ ] Complete840 development observations and qualify all eight cells.
- [ ] Execute1,080 held-out observations after controls freeze; inspect real failures and coverage.
- [ ] Complete actual comparisons/evidence report and generated-answer assessments/calibration with truthful provenance.
- [ ] Verify post-experiment backup and final handoff; M7 remains incomplete.

Operator implementation is not execution evidence. See DEVELOPMENT_PLAN.md and private completion/state.json for recovery/live progress. Frozen Python runtime identity is unchanged. Keep local CPU worker and Docker running; shared-host/cache timing is uncontrolled.

## M7 recovery and operator hardening - 2026-10-17

- [x] Inspect saved progress/processes:226 successful development observations/0 failures at last receipt; native controller absent, live API unavailable.
- [x] Attempt Docker startup and identify actual inaccessible Secrets Engine socket failure; retain all images/data/volumes.
- [x] Add exact prepared-request verification and bounded transient API retry states;20 focused controller tests and Ruff/format pass.
- [ ] Resume existing services and controller after owner's Windows/Docker restart; verify actual database progress before reporting updated counts.

No held-out experiment, new answer assessment or completed M7 report is claimed. Full integration verification awaits the engine.

## M7 Docker recovery continuation - 2026-10-17
Docker engine29.8.2 subsequently recovered; all four existing services are healthy without image rebuild/replacement. API/worker execution identity both match source hash1123f6e613ba27ca7a9b1a97bbabe3159d6d074e1d101c8db8fbff041cda0f5e/revision863b267-dirty. Live progress verified228/840 successful development observations,0 failures, with fixed/dense resuming its existing run. No duplicate development or held-out runs were submitted. Native controller restarted at10:14:17 UTC with launcher PID30516; check private controller-process.json/actual command line rather than assuming historical PID ownership. Logs artifacts/m7-completion-watch-20261017{,-error}.txt.

Actual completed section/dense and fixed/lexical runs each retain105 successful results/86 applicable scored retrieval cases. DEVELOPMENT_DIAGNOSTICS.md reports descriptive retrieval coverage with confounding/known-evidence limitations. A deterministic30-trace development sample is retained privately with null reviewers/judgments;0 parsed citations/0 exact markers and1 output-limit hit are execution diagnostics, not quality scores. No answer evaluation was recorded.

20 focused controller tests and192 offline tests pass (54 integration tests deselected in that offline command). Follow-up real rag_test integration and Linux/Windows typing are being checked separately; do not infer completion from their launch. No frozen runtime source, images, gold labels or immutable historical results were changed. M7 remains IN PROGRESS; machine/Docker must stay awake for the remaining sequential inference.

## M7 recovery verification completed - 2026-10-17
Executed192 offline tests (54 integration deselected) and54 real PostgreSQL integration tests (192 offline deselected): all246 tests pass across the two commands; integration duration109.23 seconds. Strict mypy Linux/Windows both pass103 source files after correcting a synthetic HTTPError fixture's header type. Ruff/format pass for the changed controller/test files. No runtime core source/image rebuild or new frontend verification. Integration log: artifacts/m7-recovery-integration-20261017.txt.

Controller PID30516 is active, error log empty, phase waiting_for_development. Last observed 2026-10-17T10:19:22.046945+00:00: 237/840 development successes,0 failures, no held-out submissions. Existing worker advances after Docker recovery. M7 is still incomplete: remaining development qualification, held-out execution, actual answer assessment/calibration/report/exports and final recovery rehearsal remain. See research/postgresql-18.0/DEVELOPMENT_DIAGNOSTICS.md for actual completed-run diagnostics and limitations.

## Owner-selected exploratory delivery scope - 2026-10-17
The owner explicitly selected: “Deliver an exploratory report with answer quality unvalidated.” This supersedes the earlier human-answer-calibration completion gate for M7 delivery only. DELIVERY_SCOPE.json records the exact choice; the report must retain unavailable correctness/faithfulness/citation-support/abstention-quality metrics, no human calibration, and primary factual-accuracy hypothesis not established. Retrieval results never become answer-accuracy findings. Future validated accuracy research still needs valid assessments and independent calibration.

The frozen150-question gold,105/45 split, eight development configurations and full1,080-observation held-out matrix are unchanged. Before test submission the controller freezes this delivery scope with the controls. It may mark M7 completed_exploratory only after all eight135-observation held-out runs and all eight comparisons complete, all requested ZIPs verify, the actual report is written and manifest-bound isolated recovery passes. It then appends truthful final handoff/status from the terminal receipt. No current completion is claimed; inference is still running.

Added actual hardware/resource observations and an unreviewed30-case development answer guide. The controller report includes observed stage p50/p95/counts with unavailable values preserved and raw accounting retained.27 focused operator tests pass, including failed/partial/missing-scope delivery rejection, timing-unit conversion and guarded/idempotent final handoff preserving owner notes. No new core source/image identity, answer judgment, paid provider, public deployment or Git commit/push.

## M7 scoped controller launch verified - 2026-10-17
Owner-selected exploratory-retrieval scope is active. Latest operator source includes guarded final documentation/checkbox updates, unavailable-preserving stage timing report and scoped completion checks.27 focused controller tests pass; Ruff/format and strict Linux/Windows typing of the changed test file pass. The earlier full246-test database verification remains historical; do not claim a newly executed253-test full suite. No runtime core source/image change.

Replaced only the native controller after verifying its exact PIDs/command lines; inference worker was not restarted. Active launcher PID34512 at 2026-10-17T10:27:03.7685979Z; logs D:\RAG Reliability & Evaluation Platform\artifacts\m7-final-scope-watch-20261017.txt and error counterpart, error log empty. Verified 250/840 successful development observations,0 failures, phase waiting_for_development, no held-out submissions. Proof artifacts/m7-scoped-controller-verification.json binds operator/scope hashes. The controller can finish the authorized exploratory delivery after actual remaining execution/export/recovery, but M7 is not complete now. Estimated remaining inference roughly10.5 hours from a30-case median, excluding later work and slower configurations; not a guarantee. Keep Docker/machine running and preserve frozen worker identity.

## Frontend refresh in parallel with M7 - 2026-10-17
The owner requested all six named taste/UI skills for UI/UX/fonts. Read the supplied/local skills and project contract; retained product workflows and rejected marketing-only AIDA/hero/GSAP suggestions. Updated DESIGN_SYSTEM.md. UI now uses bundled licensed Outfit +IBM Plex Mono (~62KB), green/graphite semantic light/dark themes, persisted appearance control, less repetitive shell copy, saved runs before configuration, page-scoped run filtering, focus-aware New experiment shortcut, and expandable retrieval/workflow tools. API contracts, form field names/order, source evidence, human/AI provenance and unavailable metrics remain intact. No Python source/image, package-lock or uv.lock change. Docker benchmark services were not restarted.

Native dev preview3001 was visually inspected with actual read-only data at1440/1024/768/375, light/dark screenshots and real-font loading. Added theme/filter accessibility flows and updated retrieval disclosure tests/alternate-port origin handling. Earlier E2E run had27/28 pass; remaining shortcut-focus bug was fixed by preventing the anchor default and moving focus/scroll explicitly. A subsequent dev-server test run encountered repeated navigation/recompilation and was stopped; it is not a passing suite. Current production build and ESLint/TypeScript checks pass. Calculated text/action/control contrast meets relevant token thresholds. Final production browser rerun remains pending.

Automatic approval review rejected starting the production preview server (only reason returned: blocked by policy). Asked the owner to run npm.cmd run start --workspace @rag/web -- --port3001 (use separate --port 3001 arguments). The native dev server was stopped to build; it is currently not the live preview. Do not claim final28-test success or final production visual inspection until actually executed. No public deployment/commit/push. Benchmark controller continues independently; shared-host frontend checks are uncontrolled load, not controlled latency research.

## Frontend refresh final verification - 2026-10-17
- [x] Bundle Outfit400-700 and IBM Plex Mono400/500 locally with licenses/source hashes; zero runtime external-font requests.
- [x] Apply coherent light/dark semantic themes, persisted/system appearance, updated hierarchy/spacing, saved-run filtering, accessible configuration shortcut and restrained disclosures.
- [x] Preserve routes, navigation names, field order, API behavior, real/missing metrics and review provenance.
- [x] Production build and npm check (ESLint +both TypeScript projects) pass.
- [x] All28 Chromium checks pass on the production preview in13.1 seconds, including new theme persistence/axe and run-filter/shortcut tests.
- [x] Inspect actual read-only light/dark UI at375/768/1024/1440; additional five real pages ×two themes ×four widths have no page overflow, page errors or external font requests.
- [x] Reconfirm Python source identity1123f6e613ba27ca7a9b1a97bbabe3159d6d074e1d101c8db8fbff041cda0f5e, unchanged package-lock/uv.lock and continuing benchmark controller (315 successful development observations/0 failures at inspection).

The owner started the built production frontend at http://127.0.0.1:3001 after automatic approval review blocked agent startup. Final production browser/visual checks are now complete; that earlier block no longer prevents verification. Port3000 remains the older Docker frontend, and API/worker/database/images were not restarted/rebuilt. The owner-started3001 process should remain open for this preview. Any future source edits require a native frontend rebuild/restart to appear there; do not rebuild frozen Python experiment services. No public deployment, commit or push.

Evidence: artifacts/ui-refresh-{light-desktop,dark-desktop,dark-375,dark-768,dark-1024,datasets-dark}.png, ui-refresh-live-verification.json, ui-theme-contrast.json. Seven-axis heuristic self-review: purity4/5, task clarity4/5, typography4/5, spacing4/5, feedback4/5, keyboard/accessibility4/5, responsive behavior4/5. This is an implementation self-review, not independent usability research or blanket accessibility certification. Earlier browser failures uncovered/fixed real tablet overflow, theme-interpolation contrast and shortcut focus; the final28-test run passes. M7 itself is still running under the chosen exploratory scope.

## Landing page — 2026-10-17
- [x] Add `/` landing with Instrument Serif/Ostrich Sans, local licensed fonts, and a clearly synthetic actual demo image. Keep workspace at `/experiments`.
- [x] Integrate exact Lenis1.3.27/GSAP3.15.0 with reduced motion and route cleanup.
- [x] Verify production build, npm check, and all30 Chromium tests (13.0s), including mobile/theme axe checks, no landing API calls and Lenis teardown.
- [x] Keep frozen API/worker images and running benchmark untouched. Root frontend package-lock changes are explicitly authorized for this task; old copy retained privately.

Landing follow-up hook triage: removed only the redundant3px colored left border from .run-progress (globals.css); retained its existing1px semantic outline and explicit state/count text. No suppression added. Other pre-existing workspace accents are outside this single-finding task.

## Integrated landing and live frontend — 2026-10-17
Owner approved the landing and requested integration with the actual project. Fixed demo Local workspace and404 Open experiments links to /experiments. Web standalone Docker runtime now copies public assets; the actual synthetic demo JPEG returns200 in the container. Built only web, then applied docker compose up -d --no-deps web. Main local URL http://localhost:3000 now serves the landing and updated research workspace; native preview ports are no longer needed for normal use. API/worker/database IDs and creation times are unchanged (before snapshot in artifacts/frontend-integration-services-before.json). No backend/image/volume changes or research data mutations.

Executed npm check and real Docker standalone build successfully. All31 Chromium checks pass against Docker3000 in15.1s. Added landing→workspace→home round-trip check and corrected404/demo link assertions. Separate GET-only live smoke traversed landing/demo/workspace/documents/datasets/comparisons/settings with actual API, PostgreSQL and worker ready, saved run rows loaded, no page errors or desktop overflow. Visually inspected real loaded workspace and landing. Evidence artifacts/frontend-integration-live.json and integrated-real-{experiments,landing}.png.

M7 controller34512 remains active:412/840 development successes at inspection; held-out execution/report/export/final recovery still pending. Do not label M7 finished or retrieval scores answer accuracy. Shared-host frontend build activity is uncontrolled load and does not establish controlled latency. Current host/frontend lock differs from frozen API/worker lock by authorized Lenis/GSAP addition.

## Workspace identity and motion delivered — 2026-10-17
Owner requested matching actual project pages to the approved landing. Shared local Instrument Serif/Ostrich Sans now replace Outfit for workspace prose/headings and navigation/labels respectively; technical evidence/SQL/IDs retain Plex Mono. Added workspace-editorial.css for paper/ink/rust light/dark tokens, readable type, restrained outlines, underlined active nav and mobile adjustments. Shared app/fonts.ts prevents duplicate font definitions. Updated actual synthetic demo screenshot to match current styling.

WorkspaceMotion adds GSAP heading movement and Lenis scrolling per route; ticker/context/Lenis are destroyed on route changes/unmount or dynamic reduced-motion changes. Nested evidence/SQL panes, sidebar and form controls preserve native scrolling. Live result rows are never animated. Initial accessibility tests found opacity-animation contrast failures; fixed by removing opacity entirely, preserving full text contrast through transitions. Mobile subtitle crowding was removed.

Verified npm check and Docker standalone web build. Final32 Chromium tests pass on Docker3000 in14.8s, including new workspace route/reduced-motion/font/cleanup checks and all existing provenance/forms/trace/axe flows. Live GET-only visual/layout audit covers five pages ×four widths375/768/1024/1440 ×two themes. Representative real desktop/mobile experiments and datasets inspected. No page overflow in audit; evidence artifacts/editorial-layout-audit.json and editorial-*.png.

Only web was rebuilt/replaced with --no-deps. API96f206e0aecc, worker223c2fc3546c and db9c40de4d14f3 remain the same healthy containers. M7 controller continues waiting_for_development; no Python source/image/experiment/review changes in this frontend task. Latest UI is http://localhost:3000/experiments. Native3001/3002 previews are historical builds and should not be used for this change. No deployment, commit, push or new dependency changes.

## Project workflow diagram — 2026-10-17
Created docs/assets/project-workflow.svg (editable, accessible title/description) and its1600×1510 PNG rendered with Chromium. Shows source publication, parallel index/dataset preparation, frozen manifest, worker retrieval/context/generation, traces/metrics, comparisons, exports and runtime structure. Optional answer assessment and unfinished research limitations are explicit. Showed PNG in commentary before editing README as requested; then embedded PNG near the top with SVG/architecture links. No runtime/model/benchmark changes. Visually inspected diagram and verified image/source paths and SVG text bounds; no application tests needed for documentation/assets only.

## Owner-requested pause — 2026-10-17
Stopped verified native M7 controller processes34512/11684 and gracefully stopped the existing worker container. API/db/web stay running; no run cancellation/resubmission. Post-stop API confirms840/840 development and340/1080 held-out successes, zero held-out failures. Fixed hybrid70/135 retains running state for lease recovery; five cells queued. Source files, PostgreSQL/artifact/model volumes preserved. No Git commit/push or new full backup. Automatic approval review rejected the additional database-export command with blocked by policy; do not claim a fresh dump. Read PAUSED_HANDOFF.md first next session; resume existing images/worker and scripts/complete_m7.py --watch, verifying no duplicate controller. Do not rebuild frozen Python images. M7 remains incomplete and explicitly paused until owner resumes.

## M7 resumed at owner request — 2026-10-19
Read PAUSED_HANDOFF and current protocol/scope before restarting. Existing API/db/web healthy; worker was exited and no native controller was running. Verified API and restarted worker exact execution identity b4234e19dc8a6e2a2b71be533b7457bf60f3239d03dfbf40e2a7f064a1acbb9e equals locked-controls.json, frozen source hash1123f6e613ba27ca7a9b1a97bbabe3159d6d074e1d101c8db8fbff041cda0f5e/revision863b267-dirty. Started existing worker with docker compose start worker (Compose also ran its existing completed migrate dependency); no build, recreation or code/configuration changes. All four services subsequently healthy.
Native controller restarted hidden with existing .venv Python and scripts/complete_m7.py --watch, launcher36160; private controller-process.json updated. Logs artifacts/m7-resume-20261019.txt and error counterpart (empty at verification). Existing fixed/hybrid held-out run8c123798-3b39-4c52-be63-74b81910706d advanced70→71 successful observations,0 failures, proving execution resumed. Development840/840 completed; held-out341/1080 successful,0 failures at inspection. No duplicate runs, new reviews or answer-quality claims; phase waiting_for_heldout. Historical pause record annotated as resumed. M7 remains incomplete under exploratory scope; keep machine/Docker running. Operational checks only; no new test-suite execution or fresh backup was claimed.

## M7 paused again at owner request — 2026-10-19
Verified controller processes36160/28164 by exact command line and stopped them; gracefully stopped existing worker via docker compose stop --timeout30 worker. No native controller remains and worker is exited; API/db/web remain healthy. Post-stop API: development840/840; held-out531/1080 successful,0 failed. Fixed lexical/dense/hybrid completed135 each, fixed hybrid_rerank126/135 stored running for lease recovery; four section cells queued. Retained every existing run ID/result and volume; no rebuild/cancellation/resubmission. Private pause-receipt-20261019.json records actual counts; PAUSED_HANDOFF.md current section supersedes earlier resume notes. No fresh full backup, Git commit/push or new test-suite run. Resume only after owner instruction using existing images/worker and scripts/complete_m7.py --watch; verify old metadata is not a live controller and do not duplicate submissions. An unfinished attempt may rerun, completed observations remain immutable. M7 remains paused/incomplete under exploratory scope.

## M7 resume requested; startup blocked — 2026-10-20
Owner requested resume. Read-only checks: API/db/web healthy; worker remains stopped and no native controller running. API frozen source1123f6e613ba27ca7a9b1a97bbabe3159d6d074e1d101c8db8fbff041cda0f5e and execution digest b4234e19dc8a6e2a2b71be533b7457bf60f3239d03dfbf40e2a7f064a1acbb9e match locked controls. Live API preserves531/1080 held-out successes,0 failures: fixed lexical/dense/hybrid135 each; fixed hybrid_rerank126, four section cells queued. Automatic approval review rejected combined operational verification/worker-start command with blocked by policy before execution. No startup/rebuild/resubmission occurred. Asked owner to run docker compose start worker, then uv run python -X utf8 -u scripts/complete_m7.py --watch from repo root; keep controller terminal open. Verify actual processes and worker identity/count advancement after user starts it; historical controller-process.json is not current. No new test-suite run or backup claimed.

## Owner-started M7 continuation verified — 2026-10-20
Owner ran the worker/controller commands in their terminal. Existing worker healthy with frozen execution digest b4234e19dc8a6e2a2b71be533b7457bf60f3239d03dfbf40e2a7f064a1acbb9e and source1123f6e613ba27ca7a9b1a97bbabe3159d6d074e1d101c8db8fbff041cda0f5e. Controller OS lock is held; native process enumeration did not expose the owner-terminal process, so do not invent PID or trust old controller-process.json. No duplicate controller started. Live API verified held-out advancement531→535/1080, zero failures at2026-10-20T04:29:11.473134+00:00; development840/840 remains complete. All four services healthy. Updated historical pause note and development qualification checkbox; remaining held-out, comparisons, exports/report and final recovery stay pending. Private verification receipt operator-resume-verification-20261020.json. Existing owner terminal must stay open. No code/config/image changes, new submissions, test-suite run, reviews or research outcome claims.


## M7 exploratory delivery completed

<!-- m7-exploratory-delivery:82b6219f2b9e3d1906fec0a59add4340995b7ce76428b10de73e06492f30ba41 -->

Recorded at 2026-10-20T09:25:30.283278+00:00. All eight development runs qualified; all eight held-out runs completed 135 successful observations each (1,080 held-out observations); all eight exploratory comparisons and requested evidence exports completed. Outer/member checksums and the post-experiment manifest-bound isolated restore passed. See research/postgresql-18.0/BENCHMARK_REPORT.md and private data/research/postgresql-18.0/completion/delivery.json for actual evidence.

M7 is complete only under the owner's exploratory-retrieval delivery scope. Answer quality is unvalidated; human calibration was not performed; the primary factual-accuracy hypothesis is not established. Missing quality/cost remain unavailable. The backup captures experiments/evidence before this terminal receipt/document update; same-machine recovery is not offsite recovery or inference replay. No commit/push or public deployment is implied.

## Final M7 recovery and operator verification — 2026-10-20
Fixed final backup failure caused by the active Windows controller.lock. copy_research excludes only the exact ephemeral completion/controller.lock, preserves state/evidence and unrelated lock files, and discloses exclusion in the manifest. Original incomplete backup retained separately without overwriting. Corrected subprocess stdout typing and inventory length typing in the native operator; no frozen Python core/API/worker source or images changed.40 focused backup/controller tests, Ruff/format and strict Linux/Windows operator typing pass. No fresh full Python/browser suite was run for this operator/docs change.

Fresh private backup data/backups/m7-post-experiments-01 sealed377 files /4,467,779,569 bytes. Manifest SHA-256 d9d5b07a80c6cd81a6fdff08198600c87e989a480a80ec8f318eff125308a261. Isolated restore passed23 table fingerprints,100 artifact files,86 model files and API checks for41 originals,17 total exports,22 runs and11 comparisons. Exact installed image IDs reused only after archive integrity verification. Temporary owned restore containers/network removed; original API/db/worker/web IDs preserved and healthy. This is same-machine recovery, not offsite recovery or inference replay.

Terminal private receipt records completed_exploratory /m7_complete=true /execution_complete=true /analysis_complete=true /restore_status=passed.840 development and1,080 held-out observations succeeded, zero execution failures, eight comparisons and16 campaign evidence exports verified. Answer quality remains unvalidated, human calibration absent, factual-accuracy hypothesis not established, cost unavailable. Backup precedes terminal receipt/docs and a typing-only operator cleanup; captured frozen runtime images are the execution authority. README, PRD, dataset card, delivery checklist, backup guide and pause history updated to current scoped delivery status. No new reviews, claims of calibrated quality, public deployment, commit or push. The completed controller has exited; no campaign terminal needs to stay open.

## Open-source source-release audit — 2026-10-20
Owner selected Apache-2.0 for original code via explicit answer. Added official root LICENSE/NOTICE, dependency/font/model/PostgreSQL THIRD_PARTY_NOTICES, beginner quickstart and a clearly synthetic transaction fixture, contributor extension map, private-reporting guidance and release checklist. Updated README/font license documentation. No dependency locks, app behavior, frozen images or live database were changed. GSAP retained as owner-requested separately licensed non-OSI dependency; original Apache code license does not relicense it or LGPL dependencies/source quotations/fonts/model weights.

Heuristic audit:252 tracked files and409 historical text blobs across nine local commits/refs; no forbidden private paths or credential-pattern/exact private credential matches. History blobs capped at2MiB; not a guarantee or scan of inaccessible remotes. Final current tree258 publishable files had no credential-pattern matches; new-doc relative links and Git ignore exclusions pass. Sensitive matches/values were never printed; private reports in ignored artifacts/release-audit-20261020.json and release-final-scan-20261020.json.

Separate local clone603c98f, no .env/database/model cache: npm ci (zero npm vulnerabilities reported), npm check, production build and four selected landing/demo Chromium checks pass (4.1s) on temporary3003 production server. Temporary audit server stopped afterward; original Docker services unchanged. Not a full fresh backend/model experiment test: that remains an explicit release-checklist item. Final release changes still need owner-reviewed commit/push, newest remote CI and publication approval; no commit/tag/push/deploy performed. M7 remains completed_exploratory with unvalidated answer quality; morning controller terminal may be closed.

## Launch-video preview — 2026-10-20
- [x] Owner-invoked brag composition: 22s landscape with local project fonts, actual synthetic read-only demo captures, qualified public report excerpt, original instrumental bed and CC0 accents. Isolated ignored brag-output/; app dependencies/runtime unchanged.
- [x] Hyperframes0.8.181 browser check: zero runtime/layout/contrast errors,40/40 contrast samples passed; five non-blocking composition-organization warnings remain. Source-reveal keyframes and rendered snapshots inspected; preview HTTP200 on3004.
- [x] Owner approved with “render it”; local final MP4 render, poster-frame bake and decoded media verification completed. See launch-video delivery below.

## Launch-video delivery — 2026-10-20
- [x] Owner explicitly approved export with “render it.” Local Hyperframes0.8.181 delivery render completed:22s1920x1080 at30fps/660 frames, H.264/AAC stereo.
- [x] Settled source-inspection poster extracted at6.5s and baked as frame0; final duration/frame count/audio unchanged. Compressed audio MD5 matches original; measured peak -13.6dB. Decoded frame0/report/closing and poster visually inspected. Final brag-output/brag.mp4, brag.jpg, share-copy.txt and delivery-verification.json retained locally. No publication or push.

## README video integration — 2026-10-20
- [x] Added the owner-approved walkthrough immediately after the workflow explanation, before Reading order. Clickable poster and explicit MP4 link use repository-relative docs/assets paths; final video/poster and media credits copied into publishable assets. Verified identical SHA256 against approved outputs, local README links, Git ignore inclusion and whitespace. No commit/push.

## README native video player correction — 2026-10-20
- [x] Synced owner web commit40b7aec; removed duplicate thumbnail and isolated the actual GitHub attachment URL as its own paragraph. GitHub's GFM render API now emits a native video element; original remote markup emitted only a link. Local README fix awaits owner commit/push.

## Vercel frontend install fix — 2026-10-20
- [x] Replaced unconditional root Husky binary execution with a guarded installer that skips Vercel/CI/production/HUSKY=0 before importing Husky; local hooks still install.
- [x] Added apps/web/vercel.json to run locked root npm ci --include=dev and web build, preserving root module paths. Documented frontend-only deployment settings.
- [x] Four skip branches verified without node_modules; isolated VERCEL=1 npm ci passed (180 packages, zero reported vulnerabilities), root Next.js/TypeScript paths verified, local prepare/check/production build and diff whitespace passed. Locks/backend unchanged. Owner push and successful hosted rebuild remain pending.

## Video-shotcraft promo delivery — 2026-10-20
- [x] Owner selected autonomous custom creation. Produced a separate 36s/1080p/30fps Remotion promo in ignored artifacts/shotcraft-promo; the earlier README walkthrough is unchanged. Actual landing and synthetic read-only demo captures retain local fonts, paper/ink/rust identity and explicit unvalidated-answer qualification. No private experiments, inference, paid provider or public publication.
- [x] Final H.264/AAC output: 1,080 picture frames, 8,293,835 bytes, SHA256 c981129f777c425ce9235fb82f7c31f1fd671f0aec7f70b3b3f2737ac0b3b111. Poster, caption and independent review accompany the movie.
- [x] Isolated TypeScript check, 16 shot QA stills, final decoded-frame inspection, five exact sampled workbench parity checks and editor browser inspection passed. Independent review resolved comparison-text splicing and late/truncated impact; six measured audio peaks are within 0.481 frame, max -10.6dBFS. No exhaustive every-frame, continuous subjective-listening or external-license revalidation claim. App dependencies/backend unchanged.
