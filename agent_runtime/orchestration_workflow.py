"""Deterministic, read-only workflow plans projected from Automation Profiles."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .orchestration_contract import OrchestrationContractEntry, build_contract_manifest
from .orchestration_contract_check import ContractCheckResult
from .orchestration_profile import AutomationProfile, check_automation_profile
from .result import (
    EXIT_BLOCKED,
    EXIT_ERROR,
    EXIT_NEEDS_INPUT,
    EXIT_PASS,
    EXIT_VALIDATION_FAILED,
    Finding,
)

SCHEMA_VERSION = "control-plane/automation-workflow-plan/v1"

_PHASE_ORDER = (
    "discovery",
    "inspect",
    "decide",
    "prepare",
    "controlled_write",
    "observe",
    "capability",
)
_PHASE_BY_CONTRACT = {
    "contract_discovery": "discovery",
    "contract_requirement_gate": "discovery",
    "automation_profile_read": "discovery",
    "automation_profile_check": "discovery",
    "automation_workflow_plan": "discovery",
    "adapter_registry": "inspect",
    "task_read": "inspect",
    "routing_preflight": "decide",
    "routing_preflight_snapshot": "decide",
    "run_plan": "prepare",
    "read_loop_snapshot": "prepare",
    "task_submit": "controlled_write",
    "run_commit": "controlled_write",
    "approval_resolve": "controlled_write",
    "overview": "observe",
    "run_read": "observe",
    "artifact_read": "observe",
    "report_generate": "observe",
}


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
class AutomationWorkflowStep:
    """One unexecuted candidate step derived from a contract manifest entry."""

    phase: str
    entry: OrchestrationContractEntry

    @property
    def step_id(self) -> str:
        return f"{self.phase}:{self.entry.contract_id}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "phase": self.phase,
            "contract_id": self.entry.contract_id,
            "availability": self.entry.availability,
            "access": self.entry.access,
            "boundary": self.entry.boundary,
            "candidate_commands": [list(command) for command in self.entry.commands],
            "required_flags": list(self.entry.key_flags),
            "status": "planned",
            "execution": "not_executed",
        }


@dataclass(frozen=True)
class AutomationWorkflowPlanResult:
    """Ephemeral workflow plan projection with a content-addressed identifier."""

    status: str
    requested_profile_id: str
    profile: AutomationProfile | None = None
    contract_check: ContractCheckResult | None = None
    steps: tuple[AutomationWorkflowStep, ...] = ()
    findings: tuple[Finding, ...] = ()
    next_action: dict[str, str] | None = None
    schema_version: str = SCHEMA_VERSION

    def exit_code(self) -> int:
        return _exit_code(self.status)

    def _payload_without_id(self) -> dict[str, Any]:
        phase_counts = {phase: 0 for phase in _PHASE_ORDER}
        for step in self.steps:
            phase_counts[step.phase] += 1

        payload: dict[str, Any] = {
            "status": self.status,
            "schema_version": self.schema_version,
            "requested_profile_id": self.requested_profile_id,
            "summary": {
                "total_steps": len(self.steps),
                "phase_counts": phase_counts,
                "preview_steps": sum(
                    step.entry.availability == "preview" for step in self.steps
                ),
                "controlled_write_steps": sum(
                    step.entry.access == "controlled_write" for step in self.steps
                ),
            },
            "steps": [step.to_dict() for step in self.steps],
            "guarantees": {
                "deterministic": True,
                "ephemeral": True,
                "writes_files": False,
                "writes_ledgers": False,
                "accesses_network": False,
                "executes_commands": False,
                "executes_adapters": False,
            },
        }
        if self.profile is not None:
            payload["profile"] = self.profile.to_dict()
        if self.contract_check is not None:
            payload["contract_check"] = self.contract_check.to_dict()
        if self.findings:
            payload["findings"] = [finding.to_dict() for finding in self.findings]
        if self.next_action is not None:
            payload["next_action"] = self.next_action
        return payload

    def to_dict(self) -> dict[str, Any]:
        payload = self._payload_without_id()
        canonical = json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        return {
            **payload,
            "plan_id": f"sha256:{hashlib.sha256(canonical).hexdigest()}",
        }

    def render_human(self) -> str:
        payload = self.to_dict()
        lines = [f"AUTOMATION WORKFLOW PLAN {self.status.upper()}"]
        lines.append(f"profile_id={self.requested_profile_id}")
        lines.append(f"plan_id={payload['plan_id']}")
        lines.append(f"total_steps={len(self.steps)}")
        for step in self.steps:
            commands = " | ".join(" ".join(command) for command in step.entry.commands)
            lines.append(
                f"- {step.step_id} {step.entry.availability} {step.entry.access} "
                f"execution=not_executed commands={commands}"
            )
        for finding in self.findings:
            lines.append(f"- {finding.rule_id}: {finding.message}")
        if self.next_action is not None:
            lines.append(f"Next: {self.next_action['code']}")
        return "\n".join(lines)


def build_automation_workflow_plan(
    root: Path,
    profile_id: str,
) -> AutomationWorkflowPlanResult:
    """Project a checked Automation Profile into ordered, unexecuted CLI steps."""
    profile_check = check_automation_profile(root, profile_id)
    if profile_check.status != "pass" or profile_check.profile is None:
        return AutomationWorkflowPlanResult(
            status=profile_check.status,
            requested_profile_id=profile_id,
            profile=profile_check.profile,
            contract_check=profile_check.contract_check,
            findings=profile_check.findings,
            next_action=profile_check.next_action,
        )

    entries_by_id = {
        entry.contract_id: entry for entry in build_contract_manifest().entries
    }
    phase_rank = {phase: index for index, phase in enumerate(_PHASE_ORDER)}
    steps = tuple(
        sorted(
            (
                AutomationWorkflowStep(
                    phase=_PHASE_BY_CONTRACT.get(contract_id, "capability"),
                    entry=entries_by_id[contract_id],
                )
                for contract_id in profile_check.profile.required_contracts
            ),
            key=lambda step: (phase_rank[step.phase], step.entry.contract_id),
        )
    )
    return AutomationWorkflowPlanResult(
        status="pass",
        requested_profile_id=profile_id,
        profile=profile_check.profile,
        contract_check=profile_check.contract_check,
        steps=steps,
        next_action={
            "code": "review_workflow_plan",
            "message": "Review the projected steps; no command has been executed.",
        },
    )
