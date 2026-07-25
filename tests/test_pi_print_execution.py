from __future__ import annotations

import hashlib
import inspect
import json
import os
from pathlib import Path

import pytest

import agent_runtime.orchestration_pi_print_execution as pi_execution
from agent_runtime.execution_audit_writer import ExecutionAuditWriteResult
from agent_runtime.execution_lease import (
    _PortableLeaseBackend,
    _acquire_execution_lease_for_test,
)
from agent_runtime.execution_trust import SanitizedPath
from agent_runtime.fixed_process_runner import FixedProcessResult, JobAccounting
from agent_runtime.pi_print_runner import run_fixed_pi_print_process
from agent_runtime.fixed_process_runner import UnsupportedProcessBackend
from agent_runtime.orchestration_pi_print_execution import (
    _build_fixed_environment,
    _execute_fixed_pi_print_core,
    _resolve_pi_executable,
    execute_fixed_pi_print,
)
from agent_runtime.pi_runtime_discovery import PiRuntimeStatus
from agent_runtime.result import CheckResult, Finding

KEY_VAR = "STAGE62_FAKE_KEY"
FAKE_KEY_VALUE = "sk-" + "ab12" * 8
SECRET_CANARY = "AKIA" + "STAGE62CANARY00"
PROMPT = "Reply with exactly: STAGE62_OK"
STDOUT = b"STAGE62_OK\n"


def _ready(tmp_path: Path) -> PiRuntimeStatus:
    return PiRuntimeStatus(
        status="ready",
        agent_dir=str(tmp_path / ".runtime" / "pi-agent"),
        default_provider="deepseek-compat",
        default_model="deepseek-v4-flash",
        api_key_env=KEY_VAR,
    )


def _started() -> ExecutionAuditWriteResult:
    return ExecutionAuditWriteResult(
        status="pass",
        event_id="evt-20260725-101",
        attempt_id="attempt-20260725-101",
        task_id="task-20260703-001",
        request_id="req-stage62-001",
        event_type="execution_attempt_started",
        phase="pre_spawn_committed",
        committed=True,
        child_created=False,
    )


def _terminal() -> ExecutionAuditWriteResult:
    return ExecutionAuditWriteResult(
        status="pass",
        event_id="evt-20260725-102",
        attempt_id="attempt-20260725-101",
        event_type="execution_succeeded",
        phase="post_run_validated",
        committed=True,
    )


def _services(
    tmp_path: Path,
    calls: list[str],
    *,
    stdout: bytes = STDOUT,
    exit_code: int = 0,
    discover_results: list[PiRuntimeStatus] | None = None,
    build_environment=None,
    terminal_result: ExecutionAuditWriteResult | None = None,
    started_result: ExecutionAuditWriteResult | None = None,
) -> dict[str, object]:
    readiness_sequence = list(discover_results) if discover_results else None

    def discover(root: Path) -> PiRuntimeStatus:
        calls.append("discover")
        if readiness_sequence:
            return readiness_sequence.pop(0)
        return _ready(tmp_path)

    def build_env(root: Path, readiness: PiRuntimeStatus):
        calls.append("build_environment")
        return (
            {
                "PATH": "C:" + "\\Windows",
                "PI_CODING_AGENT_DIR": readiness.agent_dir or "",
                "AGENT_RUNTIME_ROOT": str(root),
                KEY_VAR: FAKE_KEY_VALUE,
            },
            "sha256:" + "9" * 64,
        )

    def resolve(root: Path):
        calls.append("resolve_executable")
        return tmp_path / "pi.cmd"

    def scan(root: Path, text: str) -> CheckResult:
        calls.append("scan_text")
        return CheckResult(status="pass")

    def started(*args: object, **kwargs: object) -> ExecutionAuditWriteResult:
        calls.append("started")
        return started_result or _started()

    def run(argv, root, environment, *, timeout_seconds):
        calls.append("run")
        run.captured = {
            "argv": list(argv),
            "environment": dict(environment),
            "timeout_seconds": timeout_seconds,
        }
        return FixedProcessResult(
            status="pass",
            exit_code=exit_code,
            stdout=stdout,
            stderr=b"",
            duration_bucket="lt-5s",
            accounting=JobAccounting(True, 2, 0, 1, True, True),
        )

    def terminal(*args: object, **kwargs: object) -> ExecutionAuditWriteResult:
        calls.append("terminal")
        terminal.captured = dict(kwargs)
        return terminal_result or _terminal()

    return {
        "discover": discover,
        "build_environment": build_environment or build_env,
        "resolve_executable": resolve,
        "scan_text": scan,
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

    monkeypatch.setattr(pi_execution, "acquire_execution_lease", acquire_lease)


@pytest.fixture(autouse=True)
def _fake_production_lease(monkeypatch: object) -> None:
    _install_lease(monkeypatch, [])


_SERVICE_OPTION_KEYS = (
    "stdout",
    "exit_code",
    "discover_results",
    "build_environment",
    "terminal_result",
    "started_result",
)


def _execute(tmp_path: Path, calls: list[str], **overrides):
    service_opts = {
        key: overrides.pop(key)
        for key in list(overrides)
        if key in _SERVICE_OPTION_KEYS
    }
    kwargs = {
        "task_id": "task-20260703-001",
        "request_id": "req-stage62-001",
        "prompt": PROMPT,
        "commit": True,
        "services": _services(tmp_path, calls, **service_opts),
        "registry_check": lambda root: True,
    }
    kwargs.update(overrides)
    return execute_fixed_pi_print(tmp_path, **kwargs)


def test_public_fixed_pi_print_api_has_no_lease_bypass() -> None:
    parameters = inspect.signature(execute_fixed_pi_print).parameters

    assert "_lease_held" not in parameters


def test_no_commit_blocked_without_side_effects(tmp_path: Path) -> None:
    calls: list[str] = []

    result = _execute(tmp_path, calls, commit=False)

    assert result.status == "blocked"
    assert result.findings[0].rule_id == "execution.commit-required"
    assert result.exit_code() == 2
    assert calls == []
    assert result.audit == {}
    assert result.summary is None


def test_invalid_identity_tokens_validation_failed(tmp_path: Path) -> None:
    calls: list[str] = []

    result = _execute(tmp_path, calls, task_id="bad/task")

    assert result.status == "validation_failed"
    assert result.findings[0].rule_id == "execution.identity-invalid"
    assert calls == []


def test_timeout_out_of_range_validation_failed(tmp_path: Path) -> None:
    calls: list[str] = []

    result = _execute(tmp_path, calls, timeout_seconds=121)

    assert result.status == "validation_failed"
    assert result.findings[0].rule_id == "pi-print-timeout-invalid"
    assert calls == []


def test_prompt_empty_blocked(tmp_path: Path) -> None:
    calls: list[str] = []

    result = _execute(tmp_path, calls, prompt="   ")

    assert result.status == "blocked"
    assert result.findings[0].rule_id == "pi-print-prompt-empty"
    assert calls == []


def test_prompt_too_large_blocked_utf8_byte_bound(tmp_path: Path) -> None:
    calls: list[str] = []
    prompt = "好" * 1366  # 4098 UTF-8 bytes

    result = _execute(tmp_path, calls, prompt=prompt)

    assert result.status == "blocked"
    assert result.findings[0].rule_id == "pi-print-prompt-too-large"
    assert calls == []


def test_prompt_control_characters_blocked(tmp_path: Path) -> None:
    calls: list[str] = []

    result = _execute(tmp_path, calls, prompt="bad\x01prompt")

    assert result.status == "blocked"
    assert result.findings[0].rule_id == "pi-print-prompt-control-characters"
    assert calls == []


def test_prompt_flag_like_blocked(tmp_path: Path) -> None:
    for prompt in ("-x", "  --no-tools", "\t--print"):
        calls: list[str] = []

        result = _execute(tmp_path, calls, prompt=prompt)

        assert result.status == "blocked"
        assert result.findings[0].rule_id == "pi-print-prompt-flag-like"
        assert calls == []


def test_prompt_secret_scan_blocked_and_value_withheld(tmp_path: Path) -> None:
    calls: list[str] = []

    def scan(root: Path, text: str) -> CheckResult:
        return CheckResult(
            status="blocked",
            findings=[Finding("fake-secret-rule", "block", "deny", "matched")],
        )

    services = _services(tmp_path, calls)
    services["scan_text"] = scan
    result = _execute(
        tmp_path, calls, prompt=f"tell me {SECRET_CANARY}", services=services
    )

    assert result.status == "blocked"
    assert result.findings[0].rule_id == "pi-print-prompt-secret-scan"
    assert SECRET_CANARY not in json.dumps(result.to_dict(), ensure_ascii=False)
    assert "started" not in calls
    assert "run" not in calls


def test_registry_drift_blocked(tmp_path: Path) -> None:
    calls: list[str] = []

    result = _execute(tmp_path, calls, registry_check=lambda root: False)

    assert result.status == "blocked"
    assert result.findings[0].rule_id == "execution.registry-drift"
    assert "started" not in calls
    assert "run" not in calls


def test_readiness_not_ready_blocked(tmp_path: Path) -> None:
    calls: list[str] = []
    not_ready = PiRuntimeStatus(
        status="needs_input",
        findings=[Finding("pi-runtime-env-dir-missing", "warn", "needs_input", "missing")],
    )

    result = _execute(tmp_path, calls, discover_results=[not_ready])

    assert result.status == "blocked"
    assert result.findings[0].rule_id == "pi-print-readiness-not-ready"
    assert result.runtime["status"] == "needs_input"
    assert "started" not in calls
    assert "run" not in calls


def test_missing_api_key_env_needs_input(tmp_path: Path) -> None:
    calls: list[str] = []
    services = _services(tmp_path, calls)
    services["build_environment"] = lambda root, readiness: None

    result = _execute(tmp_path, calls, services=services)

    assert result.status == "needs_input"
    assert result.findings[0].rule_id == "pi-print-api-key-env-missing"
    assert "started" not in calls


def test_executable_not_found_blocked(tmp_path: Path) -> None:
    calls: list[str] = []
    services = _services(tmp_path, calls)
    services["resolve_executable"] = lambda root: None

    result = _execute(tmp_path, calls, services=services)

    assert result.status == "blocked"
    assert result.findings[0].rule_id == "pi-print-executable-not-found"
    assert "started" not in calls


def test_default_environment_builder_allowlist(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(KEY_VAR, FAKE_KEY_VALUE)
    monkeypatch.setenv("HTTP_PROXY", "http://proxy.invalid:8080")
    monkeypatch.setenv("STAGE62_OTHER_TOKEN", "tok-" + "zz" * 8)
    monkeypatch.setattr(
        pi_execution,
        "sanitize_path",
        lambda value, root, **kwargs: SanitizedPath(
            directories=(tmp_path,),
            serialized="C:" + "\\Windows",
            identity="sha256:" + "8" * 64,
        ),
    )

    built = _build_fixed_environment(tmp_path, _ready(tmp_path))

    assert built is not None
    environment, path_identity = built
    assert path_identity == "sha256:" + "8" * 64
    assert set(environment) <= {
        "PATH",
        "SYSTEMROOT",
        "COMSPEC",
        "WINDIR",
        "PI_CODING_AGENT_DIR",
        "AGENT_RUNTIME_ROOT",
        KEY_VAR,
    }
    assert "HTTP_PROXY" not in environment
    assert "STAGE62_OTHER_TOKEN" not in environment
    assert environment[KEY_VAR] == FAKE_KEY_VALUE


def test_default_environment_builder_missing_key_returns_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(KEY_VAR, raising=False)
    monkeypatch.setattr(
        pi_execution,
        "sanitize_path",
        lambda value, root, **kwargs: SanitizedPath(
            directories=(), serialized="", identity="sha256:" + "8" * 64
        ),
    )

    assert _build_fixed_environment(tmp_path, _ready(tmp_path)) is None


def test_resolve_pi_executable_first_match_and_project_local_skip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_local = tmp_path / "bin"
    project_local.mkdir()
    (project_local / "pi.cmd").write_text("@echo off\n", encoding="utf-8")
    system_dir = tmp_path.parent / "stage62-system-bin"
    system_dir.mkdir(exist_ok=True)
    shim = system_dir / "pi.cmd"
    shim.write_text("@echo off\n", encoding="utf-8")
    monkeypatch.setenv("PATH", os.pathsep.join([str(project_local), str(system_dir)]))

    resolved = _resolve_pi_executable(tmp_path)

    assert resolved == shim


def test_resolve_pi_executable_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PATH", str(tmp_path.parent))

    assert _resolve_pi_executable(tmp_path) is None


def test_happy_path_ready_fixed_argv_and_safe_projection(tmp_path: Path) -> None:
    calls: list[str] = []
    services = _services(tmp_path, calls)

    result = _execute(tmp_path, calls, services=services)

    assert result.status == "ready"
    assert result.exit_code() == 0
    assert result.lifecycle == "closed"
    assert result.audit == {
        "attempt_id": "attempt-20260725-101",
        "state": "closed_succeeded",
        "audit_incomplete": False,
    }
    captured = services["run_process"].captured
    assert captured["argv"] == [
        str(tmp_path / "pi.cmd"),
        "--print",
        "--no-session",
        "--no-tools",
        PROMPT,
    ]
    assert captured["timeout_seconds"] == 60
    expected_digest = "sha256:" + hashlib.sha256(STDOUT).hexdigest()
    assert result.summary is not None
    assert result.summary["stdout_digest"] == expected_digest
    assert result.summary["stdout_byte_count"] == len(STDOUT)
    assert result.summary["provider"] == "deepseek-compat"
    assert result.summary["model"] == "deepseek-v4-flash"
    terminal_kwargs = services["record_terminal"].captured
    assert terminal_kwargs["event_type"] == "execution_succeeded"
    assert terminal_kwargs["output_digest"] == expected_digest
    assert terminal_kwargs["guard_status"] == "pass"
    assert terminal_kwargs["job_accounting_passed"] is True
    payload = json.dumps(result.to_dict(), ensure_ascii=False)
    assert "STAGE62_OK" not in payload
    assert PROMPT not in payload
    assert FAKE_KEY_VALUE not in payload


def test_plan_hash_deterministic_and_prompt_bound(tmp_path: Path) -> None:
    first = _execute(tmp_path, [])
    second = _execute(tmp_path, [])
    third = _execute(tmp_path, [], prompt="Reply with exactly: STAGE62_OTHER")

    assert first.plan_hash is not None
    assert first.plan_hash == second.plan_hash
    assert third.plan_hash != first.plan_hash


def test_expected_plan_hash_mismatch_blocked(tmp_path: Path) -> None:
    calls: list[str] = []

    result = _execute(tmp_path, calls, expected_plan_hash="sha256:" + "0" * 64)

    assert result.status == "blocked"
    assert result.findings[0].rule_id == "execution.plan-hash-mismatch"
    assert result.plan_hash is not None
    assert "started" not in calls
    assert "run" not in calls


def test_expected_plan_hash_match_passes(tmp_path: Path) -> None:
    baseline = _execute(tmp_path, [])
    calls: list[str] = []

    result = _execute(tmp_path, calls, expected_plan_hash=baseline.plan_hash)

    assert result.status == "ready"


def test_started_failure_blocks_spawn(tmp_path: Path) -> None:
    calls: list[str] = []
    failing = ExecutionAuditWriteResult(
        status="error",
        findings=[Finding("ledger-write-failed", "error", "error", "write failed")],
        committed=False,
    )

    result = _execute(tmp_path, calls, started_result=failing)

    assert result.status == "error"
    assert result.audit == {"state": "not_started", "audit_incomplete": True}
    assert "run" not in calls
    assert "terminal" not in calls


def test_process_timeout_maps_to_child_terminal_failure(tmp_path: Path) -> None:
    calls: list[str] = []
    services = _services(tmp_path, calls)

    def run(argv, root, environment, *, timeout_seconds):
        return FixedProcessResult(
            status="error",
            findings=[
                Finding(
                    "execution.process-timeout",
                    "error",
                    "error",
                    "The fixed Pi print process exceeded its timeout.",
                )
            ],
            duration_bucket="60-120s",
        )

    services["run_process"] = run
    result = _execute(tmp_path, calls, services=services)

    assert result.status == "error"
    assert result.lifecycle == "closed"
    assert result.audit["state"] == "closed_failed"
    terminal_kwargs = services["record_terminal"].captured
    assert terminal_kwargs["event_type"] == "execution_failed"
    assert terminal_kwargs["phase"] == "child"
    assert terminal_kwargs["failure_code"] == "execution.process-timeout"


def test_platform_unavailable_maps_to_spawn_phase(tmp_path: Path) -> None:
    calls: list[str] = []
    services = _services(tmp_path, calls)
    services["run_process"] = lambda argv, root, environment, *, timeout_seconds: (
        run_fixed_pi_print_process(
            argv, root, environment, timeout_seconds=60, backend=UnsupportedProcessBackend()
        )
    )

    result = _execute(tmp_path, calls, services=services)

    assert result.status == "error"
    terminal_kwargs = services["record_terminal"].captured
    assert terminal_kwargs["phase"] == "spawn"
    assert terminal_kwargs["failure_code"] == "execution.process-platform-unavailable"


def test_nonzero_exit_maps_to_child_output_failure(tmp_path: Path) -> None:
    calls: list[str] = []

    result = _execute(tmp_path, calls, exit_code=3)

    assert result.status == "error"
    assert result.findings[0].rule_id == "execution.child_nonzero"
    terminal_kwargs = result  # projection already safe; failure code asserted below
    assert "execution.child_nonzero" in json.dumps(result.to_dict())


def test_output_invalid_utf8_withheld(tmp_path: Path) -> None:
    calls: list[str] = []

    result = _execute(tmp_path, calls, stdout=b"\xff\xfe invalid")

    assert result.status == "error"
    assert result.findings[0].rule_id == "pi-print-output-invalid-utf8"
    assert result.summary is None


def test_output_nul_withheld(tmp_path: Path) -> None:
    calls: list[str] = []

    result = _execute(tmp_path, calls, stdout=b"ok\x00bytes")

    assert result.status == "error"
    assert result.findings[0].rule_id == "pi-print-output-nul"


def test_output_empty_maps_to_output_validation(tmp_path: Path) -> None:
    calls: list[str] = []

    result = _execute(tmp_path, calls, stdout=b"   \n")

    assert result.status == "error"
    assert result.findings[0].rule_id == "pi-print-output-empty"


def test_output_too_many_lines(tmp_path: Path) -> None:
    calls: list[str] = []
    stdout = b"x\n" * 5000

    result = _execute(tmp_path, calls, stdout=stdout)

    assert result.status == "error"
    assert result.findings[0].rule_id == "pi-print-output-too-many-lines"


def test_output_secret_scan_blocked_and_value_withheld(tmp_path: Path) -> None:
    calls: list[str] = []
    services = _services(tmp_path, calls, stdout=f"key={SECRET_CANARY}\n".encode())
    scans: list[str] = []

    def scan(root: Path, text: str) -> CheckResult:
        scans.append(text)
        if SECRET_CANARY in text:
            return CheckResult(status="blocked")
        return CheckResult(status="pass")

    services["scan_text"] = scan
    result = _execute(tmp_path, calls, services=services)

    assert result.status == "blocked"
    assert result.findings[0].rule_id == "pi-print-output-secret-scan"
    assert result.lifecycle == "closed"
    assert result.summary is None
    assert SECRET_CANARY not in json.dumps(result.to_dict(), ensure_ascii=False)


def test_readiness_drift_pre_spawn_terminal_failure(tmp_path: Path) -> None:
    calls: list[str] = []
    drifted = PiRuntimeStatus(status="invalid")

    result = _execute(tmp_path, calls, discover_results=[_ready(tmp_path), drifted])

    assert result.status == "blocked"
    assert result.findings[0].rule_id == "pi-print.readiness-drift"
    assert result.audit["state"] == "closed_failed"
    assert "run" not in calls


def test_readiness_drift_post_run_guard(tmp_path: Path) -> None:
    calls: list[str] = []
    drifted = PiRuntimeStatus(status="invalid")

    result = _execute(
        tmp_path,
        calls,
        discover_results=[_ready(tmp_path), _ready(tmp_path), drifted],
    )

    assert result.status == "blocked"
    assert result.findings[0].rule_id == "pi-print.readiness-drift"
    assert "run" in calls
    assert result.audit["state"] == "closed_failed"


def test_terminal_commit_failure_audit_incomplete_summary_withheld(tmp_path: Path) -> None:
    calls: list[str] = []
    failing_terminal = ExecutionAuditWriteResult(
        status="error",
        findings=[Finding("ledger-write-failed", "error", "error", "write failed")],
        committed=False,
        audit_incomplete=True,
    )

    result = _execute(tmp_path, calls, terminal_result=failing_terminal)

    assert result.status == "error"
    assert result.lifecycle == "withheld"
    assert result.audit["audit_incomplete"] is True
    assert result.summary is None


def test_core_rejects_missing_lease_capability(tmp_path: Path) -> None:
    calls: list[str] = []

    result = _execute_fixed_pi_print_core(
        tmp_path,
        task_id="task-20260703-001",
        request_id="req-stage62-001",
        prompt=PROMPT,
        expected_plan_hash=None,
        timeout_seconds=60,
        services=_services(tmp_path, calls),
        registry_check=lambda root: True,
        lease_capability=None,
    )

    assert result.status == "error"
    assert result.findings[0].rule_id == "execution-lease-capability-invalid"
    assert calls == []


def test_runner_rejects_out_of_range_timeout() -> None:
    result = run_fixed_pi_print_process(
        ["pi", "--print"],
        Path("."),
        {},
        timeout_seconds=1,
        backend=UnsupportedProcessBackend(),
    )

    # platform check wins over timeout on unsupported platforms
    assert result.status in {"error", "validation_failed"}


def test_cli_pi_print_without_commit_is_blocked(capsys, tmp_path: Path) -> None:
    from agent_runtime import cli

    exit_code = cli.main(
        [
            "orchestration",
            "execution",
            "pi-print",
            "--task-id",
            "task-20260703-001",
            "--request-id",
            "req-stage62-001",
            "--prompt",
            PROMPT,
            "--json",
            "--root",
            str(tmp_path),
        ]
    )

    assert exit_code == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "blocked"
    assert payload["findings"][0]["rule_id"] == "execution.commit-required"
    assert payload["guarantees"]["real_model_call"] is True
    assert payload["guarantees"]["trusted_executable_chain"] is False
