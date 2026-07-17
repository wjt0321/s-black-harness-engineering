"""Deterministic Stage 44 single-user real-execution readiness gate.

The gate validates a fixed source-backed design profile. It never starts a
process, reads credentials, accesses a network, or writes files or ledgers.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema import SchemaError as JsonSchemaError
from jsonschema import ValidationError as JsonSchemaValidationError
from jsonschema import validate

from .adapter_registry import load_adapter_registry
from .loader import load_json
from .result import Finding, _STATUS_TO_EXIT, EXIT_ERROR


SCHEMA_VERSION = "control-plane/single-user-execution-readiness/v1"
GATE_ID = "single-user-real-execution-readiness/v1"
PROFILE_PATH = "adapters/execution-readiness.sample.json"
PROFILE_SCHEMA_PATH = "adapters/execution-readiness.schema.json"
REGISTRY_PATH = "adapters/adapters.sample.json"
EVENT_SCHEMA_PATH = "tasks/event.schema.json"
EXECUTION_EVENT_TYPES = (
    "execution_started",
    "execution_succeeded",
    "execution_failed",
    "execution_cancelled",
)
CHECK_IDS = (
    "profile_schema",
    "single_user_identity",
    "candidate_registry_alignment",
    "fixed_argv",
    "working_directory",
    "environment_allowlist",
    "bounded_process",
    "side_effect_boundary",
    "approval_binding_contract",
    "audit_contract",
    "executor_implementation",
    "approval_binding_implementation",
    "audit_writer_implementation",
)
IMPLEMENTATION_FINDINGS = {
    "executor_implementation": (
        "execution-readiness-executor-unavailable",
        "The fixed one-shot executor is not implemented.",
    ),
    "approval_binding_implementation": (
        "execution-readiness-approval-binding-unavailable",
        "Approval decisions are not yet bound to a canonical plan hash.",
    ),
    "audit_writer_implementation": (
        "execution-readiness-audit-writer-unavailable",
        "Execution lifecycle event writing is not implemented.",
    ),
}
GUARANTEES = {
    "deterministic": True,
    "read_only": True,
    "single_user": True,
    "multi_user_authorization": False,
    "executes_processes": False,
    "executes_adapters": False,
    "reads_credentials": False,
    "writes_files": False,
    "writes_ledgers": False,
    "accesses_network": False,
}
SOURCE = {
    "profile": PROFILE_PATH,
    "profile_schema": PROFILE_SCHEMA_PATH,
    "adapter_registry": REGISTRY_PATH,
    "event_schema": EVENT_SCHEMA_PATH,
}


@dataclass(frozen=True)
class ExecutionReadinessResult:
    """Safe, deterministic readiness result."""

    status: str
    readiness: str
    scope: dict[str, Any] = field(default_factory=dict)
    process_contract: dict[str, Any] = field(default_factory=dict)
    approval_binding: dict[str, Any] = field(default_factory=dict)
    audit_contract: dict[str, Any] = field(default_factory=dict)
    checks: tuple[dict[str, str], ...] = ()
    findings: tuple[Finding, ...] = ()
    next_action: str = "Fix readiness contract validation before implementation."

    def exit_code(self) -> int:
        return _STATUS_TO_EXIT.get(self.status, EXIT_ERROR)

    def to_dict(self) -> dict[str, Any]:
        summary = {
            "total": len(self.checks),
            "pass": sum(check["status"] == "pass" for check in self.checks),
            "blocked": sum(check["status"] == "blocked" for check in self.checks),
        }
        return {
            "status": self.status,
            "schema_version": SCHEMA_VERSION,
            "gate": GATE_ID,
            "readiness": self.readiness,
            "source": dict(SOURCE),
            "scope": self.scope,
            "process_contract": self.process_contract,
            "approval_binding": self.approval_binding,
            "audit_contract": self.audit_contract,
            "checks": [dict(check) for check in self.checks],
            "summary": summary,
            "findings": [finding.to_dict() for finding in self.findings],
            "guarantees": dict(GUARANTEES),
            "next_action": self.next_action,
        }

    def render_human(self) -> str:
        lines = [
            "EXECUTION READINESS",
            f"status={self.status}",
            f"readiness={self.readiness}",
        ]
        lines.extend(
            f"- {check['check_id']}: {check['status']}" for check in self.checks
        )
        lines.append(f"Next: {self.next_action}")
        return "\n".join(lines)


def _check(check_id: str, status: str) -> dict[str, str]:
    return {"check_id": check_id, "status": status}


def _safe_failure(rule_id: str, message: str) -> ExecutionReadinessResult:
    return ExecutionReadinessResult(
        status="validation_failed",
        readiness="contract_invalid",
        findings=(Finding(rule_id, "error", "validation_failed", message),),
    )


def _profile_checks(profile: dict[str, Any]) -> dict[str, bool]:
    identity = profile["identity"]
    process = profile["process_contract"]
    environment = process["environment"]
    approval = profile["approval_binding"]
    audit = profile["audit_contract"]
    return {
        "profile_schema": True,
        "single_user_identity": identity == {
            "mode": "single_user_local",
            "actor": "local-operator",
            "multi_user_authorization": False,
            "future_extension": "actor_context",
        },
        "fixed_argv": process["executable"] == "git"
        and process["argv"] == ["git", "status", "--short", "--branch"]
        and process["shell"] is False,
        "working_directory": process["cwd"] == "project_root"
        and process["stdin"] == "closed",
        "environment_allowlist": environment == {
            "inherit_allowlist": ["PATH", "SYSTEMROOT", "WINDIR"],
            "set": {"GIT_OPTIONAL_LOCKS": "0"},
        },
        "bounded_process": process["timeout_seconds"] == 10
        and process["max_timeout_seconds"] == 30
        and process["max_stdout_bytes"] == 65536
        and process["max_stderr_bytes"] == 65536,
        "side_effect_boundary": process["retry_count"] == 0
        and process["network_access"] is False
        and process["writes_project_files"] is False
        and process["background"] is False,
        "approval_binding_contract": approval == {
            "required_for_approval_adapters": True,
            "bound_fields": [
                "adapter_id", "capability", "operation", "plan_hash",
                "request_id", "target_digest", "task_id",
            ],
            "decision_event_type": "approval_resolved",
            "recheck_before_spawn": True,
            "retry_reuses_approval": False,
        },
        "audit_contract": audit == {
            "event_types": list(EXECUTION_EVENT_TYPES),
            "controlled_append": True,
            "rollback_on_failure": True,
            "stores_raw_stdout": False,
            "stores_raw_stderr": False,
        },
    }


def _event_schema_matches_pre_execution_state(schema: object) -> bool:
    """Preserve the historical v1 boundary after later audit schema work.

    Stage 44 froze the absence of the legacy ``execution_started`` type. Later
    stages may add dedicated, provenance-checked execution audit types without
    changing this permanent readiness snapshot.
    """
    if not isinstance(schema, dict) or schema.get("type") != "object":
        return False
    required = schema.get("required")
    if not isinstance(required, list) or "event_type" not in required:
        return False
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        return False
    event_type = properties.get("event_type")
    if not isinstance(event_type, dict) or event_type.get("type") != "string":
        return False
    allowed = event_type.get("enum")
    return (
        isinstance(allowed, list)
        and all(isinstance(item, str) for item in allowed)
        and "execution_started" not in allowed
    )


def check_execution_readiness(root: Path) -> ExecutionReadinessResult:
    """Validate the fixed readiness profile without performing execution."""
    try:
        schema = load_json(root / PROFILE_SCHEMA_PATH)
        Draft202012Validator.check_schema(schema)
        profile = load_json(root / PROFILE_PATH)
        validate(instance=profile, schema=schema)
    except (
        OSError,
        json.JSONDecodeError,
        JsonSchemaError,
        JsonSchemaValidationError,
    ):
        return _safe_failure(
            "execution-readiness-profile-invalid",
            "The fixed execution readiness profile or schema is invalid.",
        )

    try:
        registry, _, _ = load_adapter_registry(root)
    except Exception:
        registry = None
    if registry is None:
        return _safe_failure(
            "execution-readiness-registry-invalid",
            "The adapter registry could not be validated for readiness.",
        )
    try:
        event_schema = load_json(root / EVENT_SCHEMA_PATH)
        Draft202012Validator.check_schema(event_schema)
    except (OSError, json.JSONDecodeError, JsonSchemaError):
        return _safe_failure(
            "execution-readiness-event-schema-invalid",
            "The event schema could not be read for readiness validation.",
        )

    contract_checks = _profile_checks(profile)
    contract_checks["audit_contract"] = (
        contract_checks["audit_contract"]
        and _event_schema_matches_pre_execution_state(event_schema)
    )
    candidate = profile["candidate"]
    metadata = registry.get_adapter(candidate["adapter_id"])
    contract_checks["candidate_registry_alignment"] = bool(
        metadata is not None
        and metadata.enabled
        and candidate["capability"] in metadata.capabilities
        and metadata.risk_level == candidate["risk_level"]
        and metadata.kind == "shell"
        and metadata.requires_approval is False
    )

    implementation = profile["implementation"]
    check_statuses: dict[str, str] = {}
    findings: list[Finding] = []
    for check_id in CHECK_IDS[:10]:
        passed = contract_checks.get(check_id, False)
        check_statuses[check_id] = "pass" if passed else "blocked"
        if not passed:
            findings.append(Finding(
                f"execution-readiness-{check_id.replace('_', '-')}-drift",
                "block",
                "blocked",
                "The readiness contract does not match the frozen design.",
            ))

    for check_id, field_name in (
        ("executor_implementation", "executor"),
        ("approval_binding_implementation", "approval_binding"),
        ("audit_writer_implementation", "audit_writer"),
    ):
        available = implementation[field_name] is True
        check_statuses[check_id] = "pass" if available else "blocked"
        if not available:
            rule_id, message = IMPLEMENTATION_FINDINGS[check_id]
            findings.append(Finding(rule_id, "block", "blocked", message))

    checks = tuple(_check(check_id, check_statuses[check_id]) for check_id in CHECK_IDS)
    contract_ready = all(check_statuses[item] == "pass" for item in CHECK_IDS[:10])
    readiness = (
        "design_ready_implementation_blocked"
        if contract_ready
        else "contract_drift_blocked"
    )
    return ExecutionReadinessResult(
        status="blocked",
        readiness=readiness,
        scope={
            "identity": dict(profile["identity"]),
            "candidate": dict(profile["candidate"]),
        },
        process_contract=dict(profile["process_contract"]),
        approval_binding=dict(profile["approval_binding"]),
        audit_contract=dict(profile["audit_contract"]),
        checks=checks,
        findings=tuple(findings),
        next_action=(
            "Implement the fixed executor, approval plan binding, and controlled audit writer before enabling execution."
        ),
    )
