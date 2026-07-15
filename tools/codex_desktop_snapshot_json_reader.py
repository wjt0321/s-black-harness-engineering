"""Stage 22/24 one-shot Codex Desktop snapshot JSON representation reader."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Callable, Sequence, TextIO

if __package__ in {None, ""}:  # Support direct execution by absolute script path.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent_runtime.adapter_validation import validate_envelope_file
from agent_runtime.loader import is_safe_to_read, normalize_path
from tools import codex_desktop_read_only_adapter as base_adapter
from tools.public_scan import SCAN_RULES

READER_SCHEMA_VERSION = "control-plane/codex-desktop-snapshot-read/v1"
READER_ID = "codex-desktop-snapshot-json-reader/v1"
SCOPED_READER_SCHEMA_VERSION = "control-plane/codex-desktop-snapshot-read/v2"
SCOPED_READER_ID = "codex-desktop-envelope-snapshot-json-reader/v2"
REPRESENTATION = "snapshot-json"
SNAPSHOT_SCHEMA_VERSION = "control-plane/control-panel-snapshot/v1"
DEFAULT_TIMEOUT_SECONDS = base_adapter.DEFAULT_TIMEOUT_SECONDS
MAX_TIMEOUT_SECONDS = base_adapter.MAX_TIMEOUT_SECONDS
MAX_OUTPUT_BYTES = base_adapter.MAX_OUTPUT_BYTES
SAFE_CONTENT_ID = re.compile(r"sha256:[0-9a-f]{64}\Z")
SECRET_SCAN_RULE_IDS = {
    "github-token",
    "openai-style-key",
    "tavily-key",
    "minimax-key",
    "generic-bearer-token",
}

HANDOFF_ARGV = base_adapter.PRODUCER_ARGV
CONSUMER_ARGV = base_adapter.CONSUMER_ARGV
SNAPSHOT_ARGV = (
    sys.executable,
    "-m",
    "agent_runtime.cli",
    "orchestration",
    "control-panel",
    "snapshot",
    "--json",
)
SNAPSHOT_REQUIRED_KEYS = {
    "status",
    "schema_version",
    "source",
    "summary",
    "sections",
    "guarantees",
    "next_action",
    "snapshot_id",
}
SNAPSHOT_OPTIONAL_KEYS = {"findings"}
SNAPSHOT_GUARANTEES = {
    "deterministic": True,
    "read_only": True,
    "writes_files": False,
    "writes_ledgers": False,
    "accesses_network": False,
    "executes_commands": False,
    "executes_adapters": False,
    "starts_service": False,
}
EXIT_CODES = {
    "ready": 0,
    "error": 1,
    "blocked": 2,
    "validation_failed": 5,
}


@dataclass(frozen=True)
class ReaderFinding:
    """One safe representation-reader finding."""

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
class ReaderResult:
    """Deterministic result for one explicit snapshot JSON read."""

    status: str
    lifecycle_phases: tuple[str, ...]
    handoff: dict[str, Any]
    representation: dict[str, Any]
    findings: tuple[ReaderFinding, ...] = ()
    next_action: dict[str, str] | None = None
    schema_version: str = READER_SCHEMA_VERSION
    reader_id: str = READER_ID
    source: dict[str, str] = field(
        default_factory=lambda: {"project_root": "project_root"}
    )

    def exit_code(self) -> int:
        return EXIT_CODES.get(self.status, 1)

    def to_dict(self) -> dict[str, Any]:
        guarantees = {
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
        }
        if "relative_envelope" in self.source:
            guarantees.update(
                {
                    "reads_envelope_scope": True,
                    "writes_ledgers": False,
                    "allows_arbitrary_paths": False,
                    "scans_envelope_secrets": True,
                }
            )
        return {
            "status": self.status,
            "schema_version": self.schema_version,
            "reader": self.reader_id,
            "source": self.source,
            "lifecycle": {
                "state": "closed",
                "phases": list(self.lifecycle_phases),
            },
            "handoff": self.handoff,
            "representation": self.representation,
            "findings": [finding.to_dict() for finding in self.findings],
            "guarantees": guarantees,
            "next_action": self.next_action,
        }


class ReaderProtocolError(Exception):
    """Safe protocol failure without retaining raw child output."""

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


Runner = Callable[..., base_adapter.ProcessResult]


def _finding(
    rule_id: str,
    *,
    severity: str,
    action: str,
    message: str,
) -> ReaderFinding:
    return ReaderFinding(
        rule_id=rule_id,
        severity=severity,
        action=action,
        message=message,
    )


def _next_action(status: str) -> dict[str, str]:
    if status == "ready":
        return {
            "code": "snapshot_loaded",
            "message": "Review the validated local snapshot; no operation was executed.",
        }
    if status == "blocked":
        return {
            "code": "select_snapshot_json",
            "message": "Explicitly select snapshot-json after reviewing the read-only boundary.",
        }
    if status == "validation_failed":
        return {
            "code": "fix_snapshot_contract",
            "message": "Fix the handoff or snapshot identity before another explicit read.",
        }
    return {
        "code": "review_reader_error",
        "message": "Review the local reader error before another one-shot action.",
    }


def _result(
    *,
    status: str,
    phases: Sequence[str],
    handoff: dict[str, Any] | None = None,
    representation: dict[str, Any] | None = None,
    findings: Sequence[ReaderFinding] = (),
    scope: dict[str, str] | None = None,
) -> ReaderResult:
    return ReaderResult(
        status=status,
        lifecycle_phases=tuple(phases) + ("closed",),
        handoff=handoff
        or {
            "status": "not_run",
            "exit_code": None,
            "source_handoff_id": None,
        },
        representation=representation
        or {
            "status": "not_run",
            "type": REPRESENTATION,
            "exit_code": None,
            "snapshot_id": None,
            "payload": None,
        },
        findings=tuple(findings),
        next_action=_next_action(status),
        schema_version=(SCOPED_READER_SCHEMA_VERSION if scope else READER_SCHEMA_VERSION),
        reader_id=(SCOPED_READER_ID if scope else READER_ID),
        source={"project_root": "project_root", **(scope or {})},
    )


def _failure(
    *,
    status: str,
    rule_id: str,
    message: str,
    phases: Sequence[str],
    handoff: dict[str, Any] | None = None,
    representation: dict[str, Any] | None = None,
    scope: dict[str, str] | None = None,
) -> ReaderResult:
    severity = "block" if status == "blocked" else "error"
    action = "block" if status == "blocked" else "error"
    return _result(
        status=status,
        phases=tuple(phases) + (status,),
        handoff=handoff,
        representation=representation,
        scope=scope,
        findings=(
            _finding(
                rule_id,
                severity=severity,
                action=action,
                message=message,
            ),
        ),
    )


def _parse_json_object(
    raw: bytes,
    *,
    prefix: str,
    invalid_message: str,
) -> dict[str, Any]:
    if len(raw) > MAX_OUTPUT_BYTES:
        raise ReaderProtocolError(
            f"{prefix}-output-too-large",
            invalid_message,
        )
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ReaderProtocolError(
            f"{prefix}-protocol-not-utf8",
            invalid_message,
        ) from exc
    if not text.strip():
        raise ReaderProtocolError(
            f"{prefix}-protocol-invalid-json",
            invalid_message,
        )

    def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ReaderProtocolError(
                    f"{prefix}-protocol-duplicate-key",
                    invalid_message,
                )
            result[key] = value
        return result

    try:
        payload = json.loads(text, object_pairs_hook=reject_duplicate_keys)
    except ReaderProtocolError:
        raise
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        raise ReaderProtocolError(
            f"{prefix}-protocol-invalid-json",
            invalid_message,
        ) from exc
    if not isinstance(payload, dict):
        raise ReaderProtocolError(
            f"{prefix}-protocol-invalid-json",
            invalid_message,
        )
    return payload


def _canonical_id(payload: dict[str, Any]) -> str:
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(canonical).hexdigest()}"


def _validate_envelope_scope(root: Path, envelope_file: str) -> dict[str, str]:
    raw_path = envelope_file.strip()
    normalized_input = raw_path.replace("\\", "/")
    windows_path = PureWindowsPath(raw_path)
    posix_path = PurePosixPath(normalized_input)
    if (
        not raw_path
        or raw_path != envelope_file
        or windows_path.is_absolute()
        or bool(windows_path.drive)
        or posix_path.is_absolute()
        or normalized_input.startswith("//")
        or str(posix_path) != normalized_input
        or any(part in {"", ".", ".."} for part in posix_path.parts)
    ):
        raise ReaderProtocolError(
            "envelope-path-invalid",
            "The envelope path must be an explicit normalized project-relative path.",
        )

    parts = posix_path.parts
    allowed_adapter = (
        len(parts) == 2
        and parts[0] == "adapters"
        and normalized_input.lower().endswith(".json")
    )
    allowed_runtime_draft = (
        len(parts) >= 3
        and parts[:2] == ("drafts", "runtime")
        and normalized_input.lower().endswith(".envelope.json")
    )
    if not (allowed_adapter or allowed_runtime_draft):
        raise ReaderProtocolError(
            "envelope-path-not-allowed",
            "The envelope path is outside the Stage 23 project-relative allowlist.",
        )

    resolved_root = root.resolve()
    candidate = resolved_root.joinpath(*parts)
    resolved_path = candidate.resolve()
    if resolved_path != resolved_root and resolved_root not in resolved_path.parents:
        raise ReaderProtocolError(
            "envelope-path-outside-root",
            "The envelope path resolves outside the selected project root.",
        )
    if not resolved_path.is_file() or not is_safe_to_read(resolved_path):
        raise ReaderProtocolError(
            "envelope-file-unavailable",
            "The selected envelope is not a safe readable JSON file.",
            status="error",
        )

    try:
        if resolved_path.stat().st_size > MAX_OUTPUT_BYTES:
            raise ReaderProtocolError(
                "envelope-input-too-large",
                "The selected envelope exceeded the input limit.",
            )
        raw = resolved_path.read_bytes()
    except ReaderProtocolError:
        raise
    except OSError as exc:
        raise ReaderProtocolError(
            "envelope-read-error",
            "The selected envelope could not be read safely.",
            status="error",
        ) from exc
    if len(raw) > MAX_OUTPUT_BYTES:
        raise ReaderProtocolError(
            "envelope-input-too-large",
            "The selected envelope exceeded the input limit.",
        )

    _parse_json_object(
        raw,
        prefix="envelope",
        invalid_message="The selected envelope is not a strict UTF-8 JSON object.",
    )
    text = raw.decode("utf-8")
    for rule in SCAN_RULES:
        if rule["id"] not in SECRET_SCAN_RULE_IDS:
            continue
        match = re.search(rule["regex"], text)
        if match is not None:
            line_number = text.count("\n", 0, match.start()) + 1
            raise ReaderProtocolError(
                f"envelope-secret-{rule['id']}",
                (
                    f"The selected envelope matched blocked secret rule {rule['id']} "
                    f"at line {line_number}; remove the secret before reading."
                ),
            )

    relative_path = normalize_path(resolved_path.relative_to(resolved_root))
    validation = validate_envelope_file(resolved_root, relative_path)
    if validation.status != "pass":
        rule_id = (
            validation.findings[0].rule_id
            if validation.findings
            else "envelope-validation-failed"
        )
        raise ReaderProtocolError(
            rule_id,
            "The selected envelope failed schema or consistency validation.",
        )

    content_id = f"sha256:{hashlib.sha256(raw).hexdigest()}"
    scope_identity = {
        "relative_envelope": relative_path,
        "envelope_content_id": content_id,
    }
    return {
        **scope_identity,
        "scope_id": _canonical_id(scope_identity),
    }


def _ensure_envelope_scope_unchanged(root: Path, scope: dict[str, str]) -> None:
    resolved_root = root.resolve()
    relative_path = PurePosixPath(scope["relative_envelope"])
    resolved_path = resolved_root.joinpath(*relative_path.parts).resolve()
    if (
        resolved_path != resolved_root
        and resolved_root not in resolved_path.parents
    ) or not resolved_path.is_file():
        raise ReaderProtocolError(
            "envelope-scope-content-changed",
            "The envelope scope changed during the one-shot read.",
        )
    try:
        if resolved_path.stat().st_size > MAX_OUTPUT_BYTES:
            raise ReaderProtocolError(
                "envelope-scope-content-changed",
                "The envelope scope changed during the one-shot read.",
            )
        raw = resolved_path.read_bytes()
    except ReaderProtocolError:
        raise
    except OSError as exc:
        raise ReaderProtocolError(
            "envelope-scope-content-changed",
            "The envelope scope changed during the one-shot read.",
        ) from exc
    content_id = f"sha256:{hashlib.sha256(raw).hexdigest()}"
    if content_id != scope["envelope_content_id"]:
        raise ReaderProtocolError(
            "envelope-scope-content-changed",
            "The envelope scope changed during the one-shot read.",
        )


def _scoped_argv(base: Sequence[str], relative_envelope: str) -> list[str]:
    argv = list(base)
    if argv and argv[-1] == "--json":
        return [*argv[:-1], "--envelope", relative_envelope, "--json"]
    return [*argv, "--envelope", relative_envelope]


def _safe_content_id(value: object) -> str | None:
    if isinstance(value, str) and SAFE_CONTENT_ID.fullmatch(value):
        return value
    return None


def _safe_consumer_findings(
    payload: dict[str, Any],
) -> tuple[ReaderFinding, ...]:
    status = str(payload.get("status"))
    severity = "block" if status == "blocked" else "error"
    action = "block" if status == "blocked" else "error"
    findings: list[ReaderFinding] = []
    for item in payload.get("findings", []):
        if not isinstance(item, dict):
            continue
        rule_id = item.get("rule_id")
        if not isinstance(rule_id, str) or not re.fullmatch(r"[a-z0-9-]{1,80}", rule_id):
            rule_id = "reader-consumer-finding"
        findings.append(
            _finding(
                rule_id,
                severity=severity,
                action=action,
                message="The reference consumer rejected the handoff.",
            )
        )
    return tuple(findings)


def _validate_snapshot(
    snapshot: dict[str, Any],
    *,
    handoff: dict[str, Any],
) -> None:
    snapshot_keys = set(snapshot)
    if not SNAPSHOT_REQUIRED_KEYS.issubset(snapshot_keys) or not snapshot_keys.issubset(
        SNAPSHOT_REQUIRED_KEYS | SNAPSHOT_OPTIONAL_KEYS
    ):
        raise ReaderProtocolError(
            "snapshot-protocol-shape",
            "The snapshot result does not match its strict v1 shape.",
        )
    if snapshot.get("schema_version") != SNAPSHOT_SCHEMA_VERSION:
        raise ReaderProtocolError(
            "snapshot-schema-mismatch",
            "The snapshot schema does not match the allowed representation.",
        )
    if snapshot.get("status") != "pass":
        raise ReaderProtocolError(
            "snapshot-status-invalid",
            "The snapshot representation did not return pass.",
        )
    if snapshot.get("source") != handoff.get("source"):
        raise ReaderProtocolError(
            "snapshot-source-mismatch",
            "The snapshot source does not match the validated handoff.",
        )
    if snapshot.get("guarantees") != SNAPSHOT_GUARANTEES:
        raise ReaderProtocolError(
            "snapshot-guarantees-invalid",
            "The snapshot no-write boundary does not match the reader contract.",
        )
    snapshot_id = _safe_content_id(snapshot.get("snapshot_id"))
    if snapshot_id is None:
        raise ReaderProtocolError(
            "snapshot-identity-invalid",
            "The snapshot identity is not a safe content id.",
        )
    expected = handoff.get("snapshot", {}).get("snapshot_id")
    if snapshot_id != expected:
        raise ReaderProtocolError(
            "snapshot-identity-mismatch",
            "The snapshot identity does not match the validated handoff.",
        )
    without_id = {key: value for key, value in snapshot.items() if key != "snapshot_id"}
    if _canonical_id(without_id) != snapshot_id:
        raise ReaderProtocolError(
            "snapshot-canonical-hash-mismatch",
            "The snapshot content does not match its content identity.",
        )


def _run_error(
    exc: Exception,
    *,
    phases: Sequence[str],
    handoff: dict[str, Any] | None = None,
    representation: dict[str, Any] | None = None,
    scope: dict[str, str] | None = None,
) -> ReaderResult:
    if isinstance(exc, TimeoutError):
        rule_id = "reader-process-timeout"
        message = "A fixed read-only child process exceeded its timeout."
    elif isinstance(exc, base_adapter.AdapterProcessError):
        rule_id = exc.rule_id.replace("adapter-", "reader-", 1)
        message = "A fixed read-only child process failed its bounded execution contract."
    else:
        rule_id = "reader-process-error"
        message = "A fixed read-only child process failed safely."
    return _failure(
        status="error",
        rule_id=rule_id,
        message=message,
        phases=phases,
        handoff=handoff,
        representation=representation,
        scope=scope,
    )


def run_snapshot_json_reader(
    project_root: str | Path,
    *,
    representation: str | None,
    envelope_file: str | None = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    runner: Runner | None = None,
) -> ReaderResult:
    """Read one validated snapshot JSON representation using only fixed argv."""
    if representation != REPRESENTATION:
        return _failure(
            status="blocked",
            rule_id="representation-selection-required",
            message="The snapshot-json representation must be selected explicitly.",
            phases=("created",),
        )
    if not base_adapter._valid_timeout(timeout_seconds):
        return _failure(
            status="error",
            rule_id="reader-timeout-invalid",
            message="The reader timeout must be greater than 0 and at most 60 seconds.",
            phases=("created",),
        )

    root = Path(project_root).resolve()
    if not base_adapter._is_project_root(root):
        return _failure(
            status="error",
            rule_id="reader-project-root-invalid",
            message="The selected project root is not a supported agent-runtime project.",
            phases=("created",),
        )

    scope: dict[str, str] | None = None
    if envelope_file is not None:
        try:
            scope = _validate_envelope_scope(root, envelope_file)
        except ReaderProtocolError as exc:
            return _failure(
                status=exc.status,
                rule_id=exc.rule_id,
                message=exc.message,
                phases=("created", "scoping"),
            )

    created_phases = ("created", "scoping") if scope is not None else ("created",)
    producing_phases = (*created_phases, "producing")
    validating_phases = (*producing_phases, "validating")
    reading_phases = (*validating_phases, "reading")

    handoff_argv = list(HANDOFF_ARGV)
    snapshot_argv = list(SNAPSHOT_ARGV)
    if scope is not None:
        relative_envelope = scope["relative_envelope"]
        handoff_argv = _scoped_argv(HANDOFF_ARGV, relative_envelope)
        snapshot_argv = _scoped_argv(SNAPSHOT_ARGV, relative_envelope)

    process_runner = runner or base_adapter._run_process
    handoff_summary: dict[str, Any] = {
        "status": "not_run",
        "exit_code": None,
        "source_handoff_id": None,
    }
    representation_summary: dict[str, Any] = {
        "status": "not_run",
        "type": REPRESENTATION,
        "exit_code": None,
        "snapshot_id": None,
        "payload": None,
    }

    try:
        producer_process = process_runner(
            handoff_argv,
            cwd=root,
            input_bytes=None,
            timeout_seconds=timeout_seconds,
        )
    except Exception as exc:
        return _run_error(exc, phases=producing_phases, scope=scope)

    if not producer_process.stdout:
        return _failure(
            status="error",
            rule_id="reader-handoff-no-output",
            message="The fixed handoff producer returned no descriptor.",
            phases=producing_phases,
            scope=scope,
        )
    if len(producer_process.stdout) > MAX_OUTPUT_BYTES:
        return _failure(
            status="error",
            rule_id="reader-handoff-output-too-large",
            message="The fixed handoff producer exceeded the output limit.",
            phases=producing_phases,
            scope=scope,
        )

    try:
        consumer_process = process_runner(
            list(CONSUMER_ARGV),
            cwd=root,
            input_bytes=producer_process.stdout,
            timeout_seconds=timeout_seconds,
        )
    except Exception as exc:
        return _run_error(
            exc,
            scope=scope,
            phases=validating_phases,
            handoff=handoff_summary,
        )

    try:
        consumer_payload = base_adapter._parse_consumer_result(
            consumer_process.stdout,
            returncode=consumer_process.returncode,
        )
    except base_adapter.AdapterProcessError as exc:
        return _failure(
            status="error",
            rule_id=exc.rule_id,
            message="The reference consumer returned an invalid safe result.",
            phases=validating_phases,
            scope=scope,
            handoff={
                "status": "error",
                "exit_code": consumer_process.returncode,
                "source_handoff_id": None,
            },
        )

    handoff_summary = {
        "status": consumer_payload["status"],
        "exit_code": consumer_process.returncode,
        "source_handoff_id": base_adapter._safe_handoff_id(
            consumer_payload.get("source_handoff_id")
        ),
    }
    if consumer_payload["status"] != "pass":
        mapped = (
            consumer_payload["status"]
            if consumer_payload["status"] in {"blocked", "validation_failed"}
            else "error"
        )
        return _result(
            status=mapped,
            phases=(*validating_phases, mapped),
            handoff=handoff_summary,
            representation=representation_summary,
            findings=_safe_consumer_findings(consumer_payload),
            scope=scope,
        )
    if producer_process.returncode != 0:
        return _failure(
            status="error",
            rule_id="reader-handoff-producer-nonzero",
            message="The handoff producer did not exit successfully.",
            phases=validating_phases,
            handoff=handoff_summary,
            scope=scope,
        )

    try:
        handoff_payload = _parse_json_object(
            producer_process.stdout,
            prefix="handoff",
            invalid_message="The validated handoff could not be parsed safely.",
        )
    except ReaderProtocolError as exc:
        return _failure(
            status="validation_failed",
            rule_id=exc.rule_id,
            message=exc.message,
            phases=validating_phases,
            handoff=handoff_summary,
            scope=scope,
        )

    if handoff_summary["source_handoff_id"] != handoff_payload.get("handoff_id"):
        return _failure(
            status="validation_failed",
            rule_id="handoff-identity-mismatch",
            message="The handoff identity does not match the consumer result.",
            phases=validating_phases,
            handoff=handoff_summary,
            scope=scope,
        )

    if scope is not None and handoff_payload.get("source") != {
        "envelope_file": scope["relative_envelope"]
    }:
        return _failure(
            status="validation_failed",
            rule_id="handoff-scope-mismatch",
            message="The handoff envelope scope does not match the explicit reader scope.",
            phases=validating_phases,
            handoff=handoff_summary,
            scope=scope,
        )

    try:
        snapshot_process = process_runner(
            snapshot_argv,
            cwd=root,
            input_bytes=None,
            timeout_seconds=timeout_seconds,
        )
    except Exception as exc:
        return _run_error(
            exc,
            scope=scope,
            phases=reading_phases,
            handoff=handoff_summary,
            representation=representation_summary,
        )

    representation_summary = {
        "status": "pass" if snapshot_process.returncode == 0 else "error",
        "type": REPRESENTATION,
        "exit_code": snapshot_process.returncode,
        "snapshot_id": None,
        "payload": None,
    }
    try:
        snapshot_payload = _parse_json_object(
            snapshot_process.stdout,
            prefix="snapshot",
            invalid_message="The fixed snapshot producer returned an invalid representation.",
        )
        _validate_snapshot(snapshot_payload, handoff=handoff_payload)
        if scope is not None:
            _ensure_envelope_scope_unchanged(root, scope)
    except ReaderProtocolError as exc:
        status = "error" if exc.rule_id == "snapshot-output-too-large" else "validation_failed"
        return _failure(
            status=status,
            rule_id=exc.rule_id,
            message=exc.message,
            phases=reading_phases,
            handoff=handoff_summary,
            representation=representation_summary,
            scope=scope,
        )

    if snapshot_process.returncode != 0:
        return _failure(
            status="error",
            rule_id="snapshot-exit-code-mismatch",
            message="The snapshot status and process exit code disagree.",
            phases=reading_phases,
            handoff=handoff_summary,
            representation=representation_summary,
            scope=scope,
        )

    representation_summary = {
        "status": "pass",
        "type": REPRESENTATION,
        "media_type": "application/json; charset=utf-8",
        "encoding": "utf-8",
        "exit_code": snapshot_process.returncode,
        "snapshot_id": snapshot_payload["snapshot_id"],
        "payload": snapshot_payload,
    }
    ready = _result(
        status="ready",
        phases=(*reading_phases, "ready"),
        handoff=handoff_summary,
        representation=representation_summary,
        scope=scope,
    )
    serialized = json.dumps(
        ready.to_dict(),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    if len(serialized) > MAX_OUTPUT_BYTES:
        return _failure(
            status="error",
            rule_id="reader-output-too-large",
            message="The validated reader result exceeded the output limit.",
            phases=reading_phases,
            handoff=handoff_summary,
            scope=scope,
        )
    return ready


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Read one validated local Control Panel snapshot JSON representation."
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=None,
        help="Project root to read; defaults to the current directory.",
    )
    parser.add_argument(
        "--representation",
        choices=(REPRESENTATION,),
        required=True,
        help="Explicit representation selection; only snapshot-json is supported.",
    )
    parser.add_argument(
        "--envelope",
        default=None,
        help=(
            "Explicit project-relative envelope scope under adapters/ or drafts/runtime/."
        ),
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=DEFAULT_TIMEOUT_SECONDS,
        help="Maximum seconds for each fixed child process (0 < value <= 60).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Accepted for automation compatibility; output is always JSON.",
    )
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    stdout: TextIO | None = None,
) -> int:
    args = _parser().parse_args(argv)
    result = run_snapshot_json_reader(
        args.project_root or Path.cwd(),
        representation=args.representation,
        envelope_file=args.envelope,
        timeout_seconds=args.timeout_seconds,
    )
    output = stdout if stdout is not None else sys.stdout
    json.dump(result.to_dict(), output, ensure_ascii=False, indent=2)
    output.write("\n")
    return result.exit_code()


if __name__ == "__main__":
    raise SystemExit(main())
