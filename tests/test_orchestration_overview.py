"""Tests for orchestration overview read-only aggregation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agent_runtime.cli import main


ROOT = Path(__file__).resolve().parents[1]


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")


def test_overview_json_output_structure(capsys, tmp_path):
    fake_root = tmp_path / "project"
    fake_root.mkdir()
    tasks = [
        {
            "id": "task-20260709-001",
            "title": "First task",
            "status": "running",
            "requested_capability": "dispatch.agent.coding",
            "created_at": "2026-07-09T10:00:00+08:00",
            "updated_at": "2026-07-09T10:05:00+08:00",
        },
        {
            "id": "task-20260709-002",
            "title": "Second task",
            "status": "blocked",
            "requested_capability": "publish.github.push",
            "created_at": "2026-07-09T10:00:00+08:00",
            "updated_at": "2026-07-09T10:10:00+08:00",
        },
        {
            "id": "task-20260709-003",
            "title": "Third task",
            "status": "finished",
            "requested_capability": "inspect.repo",
            "created_at": "2026-07-09T10:00:00+08:00",
            "updated_at": "2026-07-09T10:02:00+08:00",
        },
    ]
    events = [
        {
            "event_id": "evt-20260709-001",
            "task_id": "task-20260709-001",
            "timestamp": "2026-07-09T10:05:00+08:00",
            "actor": "test",
            "event_type": "created",
        },
        {
            "event_id": "evt-20260709-002",
            "task_id": "task-20260709-002",
            "timestamp": "2026-07-09T10:10:00+08:00",
            "actor": "test",
            "event_type": "created",
        },
    ]
    _write_jsonl(fake_root / "tasks" / "tasks.jsonl", tasks)
    _write_jsonl(fake_root / "tasks" / "events.jsonl", events)

    code = main(["--root", str(fake_root), "orchestration", "overview", "--json"])
    captured = capsys.readouterr()
    assert code == 0
    result = json.loads(captured.out)
    assert result["status"] == "pass"
    assert result["summary"]["total_tasks"] == 3
    assert result["summary"]["planned_tasks"] == 0
    assert result["summary"]["running_tasks"] == 1
    assert result["summary"]["blocked_tasks"] == 1
    assert result["summary"]["finished_tasks"] == 1
    assert result["summary"]["failed_tasks"] == 0
    assert result["summary"]["total_events"] == 2
    assert result["summary"]["latest_task_updated_at"] == "2026-07-09T10:10:00+08:00"
    recent = result["recent_tasks"]
    assert len(recent) == 3
    assert recent[0]["task_id"] == "task-20260709-002"
    assert recent[0]["status"] == "blocked"
    assert "title" in recent[0]
    assert "requested_capability" in recent[0]
    assert "updated_at" in recent[0]


def test_overview_empty_ledger_stable_output(capsys, tmp_path):
    fake_root = tmp_path / "project"
    fake_root.mkdir()
    # No ledger files at all.

    code = main(["--root", str(fake_root), "orchestration", "overview", "--json"])
    captured = capsys.readouterr()
    assert code == 0
    result = json.loads(captured.out)
    assert result["status"] == "pass"
    assert result["summary"]["total_tasks"] == 0
    assert result["summary"]["total_events"] == 0
    assert result["summary"]["latest_task_updated_at"] is None
    assert result["recent_tasks"] == []


def test_overview_human_readable_smoke(capsys, tmp_path):
    fake_root = tmp_path / "project"
    fake_root.mkdir()
    tasks = [
        {
            "id": "task-20260709-001",
            "title": "Readable task",
            "status": "planned",
            "requested_capability": "inspect.repo",
            "created_at": "2026-07-09T10:00:00+08:00",
            "updated_at": "2026-07-09T10:00:00+08:00",
        }
    ]
    _write_jsonl(fake_root / "tasks" / "tasks.jsonl", tasks)

    code = main(["--root", str(fake_root), "orchestration", "overview"])
    captured = capsys.readouterr()
    assert code == 0
    assert "OVERVIEW" in captured.out
    assert "total_tasks=1" in captured.out
    assert "task-20260709-001" in captured.out


def test_overview_example_fallback(capsys, tmp_path):
    fake_root = tmp_path / "project"
    fake_root.mkdir()
    examples = [
        {
            "id": "task-example-001",
            "title": "Example task",
            "status": "finished",
            "requested_capability": "inspect.repo",
            "created_at": "2026-07-09T10:00:00+08:00",
            "updated_at": "2026-07-09T10:00:00+08:00",
        }
    ]
    _write_jsonl(fake_root / "tasks" / "examples.jsonl", examples)

    code = main(["--root", str(fake_root), "orchestration", "overview", "--json"])
    captured = capsys.readouterr()
    assert code == 0
    result = json.loads(captured.out)
    assert result["summary"]["total_tasks"] == 1
    assert result["summary"]["finished_tasks"] == 1


def test_overview_does_not_write_files(capsys, tmp_path):
    fake_root = tmp_path / "project"
    fake_root.mkdir()
    tasks = [
        {
            "id": "task-20260709-001",
            "title": "Read only",
            "status": "running",
            "requested_capability": "inspect.repo",
            "created_at": "2026-07-09T10:00:00+08:00",
            "updated_at": "2026-07-09T10:00:00+08:00",
        }
    ]
    _write_jsonl(fake_root / "tasks" / "tasks.jsonl", tasks)
    tasks_before = (fake_root / "tasks" / "tasks.jsonl").read_bytes()

    code = main(["--root", str(fake_root), "orchestration", "overview", "--json"])
    assert code == 0
    assert (fake_root / "tasks" / "tasks.jsonl").read_bytes() == tasks_before
