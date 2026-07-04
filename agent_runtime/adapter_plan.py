"""Read-only adapter execution envelope planner.

This module wraps the existing check_action preflight result into an adapter
execution envelope draft. It does not execute adapters, write ledgers, access
networks, or read credential files.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import validate, ValidationError as JsonSchemaValidationError

from .loader import load_adapters, load_schema
from .policy import check_action
from .policy_profile import resolve_profile
from .result import CheckResult, Finding


ENVELOPE_SCHEMA_PATH = "adapters/execution-envelope.schema.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")


def _generate_id(prefix: str) -> str:
    """Generate an id matching execution-envelope.schema.json id_string pattern.

    The schema requires the suffix to be digits only; use a numeric fragment
    derived from a UUID so the value is still non-sequential.
    """
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    suffix = str(uuid.uuid4().int % 10**6).zfill(6)
    return f"{prefix}-{today}-{suffix}"


def _finding_to_dict(finding: Finding) -> dict[str, Any]:
    """Convert a Finding to an envelope finding, mapping error severity to block."""
    severity = finding.severity
    if severity not in {"info", "warn", "block"}:
        severity = "block"
    return {
        "rule_id": finding.rule_id,
        "severity": severity,
        "action": finding.action,
        "message": finding.message,
    }


@dataclass
class PlanResult:
    status: str
    findings: list[Finding]
    next_action: str | None
    envelope: dict[str, Any] | None


def plan_adapter_action(
    root: Path,
    adapter_id: str,
    operation: str,
    target: str | None = None,
    actor: str = "cli",
    task_id: str | None = None,
    args: Any | None = None,
) -> PlanResult:
    """Generate an adapter execution envelope draft for a planned action.

    The function is read-only: it runs preflight checks and produces artifact
    drafts. It never executes the adapter, writes ledger files, or accesses the
    network.
    """
    profile = resolve_profile(args, root) if args else "all"
    explicit_policy = None
    if args is not None and getattr(args, "policy", None):
        explicit_policy = (root / args.policy).resolve()

    adapters_data = load_adapters(root)
    adapter = next(
        (a for a in adapters_data.get("adapters", []) if a.get("id") == adapter_id),
        None,
    )
    if adapter is None:
        return PlanResult(
            status="error",
            findings=[
                Finding(
                    rule_id="adapter-not-found",
                    severity="error",
                    action="error",
                    message=f"Adapter '{adapter_id}' not found in registry.",
                )
            ],
            next_action="Register the adapter or check the adapter id.",
            envelope=None,
        )

    risk_level = adapter.get("risk_level", "local")
    requires_approval = adapter.get("requires_approval", False)

    preflight = check_action(
        root,
        adapter_id,
        operation,
        target=target,
        explicit_policy=explicit_policy,
        profile=profile,
    )

    if task_id is None:
        task_id = _generate_id("task")

    request_id = _generate_id("req")
    timestamp = _utc_now()

    envelope: dict[str, Any] = {
        "version": 1,
        "description": f"Adapter execution plan for {adapter_id} {operation}",
        "artifacts": [],
    }

    adapter_request: dict[str, Any] = {
        "artifact_type": "adapter_request",
        "request_id": request_id,
        "task_id": task_id,
        "adapter_id": adapter_id,
        "operation": operation,
        "actor": actor,
        "target": target or "",
        "input": {
            "operation": operation,
            "target": target,
        },
        "context": {
            "source": "cli",
            "policy_profile": profile or "all",
            "risk_level": risk_level,
            "dry_run": True,
            "requires_approval": requires_approval or preflight.status == "needs_approval",
            "approval_id": None,
            "payload_refs": [],
        },
        "preflight": {
            "status": preflight.status,
            "findings": [_finding_to_dict(f) for f in preflight.findings],
        },
        "created_at": timestamp,
    }
    envelope["artifacts"].append(adapter_request)

    if preflight.status == "needs_approval":
        approval_id = _generate_id("appr")
        adapter_request["context"]["approval_id"] = approval_id

        approval_record: dict[str, Any] = {
            "artifact_type": "approval_record",
            "approval_id": approval_id,
            "request_id": request_id,
            "status": "pending",
            "scope": {
                "task_id": task_id,
                "adapter_id": adapter_id,
                "operation": operation,
                "target": target or "",
            },
            "requested_at": timestamp,
            "decided_at": None,
            "decided_by": None,
        }
        envelope["artifacts"].append(approval_record)

        execution_event: dict[str, Any] = {
            "artifact_type": "execution_event",
            "event_id": _generate_id("exe"),
            "task_id": task_id,
            "request_id": request_id,
            "timestamp": timestamp,
            "actor": actor,
            "event_type": "approval_requested",
            "message": "Approval requested before adapter execution.",
            "metadata": {
                "approval_id": approval_id,
                "adapter_id": adapter_id,
                "operation": operation,
                "target": target,
                "preflight_status": preflight.status,
            },
        }
        envelope["artifacts"].append(execution_event)

    try:
        schema = load_schema(root, ENVELOPE_SCHEMA_PATH)
        validate(instance=envelope, schema=schema)
    except (OSError, JsonSchemaValidationError) as exc:
        return PlanResult(
            status="error",
            findings=[
                Finding(
                    rule_id="envelope-schema-error",
                    severity="error",
                    action="error",
                    message=f"Generated envelope does not match schema: {exc}",
                )
            ],
            next_action="Review the generated envelope and schema.",
            envelope=None,
        )

    return PlanResult(
        status=preflight.status,
        findings=preflight.findings,
        next_action=preflight.next_action,
        envelope=envelope,
    )
