# Contributing

Read AGENTS.md, the relevant specification, TASKS.md, and CODEX_HANDOFF.md before edits. Work in small milestones and preserve user-authored changes.

Keep retrieval/evaluation logic in the shared Python core. API handlers validate and orchestrate; frontend renders persisted data. Use typed schemas, explicit states, parameterized SQL/ORM expressions, and migrations. Published snapshots and run manifests are immutable.

Update documentation when API, metric definitions, configuration, or operations change. Record consequential trade-offs in DECISIONS.md. Every metric change has a scoring revision and independent acceptance fixture.

Before proposing a change, run relevant checks from TESTING.md once infrastructure exists. Husky runs lightweight staged lint checks; CI is authoritative and also runs typing and tests. Hooks must not download models, invoke paid APIs, or run experiments.

Describe the concrete behavior change, validation performed, and material limitations in pull requests. Never commit secrets, database volumes, uploaded documents, downloaded model weights, or unreviewed private datasets. Follow source licenses for any redistributed corpus.
