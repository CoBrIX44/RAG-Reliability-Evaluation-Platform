"""Read a live draft and frozen corpus, writing audit evidence without changing records."""

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from import_benchmark import all_items, request
from rag_core.benchmark_audit import audit_curation
from rag_core.dataset_schemas import QuestionView
from rag_core.schemas import SectionView


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-id", type=UUID, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    binding = json.loads((args.source / "workspace-binding.json").read_text(encoding="utf-8"))
    dataset = request(f"/datasets/{args.dataset_id}")
    if dataset["corpus_version_id"] != binding["corpus_version_id"]:
        raise ValueError("Draft is not bound to this frozen corpus")
    versions = all_items(f"/corpora/{binding['corpus_id']}/versions")
    version = next(v for v in versions if v["id"] == binding["corpus_version_id"])
    if version["manifest_hash"] != binding["corpus_manifest_hash"]:
        raise ValueError("Published corpus hash differs from local provenance binding")
    rows = all_items(f"/datasets/{args.dataset_id}/questions")
    questions = [QuestionView.model_validate(row) for row in rows]
    sections = [
        SectionView.model_validate(row)
        for row in all_items(f"/corpus-versions/{binding['corpus_version_id']}/sections")
    ]
    report = audit_curation(
        questions,
        sections,
        allowed_revision_ids={UUID(d["revision_id"]) for d in version["manifest"]["documents"]},
    )
    # Detect edits while we read; do not report a mixed draft as one audited revision.
    current = request(f"/datasets/{args.dataset_id}")
    if current["draft_revision"] != dataset["draft_revision"]:
        raise ValueError("Draft changed during audit; rerun for a consistent revision")
    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "dataset": dataset,
        "corpus_manifest_hash": version["manifest_hash"],
        "question_snapshot_sha256": hashlib.sha256(
            json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
        "report": report.model_dump(mode="json"),
        "questions": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "questions": report.question_count,
                "reviewed": report.reviewed_count,
                "issues": len(report.issues),
                "source_groups": len(report.source_groups),
                "output": str(args.output),
            }
        )
    )


if __name__ == "__main__":
    main()
