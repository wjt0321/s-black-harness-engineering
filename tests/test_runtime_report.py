"""Tests for runtime report CLI."""

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
        "title": "Runtime report test task",
        "status": status,
        "created_at": "2026-07-03T10:00:00+08:00",
        "updated_at": "2026-07-03T10:00:00+08:00",
        "created_by": "test",
        "source": "cli",
        "assignee": "orchestrator",
        "evidence": [
            {"type": "test", "description": "Detailed evidence description", "ref": "ref-1"}
        ],
        "artifacts": ["agent_runtime/runtime_report.py"],
    }
    tasks_file.write_text(json.dumps(task) + "\n", encoding="utf-8")


def _write_events(
    tmp_path: Path,
    latest_status: str = "running",
    include_request_metadata: bool = False,
) -> None:
    """Write a consistent events.jsonl for the test task."""
    events_file = tmp_path / "tasks" / "events.jsonl"
    events_file.parent.mkdir(parents=True, exist_ok=True)
    events: list[dict[str, Any]] = [
        {
            "event_id": "evt-20260703-001",
            "task_id": "task-20260703-001",
            "timestamp": "2026-07-03T10:00:00+08:00",
            "actor": "test",
            "event_type": "created",
            "from_status": None,
            "to_status": "planned",
            "message": "Task created.",
        },
        {
            "event_id": "evt-20260703-002",
            "task_id": "task-20260703-001",
            "timestamp": "2026-07-03T10:05:00+08:00",
            "actor": "test",
            "event_type": "status_changed",
            "from_status": "planned",
            "to_status": "running",
            "message": "Task started.",
        },
    ]
    if latest_status in {"finished", "failed"}:
        events.append(
            {
                "event_id": "evt-20260703-003",
                "task_id": "task-20260703-001",
                "timestamp": "2026-07-03T10:10:00+08:00",
                "actor": "test",
                "event_type": "status_changed",
                "from_status": "running",
                "to_status": latest_status,
                "message": f"Task {latest_status}.",
            }
        )
    if include_request_metadata:
        events[-1]["metadata"] = {"request_id": "req-20260703-001"}
    events_file.write_text("".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")


def _make_envelope(
    approval_status: str | None = None,
    response_status: str | None = None,
) -> dict[str, Any]:
    """Build a minimal envelope with one adapter request and optional approval/response."""
    requires_approval = approval_status is not None
    envelope: dict[str, Any] = {
        "version": 1,
        "description": "Runtime report test envelope",
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
                    [{"type": "test", "description": "Detailed evidence description", "ref": "ref"}]
                    if response_status == "succeeded"
                    else []
                ),
                "raw_ref": None,
                "error": None,
                "finished_at": "2026-07-03T11:00:01+08:00",
            }
        )
    envelope["artifacts"].append(
        {
            "artifact_type": "execution_event",
            "event_id": "exe-20260703-001",
            "task_id": "task-20260703-001",
            "request_id": "req-20260703-001",
            "timestamp": "2026-07-03T10:05:00+08:00",
            "actor": "test",
            "event_type": "evidence_added",
            "message": "Adapter response evidence can be attached to the task ledger after review.",
            "metadata": {
                "response_id": "resp-20260703-001",
                "evidence_count": 1,
            },
        }
    )
    return envelope


def _write_envelope(tmp_path: Path, envelope: dict[str, Any]) -> Path:
    env_file = tmp_path / "envelope.json"
    env_file.write_text(json.dumps(envelope), encoding="utf-8")
    return env_file


def test_runtime_report_text_output_contains_summaries(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    _write_tasks(fake_root, "running")
    _write_events(fake_root, include_request_metadata=True)
    envelope = _make_envelope(response_status="succeeded")
    _write_envelope(fake_root, envelope)

    code = main([
        "--root", str(fake_root),
        "runtime", "report",
        "--task-id", "task-20260703-001",
        "--request-id", "req-20260703-001",
        "--envelope", "envelope.json",
    ])
    captured = capsys.readouterr()
    assert code == 0
    assert "PASS" in captured.out
    assert "Task: task-20260703-001" in captured.out
    assert "Events:" in captured.out
    assert "Envelope:" in captured.out
    assert "Gate:" in captured.out
    assert "Ledger:" in captured.out
    assert "Blockers:" in captured.out
    assert "Next:" in captured.out


def test_runtime_report_json_sanitizes_sensitive_fields(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    _write_tasks(fake_root, "running")
    _write_events(fake_root, include_request_metadata=True)
    envelope = _make_envelope(response_status="succeeded")
    _write_envelope(fake_root, envelope)

    code = main([
        "--root", str(fake_root),
        "runtime", "report",
        "--task-id", "task-20260703-001",
        "--request-id", "req-20260703-001",
        "--envelope", "envelope.json",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 0
    result = json.loads(captured.out)
    text = json.dumps(result, ensure_ascii=False)
    assert "origin/main" not in text
    assert '"input"' not in text
    assert "decision_ref" not in text
    assert "Detailed evidence description" not in text
    assert result["task_snapshot"]["evidence_count"] == 1


def test_runtime_report_terminal_task_blocked(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    _write_tasks(fake_root, "finished")
    _write_events(fake_root, latest_status="finished", include_request_metadata=True)
    envelope = _make_envelope(response_status="succeeded")
    _write_envelope(fake_root, envelope)

    code = main([
        "--root", str(fake_root),
        "runtime", "report",
        "--task-id", "task-20260703-001",
        "--request-id", "req-20260703-001",
        "--envelope", "envelope.json",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 2
    result = json.loads(captured.out)
    assert result["status"] == "blocked"
    assert any("terminal" in b for b in result["blockers"])
    assert "terminal" in result["next_action"].lower()


def test_runtime_report_does_not_write_files(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    _write_tasks(fake_root, "running")
    _write_events(fake_root, include_request_metadata=True)
    envelope = _make_envelope(response_status="succeeded")
    _write_envelope(fake_root, envelope)

    tasks_before = (fake_root / "tasks" / "tasks.jsonl").read_bytes()
    events_before = (fake_root / "tasks" / "events.jsonl").read_bytes()
    envelope_before = (fake_root / "envelope.json").read_bytes()

    code = main([
        "--root", str(fake_root),
        "runtime", "report",
        "--task-id", "task-20260703-001",
        "--request-id", "req-20260703-001",
        "--envelope", "envelope.json",
    ])
    assert code == 0
    assert (fake_root / "tasks" / "tasks.jsonl").read_bytes() == tasks_before
    assert (fake_root / "tasks" / "events.jsonl").read_bytes() == events_before
    assert (fake_root / "envelope.json").read_bytes() == envelope_before
