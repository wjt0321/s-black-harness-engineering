"""Tests for runtime event import --commit.

All destructive tests run in temporary directories and assert that failures do
not modify ledger files outside the expected append block.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from unittest.mock import patch

import pytest

from agent_runtime.cli import main
from agent_runtime.runtime_event_import import import_events_commit

ROOT = Path(__file__).resolve().parents[1]


def _setup_fake_root(tmp_path: Path) -> Path:
    """Create a fake project root with the schemas and policies needed."""
    fake_root = tmp_path / "project"
    fake_root.mkdir(parents=True, exist_ok=True)

    for src_rel in (
        "tasks/event.schema.json",
        "tasks/task.schema.json",
        "adapters/execution-envelope.schema.json",
    ):
        src = ROOT / src_rel
        dst = fake_root / src_rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.exists():
            shutil.copyfile(src, dst)

    policy_src = ROOT / "policies"
    policy_dst = fake_root / "policies"
    policy_dst.mkdir(parents=True, exist_ok=True)
    for policy_file in policy_src.glob("*.sample.policy.json"):
        shutil.copyfile(policy_file, policy_dst / policy_file.name)

    return fake_root


def _evt(event_id, task_id, event_type, from_status, to_status, message, timestamp):
    return {
        "event_id": event_id,
        "task_id": task_id,
        "timestamp": timestamp,
        "actor": "cli",
        "event_type": event_type,
        "from_status": from_status,
        "to_status": to_status,
        "message": message,
        "artifacts": [],
        "metadata": {},
    }


def _write_task(root: Path, task_id: str, status: str = "running") -> Path:
    tasks_dir = root / "tasks"
    tasks_dir.mkdir(exist_ok=True)
    tasks_file = tasks_dir / "tasks.jsonl"
    tasks_file.write_text(
        json.dumps(
            {
                "id": task_id,
                "title": "test task",
                "status": status,
                "assignee": "cli",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return tasks_file


def _write_events(root: Path, *events) -> Path:
    events_file = root / "tasks" / "events.jsonl"
    events_file.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(e, ensure_ascii=False) for e in events]
    events_file.write_text("\n".join(lines) + "\n" if lines else "", encoding="utf-8")
    return events_file


def _write_candidates(root: Path, filename: str, *events, blank_lines: int = 0) -> Path:
    candidates_file = root / filename
    lines = [json.dumps(e, ensure_ascii=False) for e in events]
    for _ in range(blank_lines):
        lines.append("")
    candidates_file.write_text("\n".join(lines) + "\n" if lines else "", encoding="utf-8")
    return candidates_file


def test_commit_import_pass(tmp_path):
    root = _setup_fake_root(tmp_path)
    task_id = "task-20260707-001"
    _write_task(root, task_id, status="running")
    events_file = _write_events(
        root,
        _evt("evt-20260707-001", task_id, "created", None, "planned", "c", "2026-07-07T10:00:00+08:00"),
        _evt("evt-20260707-002", task_id, "status_changed", "planned", "running", "s", "2026-07-07T10:01:00+08:00"),
    )
    _write_candidates(
        root,
        "candidates.jsonl",
        _evt("evt-20260707-003", task_id, "progress", "running", "running", "p1", "2026-07-07T10:02:00+08:00"),
        _evt("evt-20260707-004", task_id, "progress", "running", "running", "p2", "2026-07-07T10:03:00+08:00"),
    )

    result = import_events_commit(
        root,
        file="candidates.jsonl",
        tasks_file="tasks/tasks.jsonl",
        events_file="tasks/events.jsonl",
    )

    assert result.status == "pass"
    assert result.committed is True
    assert result.event_count == 2
    assert result.appended_line_count == 2
    assert result.post_validate == "pass"
    assert result.post_ledger_check == "pass"
    assert result.rolled_back is False
    content = events_file.read_text(encoding="utf-8")
    assert content.count("\n") == 4
    assert '"event_id": "evt-20260707-003"' in content
    assert '"event_id": "evt-20260707-004"' in content


def test_commit_dry_run_commit_mutually_exclusive(tmp_path, monkeypatch, capsys):
    root = _setup_fake_root(tmp_path)
    task_id = "task-20260707-001"
    _write_task(root, task_id)
    _write_candidates(
        root,
        "candidates.jsonl",
        _evt("evt-20260707-002", task_id, "created", None, "planned", "c", "2026-07-07T10:01:00+08:00"),
    )

    monkeypatch.setattr(
        "sys.argv",
        [
            "agent-runtime",
            "--root",
            str(root),
            "runtime",
            "event",
            "import",
            "--file",
            "candidates.jsonl",
            "--dry-run",
            "--commit",
        ],
    )
    assert main() == 1
    captured = capsys.readouterr()
    assert "dry-run-commit-mutually-exclusive" in captured.out


def test_commit_missing_mode_error(tmp_path, monkeypatch, capsys):
    root = _setup_fake_root(tmp_path)
    task_id = "task-20260707-001"
    _write_task(root, task_id)
    _write_candidates(
        root,
        "candidates.jsonl",
        _evt("evt-20260707-002", task_id, "created", None, "planned", "c", "2026-07-07T10:01:00+08:00"),
    )

    monkeypatch.setattr(
        "sys.argv",
        [
            "agent-runtime",
            "--root",
            str(root),
            "runtime",
            "event",
            "import",
            "--file",
            "candidates.jsonl",
        ],
    )
    assert main() == 1
    captured = capsys.readouterr()
    assert "missing-import-mode" in captured.out


def test_commit_candidate_not_found(tmp_path):
    root = _setup_fake_root(tmp_path)
    task_id = "task-20260707-001"
    _write_task(root, task_id)
    _write_events(
        root,
        _evt("evt-20260707-001", task_id, "created", None, "planned", "c", "2026-07-07T10:00:00+08:00"),
    )

    result = import_events_commit(
        root,
        file="missing.jsonl",
        tasks_file="tasks/tasks.jsonl",
        events_file="tasks/events.jsonl",
    )

    assert result.status == "error"
    assert any(f.rule_id == "candidate-not-found" for f in result.findings)


def test_commit_candidate_outside_root(tmp_path):
    root = _setup_fake_root(tmp_path)
    outside = tmp_path / "outside.jsonl"
    outside.write_text("{}", encoding="utf-8")

    result = import_events_commit(root, file=str(outside))

    assert result.status == "error"
    assert any(f.rule_id == "candidate-outside-root" for f in result.findings)


def test_commit_candidate_wrong_suffix(tmp_path):
    root = _setup_fake_root(tmp_path)
    bad = root / "candidates.txt"
    bad.write_text("{}", encoding="utf-8")

    result = import_events_commit(root, file="candidates.txt")

    assert result.status == "error"
    assert any(f.rule_id == "unsafe-candidate-file" for f in result.findings)


def test_commit_candidate_git_path(tmp_path):
    root = _setup_fake_root(tmp_path)
    git_dir = root / ".git"
    git_dir.mkdir()
    bad = git_dir / "candidates.jsonl"
    bad.write_text("{}", encoding="utf-8")

    result = import_events_commit(root, file=".git/candidates.jsonl")

    assert result.status == "error"
    assert any(f.rule_id == "unsafe-candidate-file" for f in result.findings)


def test_commit_invalid_json(tmp_path):
    root = _setup_fake_root(tmp_path)
    task_id = "task-20260707-001"
    _write_task(root, task_id)
    events_file = _write_events(
        root,
        _evt("evt-20260707-001", task_id, "created", None, "planned", "c", "2026-07-07T10:00:00+08:00"),
    )
    candidates = root / "candidates.jsonl"
    candidates.write_text("not json\n", encoding="utf-8")

    result = import_events_commit(root, file="candidates.jsonl")
    assert result.status == "validation_failed"
    assert any(f.rule_id == "invalid-json" for f in result.findings)
    assert events_file.read_text(encoding="utf-8").count("\n") == 1


def test_commit_not_object(tmp_path):
    root = _setup_fake_root(tmp_path)
    task_id = "task-20260707-001"
    _write_task(root, task_id)
    events_file = _write_events(
        root,
        _evt("evt-20260707-001", task_id, "created", None, "planned", "c", "2026-07-07T10:00:00+08:00"),
    )
    candidates = root / "candidates.jsonl"
    candidates.write_text("[1, 2, 3]\n", encoding="utf-8")

    result = import_events_commit(root, file="candidates.jsonl")
    assert result.status == "validation_failed"
    assert any(f.rule_id == "candidate-not-object" for f in result.findings)
    assert events_file.read_text(encoding="utf-8").count("\n") == 1


def test_commit_schema_invalid(tmp_path):
    root = _setup_fake_root(tmp_path)
    task_id = "task-20260707-001"
    _write_task(root, task_id)
    events_file = _write_events(
        root,
        _evt("evt-20260707-001", task_id, "created", None, "planned", "c", "2026-07-07T10:00:00+08:00"),
    )
    candidates = root / "candidates.jsonl"
    candidates.write_text(json.dumps({"event_id": "bad", "task_id": task_id}) + "\n", encoding="utf-8")

    result = import_events_commit(root, file="candidates.jsonl")
    assert result.status == "validation_failed"
    assert any(f.rule_id == "event-schema-validation-failed" for f in result.findings)
    assert events_file.read_text(encoding="utf-8").count("\n") == 1


def test_commit_duplicate_within_candidates(tmp_path):
    root = _setup_fake_root(tmp_path)
    task_id = "task-20260707-001"
    _write_task(root, task_id)
    events_file = _write_events(
        root,
        _evt("evt-20260707-001", task_id, "created", None, "planned", "c", "2026-07-07T10:00:00+08:00"),
    )
    dup_id = "evt-20260707-002"
    _write_candidates(
        root,
        "candidates.jsonl",
        _evt(dup_id, task_id, "progress", "running", "running", "p1", "2026-07-07T10:01:00+08:00"),
        _evt(dup_id, task_id, "progress", "running", "running", "p2", "2026-07-07T10:02:00+08:00"),
    )

    result = import_events_commit(root, file="candidates.jsonl")
    assert result.status == "validation_failed"
    assert any(f.rule_id == "duplicate-candidate-event-id" for f in result.findings)
    assert events_file.read_text(encoding="utf-8").count("\n") == 1


def test_commit_duplicate_with_existing_ledger(tmp_path):
    root = _setup_fake_root(tmp_path)
    task_id = "task-20260707-001"
    _write_task(root, task_id)
    events_file = _write_events(
        root,
        _evt("evt-20260707-001", task_id, "created", None, "planned", "c", "2026-07-07T10:00:00+08:00"),
    )
    _write_candidates(
        root,
        "candidates.jsonl",
        _evt("evt-20260707-001", task_id, "status_changed", "planned", "running", "s", "2026-07-07T10:01:00+08:00"),
    )

    result = import_events_commit(root, file="candidates.jsonl")
    assert result.status == "validation_failed"
    assert any(f.rule_id == "duplicate-event-id" for f in result.findings)
    assert events_file.read_text(encoding="utf-8").count("\n") == 1


def test_commit_unknown_task(tmp_path):
    root = _setup_fake_root(tmp_path)
    _write_task(root, "task-20260707-001")
    events_file = _write_events(
        root,
        _evt("evt-20260707-001", "task-20260707-001", "created", None, "planned", "c", "2026-07-07T10:00:00+08:00"),
    )
    _write_candidates(
        root,
        "candidates.jsonl",
        _evt("evt-20260707-002", "task-20260707-999", "created", None, "planned", "c", "2026-07-07T10:01:00+08:00"),
    )

    result = import_events_commit(root, file="candidates.jsonl")
    assert result.status == "validation_failed"
    assert any(f.rule_id == "unknown-task-id" for f in result.findings)
    assert events_file.read_text(encoding="utf-8").count("\n") == 1


def test_commit_illegal_transition_rolls_back(tmp_path):
    root = _setup_fake_root(tmp_path)
    task_id = "task-20260707-001"
    _write_task(root, task_id, status="finished")
    events_file = _write_events(
        root,
        _evt("evt-20260707-001", task_id, "created", None, "planned", "c", "2026-07-07T10:00:00+08:00"),
        _evt("evt-20260707-002", task_id, "finished", "planned", "finished", "done", "2026-07-07T10:01:00+08:00"),
    )
    original_size = events_file.stat().st_size
    _write_candidates(
        root,
        "candidates.jsonl",
        _evt("evt-20260707-003", task_id, "status_changed", "finished", "running", "back", "2026-07-07T10:02:00+08:00"),
    )

    result = import_events_commit(root, file="candidates.jsonl")
    assert result.status == "validation_failed"
    assert any(f.rule_id == "terminal-status-reverted" for f in result.findings)
    assert result.committed is False
    assert result.rolled_back is False  # preflight failure, no write happened
    assert events_file.stat().st_size == original_size


def test_commit_secret_blocked(tmp_path):
    root = _setup_fake_root(tmp_path)
    task_id = "task-20260707-001"
    _write_task(root, task_id)
    events_file = _write_events(
        root,
        _evt("evt-20260707-001", task_id, "created", None, "planned", "c", "2026-07-07T10:00:00+08:00"),
    )
    token = "ghp_" + "X" * 36
    _write_candidates(
        root,
        "candidates.jsonl",
        _evt("evt-20260707-002", task_id, "progress", "running", "running", token, "2026-07-07T10:01:00+08:00"),
    )

    result = import_events_commit(root, file="candidates.jsonl")
    assert result.status == "blocked"
    rendered = result.render_json()
    assert token not in rendered
    assert events_file.read_text(encoding="utf-8").count("\n") == 1


def test_commit_public_scan_blocked(tmp_path):
    root = _setup_fake_root(tmp_path)
    task_id = "task-20260707-001"
    _write_task(root, task_id)
    events_file = _write_events(
        root,
        _evt("evt-20260707-001", task_id, "created", None, "planned", "c", "2026-07-07T10:00:00+08:00"),
    )
    sensitive_path = "C:" + "\\secret.txt"
    _write_candidates(
        root,
        "candidates.jsonl",
        _evt("evt-20260707-002", task_id, "progress", "running", "running", "report at " + sensitive_path, "2026-07-07T10:01:00+08:00"),
    )

    result = import_events_commit(root, file="candidates.jsonl")
    assert result.status == "blocked"
    rendered = result.render_json()
    assert sensitive_path not in rendered
    assert events_file.read_text(encoding="utf-8").count("\n") == 1


def test_commit_events_file_not_exists_blocked(tmp_path):
    root = _setup_fake_root(tmp_path)
    task_id = "task-20260707-001"
    _write_task(root, task_id)
    _write_candidates(
        root,
        "candidates.jsonl",
        _evt("evt-20260707-001", task_id, "created", None, "planned", "c", "2026-07-07T10:01:00+08:00"),
    )

    result = import_events_commit(
        root,
        file="candidates.jsonl",
        tasks_file="tasks/tasks.jsonl",
        events_file="tasks/events.jsonl",
    )

    assert result.status == "blocked"
    assert any(f.rule_id == "events-file-not-found" for f in result.findings)


def test_commit_events_file_missing_trailing_newline_blocked(tmp_path):
    root = _setup_fake_root(tmp_path)
    task_id = "task-20260707-001"
    _write_task(root, task_id, status="running")
    events_file = root / "tasks" / "events.jsonl"
    events_file.parent.mkdir(parents=True, exist_ok=True)
    # Deliberately omit trailing newline.
    events_file.write_text(
        json.dumps(_evt("evt-20260707-001", task_id, "created", None, "planned", "c", "2026-07-07T10:00:00+08:00"))
        + "\n"
        + json.dumps(_evt("evt-20260707-002", task_id, "status_changed", "planned", "running", "s", "2026-07-07T10:01:00+08:00")),
        encoding="utf-8",
    )
    _write_candidates(
        root,
        "candidates.jsonl",
        _evt("evt-20260707-003", task_id, "progress", "running", "running", "p", "2026-07-07T10:02:00+08:00"),
    )

    result = import_events_commit(root, file="candidates.jsonl")
    assert result.status == "blocked"
    assert any(f.rule_id == "events-file-missing-trailing-newline" for f in result.findings)
    content = events_file.read_bytes()
    assert not content.endswith(b"\n")


def test_commit_post_check_validate_failure_rolls_back(tmp_path):
    root = _setup_fake_root(tmp_path)
    task_id = "task-20260707-001"
    _write_task(root, task_id, status="running")
    events_file = _write_events(
        root,
        _evt("evt-20260707-001", task_id, "created", None, "planned", "c", "2026-07-07T10:00:00+08:00"),
    )
    _write_candidates(
        root,
        "candidates.jsonl",
        _evt("evt-20260707-002", task_id, "status_changed", "planned", "running", "s", "2026-07-07T10:01:00+08:00"),
    )
    original_size = events_file.stat().st_size
    call_count = 0

    def _failing_validate(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        from agent_runtime.result import CheckResult, Finding
        from agent_runtime.task_validation import validate_records

        # First call is preflight simulation; subsequent calls are post-check.
        if call_count > 1:
            return CheckResult(
                status="validation_failed",
                findings=[Finding(rule_id="post-validate-failure", severity="error", action="error", message="simulated")],
                next_action="rollback",
            )
        return validate_records(*args, **kwargs)

    with patch("agent_runtime.runtime_event_import.validate_records", side_effect=_failing_validate):
        result = import_events_commit(
            root,
            file="candidates.jsonl",
            tasks_file="tasks/tasks.jsonl",
            events_file="tasks/events.jsonl",
        )

    assert result.status == "validation_failed"
    assert result.committed is False
    assert result.rolled_back is True
    assert result.post_validate == "validation_failed"
    assert events_file.stat().st_size == original_size
    assert events_file.read_text(encoding="utf-8").count("\n") == 1


def test_commit_post_check_ledger_failure_rolls_back(tmp_path):
    root = _setup_fake_root(tmp_path)
    task_id = "task-20260707-001"
    _write_task(root, task_id, status="running")
    events_file = _write_events(
        root,
        _evt("evt-20260707-001", task_id, "created", None, "planned", "c", "2026-07-07T10:00:00+08:00"),
    )
    _write_candidates(
        root,
        "candidates.jsonl",
        _evt("evt-20260707-002", task_id, "status_changed", "planned", "running", "s", "2026-07-07T10:01:00+08:00"),
    )
    original_size = events_file.stat().st_size
    call_count = 0

    def _failing_ledger(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        from agent_runtime.result import CheckResult, Finding
        from agent_runtime.ledger_consistency import check_ledger_consistency

        # First call is preflight simulation; subsequent calls are post-check.
        if call_count > 1:
            return CheckResult(
                status="validation_failed",
                findings=[Finding(rule_id="post-ledger-failure", severity="error", action="error", message="simulated")],
                next_action="rollback",
            )
        return check_ledger_consistency(*args, **kwargs)

    with patch("agent_runtime.runtime_event_import.check_ledger_consistency", side_effect=_failing_ledger):
        result = import_events_commit(
            root,
            file="candidates.jsonl",
            tasks_file="tasks/tasks.jsonl",
            events_file="tasks/events.jsonl",
        )

    assert result.status == "validation_failed"
    assert result.committed is False
    assert result.rolled_back is True
    assert result.post_ledger_check == "validation_failed"
    assert events_file.stat().st_size == original_size
    assert events_file.read_text(encoding="utf-8").count("\n") == 1


def test_commit_write_error_rolls_back(tmp_path):
    root = _setup_fake_root(tmp_path)
    task_id = "task-20260707-001"
    _write_task(root, task_id, status="running")
    events_file = _write_events(
        root,
        _evt("evt-20260707-001", task_id, "created", None, "planned", "c", "2026-07-07T10:00:00+08:00"),
    )
    _write_candidates(
        root,
        "candidates.jsonl",
        _evt("evt-20260707-002", task_id, "status_changed", "planned", "running", "s", "2026-07-07T10:01:00+08:00"),
    )
    original_size = events_file.stat().st_size

    import builtins

    real_open = builtins.open

    def _failing_open(*args, **kwargs):
        mode = kwargs.get("mode") or (args[1] if len(args) >= 2 else None)
        if mode == "a":
            raise OSError("simulated append failure")
        return real_open(*args, **kwargs)

    with patch("builtins.open", side_effect=_failing_open):
        result = import_events_commit(
            root,
            file="candidates.jsonl",
            tasks_file="tasks/tasks.jsonl",
            events_file="tasks/events.jsonl",
        )

    assert result.status == "error"
    assert result.committed is False
    assert result.rolled_back is True
    assert events_file.stat().st_size == original_size


def test_commit_rollback_failure_reports_error(tmp_path):
    root = _setup_fake_root(tmp_path)
    task_id = "task-20260707-001"
    _write_task(root, task_id, status="running")
    events_file = _write_events(
        root,
        _evt("evt-20260707-001", task_id, "created", None, "planned", "c", "2026-07-07T10:00:00+08:00"),
    )
    _write_candidates(
        root,
        "candidates.jsonl",
        _evt("evt-20260707-002", task_id, "status_changed", "planned", "running", "s", "2026-07-07T10:01:00+08:00"),
    )

    def _failing_validate(*args, **kwargs):
        from agent_runtime.result import CheckResult, Finding
        from agent_runtime.task_validation import validate_records

        if _failing_validate.call_count > 0:
            _failing_validate.call_count += 1
            return CheckResult(
                status="validation_failed",
                findings=[Finding(rule_id="post-validate-failure", severity="error", action="error", message="simulated")],
                next_action="rollback",
            )
        _failing_validate.call_count += 1
        return validate_records(*args, **kwargs)

    _failing_validate.call_count = 0

    with patch("agent_runtime.runtime_event_import.validate_records", side_effect=_failing_validate):
        with patch(
            "agent_runtime.runtime_event_import._rollback_events_file",
            return_value=(False, "simulated rollback failure"),
        ):
            result = import_events_commit(
                root,
                file="candidates.jsonl",
                tasks_file="tasks/tasks.jsonl",
                events_file="tasks/events.jsonl",
            )

    assert result.status == "error"
    assert result.committed is False
    assert result.rolled_back is False
    assert result.rollback_error == "simulated rollback failure"


def test_commit_does_not_modify_task_ledger(tmp_path):
    root = _setup_fake_root(tmp_path)
    task_id = "task-20260707-001"
    tasks_file = _write_task(root, task_id, status="running")
    events_file = _write_events(
        root,
        _evt("evt-20260707-001", task_id, "created", None, "planned", "c", "2026-07-07T10:00:00+08:00"),
    )
    original_tasks = tasks_file.read_text(encoding="utf-8")
    _write_candidates(
        root,
        "candidates.jsonl",
        _evt("evt-20260707-002", task_id, "status_changed", "planned", "running", "s", "2026-07-07T10:01:00+08:00"),
    )

    result = import_events_commit(root, file="candidates.jsonl")
    assert result.status == "pass"
    assert result.committed is True
    assert tasks_file.read_text(encoding="utf-8") == original_tasks
    assert events_file.read_text(encoding="utf-8").count("\n") == 2


def test_commit_json_output_sanitized(tmp_path, monkeypatch, capsys):
    root = _setup_fake_root(tmp_path)
    task_id = "task-20260707-001"
    _write_task(root, task_id, status="running")
    _write_events(
        root,
        _evt("evt-20260707-001", task_id, "created", None, "planned", "c", "2026-07-07T10:00:00+08:00"),
    )
    message = "progress message with sensitive details"
    _write_candidates(
        root,
        "candidates.jsonl",
        _evt("evt-20260707-002", task_id, "progress", "running", "running", message, "2026-07-07T10:01:00+08:00"),
    )

    monkeypatch.setattr(
        "sys.argv",
        [
            "agent-runtime",
            "--root",
            str(root),
            "runtime",
            "event",
            "import",
            "--file",
            "candidates.jsonl",
            "--commit",
            "--json",
        ],
    )
    assert main() == 0
    captured = capsys.readouterr()
    out = json.loads(captured.out)
    assert out["status"] == "pass"
    assert out["committed"] is True
    assert message not in captured.out
