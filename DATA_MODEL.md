# Data model

All persistent records have UUID IDs and UTC timestamps. Foreign keys enforce lineage. Published records and run manifests are immutable; review annotations are append-only and distinct from original scoring.

| Entity | Essential fields / relationships |
|---|---|
| Corpus | name, description, mutable draft revision |
| Document | corpus_id, original filename, storage key, media type, bytes, checksum, ingestion state |
| DocumentRevision | document_id, source URL/version, extraction/normalization version, content checksum |
| SourceSection | document_revision_id, ordinal, stable canonical ID, heading path, normalized text, offsets, original location |
| CorpusVersion | corpus_id, version, manifest checksum; snapshot membership of document revisions |
| IndexVariant | corpus_version_id, chunking config hash, tokenizer/model revisions, dimensions, status |
| Chunk | index_variant_id, ordinal, text, token count; section-span lineage mapping |
| Embedding | chunk_id, model revision, vector; partition/index by compatible dimension/model |
| Dataset | corpus_version_id, name, mutable draft revision |
| Question | dataset_id, text, reference answer, required facts, answerability, category, split, review status |
| Evidence | question revision, canonical section/span, required/alternative evidence group |
| DatasetVersion | dataset_id, immutable question revisions and split manifest, checksum |
| Experiment | immutable corpus/dataset version IDs and pipeline configuration |
| Run | experiment_id, manifest, fingerprint, state, counts, cancellation flag |
| QuestionResult | run_id, question_revision_id, repeat ordinal, stage state, answer, abstention, timing, error |
| RetrievedPassage | result_id, chunk_id, component ranks, fused/reranked scores, delivered offsets/order |
| Evaluation | result_id, metric ID/version, nullable value, applicability, state, rationale, judge revision |
| HumanReview | result_id, reviewer label, rubric revision, judgments, timestamp |
| ProviderCall | result_id/job_id, provider/model, tokens, latency, attempt, pricing version, estimated cost |
| Job | kind, payload reference, state, attempts, available_at, lease token/expiry, heartbeat, checkpoint |
| Export | run/comparison reference, manifest hash, artifact key, state |

## Constraints
Unique published version numbers per parent. Unique index variant fingerprints. Unique (run, question revision, repeat) results and (result, metric, scoring revision) evaluations. Snapshot memberships restrict deletion. Evidence must reference the dataset's corpus snapshot. Unanswerable cases cannot acquire positive retrieval denominators accidentally.

Store model IDs/revisions and embedding dimensions explicitly; never mix incompatible vectors. Start with exact vector search for the research baseline, adding approximate indexes only behind recorded configuration and verified recall. Lexical search uses PostgreSQL full-text search with recorded text-search configuration.

Normalized source text and source mappings are retained so span boundaries remain stable. Do not use strategy-dependent chunk IDs as dataset ground truth. Blob storage keys are generated IDs, never user-controlled paths. Indexes support job claims, run list pagination, result lookups, and source lineage. Alembic migrations own all schema changes.

## Implemented M2 schema
Migration 0002_documents implements corpora, documents, document_revisions, source_sections, corpus_versions, corpus_version_members, and ingestion jobs. Originals deduplicate by corpus_id/checksum. One sealed extraction revision is currently created per original document; parser-version reprocessing and source URL/release metadata editing are deferred. Provenance currently retains filename, original SHA-256, extracted text SHA-256, extractor version, and page/line/heading/anchor locations.

Section UUIDs derive from revision UUID and ordinal; offsets address NFC text joined by two newlines. Revision UUID derives from document UUID and extractor version. Snapshot manifests freeze revision membership and hashes. Database triggers permit sealing during construction, then reject parent updates/deletes or further child inserts/updates/deletes. Corpus draft_revision advances only for new content.

The jobs table currently references one document per unique ingestion job. Lease token/expiry guard checkpoint and evidence commits; available_at bounds retry scheduling. Future experiment jobs require a migration extending the payload model rather than overloading document_id.

## Implemented M3 schema
Migration 0003_datasets adds datasets, questions, and dataset_versions. Draft question content stores validated required facts/evidence alternatives in JSONB; dataset foreign keys fix corpus lineage. A question-evidence trigger checks embedded source UUIDs and code-point bounds against the corpus snapshot. Dataset corpus selection is immutable. Draft writes lock the dataset; question revisions reject conflicting saves.

Published questions are frozen inside the dataset-version manifest rather than duplicated into a separate question-revision table. The manifest retains logical question IDs/revisions, reviewer/time, splits, annotations, corpus hash, purpose, and evidence-policy version. Sealed dataset versions reuse the PostgreSQL immutability guard. Future run results can reference (dataset_version_id, question_id, revision), with constraints introduced in M4. A live draft question ID alone is never a run input.

## Implemented M4 lexical slice
0004_lexical_indexes adds index_variants and index_chunks. Each index variant also owns its durable build lease, attempts, scheduling, and safe failure state; this separate payload never overloads document_id in ingestion jobs. Fingerprints bind a sealed corpus version/hash, chunk configuration/version, pinned tokenizer commit/library, and lexical strategy. Completed manifests add tokenizer artifact SHA-256, chunk-content hash, and counts.

Chunks retain exact text, token count, ordinal, and JSONB canonical/chunk span mappings. PostgreSQL generates an English tsvector and GIN index. Triggers validate corpus membership and source substring equality and reject chunk mutation/appending after publication. Ready indexes are immutable. All chunks and the ready manifest commit in one fenced transaction. A failed or interrupted build therefore has no partial published chunks; an expired claim may recompute under a new lease. 0005_index_span_shape additionally rejects JSON null/noninteger offsets and unordered/overlapping chunk-local annotations without editing an already applied migration.

Immutable experiment/run manifests, saved question results, generation adapters, and per-run metrics are still M4 work. Current interactive preview responses are not run records.

## Implemented M4 dense schema
0006_dense_retrieval adds chunk_embeddings: one vector(384) per chunk, parent index ID, compatibility key, unit-norm constraint, and parent lookup index. SQL guards require matching chunk/index/model lineage and a live build lease, reject vector changes, and require all compatible vectors before dense publication. There is no approximate vector index.

The same migration adds dense_searches with immutable index/request/hash, unique (index_id, request_hash), pending/running/completed/failed state, bounded attempts, available_at, ownership token/expiry, safe errors, and nullable JSONB result. Completed results cannot be changed; publication requires a live running lease. This queue stores interactive query previews, not benchmark question results or generation runs.
