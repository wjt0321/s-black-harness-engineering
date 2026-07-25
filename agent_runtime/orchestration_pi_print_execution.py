"""Limited orchestration for the single fixed Pi dry-run print execution (Stage 62).

Contract: ``docs/110-pi-controlled-dry-run-adapter-contract.md``.

One fixed operation only::

    adapter_id  = pi-cli
    capability  = cli_agent_print
    operation   = pi_cli_print
    argv        = ["pi", "--print", "--no-session", "--no-tools", "<bounded prompt>"]
    shell       = false

A committed run performs ONE real model call through the operator-owned local
Pi CLI. Raw model output, the prompt text, environment values and every
secret stay withheld; only digests, byte counts, truncation flags and fixed
failure codes are released.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from .adapter_registry import load_adapter_registry
from .execution_audit_writer import (
    ExecutionAuditWriteResult,
    record_execution_attempt_started,
    record_execution_terminal,
)
from .execution_lease import (
    _LeaseCapability,
    _held_lease_capability,
    _validate_lease_capability,
    acquire_execution_lease,
)
from .execution_trust import WindowsTrustBackend, sanitize_path
from .pi_print_runner import FixedProcessResult, run_fixed_pi_print_process
from .pi_runtime_discovery import PiRuntimeStatus, discover_pi_runtime
from .policy import check_text
from .result import CheckResult, Finding, EXIT_PASS

SCHEMA_VERSION = "control-plane/pi-cli-print-execution/v1"
_ADAPTER_ID = "pi-cli"
_CAPABILITY = "cli_agent_print"
_OPERATION = "pi_cli_print"
_ARGV_SHAPE = ["pi", "--print", "--no-session", "--no-tools", "<prompt>"]
_TOKEN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,95}$")
_PLAN_HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_MAX_PROMPT_BYTES = 4096
_MAX_OUTPUT_LINES = 4096
_DEFAULT_TIMEOUT_SECONDS = 60
_MIN_TIMEOUT_SECONDS = 5
_MAX_TIMEOUT_SECONDS = 120
_PI_BASENAMES = ("pi.cmd", "pi.exe", "pi")
_ENV_SYSTEM_VARS = ("SYSTEMROOT", "COMSPEC", "WINDIR")
_WITHHELD = "<withheld>"


@dataclass
class PiPrintExecutionResult(CheckResult):
    plan_hash: str | None = None
    summary: dict[str, Any] | None = None
    lifecycle: str = "withheld"
    audit: dict[str, Any] = field(default_factory=dict)
    process: dict[str, Any] = field(default_factory=dict)
    runtime: dict[str, Any] = field(default_factory=dict)
    task_id: str | None = None
    request_id: str | None = None

    def exit_code(self) -> int:
        if self.status == "ready":
            return EXIT_PASS
        return super().exit_code()

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "schema_version": SCHEMA_VERSION,
            "executor": {
                "adapter_id": _ADAPTER_ID,
                "capability": _CAPABILITY,
                "operation": _OPERATION,
                "actor": "local-operator",
                "platform": "windows",
            },
            "source": {
                "adapter_registry": "adapters/adapters.sample.json",
                "audit_writer": "agent_runtime.execution_audit_writer",
                "contract": "docs/110-pi-controlled-dry-run-adapter-contract.md",
            },
            "lifecycle": self.lifecycle,
            "scope": {
                "task_id": self.task_id,
                "request_id": self.request_id,
            },
            "plan": {"plan_hash": self.plan_hash},
            "process": dict(self.process),
            "runtime": dict(self.runtime),
            "summary": None if self.summary is None else dict(self.summary),
            "audit": dict(self.audit),
            "findings": [finding.to_dict() for finding in self.findings],
            "guarantees": {
                "fixed_argv": True,
                "shell": False,
                "retry": False,
                "background": False,
                "real_model_call": True,
                "trusted_executable_chain": False,
                "prompt_withheld": True,
                "raw_output_withheld": True,
                "secrets_withheld": True,
                "session_written": False,
                "tools_enabled": False,
            },
            "next_action": self.next_action,
        }

    def render_human(self, no_color: bool = False) -> str:
        lines = [
            "FIXED PI DRY-RUN PRINT EXECUTION",
            f"status={self.status}",
            f"lifecycle={self.lifecycle}",
        ]
        if self.plan_hash is not None:
            lines.append(f"plan_hash={self.plan_hash}")
        if self.summary is not None:
            lines.append(
                "summary: "
                f"provider={self.summary.get('provider')} "
                f"model={self.summary.get('model')} "
                f"stdout_bytes={self.summary.get('stdout_byte_count')} "
                f"stdout_sha256={self.summary.get('stdout_digest')}"
            )
        for finding in self.findings:
            lines.append(f"- {finding.rule_id}: {finding.message}")
        if self.next_action:
            lines.append(f"Next: {self.next_action}")
        return "\n".join(lines)


def _result(
    status: str,
    *,
    task_id: str,
    request_id: str,
    findings: list[Finding] | None = None,
    plan_hash: str | None = None,
    lifecycle: str = "withheld",
    audit: dict[str, Any] | None = None,
    process: dict[str, Any] | None = None,
    runtime: dict[str, Any] | None = None,
    summary: dict[str, Any] | None = None,
    next_action: str,
) -> PiPrintExecutionResult:
    return PiPrintExecutionResult(
        status=status,
        findings=findings or [],
        next_action=next_action,
        plan_hash=plan_hash,
        lifecycle=lifecycle,
        audit=audit or {},
        process=process or {},
        runtime=runtime or {},
        summary=summary,
        task_id=task_id,
        request_id=request_id,
    )


def _safe_finding(rule_id: str, message: str, status: str) -> Finding:
    return Finding(
        rule_id,
        "block" if status == "blocked" else "error",
        status,
        message,
    )


def _canonical_digest(value: object) -> str:
    raw = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _default_registry_check(root: Path) -> bool:
    registry, _, _ = load_adapter_registry(root)
    if registry is None:
        return False
    adapter = registry.get_adapter(_ADAPTER_ID)
    return bool(
        adapter is not None
        and adapter.enabled
        and adapter.kind == "pi_cli"
        and adapter.risk_level == "external"
        and _CAPABILITY in adapter.capabilities
    )


def _validate_prompt(prompt: str) -> Finding | None:
    if not isinstance(prompt, str) or not prompt.strip():
        return _safe_finding(
            "pi-print-prompt-empty",
            "The fixed Pi print prompt must be a non-empty string.",
            "blocked",
        )
    if prompt.lstrip().startswith("-"):
        return _safe_finding(
            "pi-print-prompt-flag-like",
            "The fixed Pi print prompt must not start with a flag-like token.",
            "blocked",
        )
    try:
        encoded = prompt.encode("utf-8")
    except UnicodeEncodeError:
        return _safe_finding(
            "pi-print-prompt-invalid-utf8",
            "The fixed Pi print prompt must be valid UTF-8.",
            "blocked",
        )
    if len(encoded) > _MAX_PROMPT_BYTES:
        return _safe_finding(
            "pi-print-prompt-too-large",
            "The fixed Pi print prompt exceeds the bounded size limit.",
            "blocked",
        )
    for char in prompt:
        code = ord(char)
        if (code < 32 and char not in "\n\t") or code == 127:
            return _safe_finding(
                "pi-print-prompt-control-characters",
                "The fixed Pi print prompt contains disallowed control characters.",
                "blocked",
            )
    return None


def _build_fixed_environment(
    root: Path,
    readiness: PiRuntimeStatus,
) -> tuple[dict[str, str], str] | None:
    """Rebuild a minimal child environment from an explicit allowlist.

    Returns ``(environment, path_identity)`` or ``None`` when the referenced
    API key variable is missing (value presence is checked, never echoed).
    """
    allow_directory = None
    if os.name == "nt":
        backend = WindowsTrustBackend()
        allow_directory = lambda path: not backend._is_writable(path, directory=True)  # noqa: E731
    sanitized = sanitize_path(
        os.environ.get("PATH", ""),
        root,
        platform="windows",
        allow_directory=allow_directory,
    )
    environment = {"PATH": sanitized.serialized}
    for name in _ENV_SYSTEM_VARS:
        value = os.environ.get(name)
        if value:
            environment[name] = value
    environment["PI_CODING_AGENT_DIR"] = readiness.agent_dir or ""
    environment["AGENT_RUNTIME_ROOT"] = str(root)
    api_key_env = readiness.api_key_env
    if api_key_env:
        value = os.environ.get(api_key_env, "")
        if not value.strip():
            return None
        environment[api_key_env] = value
    return environment, sanitized.identity


def _resolve_pi_executable(root: Path) -> Path | None:
    """Resolve the fixed ``pi`` basename from the operator PATH (first match)."""
    root_resolved = root.resolve()
    for raw in os.environ.get("PATH", "").split(os.pathsep):
        if not raw:
            continue
        candidate_dir = Path(raw)
        if not candidate_dir.is_absolute():
            continue
        try:
            resolved_dir = candidate_dir.resolve(strict=True)
        except (OSError, RuntimeError):
            continue
        if resolved_dir == root_resolved or root_resolved in resolved_dir.parents:
            continue
        for basename in _PI_BASENAMES:
            candidate = resolved_dir / basename
            try:
                if candidate.is_file() and not candidate.is_symlink():
                    return candidate
            except OSError:
                continue
    return None


def _runtime_projection(readiness: PiRuntimeStatus) -> dict[str, Any]:
    return {
        "status": readiness.status,
        "agent_dir": readiness.agent_dir,
        "default_provider": readiness.default_provider,
        "default_model": readiness.default_model,
        "api_key_env": readiness.api_key_env,
    }


def _readiness_identity(readiness: PiRuntimeStatus) -> str:
    return _canonical_digest(
        {
            "agent_dir": readiness.agent_dir,
            "default_provider": readiness.default_provider,
            "default_model": readiness.default_model,
            "api_key_env": readiness.api_key_env,
        }
    )


def _services(
    overrides: dict[str, object] | None,
) -> dict[str, Callable[..., Any]]:
    values: dict[str, Callable[..., Any]] = {
        "discover": discover_pi_runtime,
        "build_environment": _build_fixed_environment,
        "resolve_executable": _resolve_pi_executable,
        "scan_text": lambda root, text: check_text(root, text),
        "record_started": record_execution_attempt_started,
        "run_process": run_fixed_pi_print_process,
        "record_terminal": record_execution_terminal,
    }
    if overrides:
        values.update(
            {
                key: value
                for key, value in overrides.items()
                if key in values and callable(value)
            }
        )
    return values


def _terminal_failure(
    *,
    root: Path,
    task_id: str,
    request_id: str,
    plan_hash: str,
    attempt_id: str,
    status: str,
    phase: str,
    failure_code: str,
    findings: list[Finding],
    terminal: Callable[..., ExecutionAuditWriteResult],
    process: FixedProcessResult | None = None,
    guard_status: str = "failed",
    cancelled: bool = False,
    runtime: dict[str, Any] | None = None,
) -> PiPrintExecutionResult:
    event_type = "execution_cancelled" if cancelled else "execution_failed"
    terminal_result = terminal(
        root,
        attempt_id=attempt_id,
        event_type=event_type,
        phase="cancelled" if cancelled else phase,
        exit_code=None if process is None else process.exit_code,
        duration_bucket=None if process is None else process.duration_bucket,
        stdout_byte_count=0 if process is None else len(process.stdout),
        stderr_byte_count=0 if process is None else len(process.stderr),
        stdout_truncated=False if process is None else process.stdout_truncated,
        stderr_truncated=False if process is None else process.stderr_truncated,
        guard_status=guard_status,
        failure_code=failure_code,
    )
    audit = {
        "attempt_id": attempt_id,
        "state": (
            ("closed_cancelled" if cancelled else "closed_failed")
            if terminal_result.committed
            else "awaiting_terminal"
        ),
        "audit_incomplete": not terminal_result.committed,
    }
    if terminal_result.status != "pass" or not terminal_result.committed:
        return _result(
            "error",
            task_id=task_id,
            request_id=request_id,
            plan_hash=plan_hash,
            lifecycle="withheld",
            findings=list(terminal_result.findings),
            audit=audit,
            process={} if process is None else process.to_dict(),
            runtime=runtime,
            next_action="Recover the incomplete terminal execution audit.",
        )
    return _result(
        status,
        task_id=task_id,
        request_id=request_id,
        plan_hash=plan_hash,
        lifecycle="closed",
        findings=findings,
        audit=audit,
        process={} if process is None else process.to_dict(),
        runtime=runtime,
        next_action="Inspect the fixed failure code before retrying.",
    )


def execute_fixed_pi_print(
    root: Path,
    *,
    task_id: str,
    request_id: str,
    prompt: str,
    commit: bool,
    expected_plan_hash: str | None = None,
    timeout_seconds: int = _DEFAULT_TIMEOUT_SECONDS,
    services: dict[str, object] | None = None,
    registry_check: Callable[[Path], bool] | None = None,
) -> PiPrintExecutionResult:
    """Execute the single fixed Pi dry-run print operation behind every release gate."""
    if not commit:
        return _result(
            "blocked",
            task_id=task_id,
            request_id=request_id,
            findings=[
                _safe_finding(
                    "execution.commit-required",
                    "Fixed execution requires an explicit --commit action.",
                    "blocked",
                )
            ],
            next_action="Repeat with --commit after reviewing the fixed operation.",
        )
    if (
        _TOKEN_RE.fullmatch(task_id) is None
        or _TOKEN_RE.fullmatch(request_id) is None
    ):
        return _result(
            "validation_failed",
            task_id=task_id,
            request_id=request_id,
            findings=[
                _safe_finding(
                    "execution.identity-invalid",
                    "Execution task and request ids must use bounded ASCII tokens.",
                    "validation_failed",
                )
            ],
            next_action="Use valid task and request identities.",
        )
    if (
        not isinstance(timeout_seconds, int)
        or timeout_seconds < _MIN_TIMEOUT_SECONDS
        or timeout_seconds > _MAX_TIMEOUT_SECONDS
    ):
        return _result(
            "validation_failed",
            task_id=task_id,
            request_id=request_id,
            findings=[
                _safe_finding(
                    "pi-print-timeout-invalid",
                    "The fixed Pi print timeout must be within 5..120 seconds.",
                    "validation_failed",
                )
            ],
            next_action="Use a timeout between 5 and 120 seconds.",
        )
    prompt_finding = _validate_prompt(prompt)
    if prompt_finding is not None:
        return _result(
            "blocked",
            task_id=task_id,
            request_id=request_id,
            findings=[prompt_finding],
            next_action="Fix the bounded prompt before retrying.",
        )
    scan = _services(services)["scan_text"](root, prompt)
    if scan.status != "pass":
        return _result(
            "blocked",
            task_id=task_id,
            request_id=request_id,
            findings=[
                _safe_finding(
                    "pi-print-prompt-secret-scan",
                    "The fixed Pi print prompt failed the secret scan; matched values are withheld.",
                    "blocked",
                )
            ],
            next_action="Remove secret-like content from the prompt before retrying.",
        )
    lease = acquire_execution_lease(root)
    if lease.status != "pass":
        return _result(
            lease.status,
            task_id=task_id,
            request_id=request_id,
            findings=list(lease.findings),
            next_action=lease.next_action or "Retry after the execution lease is available.",
        )
    result: PiPrintExecutionResult | None = None
    core_failure: Finding | None = None
    validation_failure: Finding | None = None
    release_failure: Finding | None = None
    lease_valid = False
    released = CheckResult(status="error")
    try:
        result = _execute_fixed_pi_print_core(
            root,
            task_id=task_id,
            request_id=request_id,
            prompt=prompt,
            expected_plan_hash=expected_plan_hash,
            timeout_seconds=timeout_seconds,
            services=services,
            registry_check=registry_check,
            lease_capability=_held_lease_capability(lease),
        )
    except Exception:
        core_failure = _safe_finding(
            "execution-core-failed",
            "Fixed execution failed unexpectedly before completion.",
            "error",
        )
    finally:
        try:
            try:
                lease_valid = lease.validate()
            except BaseException:
                validation_failure = _safe_finding(
                    "execution-lease-validation-failed",
                    "Final execution lease validation failed unexpectedly.",
                    "error",
                )
        finally:
            try:
                released = lease.release()
            except BaseException:
                release_failure = _safe_finding(
                    "execution-lease-release-failed",
                    "The execution lease cleanup failed.",
                    "error",
                )
    if core_failure is not None:
        findings = [core_failure]
        if validation_failure is not None:
            findings.append(validation_failure)
        if release_failure is not None or released.status != "pass":
            findings.append(
                _safe_finding(
                    "execution-lease-release-failed",
                    "The execution lease cleanup failed.",
                    "error",
                )
            )
        return _result(
            "error",
            task_id=task_id,
            request_id=request_id,
            findings=findings,
            lifecycle="withheld",
            next_action="Inspect execution audit and lease state before retrying.",
        )
    assert result is not None
    if (
        validation_failure is not None
        or not lease_valid
        or release_failure is not None
        or released.status != "pass"
    ):
        findings = []
        if validation_failure is not None:
            findings.append(validation_failure)
        elif not lease_valid:
            findings.append(
                _safe_finding(
                    "execution-lease-identity-drift",
                    "The execution lease failed final identity validation.",
                    "error",
                )
            )
        if release_failure is not None:
            findings.append(release_failure)
        elif released.status != "pass":
            findings.append(
                _safe_finding(
                    "execution-lease-release-failed",
                    "The execution lease cleanup failed.",
                    "error",
                )
            )
        return _result(
            "error",
            task_id=task_id,
            request_id=request_id,
            plan_hash=result.plan_hash,
            findings=findings,
            lifecycle="withheld",
            audit=dict(result.audit),
            process=dict(result.process),
            runtime=dict(result.runtime),
            summary=None,
            next_action="Repair machine-local execution lease cleanup before retrying.",
        )
    return result


def _execute_fixed_pi_print_core(
    root: Path,
    *,
    task_id: str,
    request_id: str,
    prompt: str,
    expected_plan_hash: str | None,
    timeout_seconds: int,
    services: dict[str, object] | None,
    registry_check: Callable[[Path], bool] | None,
    lease_capability: _LeaseCapability | None,
) -> PiPrintExecutionResult:
    if not _validate_lease_capability(lease_capability, root):
        return _result(
            "error",
            task_id=task_id,
            request_id=request_id,
            findings=[
                _safe_finding(
                    "execution-lease-capability-invalid",
                    "Fixed execution requires the active execution lease.",
                    "error",
                )
            ],
            next_action="Acquire the fixed machine-local execution lease.",
        )
    active = _services(services)
    started: ExecutionAuditWriteResult | None = None
    plan_hash: str | None = None
    runtime_projection: dict[str, Any] = {}

    def track_started(*args: object, **kwargs: object) -> ExecutionAuditWriteResult:
        nonlocal started, plan_hash
        plan_hash = kwargs.get("plan_hash") if isinstance(kwargs.get("plan_hash"), str) else None
        kwargs["_schema_version"] = "execution-audit/v2"
        value = active["record_started"](*args, **kwargs)
        started = value
        return value

    tracked = dict(active)
    tracked["record_started"] = track_started
    outcome: PiPrintExecutionResult | None = None
    try:
        outcome = _execute_fixed_pi_print_lifecycle(
            root,
            task_id=task_id,
            request_id=request_id,
            prompt=prompt,
            expected_plan_hash=expected_plan_hash,
            timeout_seconds=timeout_seconds,
            services=tracked,
            registry_check=registry_check,
        )
    except Exception:
        finding = _safe_finding(
            "execution.internal-failure",
            "Fixed execution failed unexpectedly and released no result.",
            "error",
        )
        if started is None or not started.committed or started.attempt_id is None:
            outcome = _result(
                "error",
                task_id=task_id,
                request_id=request_id,
                plan_hash=plan_hash,
                findings=[finding],
                audit={"state": "not_started", "audit_incomplete": True},
                runtime=runtime_projection,
                next_action="Repair the internal failure before retrying.",
            )
        else:
            terminal_committed = False
            try:
                terminal = active["record_terminal"](
                    root,
                    attempt_id=started.attempt_id,
                    event_type="execution_failed",
                    phase="audit",
                    exit_code=None,
                    duration_bucket=None,
                    stdout_byte_count=0,
                    stderr_byte_count=0,
                    stdout_truncated=False,
                    stderr_truncated=False,
                    guard_status="not_run",
                    failure_code="execution.internal-failure",
                )
                terminal_committed = bool(
                    terminal.status == "pass" and terminal.committed
                )
            except Exception:
                terminal_committed = False
            outcome = _result(
                "error",
                task_id=task_id,
                request_id=request_id,
                plan_hash=plan_hash,
                findings=[finding],
                lifecycle="closed" if terminal_committed else "withheld",
                audit={
                    "attempt_id": started.attempt_id,
                    "state": "closed_failed" if terminal_committed else "awaiting_terminal",
                    "audit_incomplete": not terminal_committed,
                },
                runtime=runtime_projection,
                next_action=(
                    "Inspect the closed internal failure before retrying."
                    if terminal_committed
                    else "Recover the incomplete terminal execution audit."
                ),
            )
    assert outcome is not None
    return outcome


def _execute_fixed_pi_print_lifecycle(
    root: Path,
    *,
    task_id: str,
    request_id: str,
    prompt: str,
    expected_plan_hash: str | None,
    timeout_seconds: int,
    services: dict[str, Callable[..., Any]],
    registry_check: Callable[[Path], bool] | None,
) -> PiPrintExecutionResult:
    active = services
    check_registry = registry_check or _default_registry_check
    if not check_registry(root):
        return _result(
            "blocked",
            task_id=task_id,
            request_id=request_id,
            findings=[
                _safe_finding(
                    "execution.registry-drift",
                    "The fixed adapter registry contract has drifted.",
                    "blocked",
                )
            ],
            next_action="Restore the frozen pi-cli cli_agent_print registry contract.",
        )
    readiness: PiRuntimeStatus = active["discover"](root)
    runtime_projection = _runtime_projection(readiness)
    if readiness.status != "ready":
        return _result(
            "blocked",
            task_id=task_id,
            request_id=request_id,
            findings=[
                _safe_finding(
                    "pi-print-readiness-not-ready",
                    "The local Pi runtime readiness probe did not pass; execution stays fail-closed.",
                    "blocked",
                ),
                *list(readiness.findings),
            ],
            runtime=runtime_projection,
            next_action=readiness.next_action or "Repair the local Pi runtime before retrying.",
        )
    built = active["build_environment"](root, readiness)
    if built is None:
        return _result(
            "needs_input",
            task_id=task_id,
            request_id=request_id,
            findings=[
                _safe_finding(
                    "pi-print-api-key-env-missing",
                    "The referenced provider API key environment variable is not set; its value is never read or echoed.",
                    "needs_input",
                )
            ],
            runtime=runtime_projection,
            next_action="Set the referenced provider API key environment variable, then retry.",
        )
    environment, path_identity = built
    executable = active["resolve_executable"](root)
    if executable is None:
        return _result(
            "blocked",
            task_id=task_id,
            request_id=request_id,
            findings=[
                _safe_finding(
                    "pi-print-executable-not-found",
                    "The fixed pi executable basename could not be resolved from the operator PATH.",
                    "blocked",
                )
            ],
            runtime=runtime_projection,
            next_action="Install the Pi CLI (see docs/105) before retrying.",
        )
    executable_identity = _canonical_digest(
        os.path.normcase(str(executable))
        if os.name == "nt"
        else str(executable)
    )
    argv = [
        str(executable),
        "--print",
        "--no-session",
        "--no-tools",
        prompt,
    ]
    prompt_digest = "sha256:" + hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    environment_identity = _canonical_digest(
        {
            key: (_WITHHELD if key == readiness.api_key_env else value)
            for key, value in environment.items()
        }
    )
    plan_hash = _canonical_digest(
        {
            "schema_version": SCHEMA_VERSION,
            "actor": "local-operator",
            "task_id": task_id,
            "request_id": request_id,
            "adapter_id": _ADAPTER_ID,
            "capability": _CAPABILITY,
            "operation": _OPERATION,
            "argv_shape": _ARGV_SHAPE,
            "prompt_sha256": prompt_digest,
            "runtime_identity": _readiness_identity(readiness),
            "executable_identity": executable_identity,
            "environment_identity": environment_identity,
            "path_identity": path_identity,
            "timeout_seconds": timeout_seconds,
        }
    )
    if expected_plan_hash is not None and (
        _PLAN_HASH_RE.fullmatch(expected_plan_hash) is None
        or expected_plan_hash != plan_hash
    ):
        return _result(
            "blocked",
            task_id=task_id,
            request_id=request_id,
            plan_hash=plan_hash,
            findings=[
                _safe_finding(
                    "execution.plan-hash-mismatch",
                    "The reviewed execution plan hash does not match current preflight.",
                    "blocked",
                )
            ],
            runtime=runtime_projection,
            next_action="Review the current plan hash before retrying.",
        )
    started: ExecutionAuditWriteResult = active["record_started"](
        root,
        task_id=task_id,
        request_id=request_id,
        plan_hash=plan_hash,
        adapter_id=_ADAPTER_ID,
        capability=_CAPABILITY,
        operation=_OPERATION,
    )
    if started.status != "pass" or not started.committed or started.attempt_id is None:
        return _result(
            "error",
            task_id=task_id,
            request_id=request_id,
            plan_hash=plan_hash,
            findings=list(started.findings),
            audit={"state": "not_started", "audit_incomplete": True},
            runtime=runtime_projection,
            next_action="Repair execution audit writing before any spawn.",
        )
    attempt_id = started.attempt_id
    first_identity = _readiness_identity(readiness)
    recheck: PiRuntimeStatus = active["discover"](root)
    if recheck.status != "ready" or _readiness_identity(recheck) != first_identity:
        return _terminal_failure(
            root=root,
            task_id=task_id,
            request_id=request_id,
            plan_hash=plan_hash,
            attempt_id=attempt_id,
            status="blocked",
            phase="pre_spawn_recheck",
            failure_code="pi-print.readiness-drift",
            findings=[
                _safe_finding(
                    "pi-print.readiness-drift",
                    "The local Pi runtime readiness changed after the started audit.",
                    "blocked",
                )
            ],
            terminal=active["record_terminal"],
            runtime=runtime_projection,
        )
    process: FixedProcessResult = active["run_process"](
        argv,
        root,
        environment,
        timeout_seconds=timeout_seconds,
    )
    post_recheck: PiRuntimeStatus = active["discover"](root)
    if (
        post_recheck.status != "ready"
        or _readiness_identity(post_recheck) != first_identity
    ):
        return _terminal_failure(
            root=root,
            task_id=task_id,
            request_id=request_id,
            plan_hash=plan_hash,
            attempt_id=attempt_id,
            status="blocked",
            phase="post_run_guard",
            failure_code="pi-print.readiness-drift",
            findings=[
                _safe_finding(
                    "pi-print.readiness-drift",
                    "The local Pi runtime readiness changed during the fixed run.",
                    "blocked",
                )
            ],
            terminal=active["record_terminal"],
            process=process,
            runtime=runtime_projection,
        )
    if process.status != "pass":
        finding = process.findings[0] if process.findings else _safe_finding(
            "execution.process-failed",
            "The fixed process failed.",
            process.status,
        )
        cancelled = finding.rule_id == "execution.process-cancelled"
        return _terminal_failure(
            root=root,
            task_id=task_id,
            request_id=request_id,
            plan_hash=plan_hash,
            attempt_id=attempt_id,
            status=process.status,
            phase=(
                "spawn"
                if finding.rule_id
                in {
                    "execution.process-start-failed",
                    "execution.process-platform-unavailable",
                }
                else "child"
            ),
            failure_code=finding.rule_id,
            findings=list(process.findings),
            terminal=active["record_terminal"],
            process=process,
            guard_status="pass",
            cancelled=cancelled,
            runtime=runtime_projection,
        )
    output_failure = _validate_output(root, process, active["scan_text"])
    if output_failure is not None:
        rule_id, phase, status = output_failure
        return _terminal_failure(
            root=root,
            task_id=task_id,
            request_id=request_id,
            plan_hash=plan_hash,
            attempt_id=attempt_id,
            status=status,
            phase=phase,
            failure_code=rule_id,
            findings=[
                _safe_finding(
                    rule_id,
                    _OUTPUT_MESSAGES[rule_id],
                    status,
                )
            ],
            terminal=active["record_terminal"],
            process=process,
            guard_status="pass",
            runtime=runtime_projection,
        )
    stdout_digest = "sha256:" + hashlib.sha256(process.stdout).hexdigest()
    accounting = process.accounting
    terminal_kwargs: dict[str, Any] = {}
    if accounting is not None:
        terminal_kwargs = {
            "job_accounting_passed": accounting.job_accounting_passed,
            "job_total_processes": accounting.job_total_processes,
            "job_active_processes": accounting.job_active_processes,
            "job_terminated_processes": accounting.job_terminated_processes,
            "direct_child_reaped": accounting.direct_child_reaped,
            "containment_closed": accounting.containment_closed,
        }
    terminal: ExecutionAuditWriteResult = active["record_terminal"](
        root,
        attempt_id=attempt_id,
        event_type="execution_succeeded",
        exit_code=0,
        duration_bucket=process.duration_bucket,
        output_digest=stdout_digest,
        stdout_byte_count=len(process.stdout),
        stderr_byte_count=len(process.stderr),
        stdout_truncated=False,
        stderr_truncated=False,
        guard_status="pass",
        **terminal_kwargs,
    )
    audit = {
        "attempt_id": attempt_id,
        "state": "closed_succeeded" if terminal.committed else "awaiting_terminal",
        "audit_incomplete": not terminal.committed,
    }
    if terminal.status != "pass" or not terminal.committed:
        return _result(
            "error",
            task_id=task_id,
            request_id=request_id,
            plan_hash=plan_hash,
            findings=list(terminal.findings),
            lifecycle="withheld",
            audit=audit,
            process=process.to_dict(),
            runtime=runtime_projection,
            next_action="Recover the incomplete terminal execution audit.",
        )
    summary = {
        "provider": readiness.default_provider,
        "model": readiness.default_model,
        "stdout_digest": stdout_digest,
        "stdout_byte_count": len(process.stdout),
        "stderr_byte_count": len(process.stderr),
        "stdout_truncated": process.stdout_truncated,
        "stderr_truncated": process.stderr_truncated,
        "duration_bucket": process.duration_bucket,
    }
    return _result(
        "ready",
        task_id=task_id,
        request_id=request_id,
        plan_hash=plan_hash,
        lifecycle="closed",
        audit=audit,
        process=process.to_dict(),
        runtime=runtime_projection,
        summary=summary,
        next_action="Inspect the model answer in the operator terminal; only its digest is released here.",
    )


_OUTPUT_MESSAGES = {
    "execution.child_nonzero": "The fixed Pi print child exited with a non-zero status.",
    "pi-print-output-empty": "The fixed Pi print produced no stdout content.",
    "pi-print-output-invalid-utf8": "The fixed Pi print stdout is not valid UTF-8.",
    "pi-print-output-nul": "The fixed Pi print stdout contains NUL bytes.",
    "pi-print-output-too-many-lines": "The fixed Pi print stdout exceeds the bounded line count.",
    "pi-print-output-secret-scan": "The fixed Pi print stdout failed the secret scan; matched values are withheld.",
}


def _validate_output(
    root: Path,
    process: FixedProcessResult,
    scan_text: Callable[[Path, str], CheckResult],
) -> tuple[str, str, str] | None:
    """Bounded output protocol validation; returns (rule_id, phase, status)."""
    if process.exit_code != 0:
        return "execution.child_nonzero", "child", "error"
    if not process.stdout.strip():
        return "pi-print-output-empty", "output_validation", "error"
    try:
        text = process.stdout.decode("utf-8")
    except UnicodeDecodeError:
        return "pi-print-output-invalid-utf8", "output_validation", "error"
    if "\x00" in text:
        return "pi-print-output-nul", "output_validation", "error"
    if text.count("\n") + 1 > _MAX_OUTPUT_LINES:
        return "pi-print-output-too-many-lines", "output_validation", "error"
    scan = scan_text(root, text)
    if scan.status != "pass":
        return "pi-print-output-secret-scan", "output_validation", "blocked"
    return None
