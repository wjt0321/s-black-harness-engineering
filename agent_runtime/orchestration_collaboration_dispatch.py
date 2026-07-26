"""Read-only validation for one-work-item collaboration dispatch proposals."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
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
ACP_READINESS_V2_SCHEMA = "adapters/acp-readiness-evidence-v2.schema.json"
ACP_RUNNER_BINDINGS = "adapters/acp-runner-bindings.sample.json"
ACP_RUNNER_BINDINGS_SCHEMA = "adapters/acp-runner-bindings.schema.json"
_MAX_BYTES = 64 * 1024


def _finding(rule_id: str, message: str) -> Finding:
    return Finding(rule_id=rule_id, severity="block", action="deny", message=message)


def _parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timezone required")
    return parsed.astimezone(timezone.utc)


def _validate_readiness_evidence(
    root: Path,
    evidence_file: str,
    socket_id: str,
    evaluated_at: str,
) -> tuple[dict[str, Any] | None, Finding | None]:
    evidence, _, failure = _load_project_json(root, evidence_file)
    if failure is not None or evidence is None:
        return None, _finding("dispatch-readiness-unavailable", "Readiness evidence must be project-local bounded JSON.")
    try:
        schema = json.loads((root / ACP_READINESS_V2_SCHEMA).read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        validate(evidence, schema)
        evaluated = _parse_time(evaluated_at)
        evidence_evaluated = _parse_time(evidence["evaluated_at"])
        expires = _parse_time(evidence["expires_at"])
    except (OSError, json.JSONDecodeError, SchemaError, ValidationError, ValueError, TypeError):
        return None, _finding("dispatch-readiness-invalid", "Readiness evidence failed schema or timestamp validation.")
    evidence_id = evidence["evidence_id"]
    body = {key: value for key, value in evidence.items() if key != "evidence_id"}
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    if evidence_id != f"sha256:{hashlib.sha256(canonical).hexdigest()}":
        return None, _finding("dispatch-readiness-tampered", "Readiness evidence content hash does not match.")
    if evidence["socket_id"] != socket_id:
        return None, _finding("dispatch-readiness-socket-mismatch", "Readiness evidence is bound to another socket.")
    if evaluated < evidence_evaluated:
        return None, _finding("dispatch-readiness-time-invalid", "Dispatch evaluation cannot precede evidence evaluation.")
    if evaluated > expires:
        return None, _finding("dispatch-readiness-expired", "Readiness evidence has expired.")
    bindings, _, binding_failure = _load_project_json(root, ACP_RUNNER_BINDINGS)
    try:
        binding_schema = json.loads((root / ACP_RUNNER_BINDINGS_SCHEMA).read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(binding_schema)
        validate(bindings, binding_schema)
    except (OSError, json.JSONDecodeError, SchemaError, ValidationError, TypeError):
        return None, _finding("dispatch-readiness-binding-invalid", "ACP runner bindings failed validation.")
    if binding_failure is not None or bindings is None:
        return None, _finding("dispatch-readiness-binding-invalid", "ACP runner bindings are unavailable.")
    binding = next((item for item in bindings["bindings"] if item["socket_id"] == socket_id), None)
    if binding is None or binding["runner_id"] != evidence["runner_id"]:
        return None, _finding("dispatch-readiness-runner-mismatch", "Readiness evidence runner does not match the socket binding.")
    return evidence, None


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
    evidence_file = data.get("readiness_evidence_file")
    if evidence_file is None:
        blocked_reasons.insert(0, "readiness_not_collected")
    else:
        collected, readiness_failure = _validate_readiness_evidence(
            root,
            evidence_file,
            data["socket_id"],
            data["evaluated_at"],
        )
        if readiness_failure is not None or collected is None:
            return CollaborationDispatchResult(
                "validation_failed", source_file,
                findings=(readiness_failure,) if readiness_failure else (),
            )
        readiness = {
            "status": collected["status"],
            "contract": collected["contract"],
            "runner_id": collected["runner_id"],
            "level": collected["level"],
            "evidence_id": collected["evidence_id"],
            "observed_at": collected["observed_at"],
            "expires_at": collected["expires_at"],
            "sufficient_for_dispatch": collected["sufficient_for_dispatch"],
            "live_probe_performed": False,
        }
        if not collected["sufficient_for_dispatch"]:
            blocked_reasons.insert(0, "readiness_insufficient")
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
