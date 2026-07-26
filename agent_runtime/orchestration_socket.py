"""Read-only Agent Socket Registry projections for the orchestration control plane.

A socket is the control-plane view of an agent-capable adapter.  It deliberately
reports declared registry state, not live process/session health: discovery must
not start external agents, consume model quota, read credentials, or probe networks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .adapter_registry import AdapterMetadata, load_adapter_registry
from .result import Finding


@dataclass
class SocketListResult:
    """Stable read-only summary of declared Agent sockets."""

    status: str = "pass"
    sockets: list[dict[str, Any]] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    next_action: str | None = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"status": self.status, "sockets": self.sockets}
        if self.findings:
            result["findings"] = [finding.to_dict() for finding in self.findings]
        if self.next_action is not None:
            result["next_action"] = self.next_action
        return result


@dataclass
class SocketDetailResult:
    """Stable read-only detail for one declared Agent socket."""

    status: str = "pass"
    socket: dict[str, Any] | None = None
    findings: list[Finding] = field(default_factory=list)
    next_action: str | None = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"status": self.status}
        if self.socket is not None:
            result["socket"] = self.socket
        if self.findings:
            result["findings"] = [finding.to_dict() for finding in self.findings]
        if self.next_action is not None:
            result["next_action"] = self.next_action
        return result


def _invocation_mode(metadata: AdapterMetadata) -> str:
    if metadata.kind == "acp_runner":
        return "acp_delegate"
    if metadata.kind == "pi_cli":
        return "local_cli"
    return "agent_api"


def _project_socket(metadata: AdapterMetadata) -> dict[str, Any]:
    """Project one agent adapter without inspecting its live runtime."""
    return {
        "socket_id": metadata.adapter_id,
        "display_name": metadata.display_name,
        "adapter_id": metadata.adapter_id,
        "invocation_mode": _invocation_mode(metadata),
        "capabilities": list(metadata.capabilities),
        "risk_level": metadata.risk_level,
        "enabled": metadata.enabled,
        "availability": "declared" if metadata.enabled else "disabled",
        "availability_detail": (
            "Declared from the local registry; no process, session, network, "
            "or quota probe was performed."
        ),
        "supports_session": metadata.supports_session,
        "supports_background": metadata.supports_background,
        "supports_cancel": metadata.supports_cancel,
        "requires_approval": metadata.requires_approval,
    }


def _load_agent_sockets(root: Path) -> tuple[list[dict[str, Any]] | None, list[Finding], str | None]:
    registry, findings, next_action = load_adapter_registry(root)
    if registry is None:
        return None, findings, next_action
    sockets = [
        _project_socket(metadata)
        for metadata in registry.list_adapters(type_filter="agent")
    ]
    return sockets, [], None


def list_sockets(root: Path, capability_filter: str | None = None) -> SocketListResult:
    """List declared Agent sockets from the shared adapter registry."""
    sockets, findings, next_action = _load_agent_sockets(root)
    if sockets is None:
        return SocketListResult(status="error", findings=findings, next_action=next_action)
    if capability_filter is not None:
        sockets = [socket for socket in sockets if capability_filter in socket["capabilities"]]
    return SocketListResult(
        sockets=sockets,
        next_action=(
            "Use orchestration socket inspect <socket_id> for its declared "
            "capabilities and invocation boundary."
        ),
    )


def get_socket(root: Path, socket_id: str) -> SocketDetailResult:
    """Inspect one declared Agent socket without live runtime probing."""
    sockets, findings, next_action = _load_agent_sockets(root)
    if sockets is None:
        return SocketDetailResult(status="error", findings=findings, next_action=next_action)
    for socket in sockets:
        if socket["socket_id"] == socket_id:
            return SocketDetailResult(
                socket=socket,
                next_action=(
                    "Use orchestration route preview with a declared capability; "
                    "this socket view does not execute or contact the agent."
                ),
            )
    return SocketDetailResult(
        status="needs_input",
        findings=[
            Finding(
                rule_id="socket-not-found",
                severity="warn",
                action="needs_input",
                message=(
                    f"Agent socket not found: {socket_id}. Only agent-capable "
                    "adapters are sockets."
                ),
            )
        ],
        next_action="Use orchestration socket list to see declared Agent sockets.",
    )
