"""Resolve authored candidates to canonical spans and import only unreviewed drafts."""

import argparse
import json
from pathlib import Path
from typing import Any

from import_benchmark import all_items, request
from rag_core.benchmark_corpus import sha256
from rag_core.dataset_schemas import QuestionInput


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--batch", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    binding = json.loads((args.source / "workspace-binding.json").read_text(encoding="utf-8"))
    if sha256((args.source / "acquisition.json").read_bytes()) != binding["acquisition_sha256"]:
        raise ValueError("Acquisition provenance changed")
    candidates = json.loads(args.batch.read_text(encoding="utf-8"))
    if not 1 <= len(candidates) <= 30:
        raise ValueError("Review batches must contain 1..30 candidates")
    evidence: list[Any] = []
    questions: list[dict[str, Any]] = []
    for candidate in candidates:
        documents = [d for d in binding["documents"] if d["filename"] == candidate["filename"]]
        if len(documents) != 1:
            raise ValueError("Candidate source is outside the acquired corpus")
        document = documents[0]
        groups = []
        section = None
        if candidate["answerable"]:
            sections = all_items(f"/documents/{document['document_id']}/sections")
            needle = candidate["match_normalized_text"].casefold()
            hits = [
                s for s in sections if needle and needle in " ".join(s["text"].split()).casefold()
            ]
            if len(hits) != 1 or hits[0]["revision_id"] != document["revision_id"]:
                raise ValueError("Candidate evidence is missing, ambiguous, or has changed lineage")
            section = hits[0]
            groups = [
                {
                    "fact_index": 0,
                    "alternatives": [
                        {
                            "spans": [
                                {
                                    "section_id": section["id"],
                                    "start_offset": 0,
                                    "end_offset": len(section["text"]),
                                }
                            ]
                        }
                    ],
                }
            ]
        value = QuestionInput(
            text=candidate["text"],
            answerable=candidate["answerable"],
            reference_answer=candidate["reference_answer"],
            required_facts=candidate["required_facts"],
            evidence_groups=groups,
            topic=candidate["topic"],
            difficulty=candidate["difficulty"],
            split="unassigned",
            split_group="pg18-" + Path(candidate["filename"]).stem,
            review_status="candidate",
            reviewer="",
        ).model_dump(mode="json")
        questions.append(value)
        evidence.append(section)
    name = "PostgreSQL 18.0 benchmark candidates — batch 01"
    description = (
        "Codex-authored candidates requiring individual human fact/answerability/evidence review. "
        "Unassigned splits; no published benchmark. Batch specification SHA-256: "
        + sha256(args.batch.read_bytes())
    )
    matches = [d for d in all_items("/datasets") if d["name"] == name]
    if len(matches) > 1 or any(
        d["corpus_version_id"] != binding["corpus_version_id"] or d["description"] != description
        for d in matches
    ):
        raise ValueError("Existing dataset has ambiguous/different provenance")
    dataset = (
        matches[0]
        if matches
        else request(
            "/datasets",
            {
                "name": name,
                "description": description,
                "purpose": "research",
                "corpus_version_id": binding["corpus_version_id"],
            },
        )
    )
    path = f"/datasets/{dataset['id']}"
    existing = all_items(path + "/questions")
    if not existing:
        raw = "\n".join(json.dumps(q) for q in questions).encode()
        request(path + "/import", file=("candidates.jsonl", raw))
        existing = all_items(path + "/questions")
    if {q["content"]["text"] for q in existing} != {q["text"] for q in questions}:
        raise ValueError("Existing draft membership differs; refusing automatic edits")
    # No PATCH, review attestation, split freeze, or dataset publication occurs here.
    by_text = {q["content"]["text"]: q for q in existing}
    args.output.mkdir(parents=True, exist_ok=True)
    records = [
        {
            "candidate": candidate,
            "question_id": by_text[q["text"]]["id"],
            "proposed_content": q,
            "source_section": section,
        }
        for candidate, q, section in zip(candidates, questions, evidence, strict=True)
    ]
    receipt = {"dataset_id": dataset["id"], "corpus_binding": binding, "records": records}
    (args.output / "review-batch-01.json").write_text(
        json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    lines = [
        "# PostgreSQL 18.0 — review batch 01",
        "",
        "Status: 10 authored candidates, not approved labels. Splits are unassigned.",
        "",
        f"Dataset: `{dataset['id']}`; corpus version: `{binding['corpus_version_id']}`.",
        "",
        "Open http://localhost:3000/datasets and select the benchmark candidates dataset. "
        "For EACH candidate, inspect the full canonical source, correct or reject its question, "
        "reference, required facts and evidence, and record your reviewer name only after review. "
        "Check unanswerable cases against the whole frozen corpus. Leave splits unassigned; "
        "grouping/leakage review precedes split freeze. This document is not an attestation.",
        "",
    ]
    for record in records:
        candidate, section = record["candidate"], record["source_section"]
        lines += [
            f"## {candidate['candidate_id']} — {candidate['topic']} / {candidate['difficulty']}",
            "",
            candidate["text"],
            "",
            f"Question ID: `{record['question_id']}`. "
            f"Proposed answerable: {candidate['answerable']}.",
            "",
            "Proposed reference: " + (candidate["reference_answer"] or "No supported answer."),
            "",
        ]
        if section:
            lines += [
                f"Source: `{candidate['filename']}`, section `{section['id']}`, "
                f"code-point span `[0, {len(section['text'])})`.",
                "",
                "````text",
                section["text"],
                "````",
                "",
            ]
        else:
            lines += ["Review rationale: " + candidate["unanswerability_rationale"], ""]
    (args.output / "REVIEW_BATCH_01.md").write_text("\n".join(lines), encoding="utf-8")
    print(
        json.dumps(
            {
                "dataset_id": dataset["id"],
                "candidates": len(existing),
                "reviewed": sum(q["content"]["review_status"] == "reviewed" for q in existing),
            }
        )
    )


if __name__ == "__main__":
    main()
