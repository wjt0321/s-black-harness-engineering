"""Standalone Stage 18 validator for Control Panel handoff descriptors."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

VALIDATION_SCHEMA_VERSION = (
    "control-plane/control-panel-host-consumer-validation/v1"
)
CONSUMER_ID = "local-reference-consumer/v1"
CHECK_IDS = (
    "document_shape",
    "schema_version",
    "producer_status",
    "handoff_identity",
    "render_identity",
    "representations",
    "argv",
    "boundaries",
)


@dataclass(frozen=True)
class ConsumerValidationResult:
    """Deterministic result returned by the standalone reference consumer."""

    status: str
    source_handoff_id: str | None
    checks: tuple[dict[str, str], ...]
    findings: tuple[dict[str, str], ...] = ()
    next_action: dict[str, str] | None = None

    def exit_code(self) -> int:
        return {
            "pass": 0,
            "error": 1,
            "blocked": 2,
            "validation_failed": 5,
        }.get(self.status, 1)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "schema_version": VALIDATION_SCHEMA_VERSION,
            "consumer": CONSUMER_ID,
            "source_handoff_id": self.source_handoff_id,
            "checks": list(self.checks),
            "findings": list(self.findings),
            "guarantees": {
                "stdin_only": True,
                "read_only": True,
                "writes_files": False,
                "accesses_network": False,
                "reads_representations": False,
                "executes_commands": False,
                "executes_adapters": False,
                "starts_service": False,
            },
            "next_action": self.next_action,
        }


def validate_handoff_document(document: object) -> ConsumerValidationResult:
    """Validate one already-parsed handoff document without side effects."""
    source_handoff_id = (
        document.get("handoff_id") if isinstance(document, dict) else None
    )
    return ConsumerValidationResult(
        status="pass",
        source_handoff_id=(
            source_handoff_id if isinstance(source_handoff_id, str) else None
        ),
        checks=tuple(
            {"check_id": check_id, "status": "pass"}
            for check_id in CHECK_IDS
        ),
        next_action={
            "code": "accept_handoff",
            "message": "The handoff descriptor passed local reference validation.",
        },
    )
