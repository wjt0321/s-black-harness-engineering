"""Deterministic read-only operator action eligibility projection.

The projection consumes fixture approval evidence and a validated Stage 79 run
history. It never invokes an Agent, starts a session, probes readiness, writes a
ledger, or turns an eligible business action into execution authority.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, SchemaError, ValidationError, validate

from .loader import normalize_path
from .orchestration_collaboration_run_state import inspect_collaboration_run_state
from .result import EXIT_ERROR, EXIT_PASS, EXIT_VALIDATION_FAILED, Finding

SCHEMA_VERSION = "control-plane/collaboration-action-eligibility/v1"
COMMAND_CANDIDATE_SCHEMA_VERSION = (
    "control-plane/collaboration-action-command-candidate/v1"
)
ACTION_ELIGIBILITY_SCHEMA = "adapters/collaboration-action-eligibility.schema.json"
_MAX_BYTES = 128 * 1024
_ACTION_CONTRACT: dict[str, tuple[str, frozenset[str]]] = {
    "approve_start": ("run", frozenset({"awaiting_approval"})),
    "cancel": ("run", frozenset({"ready", "running", "blocked"})),
    "retry": (
        "work_item_attempt",
        frozenset({"changes_requested", "failed"}),
    ),
    "request_changes": ("review", frozenset({"in_review"})),
    "approve_handoff": ("handoff", frozenset({"ready"})),
}


def _finding(rule_id: str, message: str) -> Finding:
    return Finding(rule_id=rule_id, severity="block", action="deny", message=message)


def _canonical_hash(payload: dict[str, Any]) -> str:
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(canonical).hexdigest()}"


def _load_project_json(
    root: Path, relative: str
) -> tuple[dict[str, Any] | None, str | None, Finding | None]:
    base = root.resolve()
    path = (base / relative).resolve()
    if path == base or base not in path.parents:
        return (
            None,
            None,
            _finding(
                "collaboration-action-eligibility-path-escape",
                "Action eligibility fixture must remain inside the project root.",
            ),
        )
    if path.suffix.lower() != ".json":
        return (
            None,
            None,
            _finding(
                "collaboration-action-eligibility-file-type",
                "Action eligibility fixture must use the .json extension.",
            ),
        )
    try:
        if not path.is_file() or path.stat().st_size > _MAX_BYTES:
            return (
                None,
                normalize_path(path.relative_to(base)),
                _finding(
                    "collaboration-action-eligibility-unavailable",
                    "Action eligibility fixture is missing or exceeds the 128 KiB read limit.",
                ),
            )
        return (
            json.loads(path.read_text(encoding="utf-8")),
            normalize_path(path.relative_to(base)),
            None,
        )
    except (OSError, UnicodeError, json.JSONDecodeError):
        return (
            None,
            normalize_path(path.relative_to(base)),
            _finding(
                "collaboration-action-eligibility-unavailable",
                "Action eligibility fixture could not be read as bounded UTF-8 JSON.",
            ),
        )


def _unique_map(
    rows: list[dict[str, Any]],
    field: str,
    rule_id: str,
    findings: list[Finding],
) -> dict[str, dict[str, Any]]:
    values: dict[str, dict[str, Any]] = {}
    for row in rows:
        value = row[field]
        if value in values:
            findings.append(_finding(rule_id, f"Duplicate {field}: {value}."))
        else:
            values[value] = row
    return values


def _states_as_of(events: list[dict[str, Any]], sequence: int) -> dict[tuple[str, str], str]:
    states: dict[tuple[str, str], str] = {}
    for event in events:
        if event["sequence"] > sequence:
            break
        states[(event["entity_type"], event["entity_id"])] = event["to_state"]
    return states


@dataclass(frozen=True)
class CollaborationActionEligibilityResult:
    status: str
    source_file: str | None = None
    run: dict[str, Any] | None = None
    actions: tuple[dict[str, Any], ...] = ()
    summary: dict[str, Any] | None = None
    projection_id: str | None = None
    findings: tuple[Finding, ...] = ()

    @property
    def guarantees(self) -> dict[str, Any]:
        return {
            "deterministic": True,
            "read_only": True,
            "fixture_backed": True,
            "approval_evidence": "fixture",
            "execution_authorized": False,
            "dispatch_eligible": False,
            "execution": "not_executed",
            "executes_agents": False,
            "starts_sessions": False,
            "probes_readiness": False,
            "writes_files": False,
            "writes_ledgers": False,
            "accesses_network": False,
        }

    def exit_code(self) -> int:
        if self.status == "pass":
            return EXIT_PASS
        if self.status == "validation_failed":
            return EXIT_VALIDATION_FAILED
        return EXIT_ERROR

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "status": self.status,
            "schema_version": SCHEMA_VERSION,
            "guarantees": self.guarantees,
        }
        if self.source_file is not None:
            payload["source"] = {
                "collaboration_action_file": self.source_file,
            }
        if self.run is not None:
            payload["run"] = self.run
        if self.actions:
            payload["actions"] = list(self.actions)
        if self.summary is not None:
            payload["summary"] = self.summary
        if self.projection_id is not None:
            payload["action_projection_id"] = self.projection_id
        if self.findings:
            payload["findings"] = [item.to_dict() for item in self.findings]
        payload["next_action"] = {
            "code": (
                "review_operator_action_eligibility"
                if self.status == "pass"
                else "fix_operator_action_eligibility"
            ),
            "message": (
                "Review fixture-backed eligibility; eligible does not authorize execution."
            ),
        }
        return payload

    def render_human(self) -> str:
        payload = self.to_dict()
        lines = [f"COLLABORATION ACTION ELIGIBILITY {self.status.upper()}"]
        if self.run is not None:
            lines.append(f"run_id={self.run['run_id']}")
        for item in self.actions:
            reasons = ",".join(item["blocked_reasons"]) or "none"
            lines.append(
                f"- {item['action']} target={item['target_type']}:{item['target_id']} "
                f"as_of={item['as_of_sequence']} state={item['current_state']} "
                f"eligible={str(item['action_eligible']).lower()} blocked={reasons}"
            )
        lines.append("execution_authorized=false")
        lines.append("dispatch_eligible=false")
        lines.append("execution=not_executed")
        for finding in self.findings:
            lines.append(f"- {finding.rule_id}: {finding.message}")
        return "\n".join(lines)


def inspect_collaboration_action_eligibility(
    root: Path,
    action_file: str,
) -> CollaborationActionEligibilityResult:
    """Validate fixture approvals and project operator action eligibility."""
    data, source, failure = _load_project_json(root, action_file)
    if failure is not None or data is None:
        return CollaborationActionEligibilityResult(
            "validation_failed",
            source,
            findings=(failure,) if failure else (),
        )

    try:
        schema = json.loads(
            (root / ACTION_ELIGIBILITY_SCHEMA).read_text(encoding="utf-8")
        )
        Draft202012Validator.check_schema(schema)
        validate(data, schema)
    except (OSError, json.JSONDecodeError, SchemaError, ValidationError):
        return CollaborationActionEligibilityResult(
            "validation_failed",
            source,
            findings=(
                _finding(
                    "collaboration-action-eligibility-schema-invalid",
                    "Action eligibility fixture or schema validation failed.",
                ),
            ),
        )

    run_result = inspect_collaboration_run_state(root, data["run_state_file"])
    if run_result.status != "pass" or run_result.run is None:
        return CollaborationActionEligibilityResult(
            "validation_failed",
            source,
            findings=(
                _finding(
                    "collaboration-action-eligibility-run-state-invalid",
                    "Referenced collaboration run state is not valid.",
                ),
            ),
        )

    findings: list[Finding] = []
    approvals = _unique_map(
        data["approvals"],
        "approval_id",
        "collaboration-action-eligibility-approval-id-duplicate",
        findings,
    )
    _unique_map(
        data["action_requests"],
        "request_id",
        "collaboration-action-eligibility-request-id-duplicate",
        findings,
    )
    if findings:
        return CollaborationActionEligibilityResult(
            "validation_failed",
            source,
            findings=tuple(findings),
        )

    run = run_result.run
    events = run["events"]
    event_count = len(events)
    recorded_keys = set(data["recorded_idempotency_keys"])
    seen_command_keys: set[str] = set()
    action_rows: list[dict[str, Any]] = []

    for request in data["action_requests"]:
        sequence = request["as_of_sequence"]
        current_state: str | None = None
        blocked: list[str] = []
        if sequence > event_count:
            blocked.append("checkpoint_out_of_range")
        else:
            states = _states_as_of(events, sequence)
            current_state = states.get(
                (request["target_type"], request["target_id"])
            )
            expected_target_type, allowed_states = _ACTION_CONTRACT[request["action"]]
            if request["target_type"] != expected_target_type:
                blocked.append("action_target_mismatch")
            elif current_state is None:
                blocked.append("target_not_available")
            elif (
                current_state != request["expected_state"]
                or current_state not in allowed_states
            ):
                blocked.append("target_state_mismatch")

        approval = approvals.get(request["approval_id"])
        approval_status = approval["status"] if approval is not None else "missing"
        if approval is None:
            blocked.append("approval_missing")
        else:
            if approval["status"] != "approved":
                blocked.append("approval_not_approved")
            expected_binding = {
                "run_id": run["run_id"],
                "run_projection_id": run["run_projection_id"],
                "action": request["action"],
                "target_type": request["target_type"],
                "target_id": request["target_id"],
                "as_of_sequence": request["as_of_sequence"],
                "expected_state": request["expected_state"],
            }
            if approval["binding"] != expected_binding:
                blocked.append("approval_binding_mismatch")

        command_basis = {
            "run_id": run["run_id"],
            "run_projection_id": run["run_projection_id"],
            "action": request["action"],
            "target_type": request["target_type"],
            "target_id": request["target_id"],
            "as_of_sequence": request["as_of_sequence"],
            "expected_state": request["expected_state"],
            "approval_id": request["approval_id"],
        }
        idempotency_key = _canonical_hash(command_basis)
        if idempotency_key in recorded_keys:
            blocked.append("command_already_recorded")
        if idempotency_key in seen_command_keys:
            blocked.append("command_duplicate_in_projection")
        seen_command_keys.add(idempotency_key)

        candidate: dict[str, Any] | None = None
        if not blocked:
            candidate_body = {
                "schema_version": COMMAND_CANDIDATE_SCHEMA_VERSION,
                **command_basis,
                "idempotency_key": idempotency_key,
                "execution_authorized": False,
                "dispatch_eligible": False,
                "execution": "not_executed",
            }
            candidate = {
                **candidate_body,
                "candidate_id": _canonical_hash(candidate_body),
            }

        action_rows.append(
            {
                "request_id": request["request_id"],
                "action": request["action"],
                "target_type": request["target_type"],
                "target_id": request["target_id"],
                "as_of_sequence": sequence,
                "expected_state": request["expected_state"],
                "current_state": current_state,
                "approval_id": request["approval_id"],
                "approval_status": approval_status,
                "action_eligible": not blocked,
                "execution_authorized": False,
                "idempotency_key": idempotency_key,
                "blocked_reasons": blocked,
                "command_candidate": candidate,
            }
        )

    summary = {
        "action_count": len(action_rows),
        "eligible_count": sum(item["action_eligible"] for item in action_rows),
        "blocked_count": sum(not item["action_eligible"] for item in action_rows),
        "approved_fixture_count": sum(
            item["status"] == "approved" for item in data["approvals"]
        ),
        "recorded_idempotency_key_count": len(recorded_keys),
    }
    safe_run = {
        "run_id": run["run_id"],
        "run_projection_id": run["run_projection_id"],
        "run_state_file": run_result.source_file,
        "event_count": event_count,
    }
    projection_body = {
        "run": safe_run,
        "actions": action_rows,
        "summary": summary,
    }
    return CollaborationActionEligibilityResult(
        "pass",
        source,
        run=safe_run,
        actions=tuple(action_rows),
        summary=summary,
        projection_id=_canonical_hash(projection_body),
    )
