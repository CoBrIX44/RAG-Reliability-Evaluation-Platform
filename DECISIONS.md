# Decision log

Design approved by the project owner through incremental checkpoints on 2026-10-12. Entries distinguish approved decisions from implementation proposals.

| ID | Status | Decision | Alternatives considered | Rationale / trade-off |
|---|---|---|---|---|
| D01 | Approved | Full platform for documents, datasets, experiments, comparisons | Standalone notebook/demo | Research plus backend/database/frontend engineering |
| D02 | Approved | PostgreSQL documentation first domain | ML papers, other technical documents | Concrete technical domain; supports curated factual questions |
| D03 | Approved | Local-first, individual/small-team scope | Public multi-tenant SaaS | Manageable operations and privacy boundary |
| D04 | Approved | Modular app and separate worker | Microservices; notebooks first | Shared pipeline, fewer operational components, independent heavy work |
| D05 | Approved | PostgreSQL/pgvector and PostgreSQL-backed jobs | Separate vector database and broker | One persistence system initially; requires careful lease/recovery design |
| D06 | Approved | Canonical source evidence and immutable snapshots | Chunk-ID ground truth; mutable run inputs | Comparable chunk strategies and traceable experiments |
| D07 | Approved | Controlled baselines and paired comparisons | Change all factors simultaneously | Attribute effects; retain uncertainty and null findings |
| D08 | Approved | 150 reviewed questions initially, growth to 1,000 | Large generated-only dataset | Reviewable starting benchmark; publication depends on human review |
| D09 | Approved | Distinct metrics and human spot-checks | Single opaque score; judge as sole ground truth | Explain failure types and evaluator limitations |
| D10 | Approved | Five research dashboard areas and evidence explorer | Generic KPI overview | Supports actual workflow and diagnosis |
| D11 | Approved | Text PDF/HTML/Markdown/plain text, JSONL datasets | OCR and arbitrary URL ingestion initially | Bound extraction scope and security complexity |
| D12 | Approved | User-requested UI skills and product-specific visual contract | Adopt catalogue marketing template | Evidence-focused, accessible interface; no invented metrics |
| D13 | Approved | Complete six-layer documentation plus research/dataset/security docs | Ad hoc coding | Durable specification and handoff |
| D14 | Proposed detail | Exact vector search baseline; PostgreSQL lexical rank plus RRF | Approximate-only baseline; claim BM25 without implementation | Separate approximate-search effects and keep naming accurate |
| D15 | Proposed detail | Grouped 70/30 split, 80/20 answerability, three stochastic repeats | Ungrouped/random-only split; single generation | Reduce leakage and expose variation; verify feasible curation/cost |
| D16 | Proposed detail | Light mode first; dark mode after verification | Ship untested themes together | Concentrate initial UI validation |
| D17 | Implemented | Python 3.12.13, Node 24.14.0, Next.js 16.4.0, React 19.3.0; uv/npm lockfiles | Existing Python 3.14 project runtime | Conservative Python ML runtime, compatible available Node; model dependencies remain M4 |
| D18 | Implemented | Direct node entrypoints in npm scripts | Windows package command shims | Shims failed on workspace ampersand; direct entrypoints pass native checks |
| D19 | Implemented | ESLint 10, TypeScript/React Hooks rules, browser axe checks | eslint-config-next dependency chain | Removed advisory-affected development glob chain; zero npm audit findings |
| D20 | Implemented | SWR status polling with validated server-side proxy | Manual effect polling | Revalidation, retained stale data, explicit recovery, server-only upstream settings |
| D21 | Superseded by M2 | Foundation heartbeat established the service boundary | Starting with an unverified pipeline | Worker now includes durable document ingestion |

| D22 | Implemented | Sealed extraction revisions and corpus manifests protected by PostgreSQL triggers | Application-only immutability | Prevent appending or changing published evidence through another SQL client |
| D23 | Implemented | Isolated parser subprocess, timeout, size/page/text limits; Linux 1 GiB address-space cap | Parse untrusted files inside API process | Keep heavy work out of API; native Windows OS memory cap remains deferred |
| D24 | Implemented | Integer offset pagination for append-only ingestion resources | Keyset complexity before editable run resources | Stable append ordering; keyset pagination remains planned for later resources |
| D25 | Implemented | Preserve artifacts after ambiguous database commit/cancellation | Delete every file on request failure | Avoid corrupting successfully committed documents; orphan collection deferred |

| D26 | Implemented | Freeze question content/reviews inside dataset-version manifests | Mutable question IDs as run inputs | Preserve version isolation; M4 results reference version plus logical question ID/revision |
| D27 | Implemented | Reject shared split groups and gold source sections across development/test | Allow automatic random assignment | Reduce known evidence leakage; semantic/paraphrase review remains manual |
| D28 | Implemented | Candidate labels by default; explicit named review, editor invalidation after content changes | Implicit review on import/save | Generated/imported questions never count as reviewed automatically |

## Understanding summary
Build an evidence-grounded full-stack research platform. Serve individual researchers/small teams. Focus the first controlled benchmark on PostgreSQL docs. Keep the specified stack, local Docker operations, durable jobs, versioned inputs, and transparent scoring. Exclude enterprise billing, OCR, public multi-tenancy, and high availability from the first release.

## Assumptions
10,000 pages/1,000 questions initial capacity target; ordinary dashboard p95 <2s on recorded hardware; local storage; explicitly configured inference; owner-maintained repository. These are targets, not verified performance or completed capabilities.

## Remaining implementation choices
Numbered corpus release, supported runtime/dependency pins, model/provider choices, cost budget, and reference hardware. Resolve and record these before measured research execution.

## D29 - Deliver lexical inspection before dense inference
M4 starts with a usable published-corpus -> leased index build -> lexical search -> source/context inspection slice. Index variants hold their own durable build payload instead of changing ingestion job document lineage. Atomic publication avoids partial chunk cleanup/retry duplication. The worker alternates queue priority to prevent starvation. Saved experiments and dense embedding storage remain the next M4 steps.

## D30 - Pinned tokenizer and exact source slicing
Use the public all-MiniLM-L6-v2 tokenizer at commit 1110a243fdf4706b3f48f1d95db1a4f5529b4d41, tokenizers 0.23.3, huggingface-hub 2.2.0. Record artifact SHA-256 and library identity in the index manifest. Chunking disables repository truncation/padding/special tokens and slices canonical text by original code-point offsets, rather than decoding token IDs. Download tokenizer.json only; lexical work does not need model weights. Future answer models require their own prompt/context budgeting and compatible embedding declarations.

## D31 - Exact delivered-context accounting
Pack ranked passages with a recorded separator, deduplicate repeated chunk IDs, and retokenize the combined text rather than assume token counts add. Retain a fitting source prefix of the first oversized passage, clip its canonical spans, then stop; record all truncations and omissions. The current budget applies to document text only. Recall unions canonical intervals; a complete accepted alternative requires all its supporting spans. Precision counts passages containing at least one full accepted span. Missing annotations and unanswerable denominators stay unavailable/not applicable.

Primary implementation references: https://huggingface.co/docs/tokenizers/python/latest/api/reference.html and https://www.postgresql.org/docs/17/textsearch-controls.html.

## M4 local dense baseline - 2026-10-13
Use sentence-transformers/all-MiniLM-L6-v2 at 1110a243fdf4706b3f48f1d95db1a4f5529b4d41, 384 dimensions, normalized float32, torch CPU, and exact pgvector cosine retrieval. Preserve tokenizer 0.23.3; pin sentence-transformers 6.1.0, transformers 5.19.0, torch 2.14.1+cpu from the explicit official CPU wheel index, and compatible huggingface-hub 1.33.0. Pin artifact hashes and package contract per index/query. CPU inference avoids requiring a GPU; hardware/runtime are recorded rather than treated as portable latency results.

The model accepts 256 tokens including two special tokens, so chunks/queries fit 254 content tokens. Reject overflow and any model/artifact mismatch. Download only public pinned JSON/vocabulary/safetensors artifacts with no Hub token or remote code. Heavy inference runs in a subprocess under the durable worker, with a wall timeout and Docker CPU/memory limits. Exact search has no ANN approximation. Query previews have their own idempotent leased queue; completed preview reuse is inspection convenience, not a repeat experiment or latency sample.

## D32 - Approved free local answer baseline
The user chose local CPU generation with no paid API. Pin Qwen/Qwen2.5-0.5B-Instruct at 7ae557604adf67be50417f59c2c2f167def9a775, Apache-2.0 model card, fixed safetensors/config/tokenizer hashes, float32 CPU and greedy decoding. Reuse locked transformers 5.19.0 / torch 2.14.1+cpu / tokenizers 0.23.3. Enable only through LOCAL_GENERATION_ENABLED; generation/model-selection placeholders do not invoke external providers. This makes a small local baseline usable without claiming answer quality. Official model reference: https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct/tree/7ae557604adf67be50417f59c2c2f167def9a775.

## D33 - Frozen split, fencing, and retained attempts
Freeze published question content/revisions, selected split, index/corpus/dataset lineage, prompt/model/scoring contracts, code hashes, dependency locks, declared source revision and runtime. Strict worker identity prevents silent resume under different code/settings. Global submission keys serialize in PostgreSQL; same key/experiment returns the old run and conflicts across experiments receive 409. Each successful or failed observation publishes once under live uncancelled ownership. Restart resumes uncommitted observations; interrupted checkpoints and committed results remain available. Inference may repeat after a crash and is not promised exactly once.

## D34 - Answer-tokenizer budgeting and explicit unavailable scores
Retrieval chunks use MiniLM token counts; answer context uses the pinned Qwen tokenizer. Recount document context including separators, retain clipped canonical spans, and reject full chat prompts over 2048 input tokens. Use [P1] syntactic references and exact INSUFFICIENT_EVIDENCE as recorded behaviors, not correctness/faithfulness/citation-support judgments. Even semantic refusals without the exact marker have abstained=false. Correctness, faithfulness, citation support, abstention quality, and hardware/provider cost stay unavailable until applicable evaluators/accounting exist.

## D35 - Approved development review is separate from benchmark labels
The project owner explicitly reviewed the live transaction question/reference/evidence and authorized reviewer name Project owner. Record that review and publish its existing development_fixture split/version. This one-question authored smoke fixture is not a curated PostgreSQL benchmark. Synthetic reviews/answers in automated tests remain labeled software fixtures.

## D36 - Keep dependency installs out of source rebuilds
Install locked third-party Python dependencies in a separate Docker layer using uv's workspace exclusion, then install the three editable project packages. Clear disposable uv download caches from layers and give the non-root user write access only to /app/data. This avoids redownloading/copying the full CPU runtime for every source edit while preserving source hashes and the lockfile. Reference: https://docs.astral.sh/uv/guides/integration/docker/#intermediate-layers-in-workspaces.
