"""Local generation contracts and lifecycle, with no network or model inference."""

import hashlib
from pathlib import Path
from threading import Event
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError
from rag_core.context import PackedContext
from rag_core.errors import LostLease, PlatformError
from rag_core.generation import (
    GenerationInput,
    GenerationOutput,
    citation_trace,
    generation_contract,
    run_generation_child,
)
from rag_core.settings import Settings


def output() -> GenerationOutput:
    return GenerationOutput(
        answer="INSUFFICIENT_EVIDENCE",
        context=PackedContext(
            tokenizer="software fixture",
            token_budget=0,
            token_count=0,
            text="",
            passages=[],
            truncated_chunk_ids=[],
            omitted_chunk_ids=[],
        ),
        prompt="Software fixture prompt",
        prompt_hash=hashlib.sha256(b"Software fixture prompt").hexdigest(),
        input_tokens=10,
        output_tokens=2,
        finish_reason="eos",
        abstained=True,
        citations=[],
        unknown_citations=[],
        metadata={"contract": generation_contract()},
    )


def test_citations_are_syntactic_references_not_support_scores() -> None:
    assert citation_trace("Claim [P1] [P1] [P99] [P0]", 2) == (["P1"], ["P0", "P99"])


def test_model_contract_prompt_and_abstention_are_validated() -> None:
    value = output().model_dump()
    value["prompt"] = "tampered"
    with pytest.raises(ValidationError, match="Prompt hash"):
        GenerationOutput.model_validate(value)
    value = output().model_dump()
    value["metadata"]["contract"]["revision"] = "different"
    with pytest.raises(ValidationError, match="pinned contract"):
        GenerationOutput.model_validate(value)
    value = output().model_dump()
    value["answer"] = "The evidence is insufficient."
    with pytest.raises(ValidationError, match="exact-match"):
        GenerationOutput.model_validate(value)
    value["abstained"] = False
    assert not GenerationOutput.model_validate(value).abstained


@pytest.mark.parametrize(
    "payload",
    [
        {"question": ""},
        {"question": "x", "context_tokens": 1537},
        {"question": "x", "max_new_tokens": 257},
        {"question": "x", "threads": 9},
        {"question": "x", "provider": "paid"},
    ],
)
def test_generation_bounds(payload: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        GenerationInput.model_validate(payload)


@pytest.mark.parametrize("interrupted", [False, True])
def test_generation_child_timeout_shutdown_and_secret_isolation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, interrupted: bool
) -> None:
    child = MagicMock()
    child.poll.return_value = None
    launch = MagicMock(return_value=child)
    monkeypatch.setattr("rag_core.generation.subprocess.Popen", launch)
    ticks = iter([0.0, 2.0])
    monkeypatch.setattr("rag_core.generation.time.monotonic", lambda: next(ticks))
    monkeypatch.setenv("HF_TOKEN", "must-not-enter-child")
    monkeypatch.setenv("GENERATION_API_KEY", "must-not-enter-child")
    stop = Event()
    if interrupted:
        stop.set()
    with pytest.raises(LostLease if interrupted else PlatformError):
        run_generation_child(
            GenerationInput(question="bounded"),
            Settings(_env_file=None, artifact_root=tmp_path, generation_timeout_seconds=1),
            stop,
            Event(),
        )
    child.kill.assert_called_once()
    child.wait.assert_called_once()
    assert "HF_TOKEN" not in launch.call_args.kwargs["env"]
    assert "GENERATION_API_KEY" not in launch.call_args.kwargs["env"]
    assert list(tmp_path.iterdir()) == []
