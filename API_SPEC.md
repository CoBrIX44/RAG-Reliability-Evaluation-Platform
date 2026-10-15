# API specification

Design contract. Prefix /api/v1. JSON responses, UUID resource IDs, UTC ISO-8601 timestamps. Multipart for files; JSONL for dataset interchange. Generated OpenAPI must agree with implemented endpoints.

Implemented: health/workspace/capabilities, document/corpus publication and source inspection, reviewed datasets and JSONL interchange, lexical/dense indexes and queued dense previews, immutable experiments, saved local CPU runs, cancellation, evidence metrics, question results and attempts. /workspace reports stage baselines, actual database/schema/worker state, and configuration booleans without secrets. /capabilities reports lexical/exact dense strategies and retrieval_precision/retrieval_recall/context_recall. Hybrid RRF and cross-encoder reranking are implemented in saved runs. Answer evaluators, comparisons and full run-export jobs remain planned. Readiness returns 503 for database unavailability, migration mismatch or missing vector extension; liveness is independent of PostgreSQL.

Next.js exposes /api/health and a server-side /api/workspace proxy. The proxy validates response shape, applies timeouts, and returns sanitized 503 errors for upstream failure. INTERNAL_API_URL stays server-side.

Next.js /api/platform/{path} streams document requests to an allowlisted set of API paths. POST requests reject conflicting browser origins; client resource schemas validate responses. Local trust remains the deployment model.

| Method | Path | Purpose |
|---|---|---|
| GET | /health/live | Process liveness |
| GET | /health/ready | Database/schema readiness |
| GET, POST | /corpora | List/create corpus drafts |
| GET | /corpora/{id} | Corpus draft metadata |
| GET | /corpora/{id}/documents | List ingestion status and document metadata |
| POST | /corpora/{id}/documents | Upload document; 202 with document/job IDs |
| GET | /documents/{id} | Ingestion status and metadata |
| GET | /documents/{id}/sections | Paginated extracted sections |
| POST | /documents/{id}/retry | Reset a failed ingestion job's bounded retry budget; 202 |
| POST | /corpora/{id}/versions | Publish valid corpus snapshot; 201 |
| GET | /corpora/{id}/versions | List snapshots |
| GET, POST | /datasets | List/create dataset drafts tied to corpus version |
| GET, POST | /datasets/{id}/questions | List/create questions |
| PATCH | /datasets/{id}/questions/{question_id} | Edit full draft content with expected_revision; conflicts return 409 |
| POST | /datasets/{id}/import | Validate/import JSONL atomically |
| POST | /datasets/{id}/versions | Publish reviewed dataset snapshot |
| GET | /dataset-versions/{id}/export | Immutable dataset JSONL download |
| GET | /corpus-versions/{id}/sections | Paginated published source sections, with document names |
| GET | /corpus-versions/{id}/sections/{section_id} | One source section, checked against snapshot membership |
| GET, POST | /experiments | List/create immutable experiment definitions |
| POST | /experiments/{id}/runs | Queue run; 202 |
| GET | /runs | Paginated run list (filters arrive in M6) |
| GET | /runs/{id} | Manifest summary/hash, progress, metric coverage, and safe errors |
| GET | /runs/{id}/manifest | Complete frozen input manifest |
| GET | /runs/{id}/attempts | Paginated attempt states and retained checkpoints |
| POST | /runs/{id}/cancel | Request cooperative cancellation |
| GET | /runs/{id}/results | Paginated question summaries |
| GET | /runs/{id}/results/{result_id} | Full evidence/answer/evaluation/error trace |
| POST | /comparisons | Planned M5/M6: compare selected runs with compatibility report |
| POST | /runs/{id}/exports | Planned M6: queue full artifact export; 202 |
| GET | /jobs/{id} | Job progress and sanitized error |
| GET | /exports/{id} | Planned M6: export status and local download link |
| GET | /capabilities | Configured models, supported metrics and strategies; no secrets |

## Contracts
Experiment: corpus_version_id, dataset_version_id, retrieval configuration, chunking/index configuration, generation configuration, evaluator configuration, context budget, repeats, split, seed. Reject unsupported combinations and mismatched dataset/corpus lineage before queueing.

Question: text, answerable, reference_answer, required_facts[], evidence annotations[], topic, difficulty, split, review_status. Unanswerable questions have no required positive evidence and use an abstention rubric.

Run response: state, total/completed/failed/cancelled counts, timestamps, manifest_hash, metric summaries with applicable_count/scored_count/error_count, cost with pricing provenance, stage latency summaries.

## Validation and errors
400 invalid operation; 404 absent resource; 409 publication/state/version conflict; 413 oversized upload; 415 unsupported media; 422 schema/configuration failure; 503 unavailable dependency. Error envelope: code, message, field_errors, request_id, retryable. Never include credentials or stack traces.

Implemented ingestion pagination uses an integer offset cursor, append-only ordering by timestamp/ID (versions by version number, sections by ordinal), default 100/max 100; source sections default 20. Response: items and next_cursor (string or null). Offset pagination is an explicit M2 choice; M4 runs/results/attempts also use bounded offset cursors; keyset pagination is deferred.

Upload returns the document with job_id, state, checksum, byte_count, revision_id, section_count, and safe errors. SHA-256 content deduplicates within a corpus. Publishing an unchanged draft returns its existing version; incomplete/empty drafts return 409. A published manifest includes document/revision IDs, original and normalized-text checksums, extractor version, and source counts. Section offsets address NFC text joined by two newlines; source locations retain original PDF pages, Markdown/text line ranges, or HTML anchors and heading paths. Database triggers reject mutation or appending children to sealed evidence.

Implemented run submission requires Idempotency-Key and an empty JSON object: the same key/experiment returns the original run, including after local generation is disabled; a key reused for another experiment returns 409. Retry must not silently create another experiment run. Comparisons will reject incompatible runs by default; exploratory=true returns differences and restricted paired summaries.

## Implemented dataset contract
Dataset creation: name, description (optional), corpus_version_id, purpose (research or development_fixture). The corpus must be sealed; its lineage cannot change. Questions use text, answerable, reference_answer, required_facts[], evidence_groups[], topic, difficulty (easy/medium/hard), split (unassigned/development/test), split_group, review_status (candidate/reviewed), and reviewer. Candidate is the default. Explicit reviewed status requires a named reviewer; the server records reviewed_at. Ordinary clients submit full question content; PATCH additionally requires expected_revision and returns the incremented revision.

Evidence group: fact_index and alternatives[]. Each alternative contains spans[] that must all support the fact; alternatives are interchangeable sufficient evidence. Each span contains section_id, start_offset, and end_offset. Offsets are local to the canonical section and count Unicode code points, start-inclusive/end-exclusive. UUID membership, nonempty bounds, and positive evidence rules are validated; SQL triggers also enforce source membership/bounds. A question is limited to 200 total evidence spans. Evidence contains no retrieval chunk identifiers.

Publication requires nonempty questions, a reference answer or expected abstention, named human review, topic, split, and split_group. Answerable questions need a nonempty fact list and evidence for every fact. Unanswerable questions cannot have positive facts/evidence. One split_group and one gold source section cannot appear in both development and test. Exact normalized-text duplicates are rejected in a draft; paraphrase/topic leakage still requires owner review. Unchanged publication returns the existing version. The sealed manifest freezes question IDs/revisions/content, reviewer timestamps, corpus version/hash, purpose, and evidence policy. Later draft edits cannot change exported versions.

POST /datasets/{id}/import accepts multipart file with UTF-8 JSONL, one QuestionInput per nonblank line, up to MAX_JSONL_BYTES (10 MiB) and the configured question limit. All lines and evidence validate before any insertion. Errors contain physical line numbers in field_errors; nothing commits on error. Import asserts supplied reviewer metadata; it never promotes candidates automatically. Export emits the same interchange content, excluding server-owned IDs/revisions/timestamps, so it can import into a new dataset tied to the same corpus. Downloads stream through the web proxy. Dataset resource lists use the same offset pagination contract as ingestion.

## Implemented lexical inspection contract
GET/POST /indexes lists or queues durable lexical index builds. POST body: corpus_version_id and chunking {strategy: fixed|section, max_tokens: 1..4096, overlap_tokens: 0..1024 and below max_tokens}. Only sealed corpora qualify. Identical corpus/configuration submissions return the same index. GET /indexes/{id} returns pending/running/ready/failed, attempts, config, chunk_count, fingerprint, nullable manifest, and safe errors. POST /indexes/{id}/retry accepts only failed builds and resets the bounded attempt budget.

POST /indexes/{id}/search accepts query (1..4000 trimmed characters), top_k (1..50, default 5), and context_tokens (0..8192, default 1024). A ready index and matching cached tokenizer are required. Response includes ranked chunks, canonical source spans, returned_count, and packed context with exact token count and truncated/omitted chunk IDs. A span stores section_id plus section-local start_offset/end_offset and chunk-local text_start/text_end, all Unicode code points. No context text is reconstructed from decoded tokens.

Search uses plainto_tsquery with English configuration, ts_rank_cd normalization 0, and stable ordinal/ID ties. This is PostgreSQL full-text ranking, not BM25. The preview is bounded interactive inspection, not durable experiment execution. It does not generate or score answers, persist question results, or assert reviewer labels. Index-list pagination uses the existing offset cursor contract. The workspace stage is baselines; lexical_indexing is a capability and postgresql_lexical is now a supported retrieval strategy.

## Implemented dense inspection contract
POST /indexes also accepts retrieval: lexical|dense (default lexical). Dense chunks are limited to 254 content tokens; the model is the pinned MiniLM CPU baseline, not selected through arbitrary environment model IDs. Dense configurations include the embedding compatibility contract; incompatible configurations receive distinct fingerprints.

POST /indexes/{id}/dense-searches accepts the same query/top_k/context_tokens body as lexical search and returns 202 with a durable preview. It requires a ready dense index and a query fitting 254 content tokens. The API performs no model inference. GET /dense-searches/{id} polls pending/running/completed/failed, attempts, request, nullable result, and safe errors. POST /dense-searches/{id}/retry resets only failed previews. Identical requests for an index reuse the original preview, including completed results. Failed previews must be explicitly retried.

Dense results retain ranked source-linked chunks and packed context, strategy pgvector-exact-cosine-v1, and embedding contract/artifact/runtime metadata. Scores are cosine similarities, not answer correctness. Queries use the exact same contract/artifacts as the built index; mismatches fail closed. The synchronous /indexes/{id}/search endpoint accepts lexical indexes only (409 dense_preview_required for dense). Supported capabilities add dense_indexing and retrieval strategy pgvector_exact_dense; workspace stage is now baselines with saved runs.

## Implemented saved-run contract
POST /experiments accepts name, dataset_version_id, index_id, split (development/test), top_k (1..50), context_tokens (0..1536), max_new_tokens (1..256), repeats (1..3), and seed (0..2147483644). The sealed dataset and ready index must share a corpus version; the split must be nonempty and the planned question-repeat observations within MAX_RUN_QUESTIONS. Defaults are development, 5, 1024, 128, 1, 0. Identical definitions return the same immutable experiment. Arbitrary model/provider/prompt overrides are unsupported in M4.

POST /experiments/{id}/runs requires an ASCII Idempotency-Key (1..128 letters/digits/dot/underscore/colon/hyphen) and body {}. A new key creates a fresh execution. Submission freezes actual question snapshots/revisions, corpus/dataset hashes, index manifest, matching policy, generation contract, code/lock hashes, declared source revision, runtime and bounded settings. Only new submissions require LOCAL_GENERATION_ENABLED=true. GET /runs defaults to 20 rows (max 100); other run lists default to 100. The frontend shows 20 runs per page and links to /runs/{id}.

Terminal states are completed, completed_with_errors, failed, cancelled. completed_count means successful observations; failed_count means persisted failed observations; cancelled_count counts remaining observations only after cancellation finishes. Queued cancellation is immediate; active cancellation is cooperative and prevents further publication after observation. Completed rows and terminal runs are immutable. Interrupted attempts retain checkpoints, may be executed again, and never count as published results. Recovery is bounded by the frozen max-attempt budget. There is no terminal-run reset endpoint; submit a new key for another recorded execution.

GET /runs/{id} returns nullable means and applicable/scored/error/unavailable counts for retrieval_precision, retrieval_recall, and context_recall. Correctness, faithfulness, citation support, abstention quality, and cost remain unavailable. Stage timings are raw per-question milliseconds, not run-level p50/p95 summaries yet. GET /runs/{id}/results returns small question/answer previews and evidence scores. GET /runs/{id}/results/{result_id} returns the frozen question, original ranked retrieval, delivered context, raw answer/prompt/hash, token counts, finish reason, syntactic citation references, exact abstention marker, model/query metadata, errors, timings, and attempts. result_id distinguishes repeats; it is not question_id. Canonical source endpoints resolve gold/retrieved/delivered spans against the run's corpus version.

GET /runs/{id}/manifest downloads frozen inputs; full result exports, comparison endpoints and export jobs in the original route plan remain M5/M6 work. The API queues model work; it never performs answer inference. Next.js forwards Idempotency-Key only on allowlisted routes and keeps its same-origin mutation guard.

## Implemented M5 retrieval slice
POST /experiments additionally accepts retrieval_strategy: index|hybrid|hybrid_rerank (default index), candidate_k: 1..50 (default 20), and rrf_k: 1..1000 (default 60). Hybrid variants require a ready dense index from the dataset corpus and candidate_k >= top_k. Both lexical and exact dense arms read that same index's immutable chunks; no separate lexical-index ID is selected. Each arm contributes equal-weight reciprocal ranks, one contribution per chunk/arm. Ties use chunk ordinal then ID. Reranking scores the first candidate_k fused chunks before selecting final top_k.

Experiment/run configuration freezes the fusion contract and fixed reranker contract where applicable. Query traces add nullable pipeline metadata: lexical/dense rank-score-ID lists, the complete fused ranking, actual candidate depth/constant, optional reranker passage IDs/raw logits/paired token counts/model/runtime metadata, and stage wall times. Duplicate source text is not repeated in every arm list; immutable chunk IDs identify its lineage. Original candidate text/spans are retained in retrieval_candidates before reranking. Final retrieval retains the selected ranked passages and independently scored canonical gold coverage.

RRF strategy is hybrid-rrf-v1; reranked strategy is hybrid-rrf-cross-encoder-v1. A reranker error publishes a failed observation with retained candidates, not a successful fallback or invented final score. Interrupted attempts keep their candidate checkpoint; normal lease/recovery/cancellation fences apply. Cross-encoder inference/download stays in a bounded child of the durable worker. No new synchronous hybrid preview endpoint is introduced; public /indexes/{id}/search remains lexical-only, and dense previews remain queued.

/capabilities adds hybrid_rrf and hybrid_rrf_rerank strategy labels and hybrid_retrieval/cross_encoder_reranking features. Workspace stage stays baselines while the rest of M5 is pending. Existing completed runs and snapshots remain immutable and readable; no schema change/migration is required for these JSON configuration/trace additions.


## Implemented M5 answer evaluation
- GET /evaluation-rubric returns the full answer-evidence-v1 rubric and actual local_judge_enabled flag.
- GET /runs/{run_id}/results/{result_id}/evaluations?limit=100&cursor=0 returns newest-first records and next_cursor.
- POST the same /evaluations route, body {}, queues the explicit optional local CPU judge (202). LOCAL_JUDGE_ENABLED is required for a new submission; successful saved answers only. No inference runs in the API.
- POST sibling /reviews accepts {reviewer, judgment:{facts,claims,no_factual_claims,rationale}} (201). facts is an ordered array of covered|missing|contradicted matching required_facts. Each claim has exact answer excerpt text, support: supported|unsupported|uncertain, citations: string[] of inline P IDs, and citations_supported: boolean. Empty claims require explicit no_factual_claims=true. Exact abstentions have all facts missing and no claims. Human review does not require model configuration.
- Both POSTs require the same globally unique ASCII Idempotency-Key contract as run submissions. Identical retries return the existing record; changed body/result/kind conflicts with 409. A new key creates a new retained review/job, including retry after terminal failure. Earlier records cannot be edited/deleted.
- GET /runs/{run_id}/evaluations returns a separate post-hoc projection: total_observations, eligible_answers, without_saved_answer, separate human/model metric means and applicable/known_applicable/scored/error/unavailable counts, plus paired model/human disagreement counts and mean absolute difference. Selection is latest-record-per-result-and-source-v1; latest failed/pending scores are unavailable. Claim applicability can remain null/unknown. These are observation means, not question-group bootstrap statistics.

Evaluation records freeze complete rubric, exact answer/reference/facts/delivered text, original result trace hash and run manifest hash, and model/prompt/artifact/code/lock/runtime identity. output includes judgment/derived nullable metrics or safe error; actual raw model response/prompt/hash/token usage/finish/runtime survive invalid rubric output. State is pending|running|completed|failed; attempts count leased executions. No fake zero, parsed-JSON repair, paid call, automatic human review or silent reference-to-context substitution. JSON schemas are strict; inline citation existence is distinct from support. Judge text is rendered as text. Next.js allows only these bounded explicit routes and retains same-origin mutation protection.

Original run/result endpoints continue to report their original execution traces and run-time metric availability; answer assessments are independent records, not backfills. Self-judge outputs are explicitly uncalibrated model estimates, not human or benchmark labels. Default judge disabled; reviewer labels are self-declared in the local single-workspace product.
