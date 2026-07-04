"""Read-only adapter approval status checker.

This module checks whether a specific adapter_request inside an already
validated execution envelope has an approval record that allows it to proceed.
It does not execute adapters, write ledgers, access networks, or read
credential files.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .adapter_validation import _load_envelope, validate_envelope_file
from .result import CheckResult, Finding


@dataclass
class ApprovalCheckResult:
    """Result of checking the approval status for a single adapter request."""

    status: str
    approval: dict[str, Any] = field(default_factory=dict)
    findings: list[Finding] = field(default_factory=list)
    next_action: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"status": self.status}
        if self.approval:
            d["approval"] = self.approval
        if self.findings:
            d["findings"] = [f.to_dict() for f in self.findings]
        if self.next_action is not None:
            d["next_action"] = self.next_action
        return d


def _approval_summary(
    request_id: str,
    request: dict[str, Any],
    approval: dict[str, Any] | None,
) -> dict[str, Any]:
    """Build a compact, input-free approval summary."""
    context = request.get("context", {})
    summary: dict[str, Any] = {
        "request_id": request_id,
        "adapter_id": request.get("adapter_id"),
        "operation": request.get("operation"),
        "target": request.get("target"),
        "requires_approval": bool(context.get("requires_approval")),
    }
    if approval is not None:
        summary["approval_id"] = approval.get("approval_id")
        summary["approval_status"] = approval.get("status")
        summary["decision_ref"] = approval.get("decision_ref")
    else:
        summary["approval_id"] = None
        summary["approval_status"] = None
        summary["decision_ref"] = None
    return summary


def check_adapter_approval(
    root: Path,
    file: str,
    request_id: str,
) -> ApprovalCheckResult:
    """Check whether ``request_id`` may proceed based on its approval record.

    The envelope file is validated (schema + consistency) first. If validation
    fails, the returned result uses the same status/findings/next_action as
    ``validate_envelope_file`` and contains no ``approval`` summary.

    This function is read-only: it opens the file, validates the envelope, and
    inspects the artifacts. It never executes adapters, writes ledgers, accesses
    networks, or reads credential files.
    """
    validation = validate_envelope_file(root, file)
    if validation.status != "pass":
        return ApprovalCheckResult(
            status=validation.status,
            approval={},
            findings=validation.findings,
            next_action=validation.next_action,
        )

    loaded = _load_envelope(root, file)
    if isinstance(loaded, CheckResult):
        # Defensive: validation passed, but re-loading failed (e.g. race).
        return ApprovalCheckResult(
            status=loaded.status,
            approval={},
            findings=loaded.findings,
            next_action=loaded.next_action,
        )

    envelope, _rel_path = loaded
    artifacts = envelope.get("artifacts", [])

    requests: dict[str, dict[str, Any]] = {}
    approvals_by_request: dict[str, list[dict[str, Any]]] = {}

    for artifact in artifacts:
        artifact_type = artifact.get("artifact_type")
        if artifact_type == "adapter_request":
            rid = artifact.get("request_id")
            if rid:
                requests[rid] = artifact
        elif artifact_type == "approval_record":
            rid = artifact.get("request_id")
            if rid:
                approvals_by_request.setdefault(rid, []).append(artifact)

    request = requests.get(request_id)
    if request is None:
        return ApprovalCheckResult(
            status="needs_input",
            approval={"request_id": request_id},
            findings=[
                Finding(
                    rule_id="approval-request-not-found",
                    severity="error",
                    action="needs_input",
                    message=f"Request {request_id} not found in envelope.",
                )
            ],
            next_action="Provide a request_id that exists in the envelope.",
        )

    context = request.get("context", {})
    requires_approval = bool(context.get("requires_approval"))

    if not requires_approval:
        return ApprovalCheckResult(
            status="pass",
            approval=_approval_summary(request_id, request, None),
            next_action="Request does not require approval.",
        )

    approvals = approvals_by_request.get(request_id, [])
    if not approvals:
        return ApprovalCheckResult(
            status="validation_failed",
            approval=_approval_summary(request_id, request, None),
            findings=[
                Finding(
                    rule_id="approval-record-missing",
                    severity="error",
                    action="error",
                    message=f"Request {request_id} requires approval but has no approval_record.",
                )
            ],
            next_action="Fix the envelope to include an approval_record for this request.",
        )

    # Use the first matching approval_record. A valid envelope should not have
    # more than one, and schema/consistency validation has already passed.
    approval = approvals[0]
    status = approval.get("status")
    summary = _approval_summary(request_id, request, approval)

    if status == "granted":
        return ApprovalCheckResult(
            status="pass",
            approval=summary,
            next_action="Approval granted; request may proceed.",
        )

    if status == "pending":
        return ApprovalCheckResult(
            status="needs_approval",
            approval=summary,
            findings=[
                Finding(
                    rule_id="approval-pending",
                    severity="warn",
                    action="needs_approval",
                    message=f"Approval {approval.get('approval_id')} is pending.",
                )
            ],
            next_action="Wait for the approval to be granted before proceeding.",
        )

    if status == "denied":
        return ApprovalCheckResult(
            status="blocked",
            approval=summary,
            findings=[
                Finding(
                    rule_id="approval-denied",
                    severity="block",
                    action="blocked",
                    message=f"Approval {approval.get('approval_id')} was denied.",
                )
            ],
            next_action="Request was blocked by an explicit denial; do not proceed.",
        )

    if status == "expired":
        return ApprovalCheckResult(
            status="blocked",
            approval=summary,
            findings=[
                Finding(
                    rule_id="approval-expired",
                    severity="block",
                    action="blocked",
                    message=f"Approval {approval.get('approval_id')} has expired.",
                )
            ],
            next_action="Approval expired; request a new approval before proceeding.",
        )

    # Unknown approval status should have been caught by schema validation.
    return ApprovalCheckResult(
        status="validation_failed",
        approval=summary,
        findings=[
            Finding(
                rule_id="approval-status-unknown",
                severity="error",
                action="error",
                message=f"Approval {approval.get('approval_id')} has unrecognized status {status}.",
            )
        ],
        next_action="Fix the approval_record status in the envelope.",
    )
