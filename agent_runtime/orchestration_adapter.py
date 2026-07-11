"""Read-only orchestration adapter capability views for the agent-runtime CLI.

This module projects the existing ``adapters/adapters.sample.json`` registry
into the Stage 10 unified adapter metadata read model. The source of truth is
``adapters/adapters.sample.json``; this module only adds a deterministic,
validated projection layer.

No writes, no adapter execution, no network access, no credential access.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .adapter_registry import AdapterMetadata, load_adapter_registry
from .result import Finding


@dataclass
class AdapterListResult:
    """Result of an orchestration adapter capability list."""

    status: str = "pass"
    adapters: list[dict[str, Any]] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    next_action: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"status": self.status, "adapters": self.adapters}
        if self.findings:
            d["findings"] = [f.to_dict() for f in self.findings]
        if self.next_action is not None:
            d["next_action"] = self.next_action
        return d


@dataclass
class AdapterDetailResult:
    """Result of an orchestration adapter capability inspect."""

    status: str = "pass"
    adapter: dict[str, Any] | None = None
    findings: list[Finding] = field(default_factory=list)
    next_action: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"status": self.status}
        if self.adapter is not None:
            d["adapter"] = self.adapter
        if self.findings:
            d["findings"] = [f.to_dict() for f in self.findings]
        if self.next_action is not None:
            d["next_action"] = self.next_action
        return d


def _build_summary(metadata: AdapterMetadata) -> dict[str, Any]:
    """Return a compact summary for list views."""
    return {
        "adapter_id": metadata.adapter_id,
        "display_name": metadata.display_name,
        "adapter_type": metadata.adapter_type,
        "risk_level": metadata.risk_level,
        "enabled": metadata.enabled,
        "capability_count": len(metadata.capabilities),
        "supports_session": metadata.supports_session,
        "supports_background": metadata.supports_background,
        "supports_approval_roundtrip": metadata.supports_approval_roundtrip,
        "supports_artifacts": metadata.supports_artifacts,
        "supports_cancel": metadata.supports_cancel,
    }


def list_adapters(
    root: Path,
    type_filter: str | None = None,
    risk_filter: str | None = None,
    capability_filter: str | None = None,
) -> AdapterListResult:
    """List adapters from the projected capability registry.

    Loads ``adapters/adapters.sample.json`` from ``root`` and returns a stable,
    filtered projection. All load/projection/validation errors are returned as
    ``error`` status with safe findings rather than raised.
    """
    registry, findings, next_action = load_adapter_registry(root)
    if registry is None:
        return AdapterListResult(
            status="error",
            findings=findings,
            next_action=next_action,
        )

    adapters = registry.list_adapters(
        type_filter=type_filter,
        risk_filter=risk_filter,
        capability_filter=capability_filter,
    )
    return AdapterListResult(
        status="pass",
        adapters=[_build_summary(a) for a in adapters],
        next_action="Use orchestration adapter inspect for full metadata.",
    )


def get_adapter(
    root: Path,
    adapter_id: str,
) -> AdapterDetailResult:
    """Inspect a single adapter from the projected capability registry."""
    registry, findings, next_action = load_adapter_registry(root)
    if registry is None:
        return AdapterDetailResult(
            status="error",
            findings=findings,
            next_action=next_action,
        )

    metadata = registry.get_adapter(adapter_id)
    if metadata is None:
        return AdapterDetailResult(
            status="needs_input",
            findings=[
                Finding(
                    rule_id="adapter-not-found",
                    severity="warn",
                    action="needs_input",
                    message=f"Adapter not found: {adapter_id}",
                )
            ],
            next_action=f"Adapter not found: {adapter_id}. Use orchestration adapter list to see available adapters.",
        )
    return AdapterDetailResult(
        status="pass",
        adapter=metadata.to_dict(),
        next_action="Use orchestration route preview to check capability routing.",
    )
