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


def _append_run_events(fake_root: Path, events: list[dict[str, Any]]) -> None:
    events_file = fake_root / "tasks" / "events.jsonl"
    with events_file.open("a", encoding="utf-8") as handle:
        for event in events:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")


def _run_event(
    request_id: str,
    *,
    lineage_type: str | None = None,
    retry_of: str | None = None,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "request_id": request_id,
        "adapter_id": "github-cli",
        "plan_hash": "sha256:" + request_id[-1] * 64,
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
        "message": "safe",
        "metadata": metadata,
    }


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
    assert "replay" not in result


def test_report_generate_replay_matches_run_inspect_and_is_no_write(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    _write_tasks(fake_root)
    _write_events(fake_root)
    envelope = _make_envelope()
    envelope_path = fake_root / "drafts" / "runtime" / "report-replay.envelope.json"
    envelope_path.parent.mkdir(parents=True, exist_ok=True)
    envelope_path.write_text(json.dumps(envelope, ensure_ascii=False), encoding="utf-8")

    tasks_before = (fake_root / "tasks" / "tasks.jsonl").read_bytes()
    events_before = (fake_root / "tasks" / "events.jsonl").read_bytes()
    envelope_before = envelope_path.read_bytes()
    common = [
        "--root", str(fake_root),
        "--task-id", "task-20260703-001",
        "--request-id", "req-20260703-001",
        "--envelope", str(envelope_path),
        "--replay",
        "--json",
    ]

    run_code = main(common[:2] + ["orchestration", "run", "inspect"] + common[2:])
    run_output = json.loads(capsys.readouterr().out)
    report_code = main(common[:2] + ["orchestration", "report", "generate"] + common[2:])
    report_output = json.loads(capsys.readouterr().out)

    assert run_code == report_code == 3
    assert run_output["replay"] == report_output["replay"]
    assert run_output["replay"]["schema_version"] == "control-plane/orchestration-replay/v1"
    assert run_output["replay"]["next_action"]["code"] == "blocked_wait_for_approval"
    serialized = json.dumps(run_output["replay"], ensure_ascii=False)
    assert "origin/main" not in serialized
    assert "decision_ref" not in serialized
    assert (fake_root / "tasks" / "tasks.jsonl").read_bytes() == tasks_before
    assert (fake_root / "tasks" / "events.jsonl").read_bytes() == events_before
    assert envelope_path.read_bytes() == envelope_before


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


def test_report_generate_aggregate_lineage_json_and_default_compatibility(capsys, tmp_path):
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
    envelope_path = fake_root / "drafts" / "runtime" / "report-retry.envelope.json"
    envelope_path.parent.mkdir(parents=True, exist_ok=True)
    envelope_path.write_text(json.dumps(envelope, ensure_ascii=False), encoding="utf-8")

    base_args = [
        "--root", str(fake_root),
        "orchestration", "report", "generate",
        "--task-id", "task-20260703-001",
        "--request-id", "req-20260703-002",
        "--envelope", str(envelope_path),
        "--events-file", "tasks/events.jsonl",
        "--json",
    ]
    default_code = main(base_args)
    default_result = json.loads(capsys.readouterr().out)
    aggregate_code = main(base_args[:-1] + ["--aggregate-lineage", "--json"])
    aggregate_result = json.loads(capsys.readouterr().out)

    assert default_code in (0, 4)
    assert "recovery_lineage" not in default_result
    assert aggregate_code in (0, 4)
    lineage = aggregate_result["recovery_lineage"]
    assert lineage["schema_version"] == "control-plane/recovery-lineage/v1"
    assert lineage["root_request_id"] == "req-20260703-001"
    assert lineage["latest_request_id"] == "req-20260703-002"
    assert lineage["attempt_count"] == 2
    assert "origin/main" not in json.dumps(lineage)


def test_report_generate_aggregate_lineage_human_is_compact(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    _write_tasks(fake_root)
    _write_events(fake_root)
    _append_run_events(fake_root, [_run_event("req-20260703-001")])
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
        "--events-file", "tasks/events.jsonl",
        "--aggregate-lineage",
    ])
    output = capsys.readouterr().out

    assert code == 3
    assert "Recovery lineage:" in output
    assert "root=req-20260703-001" in output
    assert "latest=req-20260703-001" in output
    assert "attempts=1" in output
    assert "origin/main" not in output


def test_report_generate_aggregate_lineage_validation_failure_wins(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    _write_tasks(fake_root)
    _write_events(fake_root)
    envelope = _make_envelope()
    envelope_path = fake_root / "drafts" / "runtime" / "report.envelope.json"
    envelope_path.parent.mkdir(parents=True, exist_ok=True)
    envelope_path.write_text(json.dumps(envelope, ensure_ascii=False), encoding="utf-8")
    events_path = fake_root / "tasks" / "events.jsonl"
    before = events_path.read_bytes()

    code = main([
        "--root", str(fake_root),
        "orchestration", "report", "generate",
        "--task-id", "task-20260703-001",
        "--request-id", "req-20260703-001",
        "--envelope", str(envelope_path),
        "--events-file", "tasks/events.jsonl",
        "--aggregate-lineage",
        "--json",
    ])
    result = json.loads(capsys.readouterr().out)

    assert code == 5
    assert result["status"] == "validation_failed"
    assert result["recovery_lineage"]["issues"] == [
        {"code": "focus_request_not_found", "request_id": "req-20260703-001"}
    ]
    assert events_path.read_bytes() == before
