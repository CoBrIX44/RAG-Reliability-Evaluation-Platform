import json
from pathlib import Path
from uuid import UUID

import pytest
from rag_core.chunking import CanonicalSection, ChunkConfig, build_chunks
from rag_core.tokenization import BASELINE_TOKENIZER_REVISION, PinnedTokenizer
from tokenizers import Tokenizer
from tokenizers.models import WordLevel
from tokenizers.pre_tokenizers import Whitespace
from tokenizers.processors import TemplateProcessing

SECTION_A = UUID(int=1)
VARIANT = UUID(int=4)


def tokenizer_file(tmp_path: Path) -> Path:
    tokenizer = Tokenizer(
        WordLevel({"[UNK]": 0, "a": 1, "b": 2, "c": 3, "[CLS]": 4, "[SEP]": 5}, unk_token="[UNK]")
    )
    tokenizer.pre_tokenizer = Whitespace()
    tokenizer.post_processor = TemplateProcessing(
        single="[CLS] $A [SEP]", special_tokens=[("[CLS]", 4), ("[SEP]", 5)]
    )
    tokenizer.enable_truncation(max_length=2)
    tokenizer.enable_padding(length=10)
    path = tmp_path / "tokenizer.json"
    tokenizer.save(str(path))
    return path


def test_pinned_tokenizer_disables_truncation_padding_and_special_tokens(tmp_path: Path) -> None:
    tokenizer = PinnedTokenizer(
        tokenizer_file(tmp_path), "software-fixture", BASELINE_TOKENIZER_REVISION
    )
    assert tokenizer.count("a b c") == 3
    assert tokenizer.offsets("a \U0001f9ea c") == [(0, 1), (2, 3), (4, 5)]
    chunks = build_chunks(
        [CanonicalSection(SECTION_A, VARIANT, 0, "a b c")],
        ChunkConfig(max_tokens=2),
        tokenizer,
        VARIANT,
    )
    assert [chunk.text for chunk in chunks] == ["a b ", "c"]
    assert "sha256=" in tokenizer.identity and BASELINE_TOKENIZER_REVISION in tokenizer.identity


def test_tokenizer_identity_changes_when_artifact_changes(tmp_path: Path) -> None:
    path = tokenizer_file(tmp_path)
    first = PinnedTokenizer(path, "fixture", BASELINE_TOKENIZER_REVISION).identity
    data = json.loads(path.read_text(encoding="utf-8"))
    data["model"]["vocab"]["d"] = 6
    path.write_text(json.dumps(data), encoding="utf-8")
    assert first != PinnedTokenizer(path, "fixture", BASELINE_TOKENIZER_REVISION).identity


@pytest.mark.parametrize("revision", ["main", "v1", "abc", "A" * 40])
def test_moving_tokenizer_revision_is_rejected(tmp_path: Path, revision: str) -> None:
    with pytest.raises(ValueError, match="immutable"):
        PinnedTokenizer.load(tmp_path, revision=revision)
