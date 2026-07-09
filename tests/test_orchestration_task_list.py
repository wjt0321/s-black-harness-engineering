"""Tests for orchestration task list read-only command."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agent_runtime.cli import main


ROOT = Path(__file__).resolve().parents[1]


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")


def test_task_list_json_output_structure(capsys, tmp_path):
    fake_root = tmp_path / "project"
    fake_root.mkdir()
    tasks = [
        {
            "id": "task-20260709-001",
            "title": "First task",
            "status": "running",
            "requested_capability": "dispatch.agent.coding",
            "assignee": "agent-a",
            "created_at": "2026-07-09T10:00:00+08:00",
            "updated_at": "2026-07-09T10:05:00+08:00",
        },
        {
            "id": "task-20260709-002",
            "title": "Second task",
            "status": "blocked",
            "requested_capability": "publish.github.push",
            "assignee": "agent-b",
            "created_at": "2026-07-09T10:00:00+08:00",
            "updated_at": "2026-07-09T10:10:00+08:00",
        },
    ]
    _write_jsonl(fake_root / "tasks" / "tasks.jsonl", tasks)

    code = main(["--root", str(fake_root), "orchestration", "task", "list", "--json"])
    captured = capsys.readouterr()
    assert code == 0
    result = json.loads(captured.out)
    assert result["status"] == "pass"
    assert len(result["tasks"]) == 2

    by_id = {task["task_id"]: task for task in result["tasks"]}
    assert "task-20260709-001" in by_id
    assert "task-20260709-002" in by_id

    first = by_id["task-20260709-001"]
    assert first["title"] == "First task"
    assert first["status"] == "running"
    assert first["requested_capability"] == "dispatch.agent.coding"
    assert first["assignee"] == "agent-a"
    assert first["created_at"] == "2026-07-09T10:00:00+08:00"
    assert first["updated_at"] == "2026-07-09T10:05:00+08:00"


def test_task_list_empty_ledger_stable_output(capsys, tmp_path):
    fake_root = tmp_path / "project"
    fake_root.mkdir()

    code = main(["--root", str(fake_root), "orchestration", "task", "list", "--json"])
    captured = capsys.readouterr()
    assert code == 0
    result = json.loads(captured.out)
    assert result["status"] == "pass"
    assert result["tasks"] == []


def test_task_list_human_readable_smoke(capsys, tmp_path):
    fake_root = tmp_path / "project"
    fake_root.mkdir()
    tasks = [
        {
            "id": "task-20260709-001",
            "title": "Readable task",
            "status": "planned",
            "requested_capability": "inspect.repo",
            "assignee": "agent-a",
            "created_at": "2026-07-09T10:00:00+08:00",
            "updated_at": "2026-07-09T10:00:00+08:00",
        }
    ]
    _write_jsonl(fake_root / "tasks" / "tasks.jsonl", tasks)

    code = main(["--root", str(fake_root), "orchestration", "task", "list"])
    captured = capsys.readouterr()
    assert code == 0
    assert "TASK LIST" in captured.out
    assert "task-20260709-001" in captured.out
    assert "planned" in captured.out


def test_task_list_example_fallback(capsys, tmp_path):
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

    code = main(["--root", str(fake_root), "orchestration", "task", "list", "--json"])
    captured = capsys.readouterr()
    assert code == 0
    result = json.loads(captured.out)
    assert len(result["tasks"]) == 1
    assert result["tasks"][0]["task_id"] == "task-example-001"


def test_task_list_status_filter(capsys, tmp_path):
    fake_root = tmp_path / "project"
    fake_root.mkdir()
    tasks = [
        {
            "id": "task-20260709-001",
            "title": "Running task",
            "status": "running",
            "requested_capability": "dispatch.agent.coding",
            "assignee": "agent-a",
            "created_at": "2026-07-09T10:00:00+08:00",
            "updated_at": "2026-07-09T10:05:00+08:00",
        },
        {
            "id": "task-20260709-002",
            "title": "Blocked task",
            "status": "blocked",
            "requested_capability": "publish.github.push",
            "assignee": "agent-b",
            "created_at": "2026-07-09T10:00:00+08:00",
            "updated_at": "2026-07-09T10:10:00+08:00",
        },
    ]
    _write_jsonl(fake_root / "tasks" / "tasks.jsonl", tasks)

    code = main([
        "--root", str(fake_root),
        "orchestration", "task", "list",
        "--status", "blocked",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 0
    result = json.loads(captured.out)
    assert len(result["tasks"]) == 1
    assert result["tasks"][0]["task_id"] == "task-20260709-002"
    assert result["tasks"][0]["status"] == "blocked"


def test_task_list_does_not_write_files(capsys, tmp_path):
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
    _write_jsonl(fake_root / "tasks" / "tasks.jsonl", tasks)
    tasks_before = (fake_root / "tasks" / "tasks.jsonl").read_bytes()

    code = main(["--root", str(fake_root), "orchestration", "task", "list", "--json"])
    assert code == 0
    assert (fake_root / "tasks" / "tasks.jsonl").read_bytes() == tasks_before
