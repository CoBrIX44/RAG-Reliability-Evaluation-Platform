"""Joint query/passage cross-encoding in a bounded CPU-only worker child."""

import json
import platform
import sys
import time
from pathlib import Path

from huggingface_hub import snapshot_download

from rag_core.errors import PlatformError
from rag_core.reranking import (
    RERANKER_ARTIFACTS,
    RERANKER_ID,
    RERANKER_REVISION,
    RerankInput,
    RerankOutput,
    artifact_digest,
    reranker_contract,
)


def snapshot(cache: Path, download: bool) -> Path:
    try:
        root = Path(
            snapshot_download(
                RERANKER_ID,
                revision=RERANKER_REVISION,
                cache_dir=str(cache),
                token=False,
                local_files_only=not download,
                allow_patterns=list(RERANKER_ARTIFACTS),
            )
        )
        if any(
            artifact_digest(root / name) != digest for name, digest in RERANKER_ARTIFACTS.items()
        ):
            raise PlatformError("reranker_artifact_mismatch", "Reranker artifact mismatch.")
        return root
    except PlatformError:
        raise
    except Exception as error:
        raise PlatformError("reranker_model_unavailable", "Reranker unavailable.") from error


def execute(request: RerankInput, cache: Path) -> dict[str, object]:
    started = time.monotonic()
    root = snapshot(cache, request.mode == "prepare")
    if request.mode == "prepare":
        return {"contract": reranker_contract()}
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    torch.set_num_threads(request.threads)
    torch.set_num_interop_threads(1)
    torch.manual_seed(0)
    torch.use_deterministic_algorithms(True)
    tokenizer = AutoTokenizer.from_pretrained(
        str(root), local_files_only=True, trust_remote_code=False
    )
    texts = [chunk.text for chunk in request.passages]
    # Validate the model's actual paired encoding, including special tokens, before inference.
    encoded = tokenizer(
        [request.query] * len(texts),
        texts,
        add_special_tokens=True,
        truncation=False,
        padding=False,
    )
    pair_tokens = [len(ids) for ids in encoded["input_ids"]]
    if any(count > 512 for count in pair_tokens):
        raise PlatformError("reranker_input_too_long", "Reranking pair exceeds token capacity.")
    model = AutoModelForSequenceClassification.from_pretrained(
        str(root),
        local_files_only=True,
        trust_remote_code=False,
        use_safetensors=True,
        dtype=torch.float32,
    )
    if model.config.num_labels != 1 or model.config.max_position_embeddings != 512:
        raise PlatformError("reranker_artifact_mismatch", "Reranker architecture differs.")
    model.eval()
    scores: list[float] = []
    with torch.inference_mode():
        for offset in range(0, len(texts), request.batch_size):
            batch = texts[offset : offset + request.batch_size]
            features = tokenizer(
                [request.query] * len(batch),
                batch,
                padding=True,
                truncation=False,
                return_tensors="pt",
            )
            logits = model(**features).logits[:, 0]
            scores.extend(float(score) for score in logits.tolist())
    return RerankOutput(
        passage_ids=[chunk.id for chunk in request.passages],
        scores=scores,
        pair_tokens=pair_tokens,
        metadata={
            "contract": reranker_contract(),
            "elapsed_ms": (time.monotonic() - started) * 1000,
            "runtime": {
                "platform": platform.system(),
                "machine": platform.machine(),
                "python": platform.python_version(),
                "threads": request.threads,
                "batch_size": request.batch_size,
                "seed": 0,
            },
        },
    ).model_dump(mode="json")


def main() -> int:
    source, target, cache = map(Path, sys.argv[1:4])
    try:
        output = execute(RerankInput.model_validate_json(source.read_text(encoding="utf-8")), cache)
        status = 0
    except Exception as error:
        output = {"error": error.code if isinstance(error, PlatformError) else "reranker_failed"}
        status = 1
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps(output, allow_nan=False), encoding="utf-8")
    temporary.replace(target)
    return status


if __name__ == "__main__":
    raise SystemExit(main())
