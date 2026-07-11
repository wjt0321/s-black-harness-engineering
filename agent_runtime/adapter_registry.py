"""Adapter Capability Registry projection for the agent-runtime CLI.

This module projects the existing ``adapters/adapters.sample.json`` registry
into the Stage 10 unified adapter metadata model. It is the read-only,
deterministic backend view used by ``orchestration adapter list/inspect``.

The source of truth remains ``adapters/adapters.sample.json`` (loaded by
``loader.load_adapters``). All Stage 10 fields are either read directly from
that source or deterministically derived/defaulted, and the projection
explicitly records which fields were derived. The projection does not filter
entries by ``enabled``; that decision is left to consumers such as routing.

No external calls, no credential access, no adapter execution.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from jsonschema import validate, ValidationError as JsonSchemaValidationError

from .loader import load_adapters, load_schema
from .result import Finding


ADAPTER_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")

ADAPTER_TYPES = {"agent", "tool", "service"}
RISK_LEVELS = {"local", "external", "destructive", "privileged"}

ADAPTER_SCHEMA_PATH = "adapters/adapter.schema.json"
SOURCE_REGISTRY_PATH = "adapters/adapters.sample.json"

KIND_TO_ADAPTER_TYPE: dict[str, str] = {
    "qwenpaw_agent_api": "agent",
    "acp_runner": "agent",
    "cli_tool": "tool",
    "shell": "tool",
    "github": "tool",
    "webbridge": "tool",
    "manual": "tool",
    "lark": "service",
}

DEFAULT_TIMEOUTS: dict[str, tuple[int, int]] = {
    "agent": (300, 1800),
    "tool": (60, 600),
    "service": (120, 900),
}


def _schema_ref(source_index: int, field: str) -> str:
    """Return a JSON Pointer into the source registry for this entry's schema."""
    return f"{SOURCE_REGISTRY_PATH}#/adapters/{source_index}/{field}"


@dataclass(frozen=True)
class TimeoutProfile:
    """Timeout bounds for an adapter."""

    default_seconds: int
    max_seconds: int

    def to_dict(self) -> dict[str, Any]:
        return {"default_seconds": self.default_seconds, "max_seconds": self.max_seconds}


@dataclass(frozen=True)
class AdapterMetadata:
    """Stage 10 unified capability declaration projected from the registry.

    Fields are either read from ``adapters/adapters.sample.json`` or
    deterministically derived/defaulted. The ``derived`` map records the origin
    of every non-source field.
    """

    adapter_id: str
    display_name: str
    adapter_type: str
    capabilities: list[str] = field(default_factory=list)
    risk_level: str = "external"
    enabled: bool = True
    supports_session: bool = False
    supports_background: bool = False
    supports_approval_roundtrip: bool = False
    supports_artifacts: bool = False
    supports_cancel: bool = False
    timeout_profile: TimeoutProfile = field(default_factory=lambda: TimeoutProfile(60, 300))
    input_schema_ref: str = ""
    output_schema_ref: str = ""
    source_index: int = 0
    derived: dict[str, str] = field(default_factory=dict)

    # Internal routing/preflight fields. Not exported by ``to_dict()``.
    kind: str = ""
    requires_approval: bool = False
    preflight_checks: list[str] = field(default_factory=list)
    input_schema: dict[str, Any] = field(default_factory=dict)
    output_schema: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "adapter_id": self.adapter_id,
            "display_name": self.display_name,
            "adapter_type": self.adapter_type,
            "capabilities": list(self.capabilities),
            "risk_level": self.risk_level,
            "enabled": self.enabled,
            "supports_session": self.supports_session,
            "supports_background": self.supports_background,
            "supports_approval_roundtrip": self.supports_approval_roundtrip,
            "supports_artifacts": self.supports_artifacts,
            "supports_cancel": self.supports_cancel,
            "timeout_profile": self.timeout_profile.to_dict(),
            "input_schema_ref": self.input_schema_ref,
            "output_schema_ref": self.output_schema_ref,
            "source_index": self.source_index,
            "derived": dict(self.derived),
        }


def validate_adapter_metadata(metadata: AdapterMetadata) -> list[str]:
    """Return a list of validation errors; empty if valid."""
    errors: list[str] = []
    if not metadata.adapter_id:
        errors.append("adapter_id is required")
    elif not ADAPTER_ID_PATTERN.match(metadata.adapter_id):
        errors.append(f"adapter_id '{metadata.adapter_id}' does not match {ADAPTER_ID_PATTERN.pattern}")
    if not metadata.display_name:
        errors.append("display_name is required")
    if metadata.adapter_type not in ADAPTER_TYPES:
        errors.append(f"adapter_type '{metadata.adapter_type}' must be one of {sorted(ADAPTER_TYPES)}")
    if metadata.risk_level not in RISK_LEVELS:
        errors.append(f"risk_level '{metadata.risk_level}' must be one of {sorted(RISK_LEVELS)}")
    if not metadata.capabilities:
        errors.append("capabilities must not be empty")
    elif len(metadata.capabilities) != len(set(metadata.capabilities)):
        errors.append("capabilities must be unique")
    if metadata.timeout_profile.default_seconds <= 0:
        errors.append("timeout_profile.default_seconds must be positive")
    if metadata.timeout_profile.max_seconds <= 0:
        errors.append("timeout_profile.max_seconds must be positive")
    if metadata.timeout_profile.default_seconds > metadata.timeout_profile.max_seconds:
        errors.append("timeout_profile.default_seconds must not exceed max_seconds")
    if not metadata.input_schema_ref:
        errors.append("input_schema_ref is required")
    if not metadata.output_schema_ref:
        errors.append("output_schema_ref is required")
    if metadata.source_index < 0:
        errors.append("source_index must be non-negative")
    return errors


def _project_adapter_type(kind: str) -> tuple[str, str]:
    """Map legacy ``kind`` to Stage 10 ``adapter_type``.

    Returns (adapter_type, derivation_note).
    """
    adapter_type = KIND_TO_ADAPTER_TYPE.get(kind)
    if adapter_type is not None:
        return adapter_type, f"mapped from kind '{kind}' -> '{adapter_type}'"
    return "tool", f"unknown kind '{kind}' defaulted to 'tool'"


def _derive_supports_session(adapter_type: str) -> tuple[bool, str]:
    value = adapter_type == "agent"
    return value, f"defaulted to {value} for adapter_type '{adapter_type}'"


def _derive_supports_background(adapter_type: str, capabilities: list[str]) -> tuple[bool, str]:
    value = adapter_type == "agent" and "background_task" in capabilities
    return value, f"derived from adapter_type='{adapter_type}' and 'background_task' in capabilities"


def _derive_supports_approval_roundtrip(
    requires_approval: bool, risk_level: str
) -> tuple[bool, str]:
    value = requires_approval or risk_level in {"external", "destructive", "privileged"}
    return value, f"derived from requires_approval={requires_approval} and risk_level='{risk_level}'"


def _derive_supports_artifacts(adapter_type: str) -> tuple[bool, str]:
    value = adapter_type in {"tool", "service"}
    return value, f"defaulted to {value} for adapter_type '{adapter_type}'"


def _derive_supports_cancel(adapter_type: str, kind: str) -> tuple[bool, str]:
    value = adapter_type == "agent" or kind == "shell"
    return value, f"derived from adapter_type='{adapter_type}' and kind='{kind}'"


def _default_timeout_profile(adapter_type: str) -> tuple[TimeoutProfile, str]:
    default, max_seconds = DEFAULT_TIMEOUTS.get(adapter_type, (60, 600))
    return TimeoutProfile(default, max_seconds), f"defaulted for adapter_type '{adapter_type}'"


def project_adapter(entry: dict[str, Any], source_index: int) -> AdapterMetadata:
    """Project a legacy adapter registry entry into Stage 10 metadata."""
    adapter_id = entry.get("id", "")
    display_name = entry.get("name", "")
    kind = entry.get("kind", "")
    capabilities = list(entry.get("capabilities", []))
    risk_level = entry.get("risk_level", "external")
    enabled = bool(entry.get("enabled", True))
    requires_approval = bool(entry.get("requires_approval", False))

    adapter_type, type_note = _project_adapter_type(kind)
    supports_session, session_note = _derive_supports_session(adapter_type)
    supports_background, background_note = _derive_supports_background(adapter_type, capabilities)
    supports_approval, approval_note = _derive_supports_approval_roundtrip(
        requires_approval, risk_level
    )
    supports_artifacts, artifacts_note = _derive_supports_artifacts(adapter_type)
    supports_cancel, cancel_note = _derive_supports_cancel(adapter_type, kind)
    timeout_profile, timeout_note = _default_timeout_profile(adapter_type)

    input_schema_ref = _schema_ref(source_index, "input_schema")
    output_schema_ref = _schema_ref(source_index, "output_schema")

    preflight_checks = list(entry.get("preflight_checks", []))
    input_schema = dict(entry.get("input_schema", {}))
    output_schema = dict(entry.get("output_schema", {}))

    derived: dict[str, str] = {
        "adapter_type": type_note,
        "supports_session": session_note,
        "supports_background": background_note,
        "supports_approval_roundtrip": approval_note,
        "supports_artifacts": artifacts_note,
        "supports_cancel": cancel_note,
        "timeout_profile": timeout_note,
        "input_schema_ref": f"pointer to {SOURCE_REGISTRY_PATH} entry {source_index} input_schema",
        "output_schema_ref": f"pointer to {SOURCE_REGISTRY_PATH} entry {source_index} output_schema",
    }

    return AdapterMetadata(
        adapter_id=adapter_id,
        display_name=display_name,
        adapter_type=adapter_type,
        capabilities=capabilities,
        risk_level=risk_level,
        enabled=enabled,
        supports_session=supports_session,
        supports_background=supports_background,
        supports_approval_roundtrip=supports_approval,
        supports_artifacts=supports_artifacts,
        supports_cancel=supports_cancel,
        timeout_profile=timeout_profile,
        input_schema_ref=input_schema_ref,
        output_schema_ref=output_schema_ref,
        source_index=source_index,
        derived=derived,
        kind=kind,
        requires_approval=requires_approval,
        preflight_checks=preflight_checks,
        input_schema=input_schema,
        output_schema=output_schema,
    )


class AdapterRegistry:
    """Read-only Stage 10 projection of the legacy adapter registry file."""

    def __init__(self, entries: dict[str, AdapterMetadata]) -> None:
        self._entries = dict(entries)
        self._validate_all()

    def _validate_all(self) -> None:
        for adapter_id, metadata in self._entries.items():
            errors = validate_adapter_metadata(metadata)
            if errors:
                raise ValueError(f"Invalid projected metadata for {adapter_id}: {'; '.join(errors)}")
            if adapter_id != metadata.adapter_id:
                raise ValueError(
                    f"Registry key '{adapter_id}' does not match metadata.adapter_id '{metadata.adapter_id}'"
                )

    def list_adapters(
        self,
        type_filter: str | None = None,
        risk_filter: str | None = None,
        capability_filter: str | None = None,
    ) -> list[AdapterMetadata]:
        """Return a stably sorted list of matching adapters."""
        results = list(self._entries.values())
        if type_filter is not None:
            results = [a for a in results if a.adapter_type == type_filter]
        if risk_filter is not None:
            results = [a for a in results if a.risk_level == risk_filter]
        if capability_filter is not None:
            results = [a for a in results if capability_filter in a.capabilities]
        return sorted(results, key=lambda a: a.adapter_id)

    def get_adapter(self, adapter_id: str) -> AdapterMetadata | None:
        """Return metadata for a single adapter, or None if not found."""
        return self._entries.get(adapter_id)

    def capability_index(self) -> dict[str, list[str]]:
        """Return a mapping from capability to sorted list of adapter_ids."""
        index: dict[str, list[str]] = {}
        for adapter_id, metadata in sorted(self._entries.items()):
            for capability in metadata.capabilities:
                index.setdefault(capability, []).append(adapter_id)
        return index


def load_adapter_registry(
    root: Path,
) -> tuple[AdapterRegistry | None, list[Finding], str | None]:
    """Load and project the adapter registry from the project root.

    Returns ``(registry, findings, next_action)``. On load/validation failure
    ``registry`` is ``None`` and ``findings`` contains a safe, non-secret error
    description. No exceptions are leaked.

    The projection preserves all entries (including disabled ones) so that the
    read model remains aligned with ``loader.load_adapters``.
    """
    try:
        data = load_adapters(root)
    except FileNotFoundError as exc:
        return None, [
            Finding(
                rule_id="adapter-registry-not-found",
                severity="error",
                action="error",
                message=f"Adapter registry not found: {exc}",
            )
        ], "Ensure adapters/adapters.sample.json exists."
    except json.JSONDecodeError as exc:
        return None, [
            Finding(
                rule_id="adapter-registry-invalid-json",
                severity="error",
                action="error",
                message=f"Adapter registry is not valid JSON: {exc}",
            )
        ], "Fix JSON syntax in adapters/adapters.sample.json."
    except OSError as exc:
        return None, [
            Finding(
                rule_id="adapter-registry-read-error",
                severity="error",
                action="error",
                message=f"Could not read adapter registry: {exc}",
            )
        ], "Check file permissions for adapters/adapters.sample.json."

    raw_adapters = data.get("adapters", [])
    if not isinstance(raw_adapters, list):
        return None, [
            Finding(
                rule_id="adapter-registry-malformed",
                severity="error",
                action="error",
                message="Adapter registry 'adapters' field is not a list.",
            )
        ], "Check adapters/adapters.sample.json structure."

    # Optional schema validation when the schema file is present.
    schema_path = root / ADAPTER_SCHEMA_PATH
    if schema_path.is_file():
        try:
            schema = load_schema(root, ADAPTER_SCHEMA_PATH)
            validate(instance=data, schema=schema)
        except (OSError, json.JSONDecodeError) as exc:
            return None, [
                Finding(
                    rule_id="adapter-schema-unreadable",
                    severity="error",
                    action="error",
                    message=f"Could not read adapter schema: {exc}",
                )
            ], f"Check {ADAPTER_SCHEMA_PATH} is readable and valid JSON."
        except JsonSchemaValidationError as exc:
            return None, [
                Finding(
                    rule_id="adapter-registry-schema-failed",
                    severity="error",
                    action="error",
                    message=f"Adapter registry does not match schema: {exc.message}",
                )
            ], "Fix adapters/adapters.sample.json to match adapters/adapter.schema.json."

    projected: dict[str, AdapterMetadata] = {}
    projection_errors: list[str] = []
    for index, entry in enumerate(raw_adapters, start=0):
        if not isinstance(entry, dict):
            projection_errors.append(f"Entry {index} is not an object")
            continue
        try:
            metadata = project_adapter(entry, source_index=index)
        except Exception as exc:  # noqa: BLE001
            projection_errors.append(f"Entry {index}: {exc}")
            continue
        validation_errors = validate_adapter_metadata(metadata)
        if validation_errors:
            projection_errors.append(
                f"Entry {index} ({metadata.adapter_id or '-'}): {'; '.join(validation_errors)}"
            )
            continue
        if metadata.adapter_id in projected:
            projection_errors.append(f"Duplicate adapter_id: {metadata.adapter_id}")
            continue
        projected[metadata.adapter_id] = metadata

    if projection_errors:
        return None, [
            Finding(
                rule_id="adapter-projection-failed",
                severity="error",
                action="error",
                message=f"Could not project adapter metadata: {'; '.join(projection_errors)}",
            )
        ], "Review adapters/adapters.sample.json entries against Stage 10 projection rules."

    try:
        registry = AdapterRegistry(projected)
    except ValueError as exc:
        return None, [
            Finding(
                rule_id="adapter-registry-validation-failed",
                severity="error",
                action="error",
                message=f"Projected registry validation failed: {exc}",
            )
        ], "Review adapters/adapters.sample.json entries."

    return registry, [], "Use orchestration adapter inspect for full metadata."
