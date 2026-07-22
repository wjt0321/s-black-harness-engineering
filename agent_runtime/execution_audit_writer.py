"""Dedicated controlled writer for execution lifecycle audit events.

This module does not execute commands. It only constructs reserved audit
events, appends one JSONL line, validates the resulting ledger, and rolls back
that line when a post-check fails.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, BinaryIO
from uuid import uuid4

from jsonschema import ValidationError as JsonSchemaValidationError
from jsonschema import validate

from .bounded_ledger import (
    BoundedLedgerSnapshot,
    BoundedLedgerSession,
    open_bounded_ledger_session,
    snapshot_jsonl,
    snapshot_matches_handle,
    snapshot_prefix_matches_handle,
)
from .ledger_consistency import check_ledger_record_consistency
from .loader import is_safe_to_read, load_schema, normalize_path
from .result import CheckResult, Finding
from .runtime_event_append import (
    RESERVED_EXECUTION_EVENT_TYPES,
    _scan_candidate_content,
)
from .task_validation import (
    DATE_TIME_FORMAT_CHECKER,
    validate_record_objects,
    validate_records,
)
from .tasks import find_task  # Compatibility sentinel; bounded writers do not call it.

_WRITER_ORIGIN = "agent_runtime.execution_audit_writer"
_WRITER_SCHEMA_VERSION = "execution-audit/v1"
_V2_SCHEMA_VERSION = "execution-audit/v2"
_ACTOR = "local-operator"
_STARTED_TYPE = "execution_attempt_started"
_TERMINAL_TYPES = RESERVED_EXECUTION_EVENT_TYPES - {_STARTED_TYPE}
_TOKEN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,95}$")
_PLAN_HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_EVENT_ID_RE = re.compile(r"^evt-([0-9]{8})-([0-9]{3,})$")
_IDENTITY_KEYS = (
    "request_id",
    "plan_hash",
    "adapter_id",
    "capability",
    "operation",
    "writer_origin",
    "writer_schema_version",
)
_MESSAGES = {
    _STARTED_TYPE: "Execution attempt audit started.",
    "execution_succeeded": "Execution attempt audit succeeded.",
    "execution_failed": "Execution attempt audit failed.",
    "execution_cancelled": "Execution attempt audit cancelled.",
}
_LOCK_OFFSET = 2_147_483_647


class _AppendWriteError(OSError):
    def __init__(self, bytes_written: int) -> None:
        super().__init__("execution audit append failed")
        self.bytes_written = bytes_written


@dataclass
class ExecutionAuditWriteResult(CheckResult):
    """Value-safe result for one dedicated audit append."""

    event_id: str | None = None
    attempt_id: str | None = None
    task_id: str | None = None
    request_id: str | None = None
    event_type: str | None = None
    phase: str | None = None
    committed: bool = False
    child_created: bool = False
    audit_incomplete: bool = False
    rolled_back: bool = False
    rollback_error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        result = super().to_dict()
        for key in (
            "event_id",
            "attempt_id",
            "task_id",
            "request_id",
            "event_type",
            "phase",
        ):
            value = getattr(self, key)
            if value is not None:
                result[key] = value
        result["committed"] = self.committed
        result["child_created"] = self.child_created
        result["audit_incomplete"] = self.audit_incomplete
        result["rolled_back"] = self.rolled_back
        if self.rollback_error is not None:
            result["rollback_error"] = self.rollback_error
        return result


@dataclass
class ExecutionAttemptInspectionResult(CheckResult):
    """Read-only safe projection for one execution attempt."""

    state: str = "missing"
    attempt_id: str | None = None
    started_event_id: str | None = None
    terminal_event_id: str | None = None
    task_id: str | None = None
    request_id: str | None = None
    plan_hash: str | None = None
    terminal_type: str | None = None
    phase: str | None = None
    recovery_action: str | None = None

    def to_dict(self) -> dict[str, Any]:
        result = super().to_dict()
        result["state"] = self.state
        for key in (
            "attempt_id",
            "started_event_id",
            "terminal_event_id",
            "task_id",
            "request_id",
            "plan_hash",
            "terminal_type",
            "phase",
            "recovery_action",
        ):
            value = getattr(self, key)
            if value is not None:
                result[key] = value
        return result


@dataclass
class _ExecutionAuditPostCheckResult(CheckResult):
    snapshot: BoundedLedgerSnapshot | None = None


@dataclass
class _LedgerSessionOwnership:
    task_session: BoundedLedgerSession
    event_session: BoundedLedgerSession | None = None
    def close(self) -> CheckResult:
        cleanup_failed = False
        for session in (self.event_session, self.task_session):
            if session is None:
                continue
            try:
                session.close()
            except BaseException:
                cleanup_failed = True
        if cleanup_failed:
            return CheckResult(
                status="error",
                findings=[
                    _finding(
                        "execution-audit-session-cleanup-failed",
                        "Execution audit session cleanup failed.",
                    )
                ],
                next_action="Inspect the audit ledgers before further execution.",
            )
        return CheckResult(status="pass")


def _close_terminal_rejection(
    ownership: _LedgerSessionOwnership,
    result: ExecutionAuditWriteResult,
) -> ExecutionAuditWriteResult:
    cleanup = ownership.close()
    if cleanup.status == "pass":
        return result
    result.status = "error"
    result.findings = list(cleanup.findings)
    result.next_action = cleanup.next_action
    return result


def _finding(
    rule_id: str,
    message: str,
    *,
    severity: str = "error",
    action: str = "error",
    line: int | None = None,
) -> Finding:
    return Finding(
        rule_id=rule_id,
        severity=severity,
        action=action,
        message=message,
        line=line,
    )


def _resolve_ledger_path(
    root: Path, relative: str, *, label: str
) -> CheckResult | Path:
    candidate = root / relative
    path = candidate.parent.resolve() / candidate.name
    if path != root and root not in path.parents:
        return CheckResult(
            status="error",
            findings=[
                _finding(
                    f"{label}-file-outside-root",
                    f"{label.title()} file must be inside the project root.",
                )
            ],
            next_action="Choose project-local JSONL ledger files.",
        )
    if not is_safe_to_read(path) or path.suffix.lower() != ".jsonl":
        return CheckResult(
            status="error",
            findings=[
                _finding(
                    f"unsafe-{label}-file",
                    f"{label.title()} file must be a safe JSONL file.",
                )
            ],
            next_action="Choose project-local JSONL ledger files.",
        )
    normalized = normalize_path(path.relative_to(root))
    if normalized in {"tasks/examples.jsonl", "tasks/events.examples.jsonl"}:
        return CheckResult(
            status="error",
            findings=[
                _finding(
                    "sample-ledger-write-blocked",
                    "Sample ledgers are not valid execution audit targets.",
                )
            ],
            next_action="Use runtime task and event ledgers.",
        )
    if not path.is_file():
        return CheckResult(
            status="error",
            findings=[
                _finding(
                    f"{label}-file-not-found",
                    f"{label.title()} ledger file was not found.",
                )
            ],
            next_action="Create and validate the ledger explicitly before writing.",
        )
    return path


def _has_trailing_newline(path: Path) -> bool:
    if path.stat().st_size == 0:
        return True
    with path.open("rb") as handle:
        handle.seek(-1, 2)
        return handle.read(1) == b"\n"


def _stat_identity(stat: os.stat_result) -> tuple[int, int]:
    return stat.st_dev, stat.st_ino


def _path_identity(path: Path) -> tuple[int, int]:
    return _stat_identity(path.stat())


def _lock_ledger(handle: BinaryIO) -> None:
    if os.name == "nt":
        import msvcrt

        handle.seek(_LOCK_OFFSET)
        msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
        return
    import fcntl

    fcntl.flock(handle.fileno(), fcntl.LOCK_EX)


def _unlock_ledger(handle: BinaryIO) -> None:
    if os.name == "nt":
        import msvcrt

        handle.seek(_LOCK_OFFSET)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        return
    import fcntl

    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _ledger_boundary(
    path: Path, handle: BinaryIO
) -> tuple[int, tuple[int, int]]:
    stat = os.fstat(handle.fileno())
    identity = _stat_identity(stat)
    if _path_identity(path) != identity:
        raise OSError("ledger identity changed")
    return stat.st_size, identity


def _rollback_events_file(
    handle: BinaryIO,
    path: Path,
    original_size: int,
    original_identity: tuple[int, int],
    expected_line: bytes,
    owned_bytes: int,
    original_snapshot: BoundedLedgerSnapshot,
) -> tuple[bool, str | None]:
    try:
        handle.flush()
        stat = os.fstat(handle.fileno())
        if (
            _stat_identity(stat) != original_identity
            or _path_identity(path) != original_identity
            or original_snapshot.identity != original_identity
            or original_snapshot.byte_count != original_size
        ):
            return False, "concurrent-ledger-change"
        if owned_bytes < 0 or owned_bytes > len(expected_line):
            return False, "concurrent-ledger-change"
        if stat.st_size != original_size + owned_bytes:
            return False, "concurrent-ledger-change"
        if not snapshot_prefix_matches_handle(original_snapshot, handle):
            return False, "concurrent-ledger-change"
        handle.seek(original_size)
        suffix = handle.read()
        if (
            len(suffix) != owned_bytes
            or suffix != expected_line[:owned_bytes]
        ):
            return False, "concurrent-ledger-change"
        if not snapshot_prefix_matches_handle(original_snapshot, handle):
            return False, "concurrent-ledger-change"
        handle.seek(original_size)
        final_suffix = handle.read()
        final_stat = os.fstat(handle.fileno())
        if (
            _stat_identity(final_stat) != original_identity
            or _path_identity(path) != original_identity
            or final_stat.st_size != original_size + owned_bytes
            or len(final_suffix) != owned_bytes
            or final_suffix != expected_line[:owned_bytes]
        ):
            return False, "concurrent-ledger-change"
        handle.truncate(original_size)
        handle.flush()
        os.fsync(handle.fileno())
        return True, None
    except OSError:
        return False, "rollback-failed"


def _append_event_line(handle: BinaryIO, line: bytes) -> int:
    handle.seek(0, os.SEEK_END)
    try:
        written = handle.write(line)
    except OSError as exc:
        raise _AppendWriteError(0) from exc
    if written != len(line):
        raise _AppendWriteError(written)
    try:
        handle.flush()
        os.fsync(handle.fileno())
    except OSError as exc:
        raise _AppendWriteError(written) from exc
    return written


def _verify_owned_append(
    handle: BinaryIO,
    path: Path,
    original_size: int,
    original_identity: tuple[int, int],
    expected_line: bytes,
) -> bool:
    try:
        stat = os.fstat(handle.fileno())
        if (
            _stat_identity(stat) != original_identity
            or _path_identity(path) != original_identity
            or stat.st_size != original_size + len(expected_line)
        ):
            return False
        handle.seek(original_size)
        return handle.read(len(expected_line)) == expected_line
    except OSError:
        return False


def _validate_token_fields(values: dict[str, str]) -> CheckResult | None:
    for value in values.values():
        if not isinstance(value, str) or _TOKEN_RE.fullmatch(value) is None:
            return CheckResult(
                status="validation_failed",
                findings=[
                    _finding(
                        "invalid-execution-audit-token",
                        "Execution audit identity must use a bounded ASCII token.",
                    )
                ],
                next_action="Use safe execution identity tokens.",
            )
    return None


def _validate_event_object(root: Path, event: dict[str, Any]) -> CheckResult | None:
    version = event.get("metadata", {}).get("writer_schema_version")
    audit_schema = (
        "tasks/execution-audit-event-v2.schema.json"
        if version == _V2_SCHEMA_VERSION
        else "tasks/execution-audit-event.schema.json"
    )
    for schema_rel, rule_id in (
        ("tasks/event.schema.json", "event-schema-validation-failed"),
        (audit_schema, "execution-audit-schema-validation-failed"),
    ):
        try:
            validate(
                instance=event,
                schema=load_schema(root, schema_rel),
                format_checker=DATE_TIME_FORMAT_CHECKER,
            )
        except JsonSchemaValidationError:
            return CheckResult(
                status="validation_failed",
                findings=[
                    _finding(
                        rule_id,
                        "Constructed execution audit event failed schema validation.",
                    )
                ],
                next_action="Keep the dedicated writer and schema contract aligned.",
            )
    scan_findings = _scan_candidate_content(root, event)
    if scan_findings:
        return CheckResult(
            status="blocked",
            findings=scan_findings,
            next_action="Use only safe execution audit identities and evidence.",
        )
    return None


def _scan_identity_inputs(root: Path, *values: str) -> CheckResult | None:
    scan_findings = _scan_candidate_content(root, {"identity": list(values)})
    if not scan_findings:
        return None
    return CheckResult(
        status="blocked",
        findings=scan_findings,
        next_action="Use only safe execution audit identities.",
    )


def _sanitized_findings(check: CheckResult) -> list[Finding]:
    return [
        Finding(
            rule_id=finding.rule_id,
            severity=finding.severity,
            action=finding.action,
            message="Ledger validation failed.",
            line=finding.line,
            column=finding.column,
        )
        for finding in check.findings
    ]


def _generate_ids(records: list[dict[str, Any]]) -> tuple[str, str]:
    date_part = datetime.now(timezone.utc).strftime("%Y%m%d")
    used_event_ids = {
        record.get("event_id")
        for record in records
        if isinstance(record.get("event_id"), str)
    }
    used_attempt_ids = {
        metadata.get("attempt_id")
        for record in records
        if isinstance((metadata := record.get("metadata")), dict)
    }
    sequence = 1
    while True:
        event_id = f"evt-{date_part}-{sequence:03d}"
        attempt_id = f"attempt-{date_part}-{sequence:03d}"
        if event_id not in used_event_ids and attempt_id not in used_attempt_ids:
            return event_id, attempt_id
        sequence += 1


def _generate_event_id(records: list[dict[str, Any]]) -> str:
    date_part = datetime.now(timezone.utc).strftime("%Y%m%d")
    used: set[str] = set()
    max_sequence = 0
    for record in records:
        event_id = record.get("event_id")
        if not isinstance(event_id, str):
            continue
        used.add(event_id)
        match = _EVENT_ID_RE.fullmatch(event_id)
        if match and match.group(1) == date_part:
            max_sequence = max(max_sequence, int(match.group(2)))
    sequence = max_sequence + 1
    while f"evt-{date_part}-{sequence:03d}" in used:
        sequence += 1
    return f"evt-{date_part}-{sequence:03d}"


def _reserved_records(
    records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return [
        record
        for record in records
        if record.get("event_type") in RESERVED_EXECUTION_EVENT_TYPES
    ]


def _audit_chain_findings(
    root: Path, records: list[dict[str, Any]]
) -> list[Finding]:
    findings: list[Finding] = []
    schema_paths = {
        "execution-audit/v1": "tasks/execution-audit-event.schema.json",
        "execution-audit/v2": "tasks/execution-audit-event-v2.schema.json",
    }
    schemas: dict[str, dict[str, Any]] = {}
    reserved = _reserved_records(records)
    event_ids: set[str] = set()
    append_tokens: set[str] = set()
    groups: dict[str, list[dict[str, Any]]] = {}

    for record in reserved:
        line_no = record.get("_line_no")
        candidate = {key: value for key, value in record.items() if key != "_line_no"}
        metadata = candidate.get("metadata")
        version = (
            metadata.get("writer_schema_version")
            if isinstance(metadata, dict)
            else None
        )
        schema_version = (
            version if version in schema_paths else "execution-audit/v1"
        )
        schema = schemas.get(schema_version)
        if schema is None:
            schema = load_schema(root, schema_paths[schema_version])
            schemas[schema_version] = schema
        try:
            validate(
                instance=candidate,
                schema=schema,
                format_checker=DATE_TIME_FORMAT_CHECKER,
            )
        except JsonSchemaValidationError:
            findings.append(
                _finding(
                    "execution-audit-schema-validation-failed",
                    "Execution audit event failed its dedicated schema.",
                    line=line_no,
                )
            )
            continue
        scan_findings = _scan_candidate_content(root, candidate)
        if scan_findings:
            findings.extend(scan_findings)
            continue
        event_id = record["event_id"]
        if event_id in event_ids:
            findings.append(
                _finding(
                    "duplicate-execution-audit-event-id",
                    "Execution audit event id must be unique.",
                    line=line_no,
                )
            )
        event_ids.add(event_id)
        append_token = record["metadata"]["append_token"]
        if append_token in append_tokens:
            findings.append(
                _finding(
                    "duplicate-execution-audit-append-token",
                    "Execution audit append provenance must be unique.",
                    line=line_no,
                )
            )
        append_tokens.add(append_token)
        attempt_id = record["metadata"]["attempt_id"]
        groups.setdefault(attempt_id, []).append(record)

    for events in groups.values():
        started = [
            event for event in events if event.get("event_type") == _STARTED_TYPE
        ]
        terminals = [
            event for event in events if event.get("event_type") in _TERMINAL_TYPES
        ]
        if not started:
            findings.append(
                _finding(
                    "execution-audit-missing-started",
                    "Execution audit attempt has terminal evidence without a started event.",
                    line=events[0].get("_line_no"),
                )
            )
            continue
        if len(started) > 1:
            findings.append(
                _finding(
                    "execution-audit-duplicate-started",
                    "Execution audit attempt has more than one started event.",
                    line=started[1].get("_line_no"),
                )
            )
        if len(terminals) > 1:
            findings.append(
                _finding(
                    "execution-audit-duplicate-terminal",
                    "Execution audit attempt has more than one terminal event.",
                    line=terminals[1].get("_line_no"),
                )
            )
        if len(started) != 1:
            continue
        start = started[0]
        start_metadata = start["metadata"]
        for terminal in terminals:
            metadata = terminal["metadata"]
            if metadata.get("writer_schema_version") != start_metadata.get(
                "writer_schema_version"
            ):
                findings.append(
                    _finding(
                        "execution-audit-version-mismatch",
                        "Execution audit started and terminal versions must match.",
                        line=terminal.get("_line_no"),
                    )
                )
            if terminal.get("_line_no", 0) <= start.get("_line_no", 0):
                findings.append(
                    _finding(
                        "execution-audit-terminal-before-started",
                        "Execution audit terminal must follow its started event.",
                        line=terminal.get("_line_no"),
                    )
                )
            if metadata.get("started_event_id") != start.get("event_id"):
                findings.append(
                    _finding(
                        "execution-audit-started-reference-mismatch",
                        "Execution audit terminal references a different started event.",
                        line=terminal.get("_line_no"),
                    )
                )
            if terminal.get("task_id") != start.get("task_id") or any(
                metadata.get(key) != start_metadata.get(key)
                for key in _IDENTITY_KEYS
            ):
                findings.append(
                    _finding(
                        "execution-audit-identity-mismatch",
                        "Execution audit terminal identity does not match its started event.",
                        line=terminal.get("_line_no"),
                    )
                )
    return findings


def validate_execution_audit_ledger(
    root: Path,
    *,
    events_file: str | None = None,
    tasks_file: str | None = None,
) -> CheckResult:
    """Validate reserved execution audit chains without writing."""
    root = root.resolve()
    relative = events_file or "tasks/events.jsonl"
    resolved = _resolve_ledger_path(root, relative, label="events")
    if isinstance(resolved, CheckResult):
        return resolved
    opened = open_bounded_ledger_session(resolved)
    if isinstance(opened, CheckResult):
        return opened
    with opened as session:
        validated = _validate_execution_audit_snapshot(
            root,
            session.snapshot,
            tasks_file=tasks_file or "tasks/tasks.jsonl",
        )
        if isinstance(validated, CheckResult):
            return validated
        final_verification = session.verify_current()
        if final_verification.status != "pass":
            return final_verification
        return CheckResult(
            status="pass",
            next_action="Execution audit ledger is consistent.",
        )


def _snapshot_and_validate_execution_audit(
    root: Path,
    path: Path,
    *,
    tasks_file: str = "tasks/tasks.jsonl",
) -> BoundedLedgerSnapshot | CheckResult:
    opened = open_bounded_ledger_session(path)
    if isinstance(opened, CheckResult):
        return opened
    with opened as session:
        return _validate_execution_audit_snapshot(
            root, session.snapshot, tasks_file=tasks_file
        )


def _validate_execution_audit_snapshot(
    root: Path,
    snapshot: BoundedLedgerSnapshot | CheckResult,
    *,
    tasks_file: str,
    task_snapshot: BoundedLedgerSnapshot | None = None,
) -> BoundedLedgerSnapshot | CheckResult:
    if isinstance(snapshot, CheckResult):
        return snapshot
    validation = _validate_execution_audit_records(root, list(snapshot.records))
    if validation.status != "pass":
        return validation
    event_validation = validate_record_objects(root, snapshot.records, "event")
    if event_validation.status != "pass":
        return event_validation
    if task_snapshot is None:
        tasks = _load_validated_task_records(root, tasks_file)
        if isinstance(tasks, CheckResult):
            return tasks
    else:
        task_validation = validate_record_objects(root, task_snapshot.records, "task")
        if task_validation.status != "pass":
            return CheckResult(
                status="validation_failed",
                findings=[
                    _finding(
                        "execution-audit-tasks-invalid",
                        "Execution audit task ledger is invalid.",
                    )
                ],
                next_action="Repair the task ledger before audit validation.",
            )
        tasks = list(task_snapshot.records)
    consistency = check_ledger_record_consistency(
        tasks, snapshot.records
    )
    if consistency.status != "pass":
        return CheckResult(
            status=consistency.status,
            findings=_sanitized_findings(consistency),
            next_action=consistency.next_action,
        )
    return snapshot


def _load_validated_task_records(
    root: Path, tasks_file: str
) -> list[dict[str, Any]] | CheckResult:
    resolved = _resolve_ledger_path(root, tasks_file, label="tasks")
    if isinstance(resolved, CheckResult):
        return CheckResult(
            status="error",
            findings=[
                _finding(
                    "execution-audit-tasks-read-failed",
                    "Execution audit task ledger could not be read.",
                )
            ],
            next_action="Repair the task ledger before audit validation.",
        )
    path = resolved
    try:
        opened = open_bounded_ledger_session(path)
    except (OSError, ValueError, json.JSONDecodeError):
        return CheckResult(
            status="error",
            findings=[
                _finding(
                    "execution-audit-tasks-read-failed",
                    "Execution audit task ledger could not be read.",
                )
            ],
            next_action="Repair the task ledger before audit validation.",
        )
    if isinstance(opened, CheckResult):
        rule_id = (
            "execution-audit-tasks-invalid"
            if opened.status == "validation_failed"
            else "execution-audit-tasks-read-failed"
        )
        return CheckResult(
            status=(
                "validation_failed"
                if rule_id == "execution-audit-tasks-invalid"
                else "error"
            ),
            findings=[
                _finding(
                    rule_id,
                    "Execution audit task ledger is invalid."
                    if rule_id == "execution-audit-tasks-invalid"
                    else "Execution audit task ledger could not be read.",
                )
            ],
            next_action="Repair the task ledger before audit validation.",
        )
    with opened as session:
        snapshot = session.snapshot
        if not isinstance(snapshot, BoundedLedgerSnapshot):
            return CheckResult(
                status="validation_failed",
                findings=[
                    _finding(
                        "execution-audit-tasks-invalid",
                        "Execution audit task ledger is invalid.",
                    )
                ],
                next_action="Repair the task ledger before audit validation.",
            )
        validation = validate_record_objects(root, snapshot.records, "task")
        if validation.status != "pass":
            return CheckResult(
                status="validation_failed",
                findings=[
                    _finding(
                        "execution-audit-tasks-invalid",
                        "Execution audit task ledger is invalid.",
                    )
                ],
                next_action="Repair the task ledger before audit validation.",
            )
        final_verification = session.verify_current()
        if final_verification.status != "pass":
            return CheckResult(
                status="error",
                findings=[
                    _finding(
                        "execution-audit-tasks-read-failed",
                        "Execution audit task ledger could not be read.",
                    )
                ],
                next_action="Repair the task ledger before audit validation.",
            )
        return list(snapshot.records)


def _validate_execution_audit_records(
    root: Path, records: list[dict[str, Any]]
) -> CheckResult:
    findings = _audit_chain_findings(root, records)
    if findings:
        return CheckResult(
            status="validation_failed",
            findings=findings,
            next_action="Repair execution audit chains before further writes.",
        )
    return CheckResult(
        status="pass",
        next_action="Execution audit ledger is consistent.",
    )


def _preflight_ledgers(
    root: Path, tasks_file: str, events_file: str
) -> CheckResult | tuple[
    Path,
    Path,
    list[dict[str, Any]],
    tuple[int, int],
    int,
    BoundedLedgerSnapshot,
    _LedgerSessionOwnership,
]:
    tasks_path = _resolve_ledger_path(root, tasks_file, label="tasks")
    if isinstance(tasks_path, CheckResult):
        return tasks_path
    events_path = _resolve_ledger_path(root, events_file, label="events")
    if isinstance(events_path, CheckResult):
        return events_path
    try:
        preflight_stat = events_path.stat()
        preflight_identity = _stat_identity(preflight_stat)
        preflight_size = preflight_stat.st_size
    except OSError:
        return CheckResult(
            status="error",
            findings=[
                _finding(
                    "events-file-read-failed",
                    "Could not inspect the execution audit ledger.",
                )
            ],
            next_action="Check ledger permissions before retrying.",
        )
    try:
        has_trailing_newline = _has_trailing_newline(events_path)
    except OSError:
        return CheckResult(
            status="error",
            findings=[
                _finding(
                    "events-file-read-failed",
                    "Could not inspect the execution audit ledger.",
                )
            ],
            next_action="Check ledger permissions before retrying.",
        )
    if not has_trailing_newline:
        return CheckResult(
            status="blocked",
            findings=[
                _finding(
                    "events-file-missing-trailing-newline",
                    "Events file must end with a newline before append.",
                    severity="block",
                    action="deny",
                )
            ],
            next_action="Fix the ledger newline explicitly before retrying.",
        )
    task_opened = open_bounded_ledger_session(tasks_path)
    if isinstance(task_opened, CheckResult):
        return task_opened
    ownership = _LedgerSessionOwnership(task_session=task_opened)
    task_snapshot = task_opened.snapshot
    if not isinstance(task_snapshot, BoundedLedgerSnapshot):
        cleanup = ownership.close()
        if cleanup.status != "pass":
            return cleanup
        return task_snapshot
    task_validation = validate_record_objects(root, task_snapshot.records, "task")
    if task_validation.status != "pass":
        cleanup = ownership.close()
        if cleanup.status != "pass":
            return cleanup
        return CheckResult(
            status="validation_failed",
            findings=_sanitized_findings(task_validation),
            next_action=task_validation.next_action,
        )
    try:
        opened = open_bounded_ledger_session(events_path, exclusive=True)
    except Exception:
        cleanup = ownership.close()
        if cleanup.status != "pass":
            return cleanup
        return CheckResult(
            status="error",
            findings=[
                _finding(
                    "execution-audit-session-open-failed",
                    "Execution audit session acquisition failed.",
                )
            ],
            next_action="Inspect the audit ledgers before retrying.",
        )
    except BaseException:
        ownership.close()
        raise
    if isinstance(opened, CheckResult):
        cleanup = ownership.close()
        if cleanup.status != "pass":
            return cleanup
        return opened
    ownership.event_session = opened
    audit_snapshot = _validate_execution_audit_snapshot(
        root,
        opened.snapshot,
        tasks_file=tasks_file,
        task_snapshot=task_snapshot,
    )
    if isinstance(audit_snapshot, CheckResult):
        cleanup = ownership.close()
        if cleanup.status != "pass":
            return cleanup
        return audit_snapshot
    preflight_identity = audit_snapshot.identity
    preflight_size = audit_snapshot.byte_count
    handle = opened.handle
    try:
        handle.seek(0, os.SEEK_END)
        authoritative_size = handle.tell()
        if authoritative_size:
            handle.seek(-1, os.SEEK_END)
        if authoritative_size and handle.read(1) != b"\n":
            cleanup = ownership.close()
            if cleanup.status != "pass":
                return cleanup
            return CheckResult(
                status="blocked",
                findings=[
                    _finding(
                        "events-file-missing-trailing-newline",
                        "Events file must end with a newline before append.",
                        severity="block",
                        action="deny",
                    )
                ],
                next_action="Fix the ledger newline explicitly before retrying.",
            )
    except OSError:
        cleanup = ownership.close()
        if cleanup.status != "pass":
            return cleanup
        return CheckResult(
            status="error",
            findings=[
                _finding(
                    "events-file-read-failed",
                    "Could not inspect the execution audit ledger.",
                )
            ],
            next_action="Check ledger permissions before retrying.",
        )
    loaded = list(audit_snapshot.records)
    return (
        tasks_path,
        events_path,
        loaded,
        preflight_identity,
        preflight_size,
        audit_snapshot,
        ownership,
    )


def _post_check(
    root: Path,
    tasks_file: str,
    events_file: str,
    *,
    session: BoundedLedgerSession,
    task_session: BoundedLedgerSession,
) -> CheckResult:
    task_snapshot = task_session.snapshot
    if not isinstance(task_snapshot, BoundedLedgerSnapshot):
        return task_snapshot
    audit_snapshot = _validate_execution_audit_snapshot(
        root,
        session.refresh(),
        tasks_file=tasks_file,
        task_snapshot=task_snapshot,
    )
    task_current = task_session.verify_current()
    checks = (
        (task_current, True),
        (audit_snapshot if isinstance(audit_snapshot, CheckResult) else CheckResult(status="pass"), False),
    )
    findings: list[Finding] = []
    for check, sanitize in checks:
        if check.status != "pass":
            findings.extend(
                _sanitized_findings(check) if sanitize else check.findings
            )
    if findings:
        return CheckResult(
            status="validation_failed",
            findings=findings,
            next_action="Rollback the current execution audit append.",
        )
    if not isinstance(audit_snapshot, BoundedLedgerSnapshot):
        return CheckResult(
            status="error",
            findings=[
                _finding(
                    "execution-audit-post-check-drift",
                    "Execution audit ledger changed after bounded post-check.",
                )
            ],
            next_action="Rollback the current execution audit append.",
        )
    return _ExecutionAuditPostCheckResult(
        status="pass", snapshot=audit_snapshot
    )


def _append_and_validate(
    root: Path,
    *,
    event: dict[str, Any],
    attempt_id: str,
    tasks_file: str,
    events_file: str,
    events_path: Path,
    preflight_identity: tuple[int, int],
    preflight_size: int,
    preflight_snapshot: BoundedLedgerSnapshot,
    ownership: _LedgerSessionOwnership,
    audit_incomplete_on_failure: bool,
) -> ExecutionAuditWriteResult:
    session = ownership.event_session
    task_session = ownership.task_session
    metadata = event["metadata"]
    result = ExecutionAuditWriteResult(
        status="pass",
        event_id=event["event_id"],
        attempt_id=attempt_id,
        task_id=event["task_id"],
        request_id=metadata["request_id"],
        event_type=event["event_type"],
        phase=metadata["phase"],
        child_created=False,
    )
    handle = session.handle
    try:
        try:
            line = (
                json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n"
            ).encode("utf-8")
        except BaseException:
            result.status = "error"
            result.findings = [
                _finding(
                    "execution-audit-append-construction-failed",
                    "Execution audit append construction failed.",
                )
            ]
            result.audit_incomplete = audit_incomplete_on_failure
            result.next_action = "Inspect the audit ledgers before retrying."
            return result
        try:
            try:
                original_size, original_identity = _ledger_boundary(
                    events_path, handle
                )
            except OSError:
                result.status = "error"
                result.findings = [
                    _finding(
                        "execution-audit-ledger-stat-failed",
                        "Could not bind the append to the validated ledger.",
                    )
                ]
                result.audit_incomplete = audit_incomplete_on_failure
                result.next_action = "Revalidate the ledger before retrying."
                return result
            if (
                original_identity != preflight_identity
                or original_size != preflight_size
                or not snapshot_matches_handle(preflight_snapshot, handle)
            ):
                result.status = "error"
                result.findings = [
                    _finding(
                        "execution-audit-preflight-drift",
                        "Execution audit ledger changed after preflight.",
                    )
                ]
                result.audit_incomplete = audit_incomplete_on_failure
                result.next_action = "Retry against a stable ledger snapshot."
                return result

            owned_bytes = 0
            try:
                owned_bytes = _append_event_line(handle, line)
            except Exception as exc:
                owned_bytes = (
                    exc.bytes_written
                    if isinstance(exc, _AppendWriteError)
                    else 0
                )
                rollback_ok, rollback_error = _rollback_events_file(
                    handle,
                    events_path,
                    original_size,
                    original_identity,
                    line,
                    owned_bytes,
                    preflight_snapshot,
                )
                result.status = "error"
                result.rolled_back = rollback_ok
                result.audit_incomplete = audit_incomplete_on_failure
                result.findings = [
                    _finding(
                        "execution-audit-write-failed",
                        "Execution audit append failed.",
                    )
                ]
                if not rollback_ok:
                    result.findings.append(
                        _finding(
                            "execution-audit-rollback-failed",
                            "Execution audit rollback failed.",
                        )
                    )
                    result.rollback_error = (
                        "concurrent-ledger-change"
                        if rollback_error == "concurrent-ledger-change"
                        else "rollback-failed"
                    )
                result.next_action = (
                    "Inspect and restore the event ledger before retrying."
                )
                return result

            if not _verify_owned_append(
                handle,
                events_path,
                original_size,
                original_identity,
                line,
            ):
                rollback_ok, rollback_error = _rollback_events_file(
                    handle,
                    events_path,
                    original_size,
                    original_identity,
                    line,
                    owned_bytes,
                    preflight_snapshot,
                )
                result.status = "error"
                result.rolled_back = rollback_ok
                result.audit_incomplete = audit_incomplete_on_failure
                result.findings = [
                    _finding(
                        "execution-audit-identity-changed",
                        "Execution audit append lost its ledger identity binding.",
                    )
                ]
                if not rollback_ok:
                    result.findings.append(
                        _finding(
                            "execution-audit-rollback-failed",
                            "Execution audit rollback failed.",
                        )
                    )
                    result.rollback_error = (
                        "concurrent-ledger-change"
                        if rollback_error == "concurrent-ledger-change"
                        else "rollback-failed"
                    )
                result.next_action = (
                    "Revalidate and restore the event ledger before retrying."
                )
                return result

            try:
                post_check = _post_check(
                    root,
                    tasks_file,
                    events_file,
                    session=session,
                    task_session=task_session,
                )
            except Exception:  # noqa: BLE001
                post_check = CheckResult(
                    status="error",
                    findings=[
                        _finding(
                            "execution-audit-post-check-failed",
                            "Execution audit post-check could not complete.",
                        )
                    ],
                    next_action="Rollback the current execution audit append.",
                )
            post_snapshot = getattr(post_check, "snapshot", None)
            if (
                post_check.status == "pass"
                and isinstance(post_snapshot, BoundedLedgerSnapshot)
                and _verify_owned_append(
                handle,
                events_path,
                original_size,
                original_identity,
                line,
                )
                and snapshot_matches_handle(post_snapshot, handle)
            ):
                result.committed = True
                result.next_action = (
                    "Record the terminal audit before exposing an execution outcome."
                    if event["event_type"] == _STARTED_TYPE
                    else "Execution audit attempt is closed."
                )
                return result

            rollback_ok, rollback_error = _rollback_events_file(
                handle,
                events_path,
                original_size,
                original_identity,
                line,
                owned_bytes,
                preflight_snapshot,
            )
            if post_check.status == "pass":
                result.status = "error"
                result.findings = [
                    _finding(
                        "execution-audit-identity-changed",
                        "Execution audit ledger identity changed before commit.",
                    )
                ]
            else:
                result.status = (
                    "error"
                    if post_check.status == "error" or not rollback_ok
                    else "validation_failed"
                )
                result.findings = list(post_check.findings)
            result.rolled_back = rollback_ok
            result.audit_incomplete = audit_incomplete_on_failure
            if not rollback_ok:
                result.status = "error"
                result.findings.append(
                    _finding(
                        "execution-audit-rollback-failed",
                        "Execution audit rollback failed.",
                    )
                )
                result.rollback_error = (
                    "concurrent-ledger-change"
                    if rollback_error == "concurrent-ledger-change"
                    else "rollback-failed"
                )
            result.next_action = (
                "Post-check failed and the current audit append was rolled back."
                if rollback_ok
                else "Restore the event ledger manually before further execution."
            )
            return result
        finally:
            pass
    finally:
        cleanup = ownership.close()
        if cleanup.status != "pass":
            result.status = "error"
            result.findings = list(cleanup.findings)
            result.next_action = cleanup.next_action


def record_execution_attempt_started(
    root: Path,
    *,
    task_id: str,
    request_id: str,
    plan_hash: str,
    adapter_id: str,
    capability: str,
    operation: str,
    tasks_file: str | None = None,
    events_file: str | None = None,
    _schema_version: str = _WRITER_SCHEMA_VERSION,
) -> ExecutionAuditWriteResult:
    """Append one internally constructed execution-attempt started event."""
    root = root.resolve()
    tasks_rel = tasks_file or "tasks/tasks.jsonl"
    events_rel = events_file or "tasks/events.jsonl"
    tokens = _validate_token_fields(
        {
            "task_id": task_id,
            "request_id": request_id,
            "adapter_id": adapter_id,
            "capability": capability,
            "operation": operation,
        }
    )
    if tokens is not None:
        return ExecutionAuditWriteResult(
            status=tokens.status,
            findings=tokens.findings,
            next_action=tokens.next_action,
        )
    identity_scan = _scan_identity_inputs(
        root,
        task_id,
        request_id,
        adapter_id,
        capability,
        operation,
    )
    if identity_scan is not None:
        return ExecutionAuditWriteResult(
            status=identity_scan.status,
            findings=identity_scan.findings,
            next_action=identity_scan.next_action,
        )
    if not isinstance(plan_hash, str) or _PLAN_HASH_RE.fullmatch(plan_hash) is None:
        return ExecutionAuditWriteResult(
            status="validation_failed",
            findings=[
                _finding(
                    "invalid-plan-hash",
                    "Execution audit plan hash must be a lowercase SHA-256 digest.",
                )
            ],
            next_action="Use the reviewed plan hash.",
        )
    preflight = _preflight_ledgers(root, tasks_rel, events_rel)
    if isinstance(preflight, CheckResult):
        return ExecutionAuditWriteResult(
            status=preflight.status,
            findings=preflight.findings,
            next_action=preflight.next_action,
        )
    (
        _,
        events_path,
        records,
        preflight_identity,
        preflight_size,
        preflight_snapshot,
        ownership,
    ) = preflight
    try:
        task_snapshot = ownership.task_session.snapshot
        task_exists = bool(
            isinstance(task_snapshot, BoundedLedgerSnapshot)
            and any(record.get("id") == task_id for record in task_snapshot.records)
        )
        if not task_exists:
            return _close_terminal_rejection(ownership, ExecutionAuditWriteResult(
                status="error",
                findings=[
                    _finding(
                        "unknown-task-id",
                        "Execution audit task was not found in the task ledger.",
                    )
                ],
                next_action="Use an existing task before recording execution audit.",
            ))
        if _schema_version not in {_WRITER_SCHEMA_VERSION, _V2_SCHEMA_VERSION}:
            return _close_terminal_rejection(ownership, ExecutionAuditWriteResult(
                status="validation_failed",
                findings=[_finding(
                    "invalid-execution-audit-version",
                    "Execution audit schema version is not supported.",
                )],
                next_action="Use a supported execution audit schema version.",
            ))
        event_id, attempt_id = _generate_ids(records)
        event = {
            "event_id": event_id,
            "task_id": task_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "actor": _ACTOR,
            "event_type": _STARTED_TYPE,
            "message": _MESSAGES[_STARTED_TYPE],
            "metadata": {
                "writer_origin": _WRITER_ORIGIN,
                "writer_schema_version": _schema_version,
                "append_token": f"append-{uuid4().hex}",
                "attempt_id": attempt_id,
                "request_id": request_id,
                "plan_hash": plan_hash,
                "adapter_id": adapter_id,
                "capability": capability,
                "operation": operation,
                "phase": "pre_spawn_committed",
            },
        }
        invalid = _validate_event_object(root, event)
    except BaseException:
        cleanup = ownership.close()
        if cleanup.status != "pass":
            return ExecutionAuditWriteResult(
                status="error",
                findings=list(cleanup.findings),
                next_action=cleanup.next_action,
            )
        raise
    if invalid is not None:
        return _close_terminal_rejection(ownership, ExecutionAuditWriteResult(
            status=invalid.status,
            findings=invalid.findings,
            next_action=invalid.next_action,
        ))
    return _append_and_validate(
        root,
        event=event,
        attempt_id=attempt_id,
        tasks_file=tasks_rel,
        events_file=events_rel,
        events_path=events_path,
        preflight_identity=preflight_identity,
        preflight_size=preflight_size,
        preflight_snapshot=preflight_snapshot,
        ownership=ownership,
        audit_incomplete_on_failure=False,
    )


def _attempt_events(
    records: list[dict[str, Any]], attempt_id: str
) -> list[dict[str, Any]]:
    return [
        record
        for record in _reserved_records(records)
        if isinstance(record.get("metadata"), dict)
        and record["metadata"].get("attempt_id") == attempt_id
    ]


def inspect_execution_attempt(
    root: Path,
    attempt_id: str,
    *,
    events_file: str | None = None,
    tasks_file: str | None = None,
) -> ExecutionAttemptInspectionResult:
    """Return a safe recovery state for one execution attempt."""
    root = root.resolve()
    if not isinstance(attempt_id, str) or _TOKEN_RE.fullmatch(attempt_id) is None:
        return ExecutionAttemptInspectionResult(
            status="validation_failed",
            state="invalid",
            findings=[
                _finding(
                    "invalid-execution-audit-token",
                    "Attempt id must be a bounded ASCII token.",
                )
            ],
            recovery_action="manual_audit_review",
        )
    identity_scan = _scan_identity_inputs(root, attempt_id)
    if identity_scan is not None:
        return ExecutionAttemptInspectionResult(
            status=identity_scan.status,
            state="invalid",
            findings=identity_scan.findings,
            next_action=identity_scan.next_action,
            recovery_action="manual_audit_review",
        )
    events_rel = events_file or "tasks/events.jsonl"
    resolved = _resolve_ledger_path(root, events_rel, label="events")
    if isinstance(resolved, CheckResult):
        return ExecutionAttemptInspectionResult(
            status=resolved.status,
            state="invalid",
            findings=resolved.findings,
            next_action=resolved.next_action,
            attempt_id=attempt_id,
            recovery_action="manual_audit_review",
        )
    opened = open_bounded_ledger_session(resolved)
    if isinstance(opened, CheckResult):
        snapshot: BoundedLedgerSnapshot | CheckResult = opened
    else:
        with opened as session:
            snapshot = _validate_execution_audit_snapshot(
                root,
                session.snapshot,
                tasks_file=tasks_file or "tasks/tasks.jsonl",
            )
            if not isinstance(snapshot, CheckResult):
                projected = _project_execution_attempt(snapshot, attempt_id)
                final_verification = session.verify_current()
                if final_verification.status == "pass":
                    return projected
                snapshot = final_verification
    return ExecutionAttemptInspectionResult(
        status=snapshot.status,
        state="invalid",
        findings=snapshot.findings,
        next_action=snapshot.next_action,
        attempt_id=attempt_id,
        recovery_action="manual_audit_review",
    )


def _project_execution_attempt(
    snapshot: BoundedLedgerSnapshot, attempt_id: str
) -> ExecutionAttemptInspectionResult:
    events = _attempt_events(list(snapshot.records), attempt_id)
    if not events:
        return ExecutionAttemptInspectionResult(
            status="needs_input",
            state="missing",
            attempt_id=attempt_id,
            recovery_action="verify_attempt_id",
            next_action="Confirm the attempt id before recording terminal audit.",
        )
    started = [event for event in events if event.get("event_type") == _STARTED_TYPE]
    terminals = [event for event in events if event.get("event_type") in _TERMINAL_TYPES]
    if len(started) != 1 or len(terminals) > 1:
        return ExecutionAttemptInspectionResult(
            status="validation_failed",
            state="invalid",
            attempt_id=attempt_id,
            recovery_action="manual_audit_review",
            next_action="Repair the audit chain before further execution.",
        )
    start = started[0]
    start_metadata = start["metadata"]
    common = {
        "attempt_id": attempt_id,
        "started_event_id": start["event_id"],
        "task_id": start["task_id"],
        "request_id": start_metadata["request_id"],
        "plan_hash": start_metadata["plan_hash"],
    }
    if not terminals:
        return ExecutionAttemptInspectionResult(
            status="pass",
            state="awaiting_terminal",
            phase=start_metadata["phase"],
            recovery_action="record_terminal_audit",
            next_action="Record exactly one terminal audit event.",
            **common,
        )
    terminal = terminals[0]
    terminal_type = terminal["event_type"]
    state = {
        "execution_succeeded": "closed_succeeded",
        "execution_failed": "closed_failed",
        "execution_cancelled": "closed_cancelled",
    }[terminal_type]
    return ExecutionAttemptInspectionResult(
        status="pass",
        state=state,
        terminal_event_id=terminal["event_id"],
        terminal_type=terminal_type,
        phase=terminal["metadata"]["phase"],
        recovery_action="none",
        next_action="Execution audit attempt is closed.",
        **common,
    )


def _record_execution_terminal(
    root: Path,
    *,
    attempt_id: str,
    event_type: str,
    phase: str | None = None,
    exit_code: int | None = None,
    duration_bucket: str | None = None,
    output_digest: str | None = None,
    stdout_byte_count: int | None = None,
    stderr_byte_count: int | None = None,
    stdout_truncated: bool | None = None,
    stderr_truncated: bool | None = None,
    guard_status: str | None = None,
    failure_code: str | None = None,
    tasks_file: str | None = None,
    events_file: str | None = None,
    _expected_started_event_id: str | None = None,
    _expected_plan_hash: str | None = None,
    _recovery_fixed: bool = False,
    job_accounting_passed: bool | None = None,
    job_total_processes: int | None = None,
    job_active_processes: int | None = None,
    job_terminated_processes: int | None = None,
    direct_child_reaped: bool | None = None,
    containment_closed: bool | None = None,
) -> ExecutionAuditWriteResult:
    """Append one terminal event derived from an existing open started event."""
    root = root.resolve()
    tasks_rel = tasks_file or "tasks/tasks.jsonl"
    events_rel = events_file or "tasks/events.jsonl"
    if not isinstance(event_type, str) or event_type not in _TERMINAL_TYPES:
        return ExecutionAuditWriteResult(
            status="validation_failed",
            findings=[
                _finding(
                    "invalid-execution-terminal-type",
                    "Terminal audit type is not allowed.",
                )
            ],
            next_action="Use a reserved terminal execution event type.",
        )
    token_values = {"attempt_id": attempt_id}
    if duration_bucket is not None:
        token_values["duration_bucket"] = duration_bucket
    if failure_code is not None:
        token_values["failure_code"] = failure_code
    tokens = _validate_token_fields(token_values)
    if tokens is not None:
        return ExecutionAuditWriteResult(
            status=tokens.status,
            findings=tokens.findings,
            next_action=tokens.next_action,
            audit_incomplete=True,
        )
    identity_scan = _scan_identity_inputs(root, attempt_id)
    if identity_scan is not None:
        return ExecutionAuditWriteResult(
            status=identity_scan.status,
            findings=identity_scan.findings,
            next_action=identity_scan.next_action,
            audit_incomplete=True,
        )
    if output_digest is not None and (
        not isinstance(output_digest, str)
        or _PLAN_HASH_RE.fullmatch(output_digest) is None
    ):
        return ExecutionAuditWriteResult(
            status="validation_failed",
            findings=[
                _finding(
                    "invalid-output-digest",
                    "Output digest must be a lowercase SHA-256 digest.",
                )
            ],
            audit_incomplete=True,
        )
    fixed_phase = {
        "execution_succeeded": "post_run_validated",
        "execution_cancelled": "cancelled",
    }.get(event_type)
    if fixed_phase is not None and phase is not None and phase != fixed_phase:
        return ExecutionAuditWriteResult(
            status="validation_failed",
            findings=[
                _finding(
                    "execution-terminal-phase-mismatch",
                    "Terminal audit phase conflicts with the fixed event contract.",
                )
            ],
            audit_incomplete=True,
            next_action="Use the fixed terminal phase for this event type.",
        )
    preflight = _preflight_ledgers(root, tasks_rel, events_rel)
    if isinstance(preflight, CheckResult):
        return ExecutionAuditWriteResult(
            status=preflight.status,
            findings=preflight.findings,
            next_action=preflight.next_action,
            attempt_id=attempt_id,
            event_type=event_type,
            audit_incomplete=True,
        )
    (
        _,
        events_path,
        records,
        preflight_identity,
        preflight_size,
        preflight_snapshot,
        ownership,
    ) = preflight
    try:
        attempt_events = _attempt_events(records, attempt_id)
        started = [
            event for event in attempt_events if event.get("event_type") == _STARTED_TYPE
        ]
        terminals = [
            event for event in attempt_events if event.get("event_type") in _TERMINAL_TYPES
        ]
    except BaseException:
        cleanup = ownership.close()
        if cleanup.status != "pass":
            return ExecutionAuditWriteResult(
                status="error",
                findings=list(cleanup.findings),
                next_action=cleanup.next_action,
                attempt_id=attempt_id,
                event_type=event_type,
                audit_incomplete=True,
            )
        raise
    if not started:
        return _close_terminal_rejection(ownership, ExecutionAuditWriteResult(
            status="needs_input",
            findings=[
                _finding(
                    "execution-attempt-not-found",
                    "Execution attempt has no matching started audit.",
                )
            ],
            attempt_id=attempt_id,
            event_type=event_type,
            audit_incomplete=True,
            next_action="Confirm the attempt id before recording terminal audit.",
        ))
    if terminals:
        return _close_terminal_rejection(ownership, ExecutionAuditWriteResult(
            status="blocked",
            findings=[
                _finding(
                    "execution-attempt-already-closed",
                    "Execution attempt already has a terminal audit.",
                    severity="block",
                    action="deny",
                )
            ],
            attempt_id=attempt_id,
            event_type=event_type,
            audit_incomplete=False,
            next_action="Do not append a second terminal audit event.",
        ))
    if len(started) != 1:
        return _close_terminal_rejection(ownership, ExecutionAuditWriteResult(
            status="validation_failed",
            findings=[
                _finding(
                    "execution-attempt-chain-invalid",
                    "Execution attempt does not have exactly one started audit.",
                )
            ],
            attempt_id=attempt_id,
            event_type=event_type,
            audit_incomplete=True,
        ))
    start = started[0]
    start_metadata = start["metadata"]
    if _expected_started_event_id is not None and start["event_id"] != _expected_started_event_id:
        return _close_terminal_rejection(ownership, ExecutionAuditWriteResult(
            status="blocked",
            findings=[
                _finding(
                    "execution-recovery-started-event-mismatch",
                    "The reviewed started event identity no longer matches.",
                    severity="block",
                    action="deny",
                )
            ],
            attempt_id=attempt_id,
            event_type=event_type,
            audit_incomplete=True,
        ))
    if _expected_plan_hash is not None and start_metadata["plan_hash"] != _expected_plan_hash:
        return _close_terminal_rejection(ownership, ExecutionAuditWriteResult(
            status="blocked",
            findings=[
                _finding(
                    "execution-recovery-plan-hash-mismatch",
                    "The reviewed execution plan hash no longer matches.",
                    severity="block",
                    action="deny",
                )
            ],
            attempt_id=attempt_id,
            event_type=event_type,
            audit_incomplete=True,
        ))
    try:
        terminal_phase = fixed_phase or phase
        metadata: dict[str, Any] = {
            **{
                key: start_metadata[key]
                for key in (
                    "writer_origin",
                    "writer_schema_version",
                    "attempt_id",
                    "request_id",
                    "plan_hash",
                    "adapter_id",
                    "capability",
                    "operation",
                )
            },
            "append_token": f"append-{uuid4().hex}",
            "phase": terminal_phase,
            "started_event_id": start["event_id"],
        }
        optional_evidence = {
            "exit_code": exit_code,
            "duration_bucket": duration_bucket,
            "output_digest": output_digest,
            "stdout_byte_count": stdout_byte_count,
            "stderr_byte_count": stderr_byte_count,
            "stdout_truncated": stdout_truncated,
            "stderr_truncated": stderr_truncated,
            "guard_status": guard_status,
            "failure_code": failure_code,
            "job_accounting_passed": job_accounting_passed,
            "job_total_processes": job_total_processes,
            "job_active_processes": job_active_processes,
            "job_terminated_processes": job_terminated_processes,
            "direct_child_reaped": direct_child_reaped,
            "containment_closed": containment_closed,
        }
        metadata.update(
            {key: value for key, value in optional_evidence.items() if value is not None}
        )
        if _recovery_fixed:
            metadata = {
                key: value
                for key, value in metadata.items()
                if key
                not in {
                    "exit_code",
                    "duration_bucket",
                    "output_digest",
                    "stdout_byte_count",
                    "stderr_byte_count",
                    "stdout_truncated",
                    "stderr_truncated",
                }
            }
        event_id = _generate_event_id(records)
        event = {
            "event_id": event_id,
            "task_id": start["task_id"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "actor": _ACTOR,
            "event_type": event_type,
            "message": _MESSAGES[event_type],
            "metadata": metadata,
        }
        invalid = _validate_event_object(root, event)
    except BaseException:
        cleanup = ownership.close()
        if cleanup.status != "pass":
            return ExecutionAuditWriteResult(
                status="error",
                findings=list(cleanup.findings),
                next_action=cleanup.next_action,
                attempt_id=attempt_id,
                event_type=event_type,
                audit_incomplete=True,
            )
        raise
    if invalid is not None:
        return _close_terminal_rejection(ownership, ExecutionAuditWriteResult(
            status=invalid.status,
            findings=invalid.findings,
            next_action=invalid.next_action,
            audit_incomplete=True,
        ))
    return _append_and_validate(
        root,
        event=event,
        attempt_id=attempt_id,
        tasks_file=tasks_rel,
        events_file=events_rel,
        events_path=events_path,
        preflight_identity=preflight_identity,
        preflight_size=preflight_size,
        preflight_snapshot=preflight_snapshot,
        ownership=ownership,
        audit_incomplete_on_failure=True,
    )


def record_execution_terminal(
    root: Path,
    *,
    attempt_id: str,
    event_type: str,
    phase: str | None = None,
    exit_code: int | None = None,
    duration_bucket: str | None = None,
    output_digest: str | None = None,
    stdout_byte_count: int | None = None,
    stderr_byte_count: int | None = None,
    stdout_truncated: bool | None = None,
    stderr_truncated: bool | None = None,
    guard_status: str | None = None,
    failure_code: str | None = None,
    tasks_file: str | None = None,
    events_file: str | None = None,
    _schema_version: str | None = None,
    job_accounting_passed: bool | None = None,
    job_total_processes: int | None = None,
    job_active_processes: int | None = None,
    job_terminated_processes: int | None = None,
    direct_child_reaped: bool | None = None,
    containment_closed: bool | None = None,
) -> ExecutionAuditWriteResult:
    """Append one terminal event derived from an existing open started event."""
    return _record_execution_terminal(
        root,
        attempt_id=attempt_id,
        event_type=event_type,
        phase=phase,
        exit_code=exit_code,
        duration_bucket=duration_bucket,
        output_digest=output_digest,
        stdout_byte_count=stdout_byte_count,
        stderr_byte_count=stderr_byte_count,
        stdout_truncated=stdout_truncated,
        stderr_truncated=stderr_truncated,
        guard_status=guard_status,
        failure_code=failure_code,
        tasks_file=tasks_file,
        events_file=events_file,
        job_accounting_passed=job_accounting_passed,
        job_total_processes=job_total_processes,
        job_active_processes=job_active_processes,
        job_terminated_processes=job_terminated_processes,
        direct_child_reaped=direct_child_reaped,
        containment_closed=containment_closed,
    )


def record_execution_recovery_terminal(
    root: Path,
    *,
    attempt_id: str,
    expected_started_event_id: str,
    expected_plan_hash: str,
) -> ExecutionAuditWriteResult:
    """Append the one fixed outcome-unknown recovery terminal."""
    return _record_execution_terminal(
        root,
        attempt_id=attempt_id,
        event_type="execution_failed",
        phase="audit",
        guard_status="not_run",
        failure_code="execution.recovery_outcome_unknown",
        _expected_started_event_id=expected_started_event_id,
        _expected_plan_hash=expected_plan_hash,
        _recovery_fixed=True,
    )
