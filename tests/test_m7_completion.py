"""Synthetic phase-gate/checksum fixtures; these never stand in for research results."""

import hashlib
import importlib.util
import io
import json
import urllib.error
from copy import deepcopy
from email.message import Message
from pathlib import Path
from types import ModuleType
from typing import Any
from uuid import uuid4
from zipfile import ZipFile

import pytest


@pytest.fixture
def controller() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "completion_operator_fixture",
        Path(__file__).resolve().parents[1] / "scripts/complete_m7.py",
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def inputs() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    cells = [
        f"{s}/{m}"
        for s in ["fixed", "section"]
        for m in ["lexical", "dense", "hybrid", "hybrid_rerank"]
    ]
    dataset_id = str(uuid4())
    questions = [
        {"id": str(uuid4()), "revision": 2, "content": {"split": "development"}} for _ in range(105)
    ]
    definition = {
        "cells": [
            {
                "cell": c,
                "request": {
                    "dataset_version_id": dataset_id,
                    "index_id": "synthetic-index-" + c,
                    "split": "development",
                    "repeats": 1,
                },
            }
            for c in cells
        ],
        "dataset_version_id": dataset_id,
        "dataset_manifest_hash": "synthetic",
    }
    runs = {
        c: {"state": "completed", "completed_count": 105, "failed_count": 0, "total_count": 105}
        for c in cells
    }
    manifests = {
        c: {
            "dataset_version_id": dataset_id,
            "index_id": "synthetic-index-" + c,
            "dataset_hash": "synthetic",
            "config": {"split": "development", "repeats": 1},
            "questions": deepcopy(questions),
            "execution": {"synthetic": True},
        }
        for c in cells
    }
    return definition, runs, manifests


@pytest.mark.parametrize("field", ["index_id", "top_k", "context_tokens", "measurement_notes"])
def test_exact_development_controls_cannot_drift(controller: ModuleType, field: str) -> None:
    definition, runs, manifests = inputs()
    target = definition["cells"][0]
    target["request"][field] = "frozen-fixture"
    with pytest.raises(ValueError, match="exact prepared request"):
        controller.qualify(definition, runs, manifests)


def test_transient_api_failure_retries_boundedly_and_recovery_clears_error(
    controller: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    state: dict[str, Any] = {}

    def unavailable(_: Any) -> str:
        raise urllib.error.URLError("synthetic connection refusal")

    monkeypatch.setattr(controller, "step", unavailable)
    for _ in range(4):
        controller.advance(state)
        assert state["phase"] == "waiting_for_api"
    controller.advance(state)
    assert state["phase"] == "requires_attention"
    assert state["consecutive_api_errors"] == 5
    monkeypatch.setattr(controller, "step", lambda _: "waiting_for_development")
    controller.advance(state)
    assert state["phase"] == "waiting_for_development"
    assert "last_error" not in state and "consecutive_api_errors" not in state


@pytest.mark.parametrize(
    "error",
    [
        ValueError("changed lineage"),
        urllib.error.HTTPError("http://fixture", 422, "invalid request", Message(), None),
    ],
)
def test_invalid_data_or_request_never_becomes_transient_retry(
    controller: ModuleType, monkeypatch: pytest.MonkeyPatch, error: Exception
) -> None:
    def invalid(_: Any) -> str:
        raise error

    state: dict[str, Any] = {}
    monkeypatch.setattr(controller, "step", invalid)
    controller.advance(state)
    assert state["phase"] == "requires_attention"


def test_complete_development_qualifies_but_running_or_failed_never_freezes(
    controller: ModuleType,
) -> None:
    definition, runs, manifests = inputs()
    assert controller.qualify(definition, runs, manifests) == "qualified"
    runs["section/dense"]["state"] = "running"
    runs["section/dense"]["completed_count"] = 20
    assert controller.qualify(definition, runs, manifests) == "waiting_for_development"
    runs["section/dense"].update(state="completed_with_errors", failed_count=1, completed_count=104)
    assert controller.qualify(definition, runs, manifests) == "development_requires_attention"


@pytest.mark.parametrize("field", ["dataset", "split", "repeat", "execution", "question_revision"])
def test_changed_development_controls_rejected(controller: ModuleType, field: str) -> None:
    definition, runs, manifests = inputs()
    m = manifests["section/dense"]
    if field == "dataset":
        m["dataset_hash"] = "changed"
    elif field == "split":
        m["questions"][0]["content"]["split"] = "test"
    elif field == "repeat":
        m["config"]["repeats"] = 3
    elif field == "execution":
        m["execution"]["synthetic"] = False
    elif field == "question_revision":
        m["questions"][0]["revision"] += 1
    with pytest.raises(ValueError):
        controller.qualify(definition, runs, manifests)


def test_waiting_step_cannot_submit_test_jobs(
    controller: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    definition, runs, manifests = inputs()
    runs["section/dense"].update(state="running", completed_count=10)
    monkeypatch.setattr(controller, "read", lambda _: {"definition": definition, "submissions": {}})
    monkeypatch.setattr(controller, "snapshot_runs", lambda _: (runs, manifests))

    def forbidden(*args: Any) -> None:
        raise AssertionError("Held-out job was submitted before qualification")

    monkeypatch.setattr(controller, "submit_tests", forbidden)
    assert controller.step({}) == "waiting_for_development"


def test_heldout_requests_change_only_stage_controls(controller: ModuleType) -> None:
    definition, _, _ = inputs()
    for cell in definition["cells"]:
        cell["request"] = {
            "name": "Synthetic development",
            "dataset_version_id": str(uuid4()),
            "index_id": str(uuid4()),
            "split": "development",
            "repeats": 1,
            "top_k": 5,
            "context_tokens": 1024,
            "max_new_tokens": 128,
            "seed": 0,
            "candidate_k": 20,
            "rrf_k": 60,
            "cache_condition": "uncontrolled",
            "retrieval_strategy": "index",
        }
    before = deepcopy(definition)
    result = controller.heldout_requests(definition)
    assert definition == before
    assert len(result) == 8
    for original, heldout in zip(definition["cells"], result, strict=True):
        assert heldout["request"]["split"] == "test"
        assert heldout["request"]["repeats"] == 3
        for key in ["index_id", "dataset_version_id", "top_k", "context_tokens", "max_new_tokens"]:
            assert heldout["request"][key] == original["request"][key]


def test_heldout_manifest_rejects_foreign_questions_or_runtime(controller: ModuleType) -> None:
    ids = [str(uuid4()) for _ in range(45)]
    locked = {
        "test_question_ids": ids,
        "dataset_manifest_hash": "fixture",
        "execution_sha256": controller.digest({"fixture": True}),
    }
    manifest: dict[str, Any] = {
        "dataset_hash": "fixture",
        "execution": {"fixture": True},
        "config": {"split": "test", "repeats": 3},
        "questions": [{"id": qid, "content": {"split": "test"}} for qid in ids],
    }
    controller.verify_terminal({"total_count": 135}, manifest, locked)
    manifest["questions"][0]["content"]["split"] = "development"
    with pytest.raises(ValueError):
        controller.verify_terminal({"total_count": 135}, manifest, locked)
    manifest["questions"][0]["content"]["split"] = "test"
    manifest["execution"]["fixture"] = False
    with pytest.raises(ValueError):
        controller.verify_terminal({"total_count": 135}, manifest, locked)


def test_holdout_selection_stays_locked_and_review_sampling_ignores_answers(
    controller: ModuleType,
) -> None:
    questions = [
        {"id": f"{topic}-{i}", "content": {"topic": topic, "answerable": i != 0}}
        for topic in ["a", "b", "c", "d", "e"]
        for i in range(9)
    ]
    chosen = controller.select_review_questions(questions)
    assert len(chosen) == 15
    assert chosen == controller.select_review_questions(list(reversed(questions)))
    assert all(f"{topic}-0" in chosen for topic in ["a", "b", "c", "d", "e"])
    assert controller.key_for("test", {"a": 1, "b": 2}) == controller.key_for(
        "test", {"b": 2, "a": 1}
    )
    assert controller.key_for("test", {"a": 1}) != controller.key_for("export", {"a": 1})


@pytest.mark.parametrize("tampered", [False, True])
def test_evidence_zip_requires_inner_hashes_as_well_as_outer_hash(
    controller: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, tampered: bool
) -> None:
    stream = io.BytesIO()
    with ZipFile(stream, "w") as z:
        z.writestr("fact.txt", b"changed" if tampered else b"fixture")
        z.writestr(
            "checksums.json", json.dumps({"fact.txt": hashlib.sha256(b"fixture").hexdigest()})
        )
    raw = stream.getvalue()
    job = {
        "id": "synthetic-export",
        "output": {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)},
    }
    monkeypatch.setattr(controller, "WORK", tmp_path)
    monkeypatch.setattr(controller.urllib.request, "urlopen", lambda *a, **k: io.BytesIO(raw))
    if tampered:
        with pytest.raises(ValueError, match="member checksum"):
            controller.download_export(job)
        assert not (tmp_path / "evidence/synthetic-export.zip").exists()
    else:
        controller.download_export(job)
        assert (tmp_path / "evidence/synthetic-export.zip").read_bytes() == raw


def test_report_preserves_missing_metrics_and_dictionary_interval_units(
    controller: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    (tmp_path / "research/postgresql-18.0").mkdir(parents=True)
    monkeypatch.setattr(controller, "ROOT", tmp_path)
    runs = {
        "synthetic": {
            "state": "completed",
            "completed_count": 135,
            "failed_count": 0,
            "total_count": 135,
            "metrics": {
                "retrieval_recall": {"mean": None, "scored_count": 0, "applicable_count": 102}
            },
        }
    }
    comparisons = {
        "synthetic pair": {
            "id": "synthetic-report",
            "state": "completed",
            "output": {
                "accounting": {
                    "baseline": {
                        "stage_timings": {
                            "question_wall_ms": {
                                "p50": 1500,
                                "p95": None,
                                "scored_count": 2,
                                "unavailable_count": 1,
                            }
                        }
                    }
                },
                "metrics": {
                    "retrieval_recall": {
                        "difference": 0.25,
                        "interval": {"low": -0.1, "high": 0.4},
                        "paired_question_count": 10,
                        "group_count": 3,
                    },
                    "answer_correctness": {"difference": None, "interval": None},
                },
            },
        }
    }
    controller.report(runs, comparisons)
    text = (tmp_path / "research/postgresql-18.0/BENCHMARK_REPORT.md").read_text(encoding="utf-8")
    assert "25.00" in text and "-10.00 to 40.00" in text
    assert "| answer_correctness | unavailable | unavailable |" in text
    assert "**not established**" in text
    assert "question_wall_ms | 1.50 | unavailable | 2/1 |" in text


@pytest.mark.parametrize(
    "problem", [None, "missing_run", "failed_run", "short_run", "failed_analysis", "no_scope"]
)
def test_exploratory_delivery_requires_actual_execution_and_explicit_scope(
    controller: ModuleType, problem: str | None
) -> None:
    scope = {
        "schema": "m7-delivery-scope-v1",
        "mode": "exploratory_retrieval",
        "authorization": "Deliver an exploratory report with answer quality unvalidated",
        "answer_quality": "unvalidated",
        "human_calibration": "not_performed",
        "primary_factual_accuracy_hypothesis": "not_established",
    }
    runs: dict[str, Any] = {
        str(i): {
            "state": "completed",
            "completed_count": 135,
            "total_count": 135,
            "failed_count": 0,
            "cancelled_count": 0,
        }
        for i in range(8)
    }
    comparisons = {str(i): {"state": "completed"} for i in range(8)}
    if problem == "missing_run":
        runs.pop("0")
    elif problem == "failed_run":
        runs["0"].update(state="completed_with_errors", failed_count=1)
    elif problem == "short_run":
        runs["0"]["completed_count"] = 134
    elif problem == "failed_analysis":
        comparisons["0"]["state"] = "failed"
    elif problem == "no_scope":
        scope.clear()
    policy = controller.completion_policy(runs, comparisons, scope)
    assert policy["m7_complete"] is (problem is None)
    assert policy["answer_quality"] == "unvalidated"
    assert policy["human_calibration"] == "not_performed"
    assert policy["primary_factual_accuracy_hypothesis"] == "not_established"


def test_final_handoff_requires_completion_and_preserves_existing_notes(
    controller: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(controller, "ROOT", tmp_path)
    for name in ["TASKS.md", "CODEX_HANDOFF.md", "AGENTS.md"]:
        (tmp_path / name).write_text("Existing owner notes\n", encoding="utf-8")
    delivery = {
        "completed_at": "synthetic-time",
        "m7_complete": False,
        "restore_status": "passed",
        "execution_complete": True,
        "analysis_complete": True,
    }
    with pytest.raises(ValueError):
        controller.finish_handoff(delivery)
    assert (tmp_path / "TASKS.md").read_text(encoding="utf-8") == "Existing owner notes\n"
    delivery["m7_complete"] = True
    controller.finish_handoff(delivery)
    before = (tmp_path / "CODEX_HANDOFF.md").read_text(encoding="utf-8")
    controller.finish_handoff(delivery)
    assert (tmp_path / "CODEX_HANDOFF.md").read_text(encoding="utf-8") == before
    assert before.startswith("Existing owner notes\n")
    assert "Answer quality is unvalidated" in before
