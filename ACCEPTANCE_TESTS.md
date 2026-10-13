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
