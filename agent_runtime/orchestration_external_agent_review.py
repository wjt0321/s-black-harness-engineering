"""Controlled human review for immutable external-agent execution evidence."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from .external_agent_evidence_store import EvidenceStoreError, inspect_evidence, write_review_record
from .orchestration_collaboration import inspect_collaboration_plan
from .policy import check_text
from .result import CheckResult, Finding

SCHEMA_VERSION = "control-plane/external-agent-human-review/v1"
_DECISIONS = {"approve", "request_changes"}
_MAX_COMMENT_CHARS = 2000
_MAX_COMMENT_BYTES = 4096


def _canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _digest(value: object) -> str:
    data = value if isinstance(value, bytes) else _canonical(value)
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _review_id(attempt_id: str, gate_id: str) -> str:
    return "review-" + hashlib.sha256(f"{attempt_id}\0{gate_id}".encode("utf-8")).hexdigest()


def _finding(rule_id: str, message: str, *, validation: bool = False) -> Finding:
    return Finding(
        rule_id=rule_id,
        severity="error" if validation else "block",
        action="error" if validation else "deny",
        message=message,
    )


def _valid_time(value: str) -> bool:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return False
    return parsed.tzinfo is not None


@dataclass(frozen=True)
class ExternalAgentReviewResult:
    status: str
    attempt_id: str
    decision: str
    plan_hash: str | None = None
    approval_binding_id: str | None = None
    plan: dict[str, Any] | None = None
    review: dict[str, Any] | None = None
    findings: tuple[Finding, ...] = ()
    next_action: str | None = None

    def exit_code(self) -> int:
        return CheckResult(self.status).exit_code()

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "status": self.status,
            "schema_version": SCHEMA_VERSION,
            "attempt_id": self.attempt_id,
            "decision": self.decision,
            "guarantees": {
                "calls_agent": False,
                "opens_network_listener": False,
                "accepts_arbitrary_file_path": False,
                "requires_exact_one_time_approval": True,
                "overwrites_evidence": False,
            },
        }
        if self.plan_hash:
            payload["plan_hash"] = self.plan_hash
        if self.approval_binding_id:
            payload["approval_binding_id"] = self.approval_binding_id
        if self.plan is not None:
            payload["plan"] = self.plan
        if self.review is not None:
            payload["review"] = self.review
        if self.findings:
            payload["findings"] = [item.to_dict() for item in self.findings]
        if self.next_action:
            payload["next_action"] = self.next_action
        return payload


def review_external_agent_evidence(
    root: Path,
    *,
    attempt_id: str,
    decision: str,
    comment: str,
    evaluated_at: str,
    approval_binding_id: str | None,
    commit: bool,
    services: dict[str, Any] | None = None,
) -> ExternalAgentReviewResult:
    root = root.resolve()
    if not attempt_id or len(attempt_id) > 128:
        return ExternalAgentReviewResult(
            "validation_failed", attempt_id, decision,
            findings=(_finding("external-agent-review-attempt-invalid", "执行尝试编号无效。", validation=True),),
        )
    if decision not in _DECISIONS:
        return ExternalAgentReviewResult(
            "validation_failed", attempt_id, decision,
            findings=(_finding("external-agent-review-decision-invalid", "人工审阅决定只能是通过或要求修改。", validation=True),),
        )
    if (
        not isinstance(comment, str)
        or not comment.strip()
        or "\x00" in comment
        or len(comment) > _MAX_COMMENT_CHARS
        or len(comment.encode("utf-8")) > _MAX_COMMENT_BYTES
    ):
        return ExternalAgentReviewResult(
            "validation_failed", attempt_id, decision,
            findings=(_finding("external-agent-review-comment-invalid", "审阅意见为空、包含空字符或超过固定上限。", validation=True),),
        )
    if not _valid_time(evaluated_at):
        return ExternalAgentReviewResult(
            "validation_failed", attempt_id, decision,
            findings=(_finding("external-agent-review-time-invalid", "审阅时间必须是带时区的 ISO-8601 时间。", validation=True),),
        )
    try:
        evidence = inspect_evidence(root, attempt_id)
    except EvidenceStoreError as exc:
        return ExternalAgentReviewResult(
            "blocked", attempt_id, decision,
            findings=(_finding(exc.code, "无法读取已归档的真实执行证据。"),),
        )
    if evidence["status"] != "pass":
        return ExternalAgentReviewResult(
            "blocked", attempt_id, decision,
            findings=(_finding("external-agent-review-evidence-not-finalized", "执行证据尚未完成归档，不能审阅。"),),
            next_action="先使用固定证据恢复入口完成归档。",
        )
    if evidence["review"]["status"] != "pending":
        return ExternalAgentReviewResult(
            "blocked", attempt_id, decision,
            findings=(_finding("external-agent-review-not-pending", "该执行尝试当前不等待人工审阅。"),),
        )
    collaboration = inspect_collaboration_plan(root, evidence["collaboration_file"])
    if collaboration.status != "pass" or collaboration.plan is None:
        return ExternalAgentReviewResult(
            "blocked", attempt_id, decision,
            findings=(_finding("external-agent-review-plan-drift", "当前协作计划无效或已与执行证据发生漂移。"),),
        )
    current_plan = collaboration.to_dict()["plan"]
    if current_plan.get("plan_id") != evidence["collaboration_plan_id"]:
        return ExternalAgentReviewResult(
            "blocked", attempt_id, decision,
            findings=(_finding("external-agent-review-plan-drift", "当前协作计划摘要与执行证据不一致。"),),
        )
    work = next((item for item in current_plan["work_items"] if item["work_item_id"] == evidence["work_item_id"]), None)
    gate = next((item for item in current_plan["review_gates"] if item["gate_id"] == evidence["review"]["gate_id"]), None)
    if (
        work is None
        or work.get("review_required") is not True
        or gate is None
        or evidence["work_item_id"] not in gate.get("after_work_item_ids", [])
        or decision not in gate.get("decision_options", [])
    ):
        return ExternalAgentReviewResult(
            "blocked", attempt_id, decision,
            findings=(_finding("external-agent-review-gate-drift", "当前审阅门禁与执行证据不一致。"),),
        )
    scan = (services or {}).get("scan_text", check_text)(root, comment)
    if getattr(scan, "status", None) != "pass":
        return ExternalAgentReviewResult(
            "blocked", attempt_id, decision,
            findings=(_finding("external-agent-review-comment-secret-scan", "审阅意见未通过敏感信息扫描；匹配内容不会回显。"),),
        )
    comment_digest = _digest(comment.encode("utf-8"))
    review_id = _review_id(attempt_id, gate["gate_id"])
    stable = {
        "operation": "external-agent.human-review",
        "review_id": review_id,
        "attempt_id": attempt_id,
        "task_id": evidence["task_id"],
        "work_item_id": evidence["work_item_id"],
        "gate_id": gate["gate_id"],
        "decision": decision,
        "comment_digest": comment_digest,
        "artifact_id": evidence["artifact"]["artifact_id"],
        "artifact_digest": evidence["artifact"]["content_hash"],
        "manifest_digest": evidence["manifest_digest"],
        "collaboration_plan_id": evidence["collaboration_plan_id"],
    }
    plan_hash = _digest(stable)
    expected_approval = _digest({"kind": "one-time-human-review-approval", "plan_hash": plan_hash})
    if not commit:
        return ExternalAgentReviewResult(
            "needs_approval",
            attempt_id,
            decision,
            plan_hash=plan_hash,
            approval_binding_id=expected_approval,
            plan=stable,
            next_action="核对执行尝试、产物摘要、审阅门禁和决定后，携带确认摘要并显式使用 --commit。",
        )
    if approval_binding_id != expected_approval:
        return ExternalAgentReviewResult(
            "blocked",
            attempt_id,
            decision,
            plan_hash=plan_hash,
            approval_binding_id=expected_approval,
            plan=stable,
            findings=(_finding("external-agent-review-approval-binding-mismatch", "提交的确认摘要与当前人工审阅计划不一致。"),),
        )
    record = {
        "version": 1,
        "contract": "external-agent-human-review/v1",
        "review_id": review_id,
        "attempt_id": attempt_id,
        "gate_id": gate["gate_id"],
        "decision": decision,
        "comment": comment,
        "comment_digest": comment_digest,
        "artifact_id": evidence["artifact"]["artifact_id"],
        "artifact_digest": evidence["artifact"]["content_hash"],
        "manifest_digest": evidence["manifest_digest"],
        "collaboration_plan_id": evidence["collaboration_plan_id"],
        "approval_binding_id": expected_approval,
        "committed_at": evaluated_at,
    }
    try:
        stored = write_review_record(root, record)
        current = inspect_evidence(root, attempt_id)
    except EvidenceStoreError as exc:
        return ExternalAgentReviewResult(
            "blocked", attempt_id, decision, plan_hash=plan_hash, approval_binding_id=expected_approval, plan=stable,
            findings=(_finding(exc.code, "人工审阅记录未能安全写入。"),),
        )
    review = {
        "review_id": stored["review_id"],
        "status": current["review"]["status"],
        "decision": stored["decision"],
        "comment_digest": stored["comment_digest"],
        "committed_at": stored["committed_at"],
        "artifact_id": stored["artifact_id"],
        "artifact_digest": stored["artifact_digest"],
    }
    next_action = (
        "该执行尝试已通过人工审阅。"
        if review["status"] == "approved"
        else "保留当前产物并创建新的执行尝试完成修改。"
    )
    return ExternalAgentReviewResult(
        "pass", attempt_id, decision, plan_hash=plan_hash, approval_binding_id=expected_approval,
        plan=stable, review=review, next_action=next_action,
    )
