# Acceptance scenarios

These are contracts for meaningful automated/manual checks, not executed test results.

| ID | Scenario | Required observation |
|---|---|---|
| A01 | Upload supported text file | Job completes; section text and original source location are inspectable |
| A02 | Oversized/unsupported/scanned file | Clear actionable rejection; no misleading successful ingestion |
| A03 | Edit corpus after publishing | Prior snapshot/hash and run inputs remain unchanged |
| A04 | Import malformed JSONL | Line-specific errors; no partial published dataset |
| A05 | Evidence outside dataset corpus | Publication rejected with evidence lineage error |
| A06 | Compare chunk strategies | Same canonical gold evidence scores both; duplicated spans do not inflate recall |
| A07 | Restart worker mid-run | Expired lease reclaimed; committed results are not duplicated |
| A08 | Old worker attempts commit | Ownership token rejects stale publication |
| A09 | Cancel active run | Completed results retained; next question does not start after cancellation is observed |
| A10 | Provider timeout or missing judge | Typed error/unavailable score; zero is not substituted |
| A11 | Repeat submission with idempotency key | Same request returns same run; conflicting request receives 409 |
| A12 | Compare incompatible/partial runs | Differences and coverage visible; headline comparison blocked by default |
| A13 | Export completed run | Manifest matches stored hash and contains configs, evidence, outputs, and missing-score status |
| A14 | Keyboard-only core flow | Upload, form, sort, navigation, dialog, and evidence access remain usable |
| A15 | Small viewport/reduced motion | No page overflow or hidden controls; motion preference honored |
| A16 | Demo without credentials | Labeled demo readable; real inference action explains missing provider |
| A17 | Document contains executable instructions/HTML | Text cannot execute tools or unsafe browser markup |
| A18 | Backup and restore | Database plus blobs restore consistent corpus/run lineage |
| A19 | Hand-computed metric fixture | Empty, duplicate, alternative-evidence, unanswerable and no-claim cases match documented formulas |
| A20 | Dashboard performance check | Recorded reference machine and workload demonstrate or disclose p95 target failure |

## Dense inspection slice
Build lexical and dense indexes from a published corpus; dense chunk/query overflow is rejected. Exact compatible pgvector search returns source-linked cosine-ranked passages and packed context under its token budget. Query embedding stays in the worker queue and survives lease reassignment. Same index/request reuses one preview; failed previews are retryable, completed previews and vectors immutable. Stale owners and incompatible model/artifact/vector inputs cannot publish. Browser preserves query on failure, exposes retry/progress, distinguishes cosine similarity from correctness, renders source text safely, and has no page overflow at 375px. Actual public local model smoke is separate from software fixture tests and benchmark evaluation.

## Saved baseline slice
Create an immutable experiment from a reviewed dataset version and a matching ready index; reject missing inputs, empty splits and mismatched lineage. Submission uses an explicit global key; retry returns the original run even after local generation is disabled, and conflicts across experiments fail. A bounded worker generates local CPU answers from retrieval evidence without reference labels, scores original/delivered source coverage separately and saves full traces. Partial failures expose metric coverage and retained retrieval. Observed cancellation preserves prior results; a killed worker reclaims expired ownership, retains interrupted checkpoints and does not duplicate final results. Runtime/lock/source/artifact mismatch fails closed. Full prompt overflow fails without truncation. Browser deep links reopen saved results, separate gold/retrieved/delivered sources, display unavailable answer metrics, render HTML as text, preserve failed submission inputs/key, and remain accessible at small widths.

## M5 hybrid/reranking slice
Save an experiment with a reviewed dataset and same-corpus ready dense index. Hybrid combines separate lexical/dense ranks from that one frozen chunk universe using the recorded candidate depth, positive RRF constant, equal weights and deterministic ties. Cross-encoder mode scores the fused shortlist on the pinned CPU model and rejects paired-token overflow without truncation. Final top-k drives existing generation/context/evidence scoring. Reranker failure/interruption retains the pre-reranking candidate checkpoint, never substitutes success/final scores, and recovers under normal lease fences. UI distinguishes arm ranks, RRF, raw logits and actual quality metrics; retained candidates open canonical source spans. Older immutable baseline records remain exactly unchanged through the upgrade and restart.


## M5 answer-evaluation slice
Evaluate a successful saved answer with a frozen rubric and independent record; reject failed answers/wrong run-result pairs. Missing model configuration leaves automatic scoring unavailable and human review usable. Require ordered fact judgments, exact distinct answer quotes, explicit no-claim confirmation, reviewer/rationale, and original answer/evidence lineage. Use hand-computed partial facts, contradiction, unsupported claims, missing/unknown citations, no claims and unanswerable/exact-abstention cases. Invalid/truncated judge output keeps raw response/usage and has no substitute score. Identical keys replay; conflicting keys reject; corrections append. Expired owners cannot publish; shutdown leaves reclaimable jobs, attempts exhaust safely and runtime mismatch fails before inference. Terminal records and original run/results remain unchanged. Coverage includes latest failed/pending records and discloses unknown applicability and paired disagreement exclusions. Browser preserves ambiguous review inputs/key, separates human/model assessment, renders text safely and supports keyboard/375px layout.


## M5 paired analysis/accounting
Save two runs and an explicit evaluation source. New reviews do not change a frozen comparison; identical/concurrent keys reuse one snapshot, conflicting bodies reject. Failed/pending latest evaluations remain unavailable/error-counted. Repeat averaging precedes whole-group bootstrap; hand-computed unequal-group examples retain question weighting and deterministic seed/percentile results. A singleton group has no interval. Missing repeats and mismatched question revisions/groups/scoring policies exclude pairs; strict controls/partial/incomplete scoring block inference, and exploratory overrides stay visible. Unknown latency/usage/cost never becomes zero. Known usage counts retained attempts once and includes failed structured judge output. New operator cache declarations require notes; historical conditions remain unrecorded. Leases reject stale publication; stop/recovery/exhaustion/runtime mismatch behave safely; SQL protects immutable terminal reports/run lineage. UI supports deep links, safe text, coverage/CI units, keyboard local-table scrolling and 375px/no page overflow.

## M6 verified acceptance paths
- Frozen topic/difficulty filtering changes the selected paired population, rejects empty selection, recomputes selected timing coverage and preserves old reports/full-run accounting.
- Accessible quality/latency charts retain tables, omit missing-score marks, label interval limitations and use local scrolling without page overflow at 375/768/1024px.
- Diagnostics preserve frozen question/result lineage, filter explicit source and signal categories, and link to exact answer/canonical source traces without treating missing assessment as incorrectness.
- Run/comparison exports freeze evidence and pending-state membership, preserve idempotency, fence stale/shutdown publication, enforce resource caps and terminal immutability, stream downloadable ZIPs, and verify entry/overall checksums.
- The standalone synthetic demo performs zero API requests, exposes source evidence and supports both scenarios without submission controls. Exports are rediscovered after reload; actual archives and all prior saved evidence survive service restart unchanged.
