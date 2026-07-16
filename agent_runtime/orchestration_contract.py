"""Machine-readable discovery contract for orchestration CLI automation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

SCHEMA_VERSION = "control-plane/orchestration-contract/v1"


@dataclass(frozen=True)
class OrchestrationContractEntry:
    """One stable, limited, preview, or unavailable orchestration capability."""

    contract_id: str
    availability: str
    access: str
    commands: tuple[tuple[str, ...], ...]
    key_flags: tuple[str, ...]
    boundary: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_id": self.contract_id,
            "availability": self.availability,
            "access": self.access,
            "commands": [list(command) for command in self.commands],
            "key_flags": list(self.key_flags),
            "boundary": self.boundary,
        }


@dataclass(frozen=True)
class OrchestrationContractManifest:
    """Versioned, deterministic contract manifest for local CLI consumers."""

    entries: tuple[OrchestrationContractEntry, ...]
    status: str = "pass"
    schema_version: str = SCHEMA_VERSION
    consumer: str = "cli-automation"

    def to_dict(self) -> dict[str, Any]:
        availability_order = ("stable", "stable_limited", "preview", "unavailable")
        summary = {name: 0 for name in availability_order}
        for entry in self.entries:
            summary[entry.availability] += 1

        return {
            "status": self.status,
            "schema_version": self.schema_version,
            "consumer": self.consumer,
            "summary": {
                "total_entries": len(self.entries),
                **summary,
            },
            "entries": [entry.to_dict() for entry in self.entries],
            "guarantees": {
                "deterministic": True,
                "read_only_discovery": True,
                "writes_files": False,
                "accesses_network": False,
                "executes_adapters": False,
            },
        }


def _entry(
    contract_id: str,
    availability: str,
    access: str,
    *,
    commands: tuple[tuple[str, ...], ...] = (),
    key_flags: tuple[str, ...] = (),
    boundary: str,
) -> OrchestrationContractEntry:
    """Normalize one source entry so the public manifest stays deterministic."""
    return OrchestrationContractEntry(
        contract_id=contract_id,
        availability=availability,
        access=access,
        commands=tuple(sorted(commands)),
        key_flags=tuple(sorted(key_flags)),
        boundary=boundary,
    )


def build_contract_manifest() -> OrchestrationContractManifest:
    """Build the frozen v1 orchestration capability manifest without I/O."""
    entries = (
        _entry(
            "adapter_registry",
            "stable",
            "read_only",
            commands=(
                ("orchestration", "adapter", "inspect"),
                ("orchestration", "adapter", "list"),
            ),
            boundary="Source-backed metadata only; online availability is not probed.",
        ),
        _entry(
            "approval_read",
            "stable_limited",
            "read_only",
            commands=(
                ("orchestration", "approval", "get"),
                ("orchestration", "approval", "list"),
            ),
            boundary="Envelope-scoped approval projection; no independent approval store.",
        ),
        _entry(
            "approval_resolve",
            "stable_limited",
            "controlled_write",
            commands=(("orchestration", "approval", "resolve"),),
            key_flags=("--commit",),
            boundary="Records a decision only and never executes the original request.",
        ),
        _entry(
            "artifact_read",
            "stable_limited",
            "read_only",
            commands=(
                ("orchestration", "artifact", "get"),
                ("orchestration", "artifact", "list"),
            ),
            boundary="Reads safe envelope metadata; no independent artifact store.",
        ),
        _entry(
            "automation_profile_check",
            "stable",
            "read_only",
            commands=(("orchestration", "profile", "check"),),
            key_flags=("--profile-id",),
            boundary="Evaluates a fixed project profile without executing requirements.",
        ),
        _entry(
            "automation_profile_read",
            "stable",
            "read_only",
            commands=(
                ("orchestration", "profile", "inspect"),
                ("orchestration", "profile", "list"),
            ),
            key_flags=("--profile-id",),
            boundary="Reads the fixed project Automation Profile registry only.",
        ),
        _entry(
            "automation_workflow_check",
            "preview",
            "read_only",
            commands=(("orchestration", "workflow", "check"),),
            key_flags=("--expected-plan-id", "--profile-id"),
            boundary="Re-projects a profile and detects content-hash drift without execution.",
        ),
        _entry(
            "automation_workflow_plan",
            "preview",
            "read_only",
            commands=(("orchestration", "workflow", "plan"),),
            key_flags=("--profile-id",),
            boundary="Projects checked profile requirements into unexecuted CLI candidates.",
        ),
        _entry(
            "control_panel_read",
            "preview",
            "read_only",
            commands=(
                ("orchestration", "control-panel", "handoff"),
                ("orchestration", "control-panel", "render"),
                ("orchestration", "control-panel", "snapshot"),
            ),
            key_flags=("--envelope",),
            boundary=(
                "Aggregates existing read models into a deterministic local Control "
                "Panel and host handoff without service, network, or execution."
            ),
        ),
        _entry(
            "contract_discovery",
            "stable",
            "read_only",
            commands=(("orchestration", "contract", "inspect"),),
            boundary="Returns this versioned manifest without reading project runtime data.",
        ),
        _entry(
            "contract_requirement_gate",
            "stable",
            "read_only",
            commands=(("orchestration", "contract", "check"),),
            key_flags=("--allow-preview", "--max-access", "--require"),
            boundary="Evaluates declared requirements without executing their commands.",
        ),
        _entry(
            "execution_readiness",
            "preview",
            "read_only",
            commands=(("orchestration", "execution", "readiness"),),
            boundary="Validates a fixed single-user execution design profile and does not execute processes or adapters.",
        ),
        _entry(
            "external_execution_service_stack",
            "unavailable",
            "unavailable",
            boundary="Real adapter execution, long-running service, auth, database, and interactive write-capable UI are unavailable.",
        ),
        _entry(
            "orchestration_artifact_export",
            "unavailable",
            "unavailable",
            boundary="No orchestration-level artifact export operation exists.",
        ),
        _entry(
            "overview",
            "stable",
            "read_only",
            commands=(("orchestration", "overview"),),
            boundary="Read-only task and event ledger aggregation.",
        ),
        _entry(
            "persistent_run_report_collection",
            "unavailable",
            "unavailable",
            boundary="Persistent run and report collections with independent ids are unavailable.",
        ),
        _entry(
            "read_loop_snapshot",
            "preview",
            "read_only",
            commands=(("orchestration", "run"),),
            key_flags=("--dry-run", "--snapshot"),
            boundary="Ephemeral Run/Event/Report projection with no persistent ids.",
        ),
        _entry(
            "report_generate",
            "stable_limited",
            "read_only",
            commands=(("orchestration", "report", "generate"),),
            key_flags=("--aggregate-lineage", "--replay"),
            boundary="Task and request projection; no independent report collection.",
        ),
        _entry(
            "routing_preflight",
            "stable",
            "read_only",
            commands=(
                ("orchestration", "preflight"),
                ("orchestration", "route", "preview"),
            ),
            key_flags=("--explain",),
            boundary="Read-only routing and guardrail decisions; adapters are not executed.",
        ),
        _entry(
            "routing_preflight_snapshot",
            "preview",
            "read_only",
            commands=(
                ("orchestration", "preflight"),
                ("orchestration", "route", "snapshot"),
            ),
            key_flags=("--snapshot",),
            boundary="Deterministic content-addressed projection that is not persisted.",
        ),
        _entry(
            "run_commit",
            "stable",
            "controlled_write",
            commands=(("orchestration", "run"),),
            key_flags=("--commit", "--expected-plan-hash"),
            boundary="Writes an envelope draft and lifecycle events but never executes an adapter.",
        ),
        _entry(
            "run_plan",
            "preview",
            "read_only",
            commands=(("orchestration", "run"),),
            key_flags=("--dry-run", "--fallback-from", "--fallback-to", "--retry-of"),
            boundary="Plan preview only; no persistent Run is created.",
        ),
        _entry(
            "run_read",
            "stable_limited",
            "read_only",
            commands=(
                ("orchestration", "run", "inspect"),
                ("orchestration", "run", "list"),
            ),
            key_flags=("--aggregate-lineage", "--replay"),
            boundary="Envelope-scoped read models; not a cross-envelope Run collection.",
        ),
        _entry(
            "task_read",
            "stable",
            "read_only",
            commands=(
                ("orchestration", "task", "get"),
                ("orchestration", "task", "list"),
            ),
            boundary="Reads task ledger data and the task event timeline.",
        ),
        _entry(
            "task_submit",
            "stable",
            "controlled_write",
            commands=(("orchestration", "task", "submit"),),
            key_flags=("--commit", "--dry-run"),
            boundary="Commit atomically appends a task and its created event after validation.",
        ),
    )
    return OrchestrationContractManifest(entries=tuple(sorted(entries, key=lambda item: item.contract_id)))
