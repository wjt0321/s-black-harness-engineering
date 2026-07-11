"""Read-only orchestration run views for the agent-runtime CLI.

This module provides orchestration-namespace wrappers over existing envelope
and runtime report aggregators. It does not introduce a new Run storage layer:

* ``inspect_run`` identifies a run by the triple
  ``(task_id, request_id, envelope_file)`` and delegates to
  ``check_runtime_report``.
* ``list_runs`` is an envelope-scoped read model: it extracts request/response
  pairs from a single adapter execution envelope and returns one summary row
  per request.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .adapter_validation import validate_envelope_file
from .orchestration_recovery import RecoveryLineageResult, aggregate_recovery_lineage
from .runtime_report import RuntimeReportResult, check_runtime_report


_LINEAGE_KEYS = ("lineage_type", "retry_of", "fallback_from", "fallback_to")


def _lineage_fields(source: dict[str, Any]) -> dict[str, Any]:
    """Return lineage keys from ``source`` when their values are present.

    Keeps retry/fallback lineage compact: absent or ``None`` values are omitted
    so normal runs do not carry empty lineage fields.
    """
    return {k: v for k, v in source.items() if k in _LINEAGE_KEYS and v is not None}


@dataclass
class RunInspectResult:
    """Result of an orchestration run inspect."""

    status: str
    task_id: str
    request_id: str
    task_status: str | None = None
    envelope_summary: dict[str, Any] | None = None
    gate: dict[str, Any] | None = None
    ledger: dict[str, Any] | None = None
    blockers: list[str] = field(default_factory=list)
    next_action: str | None = None
    event_summary: dict[str, Any] = field(default_factory=dict)
    task_snapshot: dict[str, Any] = field(default_factory=dict)
    lineage_type: str | None = None
    retry_of: str | None = None
    fallback_from: str | None = None
    fallback_to: str | None = None
    recovery_lineage: RecoveryLineageResult | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "status": self.status,
            "task_id": self.task_id,
            "request_id": self.request_id,
        }
        if self.task_status is not None:
            d["task_status"] = self.task_status
        if self.envelope_summary is not None:
            d["envelope_summary"] = self.envelope_summary
        if self.gate is not None:
            d["gate"] = self.gate
        if self.ledger is not None:
            d["ledger"] = self.ledger
        if self.blockers:
            d["blockers"] = self.blockers
        if self.next_action is not None:
            d["next_action"] = self.next_action
        if self.event_summary:
            d["event_summary"] = self.event_summary
        if self.task_snapshot:
            d["task_snapshot"] = self.task_snapshot
        if self.lineage_type is not None:
            d["lineage_type"] = self.lineage_type
        if self.retry_of is not None:
            d["retry_of"] = self.retry_of
        if self.fallback_from is not None:
            d["fallback_from"] = self.fallback_from
        if self.fallback_to is not None:
            d["fallback_to"] = self.fallback_to
        if self.recovery_lineage is not None:
            d["recovery_lineage"] = self.recovery_lineage.to_dict()
        return d


def _extract_lineage_for_request(
    envelope_summary: dict[str, Any] | None, request_id: str
) -> dict[str, Any]:
    """Return lineage fields for ``request_id`` from an envelope summary."""
    if envelope_summary is None:
        return {}
    for request_summary in envelope_summary.get("requests", []):
        if request_summary.get("request_id") == request_id:
            return _lineage_fields(request_summary)
    return {}


def inspect_run(
    root: Path,
    task_id: str,
    request_id: str,
    envelope_file: str,
    tasks_file: str | None = None,
    events_file: str | None = None,
    aggregate_lineage: bool = False,
) -> RunInspectResult:
    """Inspect a run through the existing runtime report aggregator.

    This is a thin wrapper: it calls ``check_runtime_report`` with the same
    arguments and repackages the result with a ``request_id`` field. No
    adapters are executed and no ledgers are written.
    """
    report = check_runtime_report(
        root,
        task_id=task_id,
        request_id=request_id,
        envelope_file=envelope_file,
        tasks_file=tasks_file,
        events_file=events_file,
    )
    lineage = _extract_lineage_for_request(report.envelope_summary, request_id)
    recovery_lineage = None
    status = report.status
    if aggregate_lineage:
        recovery_lineage = aggregate_recovery_lineage(
            root,
            task_id=task_id,
            request_id=request_id,
            events_file=events_file,
        )
        precedence = {
            "pass": 0,
            "needs_approval": 1,
            "needs_input": 2,
            "blocked": 3,
            "validation_failed": 4,
            "error": 5,
        }
        if precedence.get(recovery_lineage.status, 5) > precedence.get(status, 5):
            status = recovery_lineage.status

    return RunInspectResult(
        status=status,
        task_id=report.task_id,
        request_id=request_id,
        task_status=report.task_status,
        envelope_summary=report.envelope_summary,
        gate=report.gate,
        ledger=report.ledger,
        blockers=report.blockers,
        next_action=report.next_action,
        event_summary=report.event_summary,
        task_snapshot=report.task_snapshot,
        recovery_lineage=recovery_lineage,
        **lineage,
    )


@dataclass
class RunListResult:
    """Result of an orchestration run list (envelope-scoped read model)."""

    status: str
    runs: list[dict[str, Any]] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    next_action: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "status": self.status,
            "runs": self.runs,
        }
        if self.findings:
            d["findings"] = [f.to_dict() for f in self.findings]
        if self.next_action is not None:
            d["next_action"] = self.next_action
        return d


def list_runs(
    root: Path,
    envelope_file: str,
    task_id_filter: str | None = None,
) -> RunListResult:
    """List runs from a single adapter execution envelope.

    This is an envelope-scoped read model: it extracts ``adapter_request`` and
    ``adapter_response`` artifacts and returns one summary row per request. It
    does not introduce a persistent Run collection, execute adapters, or write
    any files.
    """
    validation = validate_envelope_file(root, envelope_file)
    if validation.status != "pass":
        return RunListResult(
            status=validation.status,
            findings=validation.findings,
            next_action=validation.next_action,
        )

    # Validation already checked path safety and JSON syntax.
    path = (root / envelope_file).resolve()
    envelope = json.loads(path.read_text(encoding="utf-8"))

    artifacts = envelope.get("artifacts", [])
    responses: dict[str, dict[str, Any]] = {}
    for artifact in artifacts:
        if artifact.get("artifact_type") == "adapter_response":
            responses[artifact.get("request_id", "")] = artifact

    runs: list[dict[str, Any]] = []
    for artifact in artifacts:
        if artifact.get("artifact_type") != "adapter_request":
            continue

        request_id = artifact.get("request_id", "")
        task_id = artifact.get("task_id", "")
        if task_id_filter is not None and task_id != task_id_filter:
            continue

        context = artifact.get("context", {})
        preflight = artifact.get("preflight", {})
        response = responses.get(request_id)

        # Status inference: concrete response status wins over preflight status.
        status = preflight.get("status", "unknown")
        if response is not None:
            status = response.get("status", status)

        mode = "dry-run" if context.get("dry_run") else "commit"

        run: dict[str, Any] = {
            "request_id": request_id,
            "task_id": task_id,
            "adapter_id": artifact.get("adapter_id", ""),
            "capability": context.get("capability", ""),
            "operation": artifact.get("operation", ""),
            "mode": mode,
            "status": status,
            "started_at": artifact.get("created_at", ""),
            "ended_at": response.get("finished_at", "") if response else "",
        }
        run.update(_lineage_fields(context))
        runs.append(run)

    # Preserve request order from the envelope.
    return RunListResult(
        status="pass",
        runs=runs,
        next_action="Use orchestration run inspect for per-run details.",
    )
