"""Worker-only CPU inference from a safetensors snapshot; never execute uploaded content."""

import hashlib
import json
import os
import platform
import sys
import time
from pathlib import Path

from rag_core.embeddings import EmbeddingInput, EmbeddingOutput, embedding_contract
from rag_core.errors import PlatformError
from rag_core.tokenization import BASELINE_TOKENIZER_ID, BASELINE_TOKENIZER_REVISION


def encode(request: EmbeddingInput, cache: Path) -> EmbeddingOutput:
    # Heavy libraries are imported only inside this worker subprocess.
    import torch
    from huggingface_hub import snapshot_download
    from sentence_transformers import SentenceTransformer

    started = time.monotonic()
    torch.set_num_threads(request.threads)
    torch.set_num_interop_threads(1)
    torch.manual_seed(0)
    torch.use_deterministic_algorithms(True)
    try:
        snapshot = Path(
            snapshot_download(
                BASELINE_TOKENIZER_ID,
                revision=BASELINE_TOKENIZER_REVISION,
                cache_dir=str(cache),
                local_files_only=not request.allow_download,
                token=False,
                allow_patterns=[
                    "*.json",
                    "vocab.txt",
                    "model.safetensors",
                    "1_Pooling/config.json",
                ],
            )
        )
        model = SentenceTransformer(
            str(snapshot),
            device="cpu",
            trust_remote_code=False,
            local_files_only=True,
            token=False,
            model_kwargs={"use_safetensors": True},
        )
    except Exception as error:
        raise PlatformError(
            "embedding_model_unavailable", "Pinned embedding model unavailable."
        ) from error
    contract = embedding_contract()
    if model.get_embedding_dimension() != contract["dimensions"] or model.max_seq_length != 256:
        raise PlatformError(
            "embedding_model_mismatch", "Embedding model differs from its contract."
        )
    # Check the actual model tokenizer with special tokens, not a heuristic character limit.
    for text in request.texts:
        ids = model.tokenizer.encode(text, add_special_tokens=True, truncation=False)
        if len(ids) > model.max_seq_length:
            raise PlatformError("embedding_input_too_long", "Input exceeds model capacity.")
    vectors = model.encode(
        request.texts,
        batch_size=request.batch_size,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
        precision="float32",
    )
    artifacts = {
        path.relative_to(snapshot).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(snapshot.rglob("*"))
        if path.is_file()
    }
    return EmbeddingOutput(
        vectors=vectors.tolist(),
        metadata={
            "contract": contract,
            "artifact_hashes": artifacts,
            "elapsed_ms": (time.monotonic() - started) * 1000,
            "runtime": {
                "platform": platform.system(),
                "machine": platform.machine(),
                "python": platform.python_version(),
                "logical_cpus": os.cpu_count(),
                "threads": request.threads,
                "batch_size": request.batch_size,
            },
        },
    )


def main() -> int:
    source, target, cache = map(Path, sys.argv[1:4])
    try:
        request = EmbeddingInput.model_validate_json(source.read_text(encoding="utf-8"))
        output: dict[str, object] = encode(request, cache).model_dump()
        status = 0
    except Exception as error:
        output = {"error": error.code if isinstance(error, PlatformError) else "embedding_failed"}
        status = 1
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps(output, allow_nan=False), encoding="utf-8")
    temporary.replace(target)
    return status


if __name__ == "__main__":
    raise SystemExit(main())
