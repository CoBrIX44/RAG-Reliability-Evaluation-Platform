# Quickstart

Run the commands from a cloned repository root. Windows examples use PowerShell and `npm.cmd`; on Linux/macOS use `npm` and the equivalent copy/environment commands. See [README](../README.md), [deployment](../DEPLOYMENT.md), and [security model](../SECURITY.md) for the complete environment.

## Try the interface without a database or models

Requires Node 24 and npm. No Python, Docker, account, API key, corpus download, or inference is needed for this path.

```powershell
npm.cmd ci
npm.cmd run dev
```

Open [the landing page](http://127.0.0.1:3000/) and choose **Explore the demo**, or go directly to [the read-only demo](http://127.0.0.1:3000/demo). Switch the demonstration scenario and inspect Gold source. Its values are synthetic software fixtures, not measured research results. The demo makes no API calls; the actual workspace needs the backend and will report unavailable services until they run. The initial npm install requires network access. Ctrl+C stops the preview.

If port 3000 is already occupied, use `npm.cmd run dev --workspace @rag/web -- --port 3003` and open that port instead.

## Start a new full local workspace

Requires Docker Desktop/Engine with Compose. Native development additionally needs uv and Python 3.12; Docker builds provision Python themselves. These are instructions for a **new installation**. Preserve an existing `.env`, database volumes, and frozen images rather than overwriting or rebuilding a campaign.

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
docker compose up --build --wait --wait-timeout 180
```

Open [the workspace](http://localhost:3000/experiments) and **Settings**. API, PostgreSQL, and worker should be ready. Answer generation and the optional self-judge are disabled by default. The example database password is only for the loopback-bound development setup; this is not an authenticated public service. If your machine already has services on ports 3000, 8000, or 5432, choose different `WEB_PORT`, `API_PORT`, and `POSTGRES_PORT` values before startup and adjust browser/native URLs accordingly.

To stop this installation while retaining data, run `docker compose stop`. Resume existing containers using `docker compose start`. Do not use `down -v`, volume pruning, or the private M7 operator as a beginner reset command.

## A small real experiment

Use the bundled [synthetic transaction document](../examples/transactions.md) as your own **development fixture**, not a research benchmark.

1. In **Documents**, create a corpus, upload `examples/transactions.md`, wait for extraction, inspect the section, and publish the corpus.
2. In **Datasets**, create a dataset with purpose **Development fixture**, selecting that published corpus.
3. Add the question: **According to this fixture, what does a transaction group?** Reference answer / required fact: **A transaction groups operations into a single unit.** Mark it answerable, set Topic to `transactions` and Difficulty to `Easy`, and assign the Development split and Split group `transactions-example`.
4. Use the actual extracted source section to annotate that sentence as gold evidence. Do not fabricate document IDs, section IDs, or offsets. Read the source and reference yourself, record your own explicit review, then publish. Software validation does not count as a human review.
5. In **Experiments → Retrieval preview**, build a lexical, fixed-token index for the same corpus version. The pinned tokenizer downloads on first use; this is a tokenizer download, not answer-model inference. Search **What does a transaction group?** and inspect the original evidence.
6. To execute saved answers, enable `LOCAL_GENERATION_ENABLED=true` in the server-side `.env` for this new installation. Keep `LOCAL_JUDGE_ENABLED=false` for the first run. Record a truthful `SOURCE_REVISION` (the checked-out Git commit, plus a dirty suffix if modified). Recreate that new installation with `docker compose up -d --force-recreate api worker` so API and worker receive the same environment. Never use that recreation command over someone else's unfinished frozen runs.
7. Create an experiment with your published development dataset, ready lexical index, development split, and one repeat. Keep the remaining bounded defaults. Start it, wait for completion, then inspect the saved answer, retrieved/delivered passages, source evidence, timings, and unavailable answer assessments. A failed or unsupported answer is useful diagnostic evidence; this small local model is not a correctness oracle.

Dense search, hybrid fusion and reranking can be explored after that first saved run. They add embedding/reranker model downloads. Run names, fixtures, and source reviews must not imply published research or calibrated model quality.

## Resources and downloads

The demo has no model downloads. Lexical indexing downloads tokenizer files. Dense retrieval, generation, and reranking download their pinned public models on first use, then use local caches. No paid model provider is needed. Network access, model storage, and CPU time are required; a first run can be slower while files are acquired and validated.

The configured worker is limited to four CPUs / 4 GiB; the database, API, frontend, Docker and build processes need additional memory. This is a worker limit, not a certified minimum machine requirement. The recorded campaign ran on a 32-GB Windows host with about 16 GB assigned to Docker; its model-storage snapshot was about 3.54 GB and the full private backup about 4.47 GB, excluding many installed/build dependencies. See [observed hardware](../research/postgresql-18.0/HARDWARE.md). Full benchmark execution is much longer than this one-question example; timings are not portable guarantees.

## Troubleshooting

| Symptom | Check |
|---|---|
| Workspace API unavailable | Docker engine, `docker compose ps`, and **Settings**; demo still works independently. |
| Port already in use | Stop only your conflicting preview or configure distinct ports before startup. |
| No published dataset or ready index | Publish reviewed questions and build an index from the matching corpus version. |
| Generation disabled | Set the server-side flag and recreate API/worker together for this new installation. |
| First model download fails | Network access, available disk, and worker logs; do not replace pinned hashes or disable validation. |
| Interrupted run | Start the existing worker; leases/checkpoints recover work. Do not cancel/resubmit merely to resume. |

No live M7 database, private backup, owner `.env`, or pre-populated model cache is shipped with a clone. [Backup recovery](../BACKUP_RESTORE.md) is for a trusted private snapshot; it is not the public onboarding path.
