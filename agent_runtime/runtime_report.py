"""Read-only runtime report aggregator.

Combines task snapshot, event stream summary, adapter envelope inspection,
runtime gate status, and runtime ledger audit into a single report. It does
not execute adapters, write ledgers, access networks, or read credential
files.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .result import Finding, coalesce_status
from .runtime_draft import inspect_runtime_draft
from .runtime_gate import check_runtime_gate
from .runtime_ledger import check_runtime_ledger
from .tasks import find_task, find_task_events


TERMINAL_STATUSES = {"finished", "failed"}


@dataclass
class RuntimeReportResult:
    """Result of a runtime report aggregation."""

    status: str
    task_id: str
    task_status: str | None = None
    task_snapshot: dict[str, Any] = field(default_factory=dict)
    event_summary: dict[str, Any] = field(default_factory=dict)
    envelope_summary: dict[str, Any] | None = None
    gate: dict[str, Any] | None = None
    ledger: dict[str, Any] | None = None
    blockers: list[str] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    next_action: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "status": self.status,
            "task_id": self.task_id,
        }
        if self.task_status is not None:
            d["task_status"] = self.task_status
        if self.task_snapshot:
            d["task_snapshot"] = self.task_snapshot
        if self.event_summary:
            d["event_summary"] = self.event_summary
        if self.envelope_summary is not None:
            d["envelope_summary"] = self.envelope_summary
        if self.gate is not None:
            d["gate"] = self.gate
        if self.ledger is not None:
            d["ledger"] = self.ledger
        if self.blockers:
            d["blockers"] = self.blockers
        if self.findings:
            d["findings"] = [f.to_dict() for f in self.findings]
        if self.next_action is not None:
            d["next_action"] = self.next_action
        return d


def _sanitize_task_snapshot(task: dict[str, Any]) -> dict[str, Any]:
    """Return a value-safe task snapshot.

    Keeps ids, status, title, assignee, timestamps, and high-level counts.
    Omits full evidence descriptions/refs and artifact lists.
    """
    safe: dict[str, Any] = {
        "id": task.get("id"),
        "title": task.get("title"),
        "status": task.get("status"),
        "assignee": task.get("assignee"),
        "created_at": task.get("created_at"),
        "updated_at": task.get("updated_at"),
    }
    if task.get("current_step"):
        safe["current_step"] = task["current_step"]
    if task.get("blocked_reason"):
        safe["blocked_reason"] = task["blocked_reason"]
    if task.get("failure_reason"):
        safe["failure_reason"] = task["failure_reason"]
    evidence = task.get("evidence")
    if isinstance(evidence, list):
        safe["evidence_count"] = len(evidence)
    artifacts = task.get("artifacts")
    if isinstance(artifacts, list):
        safe["artifact_count"] = len(artifacts)
    return safe


def _build_event_summary(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Return a compact, value-safe event stream summary."""
    type_counts: dict[str, int] = {}
    latest: dict[str, Any] | None = None
    for event in events:
        event_type = event.get("event_type", "unknown")
        type_counts[event_type] = type_counts.get(event_type, 0) + 1
        if latest is None or str(event.get("timestamp", "")) > str(latest.get("timestamp", "")):
            latest = event

    summary: dict[str, Any] = {
        "total": len(events),
        "type_counts": type_counts,
    }
    if latest is not None:
        summary["latest"] = {
            "event_id": latest.get("event_id"),
            "event_type": latest.get("event_type"),
            "timestamp": latest.get("timestamp"),
            "from_status": latest.get("from_status"),
            "to_status": latest.get("to_status"),
        }
    return summary


def check_runtime_report(
    root: Path,
    task_id: str,
    request_id: str,
    envelope_file: str,
    tasks_file: str | None = None,
    events_file: str | None = None,
) -> RuntimeReportResult:
    """Generate a read-only runtime report for a task + request pair."""
    root = root.resolve()
    findings: list[Finding] = []
    statuses: list[str] = []
    blockers: list[str] = []

    # 1. Task snapshot
    task = find_task(root, task_id, explicit_file=tasks_file)
    if task is None:
        return RuntimeReportResult(
            status="error",
            task_id=task_id,
            task_status=None,
            findings=[
                Finding(
                    rule_id="task-not-found",
                    severity="error",
                    action="error",
                    message=f"Task {task_id} not found in task ledger.",
                )
            ],
            next_action="Provide a task_id that exists in the task ledger.",
        )

    task_status = task.get("status")
    task_snapshot = _sanitize_task_snapshot(task)
    if task_status in TERMINAL_STATUSES:
        blockers.append(f"Task is in terminal state ({task_status}).")

    # 2. Event stream summary
    events = find_task_events(root, task_id, explicit_file=events_file)
    event_summary = _build_event_summary(events)

    # 3. Envelope inspection (reuses existing sanitize/summary logic)
    inspect_result, envelope_summary = inspect_runtime_draft(
        root, file=envelope_file, stdin=False
    )
    statuses.append(inspect_result.status)
    if inspect_result.status != "pass":
        findings.extend(inspect_result.findings)
        blockers.append("Envelope validation failed.")

    # 4. Runtime gate
    gate_result = check_runtime_gate(
        root,
        task_id=task_id,
        request_id=request_id,
        envelope_file=envelope_file,
        tasks_file=tasks_file,
        events_file=events_file,
    )
    statuses.append(gate_result.status)
    gate = gate_result.gate if gate_result.gate else None
    if gate and gate.get("can_proceed") is False:
        blockers.append(f"Gate cannot proceed (stage={gate.get('stage', '-')}).")

    # 5. Runtime ledger audit
    ledger_result = check_runtime_ledger(
        root,
        tasks_file=tasks_file or "tasks/tasks.jsonl",
        events_file=events_file or "tasks/events.jsonl",
        envelope_file=envelope_file,
    )
    statuses.append(ledger_result.status)
    ledger = ledger_result.to_dict()
    if ledger_result.status == "error":
        blockers.append("Ledger audit failed.")
    elif ledger_result.status == "warn":
        blockers.append("Ledger audit has warnings.")

    # 6. Overall status and next_action
    overall_status = coalesce_status(statuses)
    # Terminal task always blocks, even if other checks pass.
    if task_status in TERMINAL_STATUSES:
        overall_status = coalesce_status([overall_status, "blocked"])

    if overall_status == "error":
        next_action = "Fix errors before proceeding."
    elif task_status in TERMINAL_STATUSES:
        next_action = f"Task is terminal ({task_status}); no new actions can be planned."
    elif overall_status == "blocked":
        next_action = gate_result.next_action or "Resolve blockers before proceeding."
    elif overall_status == "needs_approval":
        next_action = gate_result.next_action or "Wait for user approval."
    elif overall_status == "needs_input":
        next_action = gate_result.next_action or "Provide missing input."
    elif overall_status == "warn":
        next_action = "Review warnings; report passed with warnings."
    else:
        next_action = gate_result.next_action or "Proceed with adapter execution."

    return RuntimeReportResult(
        status=overall_status,
        task_id=task_id,
        task_status=task_status,
        task_snapshot=task_snapshot,
        event_summary=event_summary,
        envelope_summary=envelope_summary,
        gate=gate,
        ledger=ledger,
        blockers=blockers,
        findings=findings,
        next_action=next_action,
    )
