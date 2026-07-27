"""Read and recover immutable external-agent execution evidence."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .external_agent_evidence_store import (
    EvidenceStoreError,
    finalize_evidence,
    inspect_evidence,
    read_artifact_content,
)
from .result import CheckResult, Finding

SCHEMA_VERSION = "control-plane/external-agent-evidence/v1"
_EVENT_LABELS = {
    "request_claimed": "请求已领取",
    "host_turn_dispatched": "轮次已派发",
    "host_turn_started": "智能体已开始",
    "host_turn_completed": "智能体已结束",
    "host_turn_blocked": "轮次被安全策略阻止",
    "host_turn_timed_out": "轮次已超时",
    "host_session_closed": "宿主会话已关闭",
}


def _canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _digest(value: object) -> str:
    data = value if isinstance(value, bytes) else _canonical(value)
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _finding(rule_id: str, message: str) -> Finding:
    return Finding(rule_id=rule_id, severity="block", action="deny", message=message)


def _projection(evidence: dict[str, Any], *, content: str | None = None) -> dict[str, Any]:
    artifact = {
        "artifact_id": evidence["artifact"]["artifact_id"],
        "artifact_type": evidence["artifact"]["artifact_type"],
        "media_type": evidence["artifact"]["media_type"],
        "content_hash": evidence["artifact"]["content_hash"],
        "byte_count": evidence["artifact"]["byte_count"],
    }
    if content is not None:
        artifact["content"] = content
    review = evidence["review"]
    projected: dict[str, Any] = {
        "attempt_id": evidence["attempt_id"],
        "task_id": evidence["task_id"],
        "request_id": evidence["request_id"],
        "work_item_id": evidence["work_item_id"],
        "target_profile": evidence["target_profile"],
        "completed_at": evidence["completed_at"],
        "archive_status": "archived" if evidence["status"] == "pass" else "recovery_pending",
        "manifest_digest": evidence["manifest_digest"],
        "events": [
            {
                "sequence": event["sequence"],
                "event_type": event["event_type"],
                "label_zh": _EVENT_LABELS[event["event_type"]],
                "occurred_at": event["occurred_at"],
                **({"failure_code": event["failure_code"]} if event.get("failure_code") else {}),
            }
            for event in evidence["host_events"]
        ],
        "artifact": artifact,
        "review_required": review["required"],
        "review_gate_id": review["gate_id"],
        "review_status": review["status"],
    }
    record = review.get("record")
    if record is not None:
        projected["review"] = {
            "review_id": record["review_id"],
            "decision": record["decision"],
            "comment_digest": record["comment_digest"],
            "committed_at": record["committed_at"],
        }
    return projected


@dataclass(frozen=True)
class ExternalAgentEvidenceResult:
    status: str
    attempt_id: str
    evidence: dict[str, Any] | None = None
    plan_hash: str | None = None
    approval_binding_id: str | None = None
    findings: tuple[Finding, ...] = ()
    next_action: str | None = None

    def exit_code(self) -> int:
        return CheckResult(self.status).exit_code()

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "status": self.status,
            "schema_version": SCHEMA_VERSION,
            "attempt_id": self.attempt_id,
            "guarantees": {
                "calls_agent": False,
                "opens_network_listener": False,
                "accepts_arbitrary_file_path": False,
                "overwrites_evidence": False,
            },
        }
        if self.evidence is not None:
            payload["evidence"] = self.evidence
        if self.plan_hash:
            payload["plan_hash"] = self.plan_hash
        if self.approval_binding_id:
            payload["approval_binding_id"] = self.approval_binding_id
        if self.findings:
            payload["findings"] = [finding.to_dict() for finding in self.findings]
        if self.next_action:
            payload["next_action"] = self.next_action
        return payload


def inspect_external_agent_evidence(
    root: Path,
    attempt_id: str,
    *,
    include_content: bool = False,
) -> ExternalAgentEvidenceResult:
    try:
        evidence = inspect_evidence(root.resolve(), attempt_id)
        content = read_artifact_content(root.resolve(), attempt_id) if include_content and evidence["status"] == "pass" else None
    except EvidenceStoreError as exc:
        return ExternalAgentEvidenceResult(
            "blocked", attempt_id,
            findings=(_finding(exc.code, "无法读取指定的真实执行证据。"),),
        )
    projected = _projection(evidence, content=content)
    next_action = None
    if projected["archive_status"] == "recovery_pending":
        next_action = "使用固定恢复入口完成证据归档；不要重新执行 Agent。"
    elif projected["review_status"] == "pending":
        next_action = "查看结果产物后提交人工审阅。"
    elif projected["review_status"] == "changes_requested":
        next_action = "保留旧产物并创建新的执行尝试。"
    return ExternalAgentEvidenceResult("pass", attempt_id, evidence=projected, next_action=next_action)


def recover_external_agent_evidence(
    root: Path,
    attempt_id: str,
    *,
    approval_binding_id: str | None,
    commit: bool,
) -> ExternalAgentEvidenceResult:
    try:
        evidence = inspect_evidence(root.resolve(), attempt_id)
    except EvidenceStoreError as exc:
        return ExternalAgentEvidenceResult(
            "blocked", attempt_id,
            findings=(_finding(exc.code, "无法读取待恢复执行证据。"),),
        )
    if evidence["status"] != "recovery_pending":
        return ExternalAgentEvidenceResult(
            "blocked", attempt_id,
            evidence=_projection(evidence),
            findings=(_finding("external-agent-evidence-recovery-not-pending", "该执行尝试当前没有待恢复证据。"),),
        )
    stable = {
        "operation": "external-agent.evidence-recover",
        "attempt_id": attempt_id,
        "manifest_digest": evidence["manifest_digest"],
        "artifact_digest": evidence["artifact"]["content_hash"],
    }
    plan_hash = _digest(stable)
    expected_approval = _digest({"kind": "one-time-evidence-recovery-approval", "plan_hash": plan_hash})
    projected = _projection(evidence)
    if not commit:
        return ExternalAgentEvidenceResult(
            "needs_approval", attempt_id, evidence=projected,
            plan_hash=plan_hash, approval_binding_id=expected_approval,
            next_action="核对执行尝试和证据摘要后，携带确认摘要并显式使用 --commit。",
        )
    if approval_binding_id != expected_approval:
        return ExternalAgentEvidenceResult(
            "blocked", attempt_id, evidence=projected,
            plan_hash=plan_hash, approval_binding_id=expected_approval,
            findings=(_finding("external-agent-evidence-recovery-binding-mismatch", "提交的确认摘要与当前待恢复证据不一致。"),),
        )
    try:
        finalized = finalize_evidence(root.resolve(), attempt_id)
    except EvidenceStoreError as exc:
        return ExternalAgentEvidenceResult(
            "blocked", attempt_id, evidence=projected,
            plan_hash=plan_hash, approval_binding_id=expected_approval,
            findings=(_finding(exc.code, "待恢复证据未能完成安全归档。"),),
        )
    return ExternalAgentEvidenceResult(
        "pass", attempt_id, evidence=_projection(finalized),
        plan_hash=plan_hash, approval_binding_id=expected_approval,
        next_action="证据已归档；可在中文控制面查看真实事件、产物和审阅状态。",
    )
