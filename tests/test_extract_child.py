import hashlib
import json
import subprocess
import sys
from pathlib import Path

from rag_core.schemas import Extraction


def test_parser_subprocess_writes_valid_checkpoint_without_shell_execution(tmp_path: Path) -> None:
    source = tmp_path / "original & SQL.txt"
    raw = b"  SELECT\n    1;"
    source.write_bytes(raw)
    output = tmp_path / "checkpoint.json"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "rag_core.extract_child",
            str(source),
            str(output),
            source.name,
            hashlib.sha256(raw).hexdigest(),
            "10000",
            "20",
        ],
        capture_output=True,
        timeout=10,
        check=True,
    )
    checkpoint = Extraction.model_validate(
        json.loads(output.read_text(encoding="utf-8"))["extraction"]
    )
    assert checkpoint.sections[0].text == "  SELECT\n    1;"
    assert result.stdout == b""
    assert not output.with_suffix(".tmp").exists()


def test_tampered_checkpoint_text_is_rejected(tmp_path: Path) -> None:
    source = tmp_path / "original.txt"
    raw = b"Evidence"
    source.write_bytes(raw)
    output = tmp_path / "checkpoint.json"
    subprocess.run(
        [
            sys.executable,
            "-m",
            "rag_core.extract_child",
            str(source),
            str(output),
            source.name,
            "0" * 64,
            "10000",
            "20",
        ],
        timeout=10,
        check=True,
    )
    result = json.loads(output.read_text(encoding="utf-8"))
    assert result["error"]["code"] == "checksum_mismatch"
