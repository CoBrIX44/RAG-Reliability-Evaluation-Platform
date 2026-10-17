"""Prepare four frozen-corpus indexes through the durable worker; never submit answer runs."""

import argparse
import json
import time
from pathlib import Path

from import_benchmark import all_items, request
from rag_core.indexes import IndexCreate


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    args = parser.parse_args()
    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    binding = json.loads((args.source / "workspace-binding.json").read_text(encoding="utf-8"))
    if plan["corpus_version_id"] != binding["corpus_version_id"] or len(plan["chunking"]) != 2:
        raise ValueError("Use the bounded two-strategy proposal and its acquired corpus")
    versions = all_items(f"/corpora/{binding['corpus_id']}/versions")
    version = next(v for v in versions if v["id"] == binding["corpus_version_id"])
    if version["manifest_hash"] != binding["corpus_manifest_hash"]:
        raise ValueError("Published corpus differs from acquisition binding")
    selected = []
    for chunking in plan["chunking"]:
        for retrieval in ["lexical", "dense"]:
            value = IndexCreate(
                corpus_version_id=plan["corpus_version_id"], chunking=chunking, retrieval=retrieval
            )
            saved = request("/indexes", value.model_dump(mode="json"))
            selected.append(
                {"chunking": chunking["strategy"], "retrieval": retrieval, "id": saved["id"]}
            )
    deadline, states = time.monotonic() + 1200, {}
    while True:
        records = []
        for selected_index in selected:
            saved = request("/indexes/" + selected_index["id"])
            records.append(saved)
            if states.get(saved["id"]) != saved["state"]:
                print(
                    json.dumps(
                        {**selected_index, "state": saved["state"], "chunks": saved["chunk_count"]}
                    ),
                    flush=True,
                )
                states[saved["id"]] = saved["state"]
            if saved["state"] == "failed":
                raise ValueError(f"Index build failed: {saved['error_code']}")
        if all(row["state"] == "ready" for row in records):
            break
        if time.monotonic() >= deadline:
            raise TimeoutError("Durable index work is still queued; rerun to resume polling")
        time.sleep(2)
    result = {
        "corpus_manifest_hash": binding["corpus_manifest_hash"],
        "selections": selected,
        "indexes": records,
        "answer_runs_submitted": 0,
    }
    (args.source / "index-preparation.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    print("All four indexes ready; hybrid and reranking reuse each dense index.", flush=True)


if __name__ == "__main__":
    main()
