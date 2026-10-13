"""Embedding safety contracts; no model downloads or benchmark labels in unit tests."""

import json
from pathlib import Path
from threading import Event
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError
from rag_core import embeddings
from rag_core.embeddings import EmbeddingInput, EmbeddingOutput, embedding_contract, vector_literal
from rag_core.errors import LostLease, PlatformError
from rag_core.settings import Settings


def encoded(vectors: list[list[float]]) -> EmbeddingOutput:
    return EmbeddingOutput(
        vectors=vectors,
        metadata={
            "contract": embedding_contract(),
            "artifact_hashes": {
                name: "0" * 64
                for name in (
                    "model.safetensors",
                    "tokenizer.json",
                    "config.json",
                    "modules.json",
                    "1_Pooling/config.json",
                    "sentence_bert_config.json",
                )
            },
            "runtime": {"fixture": "hand-computed software vectors; no model inference"},
        },
    )


@pytest.mark.parametrize(
    "vector", [[1.0], [0.0] * 384, [float("nan")] * 384, [float("inf")] * 384, [1.0] * 384]
)
def test_invalid_vectors_rejected(vector: list[float]) -> None:
    with pytest.raises(PlatformError, match="vector"):
        vector_literal(vector)
    with pytest.raises(ValidationError):
        encoded([vector])


def test_contract_and_artifact_hashes_fail_closed() -> None:
    valid = encoded([[1.0] + [0.0] * 383])
    assert json.loads(vector_literal(valid.vectors[0])) == valid.vectors[0]
    data = valid.model_dump()
    data["metadata"]["contract"]["revision"] = "different"
    with pytest.raises(ValidationError, match="incompatible"):
        EmbeddingOutput.model_validate(data)
    data = valid.model_dump()
    data["metadata"]["artifact_hashes"] = {}
    with pytest.raises(ValidationError, match="artifacts"):
        EmbeddingOutput.model_validate(data)


@pytest.mark.parametrize("texts", [[], [""], ["a" * 100_001], ["a" * 100_000] * 51])
def test_input_capacity(texts: list[str]) -> None:
    with pytest.raises(ValidationError):
        EmbeddingInput(texts=texts)


@pytest.mark.parametrize("interrupted", [False, True])
def test_child_timeout_or_shutdown_kills_child_and_removes_inputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    interrupted: bool,
) -> None:
    child = MagicMock()
    child.poll.return_value = None
    launch = MagicMock(return_value=child)
    monkeypatch.setattr("rag_core.embeddings.subprocess.Popen", launch)
    ticks = iter([0.0, 2.0])
    monkeypatch.setattr("rag_core.embeddings.time.monotonic", lambda: next(ticks))
    monkeypatch.setenv("GENERATION_API_KEY", "must-not-enter-child")
    stop = Event()
    if interrupted:
        stop.set()
    with pytest.raises(LostLease if interrupted else PlatformError):
        embeddings.run_embeddings(
            ["bounded"],
            Settings(
                _env_file=None,
                artifact_root=tmp_path,
                model_timeout_seconds=1,
            ),
            stop,
            Event(),
        )
    child.kill.assert_called_once()
    child.wait.assert_called_once()
    assert "GENERATION_API_KEY" not in launch.call_args.kwargs["env"]
    assert list(tmp_path.iterdir()) == []
