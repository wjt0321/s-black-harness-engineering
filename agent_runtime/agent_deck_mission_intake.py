"""Bounded Agent Deck mission intake built on the existing A+B task ledger transaction.

This is an intake boundary, not an execution boundary.  A user supplies one
natural-language goal; the module derives every internal identity and uses the
existing controlled task submit transaction to append exactly one task and one
``created`` event.  It never starts an Agent, a host process, or a collaboration
chain.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .orchestration_task_submit import TaskSubmitResult, submit_task
from .policy import check_text
from .result import CheckResult, Finding
from .tasks import load_tasks

_SCHEMA_VERSION = "agent-deck/mission-intake/v1"
_TASK_ID_RE = re.compile(r"^task-(?P<day>[0-9]{8})-(?P<sequence>[0-9]{3,})$")
_MAX_GOAL_BYTES = 1_024
_MAX_GOAL_CHARS = 500


@dataclass
class AgentDeckMissionResult(CheckResult):
    """Safe public result for a mission intake preview or commit.

    The free-text goal stays in the controlled task ledger only after a
    successful commit.  It is deliberately not re-emitted in CLI JSON so that
    snapshot and automation consumers only receive identities and state.
    """

    task_id: str | None = None
    event_id: str | None = None
    goal_present: bool = False
    goal_byte_count: int = 0
    phase_label_zh: str = "待登记"
    committed: bool = False
    created_event_committed: bool = False
    submission: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        payload.update(
            {
                "schema_version": _SCHEMA_VERSION,
                "task_id": self.task_id,
                "event_id": self.event_id,
                "goal_present": self.goal_present,
                "goal_byte_count": self.goal_byte_count,
                "phase_label_zh": self.phase_label_zh,
                "committed": self.committed,
                "created_event_committed": self.created_event_committed,
                "guarantees": {
                    "fixed_ledger_paths": True,
                    "user_supplied_internal_id": False,
                    "starts_agent": False,
                    "starts_host": False,
                    "starts_chain": False,
                    "requires_commit": True,
                },
            }
        )
        if self.submission:
            payload["submission"] = dict(self.submission)
        return payload


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _finding(rule_id: str, message: str, *, status: str) -> Finding:
    return Finding(rule_id=rule_id, severity="error", action=status, message=message)


def _validate_goal(root: Path, goal: object) -> tuple[str, int] | CheckResult:
    if not isinstance(goal, str):
        return AgentDeckMissionResult(
            status="validation_failed",
            findings=[_finding("agent-deck-mission-goal-invalid", "任务目标必须是单段文本。", status="validation_failed")],
            next_action="请输入一段不含控制字符的任务目标。",
        )
    normalized = goal.strip()
    encoded = normalized.encode("utf-8")
    if (
        not normalized
        or len(normalized) > _MAX_GOAL_CHARS
        or len(encoded) > _MAX_GOAL_BYTES
        or any(ord(char) < 32 or ord(char) == 127 for char in normalized)
    ):
        return AgentDeckMissionResult(
            status="validation_failed",
            findings=[_finding("agent-deck-mission-goal-invalid", "任务目标必须是有界的单段文本。", status="validation_failed")],
            next_action="将目标缩短为不超过 500 个字符、1 KiB 的单段文本。",
        )
    scan = check_text(root, normalized)
    if scan.status != "pass":
        return AgentDeckMissionResult(
            status="blocked",
            findings=[_finding("agent-deck-mission-goal-secret-scan", "任务目标未通过安全扫描；匹配内容不会显示。", status="blocked")],
            next_action="移除可能包含凭据或敏感内容的片段后重试。",
        )
    return normalized, len(encoded)


def _next_task_id(root: Path, *, day: str) -> str:
    highest = 0
    for record in load_tasks(root):
        task_id = record.get("id") if isinstance(record, dict) else None
        if not isinstance(task_id, str):
            continue
        match = _TASK_ID_RE.fullmatch(task_id)
        if match is not None and match.group("day") == day:
            highest = max(highest, int(match.group("sequence")))
    return f"task-{day}-{highest + 1:03d}"


def _candidate(*, task_id: str, goal: str, timestamp: str) -> dict[str, Any]:
    return {
        "id": task_id,
        "title": goal,
        "status": "planned",
        "created_at": timestamp,
        "updated_at": timestamp,
        "created_by": "agent-deck-user",
        "source": "agent-deck",
        "assignee": "main-agent",
        "priority": "normal",
        "tags": ["agent-deck", "awaiting-main-plan"],
        "current_step": "等待主控 Agent 规划",
        "summary": None,
        "artifacts": [],
        "evidence": [],
        "blocked_reason": None,
        "blocked_message": None,
        "failure_reason": None,
        "next_action": "等待主控 Agent 提出协作计划。",
        "parent_id": None,
    }


def _submission_projection(result: TaskSubmitResult) -> dict[str, Any]:
    return {
        "ledger_check": result.ledger_check,
        "would_create": result.would_create,
        "would_append_created_event": result.would_append_created_event,
        "post_validate_tasks": result.post_validate_tasks,
        "post_validate_events": result.post_validate_events,
        "post_ledger_check": result.post_ledger_check,
        "rolled_back": result.rolled_back,
    }


def submit_agent_deck_mission(
    root: Path,
    *,
    goal: object,
    dry_run: bool,
    commit: bool,
    now: datetime | None = None,
) -> AgentDeckMissionResult:
    """Preview or register a single formal Agent Deck mission.

    ``--commit`` is the only write mode.  Internal task/event identities,
    ledger locations, ownership and initial planning state are fixed by this
    module; callers cannot provide paths, task IDs, Agent arguments or host
    settings.
    """
    root = root.resolve()
    validated = _validate_goal(root, goal)
    if isinstance(validated, CheckResult):
        return validated
    normalized_goal, goal_bytes = validated
    if dry_run == commit:
        return AgentDeckMissionResult(
            status="validation_failed",
            goal_present=True,
            goal_byte_count=goal_bytes,
            findings=[_finding("agent-deck-mission-mode-invalid", "必须且只能选择预览或正式登记。", status="validation_failed")],
            next_action="使用 --dry-run 预览，或使用 --commit 正式登记。",
        )
    current = now or _utc_now()
    if current.tzinfo is None:
        return AgentDeckMissionResult(
            status="validation_failed",
            goal_present=True,
            goal_byte_count=goal_bytes,
            findings=[_finding("agent-deck-mission-clock-invalid", "任务登记时钟必须带有时区。", status="validation_failed")],
            next_action="使用带时区的系统时间后重试。",
        )
    timestamp = current.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    task_id = _next_task_id(root, day=current.astimezone(timezone.utc).strftime("%Y%m%d"))
    submitted = submit_task(
        root,
        dry_run=dry_run,
        commit=commit,
        tasks_file="tasks/tasks.jsonl",
        events_file="tasks/events.jsonl",
        candidate=_candidate(task_id=task_id, goal=normalized_goal, timestamp=timestamp),
    )
    safe_submission = _submission_projection(submitted) if isinstance(submitted, TaskSubmitResult) else {}
    actual_task_id = submitted.task_id if isinstance(submitted, TaskSubmitResult) else task_id
    actual_event_id = submitted.event_id if isinstance(submitted, TaskSubmitResult) else None
    is_committed = bool(getattr(submitted, "committed", False))
    event_committed = bool(getattr(submitted, "created_event_committed", False))
    return AgentDeckMissionResult(
        status=submitted.status,
        task_id=actual_task_id,
        event_id=actual_event_id,
        goal_present=True,
        goal_byte_count=goal_bytes,
        phase_label_zh="等待主控 Agent 规划" if is_committed else "待登记",
        committed=is_committed,
        created_event_committed=event_committed,
        submission=safe_submission,
        findings=list(submitted.findings),
        next_action=(
            "任务已正式登记，等待主控 Agent 规划；本操作不会启动任何 Agent。"
            if is_committed
            else submitted.next_action
        ),
    )
