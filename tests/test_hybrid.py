"""Independently computed rank fusion fixtures; no model or benchmark data."""

from pathlib import Path
from threading import Event
from unittest.mock import MagicMock
from uuid import UUID

import pytest
from pydantic import ValidationError
from rag_core.chunking import CanonicalSpan, Chunk
from rag_core.errors import LostLease, PlatformError
from rag_core.hybrid import fuse_hits
from rag_core.indexes import SearchHit
from rag_core.reranking import RerankInput, RerankOutput, reranker_contract, run_reranker_child
from rag_core.runs import ExperimentCreate
from rag_core.settings import Settings


def hit(number: int, rank: int = 1, score: float = 0) -> SearchHit:
    chunk = Chunk(
        id=UUID(int=number),
        ordinal=number,
        text=f"Software fixture {number}",
        token_count=3,
        spans=[
            CanonicalSpan(
                section_id=UUID(int=number),
                start_offset=0,
                end_offset=len(f"Software fixture {number}"),
                text_start=0,
                text_end=len(f"Software fixture {number}"),
            )
        ],
    )
    return SearchHit(rank=rank, score=score, chunk=chunk)


def test_rrf_uses_reciprocal_ranks_and_deduplicates_each_arm() -> None:
    # A appears at rank 1 and 2: 1/61 + 1/62. B and C appear once.
    lexical = [hit(1, 1, 999), hit(2, 2, 998)]
    dense = [hit(3, 1, 0.9), hit(1, 2, -0.2)]
    result = fuse_hits(lexical + [lexical[0]], dense, 60)
    assert [h.chunk.id.int for h in result] == [1, 3, 2]
    assert [h.rank for h in result] == [1, 2, 3]
    assert [h.score for h in result] == pytest.approx([1 / 61 + 1 / 62, 1 / 61, 1 / 62])
    assert fuse_hits([], [], 60) == []


def test_fusion_stable_ties_and_conflicting_source_content() -> None:
    assert [h.chunk.id.int for h in fuse_hits([hit(3)], [hit(2)], 60)] == [2, 3]
    changed = hit(1).model_copy(
        update={"chunk": hit(1).chunk.model_copy(update={"text": "tampered"})}
    )
    with pytest.raises(PlatformError, match="content differs"):
        fuse_hits([hit(1)], [changed], 60)
    with pytest.raises(PlatformError):
        fuse_hits([], [], 0)


@pytest.mark.parametrize("scores", [[float("nan")], [float("inf")], []])
def test_reranker_output_rejects_missing_and_nonfinite_logits(scores: list[float]) -> None:
    with pytest.raises(ValidationError):
        RerankOutput(
            passage_ids=[UUID(int=1)],
            scores=scores,
            pair_tokens=[12],
            metadata={"contract": reranker_contract()},
        )


def test_reranker_contract_tokens_and_counts_fail_closed() -> None:
    output = RerankOutput(
        passage_ids=[UUID(int=1)],
        scores=[-8.5],
        pair_tokens=[512],
        metadata={"contract": reranker_contract()},
    )
    assert output.scores == [-8.5]  # Raw negative logits are valid; no fake probability transform.
    data = output.model_dump()
    data["metadata"]["contract"]["revision"] = "different"
    with pytest.raises(ValidationError, match="pinned contract"):
        RerankOutput.model_validate(data)
    updates: list[dict[str, object]] = [
        {"pair_tokens": [513]},
        {"passage_ids": [UUID(int=1), UUID(int=1)]},
        {"scores": [1, 2]},
    ]
    for update in updates:
        with pytest.raises(ValidationError):
            RerankOutput.model_validate(output.model_dump() | update)


def test_candidate_limits_input_and_configuration_validation() -> None:
    with pytest.raises(ValidationError):
        RerankInput(query="q", passages=[hit(1).chunk, hit(1).chunk])
    with pytest.raises(ValidationError):
        RerankInput(query="")
    with pytest.raises(ValidationError, match="Candidate depth"):
        ExperimentCreate(
            name="Synthetic",
            dataset_version_id=UUID(int=1),
            index_id=UUID(int=2),
            retrieval_strategy="hybrid",
            top_k=10,
            candidate_k=5,
        )
    with pytest.raises(ValidationError):
        ExperimentCreate(
            name="Synthetic",
            dataset_version_id=UUID(int=1),
            index_id=UUID(int=2),
            retrieval_strategy="hybrid",
            rrf_k=0,
        )


@pytest.mark.parametrize("interrupted", [False, True])
def test_reranker_child_is_bounded_and_does_not_inherit_secrets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, interrupted: bool
) -> None:
    child = MagicMock()
    child.poll.return_value = None
    launch = MagicMock(return_value=child)
    monkeypatch.setattr("rag_core.reranking.subprocess.Popen", launch)
    ticks = iter([0.0, 2.0])
    monkeypatch.setattr("rag_core.reranking.time.monotonic", lambda: next(ticks))
    monkeypatch.setenv("HF_TOKEN", "must-not-enter-child")
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql+psycopg://fixture:software-secret@127.0.0.1/fixture"
    )
    stop = Event()
    if interrupted:
        stop.set()
    with pytest.raises(LostLease if interrupted else PlatformError):
        run_reranker_child(
            RerankInput(query="q", passages=[hit(1).chunk]),
            Settings(_env_file=None, artifact_root=tmp_path, reranker_timeout_seconds=1),
            stop,
            Event(),
        )
    child.kill.assert_called_once()
    child.wait.assert_called_once()
    assert "HF_TOKEN" not in launch.call_args.kwargs["env"]
    assert "DATABASE_URL" not in launch.call_args.kwargs["env"]
    assert list(tmp_path.iterdir()) == []
