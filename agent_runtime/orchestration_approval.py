"""Read-only orchestration approval views for the agent-runtime CLI.

This module provides envelope-scoped read models for approval records. It does
not introduce an independent Approval storage layer and does not implement
approval resolution (writing). It extracts ``approval_record`` artifacts from a
single adapter execution envelope and returns compact, value-safe summaries.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .adapter_validation import validate_envelope_file
from .result import Finding


@dataclass
class ApprovalListResult:
    """Result of an orchestration approval list (envelope-scoped read model)."""

    status: str
    approvals: list[dict[str, Any]] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    next_action: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "status": self.status,
            "approvals": self.approvals,
        }
        if self.findings:
            d["findings"] = [f.to_dict() for f in self.findings]
        if self.next_action is not None:
            d["next_action"] = self.next_action
        return d


@dataclass
class ApprovalDetailResult:
    """Result of an orchestration approval get (envelope-scoped read model)."""

    status: str
    approval: dict[str, Any] | None = None
    related_request: dict[str, Any] | None = None
    findings: list[Finding] = field(default_factory=list)
    next_action: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"status": self.status}
        if self.approval is not None:
            d["approval"] = self.approval
        if self.related_request is not None:
            d["related_request"] = self.related_request
        if self.findings:
            d["findings"] = [f.to_dict() for f in self.findings]
        if self.next_action is not None:
            d["next_action"] = self.next_action
        return d


def _load_envelope(root: Path, envelope_file: str) -> tuple[dict[str, Any], list[Finding], str | None]:
    """Validate and load an envelope, returning (envelope, findings, next_action).

    On validation failure returns (None, findings, next_action).
    """
    validation = validate_envelope_file(root, envelope_file)
    if validation.status != "pass":
        return None, validation.findings, validation.next_action

    path = (root / envelope_file).resolve()
    envelope = json.loads(path.read_text(encoding="utf-8"))
    return envelope, [], None


def _build_approval_summary(approval: dict[str, Any]) -> dict[str, Any]:
    """Return a compact, value-safe summary of an approval_record."""
    scope = approval.get("scope", {})
    return {
        "approval_id": approval.get("approval_id", ""),
        "request_id": approval.get("request_id", ""),
        "task_id": scope.get("task_id", ""),
        "adapter_id": scope.get("adapter_id", ""),
        "operation": scope.get("operation", ""),
        "target": scope.get("target", ""),
        "status": approval.get("status", ""),
        "requested_at": approval.get("requested_at", ""),
        "resolved_at": approval.get("decided_at") or "",
        "resolver": approval.get("decided_by") or "",
    }


def _build_related_request_summary(request: dict[str, Any]) -> dict[str, Any]:
    """Return a value-safe summary of a related adapter_request.

    Does not include input, payload_refs, or any raw payload data.
    """
    context = request.get("context", {})
    return {
        "request_id": request.get("request_id", ""),
        "task_id": request.get("task_id", ""),
        "adapter_id": request.get("adapter_id", ""),
        "operation": request.get("operation", ""),
        "target": request.get("target", ""),
        "risk_level": context.get("risk_level", ""),
        "dry_run": bool(context.get("dry_run", False)),
        "requires_approval": bool(context.get("requires_approval", False)),
        "capability": context.get("capability", ""),
    }


def list_approvals(
    root: Path,
    envelope_file: str,
    status_filter: str | None = None,
) -> ApprovalListResult:
    """List approval records from a single adapter execution envelope.

    This is an envelope-scoped read model: it extracts ``approval_record``
    artifacts and returns one summary row per approval. It does not introduce a
    persistent Approval collection, resolve approvals, or write any files.
    """
    envelope, findings, next_action = _load_envelope(root, envelope_file)
    if envelope is None:
        return ApprovalListResult(
            status="error" if findings and findings[0].rule_id == "file-not-found" else "validation_failed",
            findings=findings,
            next_action=next_action,
        )

    approvals: list[dict[str, Any]] = []
    for artifact in envelope.get("artifacts", []):
        if artifact.get("artifact_type") != "approval_record":
            continue
        status = artifact.get("status", "")
        if status_filter is not None and status != status_filter:
            continue
        approvals.append(_build_approval_summary(artifact))

    return ApprovalListResult(
        status="pass",
        approvals=approvals,
        next_action="Use orchestration approval get for per-approval details.",
    )


def get_approval(
    root: Path,
    approval_id: str,
    envelope_file: str,
) -> ApprovalDetailResult:
    """Get a single approval record from a single adapter execution envelope.

    Returns the full value-safe approval detail plus a safe summary of the
    related adapter_request. No input or raw payload is included.
    """
    envelope, findings, next_action = _load_envelope(root, envelope_file)
    if envelope is None:
        return ApprovalDetailResult(
            status="error" if findings and findings[0].rule_id == "file-not-found" else "validation_failed",
            findings=findings,
            next_action=next_action,
        )

    approval: dict[str, Any] | None = None
    related_request: dict[str, Any] | None = None
    requests: dict[str, dict[str, Any]] = {}

    for artifact in envelope.get("artifacts", []):
        artifact_type = artifact.get("artifact_type")
        if artifact_type == "adapter_request":
            requests[artifact.get("request_id", "")] = artifact
        elif artifact_type == "approval_record" and artifact.get("approval_id") == approval_id:
            approval = artifact

    if approval is None:
        return ApprovalDetailResult(
            status="needs_input",
            next_action=f"Approval not found: {approval_id}",
        )

    request_id = approval.get("request_id", "")
    if request_id in requests:
        related_request = _build_related_request_summary(requests[request_id])

    scope = approval.get("scope", {})
    approval_detail = {
        "approval_id": approval.get("approval_id", ""),
        "request_id": request_id,
        "status": approval.get("status", ""),
        "scope": {
            "task_id": scope.get("task_id", ""),
            "adapter_id": scope.get("adapter_id", ""),
            "operation": scope.get("operation", ""),
            "target": scope.get("target", ""),
        },
        "requested_at": approval.get("requested_at", ""),
        "resolved_at": approval.get("decided_at") or "",
        "resolver": approval.get("decided_by") or "",
    }

    return ApprovalDetailResult(
        status="pass",
        approval=approval_detail,
        related_request=related_request,
        next_action="Use orchestration approval resolve to write a decision (not yet implemented).",
    )
