"""Offline safetensors CPU inference for the explicit answer-review prompt."""

import hashlib
import json
import platform
import sys
import time
from pathlib import Path

from rag_core.errors import PlatformError
from rag_core.generate_child import snapshot
from rag_core.judge import JUDGE_PROMPT, JudgeRequest, judge_contract


def execute(request: JudgeRequest, cache: Path) -> dict[str, object]:
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer, GenerationConfig

    started = time.monotonic()
    root = snapshot(cache, False)
    torch.set_num_threads(request.threads)
    torch.set_num_interop_threads(1)
    torch.manual_seed(0)
    torch.use_deterministic_algorithms(True)
    chat = AutoTokenizer.from_pretrained(str(root), local_files_only=True, trust_remote_code=False)
    prompt = chat.apply_chat_template(
        [
            {"role": "system", "content": JUDGE_PROMPT},
            {"role": "user", "content": json.dumps(request.inputs, ensure_ascii=False)},
        ],
        tokenize=False,
        add_generation_prompt=True,
    )
    if not isinstance(prompt, str):
        raise PlatformError("judge_failed", "Judge prompt did not render text.")
    inputs = chat(prompt, return_tensors="pt", add_special_tokens=False, truncation=False)
    count = inputs["input_ids"].shape[-1]
    if count > 4096:
        raise PlatformError("judge_prompt_too_long", "Judge input exceeds 4096 tokens.")
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
        max_new_tokens=768,
        eos_token_id=model.generation_config.eos_token_id,
        pad_token_id=model.generation_config.pad_token_id,
        use_cache=True,
    )
    with torch.inference_mode():
        ids = model.generate(**inputs, generation_config=options)[0][count:]  # type: ignore[misc]
    answer = chat.decode(ids, skip_special_tokens=True)
    if not isinstance(answer, str):
        raise PlatformError("judge_failed", "Judge decoder did not return text.")
    eos = options.eos_token_id
    finished = bool(len(ids) and int(ids[-1]) in (eos if isinstance(eos, list) else [eos]))
    return {
        "answer": answer,
        "prompt": prompt,
        "prompt_hash": hashlib.sha256(prompt.encode()).hexdigest(),
        "input_tokens": count,
        "output_tokens": len(ids),
        "finish_reason": "eos" if finished else "length",
        "contract": judge_contract(),
        "elapsed_ms": (time.monotonic() - started) * 1000,
        "runtime": {
            "platform": platform.system(),
            "machine": platform.machine(),
            "python": platform.python_version(),
            "threads": request.threads,
        },
    }


def main() -> int:
    source, target, cache = map(Path, sys.argv[1:4])
    try:
        output = execute(
            JudgeRequest.model_validate_json(source.read_text(encoding="utf-8")), cache
        )
        status = 0
    except Exception as error:
        output = {
            "error": error.code.replace("generation_", "judge_", 1)
            if isinstance(error, PlatformError)
            else "judge_failed"
        }
        status = 1
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps(output, allow_nan=False), encoding="utf-8")
    temporary.replace(target)
    return status


if __name__ == "__main__":
    raise SystemExit(main())
