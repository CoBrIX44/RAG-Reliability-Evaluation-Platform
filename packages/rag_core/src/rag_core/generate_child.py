"""Worker child: fixed safetensors-only CPU model, safe text prompts, no tools."""

import hashlib
import json
import platform
import sys
import time
from pathlib import Path

from huggingface_hub import snapshot_download

from rag_core.context import pack_context
from rag_core.errors import PlatformError
from rag_core.generation import (
    ARTIFACT_HASHES,
    MODEL_ID,
    MODEL_REVISION,
    SYSTEM_PROMPT,
    GenerationInput,
    GenerationOutput,
    citation_trace,
    generation_contract,
)
from rag_core.tokenization import PinnedTokenizer


def snapshot(cache: Path, download: bool) -> Path:
    try:
        root = Path(
            snapshot_download(
                MODEL_ID,
                revision=MODEL_REVISION,
                cache_dir=str(cache),
                local_files_only=not download,
                token=False,
                allow_patterns=list(ARTIFACT_HASHES),
            )
        )
        for name, expected in ARTIFACT_HASHES.items():
            digest = hashlib.sha256()
            with (root / name).open("rb") as file:
                while block := file.read(1_048_576):
                    digest.update(block)
            if digest.hexdigest() != expected:
                raise PlatformError("generation_artifact_mismatch", "Model artifact mismatch.")
        return root
    except PlatformError:
        raise
    except Exception as error:
        raise PlatformError("generation_model_unavailable", "Answer model unavailable.") from error


def execute(request: GenerationInput, cache: Path) -> dict[str, object]:
    started = time.monotonic()
    root = snapshot(cache, request.mode == "prepare")
    if request.mode == "prepare":
        return {"contract": generation_contract()}
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer, GenerationConfig

    torch.set_num_threads(request.threads)
    torch.set_num_interop_threads(1)
    torch.manual_seed(request.seed)
    torch.use_deterministic_algorithms(True)
    tokenizer = PinnedTokenizer(root / "tokenizer.json", MODEL_ID, MODEL_REVISION)
    # Chunk storage counts use the retrieval tokenizer; delivered counts use the answer tokenizer.
    passages = [
        chunk.model_copy(update={"token_count": tokenizer.count(chunk.text)})
        for chunk in request.passages
    ]
    context = pack_context(passages, tokenizer, request.context_tokens)
    evidence = [
        {"citation": f"P{i}", "text": chunk.text} for i, chunk in enumerate(context.passages, 1)
    ]
    chat = AutoTokenizer.from_pretrained(str(root), local_files_only=True, trust_remote_code=False)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": json.dumps(
                {"question": request.question, "evidence": evidence}, ensure_ascii=False
            ),
        },
    ]
    prompt = chat.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    if not isinstance(prompt, str):
        raise PlatformError("generation_failed", "Chat template did not render text.")
    inputs = chat(prompt, return_tensors="pt", add_special_tokens=False, truncation=False)
    input_tokens = inputs["input_ids"].shape[-1]
    if input_tokens > 2048:
        raise PlatformError("generation_prompt_too_long", "Prompt exceeds input capacity.")
    model = AutoModelForCausalLM.from_pretrained(
        str(root),
        local_files_only=True,
        trust_remote_code=False,
        use_safetensors=True,
        dtype=torch.float32,
    )
    model.eval()  # type: ignore[no-untyped-call]
    options = GenerationConfig(  # type: ignore[no-untyped-call]
        do_sample=False,
        max_new_tokens=request.max_new_tokens,
        eos_token_id=model.generation_config.eos_token_id,
        pad_token_id=model.generation_config.pad_token_id,
        use_cache=True,
    )
    with torch.inference_mode():
        ids = model.generate(**inputs, generation_config=options)[0][input_tokens:]  # type: ignore[misc]
    decoded = chat.decode(ids, skip_special_tokens=True)
    if not isinstance(decoded, str):
        raise PlatformError("generation_failed", "Answer decoder did not return text.")
    answer = decoded.strip()
    citations, unknown = citation_trace(answer, len(context.passages))
    eos = options.eos_token_id
    eos_ids = eos if isinstance(eos, list) else [eos]
    finished = bool(len(ids) and int(ids[-1]) in eos_ids)
    return GenerationOutput(
        answer=answer,
        context=context,
        prompt=prompt,
        prompt_hash=hashlib.sha256(prompt.encode()).hexdigest(),
        input_tokens=input_tokens,
        output_tokens=len(ids),
        finish_reason="eos" if finished else "length",
        abstained=answer == "INSUFFICIENT_EVIDENCE",
        citations=citations,
        unknown_citations=unknown,
        metadata={
            "contract": generation_contract(),
            "elapsed_ms": (time.monotonic() - started) * 1000,
            "runtime": {
                "platform": platform.system(),
                "machine": platform.machine(),
                "python": platform.python_version(),
                "threads": request.threads,
                "seed": request.seed,
            },
        },
    ).model_dump(mode="json")


def main() -> int:
    source, target, cache = map(Path, sys.argv[1:4])
    try:
        output = execute(
            GenerationInput.model_validate_json(source.read_text(encoding="utf-8")), cache
        )
        status = 0
    except Exception as error:
        output = {"error": error.code if isinstance(error, PlatformError) else "generation_failed"}
        status = 1
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps(output, allow_nan=False), encoding="utf-8")
    temporary.replace(target)
    return status


if __name__ == "__main__":
    raise SystemExit(main())
