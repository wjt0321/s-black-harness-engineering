"""Tests for orchestration task submit controlled-write wrapper."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from agent_runtime.cli import main
from agent_runtime.orchestration_task_submit import submit_task

ROOT = Path(__file__).resolve().parents[1]


def _setup_fake_root(tmp_path: Path) -> Path:
    fake_root = tmp_path / "project"
    fake_root.mkdir(parents=True, exist_ok=True)

    for src_rel in (
        "tasks/task.schema.json",
        "tasks/event.schema.json",
        "adapters/execution-envelope.schema.json",
    ):
        src = ROOT / src_rel
        dst = fake_root / src_rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)

    policy_src = ROOT / "policies"
    policy_dst = fake_root / "policies"
    policy_dst.mkdir(parents=True, exist_ok=True)
    for policy_file in policy_src.glob("*.sample.policy.json"):
        shutil.copyfile(policy_file, policy_dst / policy_file.name)

    return fake_root


def _task(task_id: str, title: str = "test task") -> dict[str, object]:
    return {
        "id": task_id,
        "title": title,
        "status": "planned",
        "created_at": "2026-07-09T10:00:00+08:00",
        "updated_at": "2026-07-09T10:00:00+08:00",
        "created_by": "cli",
        "source": "cli",
        "assignee": "cli",
        "tags": [],
        "artifacts": [],
        "evidence": [],
    }


def _write_tasks(root: Path, *tasks: dict[str, object]) -> Path:
    tasks_dir = root / "tasks"
    tasks_dir.mkdir(exist_ok=True)
    tasks_file = tasks_dir / "tasks.jsonl"
    lines = [json.dumps(t, ensure_ascii=False) for t in tasks]
    tasks_file.write_text("\n".join(lines) + "\n" if lines else "", encoding="utf-8")
    return tasks_file


def _candidate_file(root: Path, candidate: dict[str, object]) -> Path:
    candidate_file = root / "candidate-task.json"
    candidate_file.write_text(json.dumps(candidate, ensure_ascii=False), encoding="utf-8")
    return candidate_file


def test_submit_dry_run_pass(tmp_path: Path) -> None:
    root = _setup_fake_root(tmp_path)
    _write_tasks(root, _task("task-20260709-000"))

    result = submit_task(
        root,
        dry_run=True,
        tasks_file="tasks/tasks.jsonl",
        events_file="tasks/events.jsonl",
        candidate=_task("task-20260709-001"),
    )
    assert result.status == "pass"
    assert result.committed is False
    assert "route preview" in (result.next_action or "")


def test_submit_commit_pass(tmp_path: Path) -> None:
    root = _setup_fake_root(tmp_path)
    tasks_file = _write_tasks(root, _task("task-20260709-000"))

    result = submit_task(
        root,
        commit=True,
        tasks_file="tasks/tasks.jsonl",
        events_file="tasks/events.jsonl",
        candidate=_task("task-20260709-001"),
    )
    assert result.status == "pass"
    assert result.committed is True
    assert result.post_validate == "pass"
    assert result.post_ledger_check == "pass"
    assert tasks_file.read_text(encoding="utf-8").count("\n") == 2
    assert "route preview" in (result.next_action or "")


def test_submit_missing_mode_error(tmp_path: Path) -> None:
    root = _setup_fake_root(tmp_path)
    _write_tasks(root)

    result = submit_task(
        root,
        tasks_file="tasks/tasks.jsonl",
        events_file="tasks/events.jsonl",
        candidate=_task("task-20260709-001"),
    )
    assert result.status == "error"
    assert "--dry-run or --commit" in (result.next_action or "")


def test_cli_task_submit_json(capsys, tmp_path: Path) -> None:
    root = _setup_fake_root(tmp_path)
    _write_tasks(root, _task("task-20260709-000"))
    candidate_file = _candidate_file(root, _task("task-20260709-001"))

    code = main([
        "--root", str(root),
        "orchestration", "task", "submit",
        "--file", str(candidate_file),
        "--dry-run",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 0
    result = json.loads(captured.out)
    assert result["status"] == "pass"
    assert result["task_id"] == "task-20260709-001"


def test_cli_task_submit_commit_and_list_get_smoke(capsys, tmp_path: Path) -> None:
    root = _setup_fake_root(tmp_path)
    _write_tasks(root)
    candidate_file = _candidate_file(root, _task("task-20260709-001", title="Readable task"))

    commit_code = main([
        "--root", str(root),
        "orchestration", "task", "submit",
        "--file", str(candidate_file),
        "--commit",
    ])
    commit_out = capsys.readouterr().out
    assert commit_code == 0
    assert "PASS" in commit_out

    list_code = main([
        "--root", str(root),
        "orchestration", "task", "list",
        "--json",
    ])
    list_out = capsys.readouterr().out
    assert list_code == 0
    listed = json.loads(list_out)
    assert any(task["task_id"] == "task-20260709-001" for task in listed["tasks"])

    get_code = main([
        "--root", str(root),
        "orchestration", "task", "get",
        "--task-id", "task-20260709-001",
        "--json",
    ])
    get_out = capsys.readouterr().out
    assert get_code == 0
    detail = json.loads(get_out)
    assert detail["task"]["task_id"] == "task-20260709-001"
