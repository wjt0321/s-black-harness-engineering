"""Stage 20 one-shot Codex Desktop read-only host adapter."""

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

ADAPTER_SCHEMA_VERSION = "control-plane/codex-desktop-read-only-adapter/v1"
ADAPTER_ID = "codex-desktop-read-only-adapter/v1"
CONSUMER_SCHEMA_VERSION = "control-plane/control-panel-host-consumer-validation/v1"
CONSUMER_ID = "local-reference-consumer/v1"
DEFAULT_TIMEOUT_SECONDS = 30.0
MAX_TIMEOUT_SECONDS = 60.0
MAX_OUTPUT_BYTES = 1024 * 1024
SAFE_HANDOFF_ID = re.compile(r"sha256:[0-9a-f]{64}\Z")

PRODUCER_ARGV = (
    sys.executable,
    "-m",
    "agent_runtime.cli",
    "orchestration",
    "control-panel",
    "handoff",
    "--json",
)
CONSUMER_SCRIPT = Path(__file__).with_name("control_panel_handoff_consumer.py")
CONSUMER_ARGV = (sys.executable, str(CONSUMER_SCRIPT))
CONSUMER_KEYS = {
    "status",
    "schema_version",
    "consumer",
    "source_handoff_id",
    "checks",
    "findings",
    "guarantees",
    "next_action",
}
VALID_STATUSES = {"pass", "blocked", "validation_failed", "error"}
EXIT_CODES = {
    "ready": 0,
    "error": 1,
    "blocked": 2,
    "validation_failed": 5,
}


@dataclass(frozen=True)
class ProcessResult:
    """Bounded, value-safe result of one fixed child process."""

    returncode: int
    stdout: bytes
    stderr: bytes = b""


@dataclass(frozen=True)
class AdapterFinding:
    """Safe finding emitted by the host adapter."""

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
class AdapterResult:
    """Deterministic result for one host adapter invocation."""

    status: str
    lifecycle_phases: tuple[str, ...]
    producer: dict[str, Any]
    consumer: dict[str, Any]
    findings: tuple[AdapterFinding, ...] = ()
    next_action: dict[str, str] | None = None

    def exit_code(self) -> int:
        return EXIT_CODES.get(self.status, 1)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "schema_version": ADAPTER_SCHEMA_VERSION,
            "adapter": ADAPTER_ID,
            "source": {"project_root": "project_root"},
            "lifecycle": {
                "state": "closed",
                "phases": list(self.lifecycle_phases),
            },
            "producer": self.producer,
            "consumer": self.consumer,
            "findings": [finding.to_dict() for finding in self.findings],
            "guarantees": {
                "one_shot": True,
                "read_only": True,
                "writes_files": False,
                "accesses_network": False,
                "starts_service": False,
                "reads_representations": False,
                "executes_descriptor_argv": False,
                "auto_retries": False,
            },
            "next_action": self.next_action,
        }


class AdapterProcessError(Exception):
    """Safe child-process failure without retaining raw process output."""

    def __init__(self, rule_id: str, message: str) -> None:
        super().__init__(message)
        self.rule_id = rule_id
        self.message = message


Runner = Callable[..., ProcessResult]


def _default_project_root() -> Path:
    return Path.cwd()


def _minimal_environment() -> dict[str, str]:
    """Return a small environment without secrets or user configuration."""
    allowed = {
        "APPDATA",
        "HOME",
        "HOMEDRIVE",
        "HOMEPATH",
        "LOCALAPPDATA",
        "PATH",
        "PATHEXT",
        "SYSTEMROOT",
        "TEMP",
        "TMP",
        "USERPROFILE",
        "WINDIR",
    }
    environment = {key: os.environ[key] for key in allowed if key in os.environ}
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PYTHONUNBUFFERED"] = "1"
    return environment


def _run_process(
    argv: Sequence[str],
    *,
    cwd: Path,
    input_bytes: bytes | None,
    timeout_seconds: float,
) -> ProcessResult:
    """Run one fixed process without a shell and enforce output limits."""
    try:
        completed = subprocess.run(
            list(argv),
            cwd=str(cwd),
            env=_minimal_environment(),
            input=input_bytes,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_seconds,
            check=False,
            shell=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise TimeoutError from exc
    except OSError as exc:
        raise AdapterProcessError(
            "adapter-process-start-error",
            "The read-only adapter could not start its fixed child process.",
        ) from exc

    stdout = completed.stdout or b""
    stderr = completed.stderr or b""
    if len(stdout) > MAX_OUTPUT_BYTES or len(stderr) > MAX_OUTPUT_BYTES:
        raise AdapterProcessError(
            "adapter-process-output-too-large",
            "A fixed child process exceeded the adapter output limit.",
        )
    return ProcessResult(
        returncode=int(completed.returncode),
        stdout=stdout,
        stderr=stderr,
    )


def _finding(
    rule_id: str,
    *,
    severity: str,
    action: str,
    message: str,
) -> AdapterFinding:
    return AdapterFinding(
        rule_id=rule_id,
        severity=severity,
        action=action,
        message=message,
    )


def _next_action(status: str) -> dict[str, str]:
    if status == "ready":
        return {
            "code": "handoff_validated",
            "message": "The read-only handoff was validated; no representation was loaded.",
        }
    if status == "blocked":
        return {
            "code": "reject_handoff",
            "message": "Reject the handoff until its producer or boundary is reviewed.",
        }
    if status == "validation_failed":
        return {
            "code": "fix_handoff_contract",
            "message": "Fix the handoff contract or identity before retrying validation.",
        }
    return {
        "code": "review_adapter_error",
        "message": "Review the local adapter error before starting another one-shot action.",
    }


def _result(
    *,
    status: str,
    phases: Sequence[str],
    producer: dict[str, Any] | None = None,
    consumer: dict[str, Any] | None = None,
    findings: Sequence[AdapterFinding] = (),
) -> AdapterResult:
    return AdapterResult(
        status=status,
        lifecycle_phases=tuple(phases) + ("closed",),
        producer=producer or {"status": "not_run", "exit_code": None},
        consumer=consumer or {
            "status": "not_run",
            "exit_code": None,
            "source_handoff_id": None,
        },
        findings=tuple(findings),
        next_action=_next_action(status),
    )


def _valid_timeout(value: float) -> bool:
    return math.isfinite(value) and 0 < value <= MAX_TIMEOUT_SECONDS


def _is_project_root(path: Path) -> bool:
    return (
        path.is_dir()
        and (path / "pyproject.toml").is_file()
        and (path / "agent_runtime").is_dir()
    )


def _safe_handoff_id(value: object) -> str | None:
    if isinstance(value, str) and SAFE_HANDOFF_ID.fullmatch(value):
        return value
    return None


def _parse_json_object(raw: bytes, *, rule_id: str, message: str) -> dict[str, Any]:
    if len(raw) > MAX_OUTPUT_BYTES:
        raise AdapterProcessError("adapter-consumer-output-too-large", message)
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise AdapterProcessError("consumer-protocol-not-utf8", message) from exc
    if not text.strip():
        raise AdapterProcessError(rule_id, message)

    def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise AdapterProcessError(
                    "consumer-protocol-duplicate-key",
                    "The reference consumer returned duplicate JSON keys.",
                )
            result[key] = value
        return result

    try:
        value = json.loads(text, object_pairs_hook=reject_duplicate_keys)
    except AdapterProcessError:
        raise
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        raise AdapterProcessError(rule_id, message) from exc
    if not isinstance(value, dict):
        raise AdapterProcessError(rule_id, message)
    return value


def _parse_consumer_result(raw: bytes, *, returncode: int) -> dict[str, Any]:
    payload = _parse_json_object(
        raw,
        rule_id="consumer-protocol-invalid-json",
        message="The reference consumer did not return one valid JSON object.",
    )
    if set(payload) != CONSUMER_KEYS:
        raise AdapterProcessError(
            "consumer-protocol-shape",
            "The reference consumer result does not match its strict v1 shape.",
        )
    status = payload.get("status")
    if status not in VALID_STATUSES:
        raise AdapterProcessError(
            "consumer-protocol-status",
            "The reference consumer returned an unsupported status.",
        )
    if payload.get("schema_version") != CONSUMER_SCHEMA_VERSION:
        raise AdapterProcessError(
            "consumer-protocol-schema",
            "The reference consumer returned an unsupported schema.",
        )
    if payload.get("consumer") != CONSUMER_ID:
        raise AdapterProcessError(
            "consumer-protocol-identity",
            "The reference consumer identity is not supported.",
        )
    source_handoff_id = payload.get("source_handoff_id")
    if source_handoff_id is not None and _safe_handoff_id(source_handoff_id) is None:
        raise AdapterProcessError(
            "consumer-protocol-source-id",
            "The reference consumer returned an unsafe source identity.",
        )
    expected_exit = {"pass": 0, "blocked": 2, "validation_failed": 5, "error": 1}[status]
    if returncode != expected_exit:
        raise AdapterProcessError(
            "consumer-protocol-exit-code",
            "The reference consumer status and exit code disagree.",
        )
    if not isinstance(payload.get("checks"), list):
        raise AdapterProcessError(
            "consumer-protocol-checks",
            "The reference consumer checks field is invalid.",
        )
    if not isinstance(payload.get("findings"), list):
        raise AdapterProcessError(
            "consumer-protocol-findings",
            "The reference consumer findings field is invalid.",
        )
    if not isinstance(payload.get("guarantees"), dict):
        raise AdapterProcessError(
            "consumer-protocol-guarantees",
            "The reference consumer guarantees field is invalid.",
        )
    if not isinstance(payload.get("next_action"), dict):
        raise AdapterProcessError(
            "consumer-protocol-next-action",
            "The reference consumer next_action field is invalid.",
        )
    return payload


def _consumer_findings(payload: dict[str, Any]) -> tuple[AdapterFinding, ...]:
    status = payload["status"]
    if status == "pass":
        return ()
    severity = "block" if status == "blocked" else "error"
    action = "block" if status == "blocked" else "error"
    message = (
        "The reference consumer blocked the handoff."
        if status == "blocked"
        else "The reference consumer rejected the handoff contract."
    )
    findings: list[AdapterFinding] = []
    for item in payload.get("findings", []):
        if not isinstance(item, dict):
            continue
        rule_id = item.get("rule_id")
        if not isinstance(rule_id, str) or not re.fullmatch(r"[a-z0-9-]{1,80}", rule_id):
            rule_id = "adapter-consumer-finding"
        findings.append(
            _finding(
                rule_id,
                severity=severity,
                action=action,
                message=message,
            )
        )
    return tuple(findings)


def _process_error_result(
    *,
    rule_id: str,
    message: str,
    phases: Sequence[str],
    producer: dict[str, Any] | None = None,
    consumer: dict[str, Any] | None = None,
) -> AdapterResult:
    return _result(
        status="error",
        phases=phases + ("error",),
        producer=producer,
        consumer=consumer,
        findings=(
            _finding(
                rule_id,
                severity="error",
                action="error",
                message=message,
            ),
        ),
    )


def run_read_only_adapter(
    project_root: str | Path,
    *,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    runner: Runner | None = None,
) -> AdapterResult:
    """Run fixed producer and reference consumer once, never descriptor argv."""
    if not _valid_timeout(timeout_seconds):
        return _process_error_result(
            rule_id="adapter-timeout-invalid",
            message="The adapter timeout must be greater than 0 and at most 60 seconds.",
            phases=("created",),
        )

    root = Path(project_root).resolve()
    if not _is_project_root(root):
        return _process_error_result(
            rule_id="adapter-project-root-invalid",
            message="The selected project root is not a supported agent-runtime project.",
            phases=("created",),
        )

    process_runner = runner or _run_process
    producer: dict[str, Any] = {"status": "not_run", "exit_code": None}
    consumer: dict[str, Any] = {
        "status": "not_run",
        "exit_code": None,
        "source_handoff_id": None,
    }

    try:
        producer_process = process_runner(
            list(PRODUCER_ARGV),
            cwd=root,
            input_bytes=None,
            timeout_seconds=timeout_seconds,
        )
    except TimeoutError:
        return _process_error_result(
            rule_id="adapter-process-timeout",
            message="The fixed read-only child process exceeded its timeout.",
            phases=("created", "producing"),
            producer={"status": "timeout", "exit_code": None},
            consumer=consumer,
        )
    except AdapterProcessError as exc:
        return _process_error_result(
            rule_id=exc.rule_id,
            message=exc.message,
            phases=("created", "producing"),
            producer=producer,
            consumer=consumer,
        )
    except Exception:
        return _process_error_result(
            rule_id="adapter-process-error",
            message="The fixed read-only child process failed safely.",
            phases=("created", "producing"),
            producer=producer,
            consumer=consumer,
        )

    producer = {
        "status": "pass" if producer_process.returncode == 0 else "error",
        "exit_code": producer_process.returncode,
    }
    if not producer_process.stdout:
        return _process_error_result(
            rule_id="adapter-producer-no-output",
            message="The handoff producer returned no descriptor.",
            phases=("created", "producing"),
            producer=producer,
            consumer=consumer,
        )
    if len(producer_process.stdout) > MAX_OUTPUT_BYTES:
        return _process_error_result(
            rule_id="adapter-producer-output-too-large",
            message="The handoff producer exceeded the 1 MiB descriptor limit.",
            phases=("created", "producing"),
            producer=producer,
            consumer=consumer,
        )

    try:
        consumer_process = process_runner(
            list(CONSUMER_ARGV),
            cwd=root,
            input_bytes=producer_process.stdout,
            timeout_seconds=timeout_seconds,
        )
    except TimeoutError:
        return _process_error_result(
            rule_id="adapter-process-timeout",
            message="The fixed read-only child process exceeded its timeout.",
            phases=("created", "producing", "validating"),
            producer=producer,
            consumer={"status": "timeout", "exit_code": None, "source_handoff_id": None},
        )
    except AdapterProcessError as exc:
        return _process_error_result(
            rule_id=exc.rule_id,
            message=exc.message,
            phases=("created", "producing", "validating"),
            producer=producer,
            consumer=consumer,
        )
    except Exception:
        return _process_error_result(
            rule_id="adapter-process-error",
            message="The fixed read-only child process failed safely.",
            phases=("created", "producing", "validating"),
            producer=producer,
            consumer=consumer,
        )

    try:
        consumer_payload = _parse_consumer_result(
            consumer_process.stdout,
            returncode=consumer_process.returncode,
        )
    except AdapterProcessError as exc:
        return _process_error_result(
            rule_id=exc.rule_id,
            message=exc.message,
            phases=("created", "producing", "validating"),
            producer=producer,
            consumer={
                "status": "error",
                "exit_code": consumer_process.returncode,
                "source_handoff_id": None,
            },
        )

    consumer = {
        "status": consumer_payload["status"],
        "exit_code": consumer_process.returncode,
        "source_handoff_id": _safe_handoff_id(
            consumer_payload.get("source_handoff_id")
        ),
    }
    consumer_status = consumer_payload["status"]
    if consumer_status == "pass" and producer_process.returncode != 0:
        return _process_error_result(
            rule_id="adapter-producer-nonzero",
            message="The producer process did not exit successfully.",
            phases=("created", "producing", "validating", "error"),
            producer=producer,
            consumer=consumer,
        )
    if consumer_status == "pass":
        return _result(
            status="ready",
            phases=("created", "producing", "validating", "ready"),
            producer=producer,
            consumer=consumer,
        )
    if consumer_status == "blocked":
        return _result(
            status="blocked",
            phases=("created", "producing", "validating", "blocked"),
            producer=producer,
            consumer=consumer,
            findings=_consumer_findings(consumer_payload),
        )
    if consumer_status == "validation_failed":
        return _result(
            status="validation_failed",
            phases=("created", "producing", "validating", "validation_failed"),
            producer=producer,
            consumer=consumer,
            findings=_consumer_findings(consumer_payload),
        )
    return _process_error_result(
        rule_id="adapter-consumer-error",
        message="The reference consumer returned an error status.",
        phases=("created", "producing", "validating", "error"),
        producer=producer,
        consumer=consumer,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run one fixed, read-only Codex Desktop handoff validation."
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=None,
        help="Project root to validate; defaults to the current directory.",
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
    result = run_read_only_adapter(
        args.project_root or _default_project_root(),
        timeout_seconds=args.timeout_seconds,
    )
    output = stdout if stdout is not None else sys.stdout
    json.dump(result.to_dict(), output, ensure_ascii=False, indent=2)
    output.write("\n")
    return result.exit_code()


if __name__ == "__main__":
    raise SystemExit(main())
