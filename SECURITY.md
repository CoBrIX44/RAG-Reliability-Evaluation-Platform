# Security model

## Reporting a vulnerability

Support targets the current default branch. If the repository's Security tab offers private vulnerability reporting, use that channel. Otherwise open a minimal public issue requesting a private reporting contact **without secrets, exploit payloads or private documents**; agree on a private channel before sharing details. No response-time SLA or dedicated security email is currently established. Ordinary non-sensitive bugs can use public issues with redacted reproductions.

Initial deployment is a single trusted local workspace bound to loopback. It is not a public multi-user security boundary. Current model adapters run locally; external provider placeholders do not implement a remote adapter. Any future external provider must disclose when selected document context/questions leave the workspace. Default development database credentials are public examples, not production secrets.

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
