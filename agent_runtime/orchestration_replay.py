"""Deterministic Stage 14 orchestration replay projection.

The projection reuses an existing ``RuntimeReportResult``. It does not reload
state, execute adapters, write ledgers, or expose envelope payloads. Consumers
must opt in through orchestration read-model flags so default outputs remain
compatible.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .runtime_report import RuntimeReportResult


REPLAY_SCHEMA_VERSION = "control-plane/orchestration-replay/v1"


@dataclass(frozen=True)
class OrchestrationReplayProjection:
    """Compact replay state and structured next action for one task/request."""

    schema_version: str
    status: str
    task_id: str
    request_id: str
    task_status: str | None
    next_action: dict[str, str]
    state: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "schema_version": self.schema_version,
            "status": self.status,
            "task_id": self.task_id,
            "request_id": self.request_id,
        }
        if self.task_status is not None:
            result["task_status"] = self.task_status
        result["next_action"] = self.next_action
        result["state"] = self.state
        return result


def derive_preview_next_action_code(status: str) -> str:
    """Map a dry-run preview status to the Stage 14 next-action contract."""
    if status == "pass":
        return "proceed_to_commit"
    if status == "needs_approval":
        return "blocked_wait_for_approval"
    if status == "needs_input":
        return "needs_input"
    return "needs_human_review"


def derive_next_action_code(report: RuntimeReportResult) -> str:
    """Map an existing report to the Stage 14 structured next-action contract."""
    if report.task_status == "finished":
        return "task_finished"
    if report.task_status == "failed":
        return "needs_human_review"

    approval_status = (report.gate or {}).get("approval_status")
    if report.status == "needs_approval" or approval_status == "needs_approval":
        return "blocked_wait_for_approval"
    if report.status == "needs_input" or approval_status == "needs_input":
        return "needs_input"
    if report.status in {"error", "validation_failed", "blocked", "warn"}:
        return "needs_human_review"

    overall = report.envelope_summary.get("overall", {}) if report.envelope_summary else {}
    if report.status == "pass" and overall.get("response_count", 0) == 0:
        return "proceed_to_commit"
    return "needs_human_review"


def _replay_state(report: RuntimeReportResult) -> dict[str, Any]:
    event_summary = report.event_summary or {}
    latest = event_summary.get("latest") or {}
    gate = report.gate or {}
    envelope = report.envelope_summary or {}
    artifact_counts = envelope.get("artifact_counts") or {}
    overall = envelope.get("overall") or {}

    state: dict[str, Any] = {
        "event_count": event_summary.get("total", 0),
        "artifact_count": sum(
            value for value in artifact_counts.values() if isinstance(value, int)
        ),
        "response_count": overall.get("response_count", 0),
        "evidence_count": overall.get("evidence_count", 0),
    }
    optional = {
        "latest_event_type": latest.get("event_type"),
        "latest_to_status": latest.get("to_status"),
        "gate_stage": gate.get("stage"),
        "approval_status": gate.get("approval_status"),
        "response_status": gate.get("response_status"),
        "can_proceed": gate.get("can_proceed"),
        "ledger_status": (report.ledger or {}).get("status"),
    }
    for key, value in optional.items():
        if value is not None:
            state[key] = value
    return state


def build_replay_projection(
    report: RuntimeReportResult,
    request_id: str,
) -> OrchestrationReplayProjection:
    """Project one already-computed runtime report into a replay read model."""
    next_action = {"code": derive_next_action_code(report)}
    if report.next_action is not None:
        next_action["summary"] = report.next_action

    return OrchestrationReplayProjection(
        schema_version=REPLAY_SCHEMA_VERSION,
        status=report.status,
        task_id=report.task_id,
        request_id=request_id,
        task_status=report.task_status,
        next_action=next_action,
        state=_replay_state(report),
    )
