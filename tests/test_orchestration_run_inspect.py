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
    assert "replay" not in result


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


def _make_envelope_with_lineage(lineage: dict[str, Any]) -> dict[str, Any]:
    """Build a minimal envelope with lineage in adapter_request.context."""
    envelope = _make_envelope()
    request = envelope["artifacts"][0]
    request["request_id"] = "req-20260703-002"
    request["context"].update(lineage)
    return envelope


def test_run_inspect_retry_lineage_json(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    _write_tasks(fake_root)
    _write_events(fake_root)
    envelope = _make_envelope_with_lineage(
        {"lineage_type": "retry", "retry_of": "req-20260703-001"}
    )
    envelope_path = fake_root / "drafts" / "runtime" / "run-inspect-retry.envelope.json"
    envelope_path.parent.mkdir(parents=True, exist_ok=True)
    envelope_path.write_text(json.dumps(envelope, ensure_ascii=False), encoding="utf-8")

    code = main([
        "--root", str(fake_root),
        "orchestration", "run", "inspect",
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
    assert "fallback_from" not in result
    assert "fallback_to" not in result
    # Sensitive values from the envelope must not leak.
    assert "origin/main" not in captured.out
    assert "origin" not in captured.out


def test_run_inspect_fallback_lineage_json(capsys, tmp_path):
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
    envelope_path = fake_root / "drafts" / "runtime" / "run-inspect-fallback.envelope.json"
    envelope_path.parent.mkdir(parents=True, exist_ok=True)
    envelope_path.write_text(json.dumps(envelope, ensure_ascii=False), encoding="utf-8")

    code = main([
        "--root", str(fake_root),
        "orchestration", "run", "inspect",
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
    assert "retry_of" not in result


def test_run_inspect_retry_lineage_human(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    _write_tasks(fake_root)
    _write_events(fake_root)
    envelope = _make_envelope_with_lineage(
        {"lineage_type": "retry", "retry_of": "req-20260703-001"}
    )
    envelope_path = fake_root / "drafts" / "runtime" / "run-inspect-retry.envelope.json"
    envelope_path.parent.mkdir(parents=True, exist_ok=True)
    envelope_path.write_text(json.dumps(envelope, ensure_ascii=False), encoding="utf-8")

    code = main([
        "--root", str(fake_root),
        "orchestration", "run", "inspect",
        "--task-id", "task-20260703-001",
        "--request-id", "req-20260703-002",
        "--envelope", str(envelope_path),
    ])
    captured = capsys.readouterr()
    assert code in (0, 4)
    assert "lineage_type=retry" in captured.out
    assert "retry_of=req-20260703-001" in captured.out
    assert "origin/main" not in captured.out


def test_run_inspect_normal_run_no_lineage(capsys, tmp_path):
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
    assert "lineage_type" not in result
    assert "retry_of" not in result
    assert "fallback_from" not in result
    assert "fallback_to" not in result


def _append_run_events(root: Path, events: list[dict[str, Any]]) -> None:
    events_file = root / "tasks" / "events.jsonl"
    with events_file.open("a", encoding="utf-8") as fh:
        for event in events:
            fh.write(json.dumps(event, ensure_ascii=False) + "\n")


def _run_event(
    request_id: str,
    *,
    lineage_type: str | None = None,
    retry_of: str | None = None,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "request_id": request_id,
        "adapter_id": "github-cli",
        "capability": "git_push",
        "operation": "git_push",
        "mode": "dry-run",
        "plan_hash": "sha256:" + ("a" if retry_of is None else "b") * 64,
        "freeze_check": "pass",
        "approval_status": "not_required",
        "envelope_path": f"drafts/runtime/{request_id}.envelope.json",
    }
    if lineage_type is not None:
        metadata["lineage_type"] = lineage_type
    if retry_of is not None:
        metadata["retry_of"] = retry_of
    return {
        "event_id": f"evt-{request_id}",
        "task_id": "task-20260703-001",
        "timestamp": "2026-07-12T00:00:00Z",
        "actor": "cli",
        "event_type": "run_planned",
        "message": "Run plan generated and frozen.",
        "metadata": metadata,
    }


def test_run_inspect_aggregate_lineage_json(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    _write_tasks(fake_root)
    _write_events(fake_root)
    _append_run_events(
        fake_root,
        [
            _run_event("req-20260703-001"),
            _run_event(
                "req-20260703-002",
                lineage_type="retry",
                retry_of="req-20260703-001",
            ),
        ],
    )
    envelope = _make_envelope_with_lineage(
        {"lineage_type": "retry", "retry_of": "req-20260703-001"}
    )
    envelope_path = fake_root / "drafts" / "runtime" / "run-inspect-retry.envelope.json"
    envelope_path.parent.mkdir(parents=True, exist_ok=True)
    envelope_path.write_text(json.dumps(envelope, ensure_ascii=False), encoding="utf-8")

    code = main([
        "--root", str(fake_root),
        "orchestration", "run", "inspect",
        "--task-id", "task-20260703-001",
        "--request-id", "req-20260703-002",
        "--envelope", str(envelope_path),
        "--events-file", "tasks/events.jsonl",
        "--aggregate-lineage",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code in (0, 4)
    result = json.loads(captured.out)
    aggregation = result["recovery_lineage"]
    assert aggregation["schema_version"] == "control-plane/recovery-lineage/v1"
    assert aggregation["root_request_id"] == "req-20260703-001"
    assert aggregation["latest_request_id"] == "req-20260703-002"
    assert aggregation["attempt_count"] == 2
    assert [item["request_id"] for item in aggregation["requests"]] == [
        "req-20260703-001",
        "req-20260703-002",
    ]
    assert "origin/main" not in captured.out


def test_run_inspect_aggregate_lineage_human(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    _write_tasks(fake_root)
    _write_events(fake_root)
    _append_run_events(fake_root, [_run_event("req-20260703-001")])
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
        "--events-file", "tasks/events.jsonl",
        "--aggregate-lineage",
    ])
    captured = capsys.readouterr()
    assert code in (0, 4)
    assert "Recovery lineage:" in captured.out
    assert "root=req-20260703-001" in captured.out
    assert "latest=req-20260703-001" in captured.out
    assert "attempts=1" in captured.out


def test_run_inspect_default_output_omits_recovery_lineage(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    _write_tasks(fake_root)
    _write_events(fake_root)
    _append_run_events(fake_root, [_run_event("req-20260703-001")])
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
    assert "recovery_lineage" not in json.loads(captured.out)


def test_run_inspect_aggregate_lineage_missing_focus_is_validation_failed(capsys, tmp_path):
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
        "--events-file", "tasks/events.jsonl",
        "--aggregate-lineage",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 5
    result = json.loads(captured.out)
    assert result["status"] == "validation_failed"
    assert result["recovery_lineage"]["issues"] == [
        {"code": "focus_request_not_found", "request_id": "req-20260703-001"}
    ]
