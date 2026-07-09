"""Tests for orchestration task get read-only command."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agent_runtime.cli import main


ROOT = Path(__file__).resolve().parents[1]


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")


def test_task_get_json_output_structure(capsys, tmp_path):
    fake_root = tmp_path / "project"
    fake_root.mkdir()
    tasks = [
        {
            "id": "task-20260709-001",
            "title": "Detail task",
            "summary": "A task for detail view",
            "status": "running",
            "requested_capability": "dispatch.agent.coding",
            "assignee": "agent-a",
            "workspace": "project-root",
            "priority": "high",
            "labels": ["coding", "backend"],
            "created_at": "2026-07-09T10:00:00+08:00",
            "updated_at": "2026-07-09T10:05:00+08:00",
        }
    ]
    events = [
        {
            "event_id": "evt-20260709-001",
            "task_id": "task-20260709-001",
            "timestamp": "2026-07-09T10:00:00+08:00",
            "actor": "cli",
            "event_type": "created",
            "to_status": "planned",
            "message": "Task created",
        },
        {
            "event_id": "evt-20260709-002",
            "task_id": "task-20260709-001",
            "timestamp": "2026-07-09T10:05:00+08:00",
            "actor": "cli",
            "event_type": "status_changed",
            "from_status": "planned",
            "to_status": "running",
            "message": "Started",
        },
    ]
    _write_jsonl(fake_root / "tasks" / "tasks.jsonl", tasks)
    _write_jsonl(fake_root / "tasks" / "events.jsonl", events)

    code = main([
        "--root", str(fake_root),
        "orchestration", "task", "get",
        "--task-id", "task-20260709-001",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 0
    result = json.loads(captured.out)
    assert result["status"] == "pass"

    task = result["task"]
    assert task["task_id"] == "task-20260709-001"
    assert task["title"] == "Detail task"
    assert task["summary"] == "A task for detail view"
    assert task["status"] == "running"
    assert task["requested_capability"] == "dispatch.agent.coding"
    assert task["assignee"] == "agent-a"
    assert task["workspace"] == "project-root"
    assert task["priority"] == "high"
    assert task["labels"] == ["coding", "backend"]
    assert task["created_at"] == "2026-07-09T10:00:00+08:00"
    assert task["updated_at"] == "2026-07-09T10:05:00+08:00"

    timeline = result["event_timeline"]
    assert len(timeline) == 2
    assert timeline[0]["timestamp"] == "2026-07-09T10:00:00+08:00"
    assert timeline[0]["event_type"] == "created"
    assert timeline[0]["to_status"] == "planned"
    assert timeline[1]["timestamp"] == "2026-07-09T10:05:00+08:00"
    assert timeline[1]["event_type"] == "status_changed"
    assert timeline[1]["from_status"] == "planned"
    assert timeline[1]["to_status"] == "running"


def test_task_get_human_readable_smoke(capsys, tmp_path):
    fake_root = tmp_path / "project"
    fake_root.mkdir()
    tasks = [
        {
            "id": "task-20260709-001",
            "title": "Readable detail",
            "status": "planned",
            "requested_capability": "inspect.repo",
            "assignee": "agent-a",
            "created_at": "2026-07-09T10:00:00+08:00",
            "updated_at": "2026-07-09T10:00:00+08:00",
        }
    ]
    _write_jsonl(fake_root / "tasks" / "tasks.jsonl", tasks)

    code = main([
        "--root", str(fake_root),
        "orchestration", "task", "get",
        "--task-id", "task-20260709-001",
    ])
    captured = capsys.readouterr()
    assert code == 0
    assert "task-20260709-001" in captured.out
    assert "Readable detail" in captured.out


def test_task_get_missing_task(capsys, tmp_path):
    fake_root = tmp_path / "project"
    fake_root.mkdir()

    code = main([
        "--root", str(fake_root),
        "orchestration", "task", "get",
        "--task-id", "task-missing-001",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code != 0
    result = json.loads(captured.out)
    assert result["status"] == "needs_input"
    assert "task-missing-001" in result["next_action"]


def test_task_get_example_fallback(capsys, tmp_path):
    fake_root = tmp_path / "project"
    fake_root.mkdir()
    examples = [
        {
            "id": "task-example-001",
            "title": "Example task",
            "status": "finished",
            "requested_capability": "inspect.repo",
            "assignee": "agent-example",
            "created_at": "2026-07-09T10:00:00+08:00",
            "updated_at": "2026-07-09T10:00:00+08:00",
        }
    ]
    _write_jsonl(fake_root / "tasks" / "examples.jsonl", examples)

    code = main([
        "--root", str(fake_root),
        "orchestration", "task", "get",
        "--task-id", "task-example-001",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 0
    result = json.loads(captured.out)
    assert result["task"]["task_id"] == "task-example-001"


def test_task_get_event_timeline_sorted(capsys, tmp_path):
    fake_root = tmp_path / "project"
    fake_root.mkdir()
    tasks = [
        {
            "id": "task-20260709-001",
            "title": "Sorted events",
            "status": "running",
            "requested_capability": "inspect.repo",
            "assignee": "agent-a",
            "created_at": "2026-07-09T10:00:00+08:00",
            "updated_at": "2026-07-09T10:05:00+08:00",
        }
    ]
    events = [
        {
            "event_id": "evt-002",
            "task_id": "task-20260709-001",
            "timestamp": "2026-07-09T10:05:00+08:00",
            "actor": "cli",
            "event_type": "status_changed",
            "from_status": "planned",
            "to_status": "running",
        },
        {
            "event_id": "evt-001",
            "task_id": "task-20260709-001",
            "timestamp": "2026-07-09T10:00:00+08:00",
            "actor": "cli",
            "event_type": "created",
            "to_status": "planned",
        },
    ]
    _write_jsonl(fake_root / "tasks" / "tasks.jsonl", tasks)
    _write_jsonl(fake_root / "tasks" / "events.jsonl", events)

    code = main([
        "--root", str(fake_root),
        "orchestration", "task", "get",
        "--task-id", "task-20260709-001",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 0
    result = json.loads(captured.out)
    timestamps = [event["timestamp"] for event in result["event_timeline"]]
    assert timestamps == ["2026-07-09T10:00:00+08:00", "2026-07-09T10:05:00+08:00"]


def test_task_get_does_not_write_files(capsys, tmp_path):
    fake_root = tmp_path / "project"
    fake_root.mkdir()
    tasks = [
        {
            "id": "task-20260709-001",
            "title": "Read only",
            "status": "running",
            "requested_capability": "inspect.repo",
            "assignee": "agent-a",
            "created_at": "2026-07-09T10:00:00+08:00",
            "updated_at": "2026-07-09T10:00:00+08:00",
        }
    ]
    events = [
        {
            "event_id": "evt-001",
            "task_id": "task-20260709-001",
            "timestamp": "2026-07-09T10:00:00+08:00",
            "actor": "cli",
            "event_type": "created",
        }
    ]
    _write_jsonl(fake_root / "tasks" / "tasks.jsonl", tasks)
    _write_jsonl(fake_root / "tasks" / "events.jsonl", events)
    tasks_before = (fake_root / "tasks" / "tasks.jsonl").read_bytes()
    events_before = (fake_root / "tasks" / "events.jsonl").read_bytes()

    code = main([
        "--root", str(fake_root),
        "orchestration", "task", "get",
        "--task-id", "task-20260709-001",
        "--json",
    ])
    assert code == 0
    assert (fake_root / "tasks" / "tasks.jsonl").read_bytes() == tasks_before
    assert (fake_root / "tasks" / "events.jsonl").read_bytes() == events_before
