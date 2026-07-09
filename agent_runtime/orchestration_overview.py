"""Read-only orchestration overview aggregation for the agent-runtime CLI.

This module provides a minimal ``OverviewSummary`` read model that answers
"what is the current shape of the orchestration surface?" without executing
adapters, writing ledgers, or touching external systems. It is intentionally
small: it reuses existing task/event ledger loaders and only aggregates counts
and recent-task metadata.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .tasks import load_events, load_tasks


@dataclass
class OverviewSummary:
    """Compact read model for the orchestration overview page."""

    status: str = "pass"
    total_tasks: int = 0
    planned_tasks: int = 0
    running_tasks: int = 0
    blocked_tasks: int = 0
    finished_tasks: int = 0
    failed_tasks: int = 0
    total_events: int = 0
    latest_task_updated_at: str | None = None
    recent_tasks: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "summary": {
                "total_tasks": self.total_tasks,
                "planned_tasks": self.planned_tasks,
                "running_tasks": self.running_tasks,
                "blocked_tasks": self.blocked_tasks,
                "finished_tasks": self.finished_tasks,
                "failed_tasks": self.failed_tasks,
                "total_events": self.total_events,
                "latest_task_updated_at": self.latest_task_updated_at,
            },
            "recent_tasks": self.recent_tasks,
        }


def check_overview(root: Path) -> OverviewSummary:
    """Build a read-only overview summary from task and event ledgers.

    Loads real ledgers, falling back to example files when no real ledger
    exists, exactly like the existing ``task status`` / ``task events``
    commands. No writes are performed.
    """
    tasks = load_tasks(root)
    events = load_events(root)

    summary = OverviewSummary(
        total_tasks=len(tasks),
        total_events=len(events),
    )

    for task in tasks:
        status = task.get("status", "")
        if status == "planned":
            summary.planned_tasks += 1
        elif status == "running":
            summary.running_tasks += 1
        elif status == "blocked":
            summary.blocked_tasks += 1
        elif status == "finished":
            summary.finished_tasks += 1
        elif status == "failed":
            summary.failed_tasks += 1

    if tasks:
        latest = max(str(task.get("updated_at", "")) for task in tasks)
        summary.latest_task_updated_at = latest if latest else None

    sorted_tasks = sorted(
        tasks,
        key=lambda task: str(task.get("updated_at", "")),
        reverse=True,
    )
    for task in sorted_tasks[:5]:
        summary.recent_tasks.append(
            {
                "task_id": task.get("id", ""),
                "title": task.get("title", ""),
                "status": task.get("status", ""),
                "requested_capability": task.get("requested_capability", ""),
                "updated_at": task.get("updated_at", ""),
            }
        )

    return summary
