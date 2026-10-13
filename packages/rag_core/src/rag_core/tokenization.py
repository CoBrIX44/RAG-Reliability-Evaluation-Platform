"""Pinned, offline-first tokenizer loading. No model weights or inference are involved."""

import hashlib
import importlib.metadata
import re
from pathlib import Path

from huggingface_hub import hf_hub_download
from tokenizers import Tokenizer

from rag_core.errors import PlatformError

BASELINE_TOKENIZER_ID = "sentence-transformers/all-MiniLM-L6-v2"
BASELINE_TOKENIZER_REVISION = "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"


class PinnedTokenizer:
    def __init__(self, path: Path, model_id: str, revision: str) -> None:
        if not re.fullmatch(r"[0-9a-f]{40}", revision):
            raise ValueError("Tokenizer revision must be a full immutable Hub commit SHA.")
        self._tokenizer = Tokenizer.from_file(str(path))
        # Repository settings may silently truncate inputs. Chunking must see the entire source.
        self._tokenizer.no_truncation()
        self._tokenizer.no_padding()
        checksum = hashlib.sha256(path.read_bytes()).hexdigest()
        library_version = importlib.metadata.version("tokenizers")
        self.identity = f"{model_id}@{revision}:sha256={checksum}:tokenizers={library_version}"

    @classmethod
    def load(
        cls,
        cache_dir: Path,
        *,
        model_id: str = BASELINE_TOKENIZER_ID,
        revision: str = BASELINE_TOKENIZER_REVISION,
        allow_download: bool = False,
    ) -> "PinnedTokenizer":
        if not re.fullmatch(r"[0-9a-f]{40}", revision):
            raise ValueError("Tokenizer revision must be a full immutable Hub commit SHA.")
        try:
            path = hf_hub_download(
                repo_id=model_id,
                filename="tokenizer.json",
                revision=revision,
                cache_dir=str(cache_dir),
                local_files_only=not allow_download,
                token=False,
            )
            return cls(Path(path), model_id, revision)
        except Exception as error:
            raise PlatformError(
                "tokenizer_unavailable",
                "The pinned tokenizer is unavailable. Prepare its cache before building an index.",
                status=503,
            ) from error

    def offsets(self, text: str) -> list[tuple[int, int]]:
        return list(self._tokenizer.encode(text, add_special_tokens=False).offsets)

    def count(self, text: str) -> int:
        return len(self._tokenizer.encode(text, add_special_tokens=False).ids)
