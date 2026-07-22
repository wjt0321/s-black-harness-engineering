from __future__ import annotations

import json
import inspect
import os
from pathlib import Path

from agent_runtime.execution_audit_writer import ExecutionAuditWriteResult
from agent_runtime.execution_trust import ExecutableIdentity, VerifiedTrustResult
from agent_runtime.fixed_process_runner import FixedProcessResult, JobAccounting
from agent_runtime.git_repository_guard import RepositoryGuard, RepositoryGuardResult
from agent_runtime.orchestration_git_status_execution import (
    _execute_fixed_git_status_core,
    execute_fixed_git_status,
)
from agent_runtime.result import Finding
import agent_runtime.orchestration_git_status_execution as git_status_execution

import pytest
from agent_runtime.execution_lease import (
    ExecutionLeaseResult,
    _LeaseCapability,
    _PortableLeaseBackend,
    _acquire_execution_lease_for_test,
    _held_lease_capability,
)


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
            accounting=JobAccounting(True, 1, 0, 0, True, True),
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


def _install_lease(monkeypatch: object, calls: list[str]) -> None:
    def acquire_lease(root: Path):
        calls.append("lease-acquire")
        lease = _acquire_execution_lease_for_test(
            root,
            lease_path=root.parent / "lease-local" / "execution-lease-v1.lock",
            backend=_PortableLeaseBackend(),
        )
        release = lease.release

        def tracked_release():
            result = release()
            calls.append("lease-release")
            return result

        lease.release = tracked_release
        return lease

    monkeypatch.setattr(git_status_execution, "acquire_execution_lease", acquire_lease)


@pytest.fixture(autouse=True)
def _fake_production_lease(monkeypatch: object) -> None:
    _install_lease(monkeypatch, [])


def test_public_fixed_execution_api_has_no_lease_bypass() -> None:
    parameters = inspect.signature(execute_fixed_git_status).parameters

    assert "_lease_held" not in parameters


def test_services_cannot_override_public_lease(monkeypatch: object, tmp_path: Path) -> None:
    calls: list[str] = []
    _install_lease(monkeypatch, calls)
    services = _services(tmp_path, calls)
    services["acquire_lease"] = lambda root: (_ for _ in ()).throw(
        AssertionError("public lease override used")
    )

    result = execute_fixed_git_status(
        tmp_path,
        task_id="task-20260703-001",
        request_id="req-stage49-001",
        commit=True,
        services=services,
        registry_check=lambda root: True,
    )

    assert result.status == "ready"
    assert calls[0] == "lease-acquire"


def test_fixed_execution_core_rejects_missing_lease_before_preflight(
    tmp_path: Path,
) -> None:
    calls: list[str] = []

    result = _execute_fixed_git_status_core(
        tmp_path,
        task_id="task-20260703-001",
        request_id="req-stage49-001",
        expected_plan_hash=None,
        timeout_seconds=10,
        services=_services(tmp_path, calls),
        registry_check=lambda root: True,
        lease_capability=None,
    )

    assert result.status == "error"
    assert result.findings[0].rule_id == "execution-lease-capability-invalid"
    assert calls == []


def test_fixed_execution_core_rejects_manual_unlocked_capability(
    tmp_path: Path,
) -> None:
    calls: list[str] = []
    synthetic = ExecutionLeaseResult(status="pass", lease_state="active")
    path = tmp_path / "ordinary-file"
    descriptor = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    synthetic.native_handle = descriptor
    capability = _LeaseCapability(synthetic)

    result = _execute_fixed_git_status_core(
        tmp_path,
        task_id="task-20260703-001",
        request_id="req-stage49-001",
        expected_plan_hash=None,
        timeout_seconds=10,
        services=_services(tmp_path, calls),
        registry_check=lambda root: True,
        lease_capability=capability,
    )

    assert result.status == "error"
    assert result.findings[0].rule_id == "execution-lease-capability-invalid"
    assert calls == []
    os.close(descriptor)


def test_fixed_execution_core_rejects_capability_from_another_root(
    tmp_path: Path,
) -> None:
    first_root = tmp_path / "first"
    second_root = tmp_path / "second"
    first_root.mkdir()
    second_root.mkdir()
    lease = _acquire_execution_lease_for_test(
        first_root,
        lease_path=tmp_path / "lease-local" / "execution-lease-v1.lock",
        backend=_PortableLeaseBackend(),
    )
    assert lease.status == "pass"
    calls: list[str] = []

    result = _execute_fixed_git_status_core(
        second_root,
        task_id="task-20260703-001",
        request_id="req-stage49-001",
        expected_plan_hash=None,
        timeout_seconds=10,
        services=_services(tmp_path, calls),
        registry_check=lambda root: True,
        lease_capability=_held_lease_capability(lease),
    )

    assert result.status == "error"
    assert result.findings[0].rule_id == "execution-lease-capability-invalid"
    assert calls == []
    lease.release()


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


def test_ready_path_has_fixed_order_and_safe_summary(
    tmp_path: Path, monkeypatch: object
) -> None:
    calls: list[str] = []
    _install_lease(monkeypatch, calls)
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
        "lease-acquire",
        "guard",
        "trust",
        "started",
        "trust",
        "guard",
        "run",
        "guard",
        "terminal",
        "lease-release",
    ]
    payload = result.to_dict()
    assert payload["schema_version"] == "control-plane/fixed-git-status-execution/v1"
    assert payload["summary"]["untracked"] == 1


def test_new_fixed_execution_uses_v2_and_exact_job_accounting(tmp_path: Path) -> None:
    calls: list[str] = []
    services = _services(tmp_path, calls)
    evidence: dict[str, object] = {}

    def started(*args: object, **kwargs: object) -> ExecutionAuditWriteResult:
        assert kwargs["_schema_version"] == "execution-audit/v2"
        return _started()

    def terminal(*args: object, **kwargs: object) -> ExecutionAuditWriteResult:
        evidence.update(kwargs)
        return _terminal()

    services["record_started"] = started
    services["record_terminal"] = terminal
    result = execute_fixed_git_status(
        tmp_path,
        task_id="task-20260703-001",
        request_id="req-stage49-001",
        commit=True,
        services=services,
        registry_check=lambda root: True,
    )

    assert result.status == "ready"
    assert {key: evidence[key] for key in (
        "job_accounting_passed",
        "job_total_processes",
        "job_active_processes",
        "job_terminated_processes",
        "direct_child_reaped",
        "containment_closed",
    )} == {
        "job_accounting_passed": True,
        "job_total_processes": 1,
        "job_active_processes": 0,
        "job_terminated_processes": 0,
        "direct_child_reaped": True,
        "containment_closed": True,
    }


def test_final_lease_release_failure_withholds_ready_summary(
    tmp_path: Path, monkeypatch: object
) -> None:
    calls: list[str] = []

    class CloseFailureBackend(_PortableLeaseBackend):
        def close(self, handle: int) -> None:
            raise OSError("unsafe raw detail")

    monkeypatch.setattr(
        git_status_execution,
        "acquire_execution_lease",
        lambda root: _acquire_execution_lease_for_test(
            root,
            lease_path=root.parent / "failing-lease" / "execution-lease-v1.lock",
            backend=CloseFailureBackend(),
        ),
    )

    result = execute_fixed_git_status(
        tmp_path,
        task_id="task-20260703-001",
        request_id="req-stage49-001",
        commit=True,
        services=_services(tmp_path, calls),
        registry_check=lambda root: True,
    )

    assert result.status == "error"
    assert result.lifecycle == "withheld"
    assert result.summary is None
    assert result.findings[0].rule_id == "execution-lease-release-failed"
    assert result.audit["state"] == "closed_succeeded"


def test_final_lease_validation_failure_withholds_ready_summary(
    tmp_path: Path, monkeypatch: object
) -> None:
    lease = _acquire_execution_lease_for_test(
        tmp_path,
        lease_path=tmp_path.parent / "validation-lease" / "execution-lease-v1.lock",
        backend=_PortableLeaseBackend(),
    )
    monkeypatch.setattr(lease, "validate", lambda: False)
    monkeypatch.setattr(
        git_status_execution,
        "acquire_execution_lease",
        lambda root: lease,
    )

    result = execute_fixed_git_status(
        tmp_path,
        task_id="task-20260703-001",
        request_id="req-stage49-001",
        commit=True,
        services=_services(tmp_path, []),
        registry_check=lambda root: True,
    )

    assert result.status == "error"
    assert result.lifecycle == "withheld"
    assert result.summary is None
    assert result.findings[0].rule_id == "execution-lease-identity-drift"
    assert result.audit["state"] == "closed_succeeded"


def test_combined_final_validation_and_release_failures_are_both_reported(
    tmp_path: Path, monkeypatch: object
) -> None:
    class CloseFailureBackend(_PortableLeaseBackend):
        def close(self, handle: int) -> None:
            raise OSError("unsafe raw detail")

    lease = _acquire_execution_lease_for_test(
        tmp_path,
        lease_path=tmp_path.parent / "combined-lease" / "execution-lease-v1.lock",
        backend=CloseFailureBackend(),
    )
    monkeypatch.setattr(lease, "validate", lambda: False)
    monkeypatch.setattr(
        git_status_execution,
        "acquire_execution_lease",
        lambda root: lease,
    )

    result = execute_fixed_git_status(
        tmp_path,
        task_id="task-20260703-001",
        request_id="req-stage49-001",
        commit=True,
        services=_services(tmp_path, []),
        registry_check=lambda root: True,
    )

    assert [finding.rule_id for finding in result.findings] == [
        "execution-lease-identity-drift",
        "execution-lease-release-failed",
    ]


def test_execution_wrapper_releases_after_unexpected_core_exception(
    tmp_path: Path,
    monkeypatch: object,
) -> None:
    lease = _acquire_execution_lease_for_test(
        tmp_path,
        lease_path=tmp_path.parent / "exception-lease" / "execution-lease-v1.lock",
        backend=_PortableLeaseBackend(),
    )
    release = lease.release
    released = {"value": False}

    def tracked_release():
        released["value"] = True
        return release()

    monkeypatch.setattr(lease, "release", tracked_release)
    monkeypatch.setattr(git_status_execution, "acquire_execution_lease", lambda root: lease)
    monkeypatch.setattr(
        git_status_execution,
        "_execute_fixed_git_status_core",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("raw core detail")),
    )

    result = execute_fixed_git_status(
        tmp_path,
        task_id="task-20260703-001",
        request_id="req-stage49-001",
        commit=True,
    )

    assert result.status == "error"
    assert released["value"] is True
    assert result.findings[0].rule_id == "execution-core-failed"
    assert "raw core detail" not in json.dumps(result.to_dict())
    reacquired = _acquire_execution_lease_for_test(
        tmp_path,
        lease_path=tmp_path.parent / "exception-lease" / "execution-lease-v1.lock",
        backend=_PortableLeaseBackend(),
    )
    assert reacquired.status == "pass"
    reacquired.release()


@pytest.mark.parametrize("failure_phase", ("second-trust", "guard", "process", "terminal"))
def test_keyboard_interrupt_cleans_all_resources_and_lease_before_propagating(
    tmp_path: Path, monkeypatch: object, failure_phase: str
) -> None:
    lease_path = tmp_path.parent / f"keyboard-{failure_phase}" / "execution-lease-v1.lock"
    lease = _acquire_execution_lease_for_test(
        tmp_path,
        lease_path=lease_path,
        backend=_PortableLeaseBackend(),
    )
    released = {"value": False}
    release = lease.release

    def tracked_release():
        released["value"] = True
        return release()

    monkeypatch.setattr(lease, "release", tracked_release)
    monkeypatch.setattr(git_status_execution, "acquire_execution_lease", lambda root: lease)

    resources: list[dict[str, object]] = []
    phases: list[str] = []
    trust_calls = 0
    guard_calls = 0

    def trust(root: Path) -> VerifiedTrustResult:
        nonlocal trust_calls
        trust_calls += 1
        phases.append(f"trust-{trust_calls}")
        if failure_phase == "second-trust" and trust_calls == 2:
            raise KeyboardInterrupt()
        trust_root = tmp_path / f"trust-{trust_calls}"
        trust_root.mkdir()
        identity = _identity(trust_root)
        state = {"kind": "trust", "closed": False}
        identity.close = lambda: state.__setitem__("closed", True)
        resources.append(state)
        return VerifiedTrustResult(
            status="pass",
            identity=identity,
            binding_id="sha256:" + "3" * 64,
            executable_identity="sha256:" + "4" * 64,
            path_identity="sha256:" + "1" * 64,
        )

    def guard(root: Path) -> RepositoryGuardResult:
        nonlocal guard_calls
        guard_calls += 1
        phases.append(f"guard-{guard_calls}")
        if failure_phase == "guard" and guard_calls == 2:
            raise KeyboardInterrupt()
        state = {"kind": "guard", "closed": False}

        class MutableGuard:
            identity = "sha256:" + "2" * 64
            manifest = (("x", "file", 1, 1, 1, 1, "1:x"),)

            def close(self) -> None:
                state["closed"] = True

            def to_public_dict(self) -> dict[str, object]:
                return {"guard_evidence_passed": True}

        result = RepositoryGuardResult(status="pass", guard=MutableGuard())
        resources.append(state)
        return result

    def process(*args: object, **kwargs: object) -> FixedProcessResult:
        phases.append("process")
        if failure_phase == "process":
            raise KeyboardInterrupt()
        return FixedProcessResult(
            status="pass",
            exit_code=0,
            stdout=b"## main\n",
            stderr=b"",
            duration_bucket="lt-1s",
        )

    def terminal(*args: object, **kwargs: object) -> ExecutionAuditWriteResult:
        phases.append("terminal")
        if failure_phase == "terminal":
            raise KeyboardInterrupt()
        return _terminal()

    services = {
        "verify_trust": trust,
        "build_guard": guard,
        "record_started": lambda *args, **kwargs: _started(),
        "run_process": process,
        "record_terminal": terminal,
    }

    caught = False
    result = None
    try:
        result = execute_fixed_git_status(
            tmp_path,
            task_id="task-20260703-001",
            request_id="req-stage49-001",
            commit=True,
            services=services,
            registry_check=lambda root: True,
        )
    except KeyboardInterrupt:
        caught = True

    assert caught, (
        phases,
        [] if result is None else [finding.rule_id for finding in result.findings],
        None if result is None else result.next_action,
    )

    assert resources
    assert all(resource["closed"] is True for resource in resources)
    assert released["value"] is True
    reacquired = _acquire_execution_lease_for_test(
        tmp_path,
        lease_path=lease_path,
        backend=_PortableLeaseBackend(),
    )
    assert reacquired.status == "pass"
    reacquired.release()


@pytest.mark.parametrize("core_raises", [False, True])
def test_execution_wrapper_releases_when_validation_raises(
    tmp_path: Path,
    monkeypatch: object,
    core_raises: bool,
) -> None:
    lease = _acquire_execution_lease_for_test(
        tmp_path,
        lease_path=tmp_path.parent / "validate-exception-lease" / "execution-lease-v1.lock",
        backend=_PortableLeaseBackend(),
    )
    release = lease.release
    released = {"value": False}

    def validate():
        raise TypeError("raw validate detail")

    def tracked_release():
        released["value"] = True
        return release()

    monkeypatch.setattr(lease, "validate", validate)
    monkeypatch.setattr(lease, "release", tracked_release)
    monkeypatch.setattr(git_status_execution, "acquire_execution_lease", lambda root: lease)
    if core_raises:
        monkeypatch.setattr(
            git_status_execution,
            "_execute_fixed_git_status_core",
            lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("raw core detail")),
        )

    result = execute_fixed_git_status(
        tmp_path,
        task_id="task-20260703-001",
        request_id="req-stage49-001",
        commit=True,
        services=_services(tmp_path, []),
        registry_check=lambda root: True,
    )

    assert result.status == "error"
    assert result.lifecycle == "withheld"
    assert result.summary is None
    assert released["value"] is True
    assert "execution-lease-validation-failed" in [
        finding.rule_id for finding in result.findings
    ]
    assert "raw validate detail" not in json.dumps(result.to_dict())


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


def test_pre_spawn_guard_drift_records_failure_without_spawn(
    tmp_path: Path, monkeypatch: object
) -> None:
    calls: list[str] = []
    _install_lease(monkeypatch, calls)
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
    assert calls[-2:] == ["terminal", "lease-release"]
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
    monkeypatch: object,
) -> None:
    calls: list[str] = []
    _install_lease(monkeypatch, calls)
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
    assert calls[-4:] == ["run", "guard", "terminal", "lease-release"]
    assert result.no_write_evidence["guard_evidence_passed"] is True


def test_registry_drift_blocks_before_trust(
    tmp_path: Path, monkeypatch: object
) -> None:
    calls: list[str] = []
    _install_lease(monkeypatch, calls)
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
    assert calls == ["lease-acquire", "guard", "lease-release"]


@pytest.mark.parametrize(
    ("failure", "expected_state", "terminal_expected"),
    [
        ("started", "not_started", False),
        ("second-trust", "closed_failed", True),
        ("second-guard", "closed_failed", True),
        ("process", "closed_failed", True),
        ("terminal", "awaiting_terminal", True),
    ],
)
def test_unexpected_lifecycle_exceptions_close_resources_and_project_audit(
    tmp_path: Path,
    failure: str,
    expected_state: str,
    terminal_expected: bool,
) -> None:
    calls: list[str] = []
    services = _services(tmp_path, calls)
    trust_calls = 0
    guard_calls = 0
    closed = {"trust": 0, "guard": 0}
    identity_root = tmp_path / "trust"
    identity_root.mkdir()

    def trust(root: Path) -> VerifiedTrustResult:
        nonlocal trust_calls
        trust_calls += 1
        if failure == "second-trust" and trust_calls == 2:
            raise TypeError("raw second trust")
        identity = _identity(identity_root)
        original_close = identity.close

        def close() -> None:
            closed["trust"] += 1
            original_close()

        identity.close = close
        return VerifiedTrustResult(
            status="pass",
            identity=identity,
            binding_id="sha256:" + "3" * 64,
            executable_identity="sha256:" + "4" * 64,
            path_identity=identity.path_identity,
        )

    def guard(root: Path) -> RepositoryGuardResult:
        nonlocal guard_calls
        guard_calls += 1
        if failure == "second-guard" and guard_calls == 2:
            raise TypeError("raw second guard")
        result = _guard("1")
        assert result.guard is not None
        original_close = result.guard.close

        def close() -> None:
            closed["guard"] += 1
            original_close()

        object.__setattr__(result.guard, "close", close)
        return result

    def started(*args: object, **kwargs: object) -> ExecutionAuditWriteResult:
        calls.append("started")
        if failure == "started":
            raise TypeError("raw started")
        return _started()

    terminal_calls = 0

    def terminal(*args: object, **kwargs: object) -> ExecutionAuditWriteResult:
        nonlocal terminal_calls
        terminal_calls += 1
        calls.append("terminal")
        if failure == "terminal":
            raise TypeError("raw terminal")
        if kwargs.get("event_type") == "execution_failed":
            value = _terminal()
            value.event_type = "execution_failed"
            value.committed = True
            return value
        return _terminal()

    def run(*args: object, **kwargs: object) -> FixedProcessResult:
        calls.append("run")
        if failure == "process":
            raise TypeError("raw process")
        return FixedProcessResult(
            status="pass",
            exit_code=0,
            stdout=b"## main\n",
            stderr=b"",
            duration_bucket="lt-1s",
        )

    services.update(
        {
            "verify_trust": trust,
            "build_guard": guard,
            "record_started": started,
            "record_terminal": terminal,
            "run_process": run,
        }
    )

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
    assert result.audit["state"] == expected_state
    assert result.audit["audit_incomplete"] is (expected_state != "closed_failed")
    assert (terminal_calls > 0) is terminal_expected
    assert closed["trust"] == max(0, trust_calls - (1 if failure == "second-trust" else 0))
    assert closed["guard"] == max(0, guard_calls - (1 if failure == "second-guard" else 0))
    payload = json.dumps(result.to_dict())
    assert f"raw {failure.replace('-', ' ')}" not in payload


def test_cleanup_failures_are_independent_and_preserve_terminal_fallback(
    tmp_path: Path,
) -> None:
    calls: list[str] = []
    services = _services(tmp_path, calls)
    identity_root = tmp_path / "trust"
    identity_root.mkdir()
    close_calls = {"trust": 0, "guard": 0}

    def trust(root: Path) -> VerifiedTrustResult:
        identity = _identity(identity_root)

        def close() -> None:
            close_calls["trust"] += 1
            raise OSError("raw trust close")

        identity.close = close
        return VerifiedTrustResult(
            status="pass",
            identity=identity,
            binding_id="sha256:" + "3" * 64,
            executable_identity="sha256:" + "4" * 64,
            path_identity=identity.path_identity,
        )

    def guard(root: Path) -> RepositoryGuardResult:
        result = _guard("1")
        assert result.guard is not None

        def close() -> None:
            close_calls["guard"] += 1
            raise OSError("raw guard close")

        object.__setattr__(result.guard, "close", close)
        return result

    def fail_process(*args: object, **kwargs: object) -> FixedProcessResult:
        raise TypeError("raw process")

    services.update(
        {"verify_trust": trust, "build_guard": guard, "run_process": fail_process}
    )
    result = execute_fixed_git_status(
        tmp_path,
        task_id="task-20260703-001",
        request_id="req-stage49-001",
        commit=True,
        services=services,
        registry_check=lambda root: True,
    )

    assert result.status == "error"
    assert result.audit["state"] == "closed_failed"
    assert result.audit["attempt_id"] == "attempt-20260717-001"
    assert "terminal" in calls
    assert close_calls["trust"] >= 2
    assert close_calls["guard"] >= 2
    assert {
        "execution-trust-identity-close-failed",
        "execution-repository-guard-close-failed",
    }.issubset({finding.rule_id for finding in result.findings})
    payload = json.dumps(result.to_dict())
    assert "raw trust close" not in payload
    assert "raw guard close" not in payload
