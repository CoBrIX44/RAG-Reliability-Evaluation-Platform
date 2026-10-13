# Security model

Initial deployment is a single trusted local workspace bound to loopback. It is not a public multi-user security boundary. A configurable external provider can receive selected document context/questions; show that disclosure in experiment configuration.

## Document boundary
Validate extension and content type, bound bytes and extraction resources, generate storage paths, and reject traversal. Sanitize HTML/Markdown in the browser and disable executable content. Preserve source text safely. Document instructions are data, never authority to run commands or access tools. PDFs that require OCR are unsupported initially.

## Secrets and requests
Secrets live server-side in environment/secret storage and are redacted in logs and export manifests. Parameterize database access. Restrict CORS and avoid arbitrary provider URLs unless an explicit validated adapter supports them. User-supplied document URLs are deferred; initial ingestion is uploads plus controlled corpus acquisition.

## Availability and integrity
Bound model timeout, retry attempts, upload size, worker concurrency, and token budget. Enforce ownership tokens on job commits and unique result keys. Published inputs are immutable. Validation failures must not partially publish a dataset.

## Data retention
Keep original documents, normalized sections, answers, and reviewer notes within the local workspace. Document deletion/export semantics must account for published snapshots and run lineage. Do not commit uploaded/private documents or keys. Full retention settings can follow the core pipeline; do not promise automatic deletion before implemented.

## Remote deployment
Apply DEPLOYMENT.md gates before public exposure. Security checks supplement, rather than replace, the local trust assumptions. Report observed security defects without inventing guarantees.
