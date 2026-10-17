"""Queue backlog drains without an idle-poll delay; idle workers remain bounded."""

import signal
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
import rag_worker.main as worker


@pytest.mark.parametrize("backlog", [False, True])
def test_poll_sleep_only_when_no_work(monkeypatch: pytest.MonkeyPatch, backlog: bool) -> None:
    stop = MagicMock()
    stop.is_set.side_effect = [False, False, True] if backlog else [False, True]
    queue = MagicMock()
    queue.claim.return_value = ("synthetic-job", "synthetic-lease") if backlog else None
    engine = MagicMock()
    monkeypatch.setattr(worker, "Event", lambda: stop)
    monkeypatch.setattr(worker, "Settings", lambda: SimpleNamespace(worker_poll_seconds=15))
    monkeypatch.setattr(worker, "create_database_engine", lambda _: engine)
    monkeypatch.setattr(worker, "inspect_database", lambda _: SimpleNamespace(status="ready"))
    monkeypatch.setattr(worker, "record_worker_heartbeat", lambda _: None)
    monkeypatch.setattr(signal, "signal", lambda *_: None)
    monkeypatch.setattr("sys.argv", ["rag-worker"])
    for name in [
        "IngestionQueue",
        "IndexQueue",
        "DenseSearchQueue",
        "RunQueue",
        "EvaluationQueue",
        "ComparisonQueue",
        "ExportQueue",
    ]:
        monkeypatch.setattr(worker, name, lambda *_: queue)
    assert worker.main() == 0
    if backlog:
        assert queue.process.call_count == 2
        stop.wait.assert_not_called()
    else:
        queue.process.assert_not_called()
        stop.wait.assert_called_once_with(15)
    engine.dispose.assert_called_once()
