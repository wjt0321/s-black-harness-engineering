"""Deterministic, read-only multi-Agent collaboration plan projection.

Plans are project-local JSON proposals. They are validated against declared Agent
sockets only; this module never probes readiness, contacts Agents, writes a
ledger, or executes a plan.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .loader import normalize_path
from .orchestration_socket import list_sockets
from .result import (
    EXIT_BLOCKED,
    EXIT_ERROR,
    EXIT_NEEDS_INPUT,
    EXIT_PASS,
    EXIT_VALIDATION_FAILED,
    Finding,
)

SCHEMA_VERSION = "control-plane/collaboration-plan/v1"
_MAX_PLAN_BYTES = 128 * 1024
_SAFE_ARTIFACT_TYPES = frozenset({
    "analysis", "plan", "draft", "patch", "test_result", "review", "summary",
})
_SAFE_ROLES = frozenset({
    "researcher", "planner", "implementer", "tester", "reviewer", "synthesizer",
})
_ALLOWED_PLAN_FIELDS = frozenset({
    "parent_task_ref", "revision", "socket_bindings", "work_items", "handoffs", "review_gates",
})
_ALLOWED_BINDING_FIELDS = frozenset({"socket_id", "role", "required_capabilities"})
_ALLOWED_WORK_ITEM_FIELDS = frozenset({
    "work_item_id", "socket_id", "role", "depends_on", "expected_artifact_types", "review_required",
})
_ALLOWED_HANDOFF_FIELDS = frozenset({"from_work_item_id", "to_work_item_id", "artifact_types"})
_ALLOWED_REVIEW_FIELDS = frozenset({
    "gate_id", "after_work_item_ids", "review_role", "decision_options",
})
_READINESS_CONTRACT_BY_INVOCATION = {
    "acp_delegate": "socket-readiness/acp-session/v1",
    "local_cli": "socket-readiness/local-cli/v1",
    "agent_api": "socket-readiness/agent-api/v1",
}


def _exit_code(status: str) -> int:
    return {
        "pass": EXIT_PASS,
        "blocked": EXIT_BLOCKED,
        "needs_input": EXIT_NEEDS_INPUT,
        "validation_failed": EXIT_VALIDATION_FAILED,
    }.get(status, EXIT_ERROR)


def _finding(rule_id: str, message: str, *, action: str = "deny") -> Finding:
    return Finding(rule_id=rule_id, severity="block", action=action, message=message)


def _safe_plan_path(root: Path, plan_file: str) -> tuple[Path | None, Finding | None]:
    candidate = (root.resolve() / plan_file).resolve()
    root = root.resolve()
    if candidate == root or root not in candidate.parents:
        return None, _finding("collaboration-plan-path-escape", "Plan file must remain inside the project root.")
    if candidate.suffix.lower() != ".json":
        return None, _finding("collaboration-plan-file-type", "Plan file must use the .json extension.")
    return candidate, None


def _load_plan(root: Path, plan_file: str) -> tuple[dict[str, Any] | None, str | None, tuple[Finding, ...]]:
    path, failure = _safe_plan_path(root, plan_file)
    if failure is not None:
        return None, None, (failure,)
    assert path is not None
    try:
        if not path.is_file():
            return None, None, (_finding("collaboration-plan-not-found", "Collaboration plan file was not found."),)
        if path.stat().st_size > _MAX_PLAN_BYTES:
            return None, None, (_finding("collaboration-plan-too-large", "Collaboration plan exceeds the 128 KiB read limit."),)
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None, None, (_finding("collaboration-plan-unreadable", "Collaboration plan must be readable UTF-8 JSON."),)
    if not isinstance(data, dict):
        return None, None, (_finding("collaboration-plan-malformed", "Collaboration plan top-level value must be an object."),)
    return data, normalize_path(path.relative_to(root.resolve())), ()


def _string_list(value: Any) -> list[str] | None:
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        return None
    return list(value)


def _unique_ids(rows: list[dict[str, Any]], field: str) -> tuple[set[str], list[Finding]]:
    seen: set[str] = set()
    findings: list[Finding] = []
    for row in rows:
        value = row.get(field)
        if not isinstance(value, str) or not value:
            findings.append(_finding("collaboration-plan-id-missing", f"Every entry requires a non-empty {field}."))
        elif value in seen:
            findings.append(_finding("collaboration-plan-id-duplicate", f"Duplicate {field}: {value}."))
        else:
            seen.add(value)
    return seen, findings


def _has_cycle(work_items: dict[str, dict[str, Any]]) -> bool:
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(item_id: str) -> bool:
        if item_id in visiting:
            return True
        if item_id in visited:
            return False
        visiting.add(item_id)
        for dependency in work_items[item_id].get("depends_on", []):
            if dependency in work_items and visit(dependency):
                return True
        visiting.remove(item_id)
        visited.add(item_id)
        return False

    return any(visit(item_id) for item_id in work_items)


def _safe_projection(plan: dict[str, Any], source_file: str, socket_registry: dict[str, dict[str, Any]]) -> dict[str, Any]:
    bindings = plan["socket_bindings"]
    work_items = plan["work_items"]
    handoffs = plan["handoffs"]
    reviews = plan["review_gates"]
    return {
        "status": "planned",
        "schema_version": SCHEMA_VERSION,
        "source": {"plan_file": source_file},
        "parent_task_ref": plan["parent_task_ref"],
        "revision": plan["revision"],
        "socket_registry_identity": hashlib.sha256(
            json.dumps(sorted(socket_registry), separators=(",", ":")).encode("utf-8")
        ).hexdigest(),
        "summary": {
            "socket_count": len(bindings),
            "work_item_count": len(work_items),
            "handoff_count": len(handoffs),
            "review_gate_count": len(reviews),
            "artifact_types": sorted({artifact for item in work_items for artifact in item["expected_artifact_types"]}),
        },
        "socket_bindings": [
            {
                "socket_id": item["socket_id"],
                "role": item["role"],
                "required_capabilities": list(item["required_capabilities"]),
            }
            for item in sorted(bindings, key=lambda item: item["socket_id"])
        ],
        "routing_explanations": [
            {
                "socket_id": item["socket_id"],
                "role": item["role"],
                "selection_basis": "explicit_plan_binding",
                "capability_match": True,
                "matched_capabilities": sorted(item["required_capabilities"]),
                "declared_availability": socket_registry[item["socket_id"]]["availability"],
                "invocation_mode": socket_registry[item["socket_id"]]["invocation_mode"],
                "readiness_evidence": {
                    "status": "not_collected",
                    "contract": _READINESS_CONTRACT_BY_INVOCATION[
                        socket_registry[item["socket_id"]]["invocation_mode"]
                    ],
                    "live_probe_performed": False,
                },
                "reason": "Socket was explicitly bound and declares every required capability.",
            }
            for item in sorted(bindings, key=lambda item: item["socket_id"])
        ],
        "work_items": [
            {
                "work_item_id": item["work_item_id"],
                "socket_id": item["socket_id"],
                "role": item["role"],
                "depends_on": sorted(item["depends_on"]),
                "expected_artifact_types": sorted(item["expected_artifact_types"]),
                "review_required": item["review_required"],
                "status": "planned",
                "execution": "not_executed",
            }
            for item in sorted(work_items, key=lambda item: item["work_item_id"])
        ],
        "handoffs": [
            {
                "from_work_item_id": item["from_work_item_id"],
                "to_work_item_id": item["to_work_item_id"],
                "artifact_types": sorted(item["artifact_types"]),
            }
            for item in sorted(handoffs, key=lambda item: (item["from_work_item_id"], item["to_work_item_id"]))
        ],
        "review_gates": [
            {
                "gate_id": item["gate_id"],
                "after_work_item_ids": sorted(item["after_work_item_ids"]),
                "review_role": item["review_role"],
                "decision_options": sorted(item["decision_options"]),
                "status": "planned",
            }
            for item in sorted(reviews, key=lambda item: item["gate_id"])
        ],
        "guarantees": {
            "deterministic": True,
            "read_only": True,
            "writes_files": False,
            "writes_ledgers": False,
            "accesses_network": False,
            "probes_socket_readiness": False,
            "readiness_evidence_collected": False,
            "executes_agents": False,
        },
    }


@dataclass(frozen=True)
class CollaborationPlanResult:
    status: str
    source_file: str | None = None
    plan: dict[str, Any] | None = None
    findings: tuple[Finding, ...] = ()
    next_action: dict[str, str] | None = None

    def exit_code(self) -> int:
        return _exit_code(self.status)

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"status": self.status, "schema_version": SCHEMA_VERSION}
        if self.source_file is not None:
            result["source"] = {"plan_file": self.source_file}
        if self.plan is not None:
            canonical = json.dumps(self.plan, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
            result["plan"] = {**self.plan, "plan_id": f"sha256:{hashlib.sha256(canonical).hexdigest()}"}
        if self.findings:
            result["findings"] = [finding.to_dict() for finding in self.findings]
        if self.next_action is not None:
            result["next_action"] = self.next_action
        return result


def validate_collaboration_plan(root: Path, plan_file: str) -> CollaborationPlanResult:
    """Validate one local plan against declared sockets without side effects."""
    plan, source_file, findings = _load_plan(root, plan_file)
    if plan is None:
        return CollaborationPlanResult("validation_failed", findings=findings, next_action={"code": "provide_valid_collaboration_plan", "message": "Provide a project-local collaboration plan JSON file."})

    required_lists = ("socket_bindings", "work_items", "handoffs", "review_gates")
    failures: list[Finding] = []
    unknown_plan_fields = set(plan).difference(_ALLOWED_PLAN_FIELDS)
    if unknown_plan_fields:
        failures.append(_finding("collaboration-plan-unsafe-field", "Collaboration plan includes unsupported or unsafe fields."))
    if not isinstance(plan.get("parent_task_ref"), str) or not plan["parent_task_ref"]:
        failures.append(_finding("collaboration-plan-parent-task", "parent_task_ref must be a non-empty safe identifier."))
    if not isinstance(plan.get("revision"), int) or plan["revision"] < 1:
        failures.append(_finding("collaboration-plan-revision", "revision must be a positive integer."))
    for name in required_lists:
        if not isinstance(plan.get(name), list):
            failures.append(_finding("collaboration-plan-list-missing", f"{name} must be an array."))
    if failures:
        return CollaborationPlanResult("validation_failed", source_file, findings=tuple(failures), next_action={"code": "fix_collaboration_plan_structure", "message": "Fix the required collaboration plan fields."})

    bindings = plan["socket_bindings"]
    work_items = plan["work_items"]
    handoffs = plan["handoffs"]
    reviews = plan["review_gates"]
    if not all(isinstance(item, dict) for group in (bindings, work_items, handoffs, reviews) for item in group):
        return CollaborationPlanResult("validation_failed", source_file, findings=(_finding("collaboration-plan-entry-malformed", "All collaboration plan entries must be objects."),), next_action={"code": "fix_collaboration_plan_entries", "message": "Replace malformed plan entries with objects."})

    sockets_result = list_sockets(root)
    if sockets_result.status != "pass":
        return CollaborationPlanResult("error", source_file, findings=tuple(sockets_result.findings), next_action={"code": "fix_socket_registry", "message": "Fix the shared socket registry before validating a plan."})
    sockets = {socket["socket_id"]: socket for socket in sockets_result.sockets}

    binding_ids, binding_failures = _unique_ids(bindings, "socket_id")
    work_ids, work_failures = _unique_ids(work_items, "work_item_id")
    _, handoff_failures = _unique_ids(reviews, "gate_id")
    failures.extend(binding_failures + work_failures + handoff_failures)
    for entries, allowed_fields in (
        (bindings, _ALLOWED_BINDING_FIELDS),
        (work_items, _ALLOWED_WORK_ITEM_FIELDS),
        (handoffs, _ALLOWED_HANDOFF_FIELDS),
        (reviews, _ALLOWED_REVIEW_FIELDS),
    ):
        if any(set(entry).difference(allowed_fields) for entry in entries):
            failures.append(_finding("collaboration-plan-unsafe-field", "Collaboration plan includes unsupported or unsafe fields."))

    binding_by_socket = {item.get("socket_id"): item for item in bindings if isinstance(item.get("socket_id"), str)}
    for binding in bindings:
        socket_id = binding.get("socket_id")
        capabilities = _string_list(binding.get("required_capabilities"))
        if socket_id not in sockets:
            failures.append(_finding("collaboration-plan-socket-unknown", "Socket binding must reference a declared Agent socket."))
            continue
        if not sockets[socket_id]["enabled"]:
            failures.append(_finding("collaboration-plan-socket-disabled", f"Socket {socket_id} is disabled."))
        if binding.get("role") not in _SAFE_ROLES:
            failures.append(_finding("collaboration-plan-role-invalid", "Socket binding role is not supported."))
        if capabilities is None or not set(capabilities).issubset(sockets[socket_id]["capabilities"]):
            failures.append(_finding("collaboration-plan-capability-mismatch", f"Socket {socket_id} does not declare every required capability."))

    work_by_id = {item.get("work_item_id"): item for item in work_items if isinstance(item.get("work_item_id"), str)}
    for work in work_items:
        socket_id = work.get("socket_id")
        dependencies = _string_list(work.get("depends_on"))
        artifact_types = _string_list(work.get("expected_artifact_types"))
        if socket_id not in binding_ids:
            failures.append(_finding("collaboration-plan-work-socket", "Every work item must use a declared socket binding."))
        elif work.get("role") != binding_by_socket[socket_id].get("role"):
            failures.append(_finding("collaboration-plan-work-role", "Work item role must match its socket binding."))
        if dependencies is None or any(item not in work_ids or item == work.get("work_item_id") for item in dependencies):
            failures.append(_finding("collaboration-plan-dependency-invalid", "Work item dependencies must reference other work items."))
        if artifact_types is None or not artifact_types or not set(artifact_types).issubset(_SAFE_ARTIFACT_TYPES):
            failures.append(_finding("collaboration-plan-artifact-invalid", "Work item must declare supported expected artifact types."))
        if not isinstance(work.get("review_required"), bool):
            failures.append(_finding("collaboration-plan-review-required", "review_required must be boolean."))
    if work_by_id and _has_cycle(work_by_id):
        failures.append(_finding("collaboration-plan-cycle", "Work item dependencies must not contain a cycle."))

    handoff_pairs: set[tuple[str, str]] = set()
    for handoff in handoffs:
        source = handoff.get("from_work_item_id")
        target = handoff.get("to_work_item_id")
        artifact_types = _string_list(handoff.get("artifact_types"))
        if source not in work_ids or target not in work_ids or source == target:
            failures.append(_finding("collaboration-plan-handoff-reference", "Handoff must connect two distinct known work items."))
            continue
        if source not in work_by_id[target].get("depends_on", []):
            failures.append(_finding("collaboration-plan-handoff-dependency", "Handoff target must depend on its source work item."))
        if artifact_types is None or not set(artifact_types).issubset(set(work_by_id[source].get("expected_artifact_types", []))):
            failures.append(_finding("collaboration-plan-handoff-artifact", "Handoff artifacts must be produced by its source work item."))
        pair = (source, target)
        if pair in handoff_pairs:
            failures.append(_finding("collaboration-plan-handoff-duplicate", "Duplicate work-item handoff."))
        handoff_pairs.add(pair)

    review_ids, review_failures = _unique_ids(reviews, "gate_id")
    failures.extend(review_failures)
    review_covered_work_ids: set[str] = set()
    for review in reviews:
        after = _string_list(review.get("after_work_item_ids"))
        options = _string_list(review.get("decision_options"))
        if after is None or not after or any(item not in work_ids for item in after):
            failures.append(_finding("collaboration-plan-review-reference", "Review gate must reference known work items."))
        else:
            review_covered_work_ids.update(after)
        if review.get("review_role") not in _SAFE_ROLES:
            failures.append(_finding("collaboration-plan-review-role", "Review gate role is not supported."))
        if options is None or set(options) != {"approve", "request_changes"}:
            failures.append(_finding("collaboration-plan-review-options", "Review gate options must be approve and request_changes only."))
    for work in work_items:
        if work.get("review_required") is True and work.get("work_item_id") not in review_covered_work_ids:
            failures.append(_finding("collaboration-plan-review-gate-missing", "Every review-required work item must be covered by a review gate."))

    if failures:
        return CollaborationPlanResult("validation_failed", source_file, findings=tuple(failures), next_action={"code": "fix_collaboration_plan", "message": "Resolve the reported plan validation findings."})

    projection = _safe_projection(plan, source_file or plan_file, sockets)
    return CollaborationPlanResult("pass", source_file, projection, next_action={"code": "review_collaboration_plan", "message": "Review this planned graph; no Agent has been contacted."})


def inspect_collaboration_plan(root: Path, plan_file: str) -> CollaborationPlanResult:
    """Return the same validated safe plan projection for board consumers."""
    return validate_collaboration_plan(root, plan_file)
