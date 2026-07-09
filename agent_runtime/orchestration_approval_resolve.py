"""Controlled-write orchestration approval resolve for the agent-runtime CLI.

This module records an approval decision by appending a safe event to the task
event ledger. It does **not** execute the original adapter request, does not
modify the input envelope, and does not access networks.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .adapter_validation import validate_envelope_file
from .loader import load_json, normalize_path
from .result import Finding
from .runtime_event_append import append_event, _load_existing_event_ids


MAX_REASON_LENGTH = 500


@dataclass
class ApprovalResolveResult:
    """Result of an orchestration approval resolve command."""

    status: str
    approval_id: str
    task_id: str
    request_id: str
    decision: str
    mode: str
    event_preview: dict[str, Any] | None = None
    event_written: dict[str, Any] | None = None
    envelope_summary: dict[str, Any] = field(default_factory=dict)
    write_summary: dict[str, Any] | None = None
    findings: list[Finding] = field(default_factory=list)
    next_action: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "status": self.status,
            "approval_id": self.approval_id,
            "task_id": self.task_id,
            "request_id": self.request_id,
            "decision": self.decision,
            "mode": self.mode,
            "envelope_summary": self.envelope_summary,
        }
        if self.event_preview is not None:
            d["event_preview"] = self.event_preview
        if self.event_written is not None:
            d["event_written"] = self.event_written
        if self.write_summary is not None:
            d["write_summary"] = self.write_summary
        if self.findings:
            d["findings"] = [f.to_dict() for f in self.findings]
        if self.next_action is not None:
            d["next_action"] = self.next_action
        return d


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")


def _generate_event_id(root: Path, events_file: str | None = None) -> str:
    """Generate a unique event id matching tasks/event.schema.json."""
    date = datetime.now(timezone.utc).strftime("%Y%m%d")
    existing = _load_existing_event_ids(root, events_file)
    suffix = 1
    while True:
        candidate = f"evt-{date}-{suffix:03d}"
        if candidate not in existing:
            return candidate
        suffix += 1


def _hash_reason(reason: str) -> str:
    """Return a deterministic, non-reversible hash of the decision reason.

    The full reason is required for the approval decision, but it is never
    echoed in CLI output and is not persisted verbatim in the event ledger.
    """
    return hashlib.sha256(reason.encode("utf-8")).hexdigest()[:16]


def _validate_inputs(
    decision: str | None,
    reason: str | None,
    dry_run: bool,
    commit: bool,
) -> Finding | None:
    """Return a Finding if mode/decision/reason inputs are invalid."""
    if dry_run and commit:
        return Finding(
            rule_id="dry-run-commit-conflict",
            severity="error",
            action="error",
            message="Provide either --dry-run or --commit, not both.",
        )
    if not dry_run and not commit:
        return Finding(
            rule_id="missing-mode",
            severity="error",
            action="error",
            message="Provide either --dry-run or --commit.",
        )
    if decision not in {"granted", "denied", "expired"}:
        return Finding(
            rule_id="invalid-decision",
            severity="error",
            action="error",
            message="--decision must be one of: granted, denied, expired.",
        )
    if reason is None or reason.strip() == "":
        return Finding(
            rule_id="missing-reason",
            severity="error",
            action="error",
            message="--reason is required and must not be blank.",
        )
    if len(reason) > MAX_REASON_LENGTH:
        return Finding(
            rule_id="reason-too-long",
            severity="error",
            action="error",
            message=f"--reason must not exceed {MAX_REASON_LENGTH} characters.",
        )
    return None


def _build_event_candidate(
    approval_id: str,
    task_id: str,
    request_id: str,
    decision: str,
    reason: str,
    envelope_path: str,
    root: Path,
    events_file: str | None,
    actor: str,
) -> dict[str, Any]:
    """Build an approval_resolved event candidate."""
    event_id = _generate_event_id(root, events_file)
    return {
        "event_id": event_id,
        "task_id": task_id,
        "timestamp": _utc_now(),
        "actor": actor,
        "event_type": "approval_resolved",
        "message": f"Approval {approval_id} resolved as {decision}.",
        "metadata": {
            "approval_id": approval_id,
            "request_id": request_id,
            "decision": decision,
            "reason_hash": _hash_reason(reason),
            "reason_length": len(reason.strip()),
            "envelope_path": envelope_path,
        },
    }


def _event_summary(event: dict[str, Any]) -> dict[str, Any]:
    """Return a value-safe summary of an approval event for CLI output."""
    metadata = event.get("metadata", {})
    decision = metadata.get("decision")
    return {
        "event_id": event.get("event_id"),
        "event_type": event.get("event_type"),
        "task_id": event.get("task_id"),
        "request_id": metadata.get("request_id"),
        "decision": decision,
        "timestamp": event.get("timestamp"),
        "metadata": {
            "approval_id": metadata.get("approval_id"),
            "request_id": metadata.get("request_id"),
            "decision": decision,
        },
    }


def _envelope_summary(
    envelope: dict[str, Any], approval_record: dict[str, Any]
) -> dict[str, Any]:
    """Return a value-safe summary of the envelope and approval context."""
    scope = approval_record.get("scope", {})
    return {
        "version": envelope.get("version"),
        "artifact_count": len(envelope.get("artifacts", [])),
        "approval_id": approval_record.get("approval_id"),
        "request_id": approval_record.get("request_id"),
        "adapter_id": scope.get("adapter_id"),
        "operation": scope.get("operation"),
    }


def resolve_approval(
    root: Path,
    approval_id: str,
    task_id: str,
    request_id: str,
    decision: str,
    reason: str,
    envelope_file: str,
    dry_run: bool = False,
    commit: bool = False,
    events_file: str | None = None,
    tasks_file: str | None = None,
    actor: str = "cli",
) -> ApprovalResolveResult:
    """Resolve an approval by recording a decision event.

    The function is a controlled write:

    - ``--dry-run`` produces a preview and does not modify the event ledger.
    - ``--commit`` appends one event line to the event ledger and rolls back
      the append if post-checks fail.

    It does not execute adapters, modify the envelope, access networks, or
    send messages.
    """
    input_finding = _validate_inputs(decision, reason, dry_run, commit)
    if input_finding is not None:
        return ApprovalResolveResult(
            status="error",
            approval_id=approval_id,
            task_id=task_id,
            request_id=request_id,
            decision=decision or "",
            mode=("dry-run" if dry_run else "commit") if (dry_run or commit) else "",
            findings=[input_finding],
            next_action="Fix the command arguments and retry.",
        )

    mode = "dry-run" if dry_run else "commit"
    root = root.resolve()

    # Validate envelope file (schema + consistency) before reading it.
    envelope_validation = validate_envelope_file(root, envelope_file)
    if envelope_validation.status != "pass":
        return ApprovalResolveResult(
            status=envelope_validation.status,
            approval_id=approval_id,
            task_id=task_id,
            request_id=request_id,
            decision=decision,
            mode=mode,
            findings=list(envelope_validation.findings),
            next_action=envelope_validation.next_action,
        )

    envelope_path = normalize_path(Path(envelope_file))
    envelope = load_json(root / envelope_file)

    approval_record = None
    for artifact in envelope.get("artifacts", []):
        if (
            artifact.get("artifact_type") == "approval_record"
            and artifact.get("approval_id") == approval_id
        ):
            approval_record = artifact
            break

    if approval_record is None:
        return ApprovalResolveResult(
            status="needs_input",
            approval_id=approval_id,
            task_id=task_id,
            request_id=request_id,
            decision=decision,
            mode=mode,
            envelope_summary={"envelope_path": envelope_path},
            findings=[
                Finding(
                    rule_id="approval-not-found",
                    severity="error",
                    action="error",
                    message=f"Approval '{approval_id}' not found in envelope.",
                )
            ],
            next_action="Check the approval id and envelope file.",
        )

    scope = approval_record.get("scope", {})
    envelope_task_id = scope.get("task_id")
    envelope_request_id = approval_record.get("request_id")

    if envelope_task_id and envelope_task_id != task_id:
        return ApprovalResolveResult(
            status="blocked",
            approval_id=approval_id,
            task_id=task_id,
            request_id=request_id,
            decision=decision,
            mode=mode,
            envelope_summary=_envelope_summary(envelope, approval_record),
            findings=[
                Finding(
                    rule_id="approval-task-id-mismatch",
                    severity="block",
                    action="deny",
                    message=(
                        f"Provided task_id '{task_id}' does not match "
                        f"approval scope task_id '{envelope_task_id}'."
                    ),
                )
            ],
            next_action="Provide the task_id that matches the approval scope.",
        )

    if envelope_request_id and envelope_request_id != request_id:
        return ApprovalResolveResult(
            status="blocked",
            approval_id=approval_id,
            task_id=task_id,
            request_id=request_id,
            decision=decision,
            mode=mode,
            envelope_summary=_envelope_summary(envelope, approval_record),
            findings=[
                Finding(
                    rule_id="approval-request-id-mismatch",
                    severity="block",
                    action="deny",
                    message=(
                        f"Provided request_id '{request_id}' does not match "
                        f"approval request_id '{envelope_request_id}'."
                    ),
                )
            ],
            next_action="Provide the request_id that matches the approval record.",
        )

    envelope_summary = _envelope_summary(envelope, approval_record)
    candidate = _build_event_candidate(
        approval_id=approval_id,
        task_id=task_id,
        request_id=request_id,
        decision=decision,
        reason=reason,
        envelope_path=envelope_path,
        root=root,
        events_file=events_file,
        actor=actor,
    )
    event_preview = _event_summary(candidate)

    if dry_run:
        # Reuse the same dry-run simulation used by runtime event append.
        append_result = append_event(
            root,
            candidate=candidate,
            commit=False,
            events_file=events_file,
            tasks_file=tasks_file,
            envelope_file=envelope_file,
        )
        return ApprovalResolveResult(
            status=append_result.status,
            approval_id=approval_id,
            task_id=task_id,
            request_id=request_id,
            decision=decision,
            mode=mode,
            event_preview=event_preview,
            envelope_summary=envelope_summary,
            findings=list(append_result.findings),
            next_action=(
                append_result.next_action
                or "Re-run with --commit to persist the approval decision event."
            ),
        )

    # commit path
    append_result = append_event(
        root,
        candidate=candidate,
        commit=True,
        events_file=events_file,
        tasks_file=tasks_file,
        envelope_file=envelope_file,
    )

    # Map append_event result fields to approval resolve write summary.
    write_summary: dict[str, Any] = {
        "events_file": events_file or "tasks/events.jsonl",
        "committed": getattr(append_result, "committed", False),
        "rolled_back": getattr(append_result, "rolled_back", False),
        "post_validate": getattr(append_result, "post_validate", None),
        "post_ledger_check": getattr(append_result, "post_ledger_check", None),
        "post_runtime_audit": getattr(append_result, "post_runtime_audit", None),
    }
    rollback_error = getattr(append_result, "rollback_error", None)
    if rollback_error is not None:
        write_summary["rollback_error"] = rollback_error

    if append_result.status == "pass":
        event_written = event_preview.copy()
        event_written["committed"] = True
        next_action = (
            "Approval decision recorded. Re-run preflight/run with a fresh request; "
            "do not reuse the original preflight."
            if decision == "granted"
            else "Approval decision recorded. The original request remains blocked."
        )
        return ApprovalResolveResult(
            status="pass",
            approval_id=approval_id,
            task_id=task_id,
            request_id=request_id,
            decision=decision,
            mode=mode,
            event_preview=event_preview,
            event_written=event_written,
            envelope_summary=envelope_summary,
            write_summary=write_summary,
            next_action=next_action,
        )

    # Append failed (validation_failed or error). Rollback is handled by append_event.
    return ApprovalResolveResult(
        status=append_result.status,
        approval_id=approval_id,
        task_id=task_id,
        request_id=request_id,
        decision=decision,
        mode=mode,
        event_preview=event_preview,
        envelope_summary=envelope_summary,
        write_summary=write_summary,
        findings=list(append_result.findings),
        next_action=append_result.next_action,
    )
