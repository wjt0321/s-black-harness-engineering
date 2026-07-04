"""Read-only runtime action planner.

Given a task_id and an adapter action descriptor, this module confirms the task
exists and is not in a terminal state, then generates a safe adapter_request
draft summary (and optional approval/event draft summaries when required). It
does not execute adapters, write ledgers, access networks, or read credential
files.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .adapter_plan import PlanResult, plan_adapter_action
from .result import Finding
from .tasks import find_task


TERMINAL_STATUSES = {"finished", "failed"}


@dataclass
class RuntimePlanResult:
    """Result of planning an adapter action for a task."""

    status: str
    task_id: str
    task_status: str | None = None
    request_draft: dict[str, Any] | None = None
    approval_draft: dict[str, Any] | None = None
    event_draft: dict[str, Any] | None = None
    findings: list[Finding] = field(default_factory=list)
    next_action: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "status": self.status,
            "task_id": self.task_id,
            "task_status": self.task_status,
            "request_draft": self.request_draft,
            "approval_draft": self.approval_draft,
            "event_draft": self.event_draft,
        }
        if self.findings:
            d["findings"] = [f.to_dict() for f in self.findings]
        if self.next_action is not None:
            d["next_action"] = self.next_action
        return d


def _error_result(
    task_id: str,
    message: str,
    next_action: str,
    rule_id: str,
    status: str = "error",
) -> RuntimePlanResult:
    """Build a RuntimePlanResult for a missing/invalid input scenario."""
    return RuntimePlanResult(
        status=status,
        task_id=task_id,
        findings=[
            Finding(
                rule_id=rule_id,
                severity="error" if status == "error" else "block",
                action=status,
                message=message,
            )
        ],
        next_action=next_action,
    )


def _artifact_by_type(
    envelope: dict[str, Any], artifact_type: str
) -> dict[str, Any] | None:
    for artifact in envelope.get("artifacts", []):
        if artifact.get("artifact_type") == artifact_type:
            return artifact
    return None


def _build_request_draft(request: dict[str, Any]) -> dict[str, Any]:
    """Return a value-safe adapter_request draft summary.

    The summary omits the full ``input`` payload and any credential-bearing
    context.
    """
    context = request.get("context", {})
    return {
        "request_id": request.get("request_id"),
        "adapter_id": request.get("adapter_id"),
        "operation": request.get("operation"),
        "target": request.get("target"),
        "actor": request.get("actor"),
        "policy_profile": context.get("policy_profile"),
        "risk_level": context.get("risk_level"),
        "requires_approval": context.get("requires_approval"),
        "preflight_status": request.get("preflight", {}).get("status"),
    }


def _build_approval_draft(approval: dict[str, Any]) -> dict[str, Any]:
    """Return a value-safe approval_record draft summary.

    ``decision_ref`` and other credential-bearing fields are intentionally
    omitted.
    """
    return {
        "approval_id": approval.get("approval_id"),
        "request_id": approval.get("request_id"),
        "status": approval.get("status"),
    }


def _build_event_draft(event: dict[str, Any]) -> dict[str, Any]:
    """Return a value-safe execution_event draft summary.

    The summary keeps ids, event type, and action names; it omits the full
    message, target, and any refs.
    """
    metadata = event.get("metadata", {})
    draft: dict[str, Any] = {
        "event_id": event.get("event_id"),
        "event_type": event.get("event_type"),
    }
    if metadata.get("approval_id") is not None:
        draft["approval_id"] = metadata["approval_id"]
    if metadata.get("adapter_id") is not None:
        draft["adapter_id"] = metadata["adapter_id"]
    if metadata.get("operation") is not None:
        draft["operation"] = metadata["operation"]
    return draft


def plan_runtime_action(
    root: Path,
    task_id: str,
    adapter_id: str,
    operation: str,
    target: str | None = None,
    actor: str = "cli",
    args: Any | None = None,
    tasks_file: str | None = None,
) -> RuntimePlanResult:
    """Plan an adapter action for a task.

    The function is read-only: it opens the task ledger, runs the existing
    adapter preflight planner, and returns compact draft summaries. It never
    executes the adapter, writes ledger files, accesses networks, or reads
    credential files.
    """
    task = find_task(root, task_id, explicit_file=tasks_file)
    if task is None:
        return _error_result(
            task_id=task_id,
            message=f"Task {task_id} not found in task ledger.",
            next_action="Provide a task_id that exists in the task ledger.",
            rule_id="task-not-found",
            status="error",
        )

    task_status = task.get("status")
    if task_status in TERMINAL_STATUSES:
        return RuntimePlanResult(
            status="blocked",
            task_id=task_id,
            task_status=task_status,
            findings=[
                Finding(
                    rule_id="task-terminal",
                    severity="block",
                    action="deny",
                    message=f"Task is in a terminal state ({task_status}); no new actions can be planned.",
                )
            ],
            next_action=f"Task is already in a terminal state ({task_status}); do not plan new actions.",
        )

    plan_result: PlanResult = plan_adapter_action(
        root,
        adapter_id,
        operation,
        target=target,
        actor=actor,
        task_id=task_id,
        args=args,
    )

    if plan_result.status == "error":
        return RuntimePlanResult(
            status="error",
            task_id=task_id,
            task_status=task_status,
            findings=plan_result.findings,
            next_action=plan_result.next_action,
        )

    envelope = plan_result.envelope
    if envelope is None:
        return _error_result(
            task_id=task_id,
            message="No envelope was generated for the planned action.",
            next_action="Review the adapter id, operation, and target.",
            rule_id="missing-envelope",
        )

    request = _artifact_by_type(envelope, "adapter_request")
    if request is None:
        return _error_result(
            task_id=task_id,
            message="Generated envelope is missing adapter_request.",
            next_action="Review the generated envelope and schema.",
            rule_id="missing-adapter-request",
        )

    result = RuntimePlanResult(
        status=plan_result.status,
        task_id=task_id,
        task_status=task_status,
        request_draft=_build_request_draft(request),
        findings=plan_result.findings,
        next_action=plan_result.next_action,
    )

    if plan_result.status == "needs_approval":
        approval = _artifact_by_type(envelope, "approval_record")
        if approval is not None:
            result.approval_draft = _build_approval_draft(approval)
        event = _artifact_by_type(envelope, "execution_event")
        if event is not None:
            result.event_draft = _build_event_draft(event)

    return result
