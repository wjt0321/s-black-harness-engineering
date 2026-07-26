"""Read-only validation for one-work-item collaboration dispatch proposals."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, SchemaError, ValidationError, validate

from .loader import normalize_path
from .orchestration_collaboration import inspect_collaboration_plan
from .result import EXIT_ERROR, EXIT_PASS, EXIT_VALIDATION_FAILED, Finding

SCHEMA_VERSION = "control-plane/collaboration-dispatch-proposal/v1"
DISPATCH_SCHEMA = "adapters/collaboration-dispatch.schema.json"
ACP_READINESS_SAMPLE = "adapters/acp-readiness-evidence.sample.json"
ACP_READINESS_SCHEMA = "adapters/acp-readiness-evidence.schema.json"
_MAX_BYTES = 64 * 1024


def _finding(rule_id: str, message: str) -> Finding:
    return Finding(rule_id=rule_id, severity="block", action="deny", message=message)


def _load_project_json(root: Path, relative: str, max_bytes: int = _MAX_BYTES) -> tuple[dict[str, Any] | None, str | None, Finding | None]:
    resolved_root = root.resolve()
    path = (resolved_root / relative).resolve()
    if path == resolved_root or resolved_root not in path.parents:
        return None, None, _finding("dispatch-path-escape", "Dispatch input must remain inside the project root.")
    if path.suffix.lower() != ".json":
        return None, None, _finding("dispatch-file-type", "Dispatch input must use the .json extension.")
    try:
        if not path.is_file() or path.stat().st_size > max_bytes:
            return None, None, _finding("dispatch-file-unavailable", "Dispatch input is missing or exceeds the read limit.")
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None, None, _finding("dispatch-file-unreadable", "Dispatch input must be readable UTF-8 JSON.")
    if not isinstance(payload, dict):
        return None, None, _finding("dispatch-file-malformed", "Dispatch input must be a JSON object.")
    return payload, normalize_path(path.relative_to(resolved_root)), None


@dataclass(frozen=True)
class CollaborationDispatchResult:
    status: str
    source_file: str | None = None
    proposal: dict[str, Any] | None = None
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
                "dispatches_work": False,
                "collects_readiness": False,
                "executes_agents": False,
                "accesses_network": False,
                "writes_ledgers": False,
            },
        }
        if self.source_file is not None:
            payload["source"] = {"dispatch_file": self.source_file}
        if self.proposal is not None:
            canonical = json.dumps(self.proposal, sort_keys=True, separators=(",", ":")).encode("utf-8")
            payload["proposal"] = {
                **self.proposal,
                "proposal_id": f"sha256:{hashlib.sha256(canonical).hexdigest()}",
            }
        if self.findings:
            payload["findings"] = [finding.to_dict() for finding in self.findings]
        payload["next_action"] = {
            "code": "review_dispatch_blockers" if self.status == "pass" else "fix_dispatch_proposal",
            "message": "Review eligibility and blocked reasons; no work has been dispatched.",
        }
        return payload


def inspect_collaboration_dispatch(root: Path, dispatch_file: str) -> CollaborationDispatchResult:
    """Validate a proposal and project eligibility without dispatching anything."""
    data, source_file, failure = _load_project_json(root, dispatch_file)
    if failure is not None or data is None:
        return CollaborationDispatchResult("validation_failed", source_file, findings=(failure,) if failure else ())

    try:
        schema = json.loads((root / DISPATCH_SCHEMA).read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        validate(data, schema)
    except (OSError, json.JSONDecodeError, SchemaError, ValidationError):
        return CollaborationDispatchResult(
            "validation_failed", source_file,
            findings=(_finding("dispatch-schema-invalid", "Dispatch proposal or schema validation failed."),),
        )

    plan_result = inspect_collaboration_plan(root, data["collaboration_file"])
    if plan_result.status != "pass" or plan_result.plan is None:
        return CollaborationDispatchResult(
            "validation_failed", source_file,
            findings=(_finding("dispatch-collaboration-invalid", "Referenced collaboration plan is not valid."),),
        )
    plan = plan_result.to_dict()["plan"]
    findings: list[Finding] = []
    if data["plan_id"] != plan["plan_id"]:
        findings.append(_finding("dispatch-plan-drift", "Dispatch plan_id does not match the current collaboration plan."))
    work = next((item for item in plan["work_items"] if item["work_item_id"] == data["work_item_id"]), None)
    if work is None:
        findings.append(_finding("dispatch-work-item-unknown", "Dispatch work_item_id is not present in the collaboration plan."))
    elif work["socket_id"] != data["socket_id"]:
        findings.append(_finding("dispatch-socket-mismatch", "Dispatch socket_id does not match the planned work item."))
    elif bool(work["review_required"]) != data["review_required"]:
        findings.append(_finding("dispatch-review-mismatch", "Dispatch review_required does not match the planned work item."))

    if findings:
        return CollaborationDispatchResult("validation_failed", source_file, findings=tuple(findings))

    explanation = next(item for item in plan["routing_explanations"] if item["socket_id"] == data["socket_id"])
    required_inputs = sorted({artifact for handoff in plan["handoffs"] if handoff["to_work_item_id"] == data["work_item_id"] for artifact in handoff["artifact_types"]})
    if sorted(data["input_artifact_types"]) != required_inputs:
        return CollaborationDispatchResult(
            "validation_failed", source_file,
            findings=(_finding("dispatch-input-artifact-mismatch", "Dispatch input artifacts must match incoming handoffs."),),
        )

    readiness = explanation["readiness_evidence"]
    blocked_reasons = ["execution_authority_unavailable"]
    if readiness["status"] != "collected":
        blocked_reasons.insert(0, "readiness_not_collected")
    proposal = {
        "collaboration_plan_id": plan["plan_id"],
        "work_item_id": data["work_item_id"],
        "socket_id": data["socket_id"],
        "role": work["role"],
        "input_artifact_types": required_inputs,
        "expected_artifact_types": work["expected_artifact_types"],
        "timeout_seconds": data["timeout_seconds"],
        "review_required": data["review_required"],
        "readiness_evidence": readiness,
        "plan_eligible": True,
        "dispatch_eligible": False,
        "status": "blocked",
        "blocked_reasons": blocked_reasons,
        "execution": "not_executed",
    }
    return CollaborationDispatchResult("pass", source_file, proposal)
