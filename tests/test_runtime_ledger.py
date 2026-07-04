"""Tests for runtime ledger audit CLI."""

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


def _write_tasks(tmp_path: Path, status: str = "running") -> None:
    """Write a tasks.jsonl with a single task in the given status."""
    tasks_file = tmp_path / "tasks" / "tasks.jsonl"
    tasks_file.parent.mkdir(parents=True, exist_ok=True)
    task = {
        "id": "task-20260703-001",
        "title": "Runtime ledger test task",
        "status": status,
        "created_at": "2026-07-03T10:00:00+08:00",
        "updated_at": "2026-07-03T10:00:00+08:00",
        "created_by": "test",
        "source": "cli",
    }
    tasks_file.write_text(json.dumps(task) + "\n", encoding="utf-8")


def _write_events(
    tmp_path: Path,
    include_request_metadata: bool = False,
    to_status: str = "running",
) -> None:
    """Write a minimal events.jsonl for the test task."""
    events_file = tmp_path / "tasks" / "events.jsonl"
    events_file.parent.mkdir(parents=True, exist_ok=True)
    event: dict[str, Any] = {
        "event_id": "evt-20260703-001",
        "task_id": "task-20260703-001",
        "timestamp": "2026-07-03T10:00:00+08:00",
        "actor": "test",
        "event_type": "created",
        "from_status": None,
        "to_status": to_status,
        "message": "Test task created.",
    }
    if include_request_metadata:
        event["metadata"] = {"request_id": "req-20260703-001"}
    events_file.write_text(json.dumps(event) + "\n", encoding="utf-8")


def _make_envelope(
    task_id: str = "task-20260703-001",
    request_id: str = "req-20260703-001",
    add_execution_event: bool = True,
    preflight_status: str = "needs_approval",
    requires_approval: bool = True,
) -> dict[str, Any]:
    """Build a minimal envelope with one adapter request and optional execution event."""
    artifacts: list[dict[str, Any]] = [
        {
            "artifact_type": "adapter_request",
            "request_id": request_id,
            "task_id": task_id,
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
                "status": preflight_status,
                "findings": [],
            },
            "created_at": "2026-07-03T10:00:00+08:00",
        }
    ]
    if requires_approval:
        artifacts.append(
            {
                "artifact_type": "approval_record",
                "approval_id": "appr-20260703-001",
                "request_id": request_id,
                "status": "pending",
                "scope": {
                    "task_id": task_id,
                    "adapter_id": "github-cli",
                    "operation": "git_push",
                    "target": "origin/main",
                },
                "requested_at": "2026-07-03T10:00:01+08:00",
                "decided_at": None,
                "decided_by": None,
                "decision_ref": None,
            }
        )

    if add_execution_event:
        artifacts.append(
            {
                "artifact_type": "execution_event",
                "event_id": "exe-20260703-001",
                "task_id": task_id,
                "request_id": request_id,
                "timestamp": "2026-07-03T10:00:00+08:00",
                "actor": "test",
                "event_type": "approval_requested",
                "message": "Approval requested.",
                "metadata": {
                    "approval_id": "appr-20260703-001",
                    "adapter_id": "github-cli",
                    "operation": "git_push",
                    "target": "origin/main",
                    "preflight_status": preflight_status,
                },
            }
        )
    return {
        "version": 1,
        "description": "Runtime ledger test envelope",
        "artifacts": artifacts,
    }


def _write_envelope(tmp_path: Path, envelope: dict[str, Any]) -> Path:
    env_file = tmp_path / "envelope.json"
    env_file.write_text(json.dumps(envelope), encoding="utf-8")
    return env_file


def test_runtime_check_ledger_pass(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    _write_tasks(fake_root, "running")
    _write_events(fake_root, include_request_metadata=True)
    envelope = _make_envelope()
    _write_envelope(fake_root, envelope)

    code = main([
        "--root", str(fake_root),
        "runtime", "check-ledger",
        "--tasks-file", "tasks/tasks.jsonl",
        "--events-file", "tasks/events.jsonl",
        "--envelope", "envelope.json",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 0
    result = json.loads(captured.out)
    assert result["status"] == "pass"
    assert result["counts"]["tasks"] == 1
    assert result["counts"]["events"] == 1
    assert result["counts"]["requests"] == 1
    assert result["counts"]["execution_events"] == 1


def test_runtime_check_ledger_missing_task_id(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    _write_tasks(fake_root, "running")
    _write_events(fake_root)
    envelope = _make_envelope(task_id="task-20260703-999")
    _write_envelope(fake_root, envelope)

    code = main([
        "--root", str(fake_root),
        "runtime", "check-ledger",
        "--tasks-file", "tasks/tasks.jsonl",
        "--events-file", "tasks/events.jsonl",
        "--envelope", "envelope.json",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 1
    result = json.loads(captured.out)
    assert result["status"] == "error"
    assert any(f["rule_id"] == "request-task-id-unknown" for f in result["findings"])


def test_runtime_check_ledger_missing_event_task_id(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    _write_tasks(fake_root, "running")
    _write_events(fake_root)
    envelope = _make_envelope()
    envelope["artifacts"][-1]["task_id"] = "task-20260703-999"
    _write_envelope(fake_root, envelope)

    code = main([
        "--root", str(fake_root),
        "runtime", "check-ledger",
        "--tasks-file", "tasks/tasks.jsonl",
        "--events-file", "tasks/events.jsonl",
        "--envelope", "envelope.json",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 1
    result = json.loads(captured.out)
    assert result["status"] == "error"
    assert any(f["rule_id"] == "event-task-id-unknown" for f in result["findings"])


def test_runtime_check_ledger_missing_request_id(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    _write_tasks(fake_root, "running")
    _write_events(fake_root)
    envelope = _make_envelope()
    # Break the reference by using a different execution_event request_id.
    envelope["artifacts"][-1]["request_id"] = "req-20260703-999"
    _write_envelope(fake_root, envelope)

    code = main([
        "--root", str(fake_root),
        "runtime", "check-ledger",
        "--tasks-file", "tasks/tasks.jsonl",
        "--events-file", "tasks/events.jsonl",
        "--envelope", "envelope.json",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 5
    result = json.loads(captured.out)
    assert result["status"] == "validation_failed"
    assert any(f["rule_id"] == "event-references-unknown-request" for f in result["findings"])


def test_runtime_check_ledger_warns_missing_event_metadata(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    _write_tasks(fake_root, "running")
    _write_events(fake_root, include_request_metadata=False)
    envelope = _make_envelope()
    _write_envelope(fake_root, envelope)

    code = main([
        "--root", str(fake_root),
        "runtime", "check-ledger",
        "--tasks-file", "tasks/tasks.jsonl",
        "--events-file", "tasks/events.jsonl",
        "--envelope", "envelope.json",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 0
    result = json.loads(captured.out)
    assert result["status"] == "warn"
    assert any(f["rule_id"] == "request-id-no-event-metadata" for f in result["findings"])


def test_runtime_check_ledger_terminal_task_warns(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    _write_tasks(fake_root, "finished")
    _write_events(fake_root, include_request_metadata=True, to_status="finished")
    envelope = _make_envelope()
    _write_envelope(fake_root, envelope)

    code = main([
        "--root", str(fake_root),
        "runtime", "check-ledger",
        "--tasks-file", "tasks/tasks.jsonl",
        "--events-file", "tasks/events.jsonl",
        "--envelope", "envelope.json",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 0
    result = json.loads(captured.out)
    assert result["status"] == "warn"
    assert any(f["rule_id"] == "task-terminal-but-request-pending" for f in result["findings"])


def test_runtime_check_ledger_ledger_consistency_failure(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    _write_tasks(fake_root, "running")
    # No events file -> ledger consistency error.
    envelope = _make_envelope()
    _write_envelope(fake_root, envelope)

    code = main([
        "--root", str(fake_root),
        "runtime", "check-ledger",
        "--tasks-file", "tasks/tasks.jsonl",
        "--events-file", "tasks/events.jsonl",
        "--envelope", "envelope.json",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 1
    result = json.loads(captured.out)
    assert result["status"] == "error"
    assert any(f["rule_id"] == "ledger-consistency-failed" for f in result["findings"])


def test_runtime_check_ledger_invalid_envelope(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    _write_tasks(fake_root, "running")
    _write_events(fake_root)
    bad_file = fake_root / "envelope.json"
    bad_file.write_text("{not json", encoding="utf-8")

    code = main([
        "--root", str(fake_root),
        "runtime", "check-ledger",
        "--tasks-file", "tasks/tasks.jsonl",
        "--events-file", "tasks/events.jsonl",
        "--envelope", "envelope.json",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 5
    result = json.loads(captured.out)
    assert result["status"] == "validation_failed"
    assert any(f["rule_id"] == "invalid-json" for f in result["findings"])


def test_runtime_check_ledger_human_output_no_payload(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    _write_tasks(fake_root, "running")
    _write_events(fake_root, include_request_metadata=True)
    envelope = _make_envelope()
    _write_envelope(fake_root, envelope)

    code = main([
        "--root", str(fake_root),
        "runtime", "check-ledger",
        "--tasks-file", "tasks/tasks.jsonl",
        "--events-file", "tasks/events.jsonl",
        "--envelope", "envelope.json",
    ])
    captured = capsys.readouterr()
    assert code == 0
    assert "PASS" in captured.out
    assert "counts:" in captured.out
    assert "\"input\"" not in captured.out
    assert "\"remote\"" not in captured.out
    assert "origin/main" not in captured.out


def test_runtime_check_ledger_does_not_write_ledger(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    _write_tasks(fake_root, "running")
    _write_events(fake_root, include_request_metadata=True)
    envelope = _make_envelope()
    _write_envelope(fake_root, envelope)

    tasks_before = (fake_root / "tasks" / "tasks.jsonl").read_bytes()
    events_before = (fake_root / "tasks" / "events.jsonl").read_bytes()

    code = main([
        "--root", str(fake_root),
        "runtime", "check-ledger",
        "--tasks-file", "tasks/tasks.jsonl",
        "--events-file", "tasks/events.jsonl",
        "--envelope", "envelope.json",
    ])
    assert code == 0
    assert (fake_root / "tasks" / "tasks.jsonl").read_bytes() == tasks_before
    assert (fake_root / "tasks" / "events.jsonl").read_bytes() == events_before


def test_runtime_check_ledger_invalid_envelope_schema(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    _write_tasks(fake_root, "running")
    _write_events(fake_root, include_request_metadata=True)
    envelope = _make_envelope()
    del envelope["artifacts"][0]["request_id"]
    _write_envelope(fake_root, envelope)

    code = main([
        "--root", str(fake_root),
        "runtime", "check-ledger",
        "--tasks-file", "tasks/tasks.jsonl",
        "--events-file", "tasks/events.jsonl",
        "--envelope", "envelope.json",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 5
    result = json.loads(captured.out)
    assert result["status"] == "validation_failed"
    assert any(f["rule_id"] == "envelope-schema-validation-failed" for f in result["findings"])


def test_runtime_check_ledger_warns_request_without_task_event_clue(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    _write_tasks(fake_root, "running")
    _write_events(fake_root, include_request_metadata=False)
    envelope = _make_envelope(add_execution_event=False, requires_approval=False, preflight_status="pass")
    _write_envelope(fake_root, envelope)

    code = main([
        "--root", str(fake_root),
        "runtime", "check-ledger",
        "--tasks-file", "tasks/tasks.jsonl",
        "--events-file", "tasks/events.jsonl",
        "--envelope", "envelope.json",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 0
    result = json.loads(captured.out)
    assert result["status"] == "warn"
    assert any(f["rule_id"] == "request-id-no-event-metadata" for f in result["findings"])
