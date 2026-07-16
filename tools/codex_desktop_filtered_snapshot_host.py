"""Stage 31 one-shot Codex Desktop filtered snapshot host integration."""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Sequence, TextIO

HOST_SCHEMA_VERSION = "control-plane/codex-desktop-filtered-snapshot-host/v1"
HOST_ID = "codex-desktop-filtered-snapshot-host/v1"
CONSUMER_SCHEMA_VERSION = "control-plane/filtered-snapshot-host-consumer-validation/v1"
CONSUMER_ID = "codex-desktop-filtered-snapshot-consumer/v1"
DEFAULT_TIMEOUT_SECONDS = 30.0
MAX_TIMEOUT_SECONDS = 60.0
MAX_READER_OUTPUT_BYTES = 1024 * 1024
MAX_CONSUMER_OUTPUT_BYTES = 64 * 1024
MAX_HOST_OUTPUT_BYTES = 1024 * 1024
MAX_STDERR_BYTES = 64 * 1024
MAX_FILTER_BYTES = 128
MAX_ENVELOPE_BYTES = 512
SAFE_HASH = re.compile(r"sha256:[0-9a-f]{64}\Z")
SAFE_RULE_ID = re.compile(r"[a-z0-9-]{1,80}\Z")
TASK_FILTER_PATTERN = re.compile(r"task-[0-9]{8}-[0-9]{3,}\Z")
REQUEST_FILTER_PATTERN = re.compile(r"req-[0-9]{8}-[0-9]{3,}\Z")

TOOL_DIR = Path(__file__).resolve().parent
READER_SCRIPT = TOOL_DIR / "codex_desktop_snapshot_json_reader.py"
CONSUMER_SCRIPT = TOOL_DIR / "codex_desktop_filtered_snapshot_consumer.py"
CONSUMER_ARGV = (sys.executable, str(CONSUMER_SCRIPT))
CHECK_IDS = (
    "document_shape", "schema_version", "reader_status", "lifecycle",
    "guarantees", "source_scope_identity", "filter_identity",
    "representation_links", "view_identity", "safe_sections", "filter_semantics",
)
CONSUMER_GUARANTEES = {
    "stdin_only": True, "read_only": True, "reads_filtered_snapshot": True,
    "writes_files": False, "accesses_network": False, "starts_service": False,
    "executes_reader": False, "executes_commands": False,
    "executes_adapters": False, "persists_input": False,
    "bounded_input": True, "bounded_output": True,
}
HOST_GUARANTEES = {
    "requires_explicit_user_action": True,
    "one_shot": True,
    "read_only": True,
    "reads_filtered_snapshot_json": True,
    "validates_before_display": True,
    "displays_validated_safe_summaries": True,
    "reads_html": False,
    "writes_files": False,
    "writes_ledgers": False,
    "accesses_network": False,
    "starts_service": False,
    "runs_fixed_read_processes": True,
    "executes_descriptor_argv": False,
    "executes_candidate_commands": False,
    "executes_adapters": False,
    "auto_retries": False,
    "persists_filtered_views": False,
    "allows_arbitrary_queries": False,
    "bounded_output": True,
}
EXIT_CODES = {"ready": 0, "error": 1, "blocked": 2, "validation_failed": 5}
CONSUMER_EXIT_CODES = {"pass": 0, "error": 1, "blocked": 2, "validation_failed": 5}
CONSUMER_KEYS = {
    "status", "schema_version", "consumer", "source", "checks",
    "findings", "guarantees", "next_action",
}
CONSUMER_SOURCE_KEYS = {"base_snapshot_id", "scope_id", "filter_id", "view_id"}
FINDING_KEYS = {"rule_id", "severity", "action", "message"}
NEXT_ACTION_KEYS = {"code", "message"}


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
        return {
            "rule_id": self.rule_id,
            "severity": self.severity,
            "action": self.action,
            "message": self.message,
        }


@dataclass(frozen=True)
class FilteredSnapshotHostResult:
    status: str
    lifecycle_phases: tuple[str, ...]
    reader: dict[str, Any]
    consumer: dict[str, Any]
    representation: dict[str, Any]
    findings: tuple[HostFinding, ...] = ()
    next_action: dict[str, str] | None = None

    def exit_code(self) -> int:
        return EXIT_CODES.get(self.status, 1)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "schema_version": HOST_SCHEMA_VERSION,
            "host": HOST_ID,
            "source": {"project_root": "project_root"},
            "lifecycle": {"state": "closed", "phases": list(self.lifecycle_phases)},
            "reader": self.reader,
            "consumer": self.consumer,
            "representation": self.representation,
            "findings": [finding.to_dict() for finding in self.findings],
            "guarantees": dict(HOST_GUARANTEES),
            "next_action": self.next_action,
        }


class DuplicateJSONKeyError(ValueError):
    pass


class HostProcessError(Exception):
    def __init__(self, rule_id: str, message: str) -> None:
        super().__init__(message)
        self.rule_id = rule_id
        self.message = message


Runner = Callable[..., ProcessResult]


def _minimal_environment() -> dict[str, str]:
    allowed = {
        "APPDATA", "HOME", "HOMEDRIVE", "HOMEPATH", "LOCALAPPDATA",
        "PATH", "PATHEXT", "SYSTEMROOT", "TEMP", "TMP", "USERPROFILE", "WINDIR",
    }
    environment = {key: os.environ[key] for key in allowed if key in os.environ}
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PYTHONUNBUFFERED"] = "1"
    return environment


def _run_process(
    argv: Sequence[str], *, cwd: Path, input_bytes: bytes | None, timeout_seconds: float
) -> ProcessResult:
    try:
        completed = subprocess.run(
            list(argv), cwd=str(cwd), env=_minimal_environment(), input=input_bytes,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout_seconds,
            check=False, shell=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise TimeoutError from exc
    except OSError as exc:
        raise HostProcessError(
            "host-process-start-failed",
            "The fixed local read process could not be started.",
        ) from exc
    return ProcessResult(completed.returncode, completed.stdout, completed.stderr)


def _valid_timeout(value: float) -> bool:
    return (
        isinstance(value, (int, float)) and not isinstance(value, bool)
        and math.isfinite(float(value)) and 0 < float(value) <= MAX_TIMEOUT_SECONDS
    )


def _is_project_root(root: Path) -> bool:
    return (
        root.is_dir() and (root / "pyproject.toml").is_file()
        and (root / "agent_runtime").is_dir()
        and READER_SCRIPT.is_file() and CONSUMER_SCRIPT.is_file()
    )


def _valid_filter(value: str | None, pattern: re.Pattern[str]) -> bool:
    if value is None:
        return True
    try:
        encoded = value.encode("utf-8")
    except UnicodeEncodeError:
        return False
    return (
        0 < len(encoded) <= MAX_FILTER_BYTES
        and value == value.strip() and pattern.fullmatch(value) is not None
    )


def _valid_envelope_argument(value: object) -> bool:
    if not isinstance(value, str) or not value or "\x00" in value:
        return False
    try:
        encoded = value.encode("utf-8")
    except UnicodeEncodeError:
        return False
    return len(encoded) <= MAX_ENVELOPE_BYTES


def _reader_argv(
    root: Path, *, envelope_file: str, task_id_filter: str | None,
    request_id_filter: str | None, timeout_seconds: float,
) -> list[str]:
    argv = [
        sys.executable, str(READER_SCRIPT), "--project-root", str(root),
        "--representation", "snapshot-json", "--envelope", envelope_file,
    ]
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


def _parse_json_object(raw: bytes, *, prefix: str, max_bytes: int) -> dict[str, Any]:
    if not raw:
        raise HostProcessError(f"{prefix}-no-output", "The fixed process returned no JSON document.")
    if len(raw) > max_bytes:
        raise HostProcessError(f"{prefix}-output-too-large", "The fixed process exceeded its output limit.")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HostProcessError(f"{prefix}-protocol-not-utf8", "The fixed process returned non-UTF-8 output.") from exc
    try:
        payload = json.loads(text, object_pairs_hook=_reject_duplicate_keys)
    except DuplicateJSONKeyError as exc:
        raise HostProcessError(f"{prefix}-protocol-duplicate-json-key", "The fixed process returned ambiguous JSON.") from exc
    except json.JSONDecodeError as exc:
        raise HostProcessError(f"{prefix}-protocol-invalid-json", "The fixed process returned invalid JSON.") from exc
    if not isinstance(payload, dict):
        raise HostProcessError(f"{prefix}-protocol-invalid-shape", "The fixed process must return one JSON object.")
    return payload


def _is_hash(value: object) -> bool:
    return isinstance(value, str) and SAFE_HASH.fullmatch(value) is not None


def _safe_consumer_source(payload: object = None) -> dict[str, str | None]:
    source = {"base_snapshot_id": None, "scope_id": None, "filter_id": None, "view_id": None}
    if isinstance(payload, dict) and isinstance(payload.get("source"), dict):
        for key in source:
            value = payload["source"].get(key)
            if _is_hash(value):
                source[key] = value
    return source


def _parse_consumer_result(raw: bytes, *, returncode: int) -> dict[str, Any]:
    payload = _parse_json_object(raw, prefix="host-consumer", max_bytes=MAX_CONSUMER_OUTPUT_BYTES)
    if set(payload) != CONSUMER_KEYS:
        raise HostProcessError("host-consumer-protocol-shape", "The consumer result shape is unsupported.")
    status = payload.get("status")
    if status not in CONSUMER_EXIT_CODES:
        raise HostProcessError("host-consumer-protocol-status", "The consumer returned an unsupported status.")
    if CONSUMER_EXIT_CODES[status] != returncode:
        raise HostProcessError("host-consumer-exit-mismatch", "The consumer status and exit code disagree.")
    if (
        payload.get("schema_version") != CONSUMER_SCHEMA_VERSION
        or payload.get("consumer") != CONSUMER_ID
        or payload.get("guarantees") != CONSUMER_GUARANTEES
    ):
        raise HostProcessError("host-consumer-contract-drift", "The consumer contract is unsupported.")
    source = payload.get("source")
    if not isinstance(source, dict) or set(source) != CONSUMER_SOURCE_KEYS:
        raise HostProcessError("host-consumer-source-invalid", "The consumer source summary is invalid.")
    if any(value is not None and not _is_hash(value) for value in source.values()):
        raise HostProcessError("host-consumer-source-invalid", "The consumer source summary is invalid.")
    checks = payload.get("checks")
    if not isinstance(checks, list) or len(checks) != len(CHECK_IDS):
        raise HostProcessError("host-consumer-checks-invalid", "The consumer checks are invalid.")
    actual_ids: list[str] = []
    for item in checks:
        if (
            not isinstance(item, dict) or set(item) != {"check_id", "status"}
            or not isinstance(item.get("check_id"), str)
            or item.get("status") not in {"pass", "failed", "not_run"}
        ):
            raise HostProcessError("host-consumer-checks-invalid", "The consumer checks are invalid.")
        actual_ids.append(item["check_id"])
    if tuple(actual_ids) != CHECK_IDS:
        raise HostProcessError("host-consumer-checks-invalid", "The consumer checks are invalid.")
    findings = payload.get("findings")
    if not isinstance(findings, list):
        raise HostProcessError("host-consumer-findings-invalid", "The consumer findings are invalid.")
    for item in findings:
        if (
            not isinstance(item, dict) or set(item) != FINDING_KEYS
            or not isinstance(item.get("rule_id"), str)
            or SAFE_RULE_ID.fullmatch(item["rule_id"]) is None
            or item.get("severity") not in {"warning", "error"}
            or item.get("action") not in {"block", "reject", "retry"}
            or not isinstance(item.get("message"), str)
        ):
            raise HostProcessError("host-consumer-findings-invalid", "The consumer findings are invalid.")
    next_action = payload.get("next_action")
    if (
        not isinstance(next_action, dict) or set(next_action) != NEXT_ACTION_KEYS
        or not all(isinstance(value, str) for value in next_action.values())
    ):
        raise HostProcessError("host-consumer-next-action-invalid", "The consumer next action is invalid.")
    if status == "pass" and (
        any(not _is_hash(value) for value in source.values())
        or any(item["status"] != "pass" for item in checks)
        or findings or next_action.get("code") != "accept_filtered_snapshot"
    ):
        raise HostProcessError("host-consumer-pass-invalid", "The consumer pass result is inconsistent.")
    return payload


def _extract_validated_representation(
    reader_raw: bytes, *, consumer_source: dict[str, Any]
) -> dict[str, Any]:
    document = _parse_json_object(reader_raw, prefix="host-reader", max_bytes=MAX_READER_OUTPUT_BYTES)
    source = document.get("source")
    representation = document.get("representation")
    if not isinstance(source, dict) or not isinstance(representation, dict):
        raise HostProcessError("host-reader-protocol-shape", "The validated reader result shape is unsupported.")
    payload = representation.get("payload")
    payload_source = payload.get("source") if isinstance(payload, dict) else None
    expected = {
        "base_snapshot_id": representation.get("base_snapshot_id"),
        "scope_id": source.get("scope_id"),
        "filter_id": source.get("filter_id"),
        "view_id": representation.get("view_id"),
    }
    if (
        document.get("status") != "ready" or representation.get("status") != "pass"
        or not isinstance(payload, dict) or not isinstance(payload_source, dict)
        or any(not _is_hash(value) for value in expected.values())
        or expected != consumer_source or payload.get("view_id") != expected["view_id"]
        or payload_source.get("base_snapshot_id") != expected["base_snapshot_id"]
        or payload_source.get("scope_id") != expected["scope_id"]
        or payload_source.get("filter_id") != expected["filter_id"]
    ):
        raise HostProcessError("host-validation-identity-mismatch", "The validated reader and consumer identities do not match.")
    return {
        "status": "pass", "type": "filtered-snapshot-json",
        "media_type": "application/json; charset=utf-8", "encoding": "utf-8",
        **expected, "payload": payload,
    }


def _finding(rule_id: str, *, severity: str, action: str, message: str) -> HostFinding:
    safe_rule = rule_id if SAFE_RULE_ID.fullmatch(rule_id) else "host-process-error"
    return HostFinding(safe_rule, severity, action, message)


def _empty_reader() -> dict[str, Any]:
    return {"status": "not_run", "exit_code": None}


def _empty_consumer(payload: object = None) -> dict[str, Any]:
    return {"status": "not_run", "exit_code": None, "source": _safe_consumer_source(payload)}


def _withheld_representation(source: object = None) -> dict[str, Any]:
    return {
        "status": "withheld", "type": "filtered-snapshot-json",
        "media_type": "application/json; charset=utf-8", "encoding": "utf-8",
        **_safe_consumer_source(source), "payload": None,
    }


def _next_action(status: str) -> dict[str, str]:
    if status == "ready":
        return {"code": "review_validated_filtered_snapshot", "message": "Review the validated safe summaries; no operation was executed."}
    if status == "blocked":
        return {"code": "inspect_reader_result", "message": "Inspect the reader result before another explicit read."}
    if status == "validation_failed":
        return {"code": "reject_filtered_snapshot", "message": "Reject the filtered snapshot because validation failed."}
    return {"code": "retry_explicit_read", "message": "Retry the explicit one-shot read after correcting the safe failure."}


def _result(
    *, status: str, phases: Sequence[str], reader: dict[str, Any] | None = None,
    consumer: dict[str, Any] | None = None, representation: dict[str, Any] | None = None,
    findings: Sequence[HostFinding] = (),
) -> FilteredSnapshotHostResult:
    lifecycle = tuple(phases)
    if not lifecycle or lifecycle[-1] != "closed":
        lifecycle = (*lifecycle, "closed")
    return FilteredSnapshotHostResult(
        status, lifecycle, reader or _empty_reader(), consumer or _empty_consumer(),
        representation or _withheld_representation(), tuple(findings), _next_action(status),
    )


def _failure(
    *, rule_id: str, message: str, phases: Sequence[str],
    reader: dict[str, Any] | None = None, consumer: dict[str, Any] | None = None,
) -> FilteredSnapshotHostResult:
    return _result(
        status="error", phases=(*phases, "error"), reader=reader, consumer=consumer,
        representation=_withheld_representation(consumer),
        findings=(_finding(rule_id, severity="error", action="error", message=message),),
    )


def _consumer_findings(payload: dict[str, Any]) -> tuple[HostFinding, ...]:
    blocked = payload["status"] == "blocked"
    severity, action = ("warning", "block") if blocked else ("error", "reject")
    message = (
        "The filtered snapshot consumer blocked the reader result."
        if blocked else "The filtered snapshot consumer rejected the reader result."
    )
    findings = tuple(
        _finding(item["rule_id"], severity=severity, action=action, message=message)
        for item in payload["findings"]
    )
    return findings or (_finding("host-consumer-rejected", severity=severity, action=action, message=message),)


def _serialized_size(result: FilteredSnapshotHostResult) -> int:
    return len((json.dumps(result.to_dict(), ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n").encode("utf-8"))


def run_filtered_snapshot_host(
    project_root: str | Path, *, envelope_file: str,
    task_id_filter: str | None = None, request_id_filter: str | None = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS, runner: Runner | None = None,
) -> FilteredSnapshotHostResult:
    """Run one fixed filtered reader and validate it before releasing its payload."""
    if not _valid_timeout(timeout_seconds):
        return _failure(rule_id="host-timeout-invalid", message="The host timeout must be greater than 0 and at most 60 seconds.", phases=("created",))
    root = Path(project_root).resolve()
    if not _is_project_root(root):
        return _failure(rule_id="host-project-root-invalid", message="The selected project root is not a supported agent-runtime project.", phases=("created",))
    if task_id_filter is None and request_id_filter is None:
        return _result(
            status="validation_failed", phases=("created", "validation_failed"),
            findings=(_finding("host-filter-required", severity="error", action="reject", message="The host requires at least one exact task or request filter."),),
        )
    if not _valid_filter(task_id_filter, TASK_FILTER_PATTERN) or not _valid_filter(request_id_filter, REQUEST_FILTER_PATTERN):
        return _result(
            status="validation_failed", phases=("created", "validation_failed"),
            findings=(_finding("host-filter-invalid", severity="error", action="reject", message="The host accepts only canonical exact task/request filters."),),
        )
    if not _valid_envelope_argument(envelope_file):
        return _result(
            status="validation_failed", phases=("created", "validation_failed"),
            findings=(_finding("host-envelope-required", severity="error", action="reject", message="The host requires one explicit project-relative envelope."),),
        )

    process_runner = runner or _run_process
    reader_summary = _empty_reader()
    consumer_summary = _empty_consumer()
    argv = _reader_argv(
        root, envelope_file=envelope_file, task_id_filter=task_id_filter,
        request_id_filter=request_id_filter, timeout_seconds=timeout_seconds,
    )
    try:
        reader_process = process_runner(argv, cwd=root, input_bytes=None, timeout_seconds=timeout_seconds)
    except TimeoutError:
        return _failure(rule_id="host-process-timeout", message="The fixed local read process exceeded its timeout.", phases=("created", "reading"), reader={"status": "timeout", "exit_code": None}, consumer=consumer_summary)
    except HostProcessError as exc:
        return _failure(rule_id=exc.rule_id, message=exc.message, phases=("created", "reading"), reader=reader_summary, consumer=consumer_summary)
    except Exception:
        return _failure(rule_id="host-process-error", message="The fixed local read process failed safely.", phases=("created", "reading"), reader=reader_summary, consumer=consumer_summary)

    reader_summary = {"status": "pass" if reader_process.returncode == 0 else "error", "exit_code": reader_process.returncode}
    if len(reader_process.stderr) > MAX_STDERR_BYTES:
        return _failure(rule_id="host-reader-stderr-too-large", message="The filtered snapshot reader exceeded the stderr limit.", phases=("created", "reading"), reader=reader_summary, consumer=consumer_summary)
    if not reader_process.stdout:
        return _failure(rule_id="host-reader-no-output", message="The filtered snapshot reader returned no result.", phases=("created", "reading"), reader=reader_summary, consumer=consumer_summary)
    if len(reader_process.stdout) > MAX_READER_OUTPUT_BYTES:
        return _failure(rule_id="host-reader-output-too-large", message="The filtered snapshot reader exceeded the 1 MiB output limit.", phases=("created", "reading"), reader=reader_summary, consumer=consumer_summary)

    try:
        consumer_process = process_runner(list(CONSUMER_ARGV), cwd=root, input_bytes=reader_process.stdout, timeout_seconds=timeout_seconds)
    except TimeoutError:
        return _failure(rule_id="host-process-timeout", message="The fixed local validation process exceeded its timeout.", phases=("created", "reading", "validating"), reader=reader_summary, consumer={"status": "timeout", "exit_code": None, "source": _safe_consumer_source()})
    except HostProcessError as exc:
        return _failure(rule_id=exc.rule_id, message=exc.message, phases=("created", "reading", "validating"), reader=reader_summary, consumer=consumer_summary)
    except Exception:
        return _failure(rule_id="host-process-error", message="The fixed local validation process failed safely.", phases=("created", "reading", "validating"), reader=reader_summary, consumer=consumer_summary)

    if len(consumer_process.stderr) > MAX_STDERR_BYTES:
        return _failure(rule_id="host-consumer-stderr-too-large", message="The filtered snapshot consumer exceeded the stderr limit.", phases=("created", "reading", "validating"), reader=reader_summary, consumer=consumer_summary)
    try:
        consumer_payload = _parse_consumer_result(consumer_process.stdout, returncode=consumer_process.returncode)
    except HostProcessError as exc:
        return _failure(
            rule_id=exc.rule_id, message=exc.message, phases=("created", "reading", "validating"),
            reader=reader_summary,
            consumer={"status": "error", "exit_code": consumer_process.returncode, "source": _safe_consumer_source()},
        )

    consumer_summary = {
        "status": consumer_payload["status"], "exit_code": consumer_process.returncode,
        "source": _safe_consumer_source(consumer_payload),
    }
    consumer_status = consumer_payload["status"]
    if consumer_status in {"blocked", "validation_failed"}:
        return _result(
            status=consumer_status,
            phases=("created", "reading", "validating", consumer_status),
            reader=reader_summary, consumer=consumer_summary,
            representation=_withheld_representation(consumer_payload),
            findings=_consumer_findings(consumer_payload),
        )
    if consumer_status == "error":
        return _failure(rule_id="host-consumer-error", message="The filtered snapshot consumer returned an error status.", phases=("created", "reading", "validating"), reader=reader_summary, consumer=consumer_summary)
    if reader_process.returncode != 0:
        return _failure(rule_id="host-reader-nonzero", message="The filtered snapshot reader did not exit successfully.", phases=("created", "reading", "validating"), reader=reader_summary, consumer=consumer_summary)
    try:
        representation = _extract_validated_representation(reader_process.stdout, consumer_source=consumer_payload["source"])
    except HostProcessError as exc:
        return _failure(rule_id=exc.rule_id, message=exc.message, phases=("created", "reading", "validating"), reader=reader_summary, consumer=consumer_summary)

    ready = _result(
        status="ready", phases=("created", "reading", "validating", "ready"),
        reader=reader_summary, consumer=consumer_summary, representation=representation,
    )
    if _serialized_size(ready) > MAX_HOST_OUTPUT_BYTES:
        return _failure(rule_id="host-output-too-large", message="The validated host result exceeded the 1 MiB output limit.", phases=("created", "reading", "validating"), reader=reader_summary, consumer=consumer_summary)
    return ready


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run one filtered snapshot read and validate it before display.",
        allow_abbrev=False,
    )
    parser.add_argument("--project-root", type=Path, default=None, help="Project root to read; defaults to the current directory.")
    parser.add_argument("--envelope", required=True, help="Explicit project-relative envelope accepted by the filtered reader.")
    parser.add_argument("--task-id", default=None, help="Exact canonical task id filter.")
    parser.add_argument("--request-id", default=None, help="Exact canonical request id filter.")
    parser.add_argument("--timeout-seconds", type=float, default=DEFAULT_TIMEOUT_SECONDS, help="Maximum seconds for each fixed child process (0 < value <= 60).")
    parser.add_argument("--json", action="store_true", help="Accepted for automation compatibility; output is always JSON.")
    return parser


def _has_duplicate_option(argv: Sequence[str], option: str) -> bool:
    return sum(item == option or item.startswith(f"{option}=") for item in argv) > 1


def main(argv: Sequence[str] | None = None, *, stdout: TextIO | None = None) -> int:
    raw_argv = list(argv) if argv is not None else list(sys.argv[1:])
    duplicate_filter = _has_duplicate_option(raw_argv, "--task-id") or _has_duplicate_option(raw_argv, "--request-id")
    args = _parser().parse_args(raw_argv)
    if duplicate_filter:
        result = _result(
            status="validation_failed", phases=("created", "validation_failed"),
            findings=(_finding("host-filter-argument-duplicate", severity="error", action="reject", message="Each exact host filter may be provided at most once."),),
        )
    else:
        result = run_filtered_snapshot_host(
            args.project_root or Path.cwd(), envelope_file=args.envelope,
            task_id_filter=args.task_id, request_id_filter=args.request_id,
            timeout_seconds=args.timeout_seconds,
        )
    output = stdout if stdout is not None else sys.stdout
    output.write(json.dumps(result.to_dict(), ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n")
    return result.exit_code()


if __name__ == "__main__":
    raise SystemExit(main())
