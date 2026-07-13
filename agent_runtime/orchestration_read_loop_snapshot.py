"""Read-only orchestration read-loop snapshot.

This module projects a ``RunDryRunResult`` into a stable, deterministic,
value-safe control-plane snapshot that bundles:

* a Run preview (status=planned/preview, no execution)
* candidate Event summaries (no fabricated ids/timestamps)
* a Report preview (status=preview, no persistent report id)

It does not persist the snapshot, write ledgers, generate persistent Run/Event
or Report objects, execute adapters, or access networks.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from typing import Any

from .orchestration_run_dry_run import RunDryRunResult


SCHEMA_VERSION = "control-plane/read-loop/v1"


def _canonical_json(payload: dict[str, Any]) -> str:
    """Return a deterministic compact JSON representation."""
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _compute_snapshot_id(payload: dict[str, Any]) -> str:
    """Return a deterministic sha256 content id for the snapshot payload."""
    canonical = _canonical_json(payload)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


@dataclass(frozen=True)
class OrchestrationReadLoopSnapshot:
    """Deterministic, ephemeral read model of a run preview closed loop.

    This object is intentionally not persisted. It serves as the Stage 12
    read-loop projection, consumable by future Run/Event/Report/API layers.
    """

    schema_version: str
    snapshot_id: str
    status: str
    run: dict[str, Any]
    events: list[dict[str, Any]]
    report: dict[str, Any]
    source: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "snapshot_id": self.snapshot_id,
            "status": self.status,
            "run": self.run,
            "events": self.events,
            "report": self.report,
            "source": self.source,
        }


def _run_status(dry_run: RunDryRunResult) -> str:
    """Map dry-run status to a run preview status.

    Successful dry-runs (pass / needs_approval) are marked as ``planned``;
    other statuses are propagated as-is so the snapshot can still represent
    blocked / needs_input / error / validation_failed cases.
    """
    if dry_run.status in {"pass", "needs_approval"}:
        return "planned"
    return dry_run.status


def _gate_status(dry_run: RunDryRunResult) -> str:
    """Return a stable gate status that distinguishes executable from blocked.

    ``pass`` maps to ``ready``; ``needs_approval`` maps to
    ``pending_approval``; all other statuses are propagated as-is so consumers
    do not mistake a blocked/needs_input/error run for an executable plan.
    """
    if dry_run.status == "pass":
        return "ready"
    if dry_run.status == "needs_approval":
        return "pending_approval"
    return dry_run.status


def _run_layer(dry_run: RunDryRunResult) -> dict[str, Any]:
    """Project a safe Run preview from a dry-run result."""
    route = dry_run.route
    run: dict[str, Any] = {
        "status": _run_status(dry_run),
        "gate_status": _gate_status(dry_run),
        "task_id": dry_run.task_id,
        "request_id": dry_run.request_id,
        "adapter_id": route.get("selected_adapter_id"),
        "capability": dry_run.requested_capability,
        "operation": route.get("operation"),
        "mode": dry_run.mode,
        "risk_level": route.get("risk_level"),
        "requires_approval": route.get("requires_approval"),
        "requires_dry_run": route.get("requires_dry_run"),
    }
    if dry_run.plan_hash is not None:
        run["plan_hash"] = dry_run.plan_hash
    if dry_run.routing_snapshot_id is not None:
        run["routing_snapshot_id"] = dry_run.routing_snapshot_id
    if dry_run.lineage_type is not None:
        run["lineage_type"] = dry_run.lineage_type
    if dry_run.retry_of is not None:
        run["retry_of"] = dry_run.retry_of
    if dry_run.fallback_from is not None:
        run["fallback_from"] = dry_run.fallback_from
    if dry_run.fallback_to is not None:
        run["fallback_to"] = dry_run.fallback_to
    return run


def _events_layer(dry_run: RunDryRunResult) -> list[dict[str, Any]]:
    """Project safe candidate Event summaries from a dry-run result.

    Does not fabricate ``event_id`` or ``timestamp``; the events have not been
    written to any ledger.
    """
    events: list[dict[str, Any]] = []
    for candidate in dry_run.candidate_events_summary:
        events.append(
            {
                "event_type": candidate.get("event_type"),
                "status": "planned",
                "metadata_keys": list(candidate.get("metadata_keys", [])),
            }
        )
    return events


def _report_layer(
    dry_run: RunDryRunResult, events: list[dict[str, Any]]
) -> dict[str, Any]:
    """Project a safe Report preview from a dry-run result.

    The report status is always ``preview`` to make clear that no persistent
    Report object has been generated and no completion verification has run.
    """
    artifact_refs = dry_run.artifact_candidate_refs
    evidence_refs = dry_run.evidence_candidate_refs
    event_types = [e.get("event_type") for e in events]
    artifact_types = [ref.get("artifact_type") for ref in artifact_refs if ref.get("artifact_type")]
    evidence_types = [
        ref.get("evidence_type") for ref in evidence_refs if ref.get("evidence_type")
    ]

    gate_status = _gate_status(dry_run)
    status_summary = (
        f"run_status={_run_status(dry_run)} gate_status={gate_status} "
        f"adapter={dry_run.route.get('selected_adapter_id') or '-'} "
        f"capability={dry_run.requested_capability}"
    )
    report: dict[str, Any] = {
        "status": "preview",
        "gate_status": gate_status,
        "status_summary": status_summary,
        "candidate_event_count": len(events),
        "candidate_event_types": dict(Counter(t for t in event_types if t)),
        "artifact_candidate_count": len(artifact_refs),
        "artifact_candidate_type_counts": dict(Counter(artifact_types)),
        "evidence_candidate_count": len(evidence_refs),
        "evidence_candidate_type_counts": dict(Counter(evidence_types)),
        "requires_approval": bool(
            dry_run.route.get("requires_approval")
            or dry_run.candidate_envelope_summary.get("requires_approval")
        ),
    }
    if dry_run.next_action is not None:
        report["next_action"] = dry_run.next_action
    if dry_run.lineage_type is not None:
        report["lineage_type"] = dry_run.lineage_type

    # Include only rule ids, never full finding messages.
    rule_ids = [f.rule_id for f in dry_run.findings if f.rule_id]
    if rule_ids:
        report["finding_rule_ids"] = rule_ids
        report["finding_count"] = len(rule_ids)

    return report


def _source_layer(dry_run: RunDryRunResult) -> dict[str, Any]:
    """Project source identity fields."""
    return {
        "task_id": dry_run.task_id,
        "request_id": dry_run.request_id,
        "requested_capability": dry_run.requested_capability,
    }


def build_read_loop_snapshot(
    dry_run: RunDryRunResult,
) -> OrchestrationReadLoopSnapshot:
    """Build a deterministic read-loop snapshot from a run dry-run result.

    The snapshot is a pure projection: it does not re-run routing or planning,
    mutate state, or access external systems.
    """
    run = _run_layer(dry_run)
    events = _events_layer(dry_run)
    report = _report_layer(dry_run, events)
    source = _source_layer(dry_run)

    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "status": dry_run.status,
        "run": run,
        "events": events,
        "report": report,
        "source": source,
    }
    snapshot_id = _compute_snapshot_id(payload)

    return OrchestrationReadLoopSnapshot(
        schema_version=SCHEMA_VERSION,
        snapshot_id=snapshot_id,
        status=dry_run.status,
        run=run,
        events=events,
        report=report,
        source=source,
    )
