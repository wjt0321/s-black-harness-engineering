"""Stage 22 one-shot Codex Desktop snapshot JSON representation reader."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Sequence, TextIO

if __package__ in {None, ""}:  # Support direct execution by absolute script path.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools import codex_desktop_read_only_adapter as base_adapter

READER_SCHEMA_VERSION = "control-plane/codex-desktop-snapshot-read/v1"
READER_ID = "codex-desktop-snapshot-json-reader/v1"
REPRESENTATION = "snapshot-json"
SNAPSHOT_SCHEMA_VERSION = "control-plane/control-panel-snapshot/v1"
DEFAULT_TIMEOUT_SECONDS = base_adapter.DEFAULT_TIMEOUT_SECONDS
MAX_TIMEOUT_SECONDS = base_adapter.MAX_TIMEOUT_SECONDS
MAX_OUTPUT_BYTES = base_adapter.MAX_OUTPUT_BYTES
SAFE_CONTENT_ID = re.compile(r"sha256:[0-9a-f]{64}\Z")

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

    def exit_code(self) -> int:
        return EXIT_CODES.get(self.status, 1)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "schema_version": READER_SCHEMA_VERSION,
            "reader": READER_ID,
            "source": {"project_root": "project_root"},
            "lifecycle": {
                "state": "closed",
                "phases": list(self.lifecycle_phases),
            },
            "handoff": self.handoff,
            "representation": self.representation,
            "findings": [finding.to_dict() for finding in self.findings],
            "guarantees": {
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
            },
            "next_action": self.next_action,
        }


class ReaderProtocolError(Exception):
    """Safe protocol failure without retaining raw child output."""

    def __init__(self, rule_id: str, message: str) -> None:
        super().__init__(message)
        self.rule_id = rule_id
        self.message = message


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
    )


def _failure(
    *,
    status: str,
    rule_id: str,
    message: str,
    phases: Sequence[str],
    handoff: dict[str, Any] | None = None,
    representation: dict[str, Any] | None = None,
) -> ReaderResult:
    severity = "block" if status == "blocked" else "error"
    action = "block" if status == "blocked" else "error"
    return _result(
        status=status,
        phases=tuple(phases) + (status,),
        handoff=handoff,
        representation=representation,
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
    )


def run_snapshot_json_reader(
    project_root: str | Path,
    *,
    representation: str | None,
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
            list(HANDOFF_ARGV),
            cwd=root,
            input_bytes=None,
            timeout_seconds=timeout_seconds,
        )
    except Exception as exc:
        return _run_error(exc, phases=("created", "producing"))

    if not producer_process.stdout:
        return _failure(
            status="error",
            rule_id="reader-handoff-no-output",
            message="The fixed handoff producer returned no descriptor.",
            phases=("created", "producing"),
        )
    if len(producer_process.stdout) > MAX_OUTPUT_BYTES:
        return _failure(
            status="error",
            rule_id="reader-handoff-output-too-large",
            message="The fixed handoff producer exceeded the output limit.",
            phases=("created", "producing"),
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
            phases=("created", "producing", "validating"),
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
            phases=("created", "producing", "validating"),
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
            phases=("created", "producing", "validating", mapped),
            handoff=handoff_summary,
            representation=representation_summary,
            findings=_safe_consumer_findings(consumer_payload),
        )
    if producer_process.returncode != 0:
        return _failure(
            status="error",
            rule_id="reader-handoff-producer-nonzero",
            message="The handoff producer did not exit successfully.",
            phases=("created", "producing", "validating"),
            handoff=handoff_summary,
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
            phases=("created", "producing", "validating"),
            handoff=handoff_summary,
        )

    if handoff_summary["source_handoff_id"] != handoff_payload.get("handoff_id"):
        return _failure(
            status="validation_failed",
            rule_id="handoff-identity-mismatch",
            message="The handoff identity does not match the consumer result.",
            phases=("created", "producing", "validating"),
            handoff=handoff_summary,
        )

    try:
        snapshot_process = process_runner(
            list(SNAPSHOT_ARGV),
            cwd=root,
            input_bytes=None,
            timeout_seconds=timeout_seconds,
        )
    except Exception as exc:
        return _run_error(
            exc,
            phases=("created", "producing", "validating", "reading"),
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
    except ReaderProtocolError as exc:
        status = "error" if exc.rule_id == "snapshot-output-too-large" else "validation_failed"
        return _failure(
            status=status,
            rule_id=exc.rule_id,
            message=exc.message,
            phases=("created", "producing", "validating", "reading"),
            handoff=handoff_summary,
            representation=representation_summary,
        )

    if snapshot_process.returncode != 0:
        return _failure(
            status="error",
            rule_id="snapshot-exit-code-mismatch",
            message="The snapshot status and process exit code disagree.",
            phases=("created", "producing", "validating", "reading"),
            handoff=handoff_summary,
            representation=representation_summary,
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
        phases=("created", "producing", "validating", "reading", "ready"),
        handoff=handoff_summary,
        representation=representation_summary,
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
            phases=("created", "producing", "validating", "reading"),
            handoff=handoff_summary,
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
        help="Explicit representation selection; v1 only supports snapshot-json.",
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
        timeout_seconds=args.timeout_seconds,
    )
    output = stdout if stdout is not None else sys.stdout
    json.dump(result.to_dict(), output, ensure_ascii=False, indent=2)
    output.write("\n")
    return result.exit_code()


if __name__ == "__main__":
    raise SystemExit(main())
