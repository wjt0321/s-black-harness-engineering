"""Tests for orchestration report generate read-only command."""

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


def _write_tasks(fake_root: Path, status: str = "running") -> None:
    """Write a tasks.jsonl with a single task in the given status."""
    tasks_file = fake_root / "tasks" / "tasks.jsonl"
    tasks_file.parent.mkdir(parents=True, exist_ok=True)
    task = {
        "id": "task-20260703-001",
        "title": "Orchestration report test task",
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


def _write_events(fake_root: Path) -> None:
    """Write a consistent events.jsonl for the test task."""
    events_file = fake_root / "tasks" / "events.jsonl"
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
    events_file.write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")


def _make_envelope() -> dict[str, Any]:
    """Build a valid envelope with one request/approval pair."""
    return {
        "version": 1,
        "description": "Orchestration report test envelope",
        "artifacts": [
            {
                "artifact_type": "adapter_request",
                "request_id": "req-20260703-001",
                "task_id": "task-20260703-001",
                "adapter_id": "github-cli",
                "operation": "git_push",
                "actor": "orchestrator",
                "target": "origin/main",
                "input": {"remote": "origin", "branch": "main"},
                "context": {
                    "source": "cli",
                    "policy_profile": "s-black",
                    "risk_level": "external",
                    "dry_run": True,
                    "requires_approval": True,
                    "approval_id": "appr-20260703-001",
                    "payload_refs": [],
                },
                "preflight": {
                    "status": "needs_approval",
                    "findings": [
                        {
                            "rule_id": "github-cli-approval",
                            "severity": "block",
                            "action": "require_user_approval",
                            "message": "External publish operation requires explicit approval.",
                        }
                    ],
                },
                "created_at": "2026-07-03T10:00:00+08:00",
            },
            {
                "artifact_type": "approval_record",
                "approval_id": "appr-20260703-001",
                "request_id": "req-20260703-001",
                "status": "pending",
                "scope": {
                    "task_id": "task-20260703-001",
                    "adapter_id": "github-cli",
                    "operation": "git_push",
                    "target": "origin/main",
                },
                "requested_at": "2026-07-03T10:00:01+08:00",
                "decided_at": None,
                "decided_by": None,
                "decision_ref": None,
            },
        ],
    }


def test_report_generate_json_output_structure(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    _write_tasks(fake_root)
    _write_events(fake_root)
    envelope = _make_envelope()
    envelope_path = fake_root / "drafts" / "runtime" / "report.envelope.json"
    envelope_path.parent.mkdir(parents=True, exist_ok=True)
    envelope_path.write_text(json.dumps(envelope, ensure_ascii=False), encoding="utf-8")

    code = main([
        "--root", str(fake_root),
        "orchestration", "report", "generate",
        "--task-id", "task-20260703-001",
        "--request-id", "req-20260703-001",
        "--envelope", str(envelope_path),
        "--json",
    ])
    captured = capsys.readouterr()
    # Runtime report returns needs_approval (exit 3) because approval is pending.
    assert code == 3
    result = json.loads(captured.out)
    assert result["status"] == "needs_approval"
    assert result["task_id"] == "task-20260703-001"
    assert result["request_id"] == "req-20260703-001"
    assert result["task_status"] == "running"
    assert "needs_approval" in result["status_summary"]
    assert result["event_summary"]["total"] == 2
    assert result["gate"]["can_proceed"] is False
    assert result["next_action"] is not None
    assert "artifact_refs" in result
    assert "evidence_refs" in result


def test_report_generate_human_readable_smoke(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    _write_tasks(fake_root)
    _write_events(fake_root)
    envelope = _make_envelope()
    envelope_path = fake_root / "drafts" / "runtime" / "report.envelope.json"
    envelope_path.parent.mkdir(parents=True, exist_ok=True)
    envelope_path.write_text(json.dumps(envelope, ensure_ascii=False), encoding="utf-8")

    code = main([
        "--root", str(fake_root),
        "orchestration", "report", "generate",
        "--task-id", "task-20260703-001",
        "--request-id", "req-20260703-001",
        "--envelope", str(envelope_path),
    ])
    captured = capsys.readouterr()
    # Runtime report returns needs_approval (exit 3) because approval is pending.
    assert code == 3
    assert "REPORT GENERATE" in captured.out
    assert "task-20260703-001" in captured.out
    assert "req-20260703-001" in captured.out
    assert "Gate:" in captured.out


def test_report_generate_missing_task(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    envelope = _make_envelope()
    envelope_path = fake_root / "drafts" / "runtime" / "report.envelope.json"
    envelope_path.parent.mkdir(parents=True, exist_ok=True)
    envelope_path.write_text(json.dumps(envelope, ensure_ascii=False), encoding="utf-8")

    code = main([
        "--root", str(fake_root),
        "orchestration", "report", "generate",
        "--task-id", "task-20260703-999",
        "--request-id", "req-20260703-001",
        "--envelope", str(envelope_path),
        "--json",
    ])
    captured = capsys.readouterr()
    assert code != 0
    result = json.loads(captured.out)
    assert result["status"] == "error"
    assert "task-20260703-999" in result["status_summary"]
    assert "Task task-20260703-999 not found" in result["key_findings"][0]


def test_report_generate_missing_envelope(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    _write_tasks(fake_root)
    _write_events(fake_root)

    code = main([
        "--root", str(fake_root),
        "orchestration", "report", "generate",
        "--task-id", "task-20260703-001",
        "--request-id", "req-20260703-001",
        "--envelope", "drafts/runtime/nonexistent.envelope.json",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code != 0
    result = json.loads(captured.out)
    assert result["status"] == "error"


def test_report_generate_invalid_envelope(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    _write_tasks(fake_root)
    _write_events(fake_root)
    envelope_path = fake_root / "drafts" / "runtime" / "report.envelope.json"
    envelope_path.parent.mkdir(parents=True, exist_ok=True)
    envelope_path.write_text('{"invalid": true}', encoding="utf-8")

    code = main([
        "--root", str(fake_root),
        "orchestration", "report", "generate",
        "--task-id", "task-20260703-001",
        "--request-id", "req-20260703-001",
        "--envelope", str(envelope_path),
        "--json",
    ])
    captured = capsys.readouterr()
    assert code != 0
    result = json.loads(captured.out)
    assert result["status"] == "validation_failed"


def test_report_generate_does_not_write_files(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    _write_tasks(fake_root)
    _write_events(fake_root)
    envelope = _make_envelope()
    envelope_path = fake_root / "drafts" / "runtime" / "report.envelope.json"
    envelope_path.parent.mkdir(parents=True, exist_ok=True)
    envelope_path.write_text(json.dumps(envelope, ensure_ascii=False), encoding="utf-8")
    envelope_before = envelope_path.read_bytes()

    code = main([
        "--root", str(fake_root),
        "orchestration", "report", "generate",
        "--task-id", "task-20260703-001",
        "--request-id", "req-20260703-001",
        "--envelope", str(envelope_path),
        "--json",
    ])
    # Runtime report returns needs_approval (exit 3) because approval is pending.
    assert code == 3
    assert envelope_path.read_bytes() == envelope_before


def _make_envelope_with_lineage(lineage: dict[str, Any]) -> dict[str, Any]:
    """Build a minimal envelope with lineage in adapter_request.context."""
    envelope = _make_envelope()
    request = envelope["artifacts"][0]
    request["request_id"] = "req-20260703-002"
    request["context"].update(lineage)
    # Make the request pass so the report status is not dominated by approval.
    request["context"]["requires_approval"] = False
    request["preflight"]["status"] = "pass"
    request["preflight"]["findings"] = []
    # Remove the approval_record since it is no longer needed.
    envelope["artifacts"] = [a for a in envelope["artifacts"] if a["artifact_type"] != "approval_record"]
    return envelope


def test_report_generate_retry_lineage_json(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    _write_tasks(fake_root)
    _write_events(fake_root)
    envelope = _make_envelope_with_lineage(
        {"lineage_type": "retry", "retry_of": "req-20260703-001"}
    )
    envelope_path = fake_root / "drafts" / "runtime" / "report-retry.envelope.json"
    envelope_path.parent.mkdir(parents=True, exist_ok=True)
    envelope_path.write_text(json.dumps(envelope, ensure_ascii=False), encoding="utf-8")

    code = main([
        "--root", str(fake_root),
        "orchestration", "report", "generate",
        "--task-id", "task-20260703-001",
        "--request-id", "req-20260703-002",
        "--envelope", str(envelope_path),
        "--json",
    ])
    captured = capsys.readouterr()
    assert code in (0, 4)
    result = json.loads(captured.out)
    assert result["lineage_type"] == "retry"
    assert result["retry_of"] == "req-20260703-001"
    assert "lineage_type=retry" in result["status_summary"]
    assert "origin/main" not in captured.out


def test_report_generate_fallback_lineage_json(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    _write_tasks(fake_root)
    _write_events(fake_root)
    envelope = _make_envelope_with_lineage(
        {
            "lineage_type": "fallback",
            "fallback_from": "req-20260703-001",
            "fallback_to": "dummy-fallback",
        }
    )
    envelope_path = fake_root / "drafts" / "runtime" / "report-fallback.envelope.json"
    envelope_path.parent.mkdir(parents=True, exist_ok=True)
    envelope_path.write_text(json.dumps(envelope, ensure_ascii=False), encoding="utf-8")

    code = main([
        "--root", str(fake_root),
        "orchestration", "report", "generate",
        "--task-id", "task-20260703-001",
        "--request-id", "req-20260703-002",
        "--envelope", str(envelope_path),
        "--json",
    ])
    captured = capsys.readouterr()
    assert code in (0, 4)
    result = json.loads(captured.out)
    assert result["lineage_type"] == "fallback"
    assert result["fallback_from"] == "req-20260703-001"
    assert result["fallback_to"] == "dummy-fallback"
    assert "lineage_type=fallback" in result["status_summary"]
