"""Read-only adapter gate check.

This module aggregates ``check_adapter_approval`` and ``check_adapter_response``
to give a single ``can_proceed`` decision for an adapter request. It does not
execute adapters, write ledgers, access networks, or read credential files.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .adapter_approval import ApprovalCheckResult, check_adapter_approval
from .adapter_response import ResponseCheckResult, check_adapter_response
from .result import Finding


@dataclass
class GateCheckResult:
    """Result of gating an adapter request through approval + response checks."""

    status: str
    gate: dict[str, Any] = field(default_factory=dict)
    findings: list[Finding] = field(default_factory=list)
    next_action: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"status": self.status}
        if self.gate:
            d["gate"] = self.gate
        if self.findings:
            d["findings"] = [f.to_dict() for f in self.findings]
        if self.next_action is not None:
            d["next_action"] = self.next_action
        return d


def _gate_summary(request_id: str, approval_status: str, response_status: str | None, stage: str, can_proceed: bool, next_action: str | None) -> dict[str, Any]:
    """Build the compact gate summary shown to the user."""
    return {
        "request_id": request_id,
        "stage": stage,
        "approval_status": approval_status,
        "response_status": response_status,
        "can_proceed": can_proceed,
        "next_action": next_action,
    }


def check_adapter_gate(
    root: Path,
    file: str,
    request_id: str,
) -> GateCheckResult:
    """Run approval check then response check and return a single gate decision.

    The gate is read-only: it reuses the existing approval and response check
    functions, both of which only open and validate the envelope file. It never
    executes adapters, writes ledgers, accesses networks, or reads credential
    files.

    Aggregation rules:

    * The approval check runs first.
    * If it does not return ``pass``, the gate stops at the approval stage and
      returns the approval status unchanged.
    * If the approval check returns ``pass``, the response check runs and its
      status becomes the final gate status.
    * ``can_proceed`` is ``True`` only when the final status is ``pass``.
    """
    approval: ApprovalCheckResult = check_adapter_approval(root, file, request_id)

    stage = "approval"
    gate: dict[str, Any] = _gate_summary(
        request_id=request_id,
        approval_status=approval.status,
        response_status=None,
        stage=stage,
        can_proceed=False,
        next_action=approval.next_action,
    )

    if approval.approval:
        gate["approval"] = approval.approval

    if approval.status != "pass":
        return GateCheckResult(
            status=approval.status,
            gate=gate,
            findings=approval.findings,
            next_action=approval.next_action,
        )

    response: ResponseCheckResult = check_adapter_response(root, file, request_id)

    stage = "response"
    gate["stage"] = stage
    gate["response_status"] = response.status
    gate["approval_status"] = approval.status
    gate["can_proceed"] = response.status == "pass"
    gate["next_action"] = response.next_action

    if response.response:
        gate["response"] = response.response

    return GateCheckResult(
        status=response.status,
        gate=gate,
        findings=response.findings,
        next_action=response.next_action,
    )
