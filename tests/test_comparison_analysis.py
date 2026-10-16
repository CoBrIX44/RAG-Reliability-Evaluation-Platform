"""Independent synthetic examples for paired means, cluster resampling and missing data."""

from threading import Event
from typing import Any

import pytest
from pydantic import ValidationError
from rag_core.comparison_analysis import (
    Datum,
    FrozenQuestion,
    Observation,
    RunSample,
    analyze,
    quantile,
    timing_summary,
)
from rag_core.comparison_snapshot import usage
from rag_core.comparisons import ComparisonCreate
from rag_core.errors import LostLease


def sample(values: list[list[float]], groups: list[str] | None = None) -> RunSample:
    questions = [
        FrozenQuestion(
            id=str(i),
            revision=1,
            content_hash=str(i),
            text=f"Synthetic {i}",
            group=(groups or [str(j) for j in range(len(values))])[i],
            answerable=True,
        )
        for i in range(len(values))
    ]
    return RunSample(
        id="synthetic",
        manifest_hash="fixture",
        state="completed",
        purpose="development_fixture",
        corpus_hash="corpus",
        dataset_hash="dataset",
        config={"repeats": len(values[0]), "split": "test"},
        execution={},
        questions=questions,
        observations=[
            Observation(
                result_id=f"{i}:{repeat}",
                question_id=str(i),
                repeat=repeat,
                state="succeeded",
                metrics={
                    "answer_correctness": Datum(state="scored", value=value, policy_hash="rubric")
                },
            )
            for i, repeats in enumerate(values)
            for repeat, value in enumerate(repeats)
        ],
        accounting={},
    )


def report(a: RunSample, b: RunSample, exploratory: bool = False) -> dict[str, Any]:
    result = analyze(
        a, b, exploratory=exploratory, seed=42, resamples=1000, stop=Event(), lost=Event()
    )
    return dict(result["metrics"]["answer_correctness"])


def test_repeats_are_question_means_not_independent_samples() -> None:
    a, b = sample([[0, 0], [0, 0]]), sample([[0, 1], [1, 1]])
    r = report(a, b)
    assert r["paired_question_count"] == r["group_count"] == 2
    assert r["difference"] == 0.75
    assert r["interval"]["low"] == 0.5 and r["interval"]["high"] == 1
    assert r == report(a, b)


def test_whole_unequal_groups_are_resampled_with_question_weighted_estimator() -> None:
    a = sample([[0], [0], [0]], ["shared", "shared", "other"])
    b = sample([[0], [0], [1]], ["shared", "shared", "other"])
    r = report(a, b)
    assert r["paired_question_count"] == 3 and r["group_count"] == 2
    assert r["difference"] == pytest.approx(1 / 3)
    assert r["interval"]["low"] == 0 and r["interval"]["high"] == 1


def test_single_group_never_gets_a_fabricated_interval() -> None:
    r = report(sample([[0], [0]], ["same", "same"]), sample([[1], [1]], ["same", "same"]))
    assert r["difference"] == 1 and r["interval"] is None and r["group_count"] == 1


def test_missing_repeat_excludes_whole_question_and_blocks_strict_analysis() -> None:
    a, b = sample([[0, 0], [0, 0]]), sample([[1, 1], [1, 1]])
    b.observations.pop()
    r = report(a, b)
    assert r["paired_question_count"] == 1 and r["state"] == "blocked"
    assert r["candidate_coverage"]["unavailable_count"] == 1
    assert r["interval"] is None
    assert report(a, b, True)["state"] == "scored"


def test_missing_scores_not_zero_and_scoring_policy_mismatch_is_excluded() -> None:
    a, b = sample([[0], [0]]), sample([[1], [1]])
    b.observations[0].metrics["answer_correctness"] = Datum(state="error")
    b.observations[1].metrics["answer_correctness"].policy_hash = "different"
    r = report(a, b)
    assert r["difference"] is None and r["paired_question_count"] == 0
    assert r["candidate_coverage"]["error_count"] == 1
    assert r["exclusion_counts"]["scoring_policy_mismatch"] == 1


def test_controls_partial_runs_and_exploratory_override() -> None:
    a, b = sample([[0], [0]]), sample([[1], [1]])
    b.config["context_tokens"] = 99
    b.state = "cancelled"
    assert report(a, b)["state"] == "blocked"
    assert report(a, b, True)["interval"] is not None


def test_question_revision_group_or_content_mismatch_never_pairs() -> None:
    a, b = sample([[0], [0]]), sample([[1], [1]])
    b.questions[0].content_hash = "changed"
    b.questions[1].group = "changed"
    assert report(a, b, True)["paired_question_count"] == 0


def test_mixed_scoring_revisions_across_questions_block_even_exploratory_intervals() -> None:
    a, b = sample([[0], [0]]), sample([[1], [1]])
    for run in (a, b):
        run.observations[1].metrics["answer_correctness"].policy_hash = "another-rubric"
    r = report(a, b, True)
    assert r["state"] == "blocked" and r["interval"] is None
    assert r["scoring_policy_count"] == 2


def test_shutdown_stops_bootstrap_and_quantiles_never_invent_empty_measurements() -> None:
    stop = Event()
    stop.set()
    with pytest.raises(LostLease):
        analyze(
            sample([[0]]),
            sample([[1]]),
            exploratory=False,
            seed=0,
            resamples=200,
            stop=stop,
            lost=Event(),
        )
    assert quantile([], 0.5) is None and quantile([10], 0.95) == 10
    assert quantile([10, 20, 30, 40], 0.95) == pytest.approx(38.5)
    assert timing_summary([10, float("nan"), -1], 3)["unavailable_count"] == 2


def test_usage_preserves_unknown_tokens_and_counts_incomplete_calls() -> None:
    assert usage([], 1)["input_tokens"] is None
    assert usage([{"input_tokens": 5, "output_tokens": 2}, None], 1) == {
        "recorded_call_count": 1,
        "input_tokens": 5,
        "output_tokens": 2,
        "potential_unobserved_call_count": 2,
        "policy": "available-attempt-usage-no-inferred-zero-v1",
    }


@pytest.mark.parametrize("change", [{"resamples": 100000}, {"seed": -1}])
def test_resource_bounds(change: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        ComparisonCreate.model_validate(
            {"name": "Synthetic", "baseline_run_id": "1" * 32, "candidate_run_id": "2" * 32}
            | change
        )
