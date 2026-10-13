# API specification

Design contract. Prefix /api/v1. JSON responses, UUID resource IDs, UTC ISO-8601 timestamps. Multipart for files; JSONL for dataset interchange. Generated OpenAPI must agree with implemented endpoints.

Implemented: health, workspace, capabilities, corpora, document ingestion/status/sections/retry, corpus versions, ingestion job status, datasets/questions, dataset publication, JSONL import/export, and published source lookup. Lexical index build/status/retry/search endpoints are also implemented; experiment/comparison/run-export endpoints remain planned. /workspace returns stage datasets, actual database/schema/worker status, and provider-configuration booleans; no secrets. Readiness returns 503 for database unavailability, migration mismatch, or missing vector extension. Liveness is independent of PostgreSQL. /capabilities lists PDF/HTML/Markdown/text support; the lexical strategy is available and run-metric lists remain empty.

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
| GET | /runs | Filtered run list |
| GET | /runs/{id} | Manifest, progress, summary, compatibility fingerprint |
| POST | /runs/{id}/cancel | Request cooperative cancellation |
| GET | /runs/{id}/results | Paginated question summaries |
| GET | /runs/{id}/results/{question_id} | Full evidence/answer/evaluation/error trace |
| POST | /comparisons | Compare selected runs with explicit compatibility report |
| POST | /runs/{id}/exports | Queue artifact export; 202 |
| GET | /jobs/{id} | Job progress and sanitized error |
| GET | /exports/{id} | Export status and local download link |
| GET | /capabilities | Configured models, supported metrics and strategies; no secrets |

## Contracts
Experiment: corpus_version_id, dataset_version_id, retrieval configuration, chunking/index configuration, generation configuration, evaluator configuration, context budget, repeats, split, seed. Reject unsupported combinations and mismatched dataset/corpus lineage before queueing.

Question: text, answerable, reference_answer, required_facts[], evidence annotations[], topic, difficulty, split, review_status. Unanswerable questions have no required positive evidence and use an abstention rubric.

Run response: state, total/completed/failed/cancelled counts, timestamps, manifest_hash, metric summaries with applicable_count/scored_count/error_count, cost with pricing provenance, stage latency summaries.

## Validation and errors
400 invalid operation; 404 absent resource; 409 publication/state/version conflict; 413 oversized upload; 415 unsupported media; 422 schema/configuration failure; 503 unavailable dependency. Error envelope: code, message, field_errors, request_id, retryable. Never include credentials or stack traces.

Implemented ingestion pagination uses an integer offset cursor, append-only ordering by timestamp/ID (versions by version number, sections by ordinal), default 100/max 100; source sections default 20. Response: items and next_cursor (string or null). Offset pagination is an explicit M2 choice; future editable run resources will use keyset cursors.

Upload returns the document with job_id, state, checksum, byte_count, revision_id, section_count, and safe errors. SHA-256 content deduplicates within a corpus. Publishing an unchanged draft returns its existing version; incomplete/empty drafts return 409. A published manifest includes document/revision IDs, original and normalized-text checksums, extractor version, and source counts. Section offsets address NFC text joined by two newlines; source locations retain original PDF pages, Markdown/text line ranges, or HTML anchors and heading paths. Database triggers reject mutation or appending children to sealed evidence.

Planned run submission accepts Idempotency-Key: same key/body returns original run, different body returns 409. Retry must not silently create another experiment run. Comparisons will reject incompatible runs by default; exploratory=true returns differences and restricted paired summaries.

## Implemented dataset contract
Dataset creation: name, description (optional), corpus_version_id, purpose (research or development_fixture). The corpus must be sealed; its lineage cannot change. Questions use text, answerable, reference_answer, required_facts[], evidence_groups[], topic, difficulty (easy/medium/hard), split (unassigned/development/test), split_group, review_status (candidate/reviewed), and reviewer. Candidate is the default. Explicit reviewed status requires a named reviewer; the server records reviewed_at. Ordinary clients submit full question content; PATCH additionally requires expected_revision and returns the incremented revision.

Evidence group: fact_index and alternatives[]. Each alternative contains spans[] that must all support the fact; alternatives are interchangeable sufficient evidence. Each span contains section_id, start_offset, and end_offset. Offsets are local to the canonical section and count Unicode code points, start-inclusive/end-exclusive. UUID membership, nonempty bounds, and positive evidence rules are validated; SQL triggers also enforce source membership/bounds. A question is limited to 200 total evidence spans. Evidence contains no retrieval chunk identifiers.

Publication requires nonempty questions, a reference answer or expected abstention, named human review, topic, split, and split_group. Answerable questions need a nonempty fact list and evidence for every fact. Unanswerable questions cannot have positive facts/evidence. One split_group and one gold source section cannot appear in both development and test. Exact normalized-text duplicates are rejected in a draft; paraphrase/topic leakage still requires owner review. Unchanged publication returns the existing version. The sealed manifest freezes question IDs/revisions/content, reviewer timestamps, corpus version/hash, purpose, and evidence policy. Later draft edits cannot change exported versions.

POST /datasets/{id}/import accepts multipart file with UTF-8 JSONL, one QuestionInput per nonblank line, up to MAX_JSONL_BYTES (10 MiB) and the configured question limit. All lines and evidence validate before any insertion. Errors contain physical line numbers in field_errors; nothing commits on error. Import asserts supplied reviewer metadata; it never promotes candidates automatically. Export emits the same interchange content, excluding server-owned IDs/revisions/timestamps, so it can import into a new dataset tied to the same corpus. Downloads stream through the web proxy. Dataset resource lists use the same offset pagination contract as ingestion.

## Implemented lexical inspection contract
GET/POST /indexes lists or queues durable lexical index builds. POST body: corpus_version_id and chunking {strategy: fixed|section, max_tokens: 1..4096, overlap_tokens: 0..1024 and below max_tokens}. Only sealed corpora qualify. Identical corpus/configuration submissions return the same index. GET /indexes/{id} returns pending/running/ready/failed, attempts, config, chunk_count, fingerprint, nullable manifest, and safe errors. POST /indexes/{id}/retry accepts only failed builds and resets the bounded attempt budget.

POST /indexes/{id}/search accepts query (1..4000 trimmed characters), top_k (1..50, default 5), and context_tokens (0..8192, default 1024). A ready index and matching cached tokenizer are required. Response includes ranked chunks, canonical source spans, returned_count, and packed context with exact token count and truncated/omitted chunk IDs. A span stores section_id plus section-local start_offset/end_offset and chunk-local text_start/text_end, all Unicode code points. No context text is reconstructed from decoded tokens.

Search uses plainto_tsquery with English configuration, ts_rank_cd normalization 0, and stable ordinal/ID ties. This is PostgreSQL full-text ranking, not BM25. The preview is bounded interactive inspection, not durable experiment execution. It does not generate or score answers, persist question results, or assert reviewer labels. Index-list pagination uses the existing offset cursor contract. The workspace stage remains datasets; lexical_indexing is a capability and postgresql_lexical is now a supported retrieval strategy.

## Implemented dense inspection contract
POST /indexes also accepts retrieval: lexical|dense (default lexical). Dense chunks are limited to 254 content tokens; the model is the pinned MiniLM CPU baseline, not selected through arbitrary environment model IDs. Dense configurations include the embedding compatibility contract; incompatible configurations receive distinct fingerprints.

POST /indexes/{id}/dense-searches accepts the same query/top_k/context_tokens body as lexical search and returns 202 with a durable preview. It requires a ready dense index and a query fitting 254 content tokens. The API performs no model inference. GET /dense-searches/{id} polls pending/running/completed/failed, attempts, request, nullable result, and safe errors. POST /dense-searches/{id}/retry resets only failed previews. Identical requests for an index reuse the original preview, including completed results. Failed previews must be explicitly retried.

Dense results retain ranked source-linked chunks and packed context, strategy pgvector-exact-cosine-v1, and embedding contract/artifact/runtime metadata. Scores are cosine similarities, not answer correctness. Queries use the exact same contract/artifacts as the built index; mismatches fail closed. The synchronous /indexes/{id}/search endpoint accepts lexical indexes only (409 dense_preview_required for dense). Supported capabilities add dense_indexing and retrieval strategy pgvector_exact_dense; workspace stage remains datasets until saved runs exist.
