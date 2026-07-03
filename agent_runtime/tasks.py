"""Read-only task ledger queries for the agent-runtime CLI."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .loader import load_jsonl, normalize_path


TASK_FILES = ("tasks/tasks.jsonl",)
TASK_FALLBACK_FILES = ("tasks/examples.jsonl",)
EVENT_FILES = ("tasks/events.jsonl",)
EVENT_FALLBACK_FILES = ("tasks/events.examples.jsonl", "tasks/policy-event.examples.jsonl")


def _load_records(root: Path, relative_paths: tuple[str, ...]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for relative_path in relative_paths:
        path = root / relative_path
        if not path.is_file():
            continue
        for record in load_jsonl(path):
            if isinstance(record, dict):
                item = dict(record)
                item["_source_file"] = normalize_path(path.relative_to(root))
                records.append(item)
    return records


def load_tasks(root: Path) -> list[dict[str, Any]]:
    """Load real task snapshots, falling back to examples when no ledger exists."""
    records = _load_records(root, TASK_FILES)
    return records if records else _load_records(root, TASK_FALLBACK_FILES)


def load_events(root: Path) -> list[dict[str, Any]]:
    """Load real task events, falling back to examples when no ledger exists."""
    records = _load_records(root, EVENT_FILES)
    return records if records else _load_records(root, EVENT_FALLBACK_FILES)


def find_task(root: Path, task_id: str) -> dict[str, Any] | None:
    for task in load_tasks(root):
        if task.get("id") == task_id:
            return task
    return None


def find_task_events(root: Path, task_id: str) -> list[dict[str, Any]]:
    events = [event for event in load_events(root) if event.get("task_id") == task_id]
    return sorted(events, key=lambda event: str(event.get("timestamp", "")))


def render_task_status(task: dict[str, Any]) -> str:
    lines = [
        f"Task: {task.get('id', '-')}",
        f"Title: {task.get('title', '-')}",
        f"Status: {task.get('status', '-')}",
        f"Assignee: {task.get('assignee', '-')}",
    ]
    if task.get("current_step"):
        lines.append(f"Current step: {task['current_step']}")
    if task.get("summary"):
        lines.append(f"Summary: {task['summary']}")
    if task.get("blocked_reason"):
        lines.append(f"Blocked reason: {task['blocked_reason']}")
    if task.get("blocked_message"):
        lines.append(f"Blocked message: {task['blocked_message']}")
    if task.get("failure_reason"):
        lines.append(f"Failure reason: {task['failure_reason']}")
    if task.get("artifacts"):
        lines.append("Artifacts:")
        lines.extend(f"- {artifact}" for artifact in task["artifacts"])
    if task.get("evidence"):
        lines.append("Evidence:")
        for evidence in task["evidence"]:
            if isinstance(evidence, dict):
                description = evidence.get("description") or evidence.get("type") or "evidence"
                ref = evidence.get("ref")
                lines.append(f"- {description}" + (f" ({ref})" if ref else ""))
            else:
                lines.append(f"- {evidence}")
    if task.get("next_action"):
        lines.append(f"Next: {task['next_action']}")
    return "\n".join(lines)


def render_task_events(events: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for event in events:
        timestamp = event.get("timestamp", "-")
        event_type = event.get("event_type", "-")
        from_status = event.get("from_status")
        to_status = event.get("to_status")
        if from_status and to_status:
            transition = f" {from_status} -> {to_status}"
        elif to_status:
            transition = f" -> {to_status}"
        else:
            transition = ""
        message = event.get("message")
        suffix = f" - {message}" if message else ""
        lines.append(f"{timestamp} {event_type}{transition}{suffix}")
    return "\n".join(lines)
