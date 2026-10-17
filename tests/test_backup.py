"""Private-backup integrity checks on synthetic local bytes; no live restore target."""

import json
from pathlib import Path

import pytest
from rag_core.backup import contained_file, inventory, verify_bundle


def test_backup_manifest_detects_modified_and_missing_bytes(tmp_path: Path) -> None:
    (tmp_path / "database.dump").write_bytes(b"synthetic database archive")
    manifest = {"schema": "workspace-backup-v1", "files": inventory(tmp_path)}
    (tmp_path / "backup-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    assert verify_bundle(tmp_path) == manifest
    (tmp_path / "database.dump").write_bytes(b"modified database archive")
    with pytest.raises(ValueError, match="integrity"):
        verify_bundle(tmp_path)
    (tmp_path / "database.dump").unlink()
    with pytest.raises(ValueError, match="Missing"):
        verify_bundle(tmp_path)


@pytest.mark.parametrize("name", ["../outside", "/outside", "C:/outside", "a\\outside", "a/../b"])
def test_backup_rejects_escaping_paths(tmp_path: Path, name: str) -> None:
    with pytest.raises(ValueError):
        contained_file(tmp_path, name)


def test_backup_inventory_only_excludes_root_control_files(tmp_path: Path) -> None:
    (tmp_path / "source").mkdir()
    (tmp_path / "source/backup-manifest.json").write_text("synthetic source", encoding="utf-8")
    (tmp_path / "backup-manifest.json").write_text("manifest", encoding="utf-8")
    assert set(inventory(tmp_path)) == {"source/backup-manifest.json"}
