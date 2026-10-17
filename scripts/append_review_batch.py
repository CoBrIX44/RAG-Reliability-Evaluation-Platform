"""Append source-linked candidates to an existing draft; retain every existing human edit."""

import argparse
import json
from pathlib import Path
from uuid import UUID

from import_benchmark import all_items, request
from rag_core.benchmark_corpus import sha256
from rag_core.dataset_schemas import QuestionInput
from rag_core.datasets import normalized_question
from rag_core.evidence_quotes import quote_span


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-id", type=UUID, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--batch", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    binding = json.loads((args.source / "workspace-binding.json").read_text(encoding="utf-8"))
    dataset = request(f"/datasets/{args.dataset_id}")
    if (
        dataset["purpose"] != "research"
        or dataset["corpus_version_id"] != binding["corpus_version_id"]
    ):
        raise ValueError("Choose a research draft bound to the acquired corpus")
    if sha256((args.source / "acquisition.json").read_bytes()) != binding["acquisition_sha256"]:
        raise ValueError("Acquisition provenance changed")
    path = f"/datasets/{args.dataset_id}"
    before = all_items(path + "/questions")
    batch_hash = sha256(args.batch.read_bytes())
    if args.receipt.exists():
        saved = json.loads(args.receipt.read_text(encoding="utf-8"))
        if saved["batch_sha256"] != batch_hash or saved["dataset_id"] != str(args.dataset_id):
            raise ValueError("Receipt belongs to different batch inputs")
        if not set(saved["question_ids"]).issubset({q["id"] for q in before}):
            raise ValueError(
                "Existing imported questions are missing; refusing automatic recreation"
            )
        print(json.dumps({"batch": len(saved["question_ids"]), "already_imported": True}))
        return
    specs = json.loads(args.batch.read_text(encoding="utf-8"))
    if not 1 <= len(specs) <= 30 or len({s["candidate_id"] for s in specs}) != len(specs):
        raise ValueError("Use 1..30 uniquely identified candidates per batch")
    sections = all_items(f"/corpus-versions/{binding['corpus_version_id']}/sections")
    revisions = {d["filename"]: d["revision_id"] for d in binding["documents"]}
    values = []
    resolved = []
    for spec in specs:
        groups = []
        quotes = []
        for evidence in spec["evidence_specs"]:
            revision_id = revisions[evidence["filename"]]
            matches = []
            for section in sections:
                if section["revision_id"] != revision_id:
                    continue
                try:
                    start, end = quote_span(section["text"], evidence["quote"])
                    matches.append((section, start, end))
                except ValueError:
                    continue
            if len(matches) != 1:
                raise ValueError(f"Missing/ambiguous canonical quote for {spec['candidate_id']}")
            section, start, end = matches[0]
            groups.append(
                {
                    "fact_index": evidence["fact_index"],
                    "alternatives": [
                        {
                            "spans": [
                                {
                                    "section_id": section["id"],
                                    "start_offset": start,
                                    "end_offset": end,
                                }
                            ]
                        }
                    ],
                }
            )
            quotes.append({"section": section, "start": start, "end": end})
        value = QuestionInput(
            text=spec["text"],
            answerable=spec["answerable"],
            reference_answer=spec["reference_answer"],
            required_facts=spec["required_facts"],
            evidence_groups=groups,
            topic=spec["topic"],
            difficulty=spec["difficulty"],
            split="unassigned",
            split_group="pg18-provisional-" + spec["candidate_id"],
            review_status="candidate",
            reviewer="",
        ).model_dump(mode="json")
        if value["answerable"] and len(groups) != len(value["required_facts"]):
            raise ValueError("Every proposed fact needs one source-linked evidence group")
        values.append(value)
        resolved.append(quotes)
    existing = {normalized_question(q["content"]["text"]): q for q in before}
    pending = []
    for value in values:
        previous = existing.get(normalized_question(value["text"]))
        if previous:
            if previous["content"] != value:
                raise ValueError(
                    "Similar existing question has different content; reconcile manually"
                )
        else:
            pending.append(value)
    if pending:
        request(
            path + "/import",
            file=("candidates.jsonl", "\n".join(json.dumps(q) for q in pending).encode()),
        )
    after = all_items(path + "/questions")
    by_id = {q["id"]: q for q in after}
    if any(by_id.get(q["id"]) != q for q in before):
        raise ValueError("An existing question changed during import; inspect concurrent edits")
    by_text = {normalized_question(q["content"]["text"]): q for q in after}
    ids = [by_text[normalized_question(v["text"])]["id"] for v in values]
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(
        json.dumps(
            {
                "dataset_id": str(args.dataset_id),
                "batch_sha256": batch_hash,
                "corpus_manifest_hash": binding["corpus_manifest_hash"],
                "question_ids": ids,
                "records": [
                    {"candidate": s, "question_id": qid, "resolved_evidence": evidence}
                    for s, qid, evidence in zip(specs, ids, resolved, strict=True)
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "imported": len(pending),
                "existing_questions_unchanged": len(before),
                "batch_question_ids": ids,
            }
        )
    )


if __name__ == "__main__":
    main()
