"""Synthetic archive tests; no network, benchmark labels, or model calls."""

import io
import json
import tarfile
from pathlib import Path

import pytest
from pydantic import ValidationError
from rag_core import benchmark_corpus as corpus


def fixture_archive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, symlink: bool = False
) -> tuple[Path, Path]:
    root = tmp_path / "acquired"
    root.mkdir()
    archive_path = root / "postgresql-18.0-docs.tar.gz"
    with tarfile.open(archive_path, "w:gz") as archive:
        for name in ["selected.html", "legalnotice.html", "excluded.html"]:
            data = b"<html><p>Synthetic archive content</p></html>"
            member = tarfile.TarInfo(corpus.PREFIX + name)
            member.size = len(data)
            if symlink and name == "selected.html":
                member.type, member.linkname, member.size = tarfile.SYMTYPE, "../../outside", 0
            archive.addfile(member, io.BytesIO(data))
    checksum = corpus.sha256(archive_path.read_bytes())
    monkeypatch.setattr(corpus, "ARCHIVE_SHA256", checksum)
    selection = tmp_path / "selection.json"
    selection.write_text(
        json.dumps(
            {
                "schema": "postgresql-corpus-selection-v1",
                "release": "18.0",
                "archive_url": corpus.ARCHIVE_URL,
                "archive_sha256": checksum,
                "selection_rationale": "Synthetic test selection",
                "pages": [{"filename": "selected.html", "topic": "synthetic"}],
            }
        ),
        encoding="utf-8",
    )
    return selection, root


def test_acquisition_hashes_exclusions_repeat_and_file_tamper(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    selection, root = fixture_archive(tmp_path, monkeypatch)
    result = corpus.prepare(selection, root)
    assert result["excluded_html"] == ["excluded.html", "legalnotice.html"]
    assert result["documents"][0]["sha256"] == corpus.sha256((root / "selected.html").read_bytes())
    assert corpus.prepare(selection, root) == result
    (root / "selected.html").write_text("tampered", encoding="utf-8")
    with pytest.raises(ValueError, match="changed"):
        corpus.prepare(selection, root)
    assert (root / "selected.html").read_text(encoding="utf-8") == "tampered"


def test_archive_tamper_and_selected_member_bounds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    selection, root = fixture_archive(tmp_path, monkeypatch)
    monkeypatch.setattr(corpus, "MAX_PAGE_BYTES", 1)
    with pytest.raises(ValueError, match="oversized"):
        corpus.prepare(selection, root)
    assert not (root / "acquisition.json").exists()
    (root / "postgresql-18.0-docs.tar.gz").write_bytes(b"tampered")
    with pytest.raises(ValueError, match="SHA-256"):
        corpus.prepare(selection, root)


def test_symlink_and_unsafe_selected_paths_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    selection, root = fixture_archive(tmp_path, monkeypatch, symlink=True)
    with pytest.raises(ValueError, match="Unsafe"):
        corpus.prepare(selection, root)
    assert not (root / "selected.html").exists()
    with pytest.raises(ValidationError):
        corpus.SelectedPage(filename="../outside.html", topic="synthetic")


def test_unpinned_url_duplicate_selection_and_manifest_mutation_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    selection, root = fixture_archive(tmp_path, monkeypatch)
    value = json.loads(selection.read_text(encoding="utf-8"))
    with pytest.raises(ValidationError):
        corpus.CorpusSelection.model_validate(value | {"archive_url": "https://untrusted.invalid"})
    with pytest.raises(ValidationError):
        corpus.CorpusSelection.model_validate(value | {"pages": value["pages"] * 2})
    corpus.prepare(selection, root)
    manifest_path = root / "acquisition.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["archive_sha256"] = "changed"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="manifest differs"):
        corpus.prepare(selection, root)
