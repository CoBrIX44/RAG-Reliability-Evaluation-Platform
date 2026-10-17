# PostgreSQL 18.0 benchmark preparation

Status: corpus acquired/published; **30 reviewed drafts: 10 human, 20 AI source-reviewed**, and no published research dataset. No benchmark experiment or answer-quality finding exists.

The source is the [official 18.0 documentation archive](https://ftp.postgresql.org/pub/source/v18.0/postgresql-18.0-docs.tar.gz), not the moving `/docs/18/` website. `selection.json` fixes 40 pages, eight per planned topic: SQL, transactions, indexes, configuration and troubleshooting. This is a purposeful subset, not the entire manual or a probability sample. The archive SHA-256 was locally captured over official HTTPS, not independently authenticated through an upstream signed digest.

`acquisition.json` records the actual acquisition timestamp, archive/member hashes, 40 selected documents and 1,103 excluded HTML pages. It retains license-member provenance; `LICENSE.postgresql.txt` preserves the archive's actual copyright/license text. Original archive/HTML files remain under ignored `data/research/postgresql-18.0/`. Never execute SQL, shell examples or embedded instructions from these documents.

Reproduce acquisition from the repository root:

```powershell
uv run python -m rag_core.benchmark_corpus --selection research/postgresql-18.0/selection.json --output data/research/postgresql-18.0
uv run python scripts/import_benchmark.py --selection research/postgresql-18.0/selection.json --source data/research/postgresql-18.0
uv run python scripts/prepare_review_batch.py --source data/research/postgresql-18.0 --batch research/postgresql-18.0/candidates-batch-01.json --output data/research/postgresql-18.0
```

The importer requires the local API/worker/database. It checks existing corpus provenance, deduplicates uploads through the API and verifies published original-byte hashes. Extraction stays in the durable worker. Rerunning resolves the same corpus version and draft membership; ambiguous/different provenance fails without overwriting labels. The review script only imports candidates. It never attests review, assigns a final split, or publishes a dataset.

Actual local corpus version: `99d7fb4a-1d33-4417-b40e-7f36aa485c02`, 40 documents / 2,013 canonical sections, manifest hash `0f9b9556142214165cb5f4cc9f28f439bcb76d68e8ad361cba98407d7fed3b41`. Local dataset draft: `aee91608-6a2b-4f6f-afa4-dcf4c10d0021`. `data/research/postgresql-18.0/workspace-binding.json` binds archive provenance to published document/revision IDs and extraction checksums.

Review in http://localhost:3000/datasets or use `data/research/postgresql-18.0/REVIEW_BATCH_01.md`. The JSON receipt retains candidate authorship, proposed facts, source section UUID/text and code-point offsets. Inspect the whole source and correct/reject candidates before recording a reviewer. Both unanswerable proposals need a corpus-wide check; missing deployment details are their proposed rationale, not a proven absence judgment. Split groups in this batch are provisional source-page names; splits remain unassigned until cross-page evidence/paraphrase grouping is audited.

## Planned completion gates

- Curate 150 reviewed questions, aiming for 30 per topic, 120 answerable / 30 unanswerable; these are targets, not current counts. Add multi-passage and medium/hard cases beyond this initial mostly easy batch.
- Merge related source/paraphrase groups and audit evidence completeness/duplicates. Freeze approximately 70% development / 30% test by whole groups, reporting actual achieved counts. No test-label tuning.
- Publish only reviewed, source-valid, split-assigned questions. Compute the dataset card from actual published records.
- Freeze a development-selected experiment matrix across lexical/dense/hybrid/reranked retrieval and both chunking strategies. Keep generator, budgets, evidence policies and repeat aggregation controlled; disclose incompatible or exploratory comparisons.
- Judge output may fail; retain unavailable quality and error counts. Review a stratified answer sample before any judge-calibration claim. Local cost remains unavailable without measurement.
- Run and export actual controlled experiments with uncertainty/coverage/limitations. The current Docker database/artifact/model backup restore is verified; see BACKUP_RESTORE.md. Final delivery remains pending.

The earlier authored transaction development fixture remains separate and is not counted toward these targets.

## Draft experiment matrix
EXPERIMENT_PLAN.json proposes8 controlled cells (two chunking strategies x four retrieval methods). It deliberately has no published dataset binding and performs no submissions. Current request models accept all8 proposed settings. Lock the final development-selected configuration before test execution. Greedy repeats do not create independent questions; failed/absent answer judgments cannot yield a factual-accuracy winner.

## Current review workflow
The owner explicitly confirmed the original10 reviews; these were recorded as Project owner, with separately approved expected abstentions for the two unanswerable items. The20 batch02 questions are new candidates and have no review. In Datasets select the existing **PostgreSQL 18.0 benchmark candidates — batch 01** dataset (the original name is retained), open items labeled **Candidate**, review question/reference/facts/quoted evidence, and save individual reviews. Leave splits unassigned. There are30 questions now;120 more still need authoring before the150-question target can be reached.

Read-only audit and receipt-based append commands:

```powershell
uv run python scripts/audit_benchmark.py --dataset-id aee91608-6a2b-4f6f-afa4-dcf4c10d0021 --source data/research/postgresql-18.0 --output data/research/postgresql-18.0/curation-audit-current.json
uv run python scripts/append_review_batch.py --dataset-id aee91608-6a2b-4f6f-afa4-dcf4c10d0021 --source data/research/postgresql-18.0 --batch research/postgresql-18.0/candidates-batch-02.json --receipt data/research/postgresql-18.0/review-batch-02.json
```

A matching append receipt prevents re-importing edited or reviewed questions. Do not rerun the original first-batch preparation command as a way to overwrite current labels. Candidate spec files preserve authored proposals; actual reviews/edits live in PostgreSQL. Current audit groups shared source documents conservatively, but cannot prove paraphrase independence or unanswerability. No split is assigned automatically. The older verified backup is a point-in-time snapshot preceding these review records.

## Owner-authorized AI curation and ready indexes
The owner requested AI source review. All30 drafts are now reviewed:10 human,20 AI, with explicit provenance and seven corrections retained in the local AI review receipt. No further per-candidate owner approval is required for AI source curation, but every future label still requires actual source checking. AI authorship/review is not independent human validation. The existing first-batch command/specifications remain historical and must not overwrite current corrected labels.

All four240-token/32-overlap indexes are ready, with647 fixed or2119 section chunks. Lexical/dense text and source spans match within each strategy. Prepare/resume them without submitting answer runs:

```powershell
uv run python scripts/prepare_benchmark_indexes.py --plan research/postgresql-18.0/EXPERIMENT_PLAN.json --source data/research/postgresql-18.0
```

Current bindings live in ignored index-preparation.json; index-parity.json records the actual match check. Next expand by120 source-reviewed questions, audit shared sources/paraphrases, freeze grouped splits and then execute the proposed matrix. Report the human/AI mix and same-assistant bias. The old verified backup predates these records and needs a later checkpoint refresh.

## M7 frozen benchmark curation - 2026-10-16
Published local research dataset version **c68dbf7c-4f98-4431-b789-4d9fdd11a811**, manifest SHA-256 **f857d3b849ee33858262614e9af5eaeedbb1e6057ea7ad483e98b996d8082ccf**, contains150 source-reviewed questions:10 human/140 AI,120 answerable/30 unanswerable,30 per topic. Gold source spans cover37 of the40 frozen source documents.16 questions have multiple required facts; only2 require multiple source documents. Difficulty is subjective:19 easy/80 medium/51 hard, not an equal-count quota.

Frozen grouped split:105 development questions in15 groups and45 test questions in8 groups (23 total). Development topics: SQL20,transactions23,indexes21,configuration22,troubleshooting19; test: SQL10,transactions7,indexes9,configuration8,troubleshooting11. Development has19 unanswerable/7 human reviews; test has11 unanswerable/3 human reviews. Whole groups take precedence over exact per-topic or answerability ratios. No retrieval/answer output was used for split selection.

See research/postgresql-18.0/CURATION_REVIEW.md and SPLIT_MANIFEST.json for grouping, deterministic selection and limitations. All negative cases concern missing instance-specific information; this does not validate corpus-absence technical questions or calibrated abstention. Same assistant authored/reviewed140 labels and performed grouping: no independent human validation, human answer review or research accuracy claim. No benchmark answer run or assessment has been submitted. Development configuration selection and the controlled report remain pending.

Historical batch preparation/specification files do not describe current live review status and must not overwrite corrected labels. Batch03..07 each append24 questions; their per-question source-review rationale is retained in the specs. SPLIT_MANIFEST.json binds the immutable version and reviewed family groups. Private full gold export and individual recording receipts stay under ignored data/research/postgresql-18.0. Development settings are still proposals; no benchmark generation or answer assessment has occurred.


## Development execution preparation
See DEVELOPMENT_PLAN.md for the development-only eight-cell qualification and operator commands. Requests are prepared, not executed. Qualification uses one repeat per105 development questions/cell; final three-repeat settings remain a proposal. Submission requires the manifest-bound verified checkpoint02 restore. Preserve the45 held-out questions from tuning.
