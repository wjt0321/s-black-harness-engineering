"""Stage 34 one-shot filtered snapshot Markdown display."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Sequence, TextIO

DISPLAY_SCHEMA_VERSION = "control-plane/codex-desktop-filtered-snapshot-display/v1"
DISPLAY_ID = "codex-desktop-filtered-snapshot-markdown-display/v1"
HOST_SCHEMA_VERSION = "control-plane/codex-desktop-filtered-snapshot-host/v1"
HOST_ID = "codex-desktop-filtered-snapshot-host/v1"
FILTERED_SCHEMA_VERSION = "control-plane/filtered-envelope-snapshot/v1"
FILTER_SCHEMA_VERSION = "control-plane/envelope-snapshot-filter/v1"
DEFAULT_TIMEOUT_SECONDS = 30.0
MAX_TIMEOUT_SECONDS = 60.0
MAX_HOST_OUTPUT_BYTES = 1024 * 1024
MAX_STDERR_BYTES = 64 * 1024
MAX_DISPLAY_OUTPUT_BYTES = 64 * 1024
MAX_FILTER_BYTES = 128
MAX_ENVELOPE_BYTES = 512
HASH_RE = re.compile(r"sha256:[0-9a-f]{64}\Z")
RULE_RE = re.compile(r"[a-z0-9-]{1,80}\Z")
TASK_RE = re.compile(r"task-[0-9]{8}-[0-9]{3,}\Z")
REQUEST_RE = re.compile(r"req-[0-9]{8}-[0-9]{3,}\Z")
TOOL_DIR = Path(__file__).resolve().parent
HOST_SCRIPT = TOOL_DIR / "codex_desktop_filtered_snapshot_host.py"
EXIT_CODES = {"ready": 0, "error": 1, "blocked": 2, "validation_failed": 5}
HOST_GUARANTEES = {
    "requires_explicit_user_action": True, "one_shot": True, "read_only": True,
    "reads_filtered_snapshot_json": True, "validates_before_display": True,
    "displays_validated_safe_summaries": True, "reads_html": False,
    "writes_files": False, "writes_ledgers": False, "accesses_network": False,
    "starts_service": False, "runs_fixed_read_processes": True,
    "executes_descriptor_argv": False, "executes_candidate_commands": False,
    "executes_adapters": False, "auto_retries": False,
    "persists_filtered_views": False, "allows_arbitrary_queries": False,
    "bounded_output": True,
}
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
HOST_KEYS = {"status", "schema_version", "host", "source", "lifecycle", "reader", "consumer", "representation", "findings", "guarantees", "next_action"}
IDENTITY_KEYS = {"base_snapshot_id", "scope_id", "filter_id", "view_id"}
HOST_REP_KEYS = {"status", "type", "media_type", "encoding", *IDENTITY_KEYS, "payload"}
FILTERED_KEYS = {"status", "schema_version", "source", "filter", "summary", "sections", "view_id"}
SUMMARY_KEYS = {"matched", "run_count", "approval_count", "artifact_count", "section_statuses"}
SECTION_NAMES = {"runs", "approvals", "artifacts", "reports"}
RUN_FIELDS = ("request_id", "task_id", "adapter_id", "capability", "operation", "mode", "status", "started_at", "ended_at")
APPROVAL_FIELDS = ("approval_id", "request_id", "task_id", "adapter_id", "operation", "target", "status", "requested_at", "resolved_at", "resolver")
ARTIFACT_FIELDS = ("artifact_id", "artifact_type", "task_id", "request_id", "producer", "timestamp", "summary", "safe_to_preview")
REPORT_KEYS = {"status", "scope", "availability", "reason", "message", "command_hint"}

@dataclass(frozen=True)
class ProcessResult:
    returncode: int
    stdout: bytes
    stderr: bytes = b""

@dataclass(frozen=True)
class DisplayFinding:
    rule_id: str
    severity: str
    action: str
    message: str
    def to_dict(self) -> dict[str, str]:
        return {"rule_id": self.rule_id, "severity": self.severity, "action": self.action, "message": self.message}

@dataclass(frozen=True)
class FilteredSnapshotDisplayResult:
    status: str
    lifecycle_phases: tuple[str, ...]
    host: dict[str, Any]
    representation: dict[str, Any]
    findings: tuple[DisplayFinding, ...] = ()
    next_action: dict[str, str] | None = None
    def exit_code(self) -> int:
        return EXIT_CODES.get(self.status, 1)
    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status, "schema_version": DISPLAY_SCHEMA_VERSION,
            "display": DISPLAY_ID, "source": {"project_root": "project_root"},
            "lifecycle": {"state": "closed", "phases": list(self.lifecycle_phases)},
            "host": self.host, "representation": self.representation,
            "findings": [item.to_dict() for item in self.findings],
            "guarantees": dict(DISPLAY_GUARANTEES), "next_action": self.next_action,
        }

class DuplicateJSONKeyError(ValueError):
    pass

class DisplayProcessError(Exception):
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
    except OSError as exc:
        raise DisplayProcessError("display-host-start-failed", "The fixed host could not be started.") from exc
    return ProcessResult(completed.returncode, completed.stdout, completed.stderr)

def _valid_timeout(value: float) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value)) and 0 < float(value) <= MAX_TIMEOUT_SECONDS

def _is_project_root(root: Path) -> bool:
    return root.is_dir() and (root / "pyproject.toml").is_file() and (root / "agent_runtime").is_dir() and HOST_SCRIPT.is_file()

def _valid_filter(value: str | None, pattern: re.Pattern[str]) -> bool:
    if value is None:
        return True
    try:
        encoded = value.encode("ascii")
    except (UnicodeEncodeError, AttributeError):
        return False
    return 0 < len(encoded) <= MAX_FILTER_BYTES and value == value.strip() and pattern.fullmatch(value) is not None

def _host_argv(root: Path, *, envelope_file: str, task_id_filter: str | None, request_id_filter: str | None, timeout_seconds: float) -> list[str]:
    argv = [sys.executable, str(HOST_SCRIPT), "--project-root", str(root), "--envelope", envelope_file]
    if task_id_filter is not None:
        argv.extend(("--task-id", task_id_filter))
    if request_id_filter is not None:
        argv.extend(("--request-id", request_id_filter))
    argv.extend(("--timeout-seconds", format(float(timeout_seconds), ".15g"), "--json"))
    return argv

def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateJSONKeyError
        result[key] = value
    return result

def _parse_json_object(raw: bytes) -> dict[str, Any]:
    if not raw:
        raise DisplayProcessError("display-host-no-output", "The fixed host returned no JSON document.")
    if len(raw) > MAX_HOST_OUTPUT_BYTES:
        raise DisplayProcessError("display-host-output-too-large", "The fixed host exceeded its output limit.")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise DisplayProcessError("display-host-protocol-not-utf8", "The fixed host returned non-UTF-8 output.") from exc
    try:
        value = json.loads(text, object_pairs_hook=_reject_duplicate_keys)
    except DuplicateJSONKeyError as exc:
        raise DisplayProcessError("display-host-protocol-duplicate-json-key", "The fixed host returned ambiguous JSON.") from exc
    except json.JSONDecodeError as exc:
        raise DisplayProcessError("display-host-protocol-invalid-json", "The fixed host returned invalid JSON.") from exc
    if not isinstance(value, dict):
        raise DisplayProcessError("display-host-protocol-invalid-shape", "The fixed host must return one JSON object.")
    return value

def _is_hash(value: object) -> bool:
    return isinstance(value, str) and HASH_RE.fullmatch(value) is not None

def _plain_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)

def _string_dict(value: object, keys: set[str]) -> bool:
    return isinstance(value, dict) and set(value) == keys and all(isinstance(item, str) for item in value.values())

def _rows_valid(rows: object, fields: tuple[str, ...], bool_field: str | None = None) -> bool:
    if not isinstance(rows, list):
        return False
    for row in rows:
        if not isinstance(row, dict) or set(row) != set(fields):
            return False
        for key, value in row.items():
            if (key == bool_field and not isinstance(value, bool)) or (key != bool_field and not isinstance(value, str)):
                return False
    return True

def _validate_common(document: dict[str, Any], returncode: int) -> str:
    if set(document) != HOST_KEYS:
        raise DisplayProcessError("display-host-document-shape", "The host result shape is unsupported.")
    if document.get("schema_version") != HOST_SCHEMA_VERSION or document.get("host") != HOST_ID:
        raise DisplayProcessError("display-host-schema-unsupported", "The host schema or id is unsupported.")
    if document.get("source") != {"project_root": "project_root"} or document.get("guarantees") != HOST_GUARANTEES:
        raise DisplayProcessError("display-host-boundary-invalid", "The host source or guarantees are invalid.")
    status = document.get("status")
    if status not in EXIT_CODES or EXIT_CODES[status] != returncode:
        raise DisplayProcessError("display-host-status-exit-mismatch", "The host status and exit code do not match.")
    lifecycle = document.get("lifecycle")
    if not isinstance(lifecycle, dict) or set(lifecycle) != {"state", "phases"} or lifecycle.get("state") != "closed" or not isinstance(lifecycle.get("phases"), list) or lifecycle["phases"][:1] != ["created"] or lifecycle["phases"][-2:] != [status, "closed"] or any(not isinstance(item, str) for item in lifecycle["phases"]):
        raise DisplayProcessError("display-host-lifecycle-invalid", "The host lifecycle is invalid.")
    reader, consumer, representation = document.get("reader"), document.get("consumer"), document.get("representation")
    if not isinstance(reader, dict) or set(reader) != {"status", "exit_code"} or not isinstance(reader.get("status"), str) or (reader.get("exit_code") is not None and not _plain_int(reader.get("exit_code"))):
        raise DisplayProcessError("display-host-reader-invalid", "The host reader summary is invalid.")
    if not isinstance(consumer, dict) or set(consumer) != {"status", "exit_code", "source"} or not isinstance(consumer.get("status"), str) or (consumer.get("exit_code") is not None and not _plain_int(consumer.get("exit_code"))) or not isinstance(consumer.get("source"), dict) or set(consumer["source"]) != IDENTITY_KEYS:
        raise DisplayProcessError("display-host-consumer-invalid", "The host consumer summary is invalid.")
    if not isinstance(representation, dict) or set(representation) != HOST_REP_KEYS or representation.get("type") != "filtered-snapshot-json" or representation.get("media_type") != "application/json; charset=utf-8" or representation.get("encoding") != "utf-8":
        raise DisplayProcessError("display-host-representation-invalid", "The host representation is invalid.")
    identities = consumer["source"]
    if any(value is not None and not _is_hash(value) for value in identities.values()) or any(representation.get(key) != identities[key] for key in IDENTITY_KEYS):
        raise DisplayProcessError("display-host-identity-invalid", "The host identity links are invalid.")
    if status != "ready" and (representation.get("status") != "withheld" or representation.get("payload") is not None):
        raise DisplayProcessError("display-host-withheld-invalid", "A non-ready host must withhold its representation.")
    findings = document.get("findings")
    if not isinstance(findings, list) or any(not _string_dict(item, {"rule_id", "severity", "action", "message"}) or RULE_RE.fullmatch(item["rule_id"]) is None for item in findings):
        raise DisplayProcessError("display-host-findings-invalid", "The host findings are invalid.")
    if not _string_dict(document.get("next_action"), {"code", "message"}):
        raise DisplayProcessError("display-host-next-action-invalid", "The host next action is invalid.")
    return status

def _validate_payload(document: dict[str, Any], task_filter: str | None, request_filter: str | None) -> dict[str, Any]:
    if document["reader"] != {"status": "pass", "exit_code": 0}:
        raise DisplayProcessError("display-host-ready-reader-invalid", "The ready host reader summary is invalid.")
    consumer, rep = document["consumer"], document["representation"]
    if consumer.get("status") != "pass" or consumer.get("exit_code") != 0 or document["findings"] != [] or document["next_action"].get("code") != "review_validated_filtered_snapshot":
        raise DisplayProcessError("display-host-ready-metadata-invalid", "The ready host metadata is inconsistent.")
    if rep.get("status") != "pass" or not isinstance(rep.get("payload"), dict):
        raise DisplayProcessError("display-host-ready-representation-invalid", "The ready host representation is invalid.")
    identities = {key: rep.get(key) for key in IDENTITY_KEYS}
    if any(not _is_hash(value) for value in identities.values()) or consumer["source"] != identities:
        raise DisplayProcessError("display-host-identity-mismatch", "The host identities do not match.")
    payload = rep["payload"]
    if set(payload) != FILTERED_KEYS or payload.get("status") != "pass" or payload.get("schema_version") != FILTERED_SCHEMA_VERSION:
        raise DisplayProcessError("display-payload-shape-invalid", "The filtered payload shape is invalid.")
    source, filter_spec = payload.get("source"), payload.get("filter")
    if not isinstance(source, dict) or set(source) != {"base_snapshot_id", "scope_id", "filter_id"} or source != {key: identities[key] for key in source} or payload.get("view_id") != identities["view_id"]:
        raise DisplayProcessError("display-payload-identity-mismatch", "The filtered payload identities do not match.")
    if not isinstance(filter_spec, dict) or set(filter_spec) != {"schema_version", "task_id", "request_id"} or filter_spec.get("schema_version") != FILTER_SCHEMA_VERSION or filter_spec.get("task_id") != task_filter or filter_spec.get("request_id") != request_filter:
        raise DisplayProcessError("display-payload-filter-invalid", "The filtered payload filter is invalid.")
    summary, sections = payload.get("summary"), payload.get("sections")
    if not isinstance(summary, dict) or set(summary) != SUMMARY_KEYS or not isinstance(summary.get("matched"), bool):
        raise DisplayProcessError("display-payload-summary-invalid", "The filtered payload summary is invalid.")
    if any(not _plain_int(summary.get(key)) or summary[key] < 0 for key in ("run_count", "approval_count", "artifact_count")):
        raise DisplayProcessError("display-payload-summary-invalid", "The filtered payload counts are invalid.")
    statuses = summary.get("section_statuses")
    if not isinstance(statuses, dict) or set(statuses) != SECTION_NAMES or any(not isinstance(value, str) for value in statuses.values()) or not isinstance(sections, dict) or set(sections) != SECTION_NAMES:
        raise DisplayProcessError("display-payload-sections-invalid", "The filtered payload sections are invalid.")
    specs = (("runs", "runs", RUN_FIELDS, None), ("approvals", "approvals", APPROVAL_FIELDS, None), ("artifacts", "artifacts", ARTIFACT_FIELDS, "safe_to_preview"))
    for section_name, collection_name, fields, bool_field in specs:
        section = sections.get(section_name)
        expected = {"status", "next_action", "scope", "availability", collection_name}
        if not isinstance(section, dict) or set(section) != expected or section.get("status") != "pass" or section.get("scope") != "envelope" or section.get("availability") != "stable_limited" or not isinstance(section.get("next_action"), str) or not _rows_valid(section.get(collection_name), fields, bool_field):
            raise DisplayProcessError("display-payload-sections-invalid", "A filtered collection is invalid.")
    reports = sections.get("reports")
    if not isinstance(reports, dict) or set(reports) != REPORT_KEYS or reports.get("status") != "unavailable" or reports.get("scope") != "request" or reports.get("availability") != "stable_limited" or reports.get("reason") != "request_context_required" or not isinstance(reports.get("message"), str) or not isinstance(reports.get("command_hint"), str):
        raise DisplayProcessError("display-payload-reports-invalid", "The filtered reports summary is invalid.")
    runs, approvals, artifacts = sections["runs"]["runs"], sections["approvals"]["approvals"], sections["artifacts"]["artifacts"]
    if summary["run_count"] != len(runs) or summary["approval_count"] != len(approvals) or summary["artifact_count"] != len(artifacts) or summary["matched"] is not bool(runs or approvals or artifacts) or statuses != {name: sections[name]["status"] for name in SECTION_NAMES}:
        raise DisplayProcessError("display-payload-summary-mismatch", "The filtered summary does not match its sections.")
    task_id, request_id = filter_spec["task_id"], filter_spec["request_id"]
    if task_id is None:
        semantics_valid = all(row["request_id"] == request_id for row in (*runs, *approvals, *artifacts))
    elif request_id is None:
        selected = {row["request_id"] for row in runs if row["request_id"]}
        semantics_valid = all(row["task_id"] == task_id for row in runs) and all(row["task_id"] == task_id or row["request_id"] in selected for row in (*approvals, *artifacts))
    else:
        selected = {row["request_id"] for row in runs if row["request_id"]}
        semantics_valid = all(row["task_id"] == task_id and row["request_id"] == request_id for row in runs) and all(row["request_id"] in selected for row in (*approvals, *artifacts))
    if not semantics_valid:
        raise DisplayProcessError("display-payload-filter-semantics-invalid", "The filtered rows do not match the exact filter semantics.")
    return payload

def _safe_literal(value: str | bool | int | None) -> str:
    literal = json.dumps(value, ensure_ascii=True, separators=(",", ":"))
    for source, escaped in {"`": "\\u0060", "|": "\\u007c", "<": "\\u003c", ">": "\\u003e", "&": "\\u0026", "[": "\\u005b", "]": "\\u005d", "(": "\\u0028", ")": "\\u0029"}.items():
        literal = literal.replace(source, escaped)
    return f"`{literal}`"

def _label(field: str) -> str:
    return field.replace("_", " ").title()

def _rows(title: str, rows: list[dict[str, Any]], fields: tuple[str, ...], empty: str) -> list[str]:
    lines = [f"## {title}", ""]
    if not rows:
        return lines + [empty, ""]
    singular = title[:-1] if title.endswith("s") else title
    for index, row in enumerate(rows, 1):
        lines += [f"### {singular} {index}", ""]
        lines += [f"- {_label(field)}: {_safe_literal(row[field])}" for field in fields]
        lines.append("")
    return lines

def _render_markdown(payload: dict[str, Any]) -> str:
    summary, filter_spec, source, sections = payload["summary"], payload["filter"], payload["source"], payload["sections"]
    lines = [
        "# Filtered Snapshot", "", "## Overview", "",
        f"- Matched: {_safe_literal(summary['matched'])}",
        f"- Run Count: {_safe_literal(summary['run_count'])}",
        f"- Approval Count: {_safe_literal(summary['approval_count'])}",
        f"- Artifact Count: {_safe_literal(summary['artifact_count'])}", "",
        "## Filter", "", f"- Task ID: {_safe_literal(filter_spec['task_id'])}",
        f"- Request ID: {_safe_literal(filter_spec['request_id'])}", "",
        "## Identity", "", f"- Base Snapshot ID: {_safe_literal(source['base_snapshot_id'])}",
        f"- Scope ID: {_safe_literal(source['scope_id'])}", f"- Filter ID: {_safe_literal(source['filter_id'])}",
        f"- View ID: {_safe_literal(payload['view_id'])}", "",
    ]
    lines += _rows("Runs", sections["runs"]["runs"], RUN_FIELDS, "No matching runs.")
    lines += _rows("Approvals", sections["approvals"]["approvals"], APPROVAL_FIELDS, "No matching approvals.")
    lines += _rows("Artifacts", sections["artifacts"]["artifacts"], ARTIFACT_FIELDS, "No matching artifacts.")
    reports = sections["reports"]
    lines += ["## Reports", "", f"- Status: {_safe_literal(reports['status'])}", f"- Availability: {_safe_literal(reports['availability'])}", f"- Reason: {_safe_literal(reports['reason'])}", f"- Message: {_safe_literal(reports['message'])}", f"- Command Hint: {_safe_literal(reports['command_hint'])}", ""]
    return "\n".join(lines)

def _withheld(identities: object = None) -> dict[str, Any]:
    safe = {key: None for key in IDENTITY_KEYS}
    if isinstance(identities, dict):
        for key in IDENTITY_KEYS:
            if _is_hash(identities.get(key)):
                safe[key] = identities[key]
    return {"status": "withheld", "type": "markdown", "media_type": "text/markdown; charset=utf-8", "encoding": "utf-8", **safe, "content_id": None, "content": None}

def _representation(payload: dict[str, Any]) -> dict[str, Any]:
    content = _render_markdown(payload)
    return {"status": "pass", "type": "markdown", "media_type": "text/markdown; charset=utf-8", "encoding": "utf-8", **payload["source"], "view_id": payload["view_id"], "content_id": "sha256:" + hashlib.sha256(content.encode("utf-8")).hexdigest(), "content": content}

def _finding(rule_id: str, status: str, message: str) -> DisplayFinding:
    safe_rule = rule_id if RULE_RE.fullmatch(rule_id) else "display-process-error"
    if status == "blocked":
        return DisplayFinding(safe_rule, "warning", "block", message)
    if status == "validation_failed":
        return DisplayFinding(safe_rule, "error", "reject", message)
    return DisplayFinding(safe_rule, "error", "retry", message)

def _next_action(status: str) -> dict[str, str]:
    values = {
        "ready": ("review_markdown_display", "Review the escaped Markdown; no operation was executed."),
        "blocked": ("inspect_host_result", "Inspect the fixed host boundary before another explicit display request."),
        "validation_failed": ("reject_host_result", "Reject the host result because validation failed."),
        "error": ("retry_explicit_display", "Retry the explicit one-shot display after correcting the safe failure."),
    }
    code, message = values.get(status, values["error"])
    return {"code": code, "message": message}

def _result(*, status: str, phases: Sequence[str], host_status: str = "not_run", host_exit_code: int | None = None, representation: dict[str, Any] | None = None, findings: Sequence[DisplayFinding] = ()) -> FilteredSnapshotDisplayResult:
    lifecycle = tuple(phases)
    if not lifecycle or lifecycle[-1] != "closed":
        lifecycle += ("closed",)
    return FilteredSnapshotDisplayResult(status, lifecycle, {"status": host_status, "exit_code": host_exit_code}, representation or _withheld(), tuple(findings), _next_action(status))

def _failure(rule_id: str, message: str, *, phases: Sequence[str], host_status: str = "error", host_exit_code: int | None = None, identities: object = None) -> FilteredSnapshotDisplayResult:
    return _result(status="error", phases=(*phases, "error"), host_status=host_status, host_exit_code=host_exit_code, representation=_withheld(identities), findings=(_finding(rule_id, "error", message),))

def _size(result: FilteredSnapshotDisplayResult) -> int:
    return len(json.dumps(result.to_dict(), ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")) + 1

def run_filtered_snapshot_display(project_root: Path, *, envelope_file: str, task_id_filter: str | None = None, request_id_filter: str | None = None, representation: str = "markdown", timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS, runner: Runner = _run_process) -> FilteredSnapshotDisplayResult:
    root = Path(project_root).resolve()
    if not _is_project_root(root):
        return _failure("display-project-root-invalid", "The selected project root is unsupported.", phases=("created",), host_status="not_run")
    if representation != "markdown":
        return _result(status="validation_failed", phases=("created", "validation_failed"), findings=(_finding("display-representation-unsupported", "validation_failed", "Only markdown is supported."),))
    if not isinstance(envelope_file, str) or not envelope_file or "\x00" in envelope_file or len(envelope_file.encode("utf-8", errors="ignore")) > MAX_ENVELOPE_BYTES:
        return _result(status="validation_failed", phases=("created", "validation_failed"), findings=(_finding("display-envelope-argument-invalid", "validation_failed", "The envelope argument is invalid."),))
    if not _valid_filter(task_id_filter, TASK_RE) or not _valid_filter(request_id_filter, REQUEST_RE) or (task_id_filter is None and request_id_filter is None):
        return _result(status="validation_failed", phases=("created", "validation_failed"), findings=(_finding("display-filter-invalid", "validation_failed", "At least one canonical exact filter is required."),))
    if not _valid_timeout(timeout_seconds):
        return _failure("display-timeout-invalid", "The timeout is invalid.", phases=("created",), host_status="not_run")
    argv = _host_argv(root, envelope_file=envelope_file, task_id_filter=task_id_filter, request_id_filter=request_id_filter, timeout_seconds=float(timeout_seconds))
    try:
        process = runner(argv, cwd=root, input_bytes=None, timeout_seconds=float(timeout_seconds))
    except TimeoutError:
        return _failure("display-host-timeout", "The fixed host timed out.", phases=("created", "loading"))
    except (DisplayProcessError, OSError) as exc:
        rule_id = exc.rule_id if isinstance(exc, DisplayProcessError) else "display-host-start-failed"
        message = exc.message if isinstance(exc, DisplayProcessError) else "The fixed host could not be started."
        return _failure(rule_id, message, phases=("created", "loading"))
    if len(process.stderr) > MAX_STDERR_BYTES:
        return _failure("display-host-stderr-too-large", "The fixed host exceeded the stderr limit.", phases=("created", "loading"), host_exit_code=process.returncode)
    try:
        document = _parse_json_object(process.stdout)
        status = _validate_common(document, process.returncode)
    except DisplayProcessError as exc:
        return _failure(exc.rule_id, exc.message, phases=("created", "loading"), host_exit_code=process.returncode)
    identities = document["consumer"]["source"]
    if status != "ready":
        result = _result(status=status, phases=("created", "loading", status), host_status=status, host_exit_code=process.returncode, representation=_withheld(identities), findings=(_finding(f"display-host-{status}", status, f"The fixed host returned {status}; content was withheld."),))
        return result if _size(result) <= MAX_DISPLAY_OUTPUT_BYTES else _failure("display-output-too-large", "The display result exceeded its output limit.", phases=("created", "loading"), host_status=status, host_exit_code=process.returncode)
    try:
        payload = _validate_payload(document, task_id_filter, request_id_filter)
        projected = _representation(payload)
    except DisplayProcessError as exc:
        return _failure(exc.rule_id, exc.message, phases=("created", "loading", "projecting"), host_status="ready", host_exit_code=0, identities=identities)
    result = _result(status="ready", phases=("created", "loading", "projecting", "ready"), host_status="ready", host_exit_code=0, representation=projected)
    return result if _size(result) <= MAX_DISPLAY_OUTPUT_BYTES else _failure("display-output-too-large", "The display result exceeded its output limit.", phases=("created", "loading", "projecting"), host_status="ready", host_exit_code=0, identities=identities)

def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Project one validated filtered snapshot into escaped Markdown.", allow_abbrev=False)
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
    duplicate = any(_duplicate(raw, option) for option in ("--task-id", "--request-id", "--representation"))
    args = _parser().parse_args(raw)
    if duplicate:
        result = _result(status="validation_failed", phases=("created", "validation_failed"), findings=(_finding("display-argument-duplicate", "validation_failed", "Each selector may be provided at most once."),))
    else:
        result = run_filtered_snapshot_display(args.project_root or Path.cwd(), envelope_file=args.envelope, task_id_filter=args.task_id, request_id_filter=args.request_id, representation=args.representation, timeout_seconds=args.timeout_seconds)
    (stdout if stdout is not None else sys.stdout).write(json.dumps(result.to_dict(), ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n")
    return result.exit_code()

if __name__ == "__main__":
    raise SystemExit(main())
