"""Read-only routing decision snapshot for the control plane state model.

This module projects Stage 11 route/preflight decisions into a stable,
deterministic, value-safe control-plane state object. It does not persist the
snapshot, write ledgers, execute adapters, or access networks.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from .orchestration_preflight import PreflightResult
from .orchestration_route import RoutePreviewResult


SCHEMA_VERSION = "control-plane/routing-decision/v1"


def _canonical_json(payload: dict[str, Any]) -> str:
    """Return a deterministic compact JSON representation."""
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _compute_snapshot_id(payload: dict[str, Any]) -> str:
    """Return a deterministic sha256 content id for the snapshot payload."""
    canonical = _canonical_json(payload)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


@dataclass(frozen=True)
class RoutingDecisionSnapshot:
    """Deterministic, ephemeral read model of a routing decision.

    This object is intentionally not persisted. It serves as the first Stage 12
    control-plane state projection, consumable by future Run/Event/API layers.
    """

    schema_version: str
    snapshot_id: str
    status: str
    routing: dict[str, Any]
    constraints: dict[str, Any]
    source: dict[str, Any]
    trace: dict[str, Any] | None = None
    guardrail: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "schema_version": self.schema_version,
            "snapshot_id": self.snapshot_id,
            "status": self.status,
            "routing": self.routing,
            "constraints": self.constraints,
            "source": self.source,
        }
        if self.trace is not None:
            d["trace"] = self.trace
        if self.guardrail is not None:
            d["guardrail"] = self.guardrail
        return d


def _routing_layer(route_result: RoutePreviewResult) -> dict[str, Any]:
    """Project routing fields from a route preview result."""
    return {
        "status": route_result.status,
        "requested_capability": route_result.requested_capability,
        "requested_mode": route_result.requested_mode,
        "selected_adapter_id": route_result.selected_adapter_id,
        "operation": route_result.operation,
        "risk_level": route_result.risk_level,
        "requires_approval": route_result.requires_approval,
        "requires_dry_run": route_result.requires_dry_run,
        "routing_reason": route_result.routing_reason,
        "fallback_adapter_ids": [
            candidate["adapter_id"] for candidate in route_result.fallback_candidates
        ],
    }


def _constraints_layer(route_result: RoutePreviewResult) -> dict[str, Any]:
    """Project a safe constraints summary from a route preview result."""
    constraints = dict(route_result.constraints)
    safe: dict[str, Any] = {
        "adapter_kind": constraints.get("adapter_kind"),
        "preflight_checks": list(constraints.get("preflight_checks", [])),
    }
    if "routing_constraints" in constraints:
        safe["routing_constraints"] = constraints["routing_constraints"]
    if "task_context" in constraints:
        safe["task_context"] = constraints["task_context"]
    return safe


def _source_layer(task_id: str | None, request_id: str | None) -> dict[str, Any]:
    """Project source identity fields."""
    return {
        "task_id": task_id,
        "request_id": request_id,
    }


def _build_payload(
    status: str,
    routing: dict[str, Any],
    constraints: dict[str, Any],
    source: dict[str, Any],
    trace: dict[str, Any] | None,
    guardrail: dict[str, Any] | None,
) -> dict[str, Any]:
    """Construct the canonical snapshot payload without snapshot_id.

    This payload is hashed to produce the deterministic snapshot_id.
    """
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "routing": routing,
        "constraints": constraints,
        "source": source,
    }
    if trace is not None:
        payload["trace"] = trace
    if guardrail is not None:
        payload["guardrail"] = guardrail
    return payload


def build_routing_snapshot(
    route_result: RoutePreviewResult,
    task_id: str | None = None,
    request_id: str | None = None,
    explain: bool = False,
) -> RoutingDecisionSnapshot:
    """Build a deterministic routing decision snapshot from a route preview.

    The snapshot is a pure projection: it does not re-run routing, mutate state,
    or access external systems.
    """
    routing = _routing_layer(route_result)
    constraints = _constraints_layer(route_result)
    source = _source_layer(task_id, request_id)
    trace = (
        route_result.decision_trace.to_dict()
        if explain and route_result.decision_trace is not None
        else None
    )

    payload = _build_payload(
        route_result.status, routing, constraints, source, trace, None
    )
    snapshot_id = _compute_snapshot_id(payload)

    return RoutingDecisionSnapshot(
        schema_version=SCHEMA_VERSION,
        snapshot_id=snapshot_id,
        status=route_result.status,
        routing=routing,
        constraints=constraints,
        source=source,
        trace=trace,
        guardrail=None,
    )


def _guardrail_summary(guardrail: dict[str, Any]) -> dict[str, Any]:
    """Return a compact, safe guardrail summary.

    Only rule ids are exposed, not full messages or payloads.
    """
    return {
        "status": guardrail.get("status"),
        "finding_count": guardrail.get("finding_count", 0),
        "blocking_rule_ids": [
            finding["rule_id"]
            for finding in guardrail.get("blocking_findings", [])
        ],
    }


def build_preflight_snapshot(
    preflight_result: PreflightResult,
    task_id: str | None = None,
    request_id: str | None = None,
    explain: bool = False,
) -> RoutingDecisionSnapshot:
    """Build a deterministic preflight decision snapshot from a preflight result.

    Builds the routing layer directly from the preflight result's route summary,
    then adds the layered guardrail summary. The final snapshot_id is computed
    from the final canonical payload (without any intermediate snapshot_id).
    """
    route_like = RoutePreviewResult(
        status=preflight_result.route["status"],
        requested_capability=preflight_result.requested_capability,
        task_id=preflight_result.task_id,
        selected_adapter_id=preflight_result.route.get("selected_adapter_id"),
        capability=preflight_result.route.get("capability"),
        operation=preflight_result.route.get("operation"),
        requested_mode=preflight_result.requested_mode,
        selected_mode=preflight_result.selected_mode,
        risk_level=preflight_result.route.get("risk_level"),
        requires_approval=preflight_result.route.get("requires_approval", False),
        requires_dry_run=preflight_result.route.get("requires_dry_run", False),
        fallback_candidates=preflight_result.route.get("fallback_candidates", []),
        routing_reason=preflight_result.route.get("routing_reason", ""),
        constraints=preflight_result.constraints,
        decision_trace=None,
    )
    routing = _routing_layer(route_like)
    constraints = _constraints_layer(route_like)
    source = _source_layer(task_id, request_id)
    trace = preflight_result.route.get("decision_trace") if explain else None
    guardrail = _guardrail_summary(preflight_result.guardrail)

    payload = _build_payload(
        preflight_result.status, routing, constraints, source, trace, guardrail
    )
    snapshot_id = _compute_snapshot_id(payload)

    return RoutingDecisionSnapshot(
        schema_version=SCHEMA_VERSION,
        snapshot_id=snapshot_id,
        status=preflight_result.status,
        routing=routing,
        constraints=constraints,
        source=source,
        trace=trace,
        guardrail=guardrail,
    )
