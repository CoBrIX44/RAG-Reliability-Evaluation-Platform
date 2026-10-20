"""Docker operator control-flow checks; commands are mocked, not restore attestations."""

import importlib.util
import subprocess
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest


@pytest.fixture
def operator() -> ModuleType:
    path = Path(__file__).resolve().parents[1] / "scripts/backup_workspace.py"
    spec = importlib.util.spec_from_file_location("backup_operator_fixture", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_restore_reuses_only_exact_installed_image_ids(
    operator: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls = []

    def fake_run(args: list[str], **kwargs: Any) -> str:
        calls.append(args)
        assert kwargs["timeout"] == 30
        return args[-1] + "\n"

    monkeypatch.setattr(operator, "run", fake_run)
    result = operator.ensure_restore_images(tmp_path, ["sha256:fixture", "sha256:fixture"])
    assert "already-present" in result
    assert len(calls) == 1
    assert calls[0][1:3] == ["image", "inspect"]


def test_research_copy_excludes_only_the_transient_controller_lock(
    operator: ModuleType, tmp_path: Path
) -> None:
    source = tmp_path / "research"
    completion = source / "postgresql-18.0" / "completion"
    completion.mkdir(parents=True)
    (completion / "controller.lock").write_bytes(b"0")
    (completion / "state.json").write_text('{"phase":"requires_attention"}')
    (completion / "evidence.lock").write_bytes(b"retained evidence")
    (source / "controller.lock").write_bytes(b"unrelated file retained")
    destination = tmp_path / "copied"
    operator.copy_research(source, destination)
    copied = destination / "postgresql-18.0" / "completion"
    assert not (copied / "controller.lock").exists()
    assert (copied / "state.json").read_bytes() == (completion / "state.json").read_bytes()
    assert (copied / "evidence.lock").read_bytes() == b"retained evidence"
    assert (destination / "controller.lock").read_bytes() == b"unrelated file retained"


def test_restore_loads_missing_image_and_checks_exact_id(
    operator: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls = []

    def fake_run(args: list[str], **kwargs: Any) -> str:
        calls.append(args)
        if len(calls) == 1:
            raise subprocess.CalledProcessError(1, args, stderr=b"Error: No such image")
        return args[-1] if args[2] == "inspect" else "Loaded"

    monkeypatch.setattr(operator, "run", fake_run)
    assert "loaded archive" in operator.ensure_restore_images(tmp_path, ["sha256:fixture"])
    assert [args[2] for args in calls] == ["inspect", "load", "inspect"]


@pytest.mark.parametrize("failure", ["daemon", "timeout", "wrong_id"])
def test_restore_does_not_treat_daemon_or_identity_failure_as_missing_image(
    operator: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, failure: str
) -> None:
    def fake_run(args: list[str], **kwargs: Any) -> str:
        if failure == "daemon":
            raise subprocess.CalledProcessError(1, args, stderr=b"engine unavailable")
        if failure == "timeout":
            raise subprocess.TimeoutExpired(args, 30)
        return "sha256:different"

    monkeypatch.setattr(operator, "run", fake_run)
    with pytest.raises((subprocess.CalledProcessError, subprocess.TimeoutExpired, ValueError)):
        operator.ensure_restore_images(tmp_path, ["sha256:fixture"])
