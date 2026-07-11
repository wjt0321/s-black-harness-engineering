"""Read-only orchestration preflight for the agent-runtime CLI.

This module aggregates a capability-routing preview with the existing policy
preflight (`policy.check_action`) to produce a safe, read-only handoff summary.
It does not execute adapters, does not write ledgers or envelopes, and does not
access networks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .adapter_registry import load_adapter_registry
from .orchestration_route import preview_route
from .policy import check_action
from .result import Finding, coalesce_status


@dataclass
class PreflightResult:
    """Result of an orchestration preflight handoff check."""

    status: str
    requested_capability: str
    task_id: str | None = None
    requested_mode: str = "dry-run"
    selected_mode: str = "dry-run"
    effective_mode: str = "dry-run"
    route: dict[str, Any] = field(default_factory=dict)
    guardrail: dict[str, Any] = field(default_factory=dict)
    requires_approval: bool = False
    requires_dry_run: bool = False
    constraints: dict[str, Any] = field(default_factory=dict)
    findings: list[Finding] = field(default_factory=list)
    next_action: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "status": self.status,
            "requested_capability": self.requested_capability,
            "task_id": self.task_id,
            "requested_mode": self.requested_mode,
            "selected_mode": self.selected_mode,
            "effective_mode": self.effective_mode,
            "route": self.route,
            "guardrail": self.guardrail,
            "requires_approval": self.requires_approval,
            "requires_dry_run": self.requires_dry_run,
            "constraints": self.constraints,
        }
        if self.findings:
            d["findings"] = [f.to_dict() for f in self.findings]
        if self.next_action is not None:
            d["next_action"] = self.next_action
        return d


def _route_summary(route_result: Any) -> dict[str, Any]:
    """Return a value-safe summary of a RoutePreviewResult."""
    return {
        "status": route_result.status,
        "selected_adapter_id": route_result.selected_adapter_id,
        "capability": route_result.capability,
        "operation": route_result.operation,
        "risk_level": route_result.risk_level,
        "requires_approval": route_result.requires_approval,
        "requires_dry_run": route_result.requires_dry_run,
        "fallback_candidates": route_result.fallback_candidates,
        "routing_reason": route_result.routing_reason,
    }


def _guardrail_summary(guardrail_result: Any) -> dict[str, Any]:
    """Return a value-safe summary of a policy CheckResult."""
    findings = guardrail_result.findings
    return {
        "status": guardrail_result.status,
        "finding_count": len(findings),
        "blocking_findings": [
            {
                "rule_id": f.rule_id,
                "severity": f.severity,
                "action": f.action,
                "message": f.message,
            }
            for f in findings
        ],
    }


def _needs_target(adapter_id: str, root: Path) -> bool:
    """Return True if the adapter input schema requires a target field."""
    registry, _findings, _next_action = load_adapter_registry(root)
    if registry is None:
        return False
    metadata = registry.get_adapter(adapter_id)
    if metadata is None:
        return False
    return "target" in metadata.input_schema.get("required", [])


def check_preflight(
    root: Path,
    capability: str,
    task_id: str | None = None,
    adapter_id: str | None = None,
    operation: str | None = None,
    target: str | None = None,
    requested_mode: str = "dry-run",
    explicit_policy: Path | None = None,
    profile: str | None = None,
) -> PreflightResult:
    """Run a read-only orchestration preflight handoff check.

    Combines `orchestration_route.preview_route` with `policy.check_action` to
    produce a safe summary of routing decision plus guardrail constraints. The
    function is read-only: it does not execute adapters, write ledgers, or
    access networks.
    """
    if requested_mode not in {"dry-run", "commit"}:
        return PreflightResult(
            status="error",
            requested_capability=capability,
            task_id=task_id,
            requested_mode=requested_mode,
            selected_mode="dry-run",
            effective_mode="dry-run",
            findings=[
                Finding(
                    rule_id="invalid-mode",
                    severity="error",
                    action="error",
                    message="--mode must be 'dry-run' or 'commit'.",
                )
            ],
            next_action="Provide --mode dry-run or --mode commit.",
        )

    route = preview_route(
        root,
        capability=capability,
        task_id=task_id,
        adapter_id=adapter_id,
        requested_mode=requested_mode,
    )

    findings: list[Finding] = list(route.findings)

    # If routing itself did not pass, do not continue to guardrail checks.
    if route.status != "pass":
        route_summary = _route_summary(route)
        return PreflightResult(
            status=route.status,
            requested_capability=capability,
            task_id=task_id,
            requested_mode=requested_mode,
            selected_mode=route.selected_mode,
            effective_mode=route.selected_mode,
            route=route_summary,
            guardrail={"status": None, "finding_count": 0, "blocking_findings": []},
            requires_approval=False,
            requires_dry_run=False,
            constraints=route.constraints,
            findings=findings,
            next_action=route.next_action,
        )

    selected_adapter_id = route.selected_adapter_id
    assert selected_adapter_id is not None

    effective_operation = operation if operation is not None else route.operation
    route_summary = _route_summary(route)
    route_summary["operation"] = effective_operation

    if effective_operation is None:
        return PreflightResult(
            status="needs_input",
            requested_capability=capability,
            task_id=task_id,
            requested_mode=requested_mode,
            selected_mode=route.selected_mode,
            effective_mode="dry-run",
            route=route_summary,
            guardrail={"status": None, "finding_count": 0, "blocking_findings": []},
            requires_approval=False,
            requires_dry_run=True,
            constraints=route.constraints,
            findings=findings,
            next_action="Provide --operation for the selected adapter.",
        )

    if target is None and _needs_target(selected_adapter_id, root):
        return PreflightResult(
            status="needs_input",
            requested_capability=capability,
            task_id=task_id,
            requested_mode=requested_mode,
            selected_mode=route.selected_mode,
            effective_mode="dry-run",
            route=route_summary,
            guardrail={"status": None, "finding_count": 0, "blocking_findings": []},
            requires_approval=False,
            requires_dry_run=True,
            constraints=route.constraints,
            findings=findings,
            next_action="Provide --target for the selected operation.",
        )

    guardrail = check_action(
        root,
        selected_adapter_id,
        effective_operation,
        target=target,
        explicit_policy=explicit_policy,
        profile=profile,
    )
    guardrail_summary = _guardrail_summary(guardrail)
    findings.extend(guardrail.findings)

    requires_approval = route.requires_approval or guardrail.status == "needs_approval"
    requires_dry_run = (
        route.requires_dry_run
        or guardrail.status != "pass"
        or requires_approval
    )

    selected_mode = route.selected_mode
    effective_mode = requested_mode
    if requested_mode == "commit" and (selected_mode == "dry-run" or guardrail.status != "pass"):
        effective_mode = "dry-run"

    statuses = [route.status, guardrail.status]
    status = coalesce_status(statuses)

    next_action: str | None = None
    if status == "pass" and effective_mode == "commit":
        next_action = "Proceed with commit."
    elif status == "pass":
        next_action = "Proceed with dry-run."
    elif guardrail.next_action:
        next_action = guardrail.next_action
    elif route.next_action:
        next_action = route.next_action

    return PreflightResult(
        status=status,
        requested_capability=capability,
        task_id=task_id,
        requested_mode=requested_mode,
        selected_mode=selected_mode,
        effective_mode=effective_mode,
        route=route_summary,
        guardrail=guardrail_summary,
        requires_approval=requires_approval,
        requires_dry_run=requires_dry_run,
        constraints=route.constraints,
        findings=findings,
        next_action=next_action,
    )
