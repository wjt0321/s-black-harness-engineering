"""Read-only orchestration run dry-run planner for the agent-runtime CLI.

This module produces a run plan preview by combining orchestration preflight
(routing + guardrail) with the existing runtime action planner. It does not
execute adapters, write ledgers or envelopes, or access networks.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .orchestration_preflight import PreflightResult, check_preflight, _needs_target
from .result import Finding
from .runtime_plan import plan_runtime_action
from .tasks import find_task


@dataclass
class RunDryRunResult:
    """Result of an orchestration run dry-run preview."""

    status: str
    task_id: str
    request_id: str
    requested_capability: str
    mode: str = "dry-run"
    route: dict[str, Any] = field(default_factory=dict)
    preflight: dict[str, Any] = field(default_factory=dict)
    candidate_envelope_summary: dict[str, Any] = field(default_factory=dict)
    candidate_events_summary: list[dict[str, Any]] = field(default_factory=list)
    artifact_candidate_refs: list[dict[str, Any]] = field(default_factory=list)
    evidence_candidate_refs: list[dict[str, Any]] = field(default_factory=list)
    plan_hash: str | None = None
    constraints: dict[str, Any] = field(default_factory=dict)
    findings: list[Finding] = field(default_factory=list)
    next_action: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "status": self.status,
            "task_id": self.task_id,
            "request_id": self.request_id,
            "requested_capability": self.requested_capability,
            "mode": self.mode,
            "route": self.route,
            "preflight": self.preflight,
            "candidate_envelope_summary": self.candidate_envelope_summary,
            "candidate_events_summary": self.candidate_events_summary,
            "artifact_candidate_refs": self.artifact_candidate_refs,
            "evidence_candidate_refs": self.evidence_candidate_refs,
            "constraints": self.constraints,
        }
        if self.plan_hash is not None:
            d["plan_hash"] = self.plan_hash
        if self.findings:
            d["findings"] = [f.to_dict() for f in self.findings]
        if self.next_action is not None:
            d["next_action"] = self.next_action
        return d


def _target_safe_summary(target: str | None) -> str:
    """Return a non-reversible, stable summary of the target for hashing."""
    if not target:
        return "none"
    digest = hashlib.sha256(target.encode("utf-8")).hexdigest()[:16]
    return f"sha256:{digest}:len={len(target)}"


def _compute_plan_hash(
    task_id: str,
    request_id: str,
    requested_capability: str,
    mode: str,
    route: dict[str, Any],
    preflight: dict[str, Any],
    candidate_envelope_summary: dict[str, Any],
    candidate_events_summary: list[dict[str, Any]],
    target: str | None,
) -> str:
    """Compute a stable plan hash from safe, deterministic fields.

    The hash intentionally excludes timestamp, generated ids, full input
    payload, target plaintext, and any credential-bearing refs.
    """
    envelope_summary_for_hash = {
        "version": candidate_envelope_summary.get("version"),
        "artifact_count": candidate_envelope_summary.get("artifact_count"),
        "adapter_id": candidate_envelope_summary.get("adapter_id"),
        "operation": candidate_envelope_summary.get("operation"),
        "preflight_status": candidate_envelope_summary.get("preflight_status"),
        "requires_approval": candidate_envelope_summary.get("requires_approval"),
    }
    event_sequence = [e.get("event_type") for e in candidate_events_summary]
    payload = {
        "task_id": task_id,
        "request_id": request_id,
        "requested_capability": requested_capability,
        "selected_adapter_id": route.get("selected_adapter_id"),
        "operation": route.get("operation"),
        "target_safe_summary": _target_safe_summary(target),
        "mode": mode,
        "route_status": route.get("status"),
        "route_risk_level": route.get("risk_level"),
        "route_requires_approval": route.get("requires_approval"),
        "route_requires_dry_run": route.get("requires_dry_run"),
        "preflight_status": preflight.get("status"),
        "preflight_effective_mode": preflight.get("effective_mode"),
        "candidate_envelope_summary": envelope_summary_for_hash,
        "candidate_event_type_sequence": event_sequence,
    }
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _error_result(
    task_id: str,
    request_id: str,
    capability: str,
    message: str,
    next_action: str,
    rule_id: str,
    status: str = "error",
) -> RunDryRunResult:
    return RunDryRunResult(
        status=status,
        task_id=task_id,
        request_id=request_id,
        requested_capability=capability,
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


def _build_envelope_summary(
    envelope: dict[str, Any], provided_request_id: str
) -> dict[str, Any]:
    """Return a value-safe summary of a generated envelope for dry-run output."""
    artifacts = envelope.get("artifacts", [])
    request = next(
        (a for a in artifacts if a.get("artifact_type") == "adapter_request"),
        {},
    )
    approval = next(
        (a for a in artifacts if a.get("artifact_type") == "approval_record"),
        None,
    )
    context = request.get("context", {}) if request else {}
    summary: dict[str, Any] = {
        "version": envelope.get("version"),
        "artifact_count": len(artifacts),
        "request_id": provided_request_id,
        "adapter_id": request.get("adapter_id"),
        "operation": request.get("operation"),
        "preflight_status": request.get("preflight", {}).get("status"),
        "requires_approval": context.get("requires_approval"),
    }
    if approval is not None:
        summary["approval_id"] = approval.get("approval_id")
    return summary


def _build_event_summary(
    event_type: str, request_id: str, task_id: str, metadata_keys: list[str]
) -> dict[str, Any]:
    return {
        "event_type": event_type,
        "task_id": task_id,
        "request_id": request_id,
        "metadata_keys": metadata_keys,
    }


def _build_candidate_events_summary(
    envelope: dict[str, Any], provided_request_id: str, task_id: str
) -> list[dict[str, Any]]:
    """Return candidate event summaries for the dry-run preview.

    These are candidate event types that would be produced on commit. They do
    not require the event schema to already contain them; they are for preview
    only.
    """
    artifacts = envelope.get("artifacts", [])
    execution_events = [
        a for a in artifacts if a.get("artifact_type") == "execution_event"
    ]
    events: list[dict[str, Any]] = []

    # If the envelope already contains an approval_requested execution_event,
    # surface it as a candidate.
    for event in execution_events:
        events.append(
            _build_event_summary(
                event_type=event.get("event_type", "approval_requested"),
                request_id=provided_request_id,
                task_id=task_id,
                metadata_keys=sorted(event.get("metadata", {}).keys()),
            )
        )

    # Always include a run_planned candidate.
    events.append(
        _build_event_summary(
            event_type="run_planned",
            request_id=provided_request_id,
            task_id=task_id,
            metadata_keys=[
                "plan_hash",
                "mode",
                "adapter_id",
                "operation",
                "capability",
            ],
        )
    )
    return events


def _build_artifact_candidate_refs(envelope: dict[str, Any]) -> list[dict[str, Any]]:
    """Return safe artifact references from a generated envelope."""
    refs: list[dict[str, Any]] = []
    for artifact in envelope.get("artifacts", []):
        artifact_type = artifact.get("artifact_type")
        ref: dict[str, Any] = {"artifact_type": artifact_type}
        if artifact_type == "adapter_request":
            ref["request_id"] = artifact.get("request_id")
            ref["adapter_id"] = artifact.get("adapter_id")
            ref["operation"] = artifact.get("operation")
        elif artifact_type == "approval_record":
            ref["approval_id"] = artifact.get("approval_id")
            ref["request_id"] = artifact.get("request_id")
        elif artifact_type == "execution_event":
            ref["event_id"] = artifact.get("event_id")
            ref["event_type"] = artifact.get("event_type")
            ref["request_id"] = artifact.get("request_id")
        refs.append(ref)
    return refs


def _build_evidence_candidate_refs() -> list[dict[str, Any]]:
    """Return empty evidence refs for a dry-run preview.

    Real evidence only exists after adapter execution, which this command never
    performs.
    """
    return []


def dry_run_run(
    root: Path,
    task_id: str,
    request_id: str,
    capability: str,
    adapter_id: str | None = None,
    operation: str | None = None,
    target: str | None = None,
    requested_mode: str = "dry-run",
    explicit_policy: Path | None = None,
    profile: str | None = None,
    actor: str = "cli",
    tasks_file: str | None = None,
    args: Any | None = None,
) -> RunDryRunResult:
    """Generate a read-only run dry-run preview.

    Combines orchestration preflight with the runtime action planner to produce
    a safe plan preview, candidate artifact/event references, and a stable
    plan_hash for future freeze guards. This function does not execute adapters,
    write ledgers or envelopes, or access networks.
    """
    if requested_mode != "dry-run":
        return _error_result(
            task_id=task_id,
            request_id=request_id,
            capability=capability,
            message=f"Mode '{requested_mode}' is not implemented for orchestration run; use --dry-run.",
            next_action="Use --dry-run to preview the run plan.",
            rule_id="run-mode-not-implemented",
            status="needs_input",
        )

    task = find_task(root, task_id, explicit_file=tasks_file)
    if task is None:
        return _error_result(
            task_id=task_id,
            request_id=request_id,
            capability=capability,
            message=f"Task '{task_id}' not found in task ledger.",
            next_action="Provide a task_id that exists in the task ledger.",
            rule_id="task-not-found",
        )

    preflight = check_preflight(
        root,
        capability=capability,
        task_id=task_id,
        adapter_id=adapter_id,
        operation=operation,
        target=target,
        requested_mode=requested_mode,
        explicit_policy=explicit_policy,
        profile=profile,
    )

    route_summary = dict(preflight.route)
    guardrail_summary = dict(preflight.guardrail)

    # If preflight did not produce a usable plan, surface its status and stop.
    if preflight.status not in {"pass", "needs_approval"}:
        return RunDryRunResult(
            status=preflight.status,
            task_id=task_id,
            request_id=request_id,
            requested_capability=capability,
            mode="dry-run",
            route=route_summary,
            preflight=guardrail_summary,
            constraints=preflight.constraints,
            findings=list(preflight.findings),
            next_action=preflight.next_action,
        )

    selected_adapter_id = route_summary.get("selected_adapter_id")
    effective_operation = operation if operation is not None else route_summary.get("operation")
    if not selected_adapter_id or not effective_operation:
        return RunDryRunResult(
            status="needs_input",
            task_id=task_id,
            request_id=request_id,
            requested_capability=capability,
            mode="dry-run",
            route=route_summary,
            preflight=guardrail_summary,
            constraints=preflight.constraints,
            findings=list(preflight.findings),
            next_action="Provide --operation for the selected adapter.",
        )

    target_missing = target is None or target.strip() == ""
    if target_missing and (route_summary.get("requires_approval") or _needs_target(selected_adapter_id, root)):
        return RunDryRunResult(
            status="needs_input",
            task_id=task_id,
            request_id=request_id,
            requested_capability=capability,
            mode="dry-run",
            route=route_summary,
            preflight=guardrail_summary,
            constraints=preflight.constraints,
            findings=list(preflight.findings),
            next_action="Provide --target for the selected operation/adapter.",
        )

    plan_result = plan_runtime_action(
        root,
        task_id=task_id,
        adapter_id=selected_adapter_id,
        operation=effective_operation,
        target=target,
        actor=actor,
        args=args,
        tasks_file=tasks_file,
    )

    if plan_result.status not in {"pass", "needs_approval"}:
        return RunDryRunResult(
            status=plan_result.status,
            task_id=task_id,
            request_id=request_id,
            requested_capability=capability,
            mode="dry-run",
            route=route_summary,
            preflight=guardrail_summary,
            constraints=preflight.constraints,
            findings=list(plan_result.findings),
            next_action=plan_result.next_action,
        )

    envelope = plan_result.envelope_draft
    if envelope is None:
        return _error_result(
            task_id=task_id,
            request_id=request_id,
            capability=capability,
            message="No envelope draft was generated for the run plan.",
            next_action="Review the adapter, operation, and target.",
            rule_id="missing-envelope-draft",
        )

    envelope_summary = _build_envelope_summary(envelope, request_id)
    events_summary = _build_candidate_events_summary(envelope, request_id, task_id)
    artifact_refs = _build_artifact_candidate_refs(envelope)
    evidence_refs = _build_evidence_candidate_refs()

    plan_hash = _compute_plan_hash(
        task_id=task_id,
        request_id=request_id,
        requested_capability=capability,
        mode="dry-run",
        route=route_summary,
        preflight={
            "status": preflight.status,
            "effective_mode": preflight.effective_mode,
        },
        candidate_envelope_summary=envelope_summary,
        candidate_events_summary=events_summary,
        target=target,
    )

    if preflight.status == "pass":
        next_action = "Review plan_hash before running with --commit."
    else:  # needs_approval
        next_action = (
            "Approval required. Use orchestration approval resolve, "
            "then re-run orchestration preflight/run before committing."
        )

    return RunDryRunResult(
        status=preflight.status,
        task_id=task_id,
        request_id=request_id,
        requested_capability=capability,
        mode="dry-run",
        route=route_summary,
        preflight=guardrail_summary,
        candidate_envelope_summary=envelope_summary,
        candidate_events_summary=events_summary,
        artifact_candidate_refs=artifact_refs,
        evidence_candidate_refs=evidence_refs,
        plan_hash=plan_hash,
        constraints=preflight.constraints,
        findings=list(preflight.findings),
        next_action=next_action,
    )
