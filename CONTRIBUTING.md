# Contributing

Try the [quickstart](docs/QUICKSTART.md) before changing code. Original project contributions use [Apache-2.0](LICENSE); dependencies, fonts, source quotations and models retain their own terms in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). Do not submit material you cannot license or private research records. There is no separate CLA in this repository.

Read AGENTS.md, the relevant specification, TASKS.md, and CODEX_HANDOFF.md before edits. Work in small milestones and preserve user-authored changes.

Keep retrieval/evaluation logic in the shared Python core. API handlers validate and orchestrate; frontend renders persisted data. Use typed schemas, explicit states, parameterized SQL/ORM expressions, and migrations. Published snapshots and run manifests are immutable.

Update documentation when API, metric definitions, configuration, or operations change. Record consequential trade-offs in DECISIONS.md. Every metric change has a scoring revision and independent acceptance fixture.

Before proposing a change, run relevant checks from TESTING.md once infrastructure exists. Husky runs lightweight staged lint checks; CI is authoritative and also runs typing and tests. Hooks must not download models, invoke paid APIs, or run experiments.

Describe the concrete behavior change, validation performed, and material limitations in pull requests. Never commit secrets, database volumes, uploaded documents, downloaded model weights, or unreviewed private datasets. Follow source licenses for any redistributed corpus.

## Where changes belong

| Change | Starting points | Required evidence |
|---|---|---|
| Retriever / reranking strategy | `packages/rag_core/src/rag_core/indexes.py`, `hybrid.py`, `reranking.py`, `runs.py`, `run_worker.py` | Explicit bounded configuration, frozen identity, deterministic scoring/lineage fixtures, checkpoint/failure tests. Update typed request enums and frontend controls together. |
| Metric / evaluator | `retrieval_evaluation.py`, `answer_evaluation.py`, `comparison_analysis.py` in the shared core | Versioned policy and independently computed fixtures; coverage/error/unavailable counts. Never backfill immutable historical scores. |
| API or storage | `services/api`, shared typed models, `migrations/versions` | Validation/error contracts, a migration when schema changes, isolated `rag_test` integration checks. |
| Frontend | `apps/web/src`, `DESIGN_SYSTEM.md`, `tests/e2e` | Accessible loading/error/unavailable states, keyboard/mobile/light/dark/reduced-motion checks; real or explicitly synthetic data. |
| Dataset / research report | `RESEARCH_PROTOCOL.md`, `DATASET_CARD.md`, `research/` | Source/license provenance, review_source and author/reviewer disclosure, frozen grouped splits and honest limitations. |

Do not run destructive integration tests against `rag`, use real credentials in fixtures, or rebuild a frozen campaign's API/worker just to test a UI change. Current validation commands and database safety rules are in [TESTING.md](TESTING.md). Open a small issue or draft PR for a proposed behavioral change; describe a concrete input and the expected result, with redacted minimal reproduction data.
