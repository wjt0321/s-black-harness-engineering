"""Limited orchestration for the single fixed Git status execution."""

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
from .execution_trust import VerifiedTrustResult, verify_execution_trust
from .fixed_process_runner import FixedProcessResult, run_fixed_git_status_process
from .git_repository_guard import (
    RepositoryGuard,
    RepositoryGuardResult,
    build_repository_guard,
    compare_repository_guards,
)
from .git_status_porcelain import GitStatusSummary, parse_git_status_output
from .result import CheckResult, Finding, EXIT_PASS

SCHEMA_VERSION = "control-plane/fixed-git-status-execution/v1"
_ADAPTER_ID = "shell-local"
_CAPABILITY = "git_status"
_OPERATION = "git_status"
_TOKEN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,95}$")
_PLAN_HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_CONFIG_OVERRIDES = (
    ("core.fsmonitor", "false"),
    ("core.untrackedCache", "false"),
    ("maintenance.auto", "false"),
    ("color.status", "false"),
    ("status.showUntrackedFiles", "all"),
    ("core.quotePath", "true"),
)


@dataclass
class GitStatusExecutionResult(CheckResult):
    plan_hash: str | None = None
    summary: GitStatusSummary | None = None
    lifecycle: str = "withheld"
    audit: dict[str, Any] = field(default_factory=dict)
    no_write_evidence: dict[str, Any] = field(
        default_factory=lambda: {
            "no_write_contract": True,
            "guard_evidence_passed": False,
            "filesystem_write_proof": False,
        }
    )
    process: dict[str, Any] = field(default_factory=dict)
    trust: dict[str, Any] = field(default_factory=dict)
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
                "trust_binding": "machine-local/execution-trust-v1",
                "audit_writer": "agent_runtime.execution_audit_writer",
            },
            "lifecycle": self.lifecycle,
            "scope": {
                "task_id": self.task_id,
                "request_id": self.request_id,
            },
            "plan": {"plan_hash": self.plan_hash},
            "process": dict(self.process),
            "trust": dict(self.trust),
            "summary": None if self.summary is None else self.summary.to_dict(),
            "audit": dict(self.audit),
            "no_write_evidence": dict(self.no_write_evidence),
            "findings": [finding.to_dict() for finding in self.findings],
            "guarantees": {
                "fixed_argv": True,
                "shell": False,
                "retry": False,
                "background": False,
                "network_operation": False,
                "raw_output_withheld": True,
                "paths_withheld": True,
                "branch_withheld": True,
                "filesystem_write_proof": False,
            },
            "next_action": self.next_action,
        }

    def render_human(self, no_color: bool = False) -> str:
        lines = [
            "FIXED GIT STATUS EXECUTION",
            f"status={self.status}",
            f"lifecycle={self.lifecycle}",
        ]
        if self.plan_hash is not None:
            lines.append(f"plan_hash={self.plan_hash}")
        if self.summary is not None:
            lines.append(
                "summary: "
                f"dirty={self.summary.dirty} "
                f"entries={self.summary.entry_count} "
                f"staged={self.summary.staged} "
                f"unstaged={self.summary.unstaged} "
                f"untracked={self.summary.untracked} "
                f"conflicted={self.summary.conflicted}"
            )
        for finding in self.findings:
            lines.append(f"- {finding.rule_id}: {finding.message}")
        if self.next_action:
            lines.append(f"Next: {self.next_action}")
        return "\n".join(lines)


def _fixed_environment(sanitized_path: str) -> dict[str, str]:
    environment = {"PATH": sanitized_path}
    for name in ("SYSTEMROOT", "WINDIR"):
        value = os.environ.get(name)
        if value:
            environment[name] = value
    environment.update(
        {
            "GIT_OPTIONAL_LOCKS": "0",
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_COUNT": str(len(_CONFIG_OVERRIDES)),
        }
    )
    for index, (key, value) in enumerate(_CONFIG_OVERRIDES):
        environment[f"GIT_CONFIG_KEY_{index}"] = key
        environment[f"GIT_CONFIG_VALUE_{index}"] = value
    return environment


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
        and adapter.kind == "shell"
        and adapter.risk_level == "local"
        and _CAPABILITY in adapter.capabilities
        and adapter.requires_approval is False
    )


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
    trust: dict[str, Any] | None = None,
    summary: GitStatusSummary | None = None,
    guard_passed: bool = False,
    next_action: str,
) -> GitStatusExecutionResult:
    return GitStatusExecutionResult(
        status=status,
        findings=findings or [],
        next_action=next_action,
        plan_hash=plan_hash,
        lifecycle=lifecycle,
        audit=audit or {},
        process=process or {},
        trust=trust or {},
        summary=summary,
        task_id=task_id,
        request_id=request_id,
        no_write_evidence={
            "no_write_contract": True,
            "guard_evidence_passed": guard_passed,
            "filesystem_write_proof": False,
        },
    )


def _safe_finding(rule_id: str, message: str, status: str) -> Finding:
    return Finding(
        rule_id,
        "block" if status == "blocked" else "error",
        status,
        message,
    )


def _services(
    overrides: dict[str, object] | None,
) -> dict[str, Callable[..., Any]]:
    values: dict[str, Callable[..., Any]] = {
        "verify_trust": verify_execution_trust,
        "build_guard": build_repository_guard,
        "record_started": record_execution_attempt_started,
        "run_process": run_fixed_git_status_process,
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


def _close_trust(result: VerifiedTrustResult | None) -> None:
    if result is not None and result.identity is not None:
        result.identity.close()


def _close_guard(result: RepositoryGuardResult | None) -> None:
    if result is not None and result.guard is not None:
        result.guard.close()


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
    trust: dict[str, Any] | None = None,
) -> GitStatusExecutionResult:
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
            trust=trust,
            guard_passed=guard_status == "pass",
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
        trust=trust,
        guard_passed=guard_status == "pass",
        next_action="Inspect the fixed failure code before retrying.",
    )


def execute_fixed_git_status(
    root: Path,
    *,
    task_id: str,
    request_id: str,
    commit: bool,
    expected_plan_hash: str | None = None,
    timeout_seconds: float = 10,
    services: dict[str, object] | None = None,
    registry_check: Callable[[Path], bool] | None = None,
) -> GitStatusExecutionResult:
    """Execute the single fixed Git status operation behind every release gate."""
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
    active = _services(services)
    first_guard: RepositoryGuardResult = active["build_guard"](root)
    if first_guard.status != "pass" or first_guard.guard is None:
        return _result(
            first_guard.status,
            task_id=task_id,
            request_id=request_id,
            findings=list(first_guard.findings),
            next_action=first_guard.next_action or "Repair repository preflight.",
        )
    root = root.resolve(strict=True)
    check_registry = registry_check or _default_registry_check
    if not check_registry(root):
        _close_guard(first_guard)
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
            next_action="Restore the frozen shell-local git_status registry contract.",
        )
    first_trust: VerifiedTrustResult | None = active["verify_trust"](root)
    if first_trust.status != "pass" or first_trust.identity is None:
        _close_guard(first_guard)
        return _result(
            first_trust.status,
            task_id=task_id,
            request_id=request_id,
            findings=list(first_trust.findings),
            trust={
                "binding_id": first_trust.binding_id,
                "executable_identity": first_trust.executable_identity,
                "path_identity": first_trust.path_identity,
            },
            next_action=first_trust.next_action or "Create a valid execution trust binding.",
        )
    environment = _fixed_environment(first_trust.identity.sanitized_path)
    plan_hash = _canonical_digest(
        {
            "schema_version": SCHEMA_VERSION,
            "actor": "local-operator",
            "task_id": task_id,
            "request_id": request_id,
            "adapter_id": _ADAPTER_ID,
            "capability": _CAPABILITY,
            "operation": _OPERATION,
            "argv": ["git", "status", "--short", "--branch"],
            "root_identity": _canonical_digest(str(root)),
            "binding_id": first_trust.binding_id,
            "executable_identity": first_trust.executable_identity,
            "path_identity": first_trust.path_identity,
            "guard_identity": first_guard.guard.identity,
            "environment_identity": _canonical_digest(environment),
            "timeout_seconds": timeout_seconds,
        }
    )
    trust_projection = {
        "binding_id": first_trust.binding_id,
        "executable_identity": first_trust.executable_identity,
        "path_identity": first_trust.path_identity,
    }
    if expected_plan_hash is not None and (
        _PLAN_HASH_RE.fullmatch(expected_plan_hash) is None
        or expected_plan_hash != plan_hash
    ):
        _close_trust(first_trust)
        _close_guard(first_guard)
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
            trust=trust_projection,
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
        _close_trust(first_trust)
        _close_guard(first_guard)
        return _result(
            "error",
            task_id=task_id,
            request_id=request_id,
            plan_hash=plan_hash,
            findings=list(started.findings),
            audit={"state": "not_started", "audit_incomplete": True},
            trust=trust_projection,
            next_action="Repair execution audit writing before any spawn.",
        )
    attempt_id = started.attempt_id
    second_trust: VerifiedTrustResult | None = active["verify_trust"](root)
    if (
        second_trust.status != "pass"
        or second_trust.identity is None
        or second_trust.binding_id != first_trust.binding_id
        or second_trust.executable_identity != first_trust.executable_identity
        or second_trust.path_identity != first_trust.path_identity
    ):
        _close_trust(first_trust)
        _close_trust(second_trust)
        _close_guard(first_guard)
        return _terminal_failure(
            root=root,
            task_id=task_id,
            request_id=request_id,
            plan_hash=plan_hash,
            attempt_id=attempt_id,
            status="blocked",
            phase="pre_spawn_recheck",
            failure_code="execution.trust-drift",
            findings=[
                _safe_finding(
                    "execution.trust-drift",
                    "Executable trust changed after the started audit.",
                    "blocked",
                )
            ],
            terminal=active["record_terminal"],
            trust=trust_projection,
        )
    second_guard: RepositoryGuardResult = active["build_guard"](root)
    guard_check = (
        compare_repository_guards(first_guard.guard, second_guard.guard)
        if second_guard.status == "pass" and second_guard.guard is not None
        else CheckResult(
            status=second_guard.status,
            findings=list(second_guard.findings),
        )
    )
    if guard_check.status != "pass":
        _close_trust(first_trust)
        _close_trust(second_trust)
        _close_guard(second_guard)
        _close_guard(first_guard)
        return _terminal_failure(
            root=root,
            task_id=task_id,
            request_id=request_id,
            plan_hash=plan_hash,
            attempt_id=attempt_id,
            status="blocked",
            phase="pre_spawn_recheck",
            failure_code="execution.repository-guard-drift",
            findings=list(guard_check.findings),
            terminal=active["record_terminal"],
            trust=trust_projection,
        )
    _close_guard(second_guard)
    _close_trust(first_trust)
    process: FixedProcessResult = active["run_process"](
        second_trust.identity,
        root,
        environment,
        timeout_seconds=timeout_seconds,
    )
    _close_trust(second_trust)
    post_guard: RepositoryGuardResult = active["build_guard"](root)
    post_check = (
        compare_repository_guards(first_guard.guard, post_guard.guard)
        if post_guard.status == "pass" and post_guard.guard is not None
        else CheckResult(
            status=post_guard.status,
            findings=list(post_guard.findings),
        )
    )
    _close_guard(post_guard)
    _close_guard(first_guard)
    if post_check.status != "pass":
        return _terminal_failure(
            root=root,
            task_id=task_id,
            request_id=request_id,
            plan_hash=plan_hash,
            attempt_id=attempt_id,
            status="blocked",
            phase="post_run_guard",
            failure_code="execution.repository-guard-drift",
            findings=list(post_check.findings),
            terminal=active["record_terminal"],
            process=process,
            guard_status="failed",
            trust=trust_projection,
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
                    "execution.process-image-mismatch",
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
            trust=trust_projection,
        )
    parsed = parse_git_status_output(
        process.stdout,
        process.stderr,
        exit_code=process.exit_code if process.exit_code is not None else -1,
    )
    if parsed.status != "pass" or parsed.summary is None:
        failure = parsed.findings[0]
        return _terminal_failure(
            root=root,
            task_id=task_id,
            request_id=request_id,
            plan_hash=plan_hash,
            attempt_id=attempt_id,
            status=parsed.status,
            phase=(
                "child"
                if failure.rule_id == "execution.child_nonzero"
                else "output_validation"
            ),
            failure_code=failure.rule_id,
            findings=list(parsed.findings),
            terminal=active["record_terminal"],
            process=process,
            guard_status="pass",
            trust=trust_projection,
        )
    terminal: ExecutionAuditWriteResult = active["record_terminal"](
        root,
        attempt_id=attempt_id,
        event_type="execution_succeeded",
        exit_code=0,
        duration_bucket=process.duration_bucket,
        output_digest=parsed.summary.stdout_digest,
        stdout_byte_count=parsed.summary.stdout_byte_count,
        stderr_byte_count=parsed.summary.stderr_byte_count,
        stdout_truncated=False,
        stderr_truncated=False,
        guard_status="pass",
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
            trust=trust_projection,
            next_action="Recover the incomplete terminal execution audit.",
        )
    return _result(
        "ready",
        task_id=task_id,
        request_id=request_id,
        plan_hash=plan_hash,
        lifecycle="closed",
        audit=audit,
        process=process.to_dict(),
        trust=trust_projection,
        summary=parsed.summary,
        guard_passed=True,
        next_action="Use the safe Git status summary.",
    )
