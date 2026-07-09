"""Read-only orchestration task list aggregation for the agent-runtime CLI.

This module provides a minimal ``TaskListResult`` read model for listing task
snapshots. It reuses the existing task ledger loader, supports an optional
``--status`` filter, and performs no writes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .tasks import find_task, find_task_events, load_tasks


@dataclass
class TaskListResult:
    """Compact read model for a list of task snapshots."""

    status: str = "pass"
    tasks: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "tasks": self.tasks,
        }


@dataclass
class TaskDetailResult:
    """Compact read model for a single task with its event timeline."""

    status: str = "pass"
    task: dict[str, Any] | None = None
    event_timeline: list[dict[str, Any]] = field(default_factory=list)
    next_action: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"status": self.status}
        if self.task is not None:
            d["task"] = self.task
        if self.event_timeline:
            d["event_timeline"] = self.event_timeline
        if self.next_action is not None:
            d["next_action"] = self.next_action
        return d


def get_task(root: Path, task_id: str) -> TaskDetailResult:
    """Build a read-only task detail read model with event timeline.

    Loads real ledgers, falling back to example files when no real ledger
    exists. Events are returned in chronological order. No writes are
    performed.
    """
    task = find_task(root, task_id)
    if task is None:
        return TaskDetailResult(
            status="needs_input",
            next_action=f"Task not found: {task_id}",
        )

    events = find_task_events(root, task_id)

    return TaskDetailResult(
        status="pass",
        task={
            "task_id": task.get("id", ""),
            "title": task.get("title", ""),
            "summary": task.get("summary", ""),
            "status": task.get("status", ""),
            "requested_capability": task.get("requested_capability", ""),
            "assignee": task.get("assignee", "") or "-",
            "workspace": task.get("workspace", ""),
            "priority": task.get("priority", ""),
            "labels": task.get("labels", []),
            "created_at": task.get("created_at", ""),
            "updated_at": task.get("updated_at", ""),
        },
        event_timeline=[
            {
                "timestamp": event.get("timestamp", ""),
                "event_type": event.get("event_type", ""),
                "from_status": event.get("from_status", ""),
                "to_status": event.get("to_status", ""),
                "actor": event.get("actor", ""),
                "message": event.get("message", ""),
            }
            for event in events
        ],
    )


def list_tasks(root: Path, status_filter: str | None = None) -> TaskListResult:
    """Build a read-only list of task snapshots.

    Loads real ledgers, falling back to example files when no real ledger
    exists, exactly like ``task status`` / ``task events``. No writes are
    performed.

    Args:
        root: Project root directory.
        status_filter: If provided, only return tasks whose ``status`` field
            matches this value exactly.
    """
    tasks = load_tasks(root)

    if status_filter is not None:
        tasks = [task for task in tasks if task.get("status") == status_filter]

    sorted_tasks = sorted(
        tasks,
        key=lambda task: str(task.get("updated_at", "")),
        reverse=True,
    )

    result = TaskListResult()
    for task in sorted_tasks:
        result.tasks.append(
            {
                "task_id": task.get("id", ""),
                "title": task.get("title", ""),
                "status": task.get("status", ""),
                "requested_capability": task.get("requested_capability", ""),
                "assignee": task.get("assignee", "") or "-",
                "created_at": task.get("created_at", ""),
                "updated_at": task.get("updated_at", ""),
            }
        )

    return result
