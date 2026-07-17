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

from .ledger_consistency import check_ledger_consistency
from .loader import is_safe_to_read, load_schema, normalize_path
from .result import CheckResult, Finding
from .runtime_event_append import (
    RESERVED_EXECUTION_EVENT_TYPES,
    _scan_candidate_content,
)
from .task_validation import DATE_TIME_FORMAT_CHECKER, validate_records
from .tasks import find_task

_WRITER_ORIGIN = "agent_runtime.execution_audit_writer"
_WRITER_SCHEMA_VERSION = "execution-audit/v1"
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
    path = (root / relative).resolve()
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
) -> tuple[bool, str | None]:
    try:
        stat = os.fstat(handle.fileno())
        if (
            _stat_identity(stat) != original_identity
            or _path_identity(path) != original_identity
            or stat.st_size < original_size
        ):
            return False, "concurrent-ledger-change"
        if owned_bytes < 0 or owned_bytes > len(expected_line):
            return False, "concurrent-ledger-change"
        handle.seek(original_size)
        suffix = handle.read()
        if (
            len(suffix) != owned_bytes
            or suffix != expected_line[:owned_bytes]
        ):
            return False, "concurrent-ledger-change"
        if os.fstat(handle.fileno()).st_size != original_size + owned_bytes:
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


def _load_event_records(path: Path) -> CheckResult | list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line_no, raw_line in enumerate(handle, start=1):
                stripped = raw_line.strip()
                if not stripped:
                    continue
                try:
                    record = json.loads(stripped)
                except json.JSONDecodeError:
                    return CheckResult(
                        status="validation_failed",
                        findings=[
                            _finding(
                                "invalid-json",
                                "Execution audit ledger contains invalid JSON.",
                                line=line_no,
                            )
                        ],
                        next_action="Repair the ledger before recording execution audit.",
                    )
                if isinstance(record, dict):
                    item = dict(record)
                    item["_line_no"] = line_no
                    records.append(item)
    except OSError:
        return CheckResult(
            status="error",
            findings=[
                _finding(
                    "events-file-read-failed",
                    "Could not read the execution audit ledger.",
                )
            ],
            next_action="Check ledger permissions before retrying.",
        )
    return records


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
    for schema_rel, rule_id in (
        ("tasks/event.schema.json", "event-schema-validation-failed"),
        (
            "tasks/execution-audit-event.schema.json",
            "execution-audit-schema-validation-failed",
        ),
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
    schema = load_schema(root, "tasks/execution-audit-event.schema.json")
    reserved = _reserved_records(records)
    event_ids: set[str] = set()
    append_tokens: set[str] = set()
    groups: dict[str, list[dict[str, Any]]] = {}

    for record in reserved:
        line_no = record.get("_line_no")
        candidate = {key: value for key, value in record.items() if key != "_line_no"}
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
    root: Path, *, events_file: str | None = None
) -> CheckResult:
    """Validate reserved execution audit chains without writing."""
    root = root.resolve()
    relative = events_file or "tasks/events.jsonl"
    resolved = _resolve_ledger_path(root, relative, label="events")
    if isinstance(resolved, CheckResult):
        return resolved
    loaded = _load_event_records(resolved)
    if isinstance(loaded, CheckResult):
        return loaded
    return _validate_execution_audit_records(root, loaded)


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
    task_validation = validate_records(root, tasks_file, "task")
    if task_validation.status != "pass":
        return CheckResult(
            status=task_validation.status,
            findings=_sanitized_findings(task_validation),
            next_action=task_validation.next_action,
        )
    event_validation = validate_records(root, events_file, "event")
    if event_validation.status != "pass":
        return CheckResult(
            status=event_validation.status,
            findings=_sanitized_findings(event_validation),
            next_action=event_validation.next_action,
        )
    ledger_validation = check_ledger_consistency(
        root, tasks_file=tasks_file, events_file=events_file
    )
    if ledger_validation.status != "pass":
        return CheckResult(
            status=ledger_validation.status,
            findings=_sanitized_findings(ledger_validation),
            next_action=ledger_validation.next_action,
        )
    audit_validation = validate_execution_audit_ledger(
        root, events_file=events_file
    )
    if audit_validation.status != "pass":
        return audit_validation
    loaded = _load_event_records(events_path)
    if isinstance(loaded, CheckResult):
        return loaded
    try:
        final_stat = events_path.stat()
    except OSError:
        return CheckResult(
            status="error",
            findings=[
                _finding(
                    "events-file-read-failed",
                    "Could not confirm the execution audit ledger snapshot.",
                )
            ],
            next_action="Revalidate the ledger before retrying.",
        )
    if (
        _stat_identity(final_stat) != preflight_identity
        or final_stat.st_size != preflight_size
    ):
        return CheckResult(
            status="error",
            findings=[
                _finding(
                    "execution-audit-preflight-drift",
                    "Execution audit ledger changed during preflight.",
                )
            ],
            next_action="Retry against a stable ledger snapshot.",
        )
    return (
        tasks_path,
        events_path,
        loaded,
        preflight_identity,
        preflight_size,
    )


def _post_check(root: Path, tasks_file: str, events_file: str) -> CheckResult:
    checks = (
        (validate_records(root, tasks_file, "task"), True),
        (validate_records(root, events_file, "event"), True),
        (
            check_ledger_consistency(
                root, tasks_file=tasks_file, events_file=events_file
            ),
            True,
        ),
        (validate_execution_audit_ledger(root, events_file=events_file), False),
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
    return CheckResult(status="pass")


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
    audit_incomplete_on_failure: bool,
) -> ExecutionAuditWriteResult:
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
    line = (
        json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n"
    ).encode("utf-8")
    try:
        handle = events_path.open("r+b")
    except OSError:
        result.status = "error"
        result.findings = [
            _finding(
                "execution-audit-ledger-open-failed",
                "Could not open the execution audit ledger for append.",
            )
        ]
        result.audit_incomplete = audit_incomplete_on_failure
        result.next_action = "Check ledger permissions before retrying."
        return result

    with handle:
        locked = False
        try:
            _lock_ledger(handle)
            locked = True
        except OSError:
            result.status = "error"
            result.findings = [
                _finding(
                    "execution-audit-ledger-lock-failed",
                    "Could not lock the execution audit ledger for append.",
                )
            ]
            result.audit_incomplete = audit_incomplete_on_failure
            result.next_action = "Retry after the current ledger writer finishes."
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
            except OSError as exc:
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
                post_check = _post_check(root, tasks_file, events_file)
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
            if post_check.status == "pass" and _verify_owned_append(
                handle,
                events_path,
                original_size,
                original_identity,
                line,
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
            if locked:
                try:
                    _unlock_ledger(handle)
                except OSError:
                    pass


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
    ) = preflight
    if find_task(root, task_id, explicit_file=tasks_rel) is None:
        return ExecutionAuditWriteResult(
            status="error",
            findings=[
                _finding(
                    "unknown-task-id",
                    "Execution audit task was not found in the task ledger.",
                )
            ],
            next_action="Use an existing task before recording execution audit.",
        )
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
            "writer_schema_version": _WRITER_SCHEMA_VERSION,
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
    if invalid is not None:
        return ExecutionAuditWriteResult(
            status=invalid.status,
            findings=invalid.findings,
            next_action=invalid.next_action,
        )
    return _append_and_validate(
        root,
        event=event,
        attempt_id=attempt_id,
        tasks_file=tasks_rel,
        events_file=events_rel,
        events_path=events_path,
        preflight_identity=preflight_identity,
        preflight_size=preflight_size,
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
    loaded = _load_event_records(resolved)
    if isinstance(loaded, CheckResult):
        return ExecutionAttemptInspectionResult(
            status=loaded.status,
            state="invalid",
            findings=loaded.findings,
            next_action=loaded.next_action,
            attempt_id=attempt_id,
            recovery_action="manual_audit_review",
        )
    audit = _validate_execution_audit_records(root, loaded)
    if audit.status != "pass":
        return ExecutionAttemptInspectionResult(
            status="validation_failed",
            state="invalid",
            findings=audit.findings,
            attempt_id=attempt_id,
            recovery_action="manual_audit_review",
            next_action="Repair the audit chain before further execution.",
        )
    events = _attempt_events(loaded, attempt_id)
    if not events:
        return ExecutionAttemptInspectionResult(
            status="needs_input",
            state="missing",
            attempt_id=attempt_id,
            recovery_action="verify_attempt_id",
            next_action="Confirm the attempt id before recording terminal audit.",
        )
    started = [
        event for event in events if event.get("event_type") == _STARTED_TYPE
    ]
    terminals = [
        event for event in events if event.get("event_type") in _TERMINAL_TYPES
    ]
    if len(started) != 1 or len(terminals) > 1:
        return ExecutionAttemptInspectionResult(
            status="validation_failed",
            state="invalid",
            findings=audit.findings,
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
    ) = preflight
    attempt_events = _attempt_events(records, attempt_id)
    started = [
        event for event in attempt_events if event.get("event_type") == _STARTED_TYPE
    ]
    terminals = [
        event for event in attempt_events if event.get("event_type") in _TERMINAL_TYPES
    ]
    if not started:
        return ExecutionAuditWriteResult(
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
        )
    if terminals:
        return ExecutionAuditWriteResult(
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
        )
    start = started[0]
    start_metadata = start["metadata"]
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
    }
    metadata.update(
        {key: value for key, value in optional_evidence.items() if value is not None}
    )
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
    if invalid is not None:
        return ExecutionAuditWriteResult(
            status=invalid.status,
            findings=invalid.findings,
            next_action=invalid.next_action,
            audit_incomplete=True,
        )
    return _append_and_validate(
        root,
        event=event,
        attempt_id=attempt_id,
        tasks_file=tasks_rel,
        events_file=events_rel,
        events_path=events_path,
        preflight_identity=preflight_identity,
        preflight_size=preflight_size,
        audit_incomplete_on_failure=True,
    )
