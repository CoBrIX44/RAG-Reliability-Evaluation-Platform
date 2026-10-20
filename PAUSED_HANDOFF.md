# Historical pause records — M7 now delivered

**Current status2026-10-20: completed_exploratory.** The final receipt and manifest-bound isolated restore pass. These pause/resume commands below are historical; do not relaunch the completed campaign. Read CODEX_HANDOFF.md and research/postgresql-18.0/BENCHMARK_REPORT.md for final status. Answer quality remains unvalidated.

# Pause record — 2026-10-19 (historical)

**Resumed by the owner on2026-10-20.** Existing worker is healthy; the owner-terminal controller holds its OS lock. Do not launch a duplicate controller. See latest CODEX_HANDOFF.md for actual counts. The pause details below are historical.

The owner requested another pause. Verified controller processes36160/28164 stopped and worker container stopped gracefully. Post-stop API confirms **840/840 development** and **531/1,080 held-out successes, zero failures**. Fixed lexical/dense/hybrid are completed135/135 each; fixed hybrid+reranking is126/135 (stored running state), and four section configurations remain queued. API/db/web remain running; results and existing volumes are preserved. No cancellation, resubmission, image rebuild, Git commit/push, or fresh full backup was performed.

Private receipt: data/research/postgresql-18.0/completion/pause-receipt-20261019.json. Native controller-process.json is historical stopped-launch metadata until resumed. The saved controller state can lag the final API counts; refresh it from live runs on resume. The resume commands below still apply. Do not start worker/controller until the owner asks to resume.

## Earlier pause and resumption (historical)

**Resumed at owner request on 2026-10-19.** The pause below is historical. Existing worker restarted and native controller relaunched; consult the latest CODEX_HANDOFF.md and private completion/controller-process.json for current process metadata. Frozen API/worker execution identities match the locked campaign. Do not start another controller while this one is active.

Work is saved locally. M7 is paused, not complete. Native controller processes 34512 and 11684 were verified by command line and stopped; the existing worker container was stopped gracefully using `docker compose stop --timeout 30 worker`. API, database and web remain running. No run was cancelled or resubmitted.

Verified from the API after stopping the worker:

- Development: 840/840 successful.
- Held-out: 340/1,080 successful, zero failed.
- Fixed lexical and fixed dense: 135/135 each, completed.
- Fixed hybrid: 70/135; stored state remains running until lease recovery.
- Five other held-out configurations remain queued.

Completed results are persisted in the PostgreSQL named volume; originals, model artifacts and exports remain in their existing volumes. Source changes remain on disk. This pause did not create a Git commit or push.

An additional database-export command was rejected by automatic approval review with “blocked by policy”; no fresh database dump or verified backup was created by this pause. Earlier verified backups remain historical. Preserve all existing Docker volumes.

## Resume tomorrow

Start Docker Desktop and wait until its engine is ready. From the repository root:

```powershell
docker compose start db api web worker
uv run python -X utf8 -u scripts/complete_m7.py --watch
```

The controller reads the existing private completion/state.json and resumes existing run IDs. Its OS lock prevents concurrent controllers. Historical controller-process.json still records the old stopped launcher; verify actual processes and update launch metadata when resuming.

Use the existing images: do not rebuild API/worker/migrate or use `docker compose up --build` during this frozen campaign. Do not reset volumes, cancel active records or submit replacement experiments. The worker reclaims interrupted work under its durable leases; an unfinished observation may need to rerun. Completed observations remain immutable.

Remaining: finish held-out execution, paired comparisons, evidence exports/report, final private backup and isolated restore, then the exploratory delivery receipt. Answer quality remains unvalidated under the owner-approved scope.
