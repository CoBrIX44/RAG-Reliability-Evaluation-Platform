# Dataset card

Status: planned; no curated research dataset exists yet.

## Intended use
Compare retrieval strategies on one frozen PostgreSQL documentation release. Not a general benchmark of all database knowledge or a guarantee of safe production answers.

## Required publication metadata
Dataset version/hash; corpus version/hash; PostgreSQL release; document URLs and licenses; acquisition date; question count; topic/difficulty/answerability distributions; author/reviewer process; annotation rubric version; exclusions; development/test grouping and deduplication procedure; evidence completeness limitations.

## Question schema
id, text, answerable, reference_answer, required_facts, evidence_groups (canonical document revision, section ID, span offsets, alternative grouping), topic, difficulty, split, review_status, provenance. Offsets use Unicode code-point positions in the stored normalized text, not original PDF byte positions. Source mapping preserves original page/anchor where available.

## Review
Human review validates facts, answerability, and evidence against the frozen corpus. Record disputed cases and adjudication. Generated questions remain candidates until reviewed. Test-set labels are held out from tuning workflows.

## Known limitations
Initial sample is small; labels may miss alternative relevant passages; topics may be imbalanced; no generalization claim beyond this version/domain; automated answer evaluation may disagree with humans.

## Release gate
Schema passes; all published questions reviewed; evidence resolves to snapshot; duplicate/leakage check complete; split frozen; licensing/attribution recorded; dataset statistics computed from actual records. Do not fill this card with invented counts or scores.
