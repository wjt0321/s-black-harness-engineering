"""Source-backed Automation Profile read models and requirement checks."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jsonschema import SchemaError as JsonSchemaError
from jsonschema import ValidationError as JsonSchemaValidationError
from jsonschema import validate

from .loader import load_json
from .orchestration_contract_check import ContractCheckResult, check_contract_requirements
from .result import (
    EXIT_BLOCKED,
    EXIT_ERROR,
    EXIT_NEEDS_INPUT,
    EXIT_PASS,
    EXIT_VALIDATION_FAILED,
    Finding,
)

SOURCE_PATH = "automation/automation-profiles.sample.json"
SCHEMA_PATH = "automation/automation-profiles.schema.json"
LIST_SCHEMA_VERSION = "control-plane/automation-profile-list/v1"
DETAIL_SCHEMA_VERSION = "control-plane/automation-profile/v1"
CHECK_SCHEMA_VERSION = "control-plane/automation-profile-check/v1"


@dataclass(frozen=True)
class AutomationProfile:
    """Normalized Automation Profile loaded from the source registry."""

    profile_id: str
    description: str
    required_contracts: tuple[str, ...]
    allow_preview: bool
    max_access: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "description": self.description,
            "required_contracts": list(self.required_contracts),
            "allow_preview": self.allow_preview,
            "max_access": self.max_access,
        }

    def to_summary_dict(self) -> dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "description": self.description,
            "requirement_count": len(self.required_contracts),
            "allow_preview": self.allow_preview,
            "max_access": self.max_access,
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
class AutomationProfileListResult:
    """Result of listing source-backed Automation Profiles."""

    status: str
    profiles: tuple[AutomationProfile, ...] = ()
    findings: tuple[Finding, ...] = ()
    next_action: dict[str, str] | None = None
    schema_version: str = LIST_SCHEMA_VERSION
    source: str = SOURCE_PATH

    def exit_code(self) -> int:
        return _exit_code(self.status)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "status": self.status,
            "schema_version": self.schema_version,
            "source": self.source,
            "summary": {"total_profiles": len(self.profiles)},
            "profiles": [profile.to_summary_dict() for profile in self.profiles],
        }
        if self.findings:
            payload["findings"] = [finding.to_dict() for finding in self.findings]
        if self.next_action is not None:
            payload["next_action"] = self.next_action
        return payload

    def render_human(self) -> str:
        lines = [f"AUTOMATION PROFILES {self.status.upper()}"]
        for profile in self.profiles:
            lines.append(
                f"- {profile.profile_id} requirements={len(profile.required_contracts)} "
                f"allow_preview={str(profile.allow_preview).lower()} "
                f"max_access={profile.max_access}"
            )
        for finding in self.findings:
            lines.append(f"- {finding.rule_id}: {finding.message}")
        if self.next_action is not None:
            lines.append(f"Next: {self.next_action['code']}")
        return "\n".join(lines)


@dataclass(frozen=True)
class AutomationProfileInspectResult:
    """Result of inspecting one Automation Profile."""

    status: str
    profile: AutomationProfile | None = None
    findings: tuple[Finding, ...] = ()
    next_action: dict[str, str] | None = None
    schema_version: str = DETAIL_SCHEMA_VERSION
    source: str = SOURCE_PATH

    def exit_code(self) -> int:
        return _exit_code(self.status)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "status": self.status,
            "schema_version": self.schema_version,
            "source": self.source,
        }
        if self.profile is not None:
            payload["profile"] = self.profile.to_dict()
        if self.findings:
            payload["findings"] = [finding.to_dict() for finding in self.findings]
        if self.next_action is not None:
            payload["next_action"] = self.next_action
        return payload

    def render_human(self) -> str:
        lines = [f"AUTOMATION PROFILE {self.status.upper()}"]
        if self.profile is not None:
            lines.extend(
                [
                    f"profile_id={self.profile.profile_id}",
                    f"allow_preview={str(self.profile.allow_preview).lower()}",
                    f"max_access={self.profile.max_access}",
                    "required_contracts:",
                ]
            )
            lines.extend(f"- {contract_id}" for contract_id in self.profile.required_contracts)
        for finding in self.findings:
            lines.append(f"- {finding.rule_id}: {finding.message}")
        if self.next_action is not None:
            lines.append(f"Next: {self.next_action['code']}")
        return "\n".join(lines)


@dataclass(frozen=True)
class AutomationProfileCheckResult:
    """Result of evaluating one profile through the Requirement Gate."""

    status: str
    profile: AutomationProfile | None = None
    contract_check: ContractCheckResult | None = None
    findings: tuple[Finding, ...] = ()
    next_action: dict[str, str] | None = None
    schema_version: str = CHECK_SCHEMA_VERSION
    source: str = SOURCE_PATH

    def exit_code(self) -> int:
        return _exit_code(self.status)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "status": self.status,
            "schema_version": self.schema_version,
            "source": self.source,
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

    def render_human(self) -> str:
        lines = [f"AUTOMATION PROFILE CHECK {self.status.upper()}"]
        if self.profile is not None:
            lines.append(f"profile_id={self.profile.profile_id}")
        if self.contract_check is not None:
            for requirement in self.contract_check.requirements:
                availability = requirement.availability or "-"
                access = requirement.access or "-"
                lines.append(
                    f"- {requirement.contract_id} {requirement.result} "
                    f"{availability} {access}"
                )
        for finding in self.findings:
            lines.append(f"- {finding.rule_id}: {finding.message}")
        if self.next_action is not None:
            lines.append(f"Next: {self.next_action['code']}")
        return "\n".join(lines)


def _validation_failure(rule_id: str, message: str) -> tuple[None, tuple[Finding, ...], dict[str, str]]:
    return (
        None,
        (
            Finding(
                rule_id=rule_id,
                severity="block",
                action="deny",
                message=message,
            ),
        ),
        {
            "code": "fix_automation_profile_registry",
            "message": "Fix the project Automation Profile registry and retry.",
        },
    )


def _load_profiles(
    root: Path,
) -> tuple[tuple[AutomationProfile, ...] | None, tuple[Finding, ...], dict[str, str] | None]:
    source_path = root / SOURCE_PATH
    schema_path = root / SCHEMA_PATH
    try:
        schema = load_json(schema_path)
        source = load_json(source_path)
    except (OSError, json.JSONDecodeError):
        return _validation_failure(
            "automation-profile-registry-unavailable",
            f"Automation Profile registry or schema is unavailable: {SOURCE_PATH}",
        )

    try:
        validate(instance=source, schema=schema)
    except (JsonSchemaValidationError, JsonSchemaError):
        return _validation_failure(
            "automation-profile-schema-invalid",
            f"Automation Profile registry failed schema validation: {SOURCE_PATH}",
        )

    profiles: list[AutomationProfile] = []
    seen_ids: set[str] = set()
    for raw in source["profiles"]:
        profile_id = raw["profile_id"]
        if profile_id in seen_ids:
            return _validation_failure(
                "duplicate-automation-profile-id",
                f"Automation Profile id is duplicated: {profile_id}",
            )
        seen_ids.add(profile_id)
        profiles.append(
            AutomationProfile(
                profile_id=profile_id,
                description=raw["description"],
                required_contracts=tuple(sorted(set(raw["required_contracts"]))),
                allow_preview=raw["allow_preview"],
                max_access=raw["max_access"],
            )
        )
    return tuple(sorted(profiles, key=lambda profile: profile.profile_id)), (), None


def list_automation_profiles(root: Path) -> AutomationProfileListResult:
    """List normalized profiles from the fixed project registry."""
    profiles, findings, next_action = _load_profiles(root)
    if profiles is None:
        return AutomationProfileListResult(
            status="validation_failed",
            findings=findings,
            next_action=next_action,
        )
    return AutomationProfileListResult(
        status="pass",
        profiles=profiles,
        next_action={
            "code": "inspect_or_check_profile",
            "message": "Inspect or check a profile by profile id.",
        },
    )


def _find_profile(
    root: Path,
    profile_id: str,
) -> tuple[AutomationProfile | None, tuple[Finding, ...], dict[str, str] | None, str]:
    profiles, findings, next_action = _load_profiles(root)
    if profiles is None:
        return None, findings, next_action, "validation_failed"
    for profile in profiles:
        if profile.profile_id == profile_id:
            return profile, (), None, "pass"
    return (
        None,
        (),
        {
            "code": "choose_known_profile",
            "message": "Choose a profile id returned by orchestration profile list.",
        },
        "needs_input",
    )


def inspect_automation_profile(root: Path, profile_id: str) -> AutomationProfileInspectResult:
    """Inspect one profile without evaluating or executing requirements."""
    profile, findings, next_action, status = _find_profile(root, profile_id)
    return AutomationProfileInspectResult(
        status=status,
        profile=profile,
        findings=findings,
        next_action=next_action,
    )


def check_automation_profile(root: Path, profile_id: str) -> AutomationProfileCheckResult:
    """Evaluate one profile by reusing the existing Requirement Gate."""
    profile, findings, next_action, status = _find_profile(root, profile_id)
    if profile is None:
        return AutomationProfileCheckResult(
            status=status,
            findings=findings,
            next_action=next_action,
        )

    contract_check = check_contract_requirements(
        list(profile.required_contracts),
        allow_preview=profile.allow_preview,
        max_access=profile.max_access,
    )
    return AutomationProfileCheckResult(
        status=contract_check.status,
        profile=profile,
        contract_check=contract_check,
        next_action=contract_check.next_action.to_dict(),
    )
