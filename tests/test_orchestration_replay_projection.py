"""Stage 14 replay/next-action projection contract tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent_runtime.orchestration_replay import (
    REPLAY_SCHEMA_VERSION,
    build_replay_projection,
    derive_next_action_code,
)
from agent_runtime.orchestration_report import generate_report
from agent_runtime.orchestration_run import inspect_run
from agent_runtime.runtime_report import RuntimeReportResult


def _report(
    *,
    status: str = "pass",
    task_status: str = "running",
    gate: dict[str, object] | None = None,
    envelope_summary: dict[str, object] | None = None,
    next_action: str = "Review the current state.",
) -> RuntimeReportResult:
    return RuntimeReportResult(
        status=status,
        task_id="task-20260713-001",
        task_status=task_status,
        event_summary={
            "total": 2,
            "latest": {
                "event_type": "run_planned",
                "to_status": "running",
            },
        },
        envelope_summary=envelope_summary
        or {
            "artifact_counts": {
                "adapter_request": 1,
                "adapter_response": 1,
                "execution_event": 2,
            },
            "overall": {
                "response_count": 1,
                "evidence_count": 2,
            },
            "source": "drafts/runtime/private-name.envelope.json",
        },
        gate=gate
        or {
            "stage": "postflight",
            "approval_status": "pass",
            "response_status": "succeeded",
            "can_proceed": True,
        },
        ledger={"status": "pass", "counts": {"tasks": 1, "events": 2}},
        next_action=next_action,
    )


@pytest.mark.parametrize(
    ("status", "task_status", "approval_status", "expected"),
    [
        ("pass", "running", "pass", "needs_human_review"),
        ("needs_approval", "blocked", "needs_approval", "blocked_wait_for_approval"),
        ("needs_input", "blocked", "needs_input", "needs_input"),
        ("blocked", "running", "blocked", "needs_human_review"),
        ("error", "running", None, "needs_human_review"),
        ("blocked", "finished", "pass", "task_finished"),
        ("blocked", "failed", "pass", "needs_human_review"),
    ],
)
def test_derive_next_action_code_has_stable_precedence(
    status: str,
    task_status: str,
    approval_status: str | None,
    expected: str,
) -> None:
    report = _report(
        status=status,
        task_status=task_status,
        gate={
            "stage": "approval" if approval_status else "unknown",
            "approval_status": approval_status,
            "can_proceed": status == "pass",
        },
    )

    assert derive_next_action_code(report) == expected


def test_replay_projection_without_response_proceeds_to_commit() -> None:
    report = _report(
        envelope_summary={
            "artifact_counts": {"adapter_request": 1},
            "overall": {"response_count": 0, "evidence_count": 0},
        }
    )

    projection = build_replay_projection(report, request_id="req-20260713-001")

    assert projection.next_action["code"] == "proceed_to_commit"


def test_build_replay_projection_is_compact_deterministic_and_value_safe() -> None:
    report = _report(next_action="Review the passed gate; no external execution is performed.")

    first = build_replay_projection(report, request_id="req-20260713-001")
    second = build_replay_projection(report, request_id="req-20260713-001")

    assert first.to_dict() == second.to_dict()
    assert first.to_dict() == {
        "schema_version": REPLAY_SCHEMA_VERSION,
        "status": "pass",
        "task_id": "task-20260713-001",
        "request_id": "req-20260713-001",
        "task_status": "running",
        "next_action": {
            "code": "needs_human_review",
            "summary": "Review the passed gate; no external execution is performed.",
        },
        "state": {
            "event_count": 2,
            "latest_event_type": "run_planned",
            "latest_to_status": "running",
            "gate_stage": "postflight",
            "approval_status": "pass",
            "response_status": "succeeded",
            "can_proceed": True,
            "artifact_count": 4,
            "response_count": 1,
            "evidence_count": 2,
            "ledger_status": "pass",
        },
    }
    serialized = json.dumps(first.to_dict(), ensure_ascii=False)
    assert "private-name" not in serialized
    assert "origin/main" not in serialized
    assert "input" not in serialized


def test_run_inspect_and_report_generate_share_replay_projection(monkeypatch, tmp_path: Path) -> None:
    report = _report(
        status="needs_approval",
        task_status="blocked",
        gate={
            "stage": "approval",
            "approval_status": "needs_approval",
            "can_proceed": False,
        },
        next_action="Wait for user approval.",
    )

    monkeypatch.setattr("agent_runtime.orchestration_run.check_runtime_report", lambda *a, **k: report)
    monkeypatch.setattr("agent_runtime.orchestration_report.check_runtime_report", lambda *a, **k: report)

    run_result = inspect_run(
        tmp_path,
        task_id=report.task_id,
        request_id="req-20260713-001",
        envelope_file="unused.json",
        replay=True,
    )
    report_result = generate_report(
        tmp_path,
        task_id=report.task_id,
        request_id="req-20260713-001",
        envelope_file="unused.json",
        replay=True,
    )

    assert run_result.replay is not None
    assert report_result.replay is not None
    assert run_result.replay.to_dict() == report_result.replay.to_dict()
    assert run_result.replay.next_action["code"] == "blocked_wait_for_approval"


def test_replay_projection_is_opt_in_for_default_compatibility(monkeypatch, tmp_path: Path) -> None:
    report = _report()
    monkeypatch.setattr("agent_runtime.orchestration_run.check_runtime_report", lambda *a, **k: report)
    monkeypatch.setattr("agent_runtime.orchestration_report.check_runtime_report", lambda *a, **k: report)

    run_result = inspect_run(
        tmp_path,
        task_id=report.task_id,
        request_id="req-20260713-001",
        envelope_file="unused.json",
    )
    report_result = generate_report(
        tmp_path,
        task_id=report.task_id,
        request_id="req-20260713-001",
        envelope_file="unused.json",
    )

    assert "replay" not in run_result.to_dict()
    assert "replay" not in report_result.to_dict()
