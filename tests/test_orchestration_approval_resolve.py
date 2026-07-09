"""Tests for orchestration approval resolve controlled-write command."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from agent_runtime.cli import main


ROOT = Path(__file__).resolve().parents[1]

APPROVAL_ID = "appr-20260709-001"
REQUEST_ID = "req-20260709-001"
TASK_ID = "task-20260709-001"


def _setup_fake_root(tmp_path: Path) -> Path:
    """Create a fake project root with required schemas."""
    fake_root = tmp_path / "project"
    fake_root.mkdir()
    for src in [
        ROOT / "adapters" / "execution-envelope.schema.json",
        ROOT / "tasks" / "event.schema.json",
        ROOT / "tasks" / "task.schema.json",
    ]:
        dst = fake_root / src.relative_to(ROOT)
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    return fake_root


def _write_envelope(
    fake_root: Path,
    approval_status: str = "pending",
    approval_id: str = APPROVAL_ID,
    request_id: str = REQUEST_ID,
    task_id: str = TASK_ID,
) -> None:
    """Write an envelope with an adapter_request and an approval_record."""
    envelope = {
        "version": 1,
        "description": "Test envelope",
        "artifacts": [
            {
                "artifact_type": "adapter_request",
                "request_id": request_id,
                "task_id": task_id,
                "adapter_id": "github-cli",
                "operation": "git_push",
                "actor": "cli",
                "target": "origin/main",
                "input": {"operation": "git_push", "target": "origin/main"},
                "context": {
                    "source": "cli",
                    "policy_profile": "all",
                    "risk_level": "external",
                    "dry_run": True,
                    "requires_approval": True,
                    "approval_id": approval_id,
                    "payload_refs": [],
                },
                "preflight": {"status": "needs_approval", "findings": []},
                "created_at": "2026-07-09T10:00:00+00:00",
            },
            {
                "artifact_type": "approval_record",
                "approval_id": approval_id,
                "request_id": request_id,
                "status": approval_status,
                "scope": {
                    "task_id": task_id,
                    "adapter_id": "github-cli",
                    "operation": "git_push",
                    "target": "origin/main",
                },
                "requested_at": "2026-07-09T10:00:00+00:00",
                "decided_at": None,
                "decided_by": None,
                "decision_ref": None,
            },
        ],
    }
    path = fake_root / "envelope.json"
    path.write_text(json.dumps(envelope, ensure_ascii=False), encoding="utf-8")


def _write_task(fake_root: Path, task_id: str = TASK_ID) -> None:
    """Write a single task to the ledger."""
    tasks_file = fake_root / "tasks" / "tasks.jsonl"
    tasks_file.parent.mkdir(parents=True, exist_ok=True)
    task = {
        "id": task_id,
        "title": "Approval resolve test task",
        "status": "running",
        "created_at": "2026-07-09T10:00:00+08:00",
        "updated_at": "2026-07-09T10:00:00+08:00",
        "created_by": "cli",
        "source": "cli",
        "assignee": "orchestrator",
        "requested_capability": "git_push",
    }
    tasks_file.write_text(json.dumps(task) + "\n", encoding="utf-8")


def _write_events(fake_root: Path, invalid_existing: bool = False) -> Path:
    """Write an empty or malformed events ledger that ends with a newline."""
    events_file = fake_root / "tasks" / "events.jsonl"
    events_file.parent.mkdir(parents=True, exist_ok=True)
    if invalid_existing:
        # Valid JSON but missing required fields; triggers post-append rollback.
        events_file.write_text('{"task_id": "task-20260709-001"}\n', encoding="utf-8")
    else:
        events_file.write_text("", encoding="utf-8")
    return events_file


def _base_args(
    fake_root: Path,
    decision: str = "granted",
    reason: str = "reviewed and approved",
    mode: str = "--dry-run",
) -> list[str]:
    return [
        "--root", str(fake_root),
        "orchestration", "approval", "resolve",
        "--approval-id", APPROVAL_ID,
        "--task-id", TASK_ID,
        "--request-id", REQUEST_ID,
        "--decision", decision,
        "--reason", reason,
        "--envelope", "envelope.json",
        "--events-file", "tasks/events.jsonl",
        mode,
    ]


def test_resolve_dry_run_does_not_write_events(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    _write_envelope(fake_root)
    _write_task(fake_root)
    events_file = _write_events(fake_root)
    before = events_file.read_bytes()

    code = main(_base_args(fake_root, mode="--dry-run") + ["--json"])
    captured = capsys.readouterr()
    assert code == 0
    result = json.loads(captured.out)
    assert result["status"] == "pass"
    assert result["mode"] == "dry-run"
    assert result["approval_id"] == APPROVAL_ID
    assert result["event_preview"]["event_type"] == "approval_resolved"
    assert result["event_preview"]["task_id"] == TASK_ID
    assert result["event_preview"]["metadata"]["decision"] == "granted"
    assert events_file.read_bytes() == before


def test_resolve_commit_appends_event(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    _write_envelope(fake_root)
    _write_task(fake_root)
    events_file = _write_events(fake_root)

    code = main(_base_args(fake_root, mode="--commit") + ["--json"])
    captured = capsys.readouterr()
    assert code == 0
    result = json.loads(captured.out)
    assert result["status"] == "pass"
    assert result["mode"] == "commit"
    assert result["event_written"]["event_type"] == "approval_resolved"
    assert result["write_summary"]["committed"] is True
    assert result["write_summary"]["rolled_back"] is False
    assert result["write_summary"]["post_validate"] == "pass"
    assert result["write_summary"]["post_ledger_check"] == "pass"

    lines = events_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    event = json.loads(lines[0])
    assert event["event_type"] == "approval_resolved"
    assert event["metadata"]["approval_id"] == APPROVAL_ID
    assert event["metadata"]["decision"] == "granted"


def test_resolve_commit_rollback_on_post_check_failure(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    _write_envelope(fake_root)
    _write_task(fake_root)
    events_file = _write_events(fake_root, invalid_existing=True)
    before = events_file.read_bytes()

    code = main(_base_args(fake_root, mode="--commit") + ["--json"])
    captured = capsys.readouterr()
    result = json.loads(captured.out)
    assert result["status"] in {"validation_failed", "error"}
    assert result["write_summary"]["committed"] is False
    assert result["write_summary"]["rolled_back"] is True
    assert events_file.read_bytes() == before


def test_resolve_missing_approval(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    _write_envelope(fake_root)
    _write_task(fake_root)
    events_file = _write_events(fake_root)
    before = events_file.read_bytes()

    args = _base_args(fake_root, mode="--dry-run")
    args[args.index("--approval-id") + 1] = "appr-missing-001"
    code = main(args + ["--json"])
    captured = capsys.readouterr()
    result = json.loads(captured.out)
    assert result["status"] == "needs_input"
    assert "approval" in result["next_action"].lower()
    assert events_file.read_bytes() == before


def test_resolve_task_mismatch(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    _write_envelope(fake_root)
    _write_task(fake_root)
    events_file = _write_events(fake_root)
    before = events_file.read_bytes()

    args = _base_args(fake_root, mode="--dry-run")
    args[args.index("--task-id") + 1] = "task-20260709-999"
    code = main(args + ["--json"])
    captured = capsys.readouterr()
    result = json.loads(captured.out)
    assert result["status"] == "blocked"
    assert "task_id" in result["next_action"].lower()
    assert events_file.read_bytes() == before


def test_resolve_request_mismatch(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    _write_envelope(fake_root)
    _write_task(fake_root)
    events_file = _write_events(fake_root)
    before = events_file.read_bytes()

    args = _base_args(fake_root, mode="--dry-run")
    args[args.index("--request-id") + 1] = "req-20260709-999"
    code = main(args + ["--json"])
    captured = capsys.readouterr()
    result = json.loads(captured.out)
    assert result["status"] == "blocked"
    assert "request_id" in result["next_action"].lower()
    assert events_file.read_bytes() == before


def test_resolve_invalid_decision(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    _write_envelope(fake_root)
    _write_task(fake_root)
    events_file = _write_events(fake_root)
    before = events_file.read_bytes()

    args = _base_args(fake_root, decision="unknown", mode="--dry-run")
    code = main(args + ["--json"])
    captured = capsys.readouterr()
    result = json.loads(captured.out)
    assert result["status"] in {"validation_failed", "error"}
    assert events_file.read_bytes() == before


def test_resolve_missing_reason(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    _write_envelope(fake_root)
    _write_task(fake_root)
    events_file = _write_events(fake_root)
    before = events_file.read_bytes()

    args = _base_args(fake_root, mode="--dry-run")
    idx = args.index("--reason")
    args = args[:idx] + args[idx + 2:]  # remove --reason and its value
    code = main(args + ["--json"])
    captured = capsys.readouterr()
    result = json.loads(captured.out)
    assert result["status"] in {"needs_input", "validation_failed", "error"}
    assert events_file.read_bytes() == before


def test_resolve_dry_run_and_commit_conflict(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    _write_envelope(fake_root)
    _write_task(fake_root)
    events_file = _write_events(fake_root)
    before = events_file.read_bytes()

    args = _base_args(fake_root, mode="--dry-run") + ["--commit"]
    code = main(args + ["--json"])
    captured = capsys.readouterr()
    result = json.loads(captured.out)
    assert result["status"] == "error"
    assert events_file.read_bytes() == before


def test_resolve_human_readable_smoke(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    _write_envelope(fake_root)
    _write_task(fake_root)
    _write_events(fake_root)

    code = main(_base_args(fake_root, mode="--dry-run"))
    captured = capsys.readouterr()
    assert code == 0
    assert "APPROVAL RESOLVE" in captured.out
    assert APPROVAL_ID in captured.out
    assert "granted" in captured.out
    assert "dry-run" in captured.out


def test_resolve_granted_next_action_requires_new_preflight(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    _write_envelope(fake_root)
    _write_task(fake_root)
    _write_events(fake_root)

    code = main(_base_args(fake_root, decision="granted", mode="--commit") + ["--json"])
    captured = capsys.readouterr()
    result = json.loads(captured.out)
    assert code == 0
    assert result["status"] == "pass"
    assert "preflight" in result["next_action"].lower() or "run" in result["next_action"].lower()


def test_resolve_denied_records_decision(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    _write_envelope(fake_root)
    _write_task(fake_root)
    events_file = _write_events(fake_root)

    code = main(_base_args(fake_root, decision="denied", reason="target not confirmed", mode="--commit") + ["--json"])
    captured = capsys.readouterr()
    result = json.loads(captured.out)
    assert code == 0
    assert result["status"] == "pass"
    assert result["decision"] == "denied"

    lines = events_file.read_text(encoding="utf-8").strip().splitlines()
    event = json.loads(lines[0])
    assert event["metadata"]["decision"] == "denied"


def test_resolve_no_secret_or_decision_ref_in_output(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    _write_envelope(fake_root)
    _write_task(fake_root)
    _write_events(fake_root)

    code = main(_base_args(fake_root, reason="decision_ref=secret-token-12345", mode="--dry-run") + ["--json"])
    captured = capsys.readouterr()
    result = json.loads(captured.out)
    assert code == 0
    output = captured.out
    assert "secret-token-12345" not in output
    assert "decision_ref" not in output
