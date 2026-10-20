# Dataset card

Status: M7 curation frozen and locally published:150 source-reviewed questions (10 human/140 AI),105 development/45 test across23 groups. Exploratory benchmark execution/report completed2026-10-20; see research/postgresql-18.0/BENCHMARK_REPORT.md. Retrieval results do not establish answer correctness or independent human validation.

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

## Development software fixture
Separate from this planned research card, the live workspace has one authored transaction question in a published development_fixture version. The project owner explicitly approved its reference answer/fact and annotated source, with reviewer Project owner. It uses the development split and transactions-smoke group. Its publication and actual local-model runs verify the software pipeline; they are not benchmark sampling, a numbered PostgreSQL release, or a research conclusion.

## Actual M7 source preparation - 2026-10-16
Official postgresql-18.0-docs.tar.gz, SHA-256 f0dfc5b0882aa68ca471e9930a0dcfe4644a10a9b9613c60d6d14bfc9c224d44, 3,845,019 bytes. Acquisition uses the fixed release archive rather than a moving major-version URL. See research/postgresql-18.0/acquisition.json for timestamp, per-file hashes and excluded pages; LICENSE.postgresql.txt preserves archive copyright/permission. The checksum was locally captured over official HTTPS, not verified against a signed upstream digest.

Purposeful 40-page subset: 8 pages each for SQL, transactions, indexes, configuration and troubleshooting, 1,173,549 source HTML bytes, 2,013 canonical sections under source-v1. 1,103 other HTML pages are excluded from retrieval (the license page is retained separately for attribution). This is a limited domain sample, not an exhaustive PostgreSQL manual. Corpus version 99d7fb4a-1d33-4417-b40e-7f36aa485c02; manifest hash 0f9b9556142214165cb5f4cc9f28f439bcb76d68e8ad361cba98407d7fed3b41. Local binding maps each original hash to document/revision and extraction hashes.

Dataset draft aee91608-6a2b-4f6f-afa4-dcf4c10d0021 has 10 Codex-authored candidates:2 per topic,8 proposed answerable/2 proposed unanswerable;7 easy/1 medium/2 hard. All 10 are candidates, reviewer blank, review timestamp null and split unassigned. Answerable spans reference published canonical sections, independently of chunk IDs. The two unanswerable cases require missing deployment information; corpus-wide human validation is still required. These counts describe proposals, not validated labels. Provisional source-page groups need a leakage/relatedness audit before split assignment. No held-out split, final publication, judge calibration or benchmark execution exists. Target 150 reviewed labels remains unmet. The project owner chose review in the Datasets screen; do not auto-approve any candidates.

## Current annotation progress
The original10 gold questions are now owner-reviewed by explicit conversation attestation, recorded as Project owner against unchanged content. Both previously blank unanswerable references were filled only after separate explicit owner approval of the exact expected-abstention text. These are dataset gold reviews, not judgments of generated answers.

Batch02 adds20 unreviewed proposals, leaving all10 reviewed records unchanged. Current total30:24 proposed answerable/6 proposed unanswerable,6 per topic and10 each easy/medium/hard. Four new cases cite multiple source documents; another cites multiple sections of one document. Twenty new questions still need individual review. All splits remain unassigned; source-document grouping proposes25 components, subject to human relatedness/paraphrase/cross-reference audit. No research dataset is published and no benchmark result exists. The 150-reviewed-question gate remains unmet. source-v1 retains HTML navigation boilerplate; annotations address body text, but retrieval can be affected by this noise.

## AI review provenance and revised curation policy
The owner authorized AI source review on2026-10-16. Current gold labels:10 human/20 AI reviewed, with30 total drafted questions and no published research version. Same assistant authored and source-reviewed batch02; this is not independent annotation or human validation. Typed review_source is retained with reviewer/time and all frozen gold outputs. AI reviews cannot establish judge calibration or answer accuracy. The revised150-question target is source-reviewed, with human/AI counts reported separately. Additional independent human validation would strengthen any research claim.

The AI pass corrected seven questions/rubrics/evidence annotations, including explicit parameter names not retained in canonical source-v1, missing joint evidence and missing requested facts. Only two corrected batch02 items still genuinely require multiple source documents; do not advertise the original four as necessary multi-document questions. Current source grouping proposes26 components, with manual relatedness auditing pending. All splits remain unassigned. HTML definition-term loss and navigation boilerplate are corpus limitations; the frozen source is unchanged.

## M7 frozen benchmark curation - 2026-10-16
Published local research dataset version **c68dbf7c-4f98-4431-b789-4d9fdd11a811**, manifest SHA-256 **f857d3b849ee33858262614e9af5eaeedbb1e6057ea7ad483e98b996d8082ccf**, contains150 source-reviewed questions:10 human/140 AI,120 answerable/30 unanswerable,30 per topic. Gold source spans cover37 of the40 frozen source documents.16 questions have multiple required facts; only2 require multiple source documents. Difficulty is subjective:19 easy/80 medium/51 hard, not an equal-count quota.

Frozen grouped split:105 development questions in15 groups and45 test questions in8 groups (23 total). Development topics: SQL20,transactions23,indexes21,configuration22,troubleshooting19; test: SQL10,transactions7,indexes9,configuration8,troubleshooting11. Development has19 unanswerable/7 human reviews; test has11 unanswerable/3 human reviews. Whole groups take precedence over exact per-topic or answerability ratios. No retrieval/answer output was used for split selection.

See research/postgresql-18.0/CURATION_REVIEW.md and SPLIT_MANIFEST.json for grouping, deterministic selection and limitations. All negative cases concern missing instance-specific information; this does not validate corpus-absence technical questions or calibrated abstention. Same assistant authored/reviewed140 labels and performed grouping: no independent human validation, human answer review or research accuracy claim. No benchmark answer run or assessment has been submitted. Development configuration selection and the controlled report remain pending.
