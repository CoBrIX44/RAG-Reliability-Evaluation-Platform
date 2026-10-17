"""Synthetic operator fixtures; never benchmark observations or gold labels."""

from copy import deepcopy
from typing import Any
from uuid import uuid4

import pytest
from rag_core.benchmark_execution import development_cells
from rag_core.runs import digest


def fixture() -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    corpus_id, dataset_id = str(uuid4()), str(uuid4())
    plan: dict[str, Any] = {
        "corpus_version_id": corpus_id,
        "dataset_version_id": dataset_id,
        "dataset_manifest_hash": "synthetic-dataset-hash",
        "chunking": [
            {"strategy": strategy, "max_tokens": 240, "overlap_tokens": 32}
            for strategy in ["fixed", "section"]
        ],
        "retrieval": [
            {"label": "lexical", "index_retrieval": "lexical", "retrieval_strategy": "index"},
            {"label": "dense", "index_retrieval": "dense", "retrieval_strategy": "index"},
            {"label": "hybrid", "index_retrieval": "dense", "retrieval_strategy": "hybrid"},
            {
                "label": "hybrid_rerank",
                "index_retrieval": "dense",
                "retrieval_strategy": "hybrid_rerank",
            },
        ],
        "controlled_run_settings": {
            "top_k": 5,
            "context_tokens": 1024,
            "max_new_tokens": 128,
            "repeats": 3,
            "seed": 0,
            "candidate_k": 20,
            "rrf_k": 60,
            "cache_condition": "uncontrolled",
        },
    }
    dataset = {
        "id": dataset_id,
        "corpus_version_id": corpus_id,
        "manifest_hash": "synthetic-dataset-hash",
        "manifest": {
            "purpose": "research",
            "corpus_manifest_hash": "synthetic-corpus-hash",
            "questions": [
                {
                    "content": {
                        "split": "development" if i < 105 else "test",
                        "review_status": "reviewed",
                    }
                }
                for i in range(150)
            ],
        },
    }
    indexes = [
        {
            "id": str(uuid4()),
            "corpus_version_id": corpus_id,
            "state": "ready",
            "config": {"chunking": chunking, "retrieval": method},
            "manifest": {
                "config": {"chunking": chunking, "retrieval": method},
                "corpus_hash": "synthetic-corpus-hash",
            },
        }
        for chunking in plan["chunking"]
        for method in ["postgresql-fts-english-ts-rank-cd-v1", "pgvector-exact-cosine-v1"]
    ]
    dataset["manifest_hash"] = digest(dataset["manifest"])
    plan["dataset_manifest_hash"] = dataset["manifest_hash"]
    return plan, dataset, indexes


def test_development_matrix_uses_only_development_and_reuses_dense_universe() -> None:
    plan, dataset, indexes = fixture()
    original = deepcopy(plan)
    cells = development_cells(plan, dataset, indexes)
    assert len(cells) == 8
    assert {c["request"]["split"] for c in cells} == {"development"}
    assert {c["request"]["repeats"] for c in cells} == {1}
    assert sum(c["expected_observations"] for c in cells) == 840
    assert plan == original  # Qualification must not rewrite the final three-repeat proposal.
    by_cell = {c["cell"]: c["request"] for c in cells}
    for strategy in ["fixed", "section"]:
        assert (
            len(
                {
                    by_cell[f"{strategy}/{method}"]["index_id"]
                    for method in ["dense", "hybrid", "hybrid_rerank"]
                }
            )
            == 1
        )
        assert (
            by_cell[f"{strategy}/lexical"]["index_id"] != by_cell[f"{strategy}/dense"]["index_id"]
        )


@pytest.mark.parametrize(
    "case",
    [
        "hash",
        "corpus",
        "purpose",
        "split",
        "review",
        "index",
        "duplicate",
        "capacity",
        "index_manifest",
    ],
)
def test_development_preparation_rejects_changed_inputs(case: str) -> None:
    plan, dataset, indexes = fixture()
    if case == "hash":
        dataset["manifest_hash"] = "changed"
    elif case == "corpus":
        dataset["corpus_version_id"] = str(uuid4())
    elif case == "purpose":
        dataset["manifest"]["purpose"] = "development_fixture"
    elif case == "split":
        dataset["manifest"]["questions"][0]["content"]["split"] = "test"
    elif case == "review":
        dataset["manifest"]["questions"][0]["content"]["review_status"] = "candidate"
    elif case == "index":
        indexes[0]["state"] = "failed"
    elif case == "duplicate":
        indexes.append(deepcopy(indexes[0]))
    elif case == "capacity":
        plan["chunking"].append(deepcopy(plan["chunking"][0]))
    elif case == "index_manifest":
        indexes[0]["manifest"]["corpus_hash"] = "different-corpus"
    with pytest.raises(ValueError):
        development_cells(plan, dataset, indexes)
