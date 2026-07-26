"""Deterministic current-state operator inbox projection.

This module consumes a current collaboration run fixture and fixture approval
collection. It never reads a real approval ledger, invokes an Agent, starts a
session, probes readiness, writes files, or grants execution authority.
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

SCHEMA_VERSION = "control-plane/collaboration-operator-inbox/v1"
COMMAND_CANDIDATE_SCHEMA_VERSION = (
    "control-plane/collaboration-action-command-candidate/v1"
)
INBOX_SCHEMA = "adapters/collaboration-operator-inbox.schema.json"
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
        return None, None, _finding(
            "collaboration-operator-inbox-path-escape",
            "Operator inbox fixture must remain inside the project root.",
        )
    if path.suffix.lower() != ".json":
        return None, None, _finding(
            "collaboration-operator-inbox-file-type",
            "Operator inbox fixture must use the .json extension.",
        )
    try:
        if not path.is_file() or path.stat().st_size > _MAX_BYTES:
            return None, normalize_path(path.relative_to(base)), _finding(
                "collaboration-operator-inbox-unavailable",
                "Operator inbox fixture is missing or exceeds the 128 KiB read limit.",
            )
        return json.loads(path.read_text(encoding="utf-8")), normalize_path(
            path.relative_to(base)
        ), None
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None, normalize_path(path.relative_to(base)), _finding(
            "collaboration-operator-inbox-unavailable",
            "Operator inbox fixture could not be read as bounded UTF-8 JSON.",
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


@dataclass(frozen=True)
class CollaborationOperatorInboxResult:
    status: str
    source_file: str | None = None
    inbox: dict[str, Any] | None = None
    current_run: dict[str, Any] | None = None
    actions: tuple[dict[str, Any], ...] = ()
    pending_approvals: tuple[dict[str, Any], ...] = ()
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
            "current_state_only": True,
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
            payload["source"] = {"collaboration_inbox_file": self.source_file}
        if self.inbox is not None:
            payload["inbox"] = self.inbox
        if self.current_run is not None:
            payload["current_run"] = self.current_run
        if self.actions:
            payload["actions"] = list(self.actions)
        if self.pending_approvals:
            payload["pending_approvals"] = list(self.pending_approvals)
        if self.summary is not None:
            payload["summary"] = self.summary
        if self.projection_id is not None:
            payload["inbox_projection_id"] = self.projection_id
        if self.findings:
            payload["findings"] = [item.to_dict() for item in self.findings]
        payload["next_action"] = {
            "code": (
                "review_current_operator_inbox"
                if self.status == "pass"
                else "fix_current_operator_inbox"
            ),
            "message": (
                "Review the current-state fixture inbox; it is not execution authority."
            ),
        }
        return payload

    def render_human(self) -> str:
        lines = [f"COLLABORATION OPERATOR INBOX {self.status.upper()}"]
        if self.current_run is not None:
            lines.append(f"run_id={self.current_run['run_id']}")
            lines.append(f"run_status={self.current_run['status']}")
        if self.summary is not None:
            lines.append(
                "summary: "
                f"actions={self.summary['action_count']} "
                f"eligible={self.summary['eligible_count']} "
                f"blocked={self.summary['blocked_count']} "
                f"pending_approvals={self.summary['pending_approval_count']}"
            )
        for item in self.actions:
            reasons = ",".join(item["blocked_reasons"]) or "none"
            lines.append(
                f"- {item['action']} target={item['target_type']}:{item['target_id']} "
                f"state={item['current_state']} eligible={str(item['action_eligible']).lower()} "
                f"blocked={reasons}"
            )
        lines.append("execution_authorized=false")
        lines.append("dispatch_eligible=false")
        lines.append("execution=not_executed")
        for finding in self.findings:
            lines.append(f"- {finding.rule_id}: {finding.message}")
        return "\n".join(lines)


def inspect_collaboration_operator_inbox(
    root: Path,
    inbox_file: str,
) -> CollaborationOperatorInboxResult:
    """Project only the latest current-state operator inbox."""
    data, source, failure = _load_project_json(root, inbox_file)
    if failure is not None or data is None:
        return CollaborationOperatorInboxResult(
            "validation_failed", source, findings=(failure,) if failure else ()
        )

    try:
        schema = json.loads((root / INBOX_SCHEMA).read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        validate(data, schema)
    except (OSError, json.JSONDecodeError, SchemaError, ValidationError):
        return CollaborationOperatorInboxResult(
            "validation_failed",
            source,
            findings=(
                _finding(
                    "collaboration-operator-inbox-schema-invalid",
                    "Operator inbox fixture or schema validation failed.",
                ),
            ),
        )

    run_result = inspect_collaboration_run_state(root, data["run_state_file"])
    if run_result.status != "pass" or run_result.run is None:
        return CollaborationOperatorInboxResult(
            "validation_failed",
            source,
            findings=(
                _finding(
                    "collaboration-operator-inbox-run-state-invalid",
                    "Referenced current collaboration run state is not valid.",
                ),
            ),
        )

    findings: list[Finding] = []
    approvals = _unique_map(
        data["approvals"],
        "approval_id",
        "collaboration-operator-inbox-approval-id-duplicate",
        findings,
    )
    _unique_map(
        data["action_requests"],
        "request_id",
        "collaboration-operator-inbox-request-id-duplicate",
        findings,
    )
    if findings:
        return CollaborationOperatorInboxResult(
            "validation_failed", source, findings=tuple(findings)
        )

    run = run_result.run
    attempts_by_id = {item["attempt_id"]: item for item in run["attempts"]}
    reviews_by_id = {item["review_id"]: item for item in run["reviews"]}
    handoffs_by_id = {item["handoff_id"]: item for item in run["handoffs"]}
    current_attempts = set(run["current_attempts"].values())
    current_work_items = {
        item["work_item_id"]: item["attempt_id"]
        for item in run["attempts"]
        if item["attempt_id"] in current_attempts
    }
    current_review_ids = {
        item["review_id"]
        for item in run["reviews"]
        if current_work_items.get(item["work_item_id"]) == item["attempt_id"]
    }
    current_handoff_ids = {
        item["handoff_id"]
        for item in run["handoffs"]
        if (
            current_work_items.get(item["from_work_item_id"])
            == item["from_attempt_id"]
            and current_work_items.get(item["to_work_item_id"])
            == item["to_attempt_id"]
        )
    }
    current_entities = {
        "run": {run["run_id"]},
        "work_item_attempt": current_attempts,
        "review": current_review_ids,
        "handoff": current_handoff_ids,
    }
    current_states = {"run": {run["run_id"]: run["status"]}}
    current_states["work_item_attempt"] = {
        item_id: attempts_by_id[item_id]["status"] for item_id in current_attempts
    }
    current_states["review"] = {
        item_id: reviews_by_id[item_id]["status"] for item_id in current_review_ids
    }
    current_states["handoff"] = {
        item_id: handoffs_by_id[item_id]["status"] for item_id in current_handoff_ids
    }

    recorded_keys = set(data["recorded_idempotency_keys"])
    seen_keys: set[str] = set()
    action_rows: list[dict[str, Any]] = []
    for request in data["action_requests"]:
        blocked: list[str] = []
        expected_type, allowed_states = _ACTION_CONTRACT[request["action"]]
        current_state: str | None = None
        if request["target_type"] != expected_type:
            blocked.append("action_target_mismatch")
        elif request["target_id"] not in current_entities[request["target_type"]]:
            blocked.append("target_not_current")
        else:
            current_state = current_states[request["target_type"]][request["target_id"]]
            if (
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
            "expected_state": request["expected_state"],
            "approval_id": request["approval_id"],
        }
        idempotency_key = _canonical_hash(command_basis)
        if idempotency_key in recorded_keys:
            blocked.append("command_already_recorded")
        if idempotency_key in seen_keys:
            blocked.append("command_duplicate_in_projection")
        seen_keys.add(idempotency_key)

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

    pending_approvals = tuple(
        {
            "approval_id": item["approval_id"],
            "status": item["status"],
            "action": item["binding"]["action"],
            "target_type": item["binding"]["target_type"],
            "target_id": item["binding"]["target_id"],
            "expected_state": item["binding"]["expected_state"],
        }
        for item in data["approvals"]
        if item["status"] == "pending"
    )
    summary = {
        "action_count": len(action_rows),
        "eligible_count": sum(item["action_eligible"] for item in action_rows),
        "blocked_count": sum(not item["action_eligible"] for item in action_rows),
        "pending_approval_count": len(pending_approvals),
        "approved_fixture_count": sum(
            item["status"] == "approved" for item in data["approvals"]
        ),
        "current_attempt_count": len(current_attempts),
        "current_review_count": len(current_review_ids),
        "current_handoff_count": len(current_handoff_ids),
    }
    current_run = {
        "run_id": run["run_id"],
        "run_projection_id": run["run_projection_id"],
        "status": run["status"],
        "run_state_file": run_result.source_file,
        "current_attempts": run["current_attempts"],
        "current_review_ids": sorted(current_review_ids),
        "current_handoff_ids": sorted(current_handoff_ids),
        "event_count": run["summary"]["event_count"],
    }
    inbox = {
        "inbox_id": data["inbox_id"],
        "operator_ref": data["operator_ref"],
        "approval_evidence": "fixture",
        "current_state_only": True,
    }
    projection_body = {
        "inbox": inbox,
        "current_run": current_run,
        "actions": action_rows,
        "pending_approvals": list(pending_approvals),
        "summary": summary,
    }
    return CollaborationOperatorInboxResult(
        "pass",
        source,
        inbox=inbox,
        current_run=current_run,
        actions=tuple(action_rows),
        pending_approvals=pending_approvals,
        summary=summary,
        projection_id=_canonical_hash(projection_body),
    )
