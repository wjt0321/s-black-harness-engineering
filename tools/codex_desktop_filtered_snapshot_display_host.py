"""Stage 40 one-shot filtered snapshot display host integration."""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Sequence, TextIO

HOST_SCHEMA_VERSION = "control-plane/codex-desktop-filtered-snapshot-display-host/v1"
HOST_ID = "codex-desktop-filtered-snapshot-display-host/v1"
DISPLAY_SCHEMA_VERSION = "control-plane/codex-desktop-filtered-snapshot-display/v1"
DISPLAY_ID = "codex-desktop-filtered-snapshot-markdown-display/v1"
CONSUMER_SCHEMA_VERSION = "control-plane/filtered-snapshot-markdown-display-consumer-validation/v1"
CONSUMER_ID = "codex-desktop-filtered-snapshot-markdown-display-consumer/v1"
DEFAULT_TIMEOUT_SECONDS = 30.0
MAX_TIMEOUT_SECONDS = 60.0
MAX_DISPLAY_OUTPUT_BYTES = 64 * 1024
MAX_CONSUMER_OUTPUT_BYTES = 64 * 1024
MAX_STDERR_BYTES = 64 * 1024
MAX_HOST_OUTPUT_BYTES = 128 * 1024
MAX_FILTER_BYTES = 128
MAX_ENVELOPE_BYTES = 512
HASH_RE = re.compile(r"sha256:[0-9a-f]{64}\Z")
RULE_RE = re.compile(r"[a-z0-9-]{1,80}\Z")
TASK_RE = re.compile(r"task-[0-9]{8}-[0-9]{3,}\Z")
REQUEST_RE = re.compile(r"req-[0-9]{8}-[0-9]{3,}\Z")
TOOL_DIR = Path(__file__).resolve().parent
DISPLAY_SCRIPT = TOOL_DIR / "codex_desktop_filtered_snapshot_display.py"
CONSUMER_SCRIPT = TOOL_DIR / "codex_desktop_filtered_snapshot_display_consumer.py"
IDENTITY_KEYS = ("base_snapshot_id", "scope_id", "filter_id", "view_id", "content_id")
CHECK_IDS = (
    "document_shape", "schema_version", "display_status", "lifecycle",
    "guarantees", "representation_metadata", "content_identity",
    "markdown_structure", "escaping_invariants", "view_coherence",
)
EXIT_CODES = {"ready": 0, "error": 1, "blocked": 2, "validation_failed": 5}
CONSUMER_EXIT_CODES = {"pass": 0, "error": 1, "blocked": 2, "validation_failed": 5}
DISPLAY_KEYS = {"status", "schema_version", "display", "source", "lifecycle", "host", "representation", "findings", "guarantees", "next_action"}
REPRESENTATION_KEYS = {"status", "type", "media_type", "encoding", *IDENTITY_KEYS, "content"}
CONSUMER_KEYS = {"status", "schema_version", "consumer", "source", "checks", "findings", "guarantees", "next_action"}
FINDING_KEYS = {"rule_id", "severity", "action", "message"}
NEXT_ACTION_KEYS = {"code", "message"}
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
CONSUMER_GUARANTEES = {
    "stdin_only": True, "read_only": True, "validates_display_result": True,
    "recomputes_content_identity": True, "validates_markdown_grammar": True,
    "renders_markdown": False, "writes_files": False, "accesses_network": False,
    "starts_service": False, "executes_display": False, "executes_host": False,
    "executes_reader": False, "executes_commands": False,
    "executes_adapters": False, "persists_input": False,
    "bounded_input": True, "bounded_output": True,
}
HOST_GUARANTEES = {
    "requires_explicit_user_action": True, "one_shot": True, "read_only": True,
    "uses_fixed_markdown_display": True, "uses_fixed_display_consumer": True,
    "validates_before_release": True, "cross_checks_display_identity": True,
    "withholds_content_until_pass": True, "renders_markdown": False,
    "writes_files": False, "writes_ledgers": False, "accesses_network": False,
    "starts_service": False, "executes_descriptor_argv": False,
    "executes_candidate_commands": False, "executes_adapters": False,
    "auto_retries": False, "persists_output": False, "exports_output": False,
    "bounded_input": True, "bounded_output": True,
}

@dataclass(frozen=True)
class ProcessResult:
    returncode: int
    stdout: bytes
    stderr: bytes = b""

@dataclass(frozen=True)
class HostFinding:
    rule_id: str
    severity: str
    action: str
    message: str
    def to_dict(self) -> dict[str, str]:
        return {"rule_id": self.rule_id, "severity": self.severity, "action": self.action, "message": self.message}

@dataclass(frozen=True)
class FilteredSnapshotDisplayHostResult:
    status: str
    lifecycle_phases: tuple[str, ...]
    display: dict[str, Any]
    consumer: dict[str, Any]
    representation: dict[str, Any]
    findings: tuple[HostFinding, ...] = ()
    next_action: dict[str, str] | None = None
    def exit_code(self) -> int:
        return EXIT_CODES.get(self.status, 1)
    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status, "schema_version": HOST_SCHEMA_VERSION,
            "host": HOST_ID, "source": {"project_root": "project_root"},
            "lifecycle": {"state": "closed", "phases": [*self.lifecycle_phases, "closed"]},
            "display": self.display, "consumer": self.consumer,
            "representation": self.representation,
            "findings": [item.to_dict() for item in self.findings],
            "guarantees": dict(HOST_GUARANTEES), "next_action": self.next_action,
        }

class DuplicateJSONKeyError(ValueError):
    pass

class DisplayHostProtocolError(Exception):
    def __init__(self, rule_id: str, message: str) -> None:
        super().__init__(message)
        self.rule_id = rule_id
        self.message = message

Runner = Callable[..., ProcessResult]

def _minimal_environment() -> dict[str, str]:
    allowed = {"APPDATA", "HOME", "HOMEDRIVE", "HOMEPATH", "LOCALAPPDATA", "PATH", "PATHEXT", "SYSTEMROOT", "TEMP", "TMP", "USERPROFILE", "WINDIR"}
    result = {key: os.environ[key] for key in allowed if key in os.environ}
    result.update(PYTHONDONTWRITEBYTECODE="1", PYTHONUNBUFFERED="1")
    return result

def _run_process(argv: Sequence[str], *, cwd: Path, input_bytes: bytes | None, timeout_seconds: float) -> ProcessResult:
    try:
        completed = subprocess.run(list(argv), cwd=str(cwd), env=_minimal_environment(), input=input_bytes, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout_seconds, check=False, shell=False)
    except subprocess.TimeoutExpired as exc:
        raise TimeoutError from exc
    return ProcessResult(completed.returncode, completed.stdout, completed.stderr)

def _plain_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)

def _is_hash(value: object) -> bool:
    return isinstance(value, str) and HASH_RE.fullmatch(value) is not None

def _string_dict(value: object, keys: set[str]) -> bool:
    return isinstance(value, dict) and set(value) == keys and all(isinstance(item, str) for item in value.values())

def _valid_timeout(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value)) and 0 < float(value) <= MAX_TIMEOUT_SECONDS

def _valid_filter(value: str | None, pattern: re.Pattern[str]) -> bool:
    if value is None:
        return True
    try:
        encoded = value.encode("ascii")
    except (UnicodeEncodeError, AttributeError):
        return False
    return 0 < len(encoded) <= MAX_FILTER_BYTES and value == value.strip() and pattern.fullmatch(value) is not None

def _valid_envelope(value: object) -> bool:
    if not isinstance(value, str) or not value or value != value.strip():
        return False
    try:
        encoded = value.encode("ascii")
    except UnicodeEncodeError:
        return False
    if len(encoded) > MAX_ENVELOPE_BYTES or Path(value).is_absolute():
        return False
    parts = PurePosixPath(value.replace("\\", "/")).parts
    return bool(parts) and ".." not in parts and "." not in parts

def _is_project_root(root: Path) -> bool:
    return root.is_dir() and (root / "pyproject.toml").is_file() and (root / "agent_runtime").is_dir() and DISPLAY_SCRIPT.is_file() and CONSUMER_SCRIPT.is_file()

def _display_argv(root: Path, *, envelope_file: str, task_id_filter: str | None, request_id_filter: str | None, timeout_seconds: float) -> list[str]:
    argv = [sys.executable, str(DISPLAY_SCRIPT), "--project-root", str(root), "--envelope", envelope_file]
    if task_id_filter is not None:
        argv.extend(("--task-id", task_id_filter))
    if request_id_filter is not None:
        argv.extend(("--request-id", request_id_filter))
    argv.extend(("--representation", "markdown", "--timeout-seconds", format(float(timeout_seconds), ".15g"), "--json"))
    return argv

def _consumer_argv() -> list[str]:
    return [sys.executable, str(CONSUMER_SCRIPT)]

def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateJSONKeyError
        result[key] = value
    return result

def _parse_object(raw: bytes, *, limit: int, prefix: str) -> dict[str, Any]:
    if not raw:
        raise DisplayHostProtocolError(f"{prefix}-no-output", "The fixed child returned no output.")
    if len(raw) > limit:
        raise DisplayHostProtocolError(f"{prefix}-output-too-large", "The fixed child exceeded its output limit.")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise DisplayHostProtocolError(f"{prefix}-not-utf8", "The fixed child output is not UTF-8.") from exc
    try:
        document = json.loads(text, object_pairs_hook=_reject_duplicate_keys)
    except DuplicateJSONKeyError as exc:
        raise DisplayHostProtocolError(f"{prefix}-duplicate-json-key", "The fixed child output contains duplicate keys.") from exc
    except json.JSONDecodeError as exc:
        raise DisplayHostProtocolError(f"{prefix}-invalid-json", "The fixed child output is not valid JSON.") from exc
    if not isinstance(document, dict):
        raise DisplayHostProtocolError(f"{prefix}-invalid-shape", "The fixed child must return one JSON object.")
    return document

def _identity_source(representation: object = None) -> dict[str, str | None]:
    source = {key: None for key in IDENTITY_KEYS}
    if isinstance(representation, dict):
        for key in IDENTITY_KEYS:
            value = representation.get(key)
            if value is None or _is_hash(value):
                source[key] = value
    return source

def _display_status_contract(document: dict[str, Any], returncode: int) -> bool:
    status = document.get("status")
    if status not in EXIT_CODES or returncode != EXIT_CODES[status]:
        return False
    host = document.get("host")
    representation = document.get("representation")
    findings = document.get("findings")
    next_action = document.get("next_action")
    if (
        not isinstance(host, dict) or set(host) != {"status", "exit_code"}
        or not isinstance(host.get("status"), str)
        or (host.get("exit_code") is not None and not _plain_int(host.get("exit_code")))
        or not isinstance(representation, dict) or set(representation) != REPRESENTATION_KEYS
        or not isinstance(findings, list) or not _string_dict(next_action, NEXT_ACTION_KEYS)
    ):
        return False
    for finding in findings:
        if not _string_dict(finding, FINDING_KEYS) or RULE_RE.fullmatch(finding["rule_id"]) is None:
            return False
    expected_action = {
        "ready": "review_markdown_display", "blocked": "inspect_host_result",
        "validation_failed": "reject_host_result", "error": "retry_explicit_display",
    }[status]
    if next_action["code"] != expected_action:
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
            or (host.get("status") == "error" and host.get("exit_code") in {None, 0, 1, 2, 5})
            or host == {"status": "ready", "exit_code": 0}
        ),
    }[status]
    return valid_host and bool(findings)

def _display_lifecycle_valid(document: dict[str, Any]) -> bool:
    lifecycle = document.get("lifecycle")
    status = document.get("status")
    if not isinstance(lifecycle, dict) or set(lifecycle) != {"state", "phases"} or lifecycle.get("state") != "closed":
        return False
    phases = lifecycle.get("phases")
    if not isinstance(phases, list) or any(not isinstance(item, str) for item in phases):
        return False
    if phases[:1] != ["created"] or phases[-2:] != [status, "closed"]:
        return False
    allowed = {"created", "loading", "projecting", status, "closed"}
    return len(phases) == len(set(phases)) and set(phases) <= allowed

def _validate_display(document: dict[str, Any], returncode: int) -> str:
    if set(document) != DISPLAY_KEYS:
        raise DisplayHostProtocolError("display-host-display-document-shape", "The display result shape is unsupported.")
    if document.get("schema_version") != DISPLAY_SCHEMA_VERSION or document.get("display") != DISPLAY_ID or document.get("source") != {"project_root": "project_root"}:
        raise DisplayHostProtocolError("display-host-display-schema", "The display result schema is unsupported.")
    if document.get("guarantees") != DISPLAY_GUARANTEES:
        raise DisplayHostProtocolError("display-host-display-guarantees", "The display guarantees are invalid.")
    if not _display_status_contract(document, returncode):
        raise DisplayHostProtocolError("display-host-display-status", "The display status and exit code are inconsistent.")
    if not _display_lifecycle_valid(document):
        raise DisplayHostProtocolError("display-host-display-lifecycle", "The display lifecycle is invalid.")
    representation = document["representation"]
    if representation.get("type") != "markdown" or representation.get("media_type") != "text/markdown; charset=utf-8" or representation.get("encoding") != "utf-8":
        raise DisplayHostProtocolError("display-host-display-metadata", "The display representation metadata is invalid.")
    status = document["status"]
    if status == "ready":
        if representation.get("status") != "pass" or not isinstance(representation.get("content"), str) or not representation["content"] or any(not _is_hash(representation.get(key)) for key in IDENTITY_KEYS):
            raise DisplayHostProtocolError("display-host-display-representation", "The ready display representation is invalid.")
    elif (
        representation.get("status") != "withheld"
        or representation.get("content") is not None
        or representation.get("content_id") is not None
        or any(representation.get(key) is not None and not _is_hash(representation.get(key)) for key in IDENTITY_KEYS[:-1])
    ):
        raise DisplayHostProtocolError("display-host-display-withheld", "The non-ready display must withhold content.")
    return status

def _consumer_status_contract(document: dict[str, Any], returncode: int) -> bool:
    status = document.get("status")
    if status not in CONSUMER_EXIT_CODES or returncode != CONSUMER_EXIT_CODES[status]:
        return False
    source = document.get("source")
    checks = document.get("checks")
    findings = document.get("findings")
    next_action = document.get("next_action")
    if (
        not isinstance(source, dict) or set(source) != set(IDENTITY_KEYS)
        or any(value is not None and not _is_hash(value) for value in source.values())
        or not isinstance(checks, list) or len(checks) != len(CHECK_IDS)
        or not isinstance(findings, list) or not _string_dict(next_action, NEXT_ACTION_KEYS)
    ):
        return False
    for expected, check in zip(CHECK_IDS, checks):
        if not isinstance(check, dict) or set(check) != {"check_id", "status"} or check.get("check_id") != expected or check.get("status") not in {"pass", "failed", "not_run"}:
            return False
    for finding in findings:
        if not _string_dict(finding, FINDING_KEYS) or RULE_RE.fullmatch(finding["rule_id"]) is None:
            return False
    expected_action = {
        "pass": "accept_markdown_display", "blocked": "reject_unsupported_display",
        "validation_failed": "reject_invalid_display", "error": "retry_consumer_validation",
    }[status]
    if next_action["code"] != expected_action:
        return False
    if status == "pass":
        return findings == [] and all(check["status"] == "pass" for check in checks)
    return bool(findings)

def _validate_consumer(document: dict[str, Any], returncode: int) -> str:
    if set(document) != CONSUMER_KEYS:
        raise DisplayHostProtocolError("display-host-consumer-document-shape", "The consumer result shape is unsupported.")
    if document.get("schema_version") != CONSUMER_SCHEMA_VERSION or document.get("consumer") != CONSUMER_ID:
        raise DisplayHostProtocolError("display-host-consumer-schema", "The consumer result schema is unsupported.")
    if document.get("guarantees") != CONSUMER_GUARANTEES:
        raise DisplayHostProtocolError("display-host-consumer-guarantees", "The consumer guarantees are invalid.")
    if not _consumer_status_contract(document, returncode):
        raise DisplayHostProtocolError("display-host-consumer-status", "The consumer status and exit code are inconsistent.")
    return document["status"]

def _finding(rule_id: str, status: str, message: str) -> HostFinding:
    safe_rule = rule_id if RULE_RE.fullmatch(rule_id) else "display-host-error"
    if status == "blocked":
        return HostFinding(safe_rule, "warning", "block", message)
    if status == "validation_failed":
        return HostFinding(safe_rule, "error", "reject", message)
    return HostFinding(safe_rule, "error", "retry", message)

def _next_action(status: str) -> dict[str, str]:
    values = {
        "ready": ("review_validated_markdown_display", "Review the Markdown display released after independent validation."),
        "blocked": ("inspect_display_result", "Inspect the safe blocked display status before an explicit retry."),
        "validation_failed": ("reject_display_result", "Reject the display result because validation did not pass."),
        "error": ("retry_explicit_display_host", "Retry the one-shot display host after correcting the safe failure."),
    }
    code, message = values.get(status, values["error"])
    return {"code": code, "message": message}

def _empty_summary(status: str = "not_run") -> dict[str, Any]:
    return {"status": status, "exit_code": None, "source": _identity_source()}

def _withheld(source: object = None) -> dict[str, Any]:
    identities = _identity_source(source)
    identities["content_id"] = None
    return {
        "status": "withheld", "type": "markdown",
        "media_type": "text/markdown; charset=utf-8", "encoding": "utf-8",
        **identities, "content": None,
    }

def _result(*, status: str, phases: Sequence[str], display: dict[str, Any] | None = None, consumer: dict[str, Any] | None = None, representation: dict[str, Any] | None = None, findings: Sequence[HostFinding] = ()) -> FilteredSnapshotDisplayHostResult:
    terminal_phases = tuple(phases)
    if not terminal_phases or terminal_phases[-1] != status:
        terminal_phases = (*terminal_phases, status)
    return FilteredSnapshotDisplayHostResult(
        status=status, lifecycle_phases=terminal_phases,
        display=display or _empty_summary(), consumer=consumer or _empty_summary(),
        representation=representation or _withheld(), findings=tuple(findings),
        next_action=_next_action(status),
    )

def _failure(rule_id: str, message: str, *, phases: Sequence[str], display: dict[str, Any] | None = None, consumer: dict[str, Any] | None = None, source: object = None) -> FilteredSnapshotDisplayHostResult:
    return _result(
        status="error", phases=phases, display=display, consumer=consumer,
        representation=_withheld(source),
        findings=(_finding(rule_id, "error", message),),
    )

def _serialized_size(result: FilteredSnapshotDisplayHostResult) -> int:
    return len(json.dumps(result.to_dict(), ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8"))

def run_filtered_snapshot_display_host(
    project_root: Path, *, envelope_file: str,
    task_id_filter: str | None = None, request_id_filter: str | None = None,
    representation: str = "markdown", timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    runner: Runner = _run_process,
) -> FilteredSnapshotDisplayHostResult:
    try:
        root = project_root.resolve()
    except (OSError, RuntimeError):
        return _failure("display-host-project-root-invalid", "The project root is invalid.", phases=("created",))
    if not _is_project_root(root):
        return _failure("display-host-project-root-invalid", "The project root is invalid.", phases=("created",))
    if not _valid_envelope(envelope_file):
        return _result(
            status="validation_failed", phases=("created",),
            findings=(_finding("display-host-envelope-invalid", "validation_failed", "The envelope selector is invalid."),),
        )
    if not _valid_filter(task_id_filter, TASK_RE) or not _valid_filter(request_id_filter, REQUEST_RE) or (task_id_filter is None and request_id_filter is None):
        return _result(
            status="validation_failed", phases=("created",),
            findings=(_finding("display-host-filter-invalid", "validation_failed", "At least one canonical exact filter is required."),),
        )
    if representation != "markdown":
        return _result(
            status="validation_failed", phases=("created",),
            findings=(_finding("display-host-representation-invalid", "validation_failed", "Only the fixed Markdown representation is supported."),),
        )
    if not _valid_timeout(timeout_seconds):
        return _failure("display-host-timeout-invalid", "The timeout is invalid.", phases=("created",))

    display_argv = _display_argv(
        root, envelope_file=envelope_file, task_id_filter=task_id_filter,
        request_id_filter=request_id_filter, timeout_seconds=float(timeout_seconds),
    )
    try:
        display_process = runner(display_argv, cwd=root, input_bytes=None, timeout_seconds=float(timeout_seconds))
    except TimeoutError:
        return _failure("display-host-display-timeout", "The fixed display timed out.", phases=("created", "displaying"))
    except KeyboardInterrupt:
        return _failure("display-host-cancelled", "The one-shot display host was cancelled.", phases=("created", "displaying"))
    except OSError:
        return _failure("display-host-display-start-failed", "The fixed display could not be started.", phases=("created", "displaying"))
    if len(display_process.stderr) > MAX_STDERR_BYTES:
        return _failure(
            "display-host-display-stderr-too-large", "The fixed display exceeded the stderr limit.",
            phases=("created", "displaying"),
            display={"status": "error", "exit_code": display_process.returncode, "source": _identity_source()},
        )
    try:
        display_document = _parse_object(
            display_process.stdout, limit=MAX_DISPLAY_OUTPUT_BYTES,
            prefix="display-host-display-protocol",
        )
        display_status = _validate_display(display_document, display_process.returncode)
    except DisplayHostProtocolError as exc:
        return _failure(
            exc.rule_id, exc.message, phases=("created", "displaying"),
            display={"status": "error", "exit_code": display_process.returncode, "source": _identity_source()},
        )

    display_source = _identity_source(display_document["representation"])
    display_summary = {"status": display_status, "exit_code": display_process.returncode, "source": display_source}
    try:
        consumer_process = runner(
            _consumer_argv(), cwd=root, input_bytes=display_process.stdout,
            timeout_seconds=float(timeout_seconds),
        )
    except TimeoutError:
        return _failure(
            "display-host-consumer-timeout", "The fixed consumer timed out.",
            phases=("created", "displaying", "validating"),
            display=display_summary, source=display_document["representation"],
        )
    except KeyboardInterrupt:
        return _failure(
            "display-host-cancelled", "The one-shot display host was cancelled.",
            phases=("created", "displaying", "validating"),
            display=display_summary, source=display_document["representation"],
        )
    except OSError:
        return _failure(
            "display-host-consumer-start-failed", "The fixed consumer could not be started.",
            phases=("created", "displaying", "validating"),
            display=display_summary, source=display_document["representation"],
        )
    if len(consumer_process.stderr) > MAX_STDERR_BYTES:
        return _failure(
            "display-host-consumer-stderr-too-large", "The fixed consumer exceeded the stderr limit.",
            phases=("created", "displaying", "validating"), display=display_summary,
            consumer={"status": "error", "exit_code": consumer_process.returncode, "source": _identity_source()},
            source=display_document["representation"],
        )
    try:
        consumer_document = _parse_object(
            consumer_process.stdout, limit=MAX_CONSUMER_OUTPUT_BYTES,
            prefix="display-host-consumer-protocol",
        )
        consumer_status = _validate_consumer(consumer_document, consumer_process.returncode)
    except DisplayHostProtocolError as exc:
        return _failure(
            exc.rule_id, exc.message, phases=("created", "displaying", "validating"),
            display=display_summary,
            consumer={"status": "error", "exit_code": consumer_process.returncode, "source": _identity_source()},
            source=display_document["representation"],
        )

    consumer_source = dict(consumer_document["source"])
    consumer_summary = {"status": consumer_status, "exit_code": consumer_process.returncode, "source": consumer_source}
    expected_consumer_status = {
        "ready": "pass", "blocked": "blocked",
        "validation_failed": "validation_failed", "error": "error",
    }[display_status]
    if consumer_status != expected_consumer_status:
        return _failure(
            "display-host-status-mismatch", "The display and consumer statuses are inconsistent.",
            phases=("created", "displaying", "validating"),
            display=display_summary, consumer=consumer_summary,
            source=display_document["representation"],
        )
    if consumer_source != display_source:
        return _failure(
            "display-host-validation-identity-mismatch", "The consumer identity does not match the display representation.",
            phases=("created", "displaying", "validating"),
            display=display_summary, consumer=consumer_summary,
            source=display_document["representation"],
        )

    if display_status != "ready":
        result = _result(
            status=display_status, phases=("created", "displaying", "validating"),
            display=display_summary, consumer=consumer_summary,
            representation=_withheld(display_document["representation"]),
            findings=(_finding(
                f"display-host-upstream-{display_status}", display_status,
                f"The validated display result is {display_status}; content was withheld.",
            ),),
        )
        if _serialized_size(result) <= MAX_HOST_OUTPUT_BYTES:
            return result
        return _failure(
            "display-host-output-too-large", "The display host result exceeded its output limit.",
            phases=("created", "displaying", "validating"),
            display=display_summary, consumer=consumer_summary,
            source=display_document["representation"],
        )

    ready = _result(
        status="ready", phases=("created", "displaying", "validating"),
        display=display_summary, consumer=consumer_summary,
        representation=dict(display_document["representation"]),
    )
    if _serialized_size(ready) <= MAX_HOST_OUTPUT_BYTES:
        return ready
    return _failure(
        "display-host-output-too-large", "The display host result exceeded its output limit.",
        phases=("created", "displaying", "validating"),
        display=display_summary, consumer=consumer_summary,
        source=display_document["representation"],
    )

def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate one fixed filtered snapshot Markdown display before release.",
        allow_abbrev=False,
    )
    parser.add_argument("--project-root", type=Path, default=None)
    parser.add_argument("--envelope", required=True)
    parser.add_argument("--task-id", default=None)
    parser.add_argument("--request-id", default=None)
    parser.add_argument("--representation", required=True, choices=("markdown",))
    parser.add_argument("--timeout-seconds", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--json", action="store_true")
    return parser

def _duplicate(argv: Sequence[str], option: str) -> bool:
    return sum(item == option or item.startswith(f"{option}=") for item in argv) > 1

def main(argv: Sequence[str] | None = None, *, stdout: TextIO | None = None) -> int:
    raw = list(argv) if argv is not None else list(sys.argv[1:])
    duplicate = any(_duplicate(raw, option) for option in ("--envelope", "--task-id", "--request-id", "--representation"))
    args = _parser().parse_args(raw)
    if duplicate:
        result = _result(
            status="validation_failed", phases=("created",),
            findings=(_finding(
                "display-host-argument-duplicate", "validation_failed",
                "Each display host selector may be provided at most once.",
            ),),
        )
    else:
        result = run_filtered_snapshot_display_host(
            args.project_root or Path.cwd(), envelope_file=args.envelope,
            task_id_filter=args.task_id, request_id_filter=args.request_id,
            representation=args.representation, timeout_seconds=args.timeout_seconds,
        )
    output = stdout if stdout is not None else sys.stdout
    output.write(json.dumps(result.to_dict(), ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n")
    return result.exit_code()

if __name__ == "__main__":
    raise SystemExit(main())
