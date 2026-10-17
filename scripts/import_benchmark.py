"""Import the verified local research subset through the existing durable ingestion API."""

import argparse
import json
import time
import urllib.request
from pathlib import Path
from typing import Any
from uuid import uuid4

from rag_core.benchmark_corpus import prepare, sha256

API = "http://127.0.0.1:8000/api/v1"


def request(path: str, data: Any = None, *, file: tuple[str, bytes] | None = None) -> Any:
    headers = {}
    body = None
    if file is not None:
        name, raw = file
        boundary = uuid4().hex
        headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
        body = (
            f'--{boundary}\r\nContent-Disposition: form-data; name="file"; '
            f'filename="{name}"\r\nContent-Type: text/html\r\n\r\n'.encode()
            + raw
            + f"\r\n--{boundary}--\r\n".encode()
        )
    elif data is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(data).encode()
    with urllib.request.urlopen(
        urllib.request.Request(API + path, data=body, headers=headers), timeout=60
    ) as response:
        return json.load(response)


def all_items(path: str) -> list[Any]:
    items: list[Any] = []
    cursor = 0
    while True:
        page = request(f"{path}?limit=100&cursor={cursor}")
        items.extend(page["items"])
        if page["next_cursor"] is None:
            return items
        cursor = page["next_cursor"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    args = parser.parse_args()
    manifest = prepare(args.selection, args.source)
    acquisition_hash = sha256((args.source / "acquisition.json").read_bytes())
    name = "PostgreSQL 18.0 benchmark source subset"
    description = (
        "Research corpus: official numbered 18.0 archive; 40 preselected topic pages. "
        f"Acquisition manifest SHA-256: {acquisition_hash}. "
        "See research/postgresql-18.0/acquisition.json for source/license/exclusions. "
        "No benchmark dataset or research result is published by this import."
    )
    matches = [c for c in all_items("/corpora") if c["name"] == name]
    if len(matches) > 1 or any(c["description"] != description for c in matches):
        raise ValueError("Existing corpus name has ambiguous/different provenance")
    corpus = (
        matches[0] if matches else request("/corpora", {"name": name, "description": description})
    )
    corpus_id = corpus["id"]
    for document in manifest["documents"]:
        raw = (args.source / document["filename"]).read_bytes()
        if sha256(raw) != document["sha256"]:
            raise ValueError("Selected file changed after verification")
        saved = request(f"/corpora/{corpus_id}/documents", file=(document["filename"], raw))
        if saved["checksum"] != document["sha256"]:
            raise ValueError("Uploaded bytes do not match acquired source")
    deadline = time.monotonic() + 1200
    expected = {d["filename"]: d["sha256"] for d in manifest["documents"]}
    while True:
        documents = all_items(f"/corpora/{corpus_id}/documents")
        if {d["filename"]: d["checksum"] for d in documents} != expected:
            raise ValueError("Corpus membership differs from acquired selection")
        if any(d["state"] == "failed" for d in documents):
            raise ValueError("Document ingestion failed; inspect retained job errors")
        if all(d["state"] == "ready" for d in documents):
            break
        if time.monotonic() > deadline:
            raise TimeoutError(
                "Ingestion is still queued; rerun to resume without duplicate uploads"
            )
        time.sleep(1)
    version = request(f"/corpora/{corpus_id}/versions", {})
    if {
        d["filename"]: d["original_checksum"] for d in version["manifest"]["documents"]
    } != expected:
        raise ValueError("Published corpus lineage differs from acquisition")
    binding = {
        "acquisition_sha256": acquisition_hash,
        "corpus_id": corpus_id,
        "corpus_version_id": version["id"],
        "corpus_manifest_hash": version["manifest_hash"],
        "documents": version["manifest"]["documents"],
    }
    (args.source / "workspace-binding.json").write_text(
        json.dumps(binding, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"corpus_version_id": version["id"], "documents": len(documents)}))


if __name__ == "__main__":
    main()
