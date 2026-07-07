"""Tests for runtime event import strict freeze mode (--require-dry-run)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from agent_runtime.cli import main
from agent_runtime.runtime_event_import import import_events_commit, import_events_dry_run

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


def _write_candidates(root: Path, filename: str, *events) -> Path:
    candidates_file = root / filename
    lines = [json.dumps(e, ensure_ascii=False) for e in events]
    candidates_file.write_text("\n".join(lines) + "\n" if lines else "", encoding="utf-8")
    return candidates_file


def test_require_dry_run_missing_expected_hash_returns_error(tmp_path):
    root = _setup_fake_root(tmp_path)
    task_id = "task-20260707-001"
    _write_task(root, task_id, status="running")
    _write_events(
        root,
        _evt("evt-20260707-001", task_id, "created", None, "planned", "c", "2026-07-07T10:00:00+08:00"),
    )
    _write_candidates(
        root,
        "candidates.jsonl",
        _evt("evt-20260707-002", task_id, "status_changed", "planned", "running", "s", "2026-07-07T10:01:00+08:00"),
    )

    result = import_events_commit(
        root,
        file="candidates.jsonl",
        tasks_file="tasks/tasks.jsonl",
        events_file="tasks/events.jsonl",
        require_dry_run=True,
    )

    assert result.status == "error"
    assert result.committed is False
    assert any(f.rule_id == "missing-expected-plan-hash" for f in result.findings)


def test_cli_require_dry_run_with_dry_run_returns_error(tmp_path, monkeypatch, capsys):
    root = _setup_fake_root(tmp_path)
    task_id = "task-20260707-001"
    _write_task(root, task_id, status="running")
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
            "--require-dry-run",
        ],
    )
    assert main() == 1
    captured = capsys.readouterr()
    assert "require-dry-run-with-dry-run" in captured.out


def test_require_dry_run_commit_with_correct_hash_passes(tmp_path):
    root = _setup_fake_root(tmp_path)
    task_id = "task-20260707-001"
    _write_task(root, task_id, status="running")
    _write_events(
        root,
        _evt("evt-20260707-001", task_id, "created", None, "planned", "c", "2026-07-07T10:00:00+08:00"),
    )
    _write_candidates(
        root,
        "candidates.jsonl",
        _evt("evt-20260707-002", task_id, "status_changed", "planned", "running", "s", "2026-07-07T10:01:00+08:00"),
    )

    dry_run = import_events_dry_run(root, file="candidates.jsonl")
    expected = dry_run.plan_hash

    result = import_events_commit(
        root,
        file="candidates.jsonl",
        tasks_file="tasks/tasks.jsonl",
        events_file="tasks/events.jsonl",
        expected_plan_hash=expected,
        require_dry_run=True,
    )

    assert result.status == "pass"
    assert result.committed is True
    assert result.freeze_check == "pass"
    assert result.expected_plan_hash == expected
    assert result.current_plan_hash == expected


def test_require_dry_run_commit_with_stale_hash_blocked_and_ledger_unchanged(tmp_path):
    root = _setup_fake_root(tmp_path)
    task_id = "task-20260707-001"
    _write_task(root, task_id, status="running")
    events_file = _write_events(
        root,
        _evt("evt-20260707-001", task_id, "created", None, "planned", "c", "2026-07-07T10:00:00+08:00"),
    )
    candidates = root / "candidates.jsonl"
    candidates.write_text(
        json.dumps(
            _evt("evt-20260707-002", task_id, "status_changed", "planned", "running", "s", "2026-07-07T10:01:00+08:00"),
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    dry_run = import_events_dry_run(root, file="candidates.jsonl")
    expected = dry_run.plan_hash
    original_ledger = events_file.read_bytes()

    # Mutate candidate after dry-run to make the hash stale.
    candidates.write_text(
        json.dumps(
            _evt("evt-20260707-002", task_id, "status_changed", "planned", "running", "changed", "2026-07-07T10:01:00+08:00"),
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    result = import_events_commit(
        root,
        file="candidates.jsonl",
        tasks_file="tasks/tasks.jsonl",
        events_file="tasks/events.jsonl",
        expected_plan_hash=expected,
        require_dry_run=True,
    )

    assert result.status == "blocked"
    assert result.committed is False
    assert result.freeze_check == "failed"
    assert result.expected_plan_hash == expected
    assert result.current_plan_hash != expected
    assert any(f.rule_id == "plan-hash-mismatch" for f in result.findings)
    assert events_file.read_bytes() == original_ledger


def test_require_dry_run_commit_stale_hash_output_sanitized(tmp_path, monkeypatch, capsys):
    root = _setup_fake_root(tmp_path)
    task_id = "task-20260707-001"
    _write_task(root, task_id, status="running")
    _write_events(
        root,
        _evt("evt-20260707-001", task_id, "created", None, "planned", "c", "2026-07-07T10:00:00+08:00"),
    )
    message = "super secret candidate message"
    candidates = root / "candidates.jsonl"
    candidates.write_text(
        json.dumps(
            _evt("evt-20260707-002", task_id, "status_changed", "planned", "running", message, "2026-07-07T10:01:00+08:00"),
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    dry_run_json, code = _run_cli(
        monkeypatch,
        capsys,
        root,
        ["runtime", "event", "import", "--file", "candidates.jsonl", "--dry-run", "--json"],
    )
    assert code == 0
    expected = json.loads(dry_run_json)["plan_hash"]

    candidates.write_text(
        json.dumps(
            _evt("evt-20260707-002", task_id, "status_changed", "planned", "running", "changed", "2026-07-07T10:01:00+08:00"),
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    out, code = _run_cli(
        monkeypatch,
        capsys,
        root,
        [
            "runtime",
            "event",
            "import",
            "--file",
            "candidates.jsonl",
            "--commit",
            "--require-dry-run",
            "--expected-plan-hash",
            expected,
            "--json",
        ],
    )
    assert code == 2
    assert message not in out
    assert "changed" not in out
    assert "plan-hash-mismatch" in out
    assert "freeze_check" in out


def test_commit_without_require_dry_run_keeps_existing_behavior(tmp_path):
    root = _setup_fake_root(tmp_path)
    task_id = "task-20260707-001"
    _write_task(root, task_id, status="running")
    _write_events(
        root,
        _evt("evt-20260707-001", task_id, "created", None, "planned", "c", "2026-07-07T10:00:00+08:00"),
    )
    _write_candidates(
        root,
        "candidates.jsonl",
        _evt("evt-20260707-002", task_id, "status_changed", "planned", "running", "s", "2026-07-07T10:01:00+08:00"),
    )

    # With expected hash but no require-dry-run should still succeed.
    dry_run = import_events_dry_run(root, file="candidates.jsonl")
    result = import_events_commit(
        root,
        file="candidates.jsonl",
        tasks_file="tasks/tasks.jsonl",
        events_file="tasks/events.jsonl",
        expected_plan_hash=dry_run.plan_hash,
    )
    assert result.status == "pass"
    assert result.committed is True
    assert result.freeze_check == "pass"

    # Without any freeze parameters should still succeed.
    _write_events(
        root,
        _evt("evt-20260707-001", task_id, "created", None, "planned", "c", "2026-07-07T10:00:00+08:00"),
    )
    result2 = import_events_commit(root, file="candidates.jsonl")
    assert result2.status == "pass"
    assert result2.committed is True
    assert result2.freeze_check is None


def _run_cli(monkeypatch, capsys, root: Path, argv: list[str]) -> tuple[str, int]:
    monkeypatch.setattr("sys.argv", ["agent-runtime", "--root", str(root), *argv])
    code = main()
    captured = capsys.readouterr()
    return captured.out, code
