"""Tests for read-only task ledger loading."""

from pathlib import Path

from agent_runtime.tasks import find_task, find_task_events


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_real_task_ledger_takes_precedence_over_examples(tmp_path):
    _write(
        tmp_path / "tasks" / "tasks.jsonl",
        '{"id":"task-20260703-001","title":"Real ledger","status":"running"}\n',
    )
    _write(
        tmp_path / "tasks" / "examples.jsonl",
        '{"id":"task-20260702-001","title":"Example ledger","status":"finished"}\n',
    )

    assert find_task(tmp_path, "task-20260703-001") is not None
    assert find_task(tmp_path, "task-20260702-001") is None


def test_task_loader_falls_back_to_examples(tmp_path):
    _write(
        tmp_path / "tasks" / "examples.jsonl",
        '{"id":"task-20260702-001","title":"Example ledger","status":"finished"}\n',
    )

    task = find_task(tmp_path, "task-20260702-001")
    assert task is not None
    assert task["title"] == "Example ledger"


def test_real_event_ledger_takes_precedence_over_examples(tmp_path):
    _write(
        tmp_path / "tasks" / "events.jsonl",
        '{"event_id":"evt-20260703-001","task_id":"task-20260703-001","timestamp":"2026-07-03T10:00:00+08:00","actor":"test","event_type":"created","message":"real"}\n',
    )
    _write(
        tmp_path / "tasks" / "events.examples.jsonl",
        '{"event_id":"evt-20260702-001","task_id":"task-20260702-001","timestamp":"2026-07-02T10:00:00+08:00","actor":"test","event_type":"created","message":"example"}\n',
    )

    assert find_task_events(tmp_path, "task-20260703-001")
    assert not find_task_events(tmp_path, "task-20260702-001")
