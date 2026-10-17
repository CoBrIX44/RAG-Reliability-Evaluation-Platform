# Local Docker workspace backup and restore

The supported scope is the trusted local Compose workspace: the live `rag` database, Docker artifact/model storage, runtime configuration, exact service images, project source/locks and `data/research` provenance/review receipts. `rag_test`, native virtual environments, `node_modules` and separate native inference caches are excluded. This is a private snapshot containing `runtime.env` and corpus/answer text; it belongs under ignored `data/backups`, not in Git or public downloads. The tool does not encrypt it.

## Create a consistent snapshot

Run from the repository root with Docker and all four services running. Use a new directory for each backup:

```powershell
uv run python scripts/backup_workspace.py create --directory data/backups/my-checkpoint-01
```

The command stops the API and worker, fingerprints every public database table in a read-only repeatable snapshot, streams a custom-format PostgreSQL dump, and captures artifact/model files while application writes are paused. It restarts the API/worker in `finally`, including on failure. The web container stays running; API actions are temporarily unavailable. Other direct database/filesystem writers must also remain idle during capture.

Model cache internal symlinks are copied as verified regular bytes, with no dependency on Windows symlink support. File capture refuses a symlink that escapes its storage root. The backup then retains private configuration, source files (including current uncommitted files), local research metadata and `docker image save` output for exact image IDs. Every outer file receives a SHA-256/byte count in `backup-manifest.json`; artifact/model archives also contain per-entry inventories. A partial backup has no completed manifest and cannot be verified. Interrupted output is retained for inspection; the command refuses to overwrite an existing directory.

`database.dump` uses the installed PostgreSQL 17 `pg_dump --format=custom --no-owner --no-acl`. Recovery recreates the application's single `rag` role; custom external roles/grants, additional databases and host-level services are outside this local deployment's scope. The saved database image preserves the PostgreSQL/pgvector runtime used to create the dump. See the official [pg_dump](https://www.postgresql.org/docs/17/app-pgdump.html) and [pg_restore](https://www.postgresql.org/docs/17/app-pgrestore.html) references.

## Verify a restore without touching the live database

Only verify a trusted backup created locally by this tool:

```powershell
uv run python scripts/backup_workspace.py verify --directory data/backups/my-checkpoint-01
```

Verification first checks every recorded outer file hash, including the saved image archive. If every saved image ID is already installed with an exact ID match, it reuses those bytes. Otherwise it loads the archive and verifies the required IDs afterward. Image inspection has a30-second bound; other external commands have a600-second bound. Daemon errors/timeouts fail rather than being treated as a missing image. It creates a unique internal Docker network and a fresh PostgreSQL container with no host ports and a1 GiB temporary database filesystem. `pg_restore --single-transaction --exit-on-error --no-owner --no-acl` restores into a new `rag_restore` database inside that container, independently of both live `rag` and `rag_test`.

Archives restore only regular files into a fresh ignored `data/restore-checks/rag-restore-...` directory. Absolute/parent/backslash/drive paths, links, duplicate entries and invalid inventory are rejected; all restored entry hashes and sizes must match. A read-only API uses the exact saved image and restored artifact/model mounts, with no worker and no externally reachable ports. Verification checks:

- Every restored public table's complete row count and SHA-256 equals the frozen source fingerprint, including canonical text, snapshots, drafts, vectors, manifests, results and failed evaluations.
- Every original document file matches its stored SHA-256.
- Every completed evidence export downloads through the restored API and matches its recorded SHA-256.
- Saved run/comparison APIs respond, and schema/pgvector readiness passes.
- All artifact/model files match the captured inventories.

Success writes `restore-report.json`, bound to the backup manifest hash. Temporary containers are removed only after checking their unique ownership labels; the isolated network is removed. Restored files remain locally for inspection, rather than deleting a computed host path automatically. Verification never starts a worker or inference call, publishes labels, resets a live record, migrates the live database, or removes a named live volume.

## Recovery and limits

The `verify` command is a rehearsal and removes its temporary database afterward. For an actual recovery, first verify the backup, then provision a **separate** Compose project with new persistent database/artifact/model volumes and distinct loopback ports. Load `images.tar`, bind the exact saved image IDs from the manifest, restore `database.dump` into that new project's `rag` database with the same `pg_restore` options, and populate its storage from the verified restored files. Restore `runtime.env` privately and adjust only that new project's database/ports/storage settings. Confirm readiness and saved evidence before switching the local UI to the recovered project. Retain the original project/volumes until recovery is accepted.

Do not execute new migrations merely because newer code exists: restore the matching schema/runtime first. Pending work requires matching frozen code/configuration/model identity before a worker can resume. Older historical run source bytes may already have been unavailable before backup; restoring the current workspace does not reconstruct those bytes or establish bitwise reproducibility of all historical inference.

This procedure tests a same-machine Docker recovery, not loss of the machine, independent offsite storage, every supported corpus size, a full native installation, or replay of measured inference. The temporary database bound is suitable for the verified current workspace; larger snapshots need a deliberately sized isolated target. Files added and labels changed after capture belong in a later backup.


## Latest verified checkpoint - 2026-10-16
Private data/backups/m7-20261016-02 now passes isolated restore:23 tables,83 artifact files and86 model files match;41 originals/one completed export/six saved runs/three comparisons and API readiness verify. restore-report.json binds backup manifest fd50d3c3a24c450a93facdfe96822c598cd417a3b71ff4d44c2a385a84e79869. Exact installed saved image IDs were reused after archive integrity verification. Temporary owned containers/network were removed. This snapshot includes the frozen150-question dataset and four indexes, but precedes the newly submitted development campaign. A later backup is needed for its results.
