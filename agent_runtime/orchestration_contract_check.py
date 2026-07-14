"""Read-only requirement gate for the orchestration contract manifest."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .orchestration_contract import build_contract_manifest
from .result import EXIT_BLOCKED, EXIT_NEEDS_INPUT, EXIT_PASS

SCHEMA_VERSION = "control-plane/orchestration-contract-check/v1"
_ACCESS_RANK = {"read_only": 0, "controlled_write": 1}


@dataclass(frozen=True)
class ContractRequirementEvaluation:
    """Evaluation of one requested contract capability."""

    contract_id: str
    result: str
    availability: str | None
    access: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_id": self.contract_id,
            "result": self.result,
            "availability": self.availability,
            "access": self.access,
        }


@dataclass(frozen=True)
class ContractCheckNextAction:
    """Stable machine action for the aggregate requirement decision."""

    code: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message}


@dataclass(frozen=True)
class ContractCheckResult:
    """Deterministic result of checking requirements against the manifest."""

    status: str
    requirements: tuple[ContractRequirementEvaluation, ...]
    allow_preview: bool
    max_access: str
    next_action: ContractCheckNextAction
    schema_version: str = SCHEMA_VERSION

    def exit_code(self) -> int:
        if self.status == "pass":
            return EXIT_PASS
        if self.status == "blocked":
            return EXIT_BLOCKED
        return EXIT_NEEDS_INPUT

    def to_dict(self) -> dict[str, Any]:
        satisfied = sum(item.result == "satisfied" for item in self.requirements)
        return {
            "status": self.status,
            "schema_version": self.schema_version,
            "constraints": {
                "allow_preview": self.allow_preview,
                "max_access": self.max_access,
            },
            "summary": {
                "total_requirements": len(self.requirements),
                "satisfied": satisfied,
                "unsatisfied": len(self.requirements) - satisfied,
            },
            "requirements": [item.to_dict() for item in self.requirements],
            "next_action": self.next_action.to_dict(),
        }

    def render_human(self) -> str:
        lines = [f"CONTRACT CHECK {self.status.upper()}"]
        lines.append(
            f"constraints: allow_preview={str(self.allow_preview).lower()} "
            f"max_access={self.max_access}"
        )
        for item in self.requirements:
            availability = item.availability or "-"
            access = item.access or "-"
            lines.append(
                f"- {item.contract_id} {item.result} {availability} {access}"
            )
        lines.append(f"Next: {self.next_action.code}")
        return "\n".join(lines)


def _evaluate_requirement(
    contract_id: str,
    *,
    entries_by_id: dict[str, Any],
    allow_preview: bool,
    max_access: str,
) -> ContractRequirementEvaluation:
    entry = entries_by_id.get(contract_id)
    if entry is None:
        return ContractRequirementEvaluation(
            contract_id=contract_id,
            result="unknown",
            availability=None,
            access=None,
        )
    if entry.availability == "unavailable":
        return ContractRequirementEvaluation(
            contract_id=contract_id,
            result="unavailable",
            availability=entry.availability,
            access=entry.access,
        )
    if entry.availability == "preview" and not allow_preview:
        return ContractRequirementEvaluation(
            contract_id=contract_id,
            result="preview_not_allowed",
            availability=entry.availability,
            access=entry.access,
        )
    if _ACCESS_RANK[entry.access] > _ACCESS_RANK[max_access]:
        return ContractRequirementEvaluation(
            contract_id=contract_id,
            result="access_exceeded",
            availability=entry.availability,
            access=entry.access,
        )
    return ContractRequirementEvaluation(
        contract_id=contract_id,
        result="satisfied",
        availability=entry.availability,
        access=entry.access,
    )


def _resolve_status_and_next_action(
    requirements: tuple[ContractRequirementEvaluation, ...],
) -> tuple[str, ContractCheckNextAction]:
    if not requirements:
        return (
            "needs_input",
            ContractCheckNextAction(
                code="provide_requirements",
                message="Provide at least one contract id to evaluate.",
            ),
        )
    results = {item.result for item in requirements}
    if "unavailable" in results:
        return (
            "blocked",
            ContractCheckNextAction(
                code="choose_available_contract",
                message="Replace unavailable requirements with implemented contract ids.",
            ),
        )
    if "access_exceeded" in results:
        return (
            "blocked",
            ContractCheckNextAction(
                code="raise_max_access_or_choose_read_only",
                message="Raise the access ceiling explicitly or choose read-only requirements.",
            ),
        )
    if "unknown" in results:
        return (
            "needs_input",
            ContractCheckNextAction(
                code="provide_known_contract_ids",
                message="Use contract ids returned by orchestration contract inspect.",
            ),
        )
    if "preview_not_allowed" in results:
        return (
            "needs_input",
            ContractCheckNextAction(
                code="allow_preview_or_choose_stable",
                message="Pass --allow-preview explicitly or choose stable requirements.",
            ),
        )
    return (
        "pass",
        ContractCheckNextAction(
            code="requirements_satisfied",
            message="All requested contract capabilities satisfy the declared constraints.",
        ),
    )


def check_contract_requirements(
    required_contract_ids: list[str],
    *,
    allow_preview: bool = False,
    max_access: str = "controlled_write",
) -> ContractCheckResult:
    """Evaluate normalized contract requirements without reading or writing files."""
    manifest = build_contract_manifest()
    entries_by_id = {entry.contract_id: entry for entry in manifest.entries}
    requirements = tuple(
        _evaluate_requirement(
            contract_id,
            entries_by_id=entries_by_id,
            allow_preview=allow_preview,
            max_access=max_access,
        )
        for contract_id in sorted(set(required_contract_ids))
    )
    status, next_action = _resolve_status_and_next_action(requirements)
    return ContractCheckResult(
        status=status,
        requirements=requirements,
        allow_preview=allow_preview,
        max_access=max_access,
        next_action=next_action,
    )
