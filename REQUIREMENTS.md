# Requirements

Priority: P0 is required for first usable release; P1 follows the core vertical slice.

| ID | Priority | Requirement | Acceptance |
|---|---|---|---|
| DOC-01 | P0 | Ingest supported text documents asynchronously | Source-linked normalized sections persist; invalid input is rejected |
| VER-01 | P0 | Publish immutable corpus/dataset versions | Editing a draft cannot change an existing run |
| DATA-01 | P0 | Curate evidence-annotated questions and JSONL interchange | Schema validation and reviewed publication gate |
| RET-01 | P0 | Lexical and dense baselines | Ranked results have provenance and deterministic tie-breaking |
| RET-02 | P1 | Hybrid fusion and reranking | Stored component ranks and explicit configuration |
| CHUNK-01 | P0 | Fixed-token and section strategies | Chunk lineage maps to canonical source sections |
| RUN-01 | P0 | Durable jobs and checkpoint recovery | Lease expiry and restart do not duplicate committed outputs |
| RUN-02 | P0 | Cancellation and bounded retries | No further questions start after cancellation is observed |
| EVAL-01 | P0 | Retrieval and answer metrics | Definitions, applicability, errors, and scoring versions persist |
| UI-01 | P0 | Run list and question inspection | Real persisted results and every required UI state |
| UI-02 | P1 | Comparisons and export | Compatibility checks, coverage counts, export manifests |
| DEMO-01 | P0 | Explicitly labeled bundled demo | Works without model credentials; never represented as measured research |

## Non-functional requirements
- Capacity and responsiveness targets in PRD.md are provisional until measured; record hardware and dataset size with benchmarks.
- Bound upload size, worker concurrency, context tokens, run question count, retries, and inference timeout via validated configuration.
- Checkpoint after every question and ingest stage; preserve completed artifacts after failure/cancellation.
- Secrets remain server-side; document storage is local by default. Provider selection determines external disclosure.
- Keyboard-operable interface, visible focus, text alternatives, chart tables, reduced motion, and tested contrast.
- Docker startup, migrations, backup/restore, lint/type checks, automated tests, and reproducible dependency lockfiles.
- No production uptime commitment. Remote hosting requires the deployment gates in DEPLOYMENT.md.
