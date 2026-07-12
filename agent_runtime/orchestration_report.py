"""Read-only orchestration report generation for the agent-runtime CLI.

This module provides a thin orchestration-namespace wrapper around the
existing runtime report aggregator. It does not introduce a new Report storage
layer; a report is currently identified by the triple
``(task_id, request_id, envelope_file)`` and generated through
``check_runtime_report``. No adapters are executed, no ledgers are written, and
no external systems are accessed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .orchestration_recovery import (
    RecoveryLineageResult,
    aggregate_recovery_lineage,
    merge_recovery_status,
)
from .orchestration_run import _extract_lineage_for_request
from .runtime_report import RuntimeReportResult, check_runtime_report


@dataclass
class ReportGenerateResult:
    """Result of an orchestration report generate command."""

    status: str
    task_id: str
    request_id: str
    task_status: str | None = None
    status_summary: str = ""
    key_findings: list[str] = field(default_factory=list)
    next_action: str | None = None
    event_summary: dict[str, Any] = field(default_factory=dict)
    envelope_summary: dict[str, Any] | None = None
    gate: dict[str, Any] | None = None
    ledger: dict[str, Any] | None = None
    artifact_refs: list[str] = field(default_factory=list)
    evidence_refs: list[str] = field(default_factory=list)
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
        if self.status_summary:
            d["status_summary"] = self.status_summary
        if self.key_findings:
            d["key_findings"] = self.key_findings
        if self.next_action is not None:
            d["next_action"] = self.next_action
        if self.event_summary:
            d["event_summary"] = self.event_summary
        if self.envelope_summary is not None:
            d["envelope_summary"] = self.envelope_summary
        if self.gate is not None:
            d["gate"] = self.gate
        if self.ledger is not None:
            d["ledger"] = self.ledger
        d["artifact_refs"] = self.artifact_refs
        d["evidence_refs"] = self.evidence_refs
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


def generate_report(
    root: Path,
    task_id: str,
    request_id: str,
    envelope_file: str,
    tasks_file: str | None = None,
    events_file: str | None = None,
    aggregate_lineage: bool = False,
) -> ReportGenerateResult:
    """Generate an orchestration report through the existing runtime report aggregator.

    This is a thin wrapper: it calls ``check_runtime_report`` with the same
    arguments and repackages the result with report-page semantics. No adapters
    are executed and no ledgers are written.
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
        status = merge_recovery_status(status, recovery_lineage.status)

    # Build a concise status summary for report-page consumption.
    status_summary = f"task_id={report.task_id} task={report.task_status or '-'} report={status}"
    if lineage.get("lineage_type"):
        status_summary += f" lineage_type={lineage['lineage_type']}"
    if report.blockers:
        status_summary += f" blockers={len(report.blockers)}"

    # Key findings are drawn from blockers first, then from high-severity findings.
    key_findings = list(report.blockers)
    for finding in report.findings:
        if finding.severity in ("block", "error"):
            key_findings.append(f"{finding.rule_id}: {finding.message}")

    return ReportGenerateResult(
        status=status,
        task_id=report.task_id,
        request_id=request_id,
        task_status=report.task_status,
        status_summary=status_summary,
        key_findings=key_findings,
        next_action=report.next_action,
        event_summary=report.event_summary,
        envelope_summary=report.envelope_summary,
        gate=report.gate,
        ledger=report.ledger,
        artifact_refs=[],
        evidence_refs=[],
        recovery_lineage=recovery_lineage,
        **lineage,
    )
