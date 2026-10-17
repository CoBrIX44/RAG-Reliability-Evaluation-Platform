---
name: rag-platform-research-evaluation
description: Implement evidence-grounded metrics and controlled RAG comparisons.
---

Read RESEARCH_PROTOCOL.md, DATASET_CARD.md, DATA_MODEL.md, and ACCEPTANCE_TESTS.md. Use published corpus/dataset versions and retain evaluator/model/prompt revisions.

Gold evidence uses canonical source spans and required-fact groups with alternatives. Deduplicate coverage. Persist pre-packing retrieval and delivered context separately. Keep correctness, faithfulness, citation support, and abstention separate. Handle undefined metrics explicitly.

Use independent hand-computed fixtures. Do not call a judged metric objective truth or a partial comparison a research winner. Aggregate repeated generations by question before paired statistics. Test-set labels are not tuning inputs. Record exclusions and judge/human disagreement.

Research artifacts contain actual outputs, provenance, manifests, sample counts, and limitations. Candidate questions require explicit source review before benchmark publication. The owner authorized AI source review on 2026-10-16; preserve review_source=ai separately from human reviews and disclose same-assistant author/reviewer bias. Never claim an AI-reviewed question is human validated.

Paired analyses use comparison_analysis.py and frozen /comparisons snapshots. Average all expected repeats per question, then resample whole split_group clusters and retain question-weighted estimation. Never bootstrap question repeats independently or give one group an interval. Preserve source/policy identity, latest failed/pending selections, exclusions and unavailable timing/cost. See CODEX_HANDOFF.md for the implemented analysis version and operator cache-declaration limits.

## M6 continuation rules
Subgroup filters must freeze before paired analysis; any change creates a new immutable report. Recompute selected timing samples and retain separately labeled full-run accounting. Missing quality/intervals are unavailable in both charts and tables. Diagnostic citation/missing-review signals do not establish incorrectness. Export only frozen evaluation selections; never backfill pending outputs or silently substitute changed historical code. Offline synthetic demos never count as research evidence.
