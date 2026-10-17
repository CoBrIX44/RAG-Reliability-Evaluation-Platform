"""Bounded, pinned research-source acquisition; ingestion still runs in the worker."""

import argparse
import hashlib
import json
import tarfile
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ARCHIVE_URL = "https://ftp.postgresql.org/pub/source/v18.0/postgresql-18.0-docs.tar.gz"
ARCHIVE_SHA256 = "f0dfc5b0882aa68ca471e9930a0dcfe4644a10a9b9613c60d6d14bfc9c224d44"
PREFIX = "postgresql-18.0/doc/src/sgml/html/"
MAX_ARCHIVE_BYTES = 8 * 1024 * 1024
MAX_PAGE_BYTES = 2 * 1024 * 1024
MAX_SELECTED_BYTES = 32 * 1024 * 1024


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


class SelectedPage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    filename: str
    topic: str = Field(min_length=1, max_length=160)

    @field_validator("filename")
    @classmethod
    def safe_filename(cls, value: str) -> str:
        if (
            not value.endswith(".html")
            or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789-." for c in value)
            or value.startswith(".")
        ):
            raise ValueError("Expected a plain PostgreSQL HTML filename")
        return value


class CorpusSelection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str = Field(alias="schema")
    release: str
    archive_url: str
    archive_sha256: str
    selection_rationale: str = Field(min_length=1)
    pages: list[SelectedPage] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def pinned(self) -> "CorpusSelection":
        if (
            self.release != "18.0"
            or self.archive_url != ARCHIVE_URL
            or self.archive_sha256 != ARCHIVE_SHA256
            or self.schema_version != "postgresql-corpus-selection-v1"
            or len({p.filename for p in self.pages}) != len(self.pages)
        ):
            raise ValueError("Selection must use the pinned 18.0 archive and unique pages")
        return self


def prepare(selection_path: Path, root: Path) -> dict[str, Any]:
    """Verify before writing selected bytes; never extract arbitrary tar paths."""
    selection_raw = selection_path.read_bytes()
    selection = CorpusSelection.model_validate_json(selection_raw)
    root.mkdir(parents=True, exist_ok=True)
    archive_path = root / "postgresql-18.0-docs.tar.gz"
    if archive_path.exists():
        if archive_path.stat().st_size > MAX_ARCHIVE_BYTES:
            raise ValueError("Archive exceeds download limit")
        raw = archive_path.read_bytes()
    else:
        with urllib.request.urlopen(ARCHIVE_URL, timeout=60) as response:
            if response.url != ARCHIVE_URL:
                raise ValueError("Unexpected archive redirect")
            raw = response.read(MAX_ARCHIVE_BYTES + 1)
        if len(raw) > MAX_ARCHIVE_BYTES or sha256(raw) != ARCHIVE_SHA256:
            raise ValueError("Archive does not match the pinned SHA-256/size limit")
        archive_path.write_bytes(raw)
    if sha256(raw) != ARCHIVE_SHA256:
        raise ValueError("Archive does not match the pinned SHA-256")
    selected = {p.filename: p.topic for p in selection.pages}
    wanted = set(selected) | {"legalnotice.html"}
    payload: dict[str, bytes] = {}
    html_names: list[str] = []
    with tarfile.open(archive_path, "r:gz") as archive:
        for ordinal, member in enumerate(archive):
            if ordinal >= 10000:
                raise ValueError("Archive contains too many entries")
            if not member.name.startswith(PREFIX):
                continue
            name = member.name.removeprefix(PREFIX)
            if member.isfile() and "/" not in name and name.endswith(".html"):
                html_names.append(name)
            if name not in wanted:
                continue
            if name in payload or not member.isfile() or member.size > MAX_PAGE_BYTES:
                raise ValueError("Unsafe or oversized selected archive member")
            stream = archive.extractfile(member)
            if stream is None:
                raise ValueError("Missing archive member bytes")
            data = stream.read(MAX_PAGE_BYTES + 1)
            if (
                len(data) != member.size
                or sum(map(len, payload.values())) + len(data) > MAX_SELECTED_BYTES
            ):
                raise ValueError("Selected corpus exceeds extraction limits")
            payload[name] = data
    if set(payload) != wanted:
        raise ValueError(f"Missing selected pages: {sorted(wanted - set(payload))}")
    # Existing evidence is verified rather than overwritten, including the acquisition timestamp.
    manifest_path = root / "acquisition.json"
    previous = (
        json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else None
    )
    manifest = {
        "schema": "postgresql-corpus-acquisition-v1",
        "release": selection.release,
        "archive_url": ARCHIVE_URL,
        "archive_sha256": ARCHIVE_SHA256,
        "archive_bytes": len(raw),
        "acquired_at": previous["acquired_at"] if previous else datetime.now(UTC).isoformat(),
        "checksum_origin": "Locally captured over official HTTPS; not an upstream signed digest",
        "selection_sha256": sha256(selection_raw),
        "selection_rationale": selection.selection_rationale,
        "license": "PostgreSQL",
        "attribution_member": PREFIX + "legalnotice.html",
        "license_sha256": sha256(payload["legalnotice.html"]),
        "documents": [
            {
                "filename": name,
                "topic": selected[name],
                "archive_member": PREFIX + name,
                "source_url": ARCHIVE_URL + "#" + PREFIX + name,
                "sha256": sha256(payload[name]),
                "bytes": len(payload[name]),
            }
            for name in sorted(selected)
        ],
        "excluded_html": sorted(set(html_names) - set(selected)),
        "exclusion_reason": (
            "Outside the preselected topic subset; navigation/reference coverage is limited"
        ),
    }
    if previous is not None and previous != manifest:
        raise ValueError("Existing acquisition manifest differs; use a new directory")
    for name, data in payload.items():
        target = root / name
        if target.exists() and target.read_bytes() != data:
            raise ValueError(f"Existing acquired file changed: {name}")
    for name, data in payload.items():
        (root / name).write_bytes(data)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest = prepare(args.selection, args.output)
    print(json.dumps({"release": manifest["release"], "documents": len(manifest["documents"])}))


if __name__ == "__main__":
    main()
