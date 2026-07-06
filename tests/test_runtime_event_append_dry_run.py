"""Tests for runtime event append --dry-run.

All tests run in temporary directories and assert that no real ledger files
are modified.
"""

from __future__ import annotations

import io
import json
import shutil
from pathlib import Path

import pytest

from agent_runtime.cli import main
from agent_runtime.runtime_event_append import append_event_dry_run

ROOT = Path(__file__).resolve().parents[1]


def _setup_fake_root(tmp_path: Path) -> Path:
    """Create a fake project root with the schemas and policies needed."""
    fake_root = tmp_path / "project"
    fake_root.mkdir(parents=True, exist_ok=True)

    for src_rel in (
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


def _write_events(root: Path, task_id: str, *events) -> Path:
    events_file = root / "tasks" / "events.jsonl"
    events_file.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(e, ensure_ascii=False) for e in events]
    events_file.write_text("\n".join(lines) + "\n" if lines else "", encoding="utf-8")
    return events_file


def test_append_event_dry_run_pass(tmp_path):
    root = _setup_fake_root(tmp_path)
    task_id = "task-20260705-001"
    _write_task(root, task_id, status="running")
    events_file = _write_events(
        root,
        task_id,
        _evt("evt-20260705-001", task_id, "created", None, "planned", "c", "2026-07-05T10:00:00+08:00"),
        _evt("evt-20260705-002", task_id, "status_changed", "planned", "running", "s", "2026-07-05T10:01:00+08:00"),
    )
    candidate = _evt("evt-20260705-003", task_id, "progress", "running", "running", "p", "2026-07-05T10:02:00+08:00")

    result = append_event_dry_run(
        root,
        file=None,
        stdin=False,
        dry_run=True,
        tasks_file="tasks/tasks.jsonl",
        events_file="tasks/events.jsonl",
        envelope_file=None,
        candidate=candidate,
    )

    assert result.status == "pass"
    assert result.event_id == "evt-20260705-003"
    assert result.task_id == task_id
    assert result.event_type == "progress"
    assert result.would_append is False
    assert result.ledger_check == "pass"
    assert result.next_action is not None
    assert events_file.read_text(encoding="utf-8").count("\n") == 2


def test_append_event_dry_run_missing_task(tmp_path):
    root = _setup_fake_root(tmp_path)
    _write_task(root, "task-20260705-001", status="running")
    candidate = _evt("evt-20260705-002", "task-20260705-999", "created", None, "planned", "c", "2026-07-05T10:00:00+08:00")

    result = append_event_dry_run(
        root,
        file=None,
        stdin=False,
        dry_run=True,
        tasks_file="tasks/tasks.jsonl",
        events_file="tasks/events.jsonl",
        envelope_file=None,
        candidate=candidate,
    )

    assert result.status == "error"
    assert any(f.rule_id == "unknown-task-id" for f in result.findings)


def test_append_event_dry_run_schema_invalid(tmp_path):
    root = _setup_fake_root(tmp_path)
    task_id = "task-20260705-001"
    _write_task(root, task_id, status="running")
    candidate = {"event_id": "bad", "task_id": task_id}

    result = append_event_dry_run(
        root,
        file=None,
        stdin=False,
        dry_run=True,
        tasks_file="tasks/tasks.jsonl",
        events_file="tasks/events.jsonl",
        envelope_file=None,
        candidate=candidate,
    )

    assert result.status == "validation_failed"
    assert any(f.rule_id == "event-schema-validation-failed" for f in result.findings)


def test_append_event_dry_run_illegal_transition(tmp_path):
    root = _setup_fake_root(tmp_path)
    task_id = "task-20260705-001"
    _write_task(root, task_id, status="finished")
    _write_events(
        root,
        task_id,
        _evt("evt-20260705-001", task_id, "created", None, "planned", "c", "2026-07-05T10:00:00+08:00"),
        _evt("evt-20260705-002", task_id, "finished", "planned", "finished", "done", "2026-07-05T10:01:00+08:00"),
    )
    candidate = _evt("evt-20260705-003", task_id, "status_changed", "finished", "running", "back", "2026-07-05T10:02:00+08:00")

    result = append_event_dry_run(
        root,
        file=None,
        stdin=False,
        dry_run=True,
        tasks_file="tasks/tasks.jsonl",
        events_file="tasks/events.jsonl",
        envelope_file=None,
        candidate=candidate,
    )

    assert result.status == "validation_failed"


def test_append_event_dry_run_secret_blocked(tmp_path):
    root = _setup_fake_root(tmp_path)
    task_id = "task-20260705-001"
    _write_task(root, task_id, status="running")
    token = "ghp_" + "X" * 36
    candidate = _evt("evt-20260705-002", task_id, "progress", "running", "running", token, "2026-07-05T10:02:00+08:00")

    result = append_event_dry_run(
        root,
        file=None,
        stdin=False,
        dry_run=True,
        tasks_file="tasks/tasks.jsonl",
        events_file="tasks/events.jsonl",
        envelope_file=None,
        candidate=candidate,
    )

    assert result.status == "blocked"
    rendered = result.render_json()
    assert token not in rendered


def test_cli_file_dry_run_pass(tmp_path, monkeypatch, capsys):
    root = _setup_fake_root(tmp_path)
    task_id = "task-20260705-001"
    _write_task(root, task_id, status="running")
    events_file = _write_events(
        root,
        task_id,
        _evt("evt-20260705-001", task_id, "created", None, "planned", "c", "2026-07-05T10:00:00+08:00"),
    )
    candidate_file = root / "candidate.json"
    candidate_file.write_text(
        json.dumps(
            _evt("evt-20260705-002", task_id, "status_changed", "planned", "running", "s", "2026-07-05T10:01:00+08:00"),
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "sys.argv",
        ["agent-runtime", "--root", str(root), "runtime", "event", "append", "--file", str(candidate_file), "--dry-run"],
    )
    assert main() == 0
    captured = capsys.readouterr()
    assert "PASS" in captured.out
    assert events_file.read_text(encoding="utf-8").count("\n") == 1


def test_cli_stdin_dry_run_pass(tmp_path, monkeypatch, capsys):
    root = _setup_fake_root(tmp_path)
    task_id = "task-20260705-001"
    _write_task(root, task_id, status="running")
    events_file = _write_events(
        root,
        task_id,
        _evt("evt-20260705-001", task_id, "created", None, "planned", "c", "2026-07-05T10:00:00+08:00"),
    )
    payload = json.dumps(
        _evt("evt-20260705-002", task_id, "status_changed", "planned", "running", "s", "2026-07-05T10:01:00+08:00"),
        ensure_ascii=False,
    )
    monkeypatch.setattr("sys.stdin", io.StringIO(payload))
    monkeypatch.setattr(
        "sys.argv",
        ["agent-runtime", "--root", str(root), "runtime", "event", "append", "--stdin", "--dry-run"],
    )
    assert main() == 0
    captured = capsys.readouterr()
    assert "PASS" in captured.out
    assert events_file.read_text(encoding="utf-8").count("\n") == 1


def test_cli_missing_dry_run(tmp_path, monkeypatch, capsys):
    root = _setup_fake_root(tmp_path)
    task_id = "task-20260705-001"
    _write_task(root, task_id, status="running")
    candidate_file = root / "candidate.json"
    candidate_file.write_text(
        json.dumps(
            _evt("evt-20260705-002", task_id, "status_changed", "planned", "running", "s", "2026-07-05T10:01:00+08:00"),
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "sys.argv",
        ["agent-runtime", "--root", str(root), "runtime", "event", "append", "--file", str(candidate_file)],
    )
    assert main() == 1
    captured = capsys.readouterr()
    assert "missing-append-mode" in captured.out


def test_cli_json_output_sanitized(tmp_path, monkeypatch, capsys):
    root = _setup_fake_root(tmp_path)
    task_id = "task-20260705-001"
    _write_task(root, task_id, status="running")
    _write_events(
        root,
        task_id,
        _evt("evt-20260705-001", task_id, "created", None, "planned", "c", "2026-07-05T10:00:00+08:00"),
    )
    message = "progress message with details"
    candidate_file = root / "candidate.json"
    candidate_file.write_text(
        json.dumps(
            _evt("evt-20260705-002", task_id, "progress", "running", "running", message, "2026-07-05T10:01:00+08:00"),
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "sys.argv",
        ["agent-runtime", "--root", str(root), "runtime", "event", "append", "--file", str(candidate_file), "--dry-run", "--json"],
    )
    assert main() == 0
    captured = capsys.readouterr()
    out = json.loads(captured.out)
    assert out["status"] == "pass"
    assert message not in captured.out


def test_cli_with_envelope_runtime_audit(tmp_path, monkeypatch, capsys):
    root = _setup_fake_root(tmp_path)
    task_id = "task-20260705-001"
    _write_task(root, task_id, status="running")
    _write_events(
        root,
        task_id,
        _evt("evt-20260705-001", task_id, "created", None, "planned", "c", "2026-07-05T10:00:00+08:00"),
    )
    candidate_file = root / "candidate.json"
    candidate_file.write_text(
        json.dumps(
            _evt("evt-20260705-002", task_id, "progress", "running", "running", "p", "2026-07-05T10:01:00+08:00"),
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    envelope_file = root / "envelope.json"
    envelope_file.write_text(
        json.dumps(
            {
                "version": 1,
                "description": "test envelope",
                "artifacts": [
                    {
                        "artifact_type": "adapter_request",
                        "request_id": "req-20260705-001",
                        "task_id": task_id,
                        "adapter_id": "github-cli",
                        "operation": "git_status",
                        "actor": "cli",
                        "target": "origin/main",
                        "input": {},
                        "context": {
                            "source": "cli",
                            "policy_profile": "all",
                            "risk_level": "local",
                            "dry_run": True,
                            "requires_approval": False,
                        },
                        "preflight": {"status": "pass", "findings": []},
                        "created_at": "2026-07-05T10:00:00+08:00",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "sys.argv",
        [
            "agent-runtime",
            "--root",
            str(root),
            "runtime",
            "event",
            "append",
            "--file",
            str(candidate_file),
            "--dry-run",
            "--envelope",
            str(envelope_file),
        ],
    )
    assert main() == 0
    captured = capsys.readouterr()
    assert "PASS" in captured.out


def test_runtime_event_append_cli_outputs_safe_summary(capsys, tmp_path):
    root = _setup_fake_root(tmp_path)
    task_id = "task-20260705-001"
    _write_task(root, task_id, status="running")
    _write_events(
        root,
        task_id,
        _evt("evt-20260705-001", task_id, "created", None, "planned", "created", "2026-07-05T10:00:00+08:00"),
        _evt("evt-20260705-002", task_id, "status_changed", "planned", "running", "started", "2026-07-05T10:01:00+08:00"),
    )
    candidate = _evt(
        "evt-20260705-003",
        task_id,
        "progress",
        "running",
        "running",
        "Detailed private message should not appear",
        "2026-07-05T10:02:00+08:00",
    )
    candidate_file = root / "candidate.json"
    candidate_file.write_text(json.dumps(candidate), encoding="utf-8")

    code = main([
        "--root", str(root),
        "runtime", "event", "append",
        "--file", "candidate.json",
        "--dry-run",
    ])
    captured = capsys.readouterr()

    assert code == 0
    assert "PASS" in captured.out
    assert "event_id=evt-20260705-003" in captured.out
    assert "task_id=task-20260705-001" in captured.out
    assert "would_append=False" in captured.out
    assert "ledger_check=pass" in captured.out
    assert "Detailed private message" not in captured.out
