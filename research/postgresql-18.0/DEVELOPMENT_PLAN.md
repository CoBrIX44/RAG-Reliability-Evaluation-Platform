# Development qualification before held-out execution

This stage uses only the frozen105-question development split from dataset version `c68dbf7c-4f98-4431-b789-4d9fdd11a811`. It does not submit the45 held-out questions. Final parameters remain proposals until development qualification is complete.

Qualify the eight proposed cells: fixed/section chunks, each with lexical, dense, hybrid and hybrid-plus-reranking retrieval. Reuse the four ready indexes and one dense chunk universe per strategy for dense/hybrid/reranking. Keep240-token chunks,32-token overlap, top-k5,1024 context tokens,128 maximum output tokens, candidate depth20, RRF constant60 and seed0.

Qualification uses **one greedy repeat per development question**, yielding105 planned observations per cell and840 if all eight are submitted. This differs deliberately from the final three-repeat proposal: it checks software execution, evidence coverage and traces before spending the full repeat budget. It does not estimate independent answer randomness or establish a research winner. Record timing as uncontrolled-cache observations; do not claim cold/warm cache control or known local financial/energy cost.

Start with `section/dense`. Inspect its actual typed failures, saved prompts, retrieval/delivered evidence and model execution identity before submitting the other cells. Require complete observation counts and disclose failures. If a resource or prompt limit requires a configuration change, preserve old runs and record a revised development campaign rather than rewriting them. Lock any final selected settings before submitting the test split. Correctness and faithfulness stay unavailable without valid answer assessments; AI gold review is not a human answer judgment or judge calibration.

The operator uses a deterministic submission key bound to its complete prepared definition and cell, written locally before the POST. Repeating a submission resolves the same durable run. Changes to prepared inputs are rejected against an existing campaign receipt. All heavy inference stays in the existing worker.

Run from the repository root:

```powershell
uv run python -m scripts.prepare_development_runs prepare
uv run python -m scripts.prepare_development_runs submit --cell section/dense
uv run python -m scripts.prepare_development_runs status
```

Preparation is read-only apart from the local receipt. Submission requires the manifest-bound successful restore report for private backup `data/backups/m7-20261016-02`, plus live matching dataset/index lineage. Other development cells require explicit `submit --cell <strategy>/<method>` calls. This preparation command does not submit tests; the separately launched completion controller below can do so after qualification.

Receipts, exact requests, manifests and observed status stay under ignored `data/research/postgresql-18.0/development-*.json`. A prepared request is not a submitted or completed experiment. Check `development-execution.json` and live status for actual progress.

## Resumable completion controller

`scripts/complete_m7.py --watch` is an operator process using the existing HTTP API. Inference, paired analysis and evidence ZIP generation remain durable worker jobs. The owner authorized finishing M7; this controller was launched on 2026-10-16. It polls every30 seconds and holds an OS-released single-process lock. Machine sleep or process exit stops orchestration; queued worker jobs persist.

It requires all eight development runs to complete with105 successes each and no failures. It verifies identical development question revisions/gold, frozen dataset and execution identities, then saves `completion/locked-controls.json` before any held-out submission. It retains all proposed retrieval methods and budgets unchanged; this is software qualification, not quality-based selection. Held-out execution is45 questions ×3 greedy repeats ×8 cells =1,080 planned observations. No test output tunes settings.

After terminal test runs it prepares up to30 real unreviewed answer cases, queues exploratory paired comparisons and worker ZIPs, verifies outer/member checksums, writes the actual benchmark report, and creates/verifies a post-experiment private backup. Failed/partial runs stay disclosed. Answer assessments, independent human calibration, known local cost and a factual-accuracy finding are never invented. The owner subsequently selected exploratory retrieval delivery with answer quality unvalidated on2026-10-17; see DELIVERY_SCOPE.json. After actual complete execution, comparisons, checked exports/report and verified isolated restoration, the controller can end `completed_exploratory` and record scoped M7 completion. Partial/failed execution remains an attention state. Missing answer quality and calibration are never marked complete.

To inspect or resume from the repository root:

```powershell
Get-Content data/research/postgresql-18.0/completion/state.json
Get-Content artifacts/m7-completion-watch.txt -Tail 2
uv run python -X utf8 scripts/complete_m7.py --watch
```

Run only one controller. The private `completion/controller-process.json` records the launched process and log paths; historical PIDs can be reused after reboot, so inspect its actual command line before stopping any process. Stopping orchestration does not cancel already queued durable runs. Temporary connection/timeouts and HTTP408/429/500/502/503/504 enter `waiting_for_api`, with30-second polls and a stop on the fifth consecutive failure. Invalid configuration/data and other HTTP errors stop immediately. Errors are saved in `state.json`; relaunch after correction reuses receipts and deterministic submission keys. Every prepared configuration field is checked against submitted/resumed manifests. Preserve matching API/worker source identity throughout unfinished runs. Keep Docker and the machine running. Timing on this shared host has uncontrolled cache and verification load, so it is not a controlled cold/warm latency claim.
