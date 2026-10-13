# Implementation plan

Each milestone leaves a reviewable artifact and updates TASKS.md and CODEX_HANDOFF.md. No milestone is complete solely because files were created.

1. **Foundation:** initialize repository, Python/JS workspaces, locked dependencies, FastAPI and Next.js shells, Compose, migrations, health checks, lint/type checking, CI, and Husky. Gate: repeatable boot and required checks pass.
2. **Document vertical slice:** upload → durable ingestion job → canonical sections → immutable corpus publication. Gate: real text fixture survives restart and is inspectable in UI; invalid/scanned content reports errors.
3. **Dataset curation:** question/evidence editor, JSONL validation, publication, split metadata. Gate: round trip and version isolation verified.
4. **Baseline experiment:** fixed/section chunking, sentence-transformer embeddings, exact pgvector and lexical retrieval, model adapter, durable runs, retrieval metrics, answer inspection. Gate: persisted real run from frozen inputs with complete manifest.
5. **Research variants:** fusion, reranking, answer judge, human review, uncertainty summaries. Gate: controlled comparisons and independently checked metrics.
6. **Dashboard completion:** comparisons, filters, failure explorer, exports, explicit demo, rendered responsive/accessibility review. Gate: end-to-end journey and UI contract verified.
7. **Benchmark and handoff:** select/acquire frozen PostgreSQL docs, curate reviewed questions, freeze split, run protocol, publish report and operations instructions. Gate: research results and limitations backed by actual artifacts.

Start with a tiny clearly labeled integration fixture; expand only after the pipeline works. Model choices and dependency versions are selected and pinned during implementation after checking hardware and supported APIs. Keep public deployment out of the first milestone.
