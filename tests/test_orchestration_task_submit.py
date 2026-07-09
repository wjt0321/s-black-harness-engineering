"""Tests for orchestration task submit controlled-write wrapper."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from unittest.mock import patch

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


def _write_events(root: Path, *events: dict[str, object]) -> Path:
    tasks_dir = root / "tasks"
    tasks_dir.mkdir(exist_ok=True)
    events_file = tasks_dir / "events.jsonl"
    lines = [json.dumps(e, ensure_ascii=False) for e in events]
    events_file.write_text("\n".join(lines) + "\n" if lines else "", encoding="utf-8")
    return events_file


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
    assert result.would_create is True
    assert result.would_append_created_event is True
    assert result.event_id is not None
    assert result.event_id.startswith("evt-")
    assert "persist the task and created event" in (result.next_action or "")


def test_submit_commit_pass(tmp_path: Path) -> None:
    root = _setup_fake_root(tmp_path)
    tasks_file = _write_tasks(root, _task("task-20260709-000"))
    events_file = _write_events(root)

    result = submit_task(
        root,
        commit=True,
        tasks_file="tasks/tasks.jsonl",
        events_file="tasks/events.jsonl",
        candidate=_task("task-20260709-001"),
    )
    assert result.status == "pass"
    assert result.committed is True
    assert result.created_event_committed is True
    assert result.post_validate_tasks == "pass"
    assert result.post_validate_events == "pass"
    assert result.post_ledger_check == "pass"

    task_lines = [json.loads(line) for line in tasks_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    event_lines = [json.loads(line) for line in events_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert any(t["id"] == "task-20260709-001" for t in task_lines)
    assert len(event_lines) == 1
    assert event_lines[0]["event_type"] == "created"
    assert event_lines[0]["task_id"] == "task-20260709-001"
    assert event_lines[0]["to_status"] == "planned"
    assert event_lines[0]["from_status"] is None
    assert "title" not in event_lines[0].get("metadata", {})
    assert "summary" not in event_lines[0].get("metadata", {})


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


def test_submit_commit_missing_events_file_no_write(tmp_path: Path) -> None:
    root = _setup_fake_root(tmp_path)
    tasks_file = _write_tasks(root, _task("task-20260709-000"))
    original_size = tasks_file.stat().st_size

    result = submit_task(
        root,
        commit=True,
        tasks_file="tasks/tasks.jsonl",
        events_file=None,
        candidate=_task("task-20260709-001"),
    )
    assert result.status == "needs_input"
    assert result.committed is False
    assert tasks_file.stat().st_size == original_size


def test_submit_commit_event_failure_rolls_back_task(tmp_path: Path) -> None:
    root = _setup_fake_root(tmp_path)
    tasks_file = _write_tasks(root, _task("task-20260709-000"))
    events_file = _write_events(root)
    original_tasks_size = tasks_file.stat().st_size

    candidate = _task("task-20260709-001")

    # Force the B append to fail by making the generated created event schema
    # invalid: patch event id generator to return a value that violates the
    # event_id pattern, so append_event validation fails after A succeeded.
    with patch(
        "agent_runtime.orchestration_task_submit._generate_event_id",
        return_value="invalid-event-id",
    ):
        result = submit_task(
            root,
            commit=True,
            tasks_file="tasks/tasks.jsonl",
            events_file="tasks/events.jsonl",
            candidate=candidate,
        )

    assert result.status in ("error", "validation_failed")
    assert result.committed is False
    assert result.created_event_committed is False
    assert result.rolled_back is True
    assert tasks_file.stat().st_size == original_tasks_size
    assert events_file.stat().st_size == 0


def test_submit_commit_post_check_failure_rolls_back_both(tmp_path: Path) -> None:
    root = _setup_fake_root(tmp_path)
    tasks_file = _write_tasks(root, _task("task-20260709-000"))
    events_file = _write_events(root)
    original_tasks_size = tasks_file.stat().st_size
    original_events_size = events_file.stat().st_size

    from agent_runtime.result import CheckResult as _CheckResult, Finding as _Finding

    call_count = 0

    def _fake_validate_records(root: Path, record_file: str, schema: str) -> _CheckResult:
        nonlocal call_count
        call_count += 1
        # Only submit_task's own post-check calls validate_records directly
        # (create_task/append_event import it from their own modules). The two
        # direct calls are: tasks validation, then events validation.
        if call_count == 2:
            return _CheckResult(
                status="validation_failed",
                findings=[
                    _Finding(
                        rule_id="post-check-events-failure",
                        severity="error",
                        action="error",
                        message="Simulated post-check failure on events ledger.",
                    )
                ],
                next_action="Fix the simulated issue.",
            )
        return _CheckResult(status="pass", findings=[])

    with patch(
        "agent_runtime.orchestration_task_submit.validate_records",
        side_effect=_fake_validate_records,
    ):
        result = submit_task(
            root,
            commit=True,
            tasks_file="tasks/tasks.jsonl",
            events_file="tasks/events.jsonl",
            candidate=_task("task-20260709-001"),
        )

    assert result.status in ("error", "validation_failed")
    assert result.committed is False
    assert result.created_event_committed is False
    assert result.rolled_back is True
    assert tasks_file.stat().st_size == original_tasks_size
    assert events_file.stat().st_size == original_events_size


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
    assert result["would_append_created_event"] is True
    assert result["event_id"] is not None


def test_cli_task_submit_commit_and_list_get_smoke(capsys, tmp_path: Path) -> None:
    root = _setup_fake_root(tmp_path)
    _write_tasks(root)
    _write_events(root)
    candidate_file = _candidate_file(root, _task("task-20260709-001", title="Readable task"))

    commit_code = main([
        "--root", str(root),
        "orchestration", "task", "submit",
        "--file", str(candidate_file),
        "--commit",
        "--events-file", "tasks/events.jsonl",
    ])
    commit_out = capsys.readouterr().out
    assert commit_code == 0
    assert "PASS" in commit_out
    assert "created_event_committed=True" in commit_out

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
    assert any(event["event_type"] == "created" for event in detail["event_timeline"])


def test_cli_task_events_see_created(capsys, tmp_path: Path) -> None:
    root = _setup_fake_root(tmp_path)
    _write_tasks(root)
    _write_events(root)
    candidate_file = _candidate_file(root, _task("task-20260709-001"))

    commit_code = main([
        "--root", str(root),
        "orchestration", "task", "submit",
        "--file", str(candidate_file),
        "--commit",
        "--events-file", "tasks/events.jsonl",
    ])
    assert commit_code == 0
    _ = capsys.readouterr().out

    events_code = main([
        "--root", str(root),
        "task", "events",
        "task-20260709-001",
        "--json",
    ])
    events_out = capsys.readouterr().out
    assert events_code == 0
    events = json.loads(events_out)
    assert any(event["event_type"] == "created" for event in events["events"])
