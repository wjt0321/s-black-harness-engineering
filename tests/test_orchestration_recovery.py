from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent_runtime.orchestration_recovery import aggregate_recovery_lineage


def _write_events(root: Path, events: list[dict]) -> str:
    path = root / "tasks" / "events.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(event, ensure_ascii=False) + "\n" for event in events),
        encoding="utf-8",
    )
    return "tasks/events.jsonl"


def _event(
    request_id: str,
    *,
    task_id: str = "task-001",
    event_type: str = "run_planned",
    plan_hash: str | None = None,
    adapter_id: str = "dummy",
    lineage_type: str | None = None,
    retry_of: str | None = None,
    fallback_from: str | None = None,
    fallback_to: str | None = None,
) -> dict:
    metadata = {
        "request_id": request_id,
        "adapter_id": adapter_id,
        "capability": "inspect.repo",
        "operation": "inspect",
        "mode": "dry-run",
        "plan_hash": plan_hash or f"sha256:{request_id.replace('-', '0'):0<64}"[:71],
        "freeze_check": "pass",
        "approval_status": "not_required",
        "envelope_path": f"drafts/runtime/{task_id}/{request_id}.envelope.json",
    }
    for key, value in {
        "lineage_type": lineage_type,
        "retry_of": retry_of,
        "fallback_from": fallback_from,
        "fallback_to": fallback_to,
    }.items():
        if value is not None:
            metadata[key] = value
    return {
        "event_id": f"evt-{task_id}-{request_id}-{event_type}",
        "task_id": task_id,
        "event_type": event_type,
        "timestamp": "2026-07-12T00:00:00Z",
        "actor": "cli",
        "message": "safe",
        "metadata": metadata,
    }


def test_normal_run_is_single_node_lineage(tmp_path: Path) -> None:
    events_file = _write_events(tmp_path, [_event("req-root")])

    result = aggregate_recovery_lineage(
        tmp_path,
        task_id="task-001",
        request_id="req-root",
        events_file=events_file,
    )

    assert result.status == "pass"
    assert result.root_request_id == "req-root"
    assert result.latest_request_id == "req-root"
    assert result.leaf_request_ids == ["req-root"]
    assert result.attempt_count == 1
    assert result.requests[0]["relationship"] == "root"
    assert result.issues == []


def test_retry_fallback_chain_is_root_first_and_effective_hash_is_leaf(tmp_path: Path) -> None:
    leaf_hash = "sha256:" + "c" * 64
    events = [
        _event("req-root", plan_hash="sha256:" + "a" * 64),
        _event(
            "req-retry",
            plan_hash="sha256:" + "b" * 64,
            lineage_type="retry",
            retry_of="req-root",
        ),
        _event(
            "req-fallback",
            plan_hash=leaf_hash,
            adapter_id="fallback-adapter",
            lineage_type="fallback",
            fallback_from="req-retry",
            fallback_to="fallback-adapter",
        ),
        _event(
            "req-fallback",
            event_type="run_draft_exported",
            plan_hash=leaf_hash,
            adapter_id="fallback-adapter",
            lineage_type="fallback",
            fallback_from="req-retry",
            fallback_to="fallback-adapter",
        ),
    ]
    events_file = _write_events(tmp_path, events)

    result = aggregate_recovery_lineage(
        tmp_path,
        task_id="task-001",
        request_id="req-retry",
        events_file=events_file,
    )

    assert result.status == "pass"
    assert result.root_request_id == "req-root"
    assert result.latest_request_id == "req-fallback"
    assert result.effective_plan_hash == leaf_hash
    assert result.attempt_count == 3
    assert [item["request_id"] for item in result.requests] == [
        "req-root",
        "req-retry",
        "req-fallback",
    ]
    assert result.requests[1]["relationship"] == "retry"
    assert result.requests[1]["parent_request_id"] == "req-root"
    assert result.requests[2]["relationship"] == "fallback"
    assert result.requests[2]["parent_request_id"] == "req-retry"
    assert result.requests[2]["fallback_to"] == "fallback-adapter"


def test_branch_returns_needs_input_without_guessing_latest(tmp_path: Path) -> None:
    events_file = _write_events(
        tmp_path,
        [
            _event("req-root"),
            _event("req-a", lineage_type="retry", retry_of="req-root"),
            _event("req-b", lineage_type="retry", retry_of="req-root"),
        ],
    )

    result = aggregate_recovery_lineage(
        tmp_path,
        task_id="task-001",
        request_id="req-root",
        events_file=events_file,
    )

    assert result.status == "needs_input"
    assert result.latest_request_id is None
    assert result.effective_plan_hash is None
    assert result.leaf_request_ids == ["req-a", "req-b"]
    assert [issue["code"] for issue in result.issues] == ["ambiguous_leaves"]


@pytest.mark.parametrize(
    ("events", "issue_code"),
    [
        (
            [_event("req-child", lineage_type="retry", retry_of="req-missing")],
            "missing_parent",
        ),
        (
            [
                _event("req-parent", task_id="task-other"),
                _event("req-child", lineage_type="retry", retry_of="req-parent"),
            ],
            "cross_task_parent",
        ),
        (
            [
                _event("req-a", lineage_type="retry", retry_of="req-b"),
                _event("req-b", lineage_type="retry", retry_of="req-a"),
            ],
            "cycle_detected",
        ),
    ],
)
def test_invalid_lineage_returns_validation_failed(
    tmp_path: Path, events: list[dict], issue_code: str
) -> None:
    events_file = _write_events(tmp_path, events)

    result = aggregate_recovery_lineage(
        tmp_path,
        task_id="task-001",
        request_id="req-child" if issue_code != "cycle_detected" else "req-a",
        events_file=events_file,
    )

    assert result.status == "validation_failed"
    assert issue_code in [issue["code"] for issue in result.issues]


def test_conflicting_duplicate_lifecycle_metadata_is_rejected(tmp_path: Path) -> None:
    events_file = _write_events(
        tmp_path,
        [
            _event("req-root", plan_hash="sha256:" + "a" * 64),
            _event(
                "req-root",
                event_type="run_draft_exported",
                plan_hash="sha256:" + "b" * 64,
            ),
        ],
    )

    result = aggregate_recovery_lineage(
        tmp_path,
        task_id="task-001",
        request_id="req-root",
        events_file=events_file,
    )

    assert result.status == "validation_failed"
    assert [issue["code"] for issue in result.issues] == [
        "conflicting_request_metadata"
    ]
    assert "sha256:" not in json.dumps(result.to_dict())


def test_missing_focus_request_is_validation_failed(tmp_path: Path) -> None:
    events_file = _write_events(tmp_path, [_event("req-other")])

    result = aggregate_recovery_lineage(
        tmp_path,
        task_id="task-001",
        request_id="req-missing",
        events_file=events_file,
    )

    assert result.status == "validation_failed"
    assert result.root_request_id is None
    assert result.requests == []
    assert [issue["code"] for issue in result.issues] == ["focus_request_not_found"]


def test_aggregation_is_deterministic_and_does_not_write_events(tmp_path: Path) -> None:
    events_file = _write_events(
        tmp_path,
        [
            _event("req-root"),
            _event("req-child", lineage_type="retry", retry_of="req-root"),
        ],
    )
    path = tmp_path / events_file
    before = path.read_bytes()

    first = aggregate_recovery_lineage(
        tmp_path,
        task_id="task-001",
        request_id="req-child",
        events_file=events_file,
    )
    second = aggregate_recovery_lineage(
        tmp_path,
        task_id="task-001",
        request_id="req-child",
        events_file=events_file,
    )

    assert first.to_dict() == second.to_dict()
    assert path.read_bytes() == before


def test_invalid_lineage_shape_is_rejected(tmp_path: Path) -> None:
    events_file = _write_events(
        tmp_path,
        [_event("req-child", lineage_type="retry")],
    )

    result = aggregate_recovery_lineage(
        tmp_path,
        task_id="task-001",
        request_id="req-child",
        events_file=events_file,
    )

    assert result.status == "validation_failed"
    assert [issue["code"] for issue in result.issues] == ["invalid_lineage_shape"]
