"""Bounded, value-safe inspection and fixed closure of open execution audits."""

from __future__ import annotations

import os
import re
import stat
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .bounded_ledger import MAX_LEDGER_BYTES, MAX_PHYSICAL_LINES, open_bounded_ledger_session
from .execution_audit_writer import (
    _TERMINAL_TYPES,
    _validate_execution_audit_snapshot,
    inspect_execution_attempt,
    record_execution_recovery_terminal,
)
from .execution_lease import acquire_execution_lease, inspect_execution_lease
from .result import CheckResult, Finding


_TOKEN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,95}$")
_PLAN_HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_OPEN_LIMIT = 128


def _finding(rule_id: str, message: str, *, blocked: bool = False) -> Finding:
    return Finding(
        rule_id=rule_id,
        severity="block" if blocked else "error",
        action="deny" if blocked else "error",
        message=message,
    )


def _sanitized_ledger_failure(status: str = "validation_failed") -> CheckResult:
    return CheckResult(
        status=status if status in {"validation_failed", "error", "blocked"} else "error",
        findings=[
            _finding(
                "execution-recovery-ledger-invalid",
                "Execution recovery ledger validation failed.",
            )
        ],
        next_action="Repair or compact the audit ledger before recovery.",
    )


def _safe_release_lease(lease: Any) -> CheckResult:
    try:
        released = lease.release()
    except BaseException:
        return CheckResult(
            status="error",
            findings=[
                _finding(
                    "execution-recovery-lease-release-failed",
                    "Execution recovery lease cleanup failed.",
                )
            ],
            next_action="Inspect the execution lease before further execution.",
        )
    if released.status != "pass":
        return CheckResult(
            status="error",
            findings=[
                _finding(
                    "execution-recovery-lease-release-failed",
                    "Execution recovery lease cleanup failed.",
                )
            ],
            next_action="Inspect the execution lease before further execution.",
        )
    return CheckResult(status="pass")


@dataclass
class OpenExecutionAttemptsResult(CheckResult):
    attempts: list[dict[str, str]] = field(default_factory=list)
    lease_state: str = "unavailable"
    schema_version: str = "control-plane/fixed-execution-recovery/v1"

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        payload["attempts"] = self.attempts
        payload["lease_state"] = self.lease_state
        payload["schema_version"] = self.schema_version
        return payload


@dataclass
class ExecutionRecoveryResult(CheckResult):
    state: str = "missing"
    attempt_id: str | None = None
    started_event_id: str | None = None
    terminal_event_id: str | None = None
    task_id: str | None = None
    request_id: str | None = None
    plan_hash: str | None = None
    phase: str | None = None
    recovery_action: str | None = None
    lease_state: str = "unavailable"
    historical_process_outcome: str | None = None
    automatic_retry_allowed: bool | None = None
    result_release_allowed: bool | None = None
    committed: bool = False
    schema_version: str = "control-plane/fixed-execution-recovery/v1"

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        payload["state"] = self.state
        for key in (
            "attempt_id",
            "started_event_id",
            "terminal_event_id",
            "task_id",
            "request_id",
            "plan_hash",
            "phase",
            "recovery_action",
            "historical_process_outcome",
            "automatic_retry_allowed",
            "result_release_allowed",
        ):
            value = getattr(self, key)
            if value is not None:
                payload[key] = value
        payload["lease_state"] = self.lease_state
        payload["committed"] = self.committed
        payload["schema_version"] = self.schema_version
        return payload


def _lease_state(root: Path) -> str:
    try:
        observed = inspect_execution_lease(root)
        return observed.lease_state
    except BaseException:
        return "unavailable"


def _validated_open_attempts(root: Path) -> list[dict[str, str]] | CheckResult:
    events_path = root / "tasks" / "events.jsonl"
    opened = open_bounded_ledger_session(events_path)
    if isinstance(opened, CheckResult):
        return opened
    with opened as session:
        validated = _validate_execution_audit_snapshot(
            root,
            session.snapshot,
            tasks_file="tasks/tasks.jsonl",
        )
        if isinstance(validated, CheckResult):
            return validated
        attempts: dict[str, list[dict[str, Any]]] = {}
        for event in validated.records:
            if event.get("event_type") not in (
                {"execution_attempt_started"} | _TERMINAL_TYPES
            ):
                continue
            metadata = event.get("metadata")
            if not isinstance(metadata, dict) or "attempt_id" not in metadata:
                continue
            attempt_id = metadata["attempt_id"]
            if attempt_id not in attempts:
                attempts[attempt_id] = []
            attempts[attempt_id].append(event)
        ordered_open: list[tuple[int, dict[str, str]]] = []
        for attempt_id, chain in attempts.items():
            started = [item for item in chain if item.get("event_type") == "execution_attempt_started"]
            terminal = [item for item in chain if item.get("event_type") in _TERMINAL_TYPES]
            if len(started) == 1 and not terminal:
                event = started[0]
                metadata = event["metadata"]
                ordered_open.append(
                    (event["_line_no"], {
                        "attempt_id": attempt_id,
                        "started_event_id": event["event_id"],
                        "task_id": event["task_id"],
                        "request_id": metadata["request_id"],
                        "plan_hash": metadata["plan_hash"],
                        "phase": metadata["phase"],
                        "recovery_action": "close_outcome_unknown",
                    })
                )
        final = session.verify_current()
        if final.status != "pass":
            return final
        ordered_open.sort(key=lambda item: item[0])
        return [item for _, item in ordered_open]


def list_open_execution_attempts(root: Path) -> OpenExecutionAttemptsResult:
    """List complete open attempts in ledger order with a fixed safe projection."""
    root = root.resolve()
    try:
        attempts = _validated_open_attempts(root)
    except BaseException:
        attempts = _sanitized_ledger_failure("error")
    lease_state = _lease_state(root)
    if isinstance(attempts, CheckResult):
        sanitized = _sanitized_ledger_failure(attempts.status)
        return OpenExecutionAttemptsResult(
            status=sanitized.status,
            findings=list(sanitized.findings),
            next_action=sanitized.next_action,
            lease_state=lease_state,
        )
    if len(attempts) > _OPEN_LIMIT:
        return OpenExecutionAttemptsResult(
            status="validation_failed",
            findings=[
                _finding(
                    "execution-recovery-open-limit-exceeded",
                    "Open execution attempts exceed the bounded recovery result limit.",
                )
            ],
            lease_state=lease_state,
        )
    return OpenExecutionAttemptsResult(
        status="pass",
        attempts=attempts,
        lease_state=lease_state,
        next_action="Inspect one open attempt before fixed recovery closure.",
    )


def _project_attempt(root: Path, attempt_id: str) -> ExecutionRecoveryResult:
    if not isinstance(attempt_id, str) or _TOKEN_RE.fullmatch(attempt_id) is None:
        return ExecutionRecoveryResult(
            status="validation_failed",
            state="invalid",
            attempt_id=None,
            findings=[_finding("invalid-execution-recovery-attempt-id", "Attempt id must be a bounded ASCII token.")],
            recovery_action="manual_audit_review",
            lease_state=_lease_state(root),
        )
    try:
        inspected = inspect_execution_attempt(root, attempt_id)
    except BaseException:
        sanitized = _sanitized_ledger_failure("error")
        return ExecutionRecoveryResult(
            status="error",
            state="invalid",
            attempt_id=None,
            findings=list(sanitized.findings),
            next_action=sanitized.next_action,
            recovery_action="manual_audit_review",
            lease_state="unavailable",
        )
    lease_state = _lease_state(root)
    if inspected.status != "pass":
        if inspected.state == "missing":
            return ExecutionRecoveryResult(
                status="needs_input",
                state="missing",
                attempt_id=attempt_id,
                recovery_action="verify_attempt_id",
                lease_state=lease_state,
                next_action="Confirm the attempt id before recovery.",
            )
        sanitized = _sanitized_ledger_failure(inspected.status)
        return ExecutionRecoveryResult(
            status=sanitized.status,
            state=inspected.state,
            attempt_id=None,
            findings=list(sanitized.findings),
            next_action=sanitized.next_action,
            recovery_action=inspected.recovery_action,
            lease_state=lease_state,
        )
    common = {
        "status": "pass",
        "state": inspected.state,
        "attempt_id": inspected.attempt_id,
        "started_event_id": inspected.started_event_id,
        "terminal_event_id": inspected.terminal_event_id,
        "task_id": inspected.task_id,
        "request_id": inspected.request_id,
        "plan_hash": inspected.plan_hash,
        "phase": inspected.phase,
        "lease_state": lease_state,
    }
    if inspected.state == "awaiting_terminal":
        return ExecutionRecoveryResult(
            **common,
            recovery_action="close_outcome_unknown",
            historical_process_outcome="unknown",
            automatic_retry_allowed=False,
            result_release_allowed=False,
        )
    return ExecutionRecoveryResult(
        **common,
        recovery_action=inspected.recovery_action,
        next_action=inspected.next_action,
    )


def inspect_open_execution_attempt(root: Path, attempt_id: str) -> ExecutionRecoveryResult:
    """Inspect one attempt without mutation."""
    return _project_attempt(root.resolve(), attempt_id)


def _cheap_ledger_bounds(root: Path) -> CheckResult:
    path = root / "tasks" / "events.jsonl"
    try:
        before = path.lstat()
        if (
            not stat.S_ISREG(before.st_mode)
            or stat.S_ISLNK(before.st_mode)
            or before.st_nlink != 1
            or before.st_size > MAX_LEDGER_BYTES
        ):
            raise ValueError
        with path.open("rb") as handle:
            opened = os.fstat(handle.fileno())
            if (
                (before.st_dev, before.st_ino, before.st_size)
                != (opened.st_dev, opened.st_ino, opened.st_size)
                or opened.st_nlink != 1
            ):
                raise ValueError
            line_count = 0
            last_byte = b""
            for chunk in iter(lambda: handle.read(64 * 1024), b""):
                line_count += chunk.count(b"\n")
                last_byte = chunk[-1:]
            if opened.st_size and last_byte != b"\n":
                line_count += 1
        if line_count > MAX_PHYSICAL_LINES:
            raise ValueError
    except (OSError, ValueError):
        return CheckResult(
            status="validation_failed",
            findings=[_finding("execution-recovery-ledger-bound-exceeded", "Execution audit ledger exceeds fixed recovery bounds.")],
        )
    return CheckResult(status="pass")


_acquire_recovery_lease = acquire_execution_lease


def close_open_execution_attempt(
    root: Path,
    *,
    attempt_id: str,
    expected_started_event_id: str,
    expected_plan_hash: str,
    commit: bool = False,
) -> ExecutionRecoveryResult:
    """Preview or commit the fixed outcome-unknown recovery closure."""
    root = root.resolve()
    if not isinstance(attempt_id, str) or _TOKEN_RE.fullmatch(attempt_id) is None:
        return ExecutionRecoveryResult(status="validation_failed", state="invalid", findings=[_finding("invalid-execution-recovery-attempt-id", "Attempt id must be a bounded ASCII token.")])
    if not isinstance(expected_started_event_id, str) or _TOKEN_RE.fullmatch(expected_started_event_id) is None:
        return ExecutionRecoveryResult(status="validation_failed", state="invalid", findings=[_finding("invalid-execution-recovery-started-event-id", "Expected started event id must be a bounded ASCII token.")])
    if not isinstance(expected_plan_hash, str) or _PLAN_HASH_RE.fullmatch(expected_plan_hash) is None:
        return ExecutionRecoveryResult(status="validation_failed", state="invalid", findings=[_finding("invalid-execution-recovery-plan-hash", "Expected plan hash must be a lowercase SHA-256 digest.")])
    if not commit:
        projected = _project_attempt(root, attempt_id)
        if projected.status != "pass" or projected.state != "awaiting_terminal":
            return projected
        if projected.started_event_id != expected_started_event_id:
            projected.status = "blocked"
            projected.findings = [_finding("execution-recovery-started-event-mismatch", "The reviewed started event identity no longer matches.", blocked=True)]
            return projected
        if projected.plan_hash != expected_plan_hash:
            projected.status = "blocked"
            projected.findings = [_finding("execution-recovery-plan-hash-mismatch", "The reviewed execution plan hash no longer matches.", blocked=True)]
            return projected
        projected.next_action = "Re-run with --commit to append the fixed recovery terminal."
        return projected
    cheap = _cheap_ledger_bounds(root)
    if cheap.status != "pass":
        return ExecutionRecoveryResult(status=cheap.status, state="invalid", findings=list(cheap.findings))
    try:
        lease = _acquire_recovery_lease(root)
    except BaseException:
        return ExecutionRecoveryResult(
            status="error",
            state="awaiting_terminal",
            findings=[
                _finding(
                    "execution-recovery-lease-acquire-failed",
                    "Execution recovery lease acquisition failed.",
                )
            ],
            lease_state="unavailable",
            historical_process_outcome="unknown",
            automatic_retry_allowed=False,
            result_release_allowed=False,
        )
    if lease.status != "pass":
        return ExecutionRecoveryResult(status=lease.status, state="awaiting_terminal", findings=list(lease.findings), lease_state=lease.lease_state, historical_process_outcome="unknown", automatic_retry_allowed=False, result_release_allowed=False)
    def close_while_held() -> ExecutionRecoveryResult:
        if not lease.validate():
            return ExecutionRecoveryResult(status="error", state="awaiting_terminal", findings=[_finding("execution-recovery-lease-invalid", "Execution lease validation failed during recovery.")], lease_state=lease.lease_state, historical_process_outcome="unknown", automatic_retry_allowed=False, result_release_allowed=False)
        projected = _project_attempt(root, attempt_id)
        if projected.status != "pass" or projected.state != "awaiting_terminal":
            return projected
        if projected.started_event_id != expected_started_event_id:
            projected.status = "blocked"
            projected.findings = [_finding("execution-recovery-started-event-mismatch", "The reviewed started event identity no longer matches.", blocked=True)]
            return projected
        if projected.plan_hash != expected_plan_hash:
            projected.status = "blocked"
            projected.findings = [_finding("execution-recovery-plan-hash-mismatch", "The reviewed execution plan hash no longer matches.", blocked=True)]
            return projected
        try:
            written = record_execution_recovery_terminal(
                root,
                attempt_id=attempt_id,
                expected_started_event_id=expected_started_event_id,
                expected_plan_hash=expected_plan_hash,
            )
        except BaseException:
            return ExecutionRecoveryResult(
                status="error",
                state="awaiting_terminal",
                attempt_id=attempt_id,
                findings=[
                    _finding(
                        "execution-audit-session-cleanup-failed",
                        "Execution audit session cleanup failed.",
                    )
                ],
                lease_state=lease.lease_state,
                historical_process_outcome="unknown",
                automatic_retry_allowed=False,
                result_release_allowed=False,
            )
        if written.status != "pass":
            if written.committed and any(
                finding.rule_id == "execution-audit-session-cleanup-failed"
                for finding in written.findings
            ):
                findings = [
                    _finding(
                        "execution-audit-session-cleanup-failed",
                        "Execution audit session cleanup failed.",
                    )
                ]
                next_action = "Inspect the audit ledger before further execution."
            else:
                sanitized = _sanitized_ledger_failure(written.status)
                findings = list(sanitized.findings)
                next_action = sanitized.next_action
            return ExecutionRecoveryResult(
                status=written.status,
                state="closed_failed" if written.committed else "awaiting_terminal",
                attempt_id=attempt_id,
                started_event_id=(
                    expected_started_event_id if written.committed else None
                ),
                terminal_event_id=written.event_id if written.committed else None,
                task_id=projected.task_id if written.committed else None,
                request_id=projected.request_id if written.committed else None,
                plan_hash=expected_plan_hash if written.committed else None,
                phase="audit" if written.committed else None,
                recovery_action="none" if written.committed else "close_outcome_unknown",
                committed=written.committed,
                findings=findings,
                next_action=next_action,
                lease_state=lease.lease_state,
                historical_process_outcome="unknown",
                automatic_retry_allowed=False,
                result_release_allowed=False,
            )
        return ExecutionRecoveryResult(
            status="pass",
            state="closed_failed",
            attempt_id=attempt_id,
            started_event_id=expected_started_event_id,
            terminal_event_id=written.event_id,
            task_id=projected.task_id,
            request_id=projected.request_id,
            plan_hash=expected_plan_hash,
            phase="audit",
            recovery_action="none",
            lease_state=lease.lease_state,
            historical_process_outcome="unknown",
            automatic_retry_allowed=False,
            result_release_allowed=False,
            committed=True,
            next_action="Audit lifecycle closed; historical execution result remains withheld.",
        )

    try:
        result = close_while_held()
    except BaseException:
        released = _safe_release_lease(lease)
        if released.status != "pass":
            findings = list(released.findings)
            next_action = released.next_action
        else:
            findings = [
                _finding(
                    "execution-recovery-lease-validation-failed",
                    "Execution recovery lease validation failed.",
                )
            ]
            next_action = "Inspect the execution lease before retrying recovery."
        return ExecutionRecoveryResult(
            status="error",
            state="awaiting_terminal",
            attempt_id=attempt_id,
            findings=findings,
            next_action=next_action,
            lease_state="unavailable",
            historical_process_outcome="unknown",
            automatic_retry_allowed=False,
            result_release_allowed=False,
        )
    released = _safe_release_lease(lease)
    if released.status != "pass":
        return ExecutionRecoveryResult(
            status="error",
            state=result.state,
            attempt_id=attempt_id,
            committed=result.committed,
            findings=list(released.findings),
            next_action=released.next_action,
            lease_state="unavailable",
            historical_process_outcome="unknown",
            automatic_retry_allowed=False,
            result_release_allowed=False,
        )
    return result
