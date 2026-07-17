from __future__ import annotations

import json
from pathlib import Path

from agent_runtime.execution_audit_writer import ExecutionAuditWriteResult
from agent_runtime.execution_trust import ExecutableIdentity, VerifiedTrustResult
from agent_runtime.fixed_process_runner import FixedProcessResult
from agent_runtime.git_repository_guard import RepositoryGuard, RepositoryGuardResult
from agent_runtime.orchestration_git_status_execution import (
    execute_fixed_git_status,
)
from agent_runtime.result import Finding


def _identity(tmp_path: Path) -> ExecutableIdentity:
    path = tmp_path / "git.exe"
    path.write_bytes(b"git")
    trusted_path = "C" + ":" + "\\trusted"
    return ExecutableIdentity(
        canonical_path=path,
        approved_root=tmp_path,
        sha256="a" * 64,
        file_identity="volume:file",
        publisher_thumbprint="B" * 40,
        owner_policy="windows-system-install",
        path_identity="sha256:" + "1" * 64,
        sanitized_path=trusted_path,
    )


def _guard(identity: str = "2") -> RepositoryGuardResult:
    value = "sha256:" + identity * 64
    return RepositoryGuardResult(
        status="pass",
        guard=RepositoryGuard(identity=value, manifest=(("x", "file", 1, 1, 1, 1, "1:x"),)),
    )


def _started() -> ExecutionAuditWriteResult:
    return ExecutionAuditWriteResult(
        status="pass",
        event_id="evt-20260717-001",
        attempt_id="attempt-20260717-001",
        task_id="task-20260703-001",
        request_id="req-stage49-001",
        event_type="execution_attempt_started",
        phase="pre_spawn_committed",
        committed=True,
        child_created=False,
    )


def _terminal() -> ExecutionAuditWriteResult:
    return ExecutionAuditWriteResult(
        status="pass",
        event_id="evt-20260717-002",
        attempt_id="attempt-20260717-001",
        event_type="execution_succeeded",
        phase="post_run_validated",
        committed=True,
    )


def _services(tmp_path: Path, calls: list[str]) -> dict[str, object]:
    identity = _identity(tmp_path)

    def trust(root: Path) -> VerifiedTrustResult:
        calls.append("trust")
        return VerifiedTrustResult(
            status="pass",
            identity=identity,
            binding_id="sha256:" + "3" * 64,
            executable_identity="sha256:" + "4" * 64,
            path_identity=identity.path_identity,
        )

    def guard(root: Path) -> RepositoryGuardResult:
        calls.append("guard")
        return _guard()

    def started(*args: object, **kwargs: object) -> ExecutionAuditWriteResult:
        calls.append("started")
        return _started()

    def run(*args: object, **kwargs: object) -> FixedProcessResult:
        calls.append("run")
        return FixedProcessResult(
            status="pass",
            exit_code=0,
            stdout=b"## main\n?? secret-file.txt\n",
            stderr=b"",
            duration_bucket="lt-1s",
        )

    def terminal(*args: object, **kwargs: object) -> ExecutionAuditWriteResult:
        calls.append("terminal")
        return _terminal()

    return {
        "verify_trust": trust,
        "build_guard": guard,
        "record_started": started,
        "run_process": run,
        "record_terminal": terminal,
    }


def test_commit_is_required_before_any_write_or_spawn(tmp_path: Path) -> None:
    calls: list[str] = []
    result = execute_fixed_git_status(
        tmp_path,
        task_id="task-20260703-001",
        request_id="req-stage49-001",
        commit=False,
        services=_services(tmp_path, calls),
    )

    assert result.status == "blocked"
    assert result.findings[0].rule_id == "execution.commit-required"
    assert calls == []


def test_ready_path_has_fixed_order_and_safe_summary(tmp_path: Path) -> None:
    calls: list[str] = []
    result = execute_fixed_git_status(
        tmp_path,
        task_id="task-20260703-001",
        request_id="req-stage49-001",
        commit=True,
        services=_services(tmp_path, calls),
        registry_check=lambda root: True,
    )

    assert result.status == "ready"
    assert result.exit_code() == 0
    assert calls == [
        "guard",
        "trust",
        "started",
        "trust",
        "guard",
        "run",
        "guard",
        "terminal",
    ]
    payload = result.to_dict()
    assert payload["schema_version"] == "control-plane/fixed-git-status-execution/v1"
    assert payload["summary"]["untracked"] == 1
    assert payload["audit"]["state"] == "closed_succeeded"
    assert payload["no_write_evidence"] == {
        "no_write_contract": True,
        "guard_evidence_passed": True,
        "filesystem_write_proof": False,
    }
    rendered = json.dumps(payload)
    assert "secret-file" not in rendered
    assert str(tmp_path) not in rendered
    assert ("C" + ":" + "\\\\trusted") not in rendered
    assert "main" not in payload["summary"]


def test_plan_hash_is_deterministic_and_expected_hash_blocks_audit(
    tmp_path: Path,
) -> None:
    first_calls: list[str] = []
    first = execute_fixed_git_status(
        tmp_path,
        task_id="task-20260703-001",
        request_id="req-stage49-001",
        commit=True,
        services=_services(tmp_path, first_calls),
        registry_check=lambda root: True,
    )
    second_calls: list[str] = []
    second = execute_fixed_git_status(
        tmp_path,
        task_id="task-20260703-001",
        request_id="req-stage49-001",
        commit=True,
        services=_services(tmp_path, second_calls),
        registry_check=lambda root: True,
    )
    assert first.plan_hash == second.plan_hash

    blocked_calls: list[str] = []
    blocked = execute_fixed_git_status(
        tmp_path,
        task_id="task-20260703-001",
        request_id="req-stage49-001",
        expected_plan_hash="sha256:" + "f" * 64,
        commit=True,
        services=_services(tmp_path, blocked_calls),
        registry_check=lambda root: True,
    )
    assert blocked.status == "blocked"
    assert blocked.findings[0].rule_id == "execution.plan-hash-mismatch"
    assert "started" not in blocked_calls
    assert "run" not in blocked_calls


def test_started_failure_prevents_runner_invocation(tmp_path: Path) -> None:
    calls: list[str] = []
    services = _services(tmp_path, calls)

    def fail_started(*args: object, **kwargs: object) -> ExecutionAuditWriteResult:
        calls.append("started")
        return ExecutionAuditWriteResult(
            status="error",
            findings=[
                Finding("audit-failed", "error", "error", "Audit failed.")
            ],
        )

    services["record_started"] = fail_started
    result = execute_fixed_git_status(
        tmp_path,
        task_id="task-20260703-001",
        request_id="req-stage49-001",
        commit=True,
        services=services,
        registry_check=lambda root: True,
    )

    assert result.status == "error"
    assert "run" not in calls
    assert "terminal" not in calls


def test_pre_spawn_guard_drift_records_failure_without_spawn(tmp_path: Path) -> None:
    calls: list[str] = []
    services = _services(tmp_path, calls)
    guards = iter([_guard("2"), _guard("5")])

    def drifting_guard(root: Path) -> RepositoryGuardResult:
        calls.append("guard")
        return next(guards)

    services["build_guard"] = drifting_guard
    result = execute_fixed_git_status(
        tmp_path,
        task_id="task-20260703-001",
        request_id="req-stage49-001",
        commit=True,
        services=services,
        registry_check=lambda root: True,
    )

    assert result.status == "blocked"
    assert "run" not in calls
    assert calls[-1] == "terminal"
    assert result.summary is None


def test_terminal_audit_failure_withholds_success_summary(tmp_path: Path) -> None:
    calls: list[str] = []
    services = _services(tmp_path, calls)

    def fail_terminal(*args: object, **kwargs: object) -> ExecutionAuditWriteResult:
        calls.append("terminal")
        return ExecutionAuditWriteResult(
            status="error",
            audit_incomplete=True,
            findings=[
                Finding("terminal-failed", "error", "error", "Terminal failed.")
            ],
        )

    services["record_terminal"] = fail_terminal
    result = execute_fixed_git_status(
        tmp_path,
        task_id="task-20260703-001",
        request_id="req-stage49-001",
        commit=True,
        services=services,
        registry_check=lambda root: True,
    )

    assert result.status == "error"
    assert result.summary is None
    assert result.audit["audit_incomplete"] is True
    assert result.audit["state"] == "awaiting_terminal"


def test_process_failure_still_runs_post_guard_before_terminal(
    tmp_path: Path,
) -> None:
    calls: list[str] = []
    services = _services(tmp_path, calls)

    def fail_process(*args: object, **kwargs: object) -> FixedProcessResult:
        calls.append("run")
        return FixedProcessResult(
            status="error",
            findings=[
                Finding(
                    "execution.process-timeout",
                    "error",
                    "error",
                    "Process timed out.",
                )
            ],
            duration_bucket="10-30s",
        )

    services["run_process"] = fail_process
    result = execute_fixed_git_status(
        tmp_path,
        task_id="task-20260703-001",
        request_id="req-stage49-001",
        commit=True,
        services=services,
        registry_check=lambda root: True,
    )

    assert result.status == "error"
    assert calls[-3:] == ["run", "guard", "terminal"]
    assert result.no_write_evidence["guard_evidence_passed"] is True


def test_registry_drift_blocks_before_trust(tmp_path: Path) -> None:
    calls: list[str] = []
    result = execute_fixed_git_status(
        tmp_path,
        task_id="task-20260703-001",
        request_id="req-stage49-001",
        commit=True,
        services=_services(tmp_path, calls),
        registry_check=lambda root: False,
    )

    assert result.status == "blocked"
    assert result.findings[0].rule_id == "execution.registry-drift"
    assert calls == ["guard"]
