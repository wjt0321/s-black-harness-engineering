"""Standalone Stage 18 validator for Control Panel handoff descriptors."""

from __future__ import annotations

import hashlib
import json
import re
import sys
from dataclasses import dataclass
from pathlib import PurePosixPath, PureWindowsPath
from typing import Any, BinaryIO, TextIO

VALIDATION_SCHEMA_VERSION = (
    "control-plane/control-panel-host-consumer-validation/v1"
)
HANDOFF_SCHEMA_VERSION = "control-plane/control-panel-handoff/v1"
SNAPSHOT_SCHEMA_VERSION = "control-plane/control-panel-snapshot/v1"
HTML_RENDERER_VERSION = "control-plane/control-panel-html/v1"
CONSUMER_ID = "local-reference-consumer/v1"
MAX_INPUT_BYTES = 1024 * 1024
CHECK_IDS = (
    "document_shape",
    "schema_version",
    "producer_status",
    "handoff_identity",
    "render_identity",
    "representations",
    "argv",
    "boundaries",
)
_SHA256_RE = re.compile(r"sha256:[0-9a-f]{64}\Z")
_TOP_LEVEL_KEYS = {
    "status",
    "schema_version",
    "handoff_id",
    "source",
    "snapshot",
    "render",
    "boundaries",
    "findings",
    "next_action",
}
_SOURCE_KEYS = {"envelope_file"}
_SNAPSHOT_KEYS = {
    "snapshot_id",
    "schema_version",
    "media_type",
    "encoding",
    "working_directory",
    "scoped_unavailable",
    "argv",
}
_RENDER_KEYS = {
    "render_id",
    "renderer_version",
    "media_type",
    "encoding",
    "working_directory",
    "self_contained",
    "argv",
}
_BOUNDARY_KEYS = {
    "read_only",
    "writes_files",
    "writes_ledgers",
    "accesses_network",
    "starts_service",
    "executes_commands",
    "executes_adapters",
}
_SCOPED_KEYS = {"section", "scope", "reason"}
_NEXT_ACTION_KEYS = {"code", "message"}
_EXPECTED_BOUNDARIES = {
    "read_only": True,
    "writes_files": False,
    "writes_ledgers": False,
    "accesses_network": False,
    "starts_service": False,
    "executes_commands": False,
    "executes_adapters": False,
}


@dataclass(frozen=True)
class ConsumerFinding:
    """Value-safe validation finding produced by the reference consumer."""

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
class ConsumerValidationResult:
    """Deterministic result returned by the standalone reference consumer."""

    status: str
    source_handoff_id: str | None
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
            "source_handoff_id": self.source_handoff_id,
            "checks": list(self.checks),
            "findings": [finding.to_dict() for finding in self.findings],
            "guarantees": {
                "stdin_only": True,
                "read_only": True,
                "writes_files": False,
                "accesses_network": False,
                "reads_representations": False,
                "executes_commands": False,
                "executes_adapters": False,
                "starts_service": False,
            },
            "next_action": self.next_action,
        }


def _canonical_hash(payload: dict[str, Any]) -> str:
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(canonical).hexdigest()}"


def _safe_handoff_id(document: object) -> str | None:
    if not isinstance(document, dict):
        return None
    value = document.get("handoff_id")
    return value if isinstance(value, str) and _SHA256_RE.fullmatch(value) else None


def _shape_is_valid(document: object) -> bool:
    if not isinstance(document, dict) or set(document) != _TOP_LEVEL_KEYS:
        return False
    if not all(
        isinstance(document[key], str)
        for key in ("status", "schema_version", "handoff_id")
    ):
        return False

    source = document.get("source")
    snapshot = document.get("snapshot")
    render = document.get("render")
    boundaries = document.get("boundaries")
    findings = document.get("findings")
    next_action = document.get("next_action")
    if not isinstance(source, dict) or set(source) != _SOURCE_KEYS:
        return False
    if source["envelope_file"] is not None and not isinstance(
        source["envelope_file"], str
    ):
        return False
    if not isinstance(snapshot, dict) or set(snapshot) != _SNAPSHOT_KEYS:
        return False
    if not isinstance(render, dict) or set(render) != _RENDER_KEYS:
        return False
    if not isinstance(boundaries, dict) or set(boundaries) != _BOUNDARY_KEYS:
        return False
    if not all(isinstance(value, bool) for value in boundaries.values()):
        return False
    if not isinstance(findings, list) or not all(
        isinstance(item, dict) for item in findings
    ):
        return False
    if not isinstance(next_action, dict) or set(next_action) != _NEXT_ACTION_KEYS:
        return False
    if not all(isinstance(next_action[key], str) for key in _NEXT_ACTION_KEYS):
        return False

    snapshot_string_fields = (
        "snapshot_id",
        "schema_version",
        "media_type",
        "encoding",
        "working_directory",
    )
    if not all(isinstance(snapshot[key], str) for key in snapshot_string_fields):
        return False
    if not isinstance(snapshot["scoped_unavailable"], list):
        return False
    for row in snapshot["scoped_unavailable"]:
        if not isinstance(row, dict) or set(row) != _SCOPED_KEYS:
            return False
        if not all(isinstance(row[key], str) for key in _SCOPED_KEYS):
            return False
    if not isinstance(snapshot["argv"], list):
        return False

    render_string_fields = (
        "render_id",
        "renderer_version",
        "media_type",
        "encoding",
        "working_directory",
    )
    if not all(isinstance(render[key], str) for key in render_string_fields):
        return False
    if not isinstance(render["self_contained"], bool):
        return False
    if not isinstance(render["argv"], list):
        return False
    return True


def _source_is_project_relative(source: dict[str, Any]) -> bool:
    value = source["envelope_file"]
    if value is None:
        return True
    if not value:
        return False
    windows_path = PureWindowsPath(value)
    posix_path = PurePosixPath(value)
    if (
        windows_path.is_absolute()
        or bool(windows_path.drive)
        or bool(windows_path.root)
    ):
        return False
    if posix_path.is_absolute():
        return False
    return ".." not in windows_path.parts and ".." not in posix_path.parts


def _representations_are_valid(document: dict[str, Any]) -> bool:
    snapshot = document["snapshot"]
    render = document["render"]
    return (
        snapshot["schema_version"] == SNAPSHOT_SCHEMA_VERSION
        and snapshot["media_type"] == "application/json; charset=utf-8"
        and snapshot["encoding"] == "utf-8"
        and snapshot["working_directory"] == "project_root"
        and render["renderer_version"] == HTML_RENDERER_VERSION
        and render["media_type"] == "text/html; charset=utf-8"
        and render["encoding"] == "utf-8"
        and render["working_directory"] == "project_root"
        and render["self_contained"] is True
        and _source_is_project_relative(document["source"])
    )


def _argv_is_valid(document: dict[str, Any]) -> bool:
    for representation in (document["snapshot"], document["render"]):
        argv = representation["argv"]
        if not argv or not all(isinstance(item, str) and item for item in argv):
            return False
    return True


def _finding(
    rule_id: str,
    *,
    status: str,
    message: str,
) -> ConsumerFinding:
    return ConsumerFinding(
        rule_id=rule_id,
        severity="block" if status == "blocked" else "error",
        action="block" if status == "blocked" else "error",
        message=message,
    )


def _next_action(status: str) -> dict[str, str]:
    if status == "pass":
        return {
            "code": "accept_handoff",
            "message": "The handoff descriptor passed local reference validation.",
        }
    if status == "blocked":
        return {
            "code": "reject_handoff",
            "message": "Reject the handoff until its producer or boundary is reviewed.",
        }
    if status == "validation_failed":
        return {
            "code": "fix_consumer_input",
            "message": "Fix the handoff contract or identity before retrying validation.",
        }
    return {
        "code": "review_consumer_error",
        "message": "Review the local consumer error before retrying.",
    }


def _result(
    *,
    status: str,
    source_handoff_id: str | None,
    check_states: dict[str, str],
    findings: list[ConsumerFinding],
) -> ConsumerValidationResult:
    return ConsumerValidationResult(
        status=status,
        source_handoff_id=source_handoff_id,
        checks=tuple(
            {"check_id": check_id, "status": check_states[check_id]}
            for check_id in CHECK_IDS
        ),
        findings=tuple(findings),
        next_action=_next_action(status),
    )


def validate_handoff_document(document: object) -> ConsumerValidationResult:
    """Validate one already-parsed handoff document without side effects."""
    source_handoff_id = _safe_handoff_id(document)
    check_states = {check_id: "not_run" for check_id in CHECK_IDS}
    findings: list[ConsumerFinding] = []

    if not _shape_is_valid(document):
        check_states["document_shape"] = "failed"
        findings.append(
            _finding(
                "consumer-document-shape",
                status="validation_failed",
                message="The handoff document does not match the strict v1 shape.",
            )
        )
        return _result(
            status="validation_failed",
            source_handoff_id=source_handoff_id,
            check_states=check_states,
            findings=findings,
        )

    typed_document = document
    check_states["document_shape"] = "pass"
    if typed_document["schema_version"] != HANDOFF_SCHEMA_VERSION:
        check_states["schema_version"] = "failed"
        findings.append(
            _finding(
                "consumer-unsupported-schema",
                status="blocked",
                message="The handoff schema version is not supported by this consumer.",
            )
        )
        return _result(
            status="blocked",
            source_handoff_id=source_handoff_id,
            check_states=check_states,
            findings=findings,
        )
    check_states["schema_version"] = "pass"

    outcome = "pass"
    if typed_document["status"] == "pass":
        check_states["producer_status"] = "pass"
    else:
        check_states["producer_status"] = "failed"
        outcome = "blocked"
        findings.append(
            _finding(
                "consumer-producer-not-pass",
                status="blocked",
                message="The producer did not mark this handoff as pass.",
            )
        )

    without_id = {
        key: value for key, value in typed_document.items() if key != "handoff_id"
    }
    if typed_document["handoff_id"] == _canonical_hash(without_id):
        check_states["handoff_identity"] = "pass"
    else:
        check_states["handoff_identity"] = "failed"
        outcome = "validation_failed"
        findings.append(
            _finding(
                "consumer-handoff-id-mismatch",
                status="validation_failed",
                message="The handoff identity does not match its canonical payload.",
            )
        )

    render_identity = {
        "snapshot_id": typed_document["snapshot"]["snapshot_id"],
        "renderer_version": typed_document["render"]["renderer_version"],
    }
    if typed_document["render"]["render_id"] == _canonical_hash(render_identity):
        check_states["render_identity"] = "pass"
    else:
        check_states["render_identity"] = "failed"
        outcome = "validation_failed"
        findings.append(
            _finding(
                "consumer-render-id-mismatch",
                status="validation_failed",
                message="The render identity does not match the snapshot and renderer.",
            )
        )

    if _representations_are_valid(typed_document):
        check_states["representations"] = "pass"
    else:
        check_states["representations"] = "failed"
        outcome = "validation_failed"
        findings.append(
            _finding(
                "consumer-representation-invalid",
                status="validation_failed",
                message="The declared representations are not valid for handoff v1.",
            )
        )

    if _argv_is_valid(typed_document):
        check_states["argv"] = "pass"
    else:
        check_states["argv"] = "failed"
        outcome = "validation_failed"
        findings.append(
            _finding(
                "consumer-argv-invalid",
                status="validation_failed",
                message="Representation argv must be a non-empty string array.",
            )
        )

    if typed_document["boundaries"] == _EXPECTED_BOUNDARIES:
        check_states["boundaries"] = "pass"
    else:
        check_states["boundaries"] = "failed"
        if outcome != "validation_failed":
            outcome = "blocked"
        findings.append(
            _finding(
                "consumer-unsafe-boundary",
                status="blocked",
                message="The handoff does not preserve the required read-only boundary.",
            )
        )

    return _result(
        status=outcome,
        source_handoff_id=source_handoff_id,
        check_states=check_states,
        findings=findings,
    )



class InputDocumentError(Exception):
    """Safe input failure that can be rendered without echoing source bytes."""

    def __init__(self, rule_id: str, message: str, *, status: str = "validation_failed"):
        super().__init__(message)
        self.rule_id = rule_id
        self.message = message
        self.status = status


class DuplicateJSONKeyError(ValueError):
    """Raised when JSON contains an ambiguous repeated object key."""


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateJSONKeyError
        result[key] = value
    return result


def read_stdin_document(stream: BinaryIO) -> object:
    """Read and parse one bounded UTF-8 JSON document from a binary stream."""
    try:
        raw = stream.read(MAX_INPUT_BYTES + 1)
    except OSError as exc:
        raise InputDocumentError(
            "consumer-input-read-error",
            "The consumer could not read stdin.",
            status="error",
        ) from exc
    if len(raw) > MAX_INPUT_BYTES:
        raise InputDocumentError(
            "consumer-input-too-large",
            "The handoff input exceeds the 1 MiB consumer limit.",
        )
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise InputDocumentError(
            "consumer-input-not-utf8",
            "The handoff input must be valid UTF-8.",
        ) from exc
    if not text.strip():
        raise InputDocumentError(
            "consumer-empty-input",
            "The consumer requires one handoff JSON document on stdin.",
        )
    try:
        return json.loads(text, object_pairs_hook=_reject_duplicate_keys)
    except DuplicateJSONKeyError as exc:
        raise InputDocumentError(
            "consumer-duplicate-json-key",
            "The handoff JSON contains a duplicate object key.",
        ) from exc
    except json.JSONDecodeError as exc:
        raise InputDocumentError(
            "consumer-invalid-json",
            "The handoff input is not valid JSON.",
        ) from exc


def _input_failure_result(error: InputDocumentError) -> ConsumerValidationResult:
    check_states = {check_id: "not_run" for check_id in CHECK_IDS}
    return _result(
        status=error.status,
        source_handoff_id=None,
        check_states=check_states,
        findings=[
            _finding(
                error.rule_id,
                status=error.status,
                message=error.message,
            )
        ],
    )


def main(
    *,
    stdin: BinaryIO | None = None,
    stdout: TextIO | None = None,
) -> int:
    """Validate one stdin descriptor and emit one deterministic JSON result."""
    input_stream = stdin if stdin is not None else sys.stdin.buffer
    output_stream = stdout if stdout is not None else sys.stdout
    try:
        document = read_stdin_document(input_stream)
    except InputDocumentError as error:
        result = _input_failure_result(error)
    else:
        result = validate_handoff_document(document)
    json.dump(result.to_dict(), output_stream, ensure_ascii=False, indent=2)
    output_stream.write("\n")
    return result.exit_code()


if __name__ == "__main__":
    raise SystemExit(main())
