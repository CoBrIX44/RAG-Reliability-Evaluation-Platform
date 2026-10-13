# RAG Reliability & Evaluation Platform

Status: approved design; M1-M4 implemented and locally verified, including ingestion, reviewed datasets, lexical/dense retrieval, saved local CPU runs and question traces. M5-M7 remain; no research benchmark results exist. See TASKS.md.

## Problem and purpose
Researchers need to distinguish retrieval failures from generation failures and compare RAG methods using the same documents, questions, and scoring protocol. This product provides document ingestion, curated datasets, reproducible experiment execution, comparison dashboards, and evidence-level failure analysis.

## Users
Individual AI engineers, students, and small research teams. The first deployment is a single trusted local workspace, not a public multi-tenant service.

## Research question
Which retrieval strategies most improve factual accuracy on a frozen collection of PostgreSQL technical documentation, under a fixed generation model and context budget?

## Approved scope
- Text-based PDF, HTML, Markdown, and plain-text uploads.
- Versioned corpora and datasets; JSONL dataset import/export.
- Lexical baseline, dense retrieval, hybrid retrieval, and hybrid with reranking.
- Fixed-token and document-section chunking.
- Precision/recall, answer correctness, faithfulness, citation support, abstention, latency, and cost.
- Background experiments, cancellation, recovery, comparison, and per-question inspection.
- Next.js, FastAPI, PostgreSQL/pgvector, sentence-transformers, Docker Compose.

## Success criteria
An operator can ingest documents, publish an evidence-annotated dataset, execute comparable configurations, inspect failures, and export the run manifest and results. Runs retain immutable inputs. A restarted worker can recover without duplicating published results. Demo data is explicitly identified, and measured outcomes are never fabricated.

Research success is a defensible comparison, including negative or inconclusive findings; improvement over the baseline is not guaranteed.

## Assumptions and boundaries
Initial capacity target: 10,000 document pages, 1,000 questions per dataset, and a small number of concurrent local users. Ordinary dashboard/API interactions target a p95 below two seconds on a documented reference machine, excluding uploads, inference, and experiments. No availability SLA; recovery matters more than always-on hosting. Local storage and explicitly configured external model providers. Maintained by the project owner with documented agent handoffs.

## Non-goals
OCR, enterprise billing, public multi-tenancy, distributed microservices, arbitrary autonomous tools, and production high-availability infrastructure in the first release.

## Risks
Incomplete relevance annotations, evaluator bias, provider nondeterminism, document-version drift, embedding memory requirements, and experimental cost. See RESEARCH_PROTOCOL.md and SECURITY.md for controls.
