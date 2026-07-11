"""Read-only orchestration route preview for the agent-runtime CLI.

This module provides a capability-routing preview: given a requested
capability and optional constraints, it selects an adapter and returns a safe
routing decision summary. It does not perform guardrail preflight, does not
execute adapters, does not write ledgers or envelopes, and does not access
networks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .adapter_registry import AdapterMetadata, load_adapter_registry
from .result import Finding
from .tasks import find_task


@dataclass
class RoutePreviewResult:
    """Result of an orchestration route preview."""

    status: str
    requested_capability: str
    task_id: str | None = None
    selected_adapter_id: str | None = None
    capability: str | None = None
    operation: str | None = None
    requested_mode: str = "dry-run"
    selected_mode: str = "dry-run"
    risk_level: str | None = None
    requires_approval: bool = False
    requires_dry_run: bool = False
    fallback_candidates: list[dict[str, Any]] = field(default_factory=list)
    routing_reason: str = ""
    constraints: dict[str, Any] = field(default_factory=dict)
    findings: list[Finding] = field(default_factory=list)
    next_action: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "status": self.status,
            "requested_capability": self.requested_capability,
        }
        if self.task_id is not None:
            d["task_id"] = self.task_id
        d["selected_adapter_id"] = self.selected_adapter_id
        if self.capability is not None:
            d["capability"] = self.capability
        if self.operation is not None:
            d["operation"] = self.operation
        d["requested_mode"] = self.requested_mode
        d["selected_mode"] = self.selected_mode
        if self.risk_level is not None:
            d["risk_level"] = self.risk_level
        d["requires_approval"] = self.requires_approval
        d["requires_dry_run"] = self.requires_dry_run
        if self.fallback_candidates:
            d["fallback_candidates"] = self.fallback_candidates
        if self.routing_reason:
            d["routing_reason"] = self.routing_reason
        if self.constraints:
            d["constraints"] = self.constraints
        if self.findings:
            d["findings"] = [f.to_dict() for f in self.findings]
        if self.next_action is not None:
            d["next_action"] = self.next_action
        return d


def _build_task_context(task: dict[str, Any] | None) -> dict[str, Any] | None:
    """Return a value-safe summary of a task for routing context."""
    if task is None:
        return None
    return {
        "task_id": task.get("id", ""),
        "status": task.get("status", ""),
        "requested_capability": task.get("requested_capability", ""),
        "assignee": task.get("assignee", "") or "-",
    }


def _select_operation(metadata: AdapterMetadata, capability: str) -> str | None:
    """Derive a safe operation name from adapter metadata.

    If the adapter's input schema requires an "operation" field and the
    capability itself is a plausible operation value, use it. Otherwise return
    None rather than guessing.
    """
    input_schema = metadata.input_schema
    properties = input_schema.get("properties", {})
    required = input_schema.get("required", [])
    if "operation" in required and "operation" in properties:
        # Capability is the best available operation hint.
        return capability
    return None


def _is_high_risk(risk_level: str | None) -> bool:
    """Return True for risk levels that should default to dry-run."""
    return risk_level in {"external", "destructive", "privileged"}


def preview_route(
    root: Path,
    capability: str,
    task_id: str | None = None,
    adapter_id: str | None = None,
    requested_mode: str = "dry-run",
) -> RoutePreviewResult:
    """Preview capability routing without executing or writing anything.

    Loads the adapter registry projection, selects the first enabled adapter
    that supports the requested capability, and returns a value-safe routing
    decision. If an explicit adapter_id is provided, it must support the
    capability or the result will be blocked/needs_input.

    This function is read-only: it does not execute adapters, write ledgers,
    or access networks.
    """
    task_context: dict[str, Any] | None = None
    if task_id is not None:
        task = find_task(root, task_id)
        if task is not None:
            task_context = _build_task_context(task)

    registry, findings, next_action = load_adapter_registry(root)
    if registry is None:
        return RoutePreviewResult(
            status="error",
            requested_capability=capability,
            task_id=task_id,
            findings=findings,
            next_action=next_action,
        )

    enabled_adapters = [a for a in registry.list_adapters() if a.enabled]
    matching = sorted(
        [a for a in enabled_adapters if capability in a.capabilities],
        key=lambda a: a.source_index,
    )

    if not matching:
        return RoutePreviewResult(
            status="needs_input",
            requested_capability=capability,
            task_id=task_id,
            routing_reason=f"No enabled adapter supports capability '{capability}'.",
            next_action="Register an adapter for this capability or check the capability name.",
        )

    selected: Any | None = None
    if adapter_id is not None:
        selected = next((a for a in matching if a.adapter_id == adapter_id), None)
        if selected is None:
            supported = [a.adapter_id for a in matching]
            return RoutePreviewResult(
                status="blocked",
                requested_capability=capability,
                task_id=task_id,
                routing_reason=(
                    f"Adapter '{adapter_id}' does not support capability '{capability}'. "
                    f"Supported adapters: {', '.join(supported)}."
                ),
                fallback_candidates=[
                    {"adapter_id": a.adapter_id, "reason": "supports requested capability"}
                    for a in matching
                ],
                next_action="Choose an adapter that supports the capability or omit --adapter.",
            )
    else:
        selected = matching[0]

    # Build fallback candidates from remaining matching adapters.
    remaining = [a for a in matching if a.adapter_id != selected.adapter_id]
    fallback_candidates = [
        {"adapter_id": a.adapter_id, "reason": "supports requested capability"}
        for a in remaining
    ]

    risk_level = selected.risk_level
    requires_approval = bool(selected.requires_approval)
    requires_dry_run = _is_high_risk(risk_level) or requires_approval

    # selected_mode is the most conservative of requested_mode and adapter constraints.
    selected_mode = requested_mode
    if requested_mode == "commit" and requires_dry_run:
        selected_mode = "dry-run"

    operation = _select_operation(selected, capability)

    constraints = {
        "adapter_kind": selected.kind,
        "risk_level": risk_level,
        "requires_approval": requires_approval,
        "requires_dry_run": requires_dry_run,
        "preflight_checks": list(selected.preflight_checks),
    }

    routing_reason = (
        f"Selected adapter '{selected.adapter_id}' for capability '{capability}' "
        f"based on source order and capability match."
    )

    if task_context is not None:
        constraints["task_context"] = task_context

    next_action = "Use orchestration preflight to aggregate routing with guardrail checks."

    return RoutePreviewResult(
        status="pass",
        requested_capability=capability,
        task_id=task_id,
        selected_adapter_id=selected.adapter_id,
        capability=capability,
        operation=operation,
        requested_mode=requested_mode,
        selected_mode=selected_mode,
        risk_level=risk_level,
        requires_approval=requires_approval,
        requires_dry_run=requires_dry_run,
        fallback_candidates=fallback_candidates,
        routing_reason=routing_reason,
        constraints=constraints,
        next_action=next_action,
    )
