# Development execution status

Observed at 2026-10-17T10:17:51.394122+00:00. This snapshot becomes stale as the worker advances.

| Cell | State | Completed/planned | Failed |
|---|---|---:|---:|
| section/dense | completed | 105/105 | 0 |
| fixed/lexical | completed | 105/105 | 0 |
| fixed/dense | running | 25/105 | 0 |
| fixed/hybrid | queued | 0/105 | 0 |
| fixed/hybrid_rerank | queued | 0/105 | 0 |
| section/lexical | queued | 0/105 | 0 |
| section/hybrid | queued | 0/105 | 0 |
| section/hybrid_rerank | queued | 0/105 | 0 |

Docker recovered on2026-10-17; all four services are healthy and API/worker retain the frozen source identity. Existing fixed/dense resumed; no replacement development runs were submitted. Native completion controller restarted at2026-10-17T10:14:17.3786983Z (launcher PID30516 at launch). Historical PIDs may be reused: check command lines.

See DEVELOPMENT_DIAGNOSTICS.md for actual completed-run coverage and30 unreviewed trace diagnostics. No generated-answer judgment, held-out observation or research winner is claimed.

Controller phase: waiting_for_development. It requires all840 development observations before freezing unchanged controls and submitting1,080 held-out observations, followed by actual exploratory reports, checked exports and post-experiment backup/restore. See DEVELOPMENT_PLAN.md for recovery. Keep Docker and the machine running; no automatic recovery across a machine reboot is configured.

Latest live state: private data/research/postgresql-18.0/completion/state.json. Inspect the Runs screen or use uv run python -m scripts.prepare_development_runs status. Do not rebuild API/worker from changed Python sources mid-campaign. Missing answer quality/cost remain unavailable; M7 is incomplete.
