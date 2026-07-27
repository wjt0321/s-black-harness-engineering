from __future__ import annotations

from pathlib import Path

from agent_runtime.external_agent_evidence_store import prepare_evidence
from agent_runtime.orchestration_external_agent_evidence import (
    inspect_external_agent_evidence,
    recover_external_agent_evidence,
)


def _pending(root: Path) -> None:
    events = [
        {"sequence": 1, "event_type": "request_claimed", "occurred_at": "2026-07-27T12:00:00Z"},
        {"sequence": 2, "event_type": "host_turn_dispatched", "occurred_at": "2026-07-27T12:00:01Z"},
        {"sequence": 3, "event_type": "host_turn_started", "occurred_at": "2026-07-27T12:00:02Z"},
        {"sequence": 4, "event_type": "host_turn_completed", "occurred_at": "2026-07-27T12:00:03Z"},
    ]
    prepare_evidence(
        root,
        attempt_id="attempt-stage88-evidence-001",
        task_id="task-stage88",
        request_id="request-stage88-evidence-001",
        collaboration_file="adapters/stage88-plan.json",
        collaboration_plan_id="sha256:" + "1" * 64,
        work_item_id="implement",
        target_profile="pi-local",
        plan_hash="sha256:" + "2" * 64,
        approval_binding_id="sha256:" + "3" * 64,
        completed_at="2026-07-27T12:00:03Z",
        host_events=events,
        output="阶段88证据读取。",
        expected_artifact_types=["test_result"],
        review_required=False,
        review_gate_id=None,
    )


def test_inspect_reports_recovery_pending_without_content(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    _pending(root)

    result = inspect_external_agent_evidence(root, "attempt-stage88-evidence-001", include_content=False)

    assert result.status == "pass"
    assert result.evidence["archive_status"] == "recovery_pending"
    assert "content" not in result.evidence["artifact"]
    assert result.evidence["events"][0]["label_zh"] == "请求已领取"


def test_exact_recovery_binding_finalizes_without_rerunning_agent(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    _pending(root)
    preview = recover_external_agent_evidence(
        root, "attempt-stage88-evidence-001", approval_binding_id=None, commit=False
    )
    wrong = recover_external_agent_evidence(
        root, "attempt-stage88-evidence-001", approval_binding_id="sha256:" + "0" * 64, commit=True
    )
    committed = recover_external_agent_evidence(
        root, "attempt-stage88-evidence-001", approval_binding_id=preview.approval_binding_id, commit=True
    )

    assert preview.status == "needs_approval"
    assert wrong.status == "blocked"
    assert committed.status == "pass"
    assert committed.evidence["archive_status"] == "archived"


def test_archived_evidence_can_include_safe_artifact_content(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    _pending(root)
    preview = recover_external_agent_evidence(
        root, "attempt-stage88-evidence-001", approval_binding_id=None, commit=False
    )
    recover_external_agent_evidence(
        root, "attempt-stage88-evidence-001", approval_binding_id=preview.approval_binding_id, commit=True
    )

    result = inspect_external_agent_evidence(root, "attempt-stage88-evidence-001", include_content=True)

    assert result.evidence["artifact"]["content"] == "阶段88证据读取。"
    assert result.evidence["review_status"] == "not_required"
