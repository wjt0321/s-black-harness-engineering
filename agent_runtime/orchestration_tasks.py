"""Read-only orchestration task list aggregation for the agent-runtime CLI.

This module provides a minimal ``TaskListResult`` read model for listing task
snapshots. It reuses the existing task ledger loader, supports an optional
``--status`` filter, and performs no writes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .tasks import load_tasks


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
