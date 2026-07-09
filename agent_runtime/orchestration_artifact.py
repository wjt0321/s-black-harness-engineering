"""Read-only orchestration artifact views for the agent-runtime CLI.

This module provides envelope-scoped read models for artifacts inside an
adapter execution envelope. It does not introduce an independent Artifact
storage layer and does not implement artifact export/persist/delete (writing).
It extracts all artifact types (``adapter_request``, ``adapter_response``,
``approval_record``, ``execution_event``) from a single envelope and returns
compact, value-safe summaries. No input, raw_ref, payload_refs, evidence
descriptions, or secret matches are echoed.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .adapter_validation import validate_envelope_file
from .result import Finding


@dataclass
class ArtifactListResult:
    """Result of an orchestration artifact list (envelope-scoped read model)."""

    status: str
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    next_action: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "status": self.status,
            "artifacts": self.artifacts,
        }
        if self.findings:
            d["findings"] = [f.to_dict() for f in self.findings]
        if self.next_action is not None:
            d["next_action"] = self.next_action
        return d


@dataclass
class ArtifactDetailResult:
    """Result of an orchestration artifact get (envelope-scoped read model)."""

    status: str
    artifact: dict[str, Any] | None = None
    related_request: dict[str, Any] | None = None
    findings: list[Finding] = field(default_factory=list)
    next_action: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"status": self.status}
        if self.artifact is not None:
            d["artifact"] = self.artifact
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


def _native_artifact_id(artifact: dict[str, Any]) -> str | None:
    """Return a native identifier for an artifact, if present."""
    artifact_type = artifact.get("artifact_type", "unknown")
    if artifact_type == "adapter_request":
        return artifact.get("request_id")
    if artifact_type == "adapter_response":
        return artifact.get("response_id")
    if artifact_type == "approval_record":
        return artifact.get("approval_id")
    if artifact_type == "execution_event":
        return artifact.get("event_id")
    return None


def _artifact_id(artifact: dict[str, Any], index: int) -> str:
    """Return a stable id for an artifact.

    Uses the artifact's native id when available; otherwise generates an
    envelope-local identifier based on its position.
    """
    native = _native_artifact_id(artifact)
    if native:
        return native
    return f"artifact-{index:04d}"


def _artifact_timestamp(artifact: dict[str, Any]) -> str:
    """Return the best available timestamp for an artifact."""
    artifact_type = artifact.get("artifact_type", "unknown")
    if artifact_type == "adapter_request":
        return artifact.get("created_at", "")
    if artifact_type == "adapter_response":
        return artifact.get("finished_at", "")
    if artifact_type == "approval_record":
        return artifact.get("requested_at", "")
    if artifact_type == "execution_event":
        return artifact.get("timestamp", "")
    return ""


def _artifact_task_id(artifact: dict[str, Any]) -> str:
    """Return the best available task_id for an artifact."""
    artifact_type = artifact.get("artifact_type", "unknown")
    if artifact_type == "adapter_request":
        return artifact.get("task_id", "")
    if artifact_type == "adapter_response":
        return ""
    if artifact_type == "approval_record":
        return artifact.get("scope", {}).get("task_id", "")
    if artifact_type == "execution_event":
        return artifact.get("task_id", "")
    return ""


def _artifact_request_id(artifact: dict[str, Any]) -> str:
    """Return the best available request_id for an artifact."""
    artifact_type = artifact.get("artifact_type", "unknown")
    if artifact_type in ("adapter_request", "adapter_response", "approval_record", "execution_event"):
        return artifact.get("request_id", "")
    return ""


def _artifact_producer(artifact: dict[str, Any]) -> str:
    """Return a short producer label for an artifact."""
    artifact_type = artifact.get("artifact_type", "unknown")
    if artifact_type == "adapter_request":
        return artifact.get("adapter_id", artifact_type)
    if artifact_type == "adapter_response":
        return artifact.get("adapter_id", "") or "adapter"
    if artifact_type == "approval_record":
        return "approval"
    if artifact_type == "execution_event":
        return artifact.get("actor", "runtime")
    return artifact_type


def _artifact_summary_text(artifact: dict[str, Any]) -> str:
    """Return a short, value-free summary text for an artifact."""
    artifact_type = artifact.get("artifact_type", "unknown")
    if artifact_type == "adapter_request":
        return f"{artifact.get('operation', '-')} on {artifact.get('target', '-')}"
    if artifact_type == "adapter_response":
        return f"status={artifact.get('status', '-')}"
    if artifact_type == "approval_record":
        return f"status={artifact.get('status', '-')}"
    if artifact_type == "execution_event":
        return f"{artifact.get('event_type', '-')}"
    return artifact_type


def _build_artifact_summary(artifact: dict[str, Any], index: int) -> dict[str, Any]:
    """Return a compact, value-safe summary of any envelope artifact."""
    artifact_id = _artifact_id(artifact, index)
    artifact_type = artifact.get("artifact_type", "unknown")
    return {
        "artifact_id": artifact_id,
        "artifact_type": artifact_type,
        "task_id": _artifact_task_id(artifact),
        "request_id": _artifact_request_id(artifact),
        "producer": _artifact_producer(artifact),
        "timestamp": _artifact_timestamp(artifact),
        "summary": _artifact_summary_text(artifact),
        "safe_to_preview": artifact_type in (
            "adapter_request",
            "adapter_response",
            "approval_record",
            "execution_event",
        ),
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


def _build_artifact_detail(artifact: dict[str, Any], index: int) -> dict[str, Any]:
    """Return a value-safe detail view of any envelope artifact."""
    artifact_type = artifact.get("artifact_type", "unknown")
    detail: dict[str, Any] = {
        "artifact_id": _artifact_id(artifact, index),
        "artifact_type": artifact_type,
        "task_id": _artifact_task_id(artifact),
        "request_id": _artifact_request_id(artifact),
        "producer": _artifact_producer(artifact),
        "timestamp": _artifact_timestamp(artifact),
        "summary": _artifact_summary_text(artifact),
        "safe_to_preview": artifact_type in (
            "adapter_request",
            "adapter_response",
            "approval_record",
            "execution_event",
        ),
    }

    # Value-safe metadata only.
    if artifact_type == "adapter_request":
        context = artifact.get("context", {})
        preflight = artifact.get("preflight", {})
        detail["metadata"] = {
            "actor": artifact.get("actor", ""),
            "risk_level": context.get("risk_level", ""),
            "dry_run": bool(context.get("dry_run", False)),
            "requires_approval": bool(context.get("requires_approval", False)),
            "capability": context.get("capability", ""),
            "preflight_status": preflight.get("status", ""),
            "finding_count": len(preflight.get("findings", [])),
        }
    elif artifact_type == "adapter_response":
        detail["metadata"] = {
            "status": artifact.get("status", ""),
            "message": artifact.get("message", ""),
            "artifact_count": len(artifact.get("artifacts", [])),
            "evidence_count": len(artifact.get("evidence", [])),
            "has_error": artifact.get("error") is not None,
            "has_raw_ref": bool(artifact.get("raw_ref")),
        }
    elif artifact_type == "approval_record":
        scope = artifact.get("scope", {})
        detail["metadata"] = {
            "status": artifact.get("status", ""),
            "scope": {
                "task_id": scope.get("task_id", ""),
                "adapter_id": scope.get("adapter_id", ""),
                "operation": scope.get("operation", ""),
                "target": scope.get("target", ""),
            },
            "requested_at": artifact.get("requested_at", ""),
            "resolved_at": artifact.get("decided_at") or "",
            "resolver": artifact.get("decided_by") or "",
            "has_decision_ref": bool(artifact.get("decision_ref")),
        }
    elif artifact_type == "execution_event":
        detail["metadata"] = {
            "event_type": artifact.get("event_type", ""),
            "actor": artifact.get("actor", ""),
            "message": artifact.get("message", ""),
            "from_status": artifact.get("from_status", ""),
            "to_status": artifact.get("to_status", ""),
        }
    else:
        detail["metadata"] = {}

    return detail


def list_artifacts(
    root: Path,
    envelope_file: str,
    type_filter: str | None = None,
    request_id_filter: str | None = None,
) -> ArtifactListResult:
    """List artifacts from a single adapter execution envelope.

    This is an envelope-scoped read model: it returns one summary row per
    artifact. It does not introduce a persistent Artifact collection, export
    artifacts, or write any files.
    """
    envelope, findings, next_action = _load_envelope(root, envelope_file)
    if envelope is None:
        return ArtifactListResult(
            status="error" if findings and findings[0].rule_id == "file-not-found" else "validation_failed",
            findings=findings,
            next_action=next_action,
        )

    requests: dict[str, dict[str, Any]] = {}
    artifacts: list[dict[str, Any]] = []
    for index, artifact in enumerate(envelope.get("artifacts", []), start=1):
        if artifact.get("artifact_type") == "adapter_request":
            requests[artifact.get("request_id", "")] = artifact

    for index, artifact in enumerate(envelope.get("artifacts", []), start=1):
        artifact_type = artifact.get("artifact_type", "unknown")
        if type_filter is not None and artifact_type != type_filter:
            continue
        request_id = _artifact_request_id(artifact)
        if request_id_filter is not None and request_id != request_id_filter:
            continue
        artifacts.append(_build_artifact_summary(artifact, index))

    return ArtifactListResult(
        status="pass",
        artifacts=artifacts,
        next_action="Use orchestration artifact get for per-artifact details.",
    )


def get_artifact(
    root: Path,
    artifact_id: str,
    envelope_file: str,
) -> ArtifactDetailResult:
    """Get a single artifact from a single adapter execution envelope.

    Looks up the artifact by its native id (request_id, response_id,
    approval_id, event_id) or by its envelope-local ``artifact-NNNN`` id.
    Returns a value-safe detail view plus a safe summary of the related
    adapter_request. No input, raw_ref, payload_refs, or evidence descriptions
    are included.
    """
    envelope, findings, next_action = _load_envelope(root, envelope_file)
    if envelope is None:
        return ArtifactDetailResult(
            status="error" if findings and findings[0].rule_id == "file-not-found" else "validation_failed",
            findings=findings,
            next_action=next_action,
        )

    requests: dict[str, dict[str, Any]] = {}
    matched: tuple[int, dict[str, Any]] | None = None

    for index, artifact in enumerate(envelope.get("artifacts", []), start=1):
        artifact_type = artifact.get("artifact_type")
        if artifact_type == "adapter_request":
            requests[artifact.get("request_id", "")] = artifact

        if _artifact_id(artifact, index) == artifact_id:
            matched = (index, artifact)

    if matched is None:
        return ArtifactDetailResult(
            status="needs_input",
            next_action=f"Artifact not found: {artifact_id}",
        )

    index, artifact = matched
    detail = _build_artifact_detail(artifact, index)

    related_request: dict[str, Any] | None = None
    request_id = _artifact_request_id(artifact)
    if request_id in requests:
        related_request = _build_related_request_summary(requests[request_id])

    return ArtifactDetailResult(
        status="pass",
        artifact=detail,
        related_request=related_request,
        next_action="Use orchestration artifact export to persist artifacts (not yet implemented).",
    )
