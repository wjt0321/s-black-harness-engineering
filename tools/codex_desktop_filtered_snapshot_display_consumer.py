"""Stage 37 stdin-only validator for filtered snapshot Markdown display results."""

from __future__ import annotations

import hashlib
import json
import re
import sys
from dataclasses import dataclass
from typing import Any, BinaryIO, TextIO

VALIDATION_SCHEMA_VERSION = (
    "control-plane/filtered-snapshot-markdown-display-consumer-validation/v1"
)
CONSUMER_ID = "codex-desktop-filtered-snapshot-markdown-display-consumer/v1"
DISPLAY_SCHEMA_VERSION = "control-plane/codex-desktop-filtered-snapshot-display/v1"
DISPLAY_ID = "codex-desktop-filtered-snapshot-markdown-display/v1"
MAX_INPUT_BYTES = 64 * 1024
MAX_OUTPUT_BYTES = 64 * 1024
HASH_RE = re.compile(r"sha256:[0-9a-f]{64}\Z")
RULE_RE = re.compile(r"[a-z0-9-]{1,80}\Z")
TASK_RE = re.compile(r"task-[0-9]{8}-[0-9]{3,}\Z")
REQUEST_RE = re.compile(r"req-[0-9]{8}-[0-9]{3,}\Z")
CHECK_IDS = (
    "document_shape", "schema_version", "display_status", "lifecycle",
    "guarantees", "representation_metadata", "content_identity",
    "markdown_structure", "escaping_invariants", "view_coherence",
)
DISPLAY_GUARANTEES = {
    "requires_explicit_user_action": True, "one_shot": True, "read_only": True,
    "uses_fixed_filtered_snapshot_host": True, "validates_host_result": True,
    "projects_safe_fields_only": True, "produces_escaped_markdown": True,
    "renders_raw_html": False, "accepts_arbitrary_input": False,
    "writes_files": False, "writes_ledgers": False, "accesses_network": False,
    "starts_service": False, "executes_descriptor_argv": False,
    "executes_candidate_commands": False, "executes_adapters": False,
    "auto_retries": False, "persists_output": False, "bounded_output": True,
}
RESULT_GUARANTEES = {
    "stdin_only": True, "read_only": True, "validates_display_result": True,
    "recomputes_content_identity": True, "validates_markdown_grammar": True,
    "renders_markdown": False, "writes_files": False, "accesses_network": False,
    "starts_service": False, "executes_display": False, "executes_host": False,
    "executes_reader": False, "executes_commands": False,
    "executes_adapters": False, "persists_input": False,
    "bounded_input": True, "bounded_output": True,
}
TOP_KEYS = {
    "status", "schema_version", "display", "source", "lifecycle", "host",
    "representation", "findings", "guarantees", "next_action",
}
REP_KEYS = {
    "status", "type", "media_type", "encoding", "base_snapshot_id",
    "scope_id", "filter_id", "view_id", "content_id", "content",
}
SOURCE_KEYS = (
    "base_snapshot_id", "scope_id", "filter_id", "view_id", "content_id",
)
FINDING_KEYS = {"rule_id", "severity", "action", "message"}
RUN_FIELDS = (
    "request_id", "task_id", "adapter_id", "capability", "operation", "mode",
    "status", "started_at", "ended_at",
)
APPROVAL_FIELDS = (
    "approval_id", "request_id", "task_id", "adapter_id", "operation", "target",
    "status", "requested_at", "resolved_at", "resolver",
)
ARTIFACT_FIELDS = (
    "artifact_id", "artifact_type", "task_id", "request_id", "producer",
    "timestamp", "summary", "safe_to_preview",
)


@dataclass(frozen=True)
class ConsumerFinding:
    rule_id: str
    severity: str
    action: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {
            "rule_id": self.rule_id, "severity": self.severity,
            "action": self.action, "message": self.message,
        }


@dataclass(frozen=True)
class DisplayValidationResult:
    status: str
    source: dict[str, str | None]
    checks: tuple[dict[str, str], ...]
    findings: tuple[ConsumerFinding, ...] = ()
    next_action: dict[str, str] | None = None

    def exit_code(self) -> int:
        return {"pass": 0, "error": 1, "blocked": 2, "validation_failed": 5}.get(
            self.status, 1
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "schema_version": VALIDATION_SCHEMA_VERSION,
            "consumer": CONSUMER_ID,
            "source": self.source,
            "checks": list(self.checks),
            "findings": [item.to_dict() for item in self.findings],
            "guarantees": dict(RESULT_GUARANTEES),
            "next_action": self.next_action,
        }


class DuplicateJSONKeyError(ValueError):
    pass


class InputDocumentError(ValueError):
    def __init__(self, rule_id: str, message: str, status: str = "validation_failed") -> None:
        super().__init__(message)
        self.rule_id = rule_id
        self.message = message
        self.status = status


class MarkdownValidationError(ValueError):
    def __init__(self, check_id: str, rule_id: str, message: str) -> None:
        super().__init__(message)
        self.check_id = check_id
        self.rule_id = rule_id
        self.message = message


def _is_hash(value: object) -> bool:
    return isinstance(value, str) and HASH_RE.fullmatch(value) is not None


def _plain_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _safe_source(document: object) -> dict[str, str | None]:
    result = {key: None for key in SOURCE_KEYS}
    if not isinstance(document, dict):
        return result
    representation = document.get("representation")
    if not isinstance(representation, dict):
        return result
    for key in SOURCE_KEYS:
        value = representation.get(key)
        if _is_hash(value):
            result[key] = value
    return result


def _finding(rule_id: str, status: str, message: str) -> ConsumerFinding:
    safe_rule = rule_id if RULE_RE.fullmatch(rule_id) else "display-consumer-error"
    if status == "blocked":
        return ConsumerFinding(safe_rule, "warning", "block", message)
    if status == "validation_failed":
        return ConsumerFinding(safe_rule, "error", "reject", message)
    return ConsumerFinding(safe_rule, "error", "retry", message)


def _next_action(status: str) -> dict[str, str]:
    values = {
        "pass": ("accept_markdown_display", "The display result satisfies the read-only consumer contract."),
        "blocked": ("reject_unsupported_display", "Do not consume the blocked or unsupported display result."),
        "validation_failed": ("reject_invalid_display", "Reject the display result because contract validation failed."),
        "error": ("retry_consumer_validation", "Retry bounded validation after correcting the safe input failure."),
    }
    code, message = values.get(status, values["error"])
    return {"code": code, "message": message}


def _result(
    status: str, document: object, states: dict[str, str],
    findings: list[ConsumerFinding] | None = None,
) -> DisplayValidationResult:
    return DisplayValidationResult(
        status=status, source=_safe_source(document),
        checks=tuple({"check_id": check, "status": states[check]} for check in CHECK_IDS),
        findings=tuple(findings or ()), next_action=_next_action(status),
    )


def _failed(
    status: str, document: object, states: dict[str, str], check_id: str,
    rule_id: str, message: str,
) -> DisplayValidationResult:
    states[check_id] = "failed"
    return _result(status, document, states, [_finding(rule_id, status, message)])


def _all_remaining_pass(states: dict[str, str]) -> None:
    for check in CHECK_IDS:
        if states[check] == "not_run":
            states[check] = "pass"


def _string_dict(value: object, keys: set[str]) -> bool:
    return (
        isinstance(value, dict) and set(value) == keys
        and all(isinstance(item, str) for item in value.values())
    )


def _common_shape(document: object) -> bool:
    if not isinstance(document, dict) or set(document) != TOP_KEYS:
        return False
    return (
        all(isinstance(document.get(key), str) for key in ("status", "schema_version", "display"))
        and document.get("source") == {"project_root": "project_root"}
        and isinstance(document.get("lifecycle"), dict)
        and isinstance(document.get("host"), dict)
        and isinstance(document.get("representation"), dict)
        and isinstance(document.get("findings"), list)
        and isinstance(document.get("guarantees"), dict)
        and isinstance(document.get("next_action"), dict)
    )


def _status_contract_valid(document: dict[str, Any]) -> bool:
    status = document["status"]
    host = document["host"]
    representation = document["representation"]
    findings = document["findings"]
    next_action = document["next_action"]
    if status not in {"ready", "blocked", "validation_failed", "error"}:
        return False
    if set(host) != {"status", "exit_code"} or not isinstance(host.get("status"), str):
        return False
    if host.get("exit_code") is not None and not _plain_int(host.get("exit_code")):
        return False
    if set(representation) != REP_KEYS:
        return False
    if not _string_dict(next_action, {"code", "message"}):
        return False
    if not isinstance(findings, list):
        return False
    for finding in findings:
        if not _string_dict(finding, FINDING_KEYS) or RULE_RE.fullmatch(finding["rule_id"]) is None:
            return False
    expected_codes = {
        "ready": "review_markdown_display", "blocked": "inspect_host_result",
        "validation_failed": "reject_host_result", "error": "retry_explicit_display",
    }
    if next_action["code"] != expected_codes[status]:
        return False
    if status == "ready":
        return host == {"status": "ready", "exit_code": 0} and findings == []
    valid_host = {
        "blocked": host == {"status": "blocked", "exit_code": 2},
        "validation_failed": host in (
            {"status": "not_run", "exit_code": None},
            {"status": "validation_failed", "exit_code": 5},
        ),
        "error": (
            host == {"status": "not_run", "exit_code": None}
            or (
                host.get("status") == "error"
                and host.get("exit_code") in {None, 0, 1, 2, 5}
            )
            or host == {"status": "ready", "exit_code": 0}
        ),
    }[status]
    return valid_host and bool(findings)


def _lifecycle_valid(document: dict[str, Any]) -> bool:
    lifecycle = document["lifecycle"]
    status = document["status"]
    if set(lifecycle) != {"state", "phases"} or lifecycle.get("state") != "closed":
        return False
    phases = lifecycle.get("phases")
    if not isinstance(phases, list) or any(not isinstance(item, str) for item in phases):
        return False
    if phases[:1] != ["created"] or phases[-2:] != [status, "closed"]:
        return False
    allowed = {"created", "loading", "projecting", status, "closed"}
    return len(phases) == len(set(phases)) and set(phases) <= allowed

class _Cursor:
    def __init__(self, content: str) -> None:
        self.lines = content.split("\n")
        self.index = 0

    def peek(self) -> str | None:
        return self.lines[self.index] if self.index < len(self.lines) else None

    def expect(self, expected: str) -> None:
        if self.peek() != expected:
            raise MarkdownValidationError(
                "markdown_structure", "display-consumer-markdown-structure",
                "The Markdown display does not match the fixed section grammar.",
            )
        self.index += 1

    def done(self) -> bool:
        return self.index == len(self.lines)


def _label(field: str) -> str:
    return field.replace("_", " ").title()


def _literal(cursor: _Cursor, label: str, kind: str) -> Any:
    line = cursor.peek()
    prefix = f"- {label}: "
    if not isinstance(line, str) or not line.startswith(prefix):
        raise MarkdownValidationError(
            "markdown_structure", "display-consumer-markdown-structure",
            "A fixed Markdown field is missing or reordered.",
        )
    token = line[len(prefix):]
    cursor.index += 1
    if len(token) < 3 or not token.startswith("`") or not token.endswith("`"):
        raise MarkdownValidationError(
            "escaping_invariants", "display-consumer-escaping-invariants",
            "Dynamic Markdown values must use one inline JSON literal.",
        )
    inner = token[1:-1]
    if not inner.isascii() or any(char in inner for char in "`|<>&[]()"):
        raise MarkdownValidationError(
            "escaping_invariants", "display-consumer-escaping-invariants",
            "Dynamic Markdown values contain a raw unsafe character.",
        )
    try:
        value = json.loads(inner)
    except json.JSONDecodeError as exc:
        raise MarkdownValidationError(
            "escaping_invariants", "display-consumer-escaping-invariants",
            "Dynamic Markdown values must be valid ASCII JSON scalars.",
        ) from exc
    allowed = isinstance(value, (str, bool, int)) or value is None
    if not allowed or isinstance(value, float):
        raise MarkdownValidationError(
            "escaping_invariants", "display-consumer-escaping-invariants",
            "Dynamic Markdown values use an unsupported scalar type.",
        )
    valid_kind = {
        "str": isinstance(value, str),
        "bool": isinstance(value, bool),
        "int": _plain_int(value),
        "nullable-str": value is None or isinstance(value, str),
    }[kind]
    if not valid_kind:
        raise MarkdownValidationError(
            "markdown_structure", "display-consumer-markdown-structure",
            "A Markdown field has an unsupported value type.",
        )
    return value


def _collection(
    cursor: _Cursor, title: str, fields: tuple[str, ...], bool_field: str | None,
) -> list[dict[str, Any]]:
    cursor.expect(f"## {title}")
    cursor.expect("")
    empty_text = f"No matching {title.lower()}."
    if cursor.peek() == empty_text:
        cursor.expect(empty_text)
        cursor.expect("")
        return []
    rows: list[dict[str, Any]] = []
    singular = title[:-1]
    while cursor.peek() == f"### {singular} {len(rows) + 1}":
        cursor.expect(f"### {singular} {len(rows) + 1}")
        cursor.expect("")
        row: dict[str, Any] = {}
        for field in fields:
            kind = "bool" if field == bool_field else "str"
            row[field] = _literal(cursor, _label(field), kind)
        cursor.expect("")
        rows.append(row)
    if not rows:
        raise MarkdownValidationError(
            "markdown_structure", "display-consumer-markdown-structure",
            "A non-empty collection must use fixed numbered row blocks.",
        )
    return rows


def _parse_markdown(content: str) -> dict[str, Any]:
    if not content or not content.endswith("\n") or "\r" in content:
        raise MarkdownValidationError(
            "markdown_structure", "display-consumer-markdown-structure",
            "The Markdown display must be one normalized LF document.",
        )
    for char in content:
        if ord(char) < 32 and char != "\n":
            raise MarkdownValidationError(
                "escaping_invariants", "display-consumer-escaping-invariants",
                "The Markdown display contains a raw control character.",
            )
    cursor = _Cursor(content)
    cursor.expect("# Filtered Snapshot")
    cursor.expect("")
    cursor.expect("## Overview")
    cursor.expect("")
    matched = _literal(cursor, "Matched", "bool")
    run_count = _literal(cursor, "Run Count", "int")
    approval_count = _literal(cursor, "Approval Count", "int")
    artifact_count = _literal(cursor, "Artifact Count", "int")
    cursor.expect("")
    cursor.expect("## Filter")
    cursor.expect("")
    task_id = _literal(cursor, "Task ID", "nullable-str")
    request_id = _literal(cursor, "Request ID", "nullable-str")
    cursor.expect("")
    cursor.expect("## Identity")
    cursor.expect("")
    base_snapshot_id = _literal(cursor, "Base Snapshot ID", "str")
    scope_id = _literal(cursor, "Scope ID", "str")
    filter_id = _literal(cursor, "Filter ID", "str")
    view_id = _literal(cursor, "View ID", "str")
    cursor.expect("")
    runs = _collection(cursor, "Runs", RUN_FIELDS, None)
    approvals = _collection(cursor, "Approvals", APPROVAL_FIELDS, None)
    artifacts = _collection(cursor, "Artifacts", ARTIFACT_FIELDS, "safe_to_preview")
    cursor.expect("## Reports")
    cursor.expect("")
    report_status = _literal(cursor, "Status", "str")
    report_availability = _literal(cursor, "Availability", "str")
    report_reason = _literal(cursor, "Reason", "str")
    report_message = _literal(cursor, "Message", "str")
    command_hint = _literal(cursor, "Command Hint", "str")
    cursor.expect("")
    if not cursor.done():
        raise MarkdownValidationError(
            "markdown_structure", "display-consumer-markdown-structure",
            "The Markdown display contains extra text.",
        )
    return {
        "matched": matched, "run_count": run_count,
        "approval_count": approval_count, "artifact_count": artifact_count,
        "task_id": task_id, "request_id": request_id,
        "base_snapshot_id": base_snapshot_id, "scope_id": scope_id,
        "filter_id": filter_id, "view_id": view_id,
        "runs": runs, "approvals": approvals, "artifacts": artifacts,
        "report_status": report_status,
        "report_availability": report_availability,
        "report_reason": report_reason, "report_message": report_message,
        "command_hint": command_hint,
    }


def _coherence_valid(parsed: dict[str, Any], representation: dict[str, Any]) -> bool:
    if any(
        not _is_hash(parsed[key])
        for key in ("base_snapshot_id", "scope_id", "filter_id", "view_id")
    ):
        return False
    if any(parsed[key] != representation[key] for key in (
        "base_snapshot_id", "scope_id", "filter_id", "view_id"
    )):
        return False
    if any(
        not _plain_int(parsed[key]) or parsed[key] < 0
        for key in ("run_count", "approval_count", "artifact_count")
    ):
        return False
    if (
        parsed["run_count"] != len(parsed["runs"])
        or parsed["approval_count"] != len(parsed["approvals"])
        or parsed["artifact_count"] != len(parsed["artifacts"])
    ):
        return False
    if parsed["matched"] is not bool(
        parsed["runs"] or parsed["approvals"] or parsed["artifacts"]
    ):
        return False
    task_id, request_id = parsed["task_id"], parsed["request_id"]
    if task_id is None and request_id is None:
        return False
    if task_id is not None and TASK_RE.fullmatch(task_id) is None:
        return False
    if request_id is not None and REQUEST_RE.fullmatch(request_id) is None:
        return False
    return (
        parsed["report_status"] == "unavailable"
        and parsed["report_availability"] == "stable_limited"
        and parsed["report_reason"] == "request_context_required"
    )


def validate_display_document(document: object) -> DisplayValidationResult:
    states = {check: "not_run" for check in CHECK_IDS}
    if not _common_shape(document):
        return _failed(
            "validation_failed", document, states, "document_shape",
            "display-consumer-document-shape",
            "The input does not match the display result wrapper shape.",
        )
    states["document_shape"] = "pass"
    assert isinstance(document, dict)
    if (
        document["schema_version"] != DISPLAY_SCHEMA_VERSION
        or document["display"] != DISPLAY_ID
    ):
        return _failed(
            "blocked", document, states, "schema_version",
            "display-consumer-unsupported-schema",
            "The display result schema or display id is unsupported.",
        )
    states["schema_version"] = "pass"
    if not _status_contract_valid(document):
        return _failed(
            "validation_failed", document, states, "display_status",
            "display-consumer-display-status",
            "The display status, host summary, findings, or next action is inconsistent.",
        )
    states["display_status"] = "pass"
    if not _lifecycle_valid(document):
        return _failed(
            "validation_failed", document, states, "lifecycle",
            "display-consumer-lifecycle", "The display lifecycle is invalid.",
        )
    states["lifecycle"] = "pass"
    if document["guarantees"] != DISPLAY_GUARANTEES:
        return _failed(
            "validation_failed", document, states, "guarantees",
            "display-consumer-guarantees", "The display guarantees are invalid.",
        )
    states["guarantees"] = "pass"
    representation = document["representation"]
    if (
        representation.get("type") != "markdown"
        or representation.get("media_type") != "text/markdown; charset=utf-8"
        or representation.get("encoding") != "utf-8"
    ):
        return _failed(
            "validation_failed", document, states, "representation_metadata",
            "display-consumer-representation-metadata",
            "The Markdown representation metadata is invalid.",
        )
    status = document["status"]
    if status != "ready":
        if (
            representation.get("status") != "withheld"
            or representation.get("content") is not None
            or representation.get("content_id") is not None
            or any(
                representation.get(key) is not None and not _is_hash(representation.get(key))
                for key in ("base_snapshot_id", "scope_id", "filter_id", "view_id")
            )
        ):
            return _failed(
                "validation_failed", document, states, "representation_metadata",
                "display-consumer-withheld-contract",
                "A non-ready display must withhold its Markdown content.",
            )
        states["representation_metadata"] = "pass"
        _all_remaining_pass(states)
        upstream = status if status in {"blocked", "validation_failed", "error"} else "error"
        return _result(
            upstream, document, states,
            [_finding(f"display-consumer-upstream-{upstream}", upstream,
                      f"The validated upstream display status is {upstream}.")],
        )
    if representation.get("status") != "pass":
        return _failed(
            "validation_failed", document, states, "representation_metadata",
            "display-consumer-representation-metadata",
            "A ready display must contain a passing Markdown representation.",
        )
    if any(not _is_hash(representation.get(key)) for key in SOURCE_KEYS):
        return _failed(
            "validation_failed", document, states, "representation_metadata",
            "display-consumer-representation-metadata",
            "A ready display must contain canonical representation identities.",
        )
    content = representation.get("content")
    if not isinstance(content, str):
        return _failed(
            "validation_failed", document, states, "representation_metadata",
            "display-consumer-representation-metadata",
            "A ready display must contain Markdown text.",
        )
    states["representation_metadata"] = "pass"
    expected_content_id = "sha256:" + hashlib.sha256(content.encode("utf-8")).hexdigest()
    if representation["content_id"] != expected_content_id:
        return _failed(
            "validation_failed", document, states, "content_identity",
            "display-consumer-content-identity",
            "The Markdown content identity does not match its UTF-8 bytes.",
        )
    states["content_identity"] = "pass"
    try:
        parsed = _parse_markdown(content)
    except MarkdownValidationError as error:
        return _failed(
            "validation_failed", document, states, error.check_id,
            error.rule_id, error.message,
        )
    states["markdown_structure"] = "pass"
    states["escaping_invariants"] = "pass"
    if not _coherence_valid(parsed, representation):
        return _failed(
            "validation_failed", document, states, "view_coherence",
            "display-consumer-view-coherence",
            "The Markdown counts, filters, identities, empty view, or reports are inconsistent.",
        )
    states["view_coherence"] = "pass"
    return _result("pass", document, states)


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateJSONKeyError
        result[key] = value
    return result


def read_stdin_document(stream: BinaryIO) -> object:
    try:
        raw = stream.read(MAX_INPUT_BYTES + 1)
    except OSError as exc:
        raise InputDocumentError(
            "display-consumer-input-read-error",
            "The consumer could not read stdin.", "error",
        ) from exc
    if len(raw) > MAX_INPUT_BYTES:
        raise InputDocumentError(
            "display-consumer-input-too-large",
            "The display result input exceeds the 64 KiB limit.",
        )
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise InputDocumentError(
            "display-consumer-input-not-utf8",
            "The display result input must be valid UTF-8.",
        ) from exc
    if not text.strip():
        raise InputDocumentError(
            "display-consumer-empty-input",
            "The consumer requires one display result on stdin.",
        )
    try:
        return json.loads(text, object_pairs_hook=_reject_duplicate_keys)
    except DuplicateJSONKeyError as exc:
        raise InputDocumentError(
            "display-consumer-duplicate-json-key",
            "The display result JSON contains a duplicate object key.",
        ) from exc
    except json.JSONDecodeError as exc:
        raise InputDocumentError(
            "display-consumer-invalid-json",
            "The display result input is not valid JSON.",
        ) from exc


def _input_failure(error: InputDocumentError) -> DisplayValidationResult:
    states = {check: "not_run" for check in CHECK_IDS}
    return _result(
        error.status, None, states,
        [_finding(error.rule_id, error.status, error.message)],
    )


def _argument_failure() -> DisplayValidationResult:
    states = {check: "not_run" for check in CHECK_IDS}
    return _result(
        "validation_failed", None, states,
        [_finding(
            "display-consumer-arguments-not-supported", "validation_failed",
            "The consumer accepts input only through stdin.",
        )],
    )


def _internal_failure() -> DisplayValidationResult:
    states = {check: "not_run" for check in CHECK_IDS}
    return _result(
        "error", None, states,
        [_finding(
            "display-consumer-internal-error", "error",
            "The consumer could not complete bounded validation.",
        )],
    )


def main(
    *, argv: list[str] | None = None, stdin: BinaryIO | None = None,
    stdout: TextIO | None = None,
) -> int:
    if argv is not None:
        raw_argv = list(argv)
    elif stdin is not None or stdout is not None:
        raw_argv = []
    else:
        raw_argv = list(sys.argv[1:])
    input_stream = stdin if stdin is not None else sys.stdin.buffer
    output_stream = stdout if stdout is not None else sys.stdout
    if raw_argv:
        result = _argument_failure()
    else:
        try:
            result = validate_display_document(read_stdin_document(input_stream))
        except InputDocumentError as error:
            result = _input_failure(error)
        except Exception:
            result = _internal_failure()
    serialized = json.dumps(result.to_dict(), ensure_ascii=False, indent=2) + "\n"
    if len(serialized.encode("utf-8")) > MAX_OUTPUT_BYTES:
        result = _internal_failure()
        serialized = json.dumps(result.to_dict(), ensure_ascii=False, indent=2) + "\n"
    output_stream.write(serialized)
    return result.exit_code()


if __name__ == "__main__":
    raise SystemExit(main())
