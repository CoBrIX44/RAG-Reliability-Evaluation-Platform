"""Bounded development-only experiment preparation, independent of HTTP submission."""

from typing import Any

from rag_core.runs import ExperimentCreate, digest


def development_cells(
    plan: dict[str, Any], dataset: dict[str, Any], indexes: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """No test configuration path exists here; qualification uses one greedy repeat."""
    if (
        plan["dataset_version_id"] != dataset["id"]
        or plan["dataset_manifest_hash"] != dataset["manifest_hash"]
        or plan["corpus_version_id"] != dataset["corpus_version_id"]
        or dataset["manifest"]["purpose"] != "research"
        or digest(dataset["manifest"]) != dataset["manifest_hash"]
    ):
        raise ValueError("Published research dataset lineage differs from the plan")
    questions = dataset["manifest"]["questions"]
    if (
        len(questions) != 150
        or sum(q["content"]["split"] == "development" for q in questions) != 105
    ):
        raise ValueError("Use the frozen150-question dataset with105 development questions")
    if any(q["content"]["review_status"] != "reviewed" for q in questions):
        raise ValueError("All frozen gold requires recorded source review")
    if len(plan["chunking"]) != 2 or len(plan["retrieval"]) != 4:
        raise ValueError("Qualification is bounded to the planned eight cells")
    cells = []
    for chunking in plan["chunking"]:
        for retrieval in plan["retrieval"]:
            strategy = chunking["strategy"]
            label = retrieval["label"]
            expected_method = (
                "postgresql-fts-english-ts-rank-cd-v1"
                if retrieval["index_retrieval"] == "lexical"
                else "pgvector-exact-cosine-v1"
            )
            matches = [
                index
                for index in indexes
                if index["config"]["chunking"] == chunking
                and index["config"]["retrieval"] == expected_method
                and index["corpus_version_id"] == plan["corpus_version_id"]
            ]
            if len(matches) != 1 or matches[0]["state"] != "ready":
                raise ValueError("Every cell requires exactly one compatible ready index")
            index = matches[0]
            if (
                index["manifest"].get("corpus_hash") != dataset["manifest"]["corpus_manifest_hash"]
                or index["manifest"].get("config") != index["config"]
            ):
                raise ValueError("Ready index manifest differs from its corpus or configuration")
            settings = dict(plan["controlled_run_settings"])
            settings["repeats"] = 1
            value = ExperimentCreate(
                name=f"PG18 development qualification: {strategy}/{label}",
                dataset_version_id=dataset["id"],
                index_id=index["id"],
                split="development",
                retrieval_strategy=retrieval["retrieval_strategy"],
                measurement_notes=(
                    "Development qualification; one greedy repeat, not the planned final three. "
                    "Uncontrolled OS/model cache; fresh model child per call. "
                    "No independent human answer-quality assessment."
                ),
                **settings,
            )
            cells.append(
                {
                    "cell": f"{strategy}/{label}",
                    "request": value.model_dump(mode="json"),
                    "index_manifest_sha256": digest(index["manifest"]),
                    "expected_observations": 105,
                }
            )
    if len({cell["cell"] for cell in cells}) != 8:
        raise ValueError("Duplicate matrix cell labels")
    return cells
