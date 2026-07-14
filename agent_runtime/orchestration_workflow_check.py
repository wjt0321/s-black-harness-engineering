"""Read-only re-check and drift validation for Automation Workflow Plans."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .orchestration_workflow import (
    AutomationWorkflowPlanResult,
    build_automation_workflow_plan,
)
from .result import (
    EXIT_BLOCKED,
    EXIT_ERROR,
    EXIT_NEEDS_INPUT,
    EXIT_PASS,
    EXIT_VALIDATION_FAILED,
    Finding,
)

SCHEMA_VERSION = "control-plane/automation-workflow-check/v1"
_PLAN_ID_PATTERN = re.compile(r"sha256:[a-f0-9]{64}")


def _exit_code(status: str) -> int:
    if status == "pass":
        return EXIT_PASS
    if status == "blocked":
        return EXIT_BLOCKED
    if status == "needs_input":
        return EXIT_NEEDS_INPUT
    if status == "validation_failed":
        return EXIT_VALIDATION_FAILED
    return EXIT_ERROR


@dataclass(frozen=True)
class AutomationWorkflowCheckResult:
    """Comparison between an expected plan id and the current projection."""

    status: str
    requested_profile_id: str
    expected_plan_id: str | None = None
    current_plan: AutomationWorkflowPlanResult | None = None
    matches_current: bool | None = None
    findings: tuple[Finding, ...] = ()
    next_action: dict[str, str] | None = None
    schema_version: str = SCHEMA_VERSION

    def exit_code(self) -> int:
        return _exit_code(self.status)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "status": self.status,
            "schema_version": self.schema_version,
            "requested_profile_id": self.requested_profile_id,
            "guarantees": {
                "deterministic": True,
                "read_only": True,
                "writes_files": False,
                "writes_ledgers": False,
                "accesses_network": False,
                "executes_commands": False,
                "executes_adapters": False,
            },
        }
        if self.expected_plan_id is not None:
            payload["expected_plan_id"] = self.expected_plan_id
        if self.current_plan is not None:
            current_payload = self.current_plan.to_dict()
            payload["current_plan"] = current_payload
            if self.matches_current is not None:
                payload["current_plan_id"] = current_payload["plan_id"]
                payload["matches_current"] = self.matches_current
                payload["drift"] = {
                    "detected": not self.matches_current,
                    "comparison_basis": "canonical_workflow_plan_projection",
                    "cause": (
                        "none"
                        if self.matches_current
                        else "content_hash_mismatch"
                    ),
                    "field_level_diff_available": False,
                }
        if self.findings:
            payload["findings"] = [finding.to_dict() for finding in self.findings]
        if self.next_action is not None:
            payload["next_action"] = self.next_action
        return payload

    def render_human(self) -> str:
        lines = [f"AUTOMATION WORKFLOW CHECK {self.status.upper()}"]
        lines.append(f"profile_id={self.requested_profile_id}")
        if self.expected_plan_id is not None:
            lines.append(f"expected_plan_id={self.expected_plan_id}")
        if self.current_plan is not None and self.matches_current is not None:
            current_plan_id = self.current_plan.to_dict()["plan_id"]
            lines.append(f"current_plan_id={current_plan_id}")
            lines.append(
                f"matches_current={str(self.matches_current).lower()}"
            )
        for finding in self.findings:
            lines.append(f"- {finding.rule_id}: {finding.message}")
        if self.next_action is not None:
            lines.append(f"Next: {self.next_action['code']}")
        return "\n".join(lines)


def check_automation_workflow_plan(
    root: Path,
    profile_id: str,
    expected_plan_id: str,
) -> AutomationWorkflowCheckResult:
    """Re-project one profile and compare its safe content-addressed plan id."""
    if _PLAN_ID_PATTERN.fullmatch(expected_plan_id) is None:
        return AutomationWorkflowCheckResult(
            status="needs_input",
            requested_profile_id=profile_id,
            findings=(
                Finding(
                    rule_id="invalid-automation-workflow-plan-id",
                    severity="warn",
                    action="request_input",
                    message=(
                        "Expected workflow plan id must use "
                        "sha256:<64 lowercase hexadecimal characters>."
                    ),
                ),
            ),
            next_action={
                "code": "provide_valid_workflow_plan_id",
                "message": "Provide a valid workflow plan id and retry.",
            },
        )

    current_plan = build_automation_workflow_plan(root, profile_id)
    if current_plan.status != "pass":
        return AutomationWorkflowCheckResult(
            status=current_plan.status,
            requested_profile_id=profile_id,
            expected_plan_id=expected_plan_id,
            current_plan=(
                current_plan
                if current_plan.profile is not None or current_plan.findings
                else None
            ),
            findings=current_plan.findings,
            next_action=current_plan.next_action,
        )

    current_plan_id = current_plan.to_dict()["plan_id"]
    if current_plan_id != expected_plan_id:
        return AutomationWorkflowCheckResult(
            status="blocked",
            requested_profile_id=profile_id,
            expected_plan_id=expected_plan_id,
            current_plan=current_plan,
            matches_current=False,
            findings=(
                Finding(
                    rule_id="automation-workflow-plan-drift",
                    severity="block",
                    action="deny",
                    message=(
                        "The current workflow plan projection does not match "
                        "the previously reviewed plan id."
                    ),
                ),
            ),
            next_action={
                "code": "regenerate_and_review_workflow_plan",
                "message": "Regenerate and review the current workflow plan projection.",
            },
        )

    return AutomationWorkflowCheckResult(
        status="pass",
        requested_profile_id=profile_id,
        expected_plan_id=expected_plan_id,
        current_plan=current_plan,
        matches_current=True,
        next_action={
            "code": "workflow_plan_current",
            "message": "The reviewed workflow plan id matches the current projection.",
        },
    )
