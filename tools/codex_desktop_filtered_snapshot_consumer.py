"""Standalone Stage 29 validator for filtered snapshot reader results."""

from __future__ import annotations

import hashlib
import json
import re
import sys
from dataclasses import dataclass
from pathlib import PurePosixPath, PureWindowsPath
from typing import Any, BinaryIO, TextIO

VALIDATION_SCHEMA_VERSION = (
    "control-plane/filtered-snapshot-host-consumer-validation/v1"
)
CONSUMER_ID = "codex-desktop-filtered-snapshot-consumer/v1"
READER_SCHEMA_VERSION = "control-plane/codex-desktop-snapshot-read/v3"
READER_ID = "codex-desktop-filtered-envelope-snapshot-json-reader/v3"
FILTERED_SCHEMA_VERSION = "control-plane/filtered-envelope-snapshot/v1"
FILTER_SCHEMA_VERSION = "control-plane/envelope-snapshot-filter/v1"
MAX_INPUT_BYTES = 1024 * 1024
MAX_OUTPUT_BYTES = 64 * 1024
CHECK_IDS = (
    "document_shape",
    "schema_version",
    "reader_status",
    "lifecycle",
    "guarantees",
    "source_scope_identity",
    "filter_identity",
    "representation_links",
    "view_identity",
    "safe_sections",
    "filter_semantics",
)
EXPECTED_PHASES = (
    "created",
    "scoping",
    "producing",
    "validating",
    "reading",
    "filtering",
    "ready",
    "closed",
)
EXPECTED_READER_GUARANTEES = {
    "requires_explicit_user_action": True,
    "one_shot": True,
    "read_only": True,
    "reads_snapshot_json": True,
    "reads_html": False,
    "writes_files": False,
    "accesses_network": False,
    "starts_service": False,
    "runs_fixed_read_processes": True,
    "executes_candidate_commands": False,
    "executes_adapters": False,
    "executes_descriptor_argv": False,
    "auto_retries": False,
    "bounded_output": True,
    "reads_envelope_scope": True,
    "writes_ledgers": False,
    "allows_arbitrary_paths": False,
    "scans_envelope_secrets": True,
    "filters_safe_summaries": True,
    "allows_arbitrary_queries": False,
    "persists_filtered_views": False,
}
RESULT_GUARANTEES = {
    "stdin_only": True,
    "read_only": True,
    "reads_filtered_snapshot": True,
    "writes_files": False,
    "accesses_network": False,
    "starts_service": False,
    "executes_reader": False,
    "executes_commands": False,
    "executes_adapters": False,
    "persists_input": False,
    "bounded_input": True,
    "bounded_output": True,
}
_TOP_LEVEL_KEYS = {
    "status",
    "schema_version",
    "reader",
    "source",
    "lifecycle",
    "handoff",
    "representation",
    "findings",
    "guarantees",
    "next_action",
}
_SOURCE_KEYS = {
    "project_root",
    "relative_envelope",
    "envelope_content_id",
    "scope_id",
    "filter_id",
}
_LIFECYCLE_KEYS = {"state", "phases"}
_HANDOFF_KEYS = {"status", "exit_code", "source_handoff_id"}
_REPRESENTATION_KEYS = {
    "status",
    "type",
    "media_type",
    "encoding",
    "exit_code",
    "base_snapshot_id",
    "view_id",
    "payload",
}
_FILTERED_KEYS = {
    "status",
    "schema_version",
    "source",
    "filter",
    "summary",
    "sections",
    "view_id",
}
_FILTERED_SOURCE_KEYS = {"base_snapshot_id", "scope_id", "filter_id"}
_FILTER_KEYS = {"schema_version", "task_id", "request_id"}
_SUMMARY_KEYS = {
    "matched",
    "run_count",
    "approval_count",
    "artifact_count",
    "section_statuses",
}
_SECTION_NAMES = {"runs", "approvals", "artifacts", "reports"}
_COLLECTION_SECTION_KEYS = {
    "status",
    "next_action",
    "scope",
    "availability",
}
_REPORT_KEYS = {
    "status",
    "scope",
    "availability",
    "reason",
    "message",
    "command_hint",
}
_RUN_KEYS = {
    "request_id",
    "task_id",
    "adapter_id",
    "capability",
    "operation",
    "mode",
    "status",
    "started_at",
    "ended_at",
}
_APPROVAL_KEYS = {
    "approval_id",
    "request_id",
    "task_id",
    "adapter_id",
    "operation",
    "target",
    "status",
    "requested_at",
    "resolved_at",
    "resolver",
}
_ARTIFACT_KEYS = {
    "artifact_id",
    "artifact_type",
    "task_id",
    "request_id",
    "producer",
    "timestamp",
    "summary",
    "safe_to_preview",
}
_NEXT_ACTION_KEYS = {"code", "message"}
_SHA256_RE = re.compile(r"sha256:[0-9a-f]{64}\Z")
_TASK_RE = re.compile(r"task-[0-9]{8}-[0-9]{3,}\Z")
_REQUEST_RE = re.compile(r"req-[0-9]{8}-[0-9]{3,}\Z")


@dataclass(frozen=True)
class ConsumerFinding:
    """Value-safe finding emitted by the standalone consumer."""

    rule_id: str
    severity: str
    action: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {
            "rule_id": self.rule_id,
            "severity": self.severity,
            "action": self.action,
            "message": self.message,
        }


@dataclass(frozen=True)
class FilteredSnapshotValidationResult:
    """Deterministic validation result for one input document."""

    status: str
    source: dict[str, str | None]
    checks: tuple[dict[str, str], ...]
    findings: tuple[ConsumerFinding, ...] = ()
    next_action: dict[str, str] | None = None

    def exit_code(self) -> int:
        return {
            "pass": 0,
            "error": 1,
            "blocked": 2,
            "validation_failed": 5,
        }.get(self.status, 1)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "schema_version": VALIDATION_SCHEMA_VERSION,
            "consumer": CONSUMER_ID,
            "source": self.source,
            "checks": list(self.checks),
            "findings": [finding.to_dict() for finding in self.findings],
            "guarantees": dict(RESULT_GUARANTEES),
            "next_action": self.next_action,
        }


class DuplicateJSONKeyError(ValueError):
    """Raised when an input object contains an ambiguous duplicate key."""


class InputDocumentError(ValueError):
    """Bounded, value-safe stdin parsing failure."""

    def __init__(
        self,
        rule_id: str,
        message: str,
        *,
        status: str = "validation_failed",
    ) -> None:
        super().__init__(message)
        self.rule_id = rule_id
        self.message = message
        self.status = status


def _canonical_id(payload: dict[str, Any]) -> str:
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(canonical).hexdigest()}"


def _is_hash(value: object) -> bool:
    return isinstance(value, str) and _SHA256_RE.fullmatch(value) is not None


def _is_plain_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _safe_source(document: object) -> dict[str, str | None]:
    source = {
        "base_snapshot_id": None,
        "scope_id": None,
        "filter_id": None,
        "view_id": None,
    }
    if not isinstance(document, dict):
        return source
    wrapper_source = document.get("source")
    representation = document.get("representation")
    if isinstance(wrapper_source, dict):
        for key in ("scope_id", "filter_id"):
            value = wrapper_source.get(key)
            if _is_hash(value):
                source[key] = value
    if isinstance(representation, dict):
        for key in ("base_snapshot_id", "view_id"):
            value = representation.get(key)
            if _is_hash(value):
                source[key] = value
    return source


def _finding(rule_id: str, *, status: str, message: str) -> ConsumerFinding:
    if status == "blocked":
        severity = "warning"
        action = "block"
    elif status == "error":
        severity = "error"
        action = "retry"
    else:
        severity = "error"
        action = "reject"
    return ConsumerFinding(
        rule_id=rule_id,
        severity=severity,
        action=action,
        message=message,
    )


def _next_action(status: str) -> dict[str, str]:
    if status == "pass":
        return {
            "code": "accept_filtered_snapshot",
            "message": "The filtered snapshot passed local consumer validation.",
        }
    if status == "blocked":
        return {
            "code": "inspect_reader_result",
            "message": "Inspect the reader result before attempting another read.",
        }
    if status == "validation_failed":
        return {
            "code": "reject_filtered_snapshot",
            "message": "Reject the filtered snapshot because validation failed.",
        }
    return {
        "code": "retry_with_bounded_stdin",
        "message": "Retry with one bounded UTF-8 JSON document on stdin.",
    }


def _result(
    *,
    status: str,
    document: object,
    check_states: dict[str, str],
    findings: list[ConsumerFinding] | None = None,
) -> FilteredSnapshotValidationResult:
    return FilteredSnapshotValidationResult(
        status=status,
        source=_safe_source(document),
        checks=tuple(
            {"check_id": check_id, "status": check_states[check_id]}
            for check_id in CHECK_IDS
        ),
        findings=tuple(findings or ()),
        next_action=_next_action(status),
    )


def _failed_result(
    *,
    status: str,
    document: object,
    check_states: dict[str, str],
    check_id: str,
    rule_id: str,
    message: str,
) -> FilteredSnapshotValidationResult:
    check_states[check_id] = "failed"
    return _result(
        status=status,
        document=document,
        check_states=check_states,
        findings=[_finding(rule_id, status=status, message=message)],
    )


def _top_shape_is_valid(document: object) -> bool:
    if not isinstance(document, dict) or set(document) != _TOP_LEVEL_KEYS:
        return False
    if not all(
        isinstance(document.get(key), str)
        for key in ("status", "schema_version", "reader")
    ):
        return False
    if not all(
        isinstance(document.get(key), dict)
        for key in (
            "source",
            "lifecycle",
            "handoff",
            "representation",
            "guarantees",
            "next_action",
        )
    ):
        return False
    return isinstance(document.get("findings"), list)


def _canonical_relative_envelope(value: object) -> bool:
    if not isinstance(value, str) or not value or value.strip() != value:
        return False
    if "\\" in value:
        return False
    windows_path = PureWindowsPath(value)
    posix_path = PurePosixPath(value)
    if (
        windows_path.is_absolute()
        or bool(windows_path.drive)
        or posix_path.is_absolute()
        or value.startswith("//")
        or str(posix_path) != value
        or any(part in {"", ".", ".."} for part in posix_path.parts)
    ):
        return False
    parts = posix_path.parts
    return (
        len(parts) == 2
        and parts[0] == "adapters"
        and value.lower().endswith(".json")
    ) or (
        len(parts) >= 3
        and parts[:2] == ("drafts", "runtime")
        and value.lower().endswith(".envelope.json")
    )


def _filter_value_valid(value: object, pattern: re.Pattern[str]) -> bool:
    if value is None:
        return True
    if not isinstance(value, str):
        return False
    try:
        encoded = value.encode("ascii")
    except UnicodeEncodeError:
        return False
    return len(encoded) <= 128 and pattern.fullmatch(value) is not None


def _rows_have_exact_shape(
    rows: object,
    *,
    keys: set[str],
    bool_key: str | None = None,
) -> bool:
    if not isinstance(rows, list):
        return False
    for row in rows:
        if not isinstance(row, dict) or set(row) != keys:
            return False
        for key, value in row.items():
            if key == bool_key:
                if not isinstance(value, bool):
                    return False
            elif not isinstance(value, str):
                return False
    return True


def _safe_sections_valid(payload: dict[str, Any]) -> bool:
    summary = payload.get("summary")
    sections = payload.get("sections")
    if not isinstance(summary, dict) or set(summary) != _SUMMARY_KEYS:
        return False
    if not isinstance(sections, dict) or set(sections) != _SECTION_NAMES:
        return False
    if not isinstance(summary.get("matched"), bool):
        return False
    for key in ("run_count", "approval_count", "artifact_count"):
        if not _is_plain_int(summary.get(key)) or summary[key] < 0:
            return False
    statuses = summary.get("section_statuses")
    if (
        not isinstance(statuses, dict)
        or set(statuses) != _SECTION_NAMES
        or any(not isinstance(value, str) for value in statuses.values())
    ):
        return False

    collections = (
        ("runs", "runs", _RUN_KEYS, None),
        ("approvals", "approvals", _APPROVAL_KEYS, None),
        ("artifacts", "artifacts", _ARTIFACT_KEYS, "safe_to_preview"),
    )
    for section_name, collection_name, row_keys, bool_key in collections:
        section = sections.get(section_name)
        expected_keys = _COLLECTION_SECTION_KEYS | {collection_name}
        if not isinstance(section, dict) or set(section) != expected_keys:
            return False
        if (
            section.get("status") != "pass"
            or section.get("scope") != "envelope"
            or section.get("availability") != "stable_limited"
            or not isinstance(section.get("next_action"), str)
            or not _rows_have_exact_shape(
                section.get(collection_name),
                keys=row_keys,
                bool_key=bool_key,
            )
        ):
            return False

    reports = sections.get("reports")
    if not isinstance(reports, dict) or set(reports) != _REPORT_KEYS:
        return False
    if (
        reports.get("status") != "unavailable"
        or reports.get("scope") != "request"
        or reports.get("availability") != "stable_limited"
        or reports.get("reason") != "request_context_required"
        or not isinstance(reports.get("message"), str)
        or not isinstance(reports.get("command_hint"), str)
    ):
        return False

    runs = sections["runs"]["runs"]
    approvals = sections["approvals"]["approvals"]
    artifacts = sections["artifacts"]["artifacts"]
    if summary["run_count"] != len(runs):
        return False
    if summary["approval_count"] != len(approvals):
        return False
    if summary["artifact_count"] != len(artifacts):
        return False
    expected_statuses = {
        name: sections[name]["status"] for name in _SECTION_NAMES
    }
    return statuses == expected_statuses


def _filter_semantics_valid(payload: dict[str, Any]) -> bool:
    filter_spec = payload["filter"]
    summary = payload["summary"]
    sections = payload["sections"]
    task_id = filter_spec["task_id"]
    request_id = filter_spec["request_id"]
    runs = sections["runs"]["runs"]
    approvals = sections["approvals"]["approvals"]
    artifacts = sections["artifacts"]["artifacts"]
    if summary["matched"] is not bool(runs or approvals or artifacts):
        return False

    if task_id is None:
        return all(row["request_id"] == request_id for row in runs) and all(
            row["request_id"] == request_id
            for row in (*approvals, *artifacts)
        )

    if request_id is None:
        selected_requests = {row["request_id"] for row in runs if row["request_id"]}
        if any(row["task_id"] != task_id for row in runs):
            return False
        return all(
            row["task_id"] == task_id or row["request_id"] in selected_requests
            for row in (*approvals, *artifacts)
        )

    selected_requests = {row["request_id"] for row in runs if row["request_id"]}
    if any(
        row["task_id"] != task_id or row["request_id"] != request_id
        for row in runs
    ):
        return False
    return all(
        row["request_id"] in selected_requests
        for row in (*approvals, *artifacts)
    )


def validate_filtered_snapshot_document(
    document: object,
) -> FilteredSnapshotValidationResult:
    """Validate one parsed filtered v3 reader result without side effects."""
    states = {check_id: "not_run" for check_id in CHECK_IDS}

    if not _top_shape_is_valid(document):
        return _failed_result(
            status="validation_failed",
            document=document,
            check_states=states,
            check_id="document_shape",
            rule_id="filtered-consumer-document-shape",
            message="The input does not match the filtered reader result shape.",
        )
    states["document_shape"] = "pass"
    assert isinstance(document, dict)

    representation_candidate = document["representation"]
    payload_candidate = representation_candidate.get("payload")
    filter_candidate = (
        payload_candidate.get("filter")
        if isinstance(payload_candidate, dict)
        else None
    )
    nested_schema_unsupported = (
        isinstance(payload_candidate, dict)
        and isinstance(payload_candidate.get("schema_version"), str)
        and payload_candidate.get("schema_version") != FILTERED_SCHEMA_VERSION
    ) or (
        isinstance(filter_candidate, dict)
        and isinstance(filter_candidate.get("schema_version"), str)
        and filter_candidate.get("schema_version") != FILTER_SCHEMA_VERSION
    )
    if (
        document["schema_version"] != READER_SCHEMA_VERSION
        or document["reader"] != READER_ID
        or nested_schema_unsupported
    ):
        return _failed_result(
            status="blocked",
            document=document,
            check_states=states,
            check_id="schema_version",
            rule_id="filtered-consumer-unsupported-schema",
            message="The reader result schema or reader id is unsupported.",
        )
    states["schema_version"] = "pass"

    if document["status"] != "ready":
        return _failed_result(
            status="blocked",
            document=document,
            check_states=states,
            check_id="reader_status",
            rule_id="filtered-consumer-reader-not-ready",
            message="The reader result is not ready for filtered display.",
        )
    handoff = document["handoff"]
    representation = document["representation"]
    next_action = document["next_action"]
    if (
        set(handoff) != _HANDOFF_KEYS
        or handoff.get("status") != "pass"
        or handoff.get("exit_code") != 0
        or not _is_hash(handoff.get("source_handoff_id"))
        or representation.get("status") != "pass"
        or representation.get("exit_code") != 0
        or document["findings"] != []
        or set(next_action) != _NEXT_ACTION_KEYS
        or next_action.get("code") != "filtered_snapshot_loaded"
        or not isinstance(next_action.get("message"), str)
    ):
        return _failed_result(
            status="validation_failed",
            document=document,
            check_states=states,
            check_id="reader_status",
            rule_id="filtered-consumer-reader-status-invalid",
            message="The ready reader result has inconsistent status metadata.",
        )
    states["reader_status"] = "pass"

    lifecycle = document["lifecycle"]
    if (
        set(lifecycle) != _LIFECYCLE_KEYS
        or lifecycle.get("state") != "closed"
        or lifecycle.get("phases") != list(EXPECTED_PHASES)
    ):
        return _failed_result(
            status="validation_failed",
            document=document,
            check_states=states,
            check_id="lifecycle",
            rule_id="filtered-consumer-lifecycle-invalid",
            message="The reader lifecycle is not the frozen closed sequence.",
        )
    states["lifecycle"] = "pass"

    guarantees = document["guarantees"]
    if (
        set(guarantees) != set(EXPECTED_READER_GUARANTEES)
        or any(not isinstance(value, bool) for value in guarantees.values())
    ):
        return _failed_result(
            status="validation_failed",
            document=document,
            check_states=states,
            check_id="guarantees",
            rule_id="filtered-consumer-guarantee-shape",
            message="The reader guarantees do not match the strict field shape.",
        )
    if guarantees != EXPECTED_READER_GUARANTEES:
        return _failed_result(
            status="blocked",
            document=document,
            check_states=states,
            check_id="guarantees",
            rule_id="filtered-consumer-guarantee-unsafe",
            message="The reader guarantees contain an unsafe value.",
        )
    states["guarantees"] = "pass"

    source = document["source"]
    payload = representation.get("payload")
    payload_source = payload.get("source") if isinstance(payload, dict) else None
    if (
        set(source) != _SOURCE_KEYS
        or source.get("project_root") != "project_root"
        or not _canonical_relative_envelope(source.get("relative_envelope"))
        or not _is_hash(source.get("envelope_content_id"))
        or not _is_hash(source.get("scope_id"))
        or not isinstance(payload_source, dict)
        or source["scope_id"]
        != _canonical_id(
            {
                "relative_envelope": source["relative_envelope"],
                "envelope_content_id": source["envelope_content_id"],
            }
        )
        or payload_source.get("scope_id") != source["scope_id"]
    ):
        return _failed_result(
            status="validation_failed",
            document=document,
            check_states=states,
            check_id="source_scope_identity",
            rule_id="filtered-consumer-scope-id-mismatch",
            message="The envelope scope identity is invalid or inconsistent.",
        )
    states["source_scope_identity"] = "pass"

    filter_spec = payload.get("filter") if isinstance(payload, dict) else None
    if not isinstance(filter_spec, dict) or set(filter_spec) != _FILTER_KEYS:
        return _failed_result(
            status="validation_failed",
            document=document,
            check_states=states,
            check_id="filter_identity",
            rule_id="filtered-consumer-filter-shape",
            message="The structured filter does not match its strict shape.",
        )
    task_id = filter_spec.get("task_id")
    request_id = filter_spec.get("request_id")
    if (
        filter_spec.get("schema_version") != FILTER_SCHEMA_VERSION
        or (task_id is None and request_id is None)
        or not _filter_value_valid(task_id, _TASK_RE)
        or not _filter_value_valid(request_id, _REQUEST_RE)
        or not _is_hash(source.get("filter_id"))
        or payload_source.get("filter_id") != source.get("filter_id")
        or source.get("filter_id") != _canonical_id(filter_spec)
    ):
        return _failed_result(
            status="validation_failed",
            document=document,
            check_states=states,
            check_id="filter_identity",
            rule_id="filtered-consumer-filter-id-mismatch",
            message="The structured filter identity is invalid or inconsistent.",
        )
    states["filter_identity"] = "pass"

    if (
        set(representation) != _REPRESENTATION_KEYS
        or representation.get("type") != "snapshot-json"
        or representation.get("media_type") != "application/json; charset=utf-8"
        or representation.get("encoding") != "utf-8"
        or not _is_hash(representation.get("base_snapshot_id"))
        or not _is_hash(representation.get("view_id"))
        or not isinstance(payload, dict)
        or set(payload) != _FILTERED_KEYS
        or payload.get("status") != "pass"
        or payload.get("schema_version") != FILTERED_SCHEMA_VERSION
        or set(payload_source) != _FILTERED_SOURCE_KEYS
        or not all(_is_hash(payload_source.get(key)) for key in _FILTERED_SOURCE_KEYS)
        or payload_source.get("base_snapshot_id")
        != representation.get("base_snapshot_id")
        or payload_source.get("scope_id") != source.get("scope_id")
        or payload_source.get("filter_id") != source.get("filter_id")
    ):
        return _failed_result(
            status="validation_failed",
            document=document,
            check_states=states,
            check_id="representation_links",
            rule_id="filtered-consumer-representation-links",
            message="The filtered representation links are invalid or inconsistent.",
        )
    states["representation_links"] = "pass"

    without_view_id = {key: value for key, value in payload.items() if key != "view_id"}
    if (
        payload.get("view_id") != representation.get("view_id")
        or payload.get("view_id") != _canonical_id(without_view_id)
    ):
        return _failed_result(
            status="validation_failed",
            document=document,
            check_states=states,
            check_id="view_identity",
            rule_id="filtered-consumer-view-id-mismatch",
            message="The filtered view identity is invalid or inconsistent.",
        )
    states["view_identity"] = "pass"

    if not _safe_sections_valid(payload):
        return _failed_result(
            status="validation_failed",
            document=document,
            check_states=states,
            check_id="safe_sections",
            rule_id="filtered-consumer-safe-sections",
            message="The filtered snapshot contains an unsafe section or row shape.",
        )
    states["safe_sections"] = "pass"

    if not _filter_semantics_valid(payload):
        return _failed_result(
            status="validation_failed",
            document=document,
            check_states=states,
            check_id="filter_semantics",
            rule_id="filtered-consumer-filter-semantics",
            message="The safe summaries do not satisfy the structured filter.",
        )
    states["filter_semantics"] = "pass"
    return _result(
        status="pass",
        document=document,
        check_states=states,
    )


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateJSONKeyError
        result[key] = value
    return result


def read_stdin_document(stream: BinaryIO) -> object:
    """Read and parse one bounded strict UTF-8 JSON document."""
    try:
        raw = stream.read(MAX_INPUT_BYTES + 1)
    except OSError as exc:
        raise InputDocumentError(
            "filtered-consumer-input-read-error",
            "The consumer could not read stdin.",
            status="error",
        ) from exc
    if len(raw) > MAX_INPUT_BYTES:
        raise InputDocumentError(
            "filtered-consumer-input-too-large",
            "The filtered snapshot input exceeds the 1 MiB limit.",
        )
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise InputDocumentError(
            "filtered-consumer-input-not-utf8",
            "The filtered snapshot input must be valid UTF-8.",
        ) from exc
    if not text.strip():
        raise InputDocumentError(
            "filtered-consumer-empty-input",
            "The consumer requires one filtered reader result on stdin.",
        )
    try:
        return json.loads(text, object_pairs_hook=_reject_duplicate_keys)
    except DuplicateJSONKeyError as exc:
        raise InputDocumentError(
            "filtered-consumer-duplicate-json-key",
            "The filtered snapshot JSON contains a duplicate object key.",
        ) from exc
    except json.JSONDecodeError as exc:
        raise InputDocumentError(
            "filtered-consumer-invalid-json",
            "The filtered snapshot input is not valid JSON.",
        ) from exc


def _input_failure_result(error: InputDocumentError) -> FilteredSnapshotValidationResult:
    states = {check_id: "not_run" for check_id in CHECK_IDS}
    return _result(
        status=error.status,
        document=None,
        check_states=states,
        findings=[
            _finding(
                error.rule_id,
                status=error.status,
                message=error.message,
            )
        ],
    )


def _argument_failure_result() -> FilteredSnapshotValidationResult:
    states = {check_id: "not_run" for check_id in CHECK_IDS}
    return _result(
        status="validation_failed",
        document=None,
        check_states=states,
        findings=[
            _finding(
                "filtered-consumer-arguments-not-supported",
                status="validation_failed",
                message="The consumer accepts input only through stdin.",
            )
        ],
    )


def _internal_error_result() -> FilteredSnapshotValidationResult:
    states = {check_id: "not_run" for check_id in CHECK_IDS}
    return _result(
        status="error",
        document=None,
        check_states=states,
        findings=[
            _finding(
                "filtered-consumer-internal-error",
                status="error",
                message="The consumer could not complete bounded validation.",
            )
        ],
    )


def main(
    *,
    argv: list[str] | None = None,
    stdin: BinaryIO | None = None,
    stdout: TextIO | None = None,
) -> int:
    """Consume one stdin document and emit one deterministic JSON result."""
    if argv is not None:
        raw_argv = list(argv)
    elif stdin is not None or stdout is not None:
        raw_argv = []
    else:
        raw_argv = list(sys.argv[1:])
    input_stream = stdin if stdin is not None else sys.stdin.buffer
    output_stream = stdout if stdout is not None else sys.stdout
    if raw_argv:
        result = _argument_failure_result()
    else:
        try:
            document = read_stdin_document(input_stream)
            result = validate_filtered_snapshot_document(document)
        except InputDocumentError as error:
            result = _input_failure_result(error)
        except Exception:
            result = _internal_error_result()

    serialized = json.dumps(result.to_dict(), ensure_ascii=False, indent=2) + "\n"
    if len(serialized.encode("utf-8")) > MAX_OUTPUT_BYTES:
        result = _internal_error_result()
        serialized = json.dumps(result.to_dict(), ensure_ascii=False, indent=2) + "\n"
    output_stream.write(serialized)
    return result.exit_code()


if __name__ == "__main__":
    raise SystemExit(main())
