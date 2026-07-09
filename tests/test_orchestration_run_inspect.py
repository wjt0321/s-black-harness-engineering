"""Tests for orchestration run inspect read-only command."""

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


def _write_tasks(tmp_path: Path) -> None:
    """Write a tasks.jsonl with a single running task."""
    tasks_file = tmp_path / "tasks" / "tasks.jsonl"
    tasks_file.parent.mkdir(parents=True, exist_ok=True)
    task = {
        "id": "task-20260703-001",
        "title": "Run inspect test task",
        "status": "running",
        "created_at": "2026-07-03T10:00:00+08:00",
        "updated_at": "2026-07-03T10:05:00+08:00",
        "created_by": "test",
        "source": "cli",
        "assignee": "orchestrator",
        "evidence": [
            {"type": "test", "description": "Detailed evidence description", "ref": "ref-1"}
        ],
        "artifacts": ["agent_runtime/runtime_report.py"],
    }
    tasks_file.write_text(json.dumps(task) + "\n", encoding="utf-8")


def _write_events(tmp_path: Path) -> None:
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
    events_file.write_text("".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")


def _make_envelope() -> dict[str, Any]:
    """Build a minimal valid envelope with one adapter request."""
    return {
        "version": 1,
        "description": "Run inspect test envelope",
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
                    "requires_approval": False,
                    "approval_id": None,
                    "payload_refs": [],
                },
                "preflight": {"status": "pass", "findings": []},
                "created_at": "2026-07-03T10:00:00+08:00",
            }
        ],
    }


def test_run_inspect_json_output_structure(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    _write_tasks(fake_root)
    _write_events(fake_root)
    envelope = _make_envelope()
    envelope_path = fake_root / "drafts" / "runtime" / "run-inspect.envelope.json"
    envelope_path.parent.mkdir(parents=True, exist_ok=True)
    envelope_path.write_text(json.dumps(envelope, ensure_ascii=False), encoding="utf-8")

    code = main([
        "--root", str(fake_root),
        "orchestration", "run", "inspect",
        "--task-id", "task-20260703-001",
        "--request-id", "req-20260703-001",
        "--envelope", str(envelope_path),
        "--json",
    ])
    captured = capsys.readouterr()
    assert code in (0, 4)
    result = json.loads(captured.out)
    assert result["status"] in ("pass", "needs_input")
    assert result["task_id"] == "task-20260703-001"
    assert result["request_id"] == "req-20260703-001"
    assert result["task_status"] == "running"
    assert "envelope_summary" in result
    assert "gate" in result
    assert "ledger" in result
    assert "event_summary" in result
    assert "task_snapshot" in result
    assert "next_action" in result


def test_run_inspect_human_readable_smoke(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    _write_tasks(fake_root)
    _write_events(fake_root)
    envelope = _make_envelope()
    envelope_path = fake_root / "drafts" / "runtime" / "run-inspect.envelope.json"
    envelope_path.parent.mkdir(parents=True, exist_ok=True)
    envelope_path.write_text(json.dumps(envelope, ensure_ascii=False), encoding="utf-8")

    code = main([
        "--root", str(fake_root),
        "orchestration", "run", "inspect",
        "--task-id", "task-20260703-001",
        "--request-id", "req-20260703-001",
        "--envelope", str(envelope_path),
    ])
    captured = capsys.readouterr()
    assert code in (0, 4)
    assert "RUN INSPECT" in captured.out
    assert "task-20260703-001" in captured.out
    assert "req-20260703-001" in captured.out


def test_run_inspect_missing_task(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    envelope = _make_envelope()
    envelope_path = fake_root / "drafts" / "runtime" / "run-inspect.envelope.json"
    envelope_path.parent.mkdir(parents=True, exist_ok=True)
    envelope_path.write_text(json.dumps(envelope, ensure_ascii=False), encoding="utf-8")

    code = main([
        "--root", str(fake_root),
        "orchestration", "run", "inspect",
        "--task-id", "task-missing-001",
        "--request-id", "req-20260703-001",
        "--envelope", str(envelope_path),
        "--json",
    ])
    captured = capsys.readouterr()
    assert code != 0
    result = json.loads(captured.out)
    assert result["status"] == "error"
    assert result["task_id"] == "task-missing-001"


def test_run_inspect_missing_envelope(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    _write_tasks(fake_root)
    _write_events(fake_root)

    code = main([
        "--root", str(fake_root),
        "orchestration", "run", "inspect",
        "--task-id", "task-20260703-001",
        "--request-id", "req-20260703-001",
        "--envelope", "drafts/runtime/nonexistent.envelope.json",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code != 0
    result = json.loads(captured.out)
    assert result["status"] == "error"


def test_run_inspect_does_not_write_files(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    _write_tasks(fake_root)
    _write_events(fake_root)
    envelope = _make_envelope()
    envelope_path = fake_root / "drafts" / "runtime" / "run-inspect.envelope.json"
    envelope_path.parent.mkdir(parents=True, exist_ok=True)
    envelope_path.write_text(json.dumps(envelope, ensure_ascii=False), encoding="utf-8")
    tasks_before = (fake_root / "tasks" / "tasks.jsonl").read_bytes()
    events_before = (fake_root / "tasks" / "events.jsonl").read_bytes()
    envelope_before = envelope_path.read_bytes()

    code = main([
        "--root", str(fake_root),
        "orchestration", "run", "inspect",
        "--task-id", "task-20260703-001",
        "--request-id", "req-20260703-001",
        "--envelope", str(envelope_path),
        "--json",
    ])
    assert code in (0, 4)
    assert (fake_root / "tasks" / "tasks.jsonl").read_bytes() == tasks_before
    assert (fake_root / "tasks" / "events.jsonl").read_bytes() == events_before
    assert envelope_path.read_bytes() == envelope_before
