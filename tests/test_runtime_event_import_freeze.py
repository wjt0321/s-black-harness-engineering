"""Tests for runtime event import consistency-freeze fields and checks."""

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


def test_dry_run_outputs_freeze_fields(tmp_path):
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

    result = import_events_dry_run(
        root,
        file="candidates.jsonl",
        tasks_file="tasks/tasks.jsonl",
        events_file="tasks/events.jsonl",
    )

    assert result.status == "pass"
    assert result.plan_hash is not None and result.plan_hash.startswith("sha256:")
    assert result.candidate_fingerprint is not None and result.candidate_fingerprint.startswith("sha256:")
    assert result.events_ledger_exists is True
    assert result.events_ledger_fingerprint is not None and result.events_ledger_fingerprint.startswith("sha256:")
    assert result.events_ledger_size_bytes > 0
    assert result.events_ledger_line_count == 1
    assert result.freeze_mode == "advisory"


def test_dry_run_plan_hash_is_stable(tmp_path):
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

    result1 = import_events_dry_run(root, file="candidates.jsonl")
    result2 = import_events_dry_run(root, file="candidates.jsonl")

    assert result1.plan_hash == result2.plan_hash
    assert result1.candidate_fingerprint == result2.candidate_fingerprint
    assert result1.events_ledger_fingerprint == result2.events_ledger_fingerprint


def test_plan_hash_changes_when_candidate_changes(tmp_path):
    root = _setup_fake_root(tmp_path)
    task_id = "task-20260707-001"
    _write_task(root, task_id, status="running")
    _write_events(
        root,
        _evt("evt-20260707-001", task_id, "created", None, "planned", "c", "2026-07-07T10:00:00+08:00"),
    )
    candidates = root / "candidates.jsonl"
    candidates.write_text(
        json.dumps(_evt("evt-20260707-002", task_id, "status_changed", "planned", "running", "s", "2026-07-07T10:01:00+08:00"), ensure_ascii=False)
        + "\n",
        encoding="utf-8",
    )

    result1 = import_events_dry_run(root, file="candidates.jsonl")

    candidates.write_text(
        json.dumps(_evt("evt-20260707-002", task_id, "status_changed", "planned", "running", "changed", "2026-07-07T10:01:00+08:00"), ensure_ascii=False)
        + "\n",
        encoding="utf-8",
    )

    result2 = import_events_dry_run(root, file="candidates.jsonl")

    assert result1.plan_hash != result2.plan_hash
    assert result1.candidate_fingerprint != result2.candidate_fingerprint


def test_plan_hash_changes_when_events_ledger_changes(tmp_path):
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

    result1 = import_events_dry_run(root, file="candidates.jsonl")

    # Append a new event to the ledger to change its fingerprint.
    events_file.write_text(
        events_file.read_text(encoding="utf-8")
        + json.dumps(_evt("evt-20260707-003", task_id, "progress", "running", "running", "p", "2026-07-07T10:02:00+08:00"), ensure_ascii=False)
        + "\n",
        encoding="utf-8",
    )

    result2 = import_events_dry_run(root, file="candidates.jsonl")

    assert result1.events_ledger_fingerprint != result2.events_ledger_fingerprint
    assert result1.plan_hash != result2.plan_hash
    assert result2.events_ledger_line_count == 2


def test_commit_with_expected_plan_hash_passes(tmp_path):
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
    )

    assert result.status == "pass"
    assert result.committed is True
    assert result.freeze_check == "pass"
    assert result.expected_plan_hash == expected
    assert result.current_plan_hash == expected


def test_commit_blocked_when_candidate_changed_after_dry_run(tmp_path):
    root = _setup_fake_root(tmp_path)
    task_id = "task-20260707-001"
    _write_task(root, task_id, status="running")
    _write_events(
        root,
        _evt("evt-20260707-001", task_id, "created", None, "planned", "c", "2026-07-07T10:00:00+08:00"),
    )
    candidates = root / "candidates.jsonl"
    candidates.write_text(
        json.dumps(_evt("evt-20260707-002", task_id, "status_changed", "planned", "running", "s", "2026-07-07T10:01:00+08:00"), ensure_ascii=False)
        + "\n",
        encoding="utf-8",
    )

    dry_run = import_events_dry_run(root, file="candidates.jsonl")
    expected = dry_run.plan_hash

    # Mutate candidate after dry-run.
    candidates.write_text(
        json.dumps(_evt("evt-20260707-002", task_id, "status_changed", "planned", "running", "changed", "2026-07-07T10:01:00+08:00"), ensure_ascii=False)
        + "\n",
        encoding="utf-8",
    )

    result = import_events_commit(
        root,
        file="candidates.jsonl",
        tasks_file="tasks/tasks.jsonl",
        events_file="tasks/events.jsonl",
        expected_plan_hash=expected,
    )

    assert result.status == "blocked"
    assert result.committed is False
    assert result.freeze_check == "failed"
    assert result.expected_plan_hash == expected
    assert result.current_plan_hash != expected
    assert any(f.rule_id == "plan-hash-mismatch" for f in result.findings)


def test_commit_blocked_when_events_ledger_changed_after_dry_run(tmp_path):
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

    dry_run = import_events_dry_run(root, file="candidates.jsonl")
    expected = dry_run.plan_hash

    # Mutate events ledger after dry-run.
    events_file.write_text(
        events_file.read_text(encoding="utf-8")
        + json.dumps(_evt("evt-20260707-003", task_id, "progress", "running", "running", "p", "2026-07-07T10:02:00+08:00"), ensure_ascii=False)
        + "\n",
        encoding="utf-8",
    )

    result = import_events_commit(
        root,
        file="candidates.jsonl",
        tasks_file="tasks/tasks.jsonl",
        events_file="tasks/events.jsonl",
        expected_plan_hash=expected,
    )

    assert result.status == "blocked"
    assert result.committed is False
    assert result.freeze_check == "failed"
    assert result.current_plan_hash != expected


def test_freeze_mismatch_output_does_not_leak_candidate_content(tmp_path):
    root = _setup_fake_root(tmp_path)
    task_id = "task-20260707-001"
    _write_task(root, task_id, status="running")
    _write_events(
        root,
        _evt("evt-20260707-001", task_id, "created", None, "planned", "c", "2026-07-07T10:00:00+08:00"),
    )
    message = "super secret progress message"
    candidates = root / "candidates.jsonl"
    candidates.write_text(
        json.dumps(_evt("evt-20260707-002", task_id, "status_changed", "planned", "running", message, "2026-07-07T10:01:00+08:00"), ensure_ascii=False)
        + "\n",
        encoding="utf-8",
    )

    dry_run = import_events_dry_run(root, file="candidates.jsonl")
    expected = dry_run.plan_hash

    candidates.write_text(
        json.dumps(_evt("evt-20260707-002", task_id, "status_changed", "planned", "running", "changed", "2026-07-07T10:01:00+08:00"), ensure_ascii=False)
        + "\n",
        encoding="utf-8",
    )

    result = import_events_commit(
        root,
        file="candidates.jsonl",
        tasks_file="tasks/tasks.jsonl",
        events_file="tasks/events.jsonl",
        expected_plan_hash=expected,
    )

    rendered = result.render_json()
    assert result.status == "blocked"
    assert message not in rendered
    assert "changed" not in rendered
    assert "plan-hash-mismatch" in rendered


def test_commit_without_expected_plan_hash_behaves_as_before(tmp_path):
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

    result = import_events_commit(root, file="candidates.jsonl")

    assert result.status == "pass"
    assert result.committed is True
    assert result.freeze_check is None
    assert result.expected_plan_hash is None
    assert result.current_plan_hash is None


def test_cli_json_output_includes_freeze_fields_and_no_secrets(tmp_path, monkeypatch, capsys):
    root = _setup_fake_root(tmp_path)
    task_id = "task-20260707-001"
    _write_task(root, task_id, status="running")
    _write_events(
        root,
        _evt("evt-20260707-001", task_id, "created", None, "planned", "c", "2026-07-07T10:00:00+08:00"),
    )
    message = "sensitive details in candidate"
    _write_candidates(
        root,
        "candidates.jsonl",
        _evt("evt-20260707-002", task_id, "status_changed", "planned", "running", message, "2026-07-07T10:01:00+08:00"),
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
            "--json",
        ],
    )
    assert main() == 0
    captured = capsys.readouterr()
    out = json.loads(captured.out)

    assert out["status"] == "pass"
    assert out["freeze_mode"] == "advisory"
    assert out["plan_hash"].startswith("sha256:")
    assert out["candidate_fingerprint"].startswith("sha256:")
    assert out["events_ledger_fingerprint"].startswith("sha256:")
    assert out["events_ledger_size_bytes"] > 0
    assert out["events_ledger_line_count"] == 1
    assert message not in captured.out
