"""Prepare and explicitly submit development-only benchmark cells to the durable worker."""

import argparse
import hashlib
import json
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from rag_core.backup import file_hash
from rag_core.benchmark_execution import development_cells
from rag_core.runs import digest

from scripts.import_benchmark import API, all_items, request

ROOT = Path(__file__).resolve().parents[1]


def write(path: Path, value: Any) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8", newline="\n")
    temporary.replace(path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["prepare", "submit", "status"])
    parser.add_argument("--cell", default="section/dense")
    parser.add_argument(
        "--plan", type=Path, default=ROOT / "research/postgresql-18.0/EXPERIMENT_PLAN.json"
    )
    parser.add_argument("--source", type=Path, default=ROOT / "data/research/postgresql-18.0")
    parser.add_argument("--backup", type=Path, default=ROOT / "data/backups/m7-20261016-02")
    args = parser.parse_args()
    source = args.source.resolve()
    if not source.is_relative_to(ROOT / "data/research"):
        raise ValueError("Execution receipts stay in ignored local research storage")
    receipt_path = source / "development-execution.json"
    if args.action == "status":
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        states = []
        for cell, entry in receipt["submissions"].items():
            if "run_id" in entry:
                run = request("/runs/" + entry["run_id"])
                states.append(
                    {
                        "cell": cell,
                        **{
                            k: run[k]
                            for k in [
                                "id",
                                "state",
                                "completed_count",
                                "failed_count",
                                "total_count",
                                "error_code",
                            ]
                        },
                    }
                )
        write(
            source / "development-status.json",
            {"observed_at": datetime.now(UTC).isoformat(), "runs": states},
        )
        print(json.dumps(states, indent=2))
        return
    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    backup = args.backup.resolve()
    if not backup.is_relative_to(ROOT / "data/backups"):
        raise ValueError("Use a private local backup")
    backup_hash = file_hash(backup / "backup-manifest.json")
    # Preparing reviewable requests is read-only; only execution depends on restore verification.
    if args.action == "submit":
        restore = json.loads((backup / "restore-report.json").read_text(encoding="utf-8"))
        if restore["status"] != "passed" or restore["backup_manifest_sha256"] != backup_hash:
            raise ValueError("A verified backup must bind the current captured manifest")
    split_manifest = json.loads(
        (args.plan.parent / plan["split_manifest"]).read_text(encoding="utf-8")
    )
    versions = all_items("/datasets/" + split_manifest["dataset_id"] + "/versions")
    dataset = next(v for v in versions if v["id"] == plan["dataset_version_id"])
    prepared = json.loads((source / "index-preparation.json").read_text(encoding="utf-8"))
    indexes = [request("/indexes/" + selected["id"]) for selected in prepared["selections"]]
    cells = development_cells(plan, dataset, indexes)
    definition = {
        "schema": "development-qualification-v1",
        "dataset_version_id": dataset["id"],
        "dataset_manifest_hash": dataset["manifest_hash"],
        "backup_manifest_sha256": backup_hash,
        "cells": cells,
        "qualification_policy": (
            "One repeat per105 development questions/cell; final test plan still three repeats. "
            "No test submission or quality endorsement."
        ),
    }
    identity = digest(definition)
    if receipt_path.exists():
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        if receipt["definition_sha256"] != identity:
            raise ValueError(
                "Development inputs changed; retain old receipts and use a new campaign"
            )
    else:
        receipt = {
            "prepared_at": datetime.now(UTC).isoformat(),
            "definition_sha256": identity,
            "definition": definition,
            "submissions": {},
        }
    if args.action == "prepare":
        write(receipt_path, receipt)
        print(
            json.dumps(
                {
                    "cells": len(cells),
                    "observations_if_all_submitted": 840,
                    "submitted": len(receipt["submissions"]),
                }
            )
        )
        return
    matches = [cell for cell in cells if cell["cell"] == args.cell]
    if len(matches) != 1:
        raise ValueError("Choose an exact prepared development cell")
    selected = matches[0]
    experiment = request("/experiments", selected["request"])
    key = "pg18-dev-" + hashlib.sha256((identity + ":" + args.cell).encode()).hexdigest()
    entry = receipt["submissions"].setdefault(
        args.cell, {"experiment_id": experiment["id"], "idempotency_key": key}
    )
    if entry["experiment_id"] != experiment["id"] or entry["idempotency_key"] != key:
        raise ValueError("Existing submission differs; do not replace its key")
    # Persist the exact key before any ambiguous network outcome. Repeating POST reuses the run.
    write(receipt_path, receipt)
    req = urllib.request.Request(
        API + "/experiments/" + experiment["id"] + "/runs",
        data=b"{}",
        headers={"Content-Type": "application/json", "Idempotency-Key": key},
    )
    with urllib.request.urlopen(req, timeout=60) as response:
        run = json.load(response)
    manifest = request("/runs/" + run["id"] + "/manifest")
    if manifest["config"]["split"] != "development" or run["total_count"] != 105:
        raise ValueError("Submission did not freeze the expected development universe")
    entry.update(
        run_id=run["id"],
        manifest_hash=run["manifest_hash"],
    )
    entry.setdefault("submitted_at", datetime.now(UTC).isoformat())
    write(source / ("development-manifest-" + run["id"] + ".json"), manifest)
    write(receipt_path, receipt)
    print(
        json.dumps(
            {
                "cell": args.cell,
                "run_id": run["id"],
                "state": run["state"],
                "observations": run["total_count"],
            }
        )
    )


if __name__ == "__main__":
    main()
