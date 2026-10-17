"""Integrity and database fingerprints for trusted, local workspace backups."""

import hashlib
import json
from pathlib import Path, PurePosixPath
from typing import Any

from sqlalchemy import Engine, inspect, text


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def contained_file(root: Path, name: str) -> Path:
    part = PurePosixPath(name)
    if (
        not name
        or "\\" in name
        or ":" in name
        or part.is_absolute()
        or any(p in {"..", "."} for p in name.split("/"))
    ):
        raise ValueError("Invalid backup member path")
    path = (root / name).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError("Missing or escaping backup file")
    return path


def inventory(root: Path) -> dict[str, dict[str, Any]]:
    return {
        p.relative_to(root).as_posix(): {"bytes": p.stat().st_size, "sha256": file_hash(p)}
        for p in sorted(root.rglob("*"))
        if p.is_file()
        and p.relative_to(root).as_posix() not in {"backup-manifest.json", "restore-report.json"}
    }


def verify_bundle(root: Path) -> dict[str, Any]:
    manifest: dict[str, Any] = json.loads(
        contained_file(root, "backup-manifest.json").read_text(encoding="utf-8")
    )
    if manifest.get("schema") != "workspace-backup-v1" or not manifest.get("files"):
        raise ValueError("Unsupported or incomplete backup manifest")
    for name, expected in manifest["files"].items():
        path = contained_file(root, name)
        if path.stat().st_size != expected["bytes"] or file_hash(path) != expected["sha256"]:
            raise ValueError(f"Backup integrity mismatch: {name}")
    return manifest


def database_fingerprint(engine: Engine) -> dict[str, Any]:
    """Hash every public application row under one read-only repeatable snapshot."""
    tables = inspect(engine).get_table_names(schema="public")
    result: dict[str, Any] = {}
    with engine.connect() as conn, conn.begin():
        conn.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
        for name in sorted(tables):
            quoted = '"' + name.replace('"', '""') + '"'
            digest, count = hashlib.sha256(), 0
            rows = conn.execution_options(stream_results=True).execute(
                text(f"SELECT to_jsonb(t) AS row FROM public.{quoted} t ORDER BY to_jsonb(t)::text")
            )
            row: Any
            for row in rows.scalars():
                digest.update(json.dumps(row, sort_keys=True, separators=(",", ":")).encode())
                digest.update(b"\n")
                count += 1
            result[name] = {"rows": count, "sha256": digest.hexdigest()}
    return result


if __name__ == "__main__":
    import os

    from sqlalchemy import create_engine

    engine = create_engine(os.environ["DATABASE_URL"])
    try:
        print(json.dumps(database_fingerprint(engine), sort_keys=True))
    finally:
        engine.dispose()
