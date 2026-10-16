"""A single pinned CPU embedding contract, isolated inference, and strict vector validation."""

import hashlib
import importlib.metadata
import json
import math
import os
import subprocess
import sys
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event

from pydantic import BaseModel, ConfigDict, Field, model_validator

from rag_core.errors import LostLease, PlatformError
from rag_core.processes import hidden_window_flags
from rag_core.settings import Settings
from rag_core.tokenization import BASELINE_TOKENIZER_ID, BASELINE_TOKENIZER_REVISION

DIMENSIONS = 384
MAX_CONTENT_TOKENS = 254
DENSE_STRATEGY = "pgvector-exact-cosine-v1"


def embedding_contract() -> dict[str, object]:
    contract: dict[str, object] = {
        "model_id": BASELINE_TOKENIZER_ID,
        "revision": BASELINE_TOKENIZER_REVISION,
        "dimensions": DIMENSIONS,
        "normalize": True,
        "dtype": "float32",
        "backend": "torch-cpu",
        "max_content_tokens": MAX_CONTENT_TOKENS,
        "sentence_transformers": importlib.metadata.version("sentence-transformers"),
        "transformers": importlib.metadata.version("transformers"),
        "torch": importlib.metadata.version("torch"),
        "tokenizers": importlib.metadata.version("tokenizers"),
    }
    contract["compatibility_key"] = hashlib.sha256(
        json.dumps(contract, sort_keys=True).encode()
    ).hexdigest()
    return contract


class EmbeddingInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    texts: list[str] = Field(min_length=1, max_length=10_000)
    allow_download: bool = False
    threads: int = Field(default=2, ge=1, le=8)
    batch_size: int = Field(default=16, ge=1, le=64)

    @model_validator(mode="after")
    def bound_text(self) -> "EmbeddingInput":
        if any(not text or len(text) > 100_000 for text in self.texts):
            raise ValueError("Embedding inputs must be nonempty and bounded.")
        if sum(map(len, self.texts)) > 5_000_000:
            raise ValueError("Embedding batch exceeds the character limit.")
        return self


class EmbeddingOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    vectors: list[list[float]] = Field(min_length=1, max_length=10_000)
    metadata: dict[str, object]

    @model_validator(mode="after")
    def validate_vectors(self) -> "EmbeddingOutput":
        for vector in self.vectors:
            if len(vector) != DIMENSIONS or not all(math.isfinite(value) for value in vector):
                raise ValueError("Embedding dimensions and finite values must match the contract.")
            if abs(math.sqrt(sum(value * value for value in vector)) - 1) > 0.001:
                raise ValueError("Embeddings must have a nonzero unit norm.")
        if self.metadata.get("contract") != embedding_contract():
            raise ValueError("Embedding output is incompatible with the pinned runtime.")
        artifacts = self.metadata.get("artifact_hashes")
        required = {
            "model.safetensors",
            "tokenizer.json",
            "config.json",
            "modules.json",
            "1_Pooling/config.json",
            "sentence_bert_config.json",
        }
        if not isinstance(artifacts, dict) or not required.issubset(artifacts):
            raise ValueError("Embedding output must identify all model artifacts.")
        if any(
            not isinstance(name, str)
            or "\\" in name
            or name.startswith("/")
            or ".." in name.split("/")
            or not isinstance(digest, str)
            or len(digest) != 64
            or any(c not in "0123456789abcdef" for c in digest)
            for name, digest in artifacts.items()
        ):
            raise ValueError("Embedding artifact hashes are invalid.")
        return self


def vector_literal(vector: list[float]) -> str:
    if len(vector) != DIMENSIONS or not all(math.isfinite(value) for value in vector):
        raise PlatformError("invalid_embedding", "Embedding vector is incompatible.")
    norm = math.sqrt(sum(value * value for value in vector))
    if abs(norm - 1) > 0.001:
        raise PlatformError("invalid_embedding", "Embedding vector must have unit norm.")
    return json.dumps(vector, allow_nan=False, separators=(",", ":"))


def run_embeddings(
    texts: list[str], settings: Settings, stop: Event, lost: Event, *, allow_download: bool = False
) -> EmbeddingOutput:
    request = EmbeddingInput(
        texts=texts,
        allow_download=allow_download,
        threads=settings.embedding_threads,
        batch_size=settings.embedding_batch_size,
    )
    settings.artifact_root.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="embedding-", dir=settings.artifact_root) as directory:
        root = Path(directory)
        source, target = root / "input.json", root / "output.json"
        source.write_text(request.model_dump_json(), encoding="utf-8")
        # No shell, document-controlled paths, or provider secrets enter the inference child.
        env = {
            key: value
            for key, value in os.environ.items()
            if key.upper()
            in {
                "PATH",
                "SYSTEMROOT",
                "WINDIR",
                "TEMP",
                "TMP",
                "HOME",
                "LOCALAPPDATA",
            }
        }
        env.update(
            {
                "HF_HUB_DISABLE_IMPLICIT_TOKEN": "1",
                "HF_HUB_DISABLE_TELEMETRY": "1",
                "TOKENIZERS_PARALLELISM": "false",
                "OMP_NUM_THREADS": str(request.threads),
            }
        )
        child = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "rag_core.embed_child",
                str(source.resolve()),
                str(target.resolve()),
                str(settings.model_cache_dir.resolve()),
            ],
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=hidden_window_flags(),
        )
        started = time.monotonic()
        try:
            while child.poll() is None:
                if stop.is_set() or lost.is_set():
                    raise LostLease
                if time.monotonic() - started > settings.model_timeout_seconds:
                    raise PlatformError(
                        "embedding_timeout", "Local embedding exceeded its time limit."
                    )
                time.sleep(0.1)
            if not target.exists() or target.stat().st_size > 120_000_000:
                raise PlatformError(
                    "embedding_failed", "Local embedding failed without a valid output."
                )
            output = json.loads(target.read_text(encoding="utf-8"))
            if "error" in output:
                code = output["error"]
                messages = {
                    "embedding_input_too_long": "Text exceeds the 254-token content limit.",
                    "embedding_model_unavailable": "Pinned embedding model is unavailable.",
                }
                raise PlatformError(code, messages.get(code, "Local embedding failed."))
            result = EmbeddingOutput.model_validate(output)
            if child.returncode != 0 or len(result.vectors) != len(texts):
                raise PlatformError("embedding_failed", "Local embedding output count is invalid.")
            return result
        finally:
            if child.poll() is None:
                child.kill()
            child.wait(timeout=10)
