from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from agent_runtime.orchestration_report import generate_report
from agent_runtime.orchestration_run import inspect_run


ROOT = Path(__file__).resolve().parents[1]
TASK_ID = "task-20260712-001"


def _setup_root(tmp_path: Path, request_id: str) -> tuple[Path, str, str]:
    root = tmp_path / "project"
    root.mkdir()
    schema_src = ROOT / "adapters" / "execution-envelope.schema.json"
    schema_dst = root / "adapters" / "execution-envelope.schema.json"
    schema_dst.parent.mkdir(parents=True, exist_ok=True)
    schema_dst.write_text(schema_src.read_text(encoding="utf-8"), encoding="utf-8")

    tasks_path = root / "tasks" / "tasks.jsonl"
    tasks_path.parent.mkdir(parents=True, exist_ok=True)
    task = {
        "id": TASK_ID,
        "title": "Recovery read model contract",
        "status": "running",
        "created_at": "2026-07-12T00:00:00Z",
        "updated_at": "2026-07-12T00:00:00Z",
        "created_by": "test",
        "source": "cli",
        "assignee": "orchestrator",
        "evidence": [],
        "artifacts": [],
    }
    tasks_path.write_text(json.dumps(task) + "\n", encoding="utf-8")

    envelope_path = root / "drafts" / "runtime" / "contract.envelope.json"
    envelope_path.parent.mkdir(parents=True, exist_ok=True)
    envelope = {
        "version": 1,
        "description": "Recovery read model contract envelope",
        "artifacts": [
            {
                "artifact_type": "adapter_request",
                "request_id": request_id,
                "task_id": TASK_ID,
                "adapter_id": "github-cli",
                "operation": "git_push",
                "actor": "test",
                "target": "origin/sensitive-target",
                "input": {"remote": "origin", "branch": "sensitive-payload"},
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
                "created_at": "2026-07-12T00:00:00Z",
            }
        ],
    }
    envelope_path.write_text(json.dumps(envelope), encoding="utf-8")
    return root, "drafts/runtime/contract.envelope.json", "tasks/events.jsonl"


def _event(
    request_id: str,
    *,
    task_id: str = TASK_ID,
    lineage_type: str | None = None,
    retry_of: str | None = None,
    plan_hash_char: str = "a",
) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "request_id": request_id,
        "adapter_id": "dummy",
        "plan_hash": "sha256:" + plan_hash_char * 64,
        "envelope_path": f"drafts/runtime/{request_id}.envelope.json",
    }
    if lineage_type is not None:
        metadata["lineage_type"] = lineage_type
    if retry_of is not None:
        metadata["retry_of"] = retry_of
    return {
        "event_id": f"evt-{task_id}-{request_id}-{plan_hash_char}",
        "task_id": task_id,
        "timestamp": "2026-07-12T00:00:00Z",
        "actor": "cli",
        "event_type": "run_planned",
        "message": "safe",
        "metadata": metadata,
    }


def _write_events(root: Path, events: list[dict[str, Any]]) -> Path:
    path = root / "tasks" / "events.jsonl"
    lifecycle_events = [
        {
            "event_id": "evt-contract-created",
            "task_id": TASK_ID,
            "timestamp": "2026-07-12T00:00:00Z",
            "actor": "test",
            "event_type": "created",
            "from_status": None,
            "to_status": "planned",
            "message": "Task created.",
        },
        {
            "event_id": "evt-contract-running",
            "task_id": TASK_ID,
            "timestamp": "2026-07-12T00:00:01Z",
            "actor": "test",
            "event_type": "status_changed",
            "from_status": "planned",
            "to_status": "running",
            "message": "Task started.",
        },
        *events,
    ]
    path.write_text(
        "".join(
            json.dumps(event, ensure_ascii=False) + "\n"
            for event in lifecycle_events
        ),
        encoding="utf-8",
    )
    return path


def _project_both(
    root: Path, envelope_file: str, events_file: str, request_id: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    inspect_result = inspect_run(
        root,
        task_id=TASK_ID,
        request_id=request_id,
        envelope_file=envelope_file,
        events_file=events_file,
        aggregate_lineage=True,
    )
    report_result = generate_report(
        root,
        task_id=TASK_ID,
        request_id=request_id,
        envelope_file=envelope_file,
        events_file=events_file,
        aggregate_lineage=True,
    )
    assert inspect_result.recovery_lineage is not None
    assert report_result.recovery_lineage is not None
    return inspect_result.to_dict(), report_result.to_dict()


def test_inspect_and_report_share_identical_recovery_lineage(tmp_path: Path) -> None:
    root, envelope_file, events_file = _setup_root(tmp_path, "req-20260712-002")
    events_path = _write_events(
        root,
        [
            _event("req-20260712-001", plan_hash_char="a"),
            _event(
                "req-20260712-002",
                lineage_type="retry",
                retry_of="req-20260712-001",
                plan_hash_char="b",
            ),
        ],
    )
    before = events_path.read_bytes()

    inspect_dict, report_dict = _project_both(
        root, envelope_file, events_file, "req-20260712-002"
    )

    assert inspect_dict["status"] == report_dict["status"]
    assert inspect_dict["recovery_lineage"] == report_dict["recovery_lineage"]
    assert inspect_dict["recovery_lineage"]["status"] == "pass"
    serialized = json.dumps(inspect_dict["recovery_lineage"], ensure_ascii=False)
    assert "sensitive-target" not in serialized
    assert "sensitive-payload" not in serialized
    assert events_path.read_bytes() == before


@pytest.mark.parametrize(
    ("focus_request_id", "events", "expected_status", "expected_issue"),
    [
        (
            "req-20260712-001",
            [
                _event("req-20260712-001"),
                _event("req-20260712-002", lineage_type="retry", retry_of="req-20260712-001"),
                _event("req-20260712-003", lineage_type="retry", retry_of="req-20260712-001"),
            ],
            "needs_input",
            "ambiguous_leaves",
        ),
        ("req-20260712-002", [], "validation_failed", "focus_request_not_found"),
        (
            "req-20260712-002",
            [_event("req-20260712-002", lineage_type="retry", retry_of="req-20260712-999")],
            "validation_failed",
            "missing_parent",
        ),
        (
            "req-20260712-002",
            [
                _event("req-20260712-998", task_id="task-other"),
                _event("req-20260712-002", lineage_type="retry", retry_of="req-20260712-998"),
            ],
            "validation_failed",
            "cross_task_parent",
        ),
        (
            "req-20260712-002",
            [
                _event("req-20260712-002", lineage_type="retry", retry_of="req-20260712-003"),
                _event("req-20260712-003", lineage_type="retry", retry_of="req-20260712-002"),
            ],
            "validation_failed",
            "cycle_detected",
        ),
        (
            "req-20260712-001",
            [
                _event("req-20260712-001", plan_hash_char="a"),
                _event("req-20260712-001", plan_hash_char="b"),
            ],
            "validation_failed",
            "conflicting_request_metadata",
        ),
    ],
)
def test_inspect_and_report_share_exception_semantics(
    tmp_path: Path,
    focus_request_id: str,
    events: list[dict[str, Any]],
    expected_status: str,
    expected_issue: str,
) -> None:
    root, envelope_file, events_file = _setup_root(tmp_path, focus_request_id)
    events_path = _write_events(root, events)
    before = events_path.read_bytes()

    inspect_dict, report_dict = _project_both(
        root, envelope_file, events_file, focus_request_id
    )

    assert inspect_dict["status"] == report_dict["status"]
    assert inspect_dict["recovery_lineage"] == report_dict["recovery_lineage"]
    assert inspect_dict["recovery_lineage"]["status"] == expected_status
    assert [
        issue["code"] for issue in inspect_dict["recovery_lineage"]["issues"]
    ] == [expected_issue]
    assert events_path.read_bytes() == before
