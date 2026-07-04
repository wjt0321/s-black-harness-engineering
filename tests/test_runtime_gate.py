"""Tests for runtime gate check CLI."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agent_runtime.cli import main


ROOT = Path(__file__).resolve().parents[1]


def _setup_fake_root(tmp_path: Path) -> Path:
    """Create a fake project root containing a copy of the envelope schema."""
    fake_root = tmp_path / "project"
    fake_root.mkdir()
    schema_src = ROOT / "adapters" / "execution-envelope.schema.json"
    schema_dst = fake_root / "adapters" / "execution-envelope.schema.json"
    schema_dst.parent.mkdir(parents=True, exist_ok=True)
    schema_dst.write_text(schema_src.read_text(encoding="utf-8"), encoding="utf-8")
    return fake_root


def _write_tasks(tmp_path: Path, status: str) -> None:
    """Write a tasks.jsonl with a single task in the given status."""
    tasks_file = tmp_path / "tasks" / "tasks.jsonl"
    tasks_file.parent.mkdir(parents=True, exist_ok=True)
    task = {
        "id": "task-20260703-001",
        "title": "Runtime gate test task",
        "status": status,
        "created_at": "2026-07-03T10:00:00+08:00",
        "updated_at": "2026-07-03T10:00:00+08:00",
        "created_by": "test",
        "source": "cli",
    }
    tasks_file.write_text(json.dumps(task) + "\n", encoding="utf-8")


def _write_events(tmp_path: Path) -> None:
    """Write a minimal events.jsonl for the test task."""
    events_file = tmp_path / "tasks" / "events.jsonl"
    events_file.parent.mkdir(parents=True, exist_ok=True)
    event = {
        "event_id": "evt-20260703-001",
        "task_id": "task-20260703-001",
        "timestamp": "2026-07-03T10:00:00+08:00",
        "actor": "test",
        "event_type": "created",
        "message": "Test task created.",
    }
    events_file.write_text(json.dumps(event) + "\n", encoding="utf-8")


def _make_envelope(
    approval_status: str | None = None,
    response_status: str | None = None,
) -> dict[str, Any]:
    """Build a minimal envelope with one adapter request and optional approval/response."""
    requires_approval = approval_status is not None
    envelope: dict[str, Any] = {
        "version": 1,
        "description": "Runtime gate test envelope",
        "artifacts": [
            {
                "artifact_type": "adapter_request",
                "request_id": "req-20260703-001",
                "task_id": "task-20260703-001",
                "adapter_id": "github-cli",
                "operation": "git_push",
                "actor": "test",
                "target": "origin/main",
                "input": {"remote": "origin", "branch": "main"},
                "context": {
                    "source": "cli",
                    "policy_profile": "s-black",
                    "risk_level": "external",
                    "dry_run": True,
                    "requires_approval": requires_approval,
                    "approval_id": "appr-20260703-001" if requires_approval else None,
                    "payload_refs": [],
                },
                "preflight": {
                    "status": "needs_approval" if requires_approval else "pass",
                    "findings": [],
                },
                "created_at": "2026-07-03T10:00:00+08:00",
            }
        ],
    }
    if requires_approval:
        envelope["artifacts"].append(
            {
                "artifact_type": "approval_record",
                "approval_id": "appr-20260703-001",
                "request_id": "req-20260703-001",
                "status": approval_status,
                "scope": {
                    "task_id": "task-20260703-001",
                    "adapter_id": "github-cli",
                    "operation": "git_push",
                    "target": "origin/main",
                },
                "requested_at": "2026-07-03T10:00:01+08:00",
                "decided_at": (
                    "2026-07-03T11:00:00+08:00" if approval_status != "pending" else None
                ),
                "decided_by": "user" if approval_status != "pending" else None,
                "decision_ref": None,
            }
        )
    if response_status is not None:
        envelope["artifacts"].append(
            {
                "artifact_type": "adapter_response",
                "response_id": "resp-20260703-001",
                "request_id": "req-20260703-001",
                "status": response_status,
                "message": "Test response.",
                "artifacts": [],
                "evidence": (
                    [{"type": "test", "description": "evidence", "ref": "ref"}]
                    if response_status == "succeeded"
                    else []
                ),
                "raw_ref": None,
                "error": None,
                "finished_at": "2026-07-03T11:00:01+08:00",
            }
        )
    return envelope


def _write_envelope(tmp_path: Path, envelope: dict[str, Any]) -> Path:
    env_file = tmp_path / "envelope.json"
    env_file.write_text(json.dumps(envelope), encoding="utf-8")
    return env_file


def test_runtime_gate_running_and_pass(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    _write_tasks(fake_root, "running")
    _write_events(fake_root)
    envelope = _make_envelope(response_status="succeeded")
    _write_envelope(fake_root, envelope)

    code = main([
        "--root", str(fake_root),
        "runtime", "gate", "check",
        "--task-id", "task-20260703-001",
        "--request-id", "req-20260703-001",
        "--envelope", "envelope.json",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 0
    result = json.loads(captured.out)
    assert result["status"] == "pass"
    assert result["task_status"] == "running"
    assert result["gate"]["can_proceed"] is True
    draft = result["suggested_event_draft"]
    assert draft["event_type"] == "status_changed"
    assert draft["to_status"] == "running"
    assert draft["metadata"]["adapter_id"] == "github-cli"
    assert draft["metadata"]["operation"] == "git_push"


def test_runtime_gate_running_pending_approval(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    _write_tasks(fake_root, "running")
    _write_events(fake_root)
    envelope = _make_envelope(approval_status="pending")
    _write_envelope(fake_root, envelope)

    code = main([
        "--root", str(fake_root),
        "runtime", "gate", "check",
        "--task-id", "task-20260703-001",
        "--request-id", "req-20260703-001",
        "--envelope", "envelope.json",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 3
    result = json.loads(captured.out)
    assert result["status"] == "needs_approval"
    assert result["task_status"] == "running"
    assert result["gate"]["can_proceed"] is False
    draft = result["suggested_event_draft"]
    assert draft["event_type"] == "blocked"
    assert draft["to_status"] == "blocked"
    assert draft["metadata"]["blocked_reason"] == "need_user_approval"


def test_runtime_gate_running_approval_denied(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    _write_tasks(fake_root, "running")
    _write_events(fake_root)
    envelope = _make_envelope(approval_status="denied")
    _write_envelope(fake_root, envelope)

    code = main([
        "--root", str(fake_root),
        "runtime", "gate", "check",
        "--task-id", "task-20260703-001",
        "--request-id", "req-20260703-001",
        "--envelope", "envelope.json",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 2
    result = json.loads(captured.out)
    assert result["status"] == "blocked"
    draft = result["suggested_event_draft"]
    assert draft["metadata"]["blocked_reason"] == "policy_blocked"


def test_runtime_gate_running_missing_response(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    _write_tasks(fake_root, "running")
    _write_events(fake_root)
    envelope = _make_envelope(approval_status="granted")
    _write_envelope(fake_root, envelope)

    code = main([
        "--root", str(fake_root),
        "runtime", "gate", "check",
        "--task-id", "task-20260703-001",
        "--request-id", "req-20260703-001",
        "--envelope", "envelope.json",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 4
    result = json.loads(captured.out)
    assert result["status"] == "needs_input"
    draft = result["suggested_event_draft"]
    assert draft["metadata"]["blocked_reason"] == "need_user_input"


def test_runtime_gate_finished_task_blocks_even_if_gate_passes(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    _write_tasks(fake_root, "finished")
    _write_events(fake_root)
    envelope = _make_envelope(response_status="succeeded")
    _write_envelope(fake_root, envelope)

    code = main([
        "--root", str(fake_root),
        "runtime", "gate", "check",
        "--task-id", "task-20260703-001",
        "--request-id", "req-20260703-001",
        "--envelope", "envelope.json",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 2
    result = json.loads(captured.out)
    assert result["status"] == "blocked"
    assert result["gate"]["can_proceed"] is True
    draft = result["suggested_event_draft"]
    assert draft["event_type"] == "blocked"
    assert draft["from_status"] == "finished"
    assert draft["to_status"] == "finished"




def test_runtime_gate_finished_task_blocks_even_if_approval_pending(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    _write_tasks(fake_root, "finished")
    _write_events(fake_root)
    envelope = _make_envelope(approval_status="pending")
    _write_envelope(fake_root, envelope)

    code = main([
        "--root", str(fake_root),
        "runtime", "gate", "check",
        "--task-id", "task-20260703-001",
        "--request-id", "req-20260703-001",
        "--envelope", "envelope.json",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 2
    result = json.loads(captured.out)
    assert result["status"] == "blocked"
    assert result["gate"]["approval_status"] == "needs_approval"
    assert result["suggested_event_draft"]["to_status"] == "finished"
    assert "terminal state" in result["next_action"]


def test_runtime_gate_task_not_found(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    _write_events(fake_root)
    envelope = _make_envelope(response_status="succeeded")
    _write_envelope(fake_root, envelope)

    code = main([
        "--root", str(fake_root),
        "runtime", "gate", "check",
        "--task-id", "task-20260703-999",
        "--request-id", "req-20260703-001",
        "--envelope", "envelope.json",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 1
    result = json.loads(captured.out)
    assert result["status"] == "error"
    assert any(f["rule_id"] == "task-not-found" for f in result["findings"])


def test_runtime_gate_request_not_found(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    _write_tasks(fake_root, "running")
    _write_events(fake_root)
    envelope = _make_envelope(response_status="succeeded")
    _write_envelope(fake_root, envelope)

    code = main([
        "--root", str(fake_root),
        "runtime", "gate", "check",
        "--task-id", "task-20260703-001",
        "--request-id", "req-20260703-999",
        "--envelope", "envelope.json",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 4
    result = json.loads(captured.out)
    assert result["status"] == "needs_input"
    assert any(f["rule_id"] == "approval-request-not-found" for f in result["findings"])


def test_runtime_gate_invalid_envelope(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    _write_tasks(fake_root, "running")
    _write_events(fake_root)
    bad_file = fake_root / "envelope.json"
    bad_file.write_text("{not json", encoding="utf-8")

    code = main([
        "--root", str(fake_root),
        "runtime", "gate", "check",
        "--task-id", "task-20260703-001",
        "--request-id", "req-20260703-001",
        "--envelope", "envelope.json",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 5
    result = json.loads(captured.out)
    assert result["status"] == "validation_failed"
    assert any(f["rule_id"] == "invalid-json" for f in result["findings"])


def test_runtime_gate_human_output_no_payload(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    _write_tasks(fake_root, "running")
    _write_events(fake_root)
    envelope = _make_envelope(response_status="succeeded")
    _write_envelope(fake_root, envelope)

    code = main([
        "--root", str(fake_root),
        "runtime", "gate", "check",
        "--task-id", "task-20260703-001",
        "--request-id", "req-20260703-001",
        "--envelope", "envelope.json",
    ])
    captured = capsys.readouterr()
    assert code == 0
    assert "PASS" in captured.out
    assert "task_id=task-20260703-001" in captured.out
    assert "Suggested event draft:" in captured.out
    assert "\"input\"" not in captured.out
    assert "\"remote\"" not in captured.out
    assert "origin/main" not in captured.out


def test_runtime_gate_explicit_ledger_files(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    # Write ledger files outside the default tasks/ directory but still inside
    # the fake project root; runtime gate must not read files outside root.
    custom_tasks = fake_root / "custom_tasks.jsonl"
    custom_events = fake_root / "custom_events.jsonl"
    task = {
        "id": "task-20260703-001",
        "title": "Custom ledger task",
        "status": "running",
        "created_at": "2026-07-03T10:00:00+08:00",
        "updated_at": "2026-07-03T10:00:00+08:00",
        "created_by": "test",
        "source": "cli",
    }
    event = {
        "event_id": "evt-20260703-001",
        "task_id": "task-20260703-001",
        "timestamp": "2026-07-03T10:00:00+08:00",
        "actor": "test",
        "event_type": "created",
        "message": "Custom event.",
    }
    custom_tasks.write_text(json.dumps(task) + "\n", encoding="utf-8")
    custom_events.write_text(json.dumps(event) + "\n", encoding="utf-8")
    envelope = _make_envelope(response_status="succeeded")
    _write_envelope(fake_root, envelope)

    code = main([
        "--root", str(fake_root),
        "runtime", "gate", "check",
        "--task-id", "task-20260703-001",
        "--request-id", "req-20260703-001",
        "--envelope", "envelope.json",
        "--tasks-file", str(custom_tasks),
        "--events-file", str(custom_events),
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 0
    result = json.loads(captured.out)
    assert result["status"] == "pass"


def test_runtime_gate_does_not_write_ledger(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    _write_tasks(fake_root, "running")
    _write_events(fake_root)
    envelope = _make_envelope(response_status="succeeded")
    _write_envelope(fake_root, envelope)

    tasks_before = (fake_root / "tasks" / "tasks.jsonl").read_bytes()
    events_before = (fake_root / "tasks" / "events.jsonl").read_bytes()

    code = main([
        "--root", str(fake_root),
        "runtime", "gate", "check",
        "--task-id", "task-20260703-001",
        "--request-id", "req-20260703-001",
        "--envelope", "envelope.json",
    ])
    assert code == 0
    assert (fake_root / "tasks" / "tasks.jsonl").read_bytes() == tasks_before
    assert (fake_root / "tasks" / "events.jsonl").read_bytes() == events_before


def test_runtime_gate_rejects_explicit_ledger_outside_root(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    _write_tasks(fake_root, "running")
    _write_events(fake_root)
    envelope = _make_envelope(response_status="succeeded")
    _write_envelope(fake_root, envelope)

    outside_tasks = tmp_path / "outside_tasks.jsonl"
    outside_task = {
        "id": "task-20260703-001",
        "title": "Outside ledger task",
        "status": "running",
        "created_at": "2026-07-03T10:00:00+08:00",
        "updated_at": "2026-07-03T10:00:00+08:00",
        "created_by": "test",
        "source": "cli",
    }
    outside_tasks.write_text(json.dumps(outside_task) + "\n", encoding="utf-8")

    code = main([
        "--root", str(fake_root),
        "runtime", "gate", "check",
        "--task-id", "task-20260703-001",
        "--request-id", "req-20260703-001",
        "--envelope", "envelope.json",
        "--tasks-file", str(outside_tasks),
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 1
    result = json.loads(captured.out)
    assert result["status"] == "error"
    assert result["findings"][0]["rule_id"] == "task-not-found"


def test_runtime_gate_ignores_unsafe_explicit_ledger_file(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    _write_tasks(fake_root, "running")
    _write_events(fake_root)
    envelope = _make_envelope(response_status="succeeded")
    _write_envelope(fake_root, envelope)

    unsafe_tasks = fake_root / ".env"
    unsafe_tasks.write_text("not jsonl and must not be read", encoding="utf-8")

    code = main([
        "--root", str(fake_root),
        "runtime", "gate", "check",
        "--task-id", "task-20260703-001",
        "--request-id", "req-20260703-001",
        "--envelope", "envelope.json",
        "--tasks-file", ".env",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 1
    result = json.loads(captured.out)
    assert result["status"] == "error"
    assert result["findings"][0]["rule_id"] == "task-not-found"


def test_runtime_gate_json_sanitizes_gate_details(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    _write_tasks(fake_root, "running")
    _write_events(fake_root)
    envelope = _make_envelope(approval_status="pending")
    _write_envelope(fake_root, envelope)

    code = main([
        "--root", str(fake_root),
        "runtime", "gate", "check",
        "--task-id", "task-20260703-001",
        "--request-id", "req-20260703-001",
        "--envelope", "envelope.json",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 3
    result = json.loads(captured.out)
    text = json.dumps(result, ensure_ascii=False)
    assert "origin/main" not in text
    assert "decision_ref" not in text
    assert "input" not in text
    assert result["gate"]["approval"]["adapter_id"] == "github-cli"
