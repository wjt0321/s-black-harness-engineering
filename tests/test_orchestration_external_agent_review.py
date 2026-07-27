from __future__ import annotations

import json
import shutil
from pathlib import Path

from agent_runtime.external_agent_evidence_store import finalize_evidence, inspect_evidence, prepare_evidence
from agent_runtime.orchestration_external_agent_review import review_external_agent_evidence
from agent_runtime.result import CheckResult

ROOT = Path(__file__).resolve().parents[1]


def _project(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    root.mkdir()
    shutil.copytree(ROOT / "adapters", root / "adapters")
    shutil.copytree(ROOT / "policies", root / "policies")
    plan = {
        "parent_task_ref": "task-stage88",
        "revision": 1,
        "socket_bindings": [
            {"socket_id": "omp-acp", "role": "implementer", "required_capabilities": ["light_coding"]},
            {"socket_id": "claude-code-acp", "role": "reviewer", "required_capabilities": ["quality_review"]},
        ],
        "work_items": [{
            "work_item_id": "implement",
            "socket_id": "omp-acp",
            "role": "implementer",
            "depends_on": [],
            "expected_artifact_types": ["test_result"],
            "review_required": True,
        }],
        "handoffs": [],
        "review_gates": [{
            "gate_id": "review-implementation",
            "after_work_item_ids": ["implement"],
            "review_role": "reviewer",
            "decision_options": ["approve", "request_changes"],
        }],
    }
    plan_path = root / "adapters/stage88-review-plan.json"
    plan_path.write_text(json.dumps(plan), encoding="utf-8")
    from agent_runtime.orchestration_collaboration import inspect_collaboration_plan

    inspected = inspect_collaboration_plan(root, "adapters/stage88-review-plan.json")
    assert inspected.status == "pass"
    plan_id = inspected.to_dict()["plan"]["plan_id"]
    events = [
        {"sequence": 1, "event_type": "request_claimed", "occurred_at": "2026-07-27T12:00:00Z"},
        {"sequence": 2, "event_type": "host_turn_dispatched", "occurred_at": "2026-07-27T12:00:01Z"},
        {"sequence": 3, "event_type": "host_turn_started", "occurred_at": "2026-07-27T12:00:02Z"},
        {"sequence": 4, "event_type": "host_turn_completed", "occurred_at": "2026-07-27T12:00:03Z"},
    ]
    prepare_evidence(
        root,
        attempt_id="attempt-stage88-review-001",
        task_id="task-stage88",
        request_id="request-stage88-review-001",
        collaboration_file="adapters/stage88-review-plan.json",
        collaboration_plan_id=plan_id,
        work_item_id="implement",
        target_profile="omp-local",
        plan_hash="sha256:" + "2" * 64,
        approval_binding_id="sha256:" + "3" * 64,
        completed_at="2026-07-27T12:00:03Z",
        host_events=events,
        output="阶段88人工审阅产物。",
        expected_artifact_types=["test_result"],
        review_required=True,
        review_gate_id="review-implementation",
    )
    finalize_evidence(root, "attempt-stage88-review-001")
    return root


def _pass_scan(*_args, **_kwargs) -> CheckResult:
    return CheckResult(status="pass")


def test_review_preview_binds_exact_evidence_without_echoing_comment(tmp_path: Path) -> None:
    root = _project(tmp_path)
    first = review_external_agent_evidence(
        root,
        attempt_id="attempt-stage88-review-001",
        decision="approve",
        comment="结果符合审阅要求。",
        evaluated_at="2026-07-27T12:05:00Z",
        approval_binding_id=None,
        commit=False,
        services={"scan_text": _pass_scan},
    )
    second = review_external_agent_evidence(
        root,
        attempt_id="attempt-stage88-review-001",
        decision="approve",
        comment="结果符合审阅要求。",
        evaluated_at="2026-07-27T12:06:00Z",
        approval_binding_id=None,
        commit=False,
        services={"scan_text": _pass_scan},
    )

    assert first.status == "needs_approval"
    assert first.approval_binding_id == second.approval_binding_id
    assert first.plan["decision"] == "approve"
    assert first.plan["manifest_digest"].startswith("sha256:")
    assert "comment" not in first.to_dict()["plan"]
    assert first.to_dict()["guarantees"]["calls_agent"] is False


def test_exact_binding_commits_approved_review(tmp_path: Path) -> None:
    root = _project(tmp_path)
    preview = review_external_agent_evidence(
        root, attempt_id="attempt-stage88-review-001", decision="approve", comment="通过。",
        evaluated_at="2026-07-27T12:05:00Z", approval_binding_id=None, commit=False,
        services={"scan_text": _pass_scan},
    )
    result = review_external_agent_evidence(
        root, attempt_id="attempt-stage88-review-001", decision="approve", comment="通过。",
        evaluated_at="2026-07-27T12:05:00Z", approval_binding_id=preview.approval_binding_id, commit=True,
        services={"scan_text": _pass_scan},
    )

    assert result.status == "pass"
    assert result.review["status"] == "approved"
    assert inspect_evidence(root, "attempt-stage88-review-001")["review"]["status"] == "approved"


def test_request_changes_is_persisted_without_overwriting_artifact(tmp_path: Path) -> None:
    root = _project(tmp_path)
    evidence_before = inspect_evidence(root, "attempt-stage88-review-001")
    preview = review_external_agent_evidence(
        root, attempt_id="attempt-stage88-review-001", decision="request_changes", comment="请补充验证依据。",
        evaluated_at="2026-07-27T12:05:00Z", approval_binding_id=None, commit=False,
        services={"scan_text": _pass_scan},
    )
    result = review_external_agent_evidence(
        root, attempt_id="attempt-stage88-review-001", decision="request_changes", comment="请补充验证依据。",
        evaluated_at="2026-07-27T12:05:00Z", approval_binding_id=preview.approval_binding_id, commit=True,
        services={"scan_text": _pass_scan},
    )

    evidence_after = inspect_evidence(root, "attempt-stage88-review-001")
    assert result.review["status"] == "changes_requested"
    assert evidence_after["artifact"] == evidence_before["artifact"]


def test_wrong_binding_and_secret_comment_fail_before_write(tmp_path: Path) -> None:
    root = _project(tmp_path)
    wrong = review_external_agent_evidence(
        root, attempt_id="attempt-stage88-review-001", decision="approve", comment="通过。",
        evaluated_at="2026-07-27T12:05:00Z", approval_binding_id="sha256:" + "0" * 64, commit=True,
        services={"scan_text": _pass_scan},
    )
    blocked = review_external_agent_evidence(
        root, attempt_id="attempt-stage88-review-001", decision="approve", comment="包含敏感信息",
        evaluated_at="2026-07-27T12:05:00Z", approval_binding_id=None, commit=False,
        services={"scan_text": lambda *_args, **_kwargs: CheckResult(status="blocked")},
    )

    assert wrong.status == "blocked"
    assert [finding.rule_id for finding in wrong.findings] == ["external-agent-review-approval-binding-mismatch"]
    assert blocked.status == "blocked"
    assert [finding.rule_id for finding in blocked.findings] == ["external-agent-review-comment-secret-scan"]
    assert inspect_evidence(root, "attempt-stage88-review-001")["review"]["status"] == "pending"


def test_plan_drift_invalidates_review_preview(tmp_path: Path) -> None:
    root = _project(tmp_path)
    preview = review_external_agent_evidence(
        root, attempt_id="attempt-stage88-review-001", decision="approve", comment="通过。",
        evaluated_at="2026-07-27T12:05:00Z", approval_binding_id=None, commit=False,
        services={"scan_text": _pass_scan},
    )
    plan_path = root / "adapters/stage88-review-plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    plan["revision"] = 2
    plan_path.write_text(json.dumps(plan), encoding="utf-8")

    result = review_external_agent_evidence(
        root, attempt_id="attempt-stage88-review-001", decision="approve", comment="通过。",
        evaluated_at="2026-07-27T12:05:00Z", approval_binding_id=preview.approval_binding_id, commit=True,
        services={"scan_text": _pass_scan},
    )

    assert result.status == "blocked"
    assert [finding.rule_id for finding in result.findings] == ["external-agent-review-plan-drift"]
