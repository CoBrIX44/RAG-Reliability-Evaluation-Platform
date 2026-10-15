"""Fixed CPU cross-encoder contract. Scores are raw ranking logits, not probabilities."""

import hashlib
import importlib.metadata
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from rag_core.chunking import Chunk
from rag_core.errors import LostLease, PlatformError
from rag_core.settings import Settings

RERANKER_ID = "cross-encoder/ms-marco-MiniLM-L6-v2"
RERANKER_REVISION = "233902d25c440f23af6f7d6e94d2946bac0bee0a"
RERANKER_ARTIFACTS = {
    "model.safetensors": "821d1aa69520101d6e0737f78a042ae25b19e5cb9160701909d10434f4aeb0ae",
    "config.json": "380e02c93f431831be65d99a4e7e5f67c133985bf2e77d9d4eba46847190bacc",
    "tokenizer.json": "d241a60d5e8f04cc1b2b3e9ef7a4921b27bf526d9f6050ab90f9267a1f9e5c66",
    "tokenizer_config.json": "a5c2e5a7b1a29a0702cd28c08a399b5ecc110c263009d17f7e3b415f25905fd8",
    "special_tokens_map.json": "3c3507f36dff57bce437223db3b3081d1e2b52ec3e56ee55438193ecb2c94dd6",
    "vocab.txt": "07eced375cec144d27c900241f3e339478dec958f92fddbc551f295c992038a3",
}


def reranker_contract() -> dict[str, object]:
    return {
        "model_id": RERANKER_ID,
        "revision": RERANKER_REVISION,
        "artifact_hashes": RERANKER_ARTIFACTS.copy(),
        "backend": "torch-cpu",
        "dtype": "float32",
        "score": "raw-single-label-logit",
        "max_pair_tokens": 512,
        "truncation": "reject-overflow",
        "transformers": importlib.metadata.version("transformers"),
        "torch": importlib.metadata.version("torch"),
        "tokenizers": importlib.metadata.version("tokenizers"),
    }


class RerankInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: Literal["prepare", "score"] = "score"
    query: str = Field(default="", max_length=4000)
    passages: list[Chunk] = Field(default_factory=list, max_length=50)
    threads: int = Field(default=2, ge=1, le=8)
    batch_size: int = Field(default=8, ge=1, le=16)

    @model_validator(mode="after")
    def bounded(self) -> "RerankInput":
        if self.mode == "score" and (not self.query.strip() or not self.passages):
            raise ValueError("Scoring needs a nonempty query and passages.")
        if sum(len(chunk.text) for chunk in self.passages) > 5_000_000:
            raise ValueError("Reranking evidence exceeds the character limit.")
        if len({chunk.id for chunk in self.passages}) != len(self.passages):
            raise ValueError("Reranking passages must have distinct IDs.")
        return self


class RerankOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    passage_ids: list[UUID] = Field(min_length=1, max_length=50)
    scores: list[float] = Field(min_length=1, max_length=50)
    pair_tokens: list[int] = Field(min_length=1, max_length=50)
    metadata: dict[str, object]

    @model_validator(mode="after")
    def compatible(self) -> "RerankOutput":
        if len(self.scores) != len(self.passage_ids) or len(self.pair_tokens) != len(self.scores):
            raise ValueError("Reranking output count mismatch.")
        if len(set(self.passage_ids)) != len(self.passage_ids):
            raise ValueError("Reranking output repeats a passage.")
        if any(count < 3 or count > 512 for count in self.pair_tokens):
            raise ValueError("Reranking pair exceeds token capacity.")
        if self.metadata.get("contract") != reranker_contract():
            raise ValueError("Reranker artifacts or runtime differ from the pinned contract.")
        return self


def run_reranker_child(
    request: RerankInput, settings: Settings, stop: Event, lost: Event
) -> dict[str, object]:
    settings.artifact_root.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="reranking-", dir=settings.artifact_root) as directory:
        source, target = Path(directory) / "input.json", Path(directory) / "output.json"
        source.write_text(request.model_dump_json(), encoding="utf-8")
        env = {
            key: value
            for key, value in os.environ.items()
            if key.upper()
            in {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "HOME", "LOCALAPPDATA"}
        }
        env.update(
            HF_HUB_DISABLE_IMPLICIT_TOKEN="1",
            HF_HUB_DISABLE_TELEMETRY="1",
            TOKENIZERS_PARALLELISM="false",
            OMP_NUM_THREADS=str(request.threads),
        )
        child = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "rag_core.rerank_child",
                str(source.resolve()),
                str(target.resolve()),
                str(settings.model_cache_dir.resolve()),
            ],
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        started = time.monotonic()
        try:
            while child.poll() is None:
                if stop.is_set() or lost.is_set():
                    raise LostLease
                if time.monotonic() - started > settings.reranker_timeout_seconds:
                    raise PlatformError(
                        "reranker_timeout", "Local reranking exceeded its time limit."
                    )
                time.sleep(0.1)
            if not target.exists() or target.stat().st_size > 200_000:
                raise PlatformError("reranker_failed", "Local reranking produced no valid output.")
            output = json.loads(target.read_text(encoding="utf-8"))
            if not isinstance(output, dict):
                raise PlatformError("reranker_failed", "Invalid reranking output.")
            if "error" in output or child.returncode != 0:
                code = str(output.get("error", "reranker_failed"))
                messages = {
                    "reranker_model_unavailable": "Pinned reranker is unavailable.",
                    "reranker_artifact_mismatch": "Reranker artifacts differ from the pin.",
                    "reranker_input_too_long": "A query/passage pair exceeds 512 tokens.",
                }
                raise PlatformError(code, messages.get(code, "Local reranking failed."))
            return output
        finally:
            if child.poll() is None:
                child.kill()
            child.wait(timeout=10)


def prepare_reranker(settings: Settings, stop: Event, lost: Event) -> None:
    output = run_reranker_child(RerankInput(mode="prepare"), settings, stop, lost)
    if output.get("contract") != reranker_contract():
        raise PlatformError("reranker_artifact_mismatch", "Reranker preparation is incompatible.")


def rerank(request: RerankInput, settings: Settings, stop: Event, lost: Event) -> RerankOutput:
    output = RerankOutput.model_validate(run_reranker_child(request, settings, stop, lost))
    if output.passage_ids != [chunk.id for chunk in request.passages]:
        raise PlatformError("reranker_result_mismatch", "Reranking output passage IDs differ.")
    return output


def artifact_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        while block := file.read(1_048_576):
            digest.update(block)
    return digest.hexdigest()
