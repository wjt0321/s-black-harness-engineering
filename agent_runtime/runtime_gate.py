"""Read-only runtime gate check.

This module aggregates task ledger state, task event history, and the adapter
execution envelope gate into a single ``can_proceed`` decision for a given
task + request pair. It does not execute adapters, write ledgers, access
networks, or read credential files.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .adapter_gate import GateCheckResult, check_adapter_gate
from .result import Finding
from .tasks import find_task, find_task_events


TERMINAL_STATUSES = {"finished", "failed"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")


def _draft_event_id(task_id: str, request_id: str | None) -> str:
    """Generate a schema-compatible event id for a draft event.

    The draft id is deterministic for the same task/request pair so that tests
    and repeated checks see a stable value.
    """
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    seed = f"{task_id}:{request_id or 'none'}"
    # Use a simple deterministic numeric suffix derived from the seed.
    suffix = str(sum(ord(c) for c in seed) % 10**6).zfill(6)
    return f"evt-{today}-{suffix}"


@dataclass
class RuntimeGateResult:
    """Result of gating a task + adapter request pair."""

    status: str
    task_id: str
    task_status: str | None = None
    request_id: str | None = None
    gate: dict[str, Any] = field(default_factory=dict)
    suggested_event_draft: dict[str, Any] | None = None
    findings: list[Finding] = field(default_factory=list)
    next_action: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "status": self.status,
            "task_id": self.task_id,
        }
        if self.task_status is not None:
            d["task_status"] = self.task_status
        if self.request_id is not None:
            d["request_id"] = self.request_id
        if self.gate:
            d["gate"] = self.gate
        if self.suggested_event_draft is not None:
            d["suggested_event_draft"] = self.suggested_event_draft
        if self.findings:
            d["findings"] = [f.to_dict() for f in self.findings]
        if self.next_action is not None:
            d["next_action"] = self.next_action
        return d


def _error_result(
    task_id: str,
    request_id: str | None,
    message: str,
    next_action: str,
    rule_id: str,
    status: str = "error",
) -> RuntimeGateResult:
    """Build a RuntimeGateResult for a missing/invalid input scenario."""
    return RuntimeGateResult(
        status=status,
        task_id=task_id,
        request_id=request_id,
        findings=[
            Finding(
                rule_id=rule_id,
                severity="error" if status == "error" else "warn",
                action=status,
                message=message,
            )
        ],
        next_action=next_action,
    )




def _sanitize_gate(gate: dict[str, Any]) -> dict[str, Any]:
    """Return a value-safe gate summary for runtime output.

    Runtime gate output should not replay full adapter artifacts, targets, input
    payloads, evidence descriptions, raw refs, or approval decision refs.
    """
    safe: dict[str, Any] = {}
    for key in (
        "request_id",
        "stage",
        "approval_status",
        "response_status",
        "can_proceed",
        "next_action",
    ):
        if key in gate:
            safe[key] = gate[key]

    approval = gate.get("approval")
    if isinstance(approval, dict):
        safe["approval"] = {
            key: approval[key]
            for key in (
                "request_id",
                "adapter_id",
                "operation",
                "requires_approval",
                "approval_status",
            )
            if key in approval
        }

    response = gate.get("response")
    if isinstance(response, dict):
        safe["response"] = {
            key: response[key]
            for key in (
                "request_id",
                "adapter_id",
                "operation",
                "response_status",
                "artifact_count",
                "evidence_count",
                "raw_ref_present",
            )
            if key in response
        }

    return safe

def _extract_adapter_info(gate: dict[str, Any]) -> tuple[str | None, str | None]:
    """Pull adapter_id and operation from the embedded approval/response summary."""
    for key in ("response", "approval"):
        sub = gate.get(key)
        if isinstance(sub, dict):
            return sub.get("adapter_id"), sub.get("operation")
    return None, None


def _build_event_draft(
    task_id: str,
    task_status: str | None,
    request_id: str | None,
    gate: dict[str, Any],
    gate_status: str,
    can_proceed: bool,
) -> dict[str, Any]:
    """Generate a value-safe task event draft from the runtime gate result.

    The draft conforms to ``tasks/event.schema.json`` but is never written to
    disk. It intentionally omits full input payloads, evidence descriptions, and
    raw references.
    """
    timestamp = _utc_now()
    actor = "runtime-gate"
    event_id = _draft_event_id(task_id, request_id)

    metadata: dict[str, Any] = {
        "request_id": request_id,
    }

    adapter_id, operation = _extract_adapter_info(gate)
    if adapter_id is not None:
        metadata["adapter_id"] = adapter_id
    if operation is not None:
        metadata["operation"] = operation

    if task_status in TERMINAL_STATUSES:
        return {
            "event_id": event_id,
            "task_id": task_id,
            "timestamp": timestamp,
            "actor": actor,
            "event_type": "blocked",
            "from_status": task_status,
            "to_status": task_status,
            "message": f"Task is already in a terminal state ({task_status}); do not proceed.",
            "metadata": metadata,
            "artifacts": [],
        }

    if can_proceed:
        return {
            "event_id": event_id,
            "task_id": task_id,
            "timestamp": timestamp,
            "actor": actor,
            "event_type": "status_changed",
            "from_status": task_status,
            "to_status": "running",
            "message": "Adapter gate passed; task may continue.",
            "metadata": metadata,
            "artifacts": [],
        }

    approval_status = gate.get("approval_status")
    response_status = gate.get("response_status")
    stage = gate.get("stage", "unknown")
    metadata["stage"] = stage
    metadata["approval_status"] = approval_status
    if response_status is not None:
        metadata["response_status"] = response_status

    if approval_status == "needs_approval":
        blocked_reason = "need_user_approval"
        message = "Adapter request is pending approval; task blocked."
    elif approval_status == "blocked":
        blocked_reason = "policy_blocked"
        message = "Adapter approval was denied or expired; task blocked."
    elif approval_status == "needs_input":
        blocked_reason = "need_user_input"
        message = "Adapter request is missing or needs input; task blocked."
    elif response_status in {"blocked", "failed", "skipped"}:
        blocked_reason = "tool_failed"
        message = f"Adapter response was {response_status}; task blocked."
    elif response_status in {"needs_approval", "needs_input"}:
        blocked_reason = "need_user_input"
        message = "Adapter response is missing or needs input; task blocked."
    else:
        blocked_reason = "policy_blocked"
        message = "Adapter gate blocked; task cannot proceed."

    metadata["blocked_reason"] = blocked_reason

    return {
        "event_id": event_id,
        "task_id": task_id,
        "timestamp": timestamp,
        "actor": actor,
        "event_type": "blocked",
        "from_status": task_status,
        "to_status": "blocked",
        "message": message,
        "metadata": metadata,
        "artifacts": [],
    }


def check_runtime_gate(
    root: Path,
    task_id: str,
    request_id: str,
    envelope_file: str,
    tasks_file: str | None = None,
    events_file: str | None = None,
) -> RuntimeGateResult:
    """Check whether a task + adapter request pair may proceed.

    The function is read-only: it opens the task ledger, event ledger, and
    adapter execution envelope, runs the existing adapter gate check, and
    returns a compact summary plus a suggested task event draft. It never
    executes adapters, writes ledgers, accesses networks, or reads credential
    files.
    """
    # Load task snapshot (explicit file support lets callers override defaults).
    task = find_task(root, task_id, explicit_file=tasks_file)
    if task is None:
        return _error_result(
            task_id=task_id,
            request_id=request_id,
            message=f"Task {task_id} not found in task ledger.",
            next_action="Provide a task_id that exists in the task ledger.",
            rule_id="task-not-found",
            status="error",
        )

    task_status = task.get("status")

    # Load task events only for context; the gate decision itself comes from the
    # adapter gate check and the task snapshot status.
    _ = find_task_events(root, task_id, explicit_file=events_file)

    # Run the existing adapter gate check (approval + response).
    gate_result: GateCheckResult = check_adapter_gate(root, envelope_file, request_id)

    raw_gate: dict[str, Any] = dict(gate_result.gate) if gate_result.gate else {}
    raw_gate.setdefault("request_id", request_id)
    gate = _sanitize_gate(raw_gate)

    # Propagate validation/level failures from the adapter gate unchanged.
    if gate_result.status in {"validation_failed", "error"}:
        return RuntimeGateResult(
            status=gate_result.status,
            task_id=task_id,
            task_status=task_status,
            request_id=request_id,
            gate=gate,
            suggested_event_draft=None,
            findings=gate_result.findings,
            next_action=gate_result.next_action,
        )

    # Determine whether the task + request pair may proceed.
    can_proceed = task_status not in TERMINAL_STATUSES and gate.get("can_proceed") is True

    suggested_event_draft = _build_event_draft(
        task_id=task_id,
        task_status=task_status,
        request_id=request_id,
        gate=gate,
        gate_status=gate_result.status,
        can_proceed=can_proceed,
    )

    if task_status in TERMINAL_STATUSES:
        status = "blocked"
        next_action = f"Task is already in a terminal state ({task_status}); do not proceed."
    elif can_proceed:
        status = "pass"
        next_action = "Adapter gate passed; task may continue."
    else:
        status = gate_result.status
        next_action = gate_result.next_action

    return RuntimeGateResult(
        status=status,
        task_id=task_id,
        task_status=task_status,
        request_id=request_id,
        gate=gate,
        suggested_event_draft=suggested_event_draft,
        findings=gate_result.findings,
        next_action=next_action,
    )
