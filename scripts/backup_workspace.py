"""Create and verify a private local backup, restoring only into isolated disposable containers."""

import argparse
import json
import shutil
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import IO
from uuid import uuid4

from rag_core.backup import database_fingerprint, file_hash, inventory, verify_bundle
from rag_core.settings import Settings
from sqlalchemy import create_engine

ROOT = Path(__file__).resolve().parents[1]

# Preserve readable regular bytes even where the Hugging Face cache uses internal symlinks.
ARCHIVE = r"""
import hashlib, io, json, sys, tarfile
from pathlib import Path

root = Path(sys.argv[1]).resolve()
entries = {}
with tarfile.open(fileobj=sys.stdout.buffer, mode="w|") as archive:
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if not path.resolve().is_relative_to(root):
            raise ValueError("Escaping storage symlink")
        name = path.relative_to(root).as_posix()
        if name == "__inventory__.json":
            raise ValueError("Reserved storage filename")
        digest = hashlib.sha256()

        class Reader:
            def read(self, size=-1):
                data = stream.read(size)
                digest.update(data)
                return data

        info = tarfile.TarInfo(name)
        info.size = path.stat().st_size
        info.mode = 0o600
        with path.open("rb") as stream:
            archive.addfile(info, Reader())
        entries[name] = {"bytes": info.size, "sha256": digest.hexdigest()}
    raw = json.dumps(entries, sort_keys=True).encode()
    info = tarfile.TarInfo("__inventory__.json")
    info.size = len(raw)
    archive.addfile(info, io.BytesIO(raw))
"""
RESTORE = r"""
import hashlib, json, sys, tarfile
from pathlib import Path, PurePosixPath

target = Path(sys.argv[2]).resolve()
target.mkdir(parents=True, exist_ok=True)
actual = {}
expected = None
with tarfile.open(sys.argv[1], "r|") as archive:
    for number, member in enumerate(archive):
        if number >= 200000:
            raise ValueError("Too many storage entries")
        name = member.name
        parts = PurePosixPath(name)
        if (
            not member.isfile()
            or parts.is_absolute()
            or any(p in ("..", ".") for p in name.split("/"))
            or "\\" in name
            or ":" in name
        ):
            raise ValueError("Unsafe storage entry")
        stream = archive.extractfile(member)
        if name == "__inventory__.json":
            if expected is not None or member.size > 32 * 1024 * 1024:
                raise ValueError("Invalid inventory")
            expected = json.load(stream)
            continue
        if name in actual:
            raise ValueError("Duplicate storage entry")
        path = target / name
        path.parent.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256()
        size = 0
        with path.open("xb") as out:
            while chunk := stream.read(1024 * 1024):
                out.write(chunk)
                digest.update(chunk)
                size += len(chunk)
        actual[name] = {"bytes": size, "sha256": digest.hexdigest()}
if actual != expected:
    raise ValueError("Restored storage checksum mismatch")
print(json.dumps({"files": len(actual), "bytes": sum(v["bytes"] for v in actual.values())}))
"""


def run(
    args: list[str], *, stdout: int | IO[bytes] | None = subprocess.PIPE, timeout: float = 600
) -> str:
    result = subprocess.run(
        args, cwd=ROOT, check=True, stdout=stdout, stderr=subprocess.PIPE, timeout=timeout
    )
    return result.stdout.decode() if result.stdout else ""


def ensure_restore_images(destination: Path, images: list[str]) -> str:
    missing = []
    for image in sorted(set(images)):
        try:
            actual = run(["docker", "image", "inspect", "--format", "{{.Id}}", image], timeout=30)
        except subprocess.CalledProcessError as error:
            # An unreachable/unhealthy daemon is not evidence that an image is missing.
            if b"No such image" not in (error.stderr or b""):
                raise
            missing.append(image)
        else:
            if actual.strip() != image:
                raise ValueError("Saved restore image ID does not match installed bytes")
    if not missing:
        return "already-present exact image IDs; archive integrity verified"
    run(["docker", "image", "load", "--input", str(destination / "images.tar")])
    for image in missing:
        actual = run(["docker", "image", "inspect", "--format", "{{.Id}}", image], timeout=30)
        if actual.strip() != image:
            raise ValueError("Loaded restore image ID differs from the saved image")
    return "loaded archive; required exact image IDs verified"


def compose(*args: str) -> list[str]:
    return ["docker", "compose", *args]


def image_of(service: str) -> tuple[str, str]:
    container = run(compose("ps", "-q", service)).strip()
    if not container:
        raise ValueError(f"Required running service missing: {service}")
    image = run(["docker", "inspect", "--format", "{{.Image}}", container]).strip()
    return container, image


def save_archive(container: str, image: str, folder: str, destination: Path) -> None:
    with destination.open("xb") as output:
        run(
            [
                "docker",
                "run",
                "--rm",
                "--network",
                "none",
                "--read-only",
                "--volumes-from",
                container + ":ro",
                "--entrypoint",
                "python",
                image,
                "-c",
                ARCHIVE,
                "/app/data/" + folder,
            ],
            stdout=output,
        )


def copy_research(source: Path, destination: Path) -> None:
    # An OS-held controller lock is transient coordination, not recoverable evidence.
    lock_folder = (source / "postgresql-18.0" / "completion").resolve()

    def ignore(folder: str, names: list[str]) -> list[str]:
        return (
            ["controller.lock"]
            if Path(folder).resolve() == lock_folder and "controller.lock" in names
            else []
        )

    shutil.copytree(source, destination, ignore=ignore)


def create(destination: Path) -> None:
    # All output is private, ignored local data. Refuse reuse and partial overwrite.
    destination.mkdir(parents=True, exist_ok=False)
    services = {name: image_of(name) for name in ["db", "api", "worker", "web"]}
    images = {name: value[1] for name, value in services.items()}
    stopped = False
    try:
        stopped = True
        run(compose("stop", "--timeout", "30", "api", "worker"))
        settings = Settings()
        engine = create_engine(settings.database_url.get_secret_value())
        try:
            snapshot = database_fingerprint(engine)
        finally:
            engine.dispose()
        (destination / "database-fingerprint.json").write_text(
            json.dumps(snapshot), encoding="utf-8"
        )
        with (destination / "database.dump").open("xb") as output:
            run(
                compose(
                    "exec",
                    "-T",
                    "db",
                    "pg_dump",
                    "-U",
                    "rag",
                    "-d",
                    "rag",
                    "--format=custom",
                    "--no-owner",
                    "--no-acl",
                ),
                stdout=output,
            )
        save_archive(*services["api"], "artifacts", destination / "artifacts.tar")
        save_archive(*services["api"], "models", destination / "models.tar")
    finally:
        if stopped:
            run(compose("start", "api", "worker"))
    print("Application writes resumed; sealing remaining local backup files.", flush=True)
    shutil.copyfile(ROOT / ".env", destination / "runtime.env")
    files = run(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"]).split("\0")
    for name in files:
        if not name:
            continue
        source = (ROOT / name).resolve()
        if not source.is_relative_to(ROOT) or not source.is_file():
            raise ValueError("Unsafe/missing project source file")
        target = destination / "source" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    research = ROOT / "data" / "research"
    if research.exists():
        copy_research(research, destination / "research-local")
    run(
        [
            "docker",
            "image",
            "save",
            "--output",
            str(destination / "images.tar"),
            *sorted(set(images.values())),
        ]
    )
    captured_files = inventory(destination)
    manifest = {
        "schema": "workspace-backup-v1",
        "created_at": datetime.now(UTC).isoformat(),
        "git_revision": run(["git", "rev-parse", "HEAD"]).strip(),
        "dirty": bool(run(["git", "status", "--porcelain"]).strip()),
        "images": images,
        "consistency": (
            "API and worker stopped during database/storage capture; no other writers assumed"
        ),
        "contains_secrets": True,
        "model_cache": "regular bytes; internal symlinks dereferenced",
        "scope": (
            "Live rag database, Docker artifacts/models, runtime.env, "
            "source/locks and local research"
        ),
        "excludes": (
            "rag_test, native virtualenv/node_modules, separate native inference caches; "
            "transient data/research/postgresql-18.0/completion/controller.lock"
        ),
        "files": captured_files,
    }
    (destination / "backup-manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    print(json.dumps({"backup": str(destination), "files": len(captured_files)}), flush=True)


def verify(destination: Path) -> None:
    manifest = verify_bundle(destination)
    token = "rag-restore-" + uuid4().hex[:16]
    network, db, api = token + "-net", token + "-db", token + "-api"
    restored = ROOT / "data" / "restore-checks" / token
    restored.mkdir(parents=True, exist_ok=False)
    created: list[str] = []
    network_created = False
    try:
        image_source = ensure_restore_images(destination, list(manifest["images"].values()))
        run(
            [
                "docker",
                "network",
                "create",
                "--internal",
                "--label",
                "rag.restore=" + token,
                network,
            ]
        )
        network_created = True
        run(
            [
                "docker",
                "run",
                "-d",
                "--name",
                db,
                "--label",
                "rag.restore=" + token,
                "--network",
                network,
                "--tmpfs",
                "/var/lib/postgresql/data:rw,size=1g",
                "-e",
                "POSTGRES_HOST_AUTH_METHOD=trust",
                "-e",
                "POSTGRES_USER=rag",
                "-e",
                "POSTGRES_DB=rag_restore",
                manifest["images"]["db"],
            ]
        )
        created.append(db)
        for attempt in range(60):
            try:
                run(["docker", "exec", db, "pg_isready", "-U", "rag", "-d", "rag_restore"])
                break
            except subprocess.CalledProcessError:
                if attempt == 59:
                    raise
                time.sleep(1)
        with (destination / "database.dump").open("rb") as dump:
            subprocess.run(
                [
                    "docker",
                    "exec",
                    "-i",
                    db,
                    "pg_restore",
                    "-U",
                    "rag",
                    "-d",
                    "rag_restore",
                    "--no-owner",
                    "--no-acl",
                    "--exit-on-error",
                    "--single-transaction",
                ],
                stdin=dump,
                check=True,
                capture_output=True,
            )
        storage = {}
        for folder in ["artifacts", "models"]:
            storage[folder] = json.loads(
                run(
                    [
                        "docker",
                        "run",
                        "--rm",
                        "--network",
                        "none",
                        "--read-only",
                        "--user",
                        "0",
                        "--mount",
                        f"type=bind,source={destination},target=/backup,readonly",
                        "--mount",
                        f"type=bind,source={restored},target=/restore",
                        "--entrypoint",
                        "python",
                        manifest["images"]["api"],
                        "-c",
                        RESTORE,
                        f"/backup/{folder}.tar",
                        f"/restore/{folder}",
                    ]
                )
            )
        # No worker or host ports: restore checks cannot dispatch queued inference.
        run(
            [
                "docker",
                "run",
                "-d",
                "--name",
                api,
                "--label",
                "rag.restore=" + token,
                "--network",
                network,
                "--read-only",
                "--tmpfs",
                "/tmp:rw,size=64m",
                "--env-file",
                str(destination / "runtime.env"),
                "-e",
                f"DATABASE_URL=postgresql+psycopg://rag@{db}:5432/rag_restore",
                "-e",
                "ARTIFACT_ROOT=/restore/artifacts",
                "-e",
                "MODEL_CACHE_DIR=/restore/models",
                "--mount",
                f"type=bind,source={restored},target=/restore,readonly",
                "--mount",
                f"type=bind,source={destination},target=/backup,readonly",
                manifest["images"]["api"],
            ]
        )
        created.append(api)
        fingerprint = json.loads(
            run(
                [
                    "docker",
                    "exec",
                    api,
                    "python",
                    "/backup/source/packages/rag_core/src/rag_core/backup.py",
                ]
            )
        )
        expected = json.loads(
            (destination / "database-fingerprint.json").read_text(encoding="utf-8")
        )
        if fingerprint != expected:
            raise ValueError("Restored database differs from the frozen source snapshot")
        for attempt in range(30):
            try:
                run(
                    [
                        "docker",
                        "exec",
                        api,
                        "python",
                        "-c",
                        "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health/ready',timeout=3)",
                    ]
                )
                break
            except subprocess.CalledProcessError:
                if attempt == 29:
                    raise
                time.sleep(1)
        checks = run(["docker", "exec", api, "python", "-c", VERIFY_API])
        report = {
            "verified_at": datetime.now(UTC).isoformat(),
            "status": "passed",
            "image_source": image_source,
            "backup_manifest_sha256": file_hash(destination / "backup-manifest.json"),
            "tables": fingerprint,
            "storage": storage,
            "api": json.loads(checks),
            "restored_files": str(restored),
            "isolation": "Internal network; no host ports; no worker",
            "limitations": (
                "Same-machine Docker restore, not independent offsite disaster recovery; "
                "no inference rerun"
            ),
        }
        (destination / "restore-report.json").write_text(
            json.dumps(report, indent=2), encoding="utf-8"
        )
        print(
            json.dumps({"restore": "passed", "tables": len(fingerprint), "storage": storage}),
            flush=True,
        )
    finally:
        for container in reversed(created):
            # Only remove our exact fresh container after validating its ownership label.
            label = run(
                [
                    "docker",
                    "inspect",
                    "--format",
                    '{{index .Config.Labels "rag.restore"}}',
                    container,
                ]
            ).strip()
            if label != token:
                raise ValueError("Restore cleanup ownership mismatch")
            run(["docker", "rm", "-f", container])
        if network_created:
            run(["docker", "network", "rm", network])


VERIFY_API = r"""
import hashlib, json, urllib.request
from pathlib import Path
from sqlalchemy import create_engine, text
from rag_core.settings import Settings

engine = create_engine(Settings().database_url.get_secret_value())
counts = {}
with engine.connect() as c:
    for row in c.execute(text("SELECT storage_key,checksum FROM documents")):
        path = Path("/restore/artifacts") / row.storage_key
        assert hashlib.sha256(path.read_bytes()).hexdigest() == row.checksum
    counts["originals"] = c.scalar(text("SELECT count(*) FROM documents"))
    for row in c.execute(text("SELECT id,output FROM export_jobs WHERE state='completed'")):
        with urllib.request.urlopen(
            "http://127.0.0.1:8000/api/v1/exports/" + str(row.id) + "/download"
        ) as r:
            raw = r.read()
        assert hashlib.sha256(raw).hexdigest() == row.output["sha256"]
    counts["exports"] = c.scalar(text("SELECT count(*) FROM export_jobs WHERE state='completed'"))
    for table, path in [("runs", "runs"), ("comparisons", "comparisons")]:
        for id in c.scalars(text("SELECT id FROM " + table)):
            with urllib.request.urlopen(
                "http://127.0.0.1:8000/api/v1/" + path + "/" + str(id)
            ) as r:
                assert r.status == 200
        counts[table] = c.scalar(text("SELECT count(*) FROM " + table))
engine.dispose()
print(json.dumps(counts))
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["create", "verify"])
    parser.add_argument("--directory", type=Path, required=True)
    args = parser.parse_args()
    destination = args.directory.resolve()
    if not destination.is_relative_to(ROOT / "data" / "backups"):
        raise ValueError("Backups must stay under ignored workspace data/backups")
    if args.action == "create":
        create(destination)
    else:
        verify(destination)


if __name__ == "__main__":
    main()
