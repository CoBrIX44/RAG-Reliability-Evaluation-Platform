"""Hand-computed rubric examples; judgments are synthetic, never research labels."""

import hashlib
import json
from pathlib import Path
from threading import Event
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError
from rag_core.answer_evaluation import ClaimJudgment, Judgment, score_judgment
from rag_core.errors import LostLease, PlatformError
from rag_core.judge import JudgeRequest, judge_contract, judge_output, run_judge_child
from rag_core.settings import Settings


def inputs(answer: str = "A is true [P1]. B is false [P99].") -> dict[str, object]:
    return {
        "answer": answer,
        "answerable": True,
        "required_facts": ["A", "B"],
        "evidence": [{"citation": "P1", "text": "A is true."}],
    }


def judgment() -> Judgment:
    return Judgment(
        facts=["covered", "missing"],
        claims=[
            ClaimJudgment(
                text="A is true", support="supported", citations=["P1"], citations_supported=True
            ),
            ClaimJudgment(
                text="B is false", support="uncertain", citations=["P99"], citations_supported=False
            ),
        ],
        no_factual_claims=False,
        rationale="Synthetic mixed-support fixture.",
    )


def test_hand_calculated_fact_claim_and_citation_denominators() -> None:
    result = score_judgment(judgment(), inputs())
    assert result["answer_correctness"] == {
        "value": 0.5,
        "numerator": 1,
        "denominator": 2,
        "state": "scored",
        "reason": None,
    }
    assert result["faithfulness"] == result["citation_support"] == result["answer_correctness"]
    assert result["abstention_quality"]["value"] == 1  # type: ignore[index]


def test_contradiction_overrides_covered_fact_credit() -> None:
    value = judgment().model_copy(update={"facts": ["covered", "contradicted"]})
    assert score_judgment(value, inputs())["answer_correctness"]["value"] == 0  # type: ignore[index]


def test_unknown_and_missing_citations_never_receive_credit() -> None:
    value = judgment()
    for claim in value.claims:
        claim.support, claim.citations_supported = "supported", True
    result = score_judgment(value, inputs())
    assert result["faithfulness"]["value"] == 1  # type: ignore[index]
    assert result["citation_support"]["value"] == 0.5  # type: ignore[index]
    value.claims[0].citations = []
    assert score_judgment(value, inputs())["citation_support"]["value"] == 0  # type: ignore[index]


@pytest.mark.parametrize("answerable, expected", [(True, 0), (False, 1)])
def test_exact_abstention_has_no_claim_denominator(answerable: bool, expected: int) -> None:
    data = inputs("INSUFFICIENT_EVIDENCE") | {
        "answerable": answerable,
        "required_facts": ["A"] if answerable else [],
    }
    value = Judgment(
        facts=["missing"] if answerable else [],
        claims=[],
        no_factual_claims=True,
        rationale="Synthetic abstention.",
    )
    result = score_judgment(value, data)
    assert result["faithfulness"]["value"] is None  # type: ignore[index]
    assert result["citation_support"]["denominator"] is None  # type: ignore[index]
    assert result["abstention_quality"]["value"] == expected  # type: ignore[index]
    assert result["answer_correctness"]["value"] == (0 if answerable else None)  # type: ignore[index]


def test_nonfactual_nonabstention_is_unavailable_not_zero_faithfulness() -> None:
    value = Judgment(
        facts=["missing", "missing"],
        claims=[],
        no_factual_claims=True,
        rationale="Synthetic greeting without factual claims.",
    )
    assert score_judgment(value, inputs("Hello!"))["faithfulness"]["value"] is None  # type: ignore[index]


@pytest.mark.parametrize(
    "change",
    [
        {"facts": []},
        {"no_factual_claims": True},
        {
            "claims": [
                {
                    "text": "Not in the answer",
                    "support": "supported",
                    "citations": [],
                    "citations_supported": False,
                }
            ]
        },
    ],
)
def test_invalid_annotation_shape_or_invented_claim_is_rejected(change: dict[str, object]) -> None:
    value = Judgment.model_validate(judgment().model_dump() | change)
    with pytest.raises(PlatformError):
        score_judgment(value, inputs())


def test_judge_requires_exact_json_contract_eos_and_retains_failed_raw_output() -> None:
    prompt = "Synthetic judge prompt"
    raw: dict[str, object] = {
        "answer": judgment().model_dump_json(),
        "prompt": prompt,
        "prompt_hash": hashlib.sha256(prompt.encode()).hexdigest(),
        "contract": judge_contract(),
        "finish_reason": "eos",
    }
    assert "judgment" in judge_output(raw, inputs())
    changes: tuple[dict[str, object], ...] = (
        {"answer": "```json\n{}\n```"},
        {"finish_reason": "length"},
        {"contract": {}},
        {"answer": json.dumps({"facts": []})},
    )
    for change in changes:
        output = judge_output(raw | change, inputs())
        assert output["error_code"] == "judge_invalid_output"
        assert output["raw"] == raw | change
        assert "metrics" not in output


def test_judge_does_not_coerce_strings_to_boolean() -> None:
    with pytest.raises(ValidationError):
        Judgment.model_validate(judgment().model_dump() | {"no_factual_claims": "false"})


@pytest.mark.parametrize("interrupted", [False, True])
def test_judge_child_timeout_stop_cleanup_and_secret_isolation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    interrupted: bool,
) -> None:
    child = MagicMock()
    child.poll.return_value = None
    launch = MagicMock(return_value=child)
    monkeypatch.setattr("rag_core.judge.subprocess.Popen", launch)
    ticks = iter([0.0, 2.0])
    monkeypatch.setattr("rag_core.judge.time.monotonic", lambda: next(ticks))
    monkeypatch.setenv("JUDGE_API_KEY", "must-not-enter-child")
    monkeypatch.setenv("HF_TOKEN", "must-not-enter-child")
    stop = Event()
    if interrupted:
        stop.set()
    with pytest.raises(LostLease if interrupted else PlatformError):
        run_judge_child(
            JudgeRequest(inputs=inputs()),
            Settings(_env_file=None, artifact_root=tmp_path, generation_timeout_seconds=1),
            stop,
            Event(),
        )
    child.kill.assert_called_once()
    child.wait.assert_called_once()
    assert "JUDGE_API_KEY" not in launch.call_args.kwargs["env"]
    assert "HF_TOKEN" not in launch.call_args.kwargs["env"]
    assert list(tmp_path.iterdir()) == []
