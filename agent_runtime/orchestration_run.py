"""Read-only orchestration run inspect for the agent-runtime CLI.

This module provides a thin orchestration-namespace wrapper around the
existing runtime report aggregator. It does not introduce a new Run storage
layer; a "run" is currently identified by the triple
``(task_id, request_id, envelope_file)`` and inspected through
``check_runtime_report``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .runtime_report import RuntimeReportResult, check_runtime_report


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
        return d


def inspect_run(
    root: Path,
    task_id: str,
    request_id: str,
    envelope_file: str,
    tasks_file: str | None = None,
    events_file: str | None = None,
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
    return RunInspectResult(
        status=report.status,
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
    )
