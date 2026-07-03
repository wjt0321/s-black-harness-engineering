"""Read-only cross-record ledger consistency checks for task/event JSONL files."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .loader import is_safe_to_read
from .result import CheckResult, Finding


VALID_STATUSES = {"planned", "running", "blocked", "finished", "failed"}
TERMINAL_STATUSES = {"finished", "failed"}
STATUS_EVENT_TYPES = {"status_changed", "blocked", "unblocked", "finished", "failed"}


def _load_records(path: Path) -> list[dict[str, Any]]:
    """Load JSONL records and attach their 1-based line number."""
    records: list[dict[str, Any]] = []
    if not path.is_file():
        return records
    with open(path, "r", encoding="utf-8") as fh:
        for line_no, raw_line in enumerate(fh, start=1):
            stripped = raw_line.strip()
            if not stripped:
                continue
            record = __import__("json").loads(stripped)
            if isinstance(record, dict):
                record["_line_no"] = line_no
                records.append(record)
    return records


def _rel(path: Path, root: Path) -> str:
    from .loader import normalize_path

    return normalize_path(path.relative_to(root))


def check_ledger_consistency(
    root: Path,
    tasks_file: str,
    events_file: str,
) -> CheckResult:
    """Check cross-record consistency between a task ledger and an event ledger.

    This function is read-only: it loads both JSONL files, validates cross-record
    constraints, and returns a result. It never writes, appends, or modifies the
    ledger.
    """
    root = root.resolve()
    tasks_path = (root / tasks_file).resolve()
    events_path = (root / events_file).resolve()
    findings: list[Finding] = []

    for label, path in (("tasks", tasks_path), ("events", events_path)):
        if path != root and root not in path.parents:
            return CheckResult(
                status="error",
                findings=[
                    Finding(
                        rule_id="path-outside-root",
                        severity="error",
                        action="error",
                        message=f"{label} file must be inside the project root.",
                    )
                ],
                next_action="Choose project-local JSONL ledger files.",
            )
        if not is_safe_to_read(path) or path.suffix.lower() != ".jsonl":
            return CheckResult(
                status="error",
                findings=[
                    Finding(
                        rule_id="unsafe-ledger-file",
                        severity="error",
                        action="error",
                        message=f"{label} file must be a safe JSONL file.",
                    )
                ],
                next_action="Choose project-local JSONL ledger files.",
            )

    if not tasks_path.is_file():
        return CheckResult(
            status="error",
            findings=[
                Finding(
                    rule_id="file-not-found",
                    severity="error",
                    action="error",
                    message=f"Tasks file not found: {tasks_file}",
                )
            ],
            next_action="Check the tasks file path.",
        )
    if not events_path.is_file():
        return CheckResult(
            status="error",
            findings=[
                Finding(
                    rule_id="file-not-found",
                    severity="error",
                    action="error",
                    message=f"Events file not found: {events_file}",
                )
            ],
            next_action="Check the events file path.",
        )

    try:
        tasks = _load_records(tasks_path)
        events = _load_records(events_path)
    except Exception as exc:  # noqa: BLE001
        return CheckResult(
            status="error",
            findings=[
                Finding(
                    rule_id="read-error",
                    severity="error",
                    action="error",
                    message=f"Could not read ledger files: {exc}",
                )
            ],
            next_action="Check file contents and permissions.",
        )

    tasks_by_id: dict[str, dict[str, Any]] = {}
    for task in tasks:
        task_id = task.get("id")
        if not task_id:
            continue
        if task_id in tasks_by_id:
            findings.append(
                Finding(
                    rule_id="duplicate-task-id",
                    severity="error",
                    action="error",
                    message=f"Duplicate task id: {task_id}",
                    line=task.get("_line_no"),
                )
            )
            continue
        tasks_by_id[task_id] = task

    events_by_task: dict[str, list[dict[str, Any]]] = {}
    for event in events:
        task_id = event.get("task_id")
        event_id = event.get("event_id", "<missing-event-id>")
        line_no = event.get("_line_no")

        if not task_id:
            findings.append(
                Finding(
                    rule_id="missing-task-id",
                    severity="error",
                    action="error",
                    message=f"event_id={event_id} is missing task_id",
                    line=line_no,
                )
            )
            continue

        if task_id not in tasks_by_id:
            findings.append(
                Finding(
                    rule_id="unknown-task-id",
                    severity="error",
                    action="error",
                    message=f"event_id={event_id} references unknown task_id={task_id}",
                    line=line_no,
                )
            )
            continue

        events_by_task.setdefault(task_id, []).append(event)

    for task_id, task_events in events_by_task.items():
        sorted_events = sorted(task_events, key=lambda e: str(e.get("timestamp", "")))

        for idx, event in enumerate(sorted_events):
            event_id = event.get("event_id", "<missing-event-id>")
            line_no = event.get("_line_no")
            event_type = event.get("event_type")
            from_status = event.get("from_status")
            to_status = event.get("to_status")

            if event_type == "created":
                if from_status is not None:
                    findings.append(
                        Finding(
                            rule_id="created-from-status-not-null",
                            severity="error",
                            action="error",
                            message=f"event_id={event_id} created event from_status should be null",
                            line=line_no,
                        )
                    )
                if to_status not in VALID_STATUSES:
                    findings.append(
                        Finding(
                            rule_id="created-invalid-to-status",
                            severity="error",
                            action="error",
                            message=f"event_id={event_id} created event has invalid to_status",
                            line=line_no,
                        )
                    )
                continue

            if event_type in STATUS_EVENT_TYPES:
                if from_status not in VALID_STATUSES:
                    findings.append(
                        Finding(
                            rule_id="invalid-from-status",
                            severity="error",
                            action="error",
                            message=f"event_id={event_id} has invalid from_status",
                            line=line_no,
                        )
                    )
                if to_status not in VALID_STATUSES:
                    findings.append(
                        Finding(
                            rule_id="invalid-to-status",
                            severity="error",
                            action="error",
                            message=f"event_id={event_id} has invalid to_status",
                            line=line_no,
                        )
                    )

                if idx == 0:
                    findings.append(
                        Finding(
                            rule_id="first-event-not-created",
                            severity="error",
                            action="error",
                            message=f"task_id={task_id} first event is not created",
                            line=line_no,
                        )
                    )
                    continue

                prev_to = sorted_events[idx - 1].get("to_status")
                if from_status != prev_to:
                    findings.append(
                        Finding(
                            rule_id="discontinuous-status",
                            severity="error",
                            action="error",
                            message=(
                                f"event_id={event_id} from_status={from_status} does not match "
                                f"previous to_status={prev_to}"
                            ),
                            line=line_no,
                        )
                    )

                prev_event = sorted_events[idx - 1]
                prev_to_status = prev_event.get("to_status")
                if prev_to_status in TERMINAL_STATUSES and to_status not in TERMINAL_STATUSES:
                    findings.append(
                        Finding(
                            rule_id="terminal-status-reverted",
                            severity="error",
                            action="error",
                            message=(
                                f"event_id={event_id} transitions from terminal status "
                                f"{prev_to_status} to {to_status}"
                            ),
                            line=line_no,
                        )
                    )

        latest_to_status = None
        for event in reversed(sorted_events):
            if event.get("to_status") in VALID_STATUSES:
                latest_to_status = event["to_status"]
                break

        task = tasks_by_id[task_id]
        snapshot_status = task.get("status")
        if latest_to_status is not None and snapshot_status != latest_to_status:
            findings.append(
                Finding(
                    rule_id="snapshot-status-mismatch",
                    severity="error",
                    action="error",
                    message=(
                        f"task_id={task_id} snapshot status={snapshot_status} does not match "
                        f"latest event to_status={latest_to_status}"
                    ),
                    line=task.get("_line_no"),
                )
            )

    if findings:
        return CheckResult(
            status="validation_failed",
            findings=findings,
            next_action="Fix ledger consistency errors before writing.",
        )
    return CheckResult(
        status="pass",
        findings=[],
        next_action="Ledger consistency checks passed.",
    )
