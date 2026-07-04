"""Read-only runtime ledger audit.

Checks cross-system consistency between task ledger, event ledger, and an
adapter execution envelope. This module does not execute adapters, write
ledgers, access networks, or read credential files.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .adapter_validation import _load_envelope, validate_envelope_file
from .ledger_consistency import check_ledger_consistency
from .result import CheckResult, Finding
from .tasks import load_events, load_tasks


TERMINAL_STATUSES = {"finished", "failed"}


@dataclass
class RuntimeLedgerResult:
    """Result of a runtime ledger audit."""

    status: str
    counts: dict[str, int] = field(default_factory=dict)
    findings: list[Finding] = field(default_factory=list)
    next_action: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "status": self.status,
            "counts": self.counts,
        }
        if self.findings:
            d["findings"] = [f.to_dict() for f in self.findings]
        if self.next_action is not None:
            d["next_action"] = self.next_action
        return d


def check_runtime_ledger(
    root: Path,
    tasks_file: str,
    events_file: str,
    envelope_file: str,
) -> RuntimeLedgerResult:
    """Check consistency between task ledger, event ledger, and envelope.

    The function is read-only: it loads both JSONL ledger files and the
    adapter execution envelope JSON file, validates cross-system references,
    and returns a compact summary. It never executes adapters, writes
    ledgers, accesses networks, or reads credential files.
    """
    root = root.resolve()
    findings: list[Finding] = []

    # 1. Base ledger consistency.
    ledger_result = check_ledger_consistency(root, tasks_file, events_file)
    if ledger_result.status == "error":
        findings.append(
            Finding(
                rule_id="ledger-consistency-failed",
                severity="error",
                action="error",
                message="Task/event ledger consistency checks failed due to a read or path error.",
            )
        )
        return RuntimeLedgerResult(
            status="error",
            counts={},
            findings=findings,
            next_action="Fix ledger file paths or contents before running the audit.",
        )

    if ledger_result.status == "validation_failed":
        findings.append(
            Finding(
                rule_id="ledger-consistency-failed",
                severity="error",
                action="error",
                message="Task/event ledger consistency checks failed.",
            )
        )

    # 2. Safe envelope validation and load. Keep schema/consistency validation
    # before extracting cross-system references so malformed artifacts are not
    # silently summarized as runtime findings.
    envelope_validation = validate_envelope_file(root, envelope_file)
    if envelope_validation.status != "pass":
        findings.extend(envelope_validation.findings)
        return RuntimeLedgerResult(
            status=envelope_validation.status,
            counts={},
            findings=findings,
            next_action=envelope_validation.next_action,
        )

    loaded = _load_envelope(root, envelope_file)
    if isinstance(loaded, CheckResult):
        findings.extend(loaded.findings)
        return RuntimeLedgerResult(
            status=loaded.status,
            counts={},
            findings=findings,
            next_action=loaded.next_action,
        )

    envelope, _rel_path = loaded

    tasks = load_tasks(root, explicit_file=tasks_file)
    events = load_events(root, explicit_file=events_file)
    task_ids = {t.get("id") for t in tasks if t.get("id")}
    task_status_by_id = {t.get("id"): t.get("status") for t in tasks if t.get("id")}

    requests: dict[str, dict[str, Any]] = {}
    execution_events: list[dict[str, Any]] = []

    for artifact in envelope.get("artifacts", []):
        artifact_type = artifact.get("artifact_type")
        if artifact_type == "adapter_request":
            request_id = artifact.get("request_id")
            if request_id:
                requests[request_id] = artifact
        elif artifact_type == "execution_event":
            execution_events.append(artifact)

    # 3. adapter_request.task_id must exist in task ledger.
    for request_id, request in requests.items():
        task_id = request.get("task_id")
        if task_id and task_id not in task_ids:
            findings.append(
                Finding(
                    rule_id="request-task-id-unknown",
                    severity="error",
                    action="error",
                    message=f"adapter_request {request_id} references unknown task_id {task_id}",
                )
            )

    # 4. execution_event.task_id must exist in task ledger.
    # 5. execution_event.request_id must reference a known adapter_request.
    event_request_ids: set[str] = set()
    for event in execution_events:
        event_id = event.get("event_id", "<missing-event-id>")
        task_id = event.get("task_id")
        request_id = event.get("request_id")

        if task_id and task_id not in task_ids:
            findings.append(
                Finding(
                    rule_id="event-task-id-unknown",
                    severity="error",
                    action="error",
                    message=f"execution_event {event_id} references unknown task_id {task_id}",
                )
            )

        if request_id:
            event_request_ids.add(request_id)
            if request_id not in requests:
                findings.append(
                    Finding(
                        rule_id="event-request-id-unknown",
                        severity="error",
                        action="error",
                        message=f"execution_event {event_id} references unknown request_id {request_id}",
                    )
                )

    # 6. Look for request_id clues in task ledger event metadata/artifacts (warn only).
    request_ids_in_events: set[str] = set()
    for event in events:
        metadata = event.get("metadata", {})
        if isinstance(metadata, dict) and metadata.get("request_id") in event_request_ids:
            request_ids_in_events.add(metadata["request_id"])
        event_artifacts = event.get("artifacts", [])
        if isinstance(event_artifacts, list):
            for artifact in event_artifacts:
                if isinstance(artifact, dict) and artifact.get("request_id") in event_request_ids:
                    request_ids_in_events.add(artifact["request_id"])

    for request_id in set(requests) - request_ids_in_events:
        findings.append(
            Finding(
                rule_id="request-id-no-event-metadata",
                severity="warn",
                action="warn",
                message=f"No task ledger event metadata/artifact references request_id {request_id}",
            )
        )

    # 7. Terminal task with an envelope request that still expects progress.
    for request_id, request in requests.items():
        task_id = request.get("task_id")
        task_status = task_status_by_id.get(task_id) if task_id else None
        if task_status in TERMINAL_STATUSES:
            context = request.get("context", {})
            preflight = request.get("preflight", {})
            requires_approval = bool(context.get("requires_approval"))
            preflight_status = preflight.get("status")
            if requires_approval or preflight_status in {"needs_approval", "pass"}:
                findings.append(
                    Finding(
                        rule_id="task-terminal-but-request-pending",
                        severity="warn",
                        action="warn",
                        message=(
                            f"task_id {task_id} is terminal ({task_status}) but "
                            f"adapter_request {request_id} still expects progress"
                        ),
                    )
                )

    counts = {
        "tasks": len(tasks),
        "events": len(events),
        "requests": len(requests),
        "execution_events": len(execution_events),
    }

    error_findings = [f for f in findings if f.severity == "error"]
    warn_findings = [f for f in findings if f.severity == "warn"]

    if error_findings:
        return RuntimeLedgerResult(
            status="error",
            counts=counts,
            findings=findings,
            next_action="Fix cross-system consistency errors before proceeding.",
        )

    if warn_findings:
        return RuntimeLedgerResult(
            status="warn",
            counts=counts,
            findings=findings,
            next_action="Review warnings; ledger audit passed with warnings.",
        )

    return RuntimeLedgerResult(
        status="pass",
        counts=counts,
        findings=[],
        next_action="Runtime ledger audit passed.",
    )
