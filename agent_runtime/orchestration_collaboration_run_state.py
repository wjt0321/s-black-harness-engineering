"""Deterministic read-only projection for fixture-backed collaboration run state.

This module validates project-local simulated history against an existing
collaboration plan. It never invokes an Agent, probes readiness, starts a
session, writes a ledger, or grants dispatch authority.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, SchemaError, ValidationError, validate

from .loader import normalize_path
from .orchestration_collaboration import inspect_collaboration_plan
from .result import EXIT_ERROR, EXIT_PASS, EXIT_VALIDATION_FAILED, Finding

SCHEMA_VERSION = "control-plane/collaboration-run-state/v1"
RUN_STATE_SCHEMA = "adapters/collaboration-run-state.schema.json"
_MAX_BYTES = 128 * 1024

_CLOSED_ATTEMPT_STATES = frozenset({"changes_requested", "completed", "failed", "cancelled"})
_TRANSITIONS: dict[str, tuple[str, frozenset[tuple[str | None, str]]]] = {
    "run_created": ("run", frozenset({(None, "draft")})),
    "plan_confirmed": ("run", frozenset({("draft", "awaiting_approval")})),
    "start_approved": ("run", frozenset({("awaiting_approval", "ready")})),
    "run_started": ("run", frozenset({("ready", "running")})),
    "run_blocked": ("run", frozenset({("running", "blocked")})),
    "run_resumed": ("run", frozenset({("blocked", "running")})),
    "cancel_requested": ("run", frozenset({("ready", "cancelling"), ("running", "cancelling"), ("blocked", "cancelling")})),
    "run_cancelled": ("run", frozenset({("cancelling", "cancelled")})),
    "run_completed": ("run", frozenset({("running", "completed")})),
    "run_failed": ("run", frozenset({("running", "failed"), ("blocked", "failed")})),
    "work_item_attempt_created": ("work_item_attempt", frozenset({(None, "planned")})),
    "work_item_ready": ("work_item_attempt", frozenset({("planned", "ready"), ("blocked", "ready")})),
    "work_item_started": ("work_item_attempt", frozenset({("ready", "running")})),
    "work_item_blocked": ("work_item_attempt", frozenset({("running", "blocked")})),
    "work_item_review_requested": ("work_item_attempt", frozenset({("running", "review_pending")})),
    "work_item_changes_requested": ("work_item_attempt", frozenset({("review_pending", "changes_requested")})),
    "work_item_completed": ("work_item_attempt", frozenset({("running", "completed"), ("review_pending", "completed")})),
    "work_item_failed": ("work_item_attempt", frozenset({("running", "failed"), ("blocked", "failed")})),
    "work_item_cancelled": ("work_item_attempt", frozenset({
        ("planned", "cancelled"), ("ready", "cancelled"), ("running", "cancelled"),
        ("blocked", "cancelled"), ("review_pending", "cancelled"),
    })),
    "review_created": ("review", frozenset({(None, "pending")})),
    "review_started": ("review", frozenset({("pending", "in_review")})),
    "review_approved": ("review", frozenset({("in_review", "approved")})),
    "review_changes_requested": ("review", frozenset({("in_review", "changes_requested")})),
    "review_cancelled": ("review", frozenset({("pending", "cancelled"), ("in_review", "cancelled")})),
    "handoff_created": ("handoff", frozenset({(None, "pending")})),
    "handoff_ready": ("handoff", frozenset({("pending", "ready")})),
    "handoff_accepted": ("handoff", frozenset({("ready", "accepted")})),
    "handoff_rejected": ("handoff", frozenset({("ready", "rejected")})),
    "handoff_superseded": ("handoff", frozenset({("pending", "superseded"), ("ready", "superseded"), ("accepted", "superseded")})),
    "artifact_expected": ("artifact", frozenset({(None, "expected")})),
    "artifact_reported": ("artifact", frozenset({("expected", "reported")})),
    "artifact_validated": ("artifact", frozenset({("reported", "validated")})),
    "artifact_rejected": ("artifact", frozenset({("reported", "rejected")})),
    "artifact_superseded": ("artifact", frozenset({("reported", "superseded"), ("validated", "superseded"), ("rejected", "superseded")})),
}


def _finding(rule_id: str, message: str) -> Finding:
    return Finding(rule_id=rule_id, severity="block", action="deny", message=message)


def _load_project_json(root: Path, relative: str) -> tuple[dict[str, Any] | None, str | None, Finding | None]:
    base = root.resolve()
    path = (base / relative).resolve()
    if path == base or base not in path.parents:
        return None, None, _finding("collaboration-run-state-path-escape", "Collaboration run file must remain inside the project root.")
    if path.suffix.lower() != ".json":
        return None, None, _finding("collaboration-run-state-file-type", "Collaboration run file must use the .json extension.")
    try:
        if not path.is_file() or path.stat().st_size > _MAX_BYTES:
            return None, None, _finding("collaboration-run-state-unavailable", "Collaboration run file is missing or exceeds the 128 KiB read limit.")
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None, None, _finding("collaboration-run-state-unreadable", "Collaboration run file must be readable UTF-8 JSON.")
    if not isinstance(value, dict):
        return None, None, _finding("collaboration-run-state-malformed", "Collaboration run file must contain a JSON object.")
    return value, normalize_path(path.relative_to(base)), None


def _unique_map(rows: list[dict[str, Any]], field: str, findings: list[Finding]) -> dict[str, dict[str, Any]]:
    values: dict[str, dict[str, Any]] = {}
    for row in rows:
        value = row[field]
        if value in values:
            findings.append(_finding("collaboration-run-state-id-duplicate", f"Duplicate {field}: {value}."))
        else:
            values[value] = row
    return values


@dataclass(frozen=True)
class CollaborationRunStateResult:
    status: str
    source_file: str | None = None
    run: dict[str, Any] | None = None
    findings: tuple[Finding, ...] = ()

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
            "guarantees": {
                "deterministic": True,
                "read_only": True,
                "fixture_backed": True,
                "dispatch_eligible": False,
                "execution": "not_executed",
                "executes_agents": False,
                "starts_sessions": False,
                "probes_readiness": False,
                "writes_files": False,
                "writes_ledgers": False,
                "accesses_network": False,
            },
        }
        if self.source_file is not None:
            payload["source"] = {"collaboration_run_file": self.source_file}
        if self.run is not None:
            payload["run"] = self.run
        if self.findings:
            payload["findings"] = [item.to_dict() for item in self.findings]
        payload["next_action"] = {
            "code": "review_collaboration_run_state" if self.status == "pass" else "fix_collaboration_run_state",
            "message": "Review the simulated run projection; no Agent work has been executed.",
        }
        return payload


def inspect_collaboration_run_state(root: Path, run_file: str) -> CollaborationRunStateResult:
    """Validate and project one simulated collaboration run without side effects."""
    data, source, failure = _load_project_json(root, run_file)
    if failure is not None or data is None:
        return CollaborationRunStateResult("validation_failed", source, findings=(failure,) if failure else ())
    try:
        schema = json.loads((root / RUN_STATE_SCHEMA).read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        validate(data, schema)
    except (OSError, json.JSONDecodeError, SchemaError, ValidationError):
        return CollaborationRunStateResult(
            "validation_failed", source,
            findings=(_finding("collaboration-run-state-schema-invalid", "Collaboration run fixture or schema validation failed."),),
        )

    plan_result = inspect_collaboration_plan(root, data["collaboration_file"])
    if plan_result.status != "pass" or plan_result.plan is None:
        return CollaborationRunStateResult(
            "validation_failed", source,
            findings=(_finding("collaboration-run-state-plan-invalid", "Referenced collaboration plan is not valid."),),
        )
    plan = plan_result.to_dict()["plan"]
    work_by_id = {item["work_item_id"]: item for item in plan["work_items"]}
    gate_by_id = {item["gate_id"]: item for item in plan["review_gates"]}
    handoff_by_pair = {
        (item["from_work_item_id"], item["to_work_item_id"]): item
        for item in plan["handoffs"]
    }

    findings: list[Finding] = []
    attempts = data["work_item_attempts"]
    reviews = data["reviews"]
    handoffs = data["handoffs"]
    artifacts = data["artifacts"]
    events = data["events"]
    attempt_by_id = _unique_map(attempts, "attempt_id", findings)
    review_by_id = _unique_map(reviews, "review_id", findings)
    handoff_by_id = _unique_map(handoffs, "handoff_id", findings)
    artifact_by_id = _unique_map(artifacts, "artifact_id", findings)
    _unique_map(events, "event_id", findings)

    attempts_by_work: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for attempt in attempts:
        work_id = attempt["work_item_id"]
        attempts_by_work[work_id].append(attempt)
        if work_id not in work_by_id:
            findings.append(_finding("collaboration-run-state-work-item-unknown", f"Attempt references unknown work item: {work_id}."))
    for work_id in work_by_id:
        rows = sorted(attempts_by_work.get(work_id, []), key=lambda item: item["attempt_number"])
        if not rows:
            findings.append(_finding("collaboration-run-state-attempt-missing", f"Work item {work_id} has no attempt projection."))
            continue
        if [item["attempt_number"] for item in rows] != list(range(1, len(rows) + 1)):
            findings.append(_finding("collaboration-run-state-attempt-sequence", f"Attempts for {work_id} must be contiguous from 1."))
        if sum(item["status"] not in _CLOSED_ATTEMPT_STATES for item in rows) > 1:
            findings.append(_finding("collaboration-run-state-attempt-sequence", f"Work item {work_id} has more than one active attempt."))
        for previous in rows[:-1]:
            if previous["status"] not in _CLOSED_ATTEMPT_STATES:
                findings.append(_finding("collaboration-run-state-attempt-sequence", f"Retry for {work_id} requires the previous attempt to be closed."))

    for artifact in artifacts:
        attempt = attempt_by_id.get(artifact["attempt_id"])
        work = work_by_id.get(artifact["work_item_id"])
        if (
            attempt is None
            or work is None
            or attempt["work_item_id"] != artifact["work_item_id"]
            or artifact["artifact_type"] not in work["expected_artifact_types"]
            or artifact["artifact_id"] not in attempt["artifact_ids"]
        ):
            findings.append(_finding("collaboration-run-state-artifact-contract", f"Artifact {artifact['artifact_id']} does not match its work-item attempt contract."))
    for attempt in attempts:
        for artifact_id in attempt["artifact_ids"]:
            artifact = artifact_by_id.get(artifact_id)
            if artifact is None or artifact["attempt_id"] != attempt["attempt_id"]:
                findings.append(_finding("collaboration-run-state-artifact-contract", f"Attempt {attempt['attempt_id']} references an invalid artifact."))

    for review in reviews:
        attempt = attempt_by_id.get(review["attempt_id"])
        gate = gate_by_id.get(review["gate_id"])
        artifact_rows = [artifact_by_id.get(item) for item in review["artifact_ids"]]
        if (
            attempt is None
            or gate is None
            or attempt["work_item_id"] != review["work_item_id"]
            or review["work_item_id"] not in gate["after_work_item_ids"]
            or review["review_id"] not in attempt["review_ids"]
            or any(item is None or item["attempt_id"] != attempt["attempt_id"] for item in artifact_rows)
        ):
            findings.append(_finding("collaboration-run-state-review-contract", f"Review {review['review_id']} does not match its gate and attempt contract."))
    for attempt in attempts:
        linked_reviews = [review_by_id.get(item) for item in attempt["review_ids"]]
        if any(item is None or item["attempt_id"] != attempt["attempt_id"] for item in linked_reviews):
            findings.append(_finding("collaboration-run-state-review-contract", f"Attempt {attempt['attempt_id']} references an invalid review."))
        work = work_by_id.get(attempt["work_item_id"])
        if attempt["status"] == "changes_requested" and not any(item and item["status"] == "changes_requested" for item in linked_reviews):
            findings.append(_finding("collaboration-run-state-review-contract", f"Changes-requested attempt {attempt['attempt_id']} requires a matching review decision."))
        if work and work["review_required"] and attempt["status"] == "completed" and not any(item and item["status"] == "approved" for item in linked_reviews):
            findings.append(_finding("collaboration-run-state-review-contract", f"Completed review-required attempt {attempt['attempt_id']} requires approval."))

    for handoff in handoffs:
        source_attempt = attempt_by_id.get(handoff["from_attempt_id"])
        target_attempt = attempt_by_id.get(handoff["to_attempt_id"])
        contract = handoff_by_pair.get((handoff["from_work_item_id"], handoff["to_work_item_id"]))
        artifact_rows = [artifact_by_id.get(item) for item in handoff["artifact_ids"]]
        if (
            source_attempt is None
            or target_attempt is None
            or contract is None
            or source_attempt["work_item_id"] != handoff["from_work_item_id"]
            or target_attempt["work_item_id"] != handoff["to_work_item_id"]
            or any(
                item is None
                or item["attempt_id"] != source_attempt["attempt_id"]
                or item["artifact_type"] not in contract["artifact_types"]
                for item in artifact_rows
            )
        ):
            findings.append(_finding("collaboration-run-state-handoff-contract", f"Handoff {handoff['handoff_id']} does not match the planned dependency and artifact contract."))

    sequences = [item["sequence"] for item in events]
    if sequences != list(range(1, len(events) + 1)):
        findings.append(_finding("collaboration-run-state-event-sequence", "Event sequence must be contiguous, ordered, and start at 1."))

    expected_states: dict[tuple[str, str], str] = {("run", data["run_id"]): data["run_state"]}
    expected_states.update({("work_item_attempt", item["attempt_id"]): item["status"] for item in attempts})
    expected_states.update({("review", item["review_id"]): item["status"] for item in reviews})
    expected_states.update({("handoff", item["handoff_id"]): item["status"] for item in handoffs})
    expected_states.update({("artifact", item["artifact_id"]): item["status"] for item in artifacts})
    replayed: dict[tuple[str, str], str] = {}
    for event in events:
        key = (event["entity_type"], event["entity_id"])
        spec = _TRANSITIONS.get(event["event_type"])
        pair = (event["from_state"], event["to_state"])
        if key not in expected_states:
            findings.append(_finding("collaboration-run-state-event-entity", f"Event {event['event_id']} references an unknown entity."))
            continue
        if spec is None or spec[0] != event["entity_type"] or pair not in spec[1] or event["from_state"] != replayed.get(key):
            findings.append(_finding("collaboration-run-state-transition-invalid", f"Event {event['event_id']} is not an allowed transition."))
            continue
        replayed[key] = event["to_state"]
    for key, expected in expected_states.items():
        if replayed.get(key) != expected:
            findings.append(_finding("collaboration-run-state-projection-mismatch", f"Event replay does not match projected state for {key[1]}."))

    latest_attempts = {
        work_id: max(rows, key=lambda item: item["attempt_number"])
        for work_id, rows in attempts_by_work.items()
        if rows and work_id in work_by_id
    }
    if data["run_state"] == "completed":
        incomplete = any(latest_attempts.get(work_id, {}).get("status") != "completed" for work_id in work_by_id)
        for work_id, work in work_by_id.items():
            latest = latest_attempts.get(work_id)
            if latest is None:
                continue
            validated_types = {
                artifact["artifact_type"]
                for artifact in artifacts
                if artifact["attempt_id"] == latest["attempt_id"] and artifact["status"] == "validated"
            }
            if not set(work["expected_artifact_types"]).issubset(validated_types):
                incomplete = True
        if any(not any(
            item["status"] == "accepted"
            and item["from_work_item_id"] == pair[0]
            and item["to_work_item_id"] == pair[1]
            for item in handoffs
        ) for pair in handoff_by_pair):
            incomplete = True
        if incomplete:
            findings.append(_finding("collaboration-run-state-completion-incomplete", "Completed run requires completed latest attempts, validated expected artifacts, and accepted planned handoffs."))

    if findings:
        return CollaborationRunStateResult("validation_failed", source, findings=tuple(findings))

    attempts_sorted = sorted(attempts, key=lambda item: (item["work_item_id"], item["attempt_number"]))
    run_body = {
        "run_id": data["run_id"],
        "collaboration_plan_id": plan["plan_id"],
        "parent_task_ref": plan["parent_task_ref"],
        "status": data["run_state"],
        "dispatch_eligible": False,
        "execution": "not_executed",
        "current_attempts": {
            work_id: latest_attempts[work_id]["attempt_id"]
            for work_id in sorted(latest_attempts)
        },
        "attempts": attempts_sorted,
        "reviews": sorted(reviews, key=lambda item: item["review_id"]),
        "handoffs": sorted(handoffs, key=lambda item: item["handoff_id"]),
        "artifacts": sorted(artifacts, key=lambda item: item["artifact_id"]),
        "events": sorted(events, key=lambda item: item["sequence"]),
        "operator_actions": [
            {"action": action, "enabled": False, "mode": "simulated"}
            for action in ("approve_start", "cancel", "retry", "request_changes", "approve_handoff")
        ],
        "summary": {
            "work_item_count": len(work_by_id),
            "attempt_count": len(attempts),
            "retry_count": sum(max(0, len(rows) - 1) for rows in attempts_by_work.values()),
            "review_count": len(reviews),
            "handoff_count": len(handoffs),
            "artifact_count": len(artifacts),
            "event_count": len(events),
            "blocked_recovery_count": sum(item["event_type"] == "run_resumed" for item in events),
        },
    }
    canonical = json.dumps(run_body, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    run = {**run_body, "run_projection_id": f"sha256:{hashlib.sha256(canonical).hexdigest()}"}
    return CollaborationRunStateResult("pass", source, run)
