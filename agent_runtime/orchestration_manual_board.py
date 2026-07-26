"""Validated read model for an operator-authored collaboration board fixture."""

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

SCHEMA_VERSION = "control-plane/manual-collaboration-board/v1"
BOARD_SCHEMA = "adapters/manual-collaboration-board.schema.json"
_MAX_BYTES = 128 * 1024


def _finding(rule_id: str, message: str) -> Finding:
    return Finding(rule_id=rule_id, severity="block", action="deny", message=message)


def _load_project_json(root: Path, relative: str) -> tuple[dict[str, Any] | None, str | None, Finding | None]:
    base = root.resolve()
    path = (base / relative).resolve()
    if path == base or base not in path.parents:
        return None, None, _finding("manual-board-path-escape", "Manual board file must remain inside the project root.")
    if path.suffix.lower() != ".json":
        return None, None, _finding("manual-board-file-type", "Manual board file must use the .json extension.")
    try:
        if not path.is_file() or path.stat().st_size > _MAX_BYTES:
            return None, None, _finding("manual-board-unavailable", "Manual board file is missing or exceeds the read limit.")
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None, None, _finding("manual-board-unreadable", "Manual board must be readable UTF-8 JSON.")
    if not isinstance(value, dict):
        return None, None, _finding("manual-board-malformed", "Manual board must be a JSON object.")
    return value, normalize_path(path.relative_to(base)), None


@dataclass(frozen=True)
class ManualBoardResult:
    status: str
    source_file: str | None = None
    board: dict[str, Any] | None = None
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
                "planning_mode": "manual",
                "operator_authored": True,
                "deterministic": True,
                "read_only": True,
                "fixture_backed": True,
                "executes_agents": False,
                "writes_files": False,
                "writes_ledgers": False,
                "accesses_network": False,
            },
        }
        if self.source_file:
            payload["source"] = {"manual_board_file": self.source_file}
        if self.board:
            payload["board"] = self.board
        if self.findings:
            payload["findings"] = [item.to_dict() for item in self.findings]
        payload["next_action"] = {
            "code": "review_manual_board" if self.status == "pass" else "fix_manual_board",
            "message": "Review the operator-authored fixture; no Agent work has been executed.",
        }
        return payload


def inspect_manual_board(root: Path, board_file: str) -> ManualBoardResult:
    """Validate and project one operator-authored fixture without executing it."""
    data, source, failure = _load_project_json(root, board_file)
    if failure is not None or data is None:
        return ManualBoardResult("validation_failed", source, findings=(failure,) if failure else ())
    try:
        schema = json.loads((root / BOARD_SCHEMA).read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        validate(data, schema)
    except (OSError, json.JSONDecodeError, SchemaError, ValidationError):
        return ManualBoardResult(
            "validation_failed", source,
            findings=(_finding("manual-board-schema-invalid", "Manual board or schema validation failed."),),
        )

    plan_result = inspect_collaboration_plan(root, data["collaboration_file"])
    if plan_result.status != "pass" or plan_result.plan is None:
        return ManualBoardResult(
            "validation_failed", source,
            findings=(_finding("manual-board-plan-invalid", "Referenced collaboration plan is not valid."),),
        )
    plan = plan_result.to_dict()["plan"]
    work_by_id = {item["work_item_id"]: item for item in plan["work_items"]}
    state_by_id = {item["work_item_id"]: item for item in data["work_item_states"]}
    findings: list[Finding] = []
    if len(state_by_id) != len(data["work_item_states"]):
        findings.append(_finding("manual-board-work-item-duplicate", "Manual board work item states must use unique work_item_id values."))
    if set(state_by_id) != set(work_by_id):
        findings.append(_finding("manual-board-work-items-mismatch", "Manual board must define one state for every planned work item."))
    for work_id, state in state_by_id.items():
        work = work_by_id.get(work_id)
        if work is None:
            continue
        if not set(state["artifact_types"]).issubset(work["expected_artifact_types"]):
            findings.append(_finding("manual-board-artifact-mismatch", "Fixture artifacts must match the planned work item contract."))
        expected_review = work["review_required"]
        if expected_review and state["review_state"] == "not_required":
            findings.append(_finding("manual-board-review-mismatch", "Review-required work cannot use not_required review state."))
        if not expected_review and state["review_state"] not in {"not_required", "pending"}:
            findings.append(_finding("manual-board-review-mismatch", "Non-review work cannot claim an approval decision."))

    sequences = [item["sequence"] for item in data["timeline"]]
    if sequences != list(range(1, len(sequences) + 1)):
        findings.append(_finding("manual-board-timeline-sequence", "Timeline sequence must be contiguous and start at 1."))
    for event in data["timeline"]:
        work = work_by_id.get(event["work_item_id"])
        if work is None:
            findings.append(_finding("manual-board-timeline-work", "Timeline events must reference planned work items."))
        elif event["event_type"] == "artifact_produced" and not set(event["artifact_types"]).issubset(work["expected_artifact_types"]):
            findings.append(_finding("manual-board-timeline-artifact", "Produced fixture artifacts must match the work item contract."))
    if findings:
        return ManualBoardResult("validation_failed", source, findings=tuple(findings))

    lanes = []
    for state in data["work_item_states"]:
        work = work_by_id[state["work_item_id"]]
        lanes.append({
            "work_item_id": work["work_item_id"],
            "socket_id": work["socket_id"],
            "role": work["role"],
            "depends_on": work["depends_on"],
            "expected_artifact_types": work["expected_artifact_types"],
            "status": state["status"],
            "artifact_types": state["artifact_types"],
            "review_state": state["review_state"],
            "execution": "simulated",
        })
    board_body = {
        "planning_mode": "manual",
        "planned_by": "operator",
        "collaboration_plan_id": plan["plan_id"],
        "parent_task_ref": plan["parent_task_ref"],
        "board_state": data["board_state"],
        "lanes": lanes,
        "timeline": data["timeline"],
        "operator_actions": [
            {"action": action, "mode": "simulated", "enabled": False}
            for action in data["operator_actions"]
        ],
        "summary": {
            "lane_count": len(lanes),
            "timeline_event_count": len(data["timeline"]),
            "simulated_complete_count": sum(item["status"] == "simulated_complete" for item in lanes),
        },
    }
    canonical = json.dumps(board_body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    board = {**board_body, "board_id": f"sha256:{hashlib.sha256(canonical).hexdigest()}"}
    return ManualBoardResult("pass", source, board)
