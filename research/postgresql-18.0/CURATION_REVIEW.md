# Frozen PostgreSQL18.0 benchmark curation

Verified2026-10-16. The owner authorized AI source review with “you review yourself and then continue with next step.” This is authorization to record AI review, not a human attestation.

Dataset version `c68dbf7c-4f98-4431-b789-4d9fdd11a811` has150 questions; manifest SHA-256 `f857d3b849ee33858262614e9af5eaeedbb1e6057ea7ad483e98b996d8082ccf`. It binds the already frozen40-document PostgreSQL18.0 corpus. No benchmark answers or research scores have been generated.

| Distribution | Count |
|---|---:|
| Human-reviewed gold | 10 |
| AI-reviewed gold | 140 |
| Answerable / unanswerable | 120 / 30 |
| Questions per topic | 30 |
| Easy / medium / hard | 19 / 80 / 51 |
| Multiple required facts | 16 |
| Necessary multiple-document evidence | 2 |
| Documents with annotated positive evidence | 37 of40 |

The original10 owner attestations and separately approved expected abstentions remain human-source records. Batch02's20 corrected AI reviews remain unchanged. Batches03–07 add120 questions with individual source-review rationales, exact supporting quotes, required facts and negative reasons. The same assistant authored and reviewed these140 AI labels. These are gold-label reviews, not assessments of generated answers or independent annotation.

Source review used the frozen canonical paragraphs and their context, rather than model-generated answers. It preserved qualifications such as Repeatable Read's first non-control-statement snapshot, non-HOT expression-index updates, PostgreSQL18 skip-scan behavior, session-versus-transaction advisory lock lifetime and crash durability versus corruption. Supporting spans use canonical section-local Unicode offsets; they do not depend on strategy-specific chunk IDs. The checks verified unique quote resolution and evidence lineage; those mechanical checks alone did not authorize review status.

All30 unanswerable items require unavailable instance-specific data or observations: live rows, settings, plans, resource measurements or transaction schedules. They test underdetermination, not exhaustive semantic absence of a technical fact from the corpus. They share a formulaic expected abstention. This is an easier and narrower negative class than general document-grounded unanswerability and must be reported that way. Difficulty labels are subjective; no empirical difficulty calibration was performed.

The grouping pass inspected all150 question texts, facts and negative rationales. It retains source documents together and merges selected related families: selection/ordering/pagination; join/table expressions; savepoints/rollback; uniqueness/payload/expression indexes; access methods/multicolumn indexes; and plan/index diagnostics. Existing groups and questions spanning multiple sources can merge families. Negative contexts are grouping anchors only, never positive retrieval evidence. Shared MVCC/row-lock/lock-monitoring evidence stays in one family; savepoint variations stay together. Distinct questions may reuse a fact within a family, but are not claimed to be150 independent observations.

The split generator sorted23 final components and evaluated20000 component selections using Python `Random(0)` with per-component selection probability0.3. It retained the first lowest objective: `100*abs(test_count-45) + 5*sum(abs(topic_test_count-9)) + 3*abs(test_unanswerable_count-9)`. It used labels and grouping only, with no retrieval or answer outputs. The achieved objective is36. Full component IDs, membership and source filenames are in `SPLIT_MANIFEST.json`.

| Split | Questions | Groups | SQL | Transactions | Indexes | Configuration | Troubleshooting | Unanswerable | Human gold |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Development | 105 | 15 | 20 | 23 | 21 | 22 | 19 | 19 | 7 |
| Test | 45 | 8 | 10 | 7 | 9 | 8 | 11 | 11 | 3 |

Development difficulty is14 easy/54 medium/37 hard; test is5 easy/26 medium/14 hard. Whole-family separation takes precedence over exact topic/answerability proportions. Eight held-out clusters are a small effective research sample. The full corpus remains retrievable for both splits; questions, rather than document access, are held out. Shared background concepts can still cross families. This grouping has no independent human semantic-deduplication validation.

The final read-only audit reports0 mechanical issues:150 reviewed, no unassigned splits, no normalized exact duplicates, valid gold lineage/bounds and no source/group crossing splits. Known relevant spans are not exhaustive relevance judgments. Corpus source-v1 retains navigation noise and can drop HTML definition terms; questions use canonical facts available to retrieval. The frozen corpus was not rewritten.

Applying splits changed only split/group/revision metadata. All existing gold text, references, facts, spans, reviewer/source and actual source-review times were preserved. The publication is immutable, repeated publication resolves the same version, and the150-row JSONL export has SHA-256 `b413aa7b3775c2d43d4d6e8c634b2a4acc50b1e114759099f5458f3c91e9a2fd`.

Private review receipts and full exports stay under ignored `data/research/postgresql-18.0`. The candidate JSON files preserve authored proposals and must not be reimported over current reviews. Next measure/select the development configuration, lock it before test execution, record actual runtime/model identities, then execute and assess the controlled matrix. Failed or missing quality assessments remain unavailable.
