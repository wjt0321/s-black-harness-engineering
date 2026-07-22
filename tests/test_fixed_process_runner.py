from __future__ import annotations

import io
import os
import ctypes
from pathlib import Path

from agent_runtime.execution_trust import ExecutableIdentity
from agent_runtime.fixed_process_runner import (
    JobAccounting,
    JobCounters,
    WindowsProcessBackend,
    run_fixed_git_status_process,
)


class FakeProcess:
    def __init__(
        self,
        stdout: bytes = b"## main\n",
        stderr: bytes = b"",
        returncode: int | None = 0,
        calls: list[object] | None = None,
        wait_error: bool = False,
        poll_error: bool = False,
    ) -> None:
        self.stdout = io.BytesIO(stdout)
        self.stderr = io.BytesIO(stderr)
        self.returncode = returncode
        self.pid = 42
        self.waited = False
        self.calls = calls
        self.wait_error = wait_error
        self.poll_error = poll_error

    def poll(self) -> int | None:
        if self.poll_error:
            raise ValueError("poll failed")
        return self.returncode

    def wait(self, timeout: float | None = None) -> int:
        self.waited = True
        if self.calls is not None:
            self.calls.append("wait")
        if self.wait_error:
            raise OSError("wait failed")
        if self.returncode is None:
            raise TimeoutError
        return self.returncode


class FakeBackend:
    platform = "windows"

    def __init__(self, process: FakeProcess | None = None) -> None:
        self.process = process or FakeProcess()
        self.calls: list[object] = []
        self.image_matches = True
        self.accounting = JobCounters(1, 0, 0)
        self.accounting_queries = 0
        self.query_error = False
        self.close_error = False

    def create_job(self) -> object:
        self.calls.append("create_job")
        return object()

    def spawn(
        self,
        argv: list[str],
        *,
        cwd: Path,
        environment: dict[str, str],
    ) -> FakeProcess:
        self.calls.append(("spawn", argv, cwd, environment))
        return self.process

    def assign(self, job: object, process: FakeProcess) -> None:
        self.calls.append("assign")

    def verify_image(
        self, process: FakeProcess, identity: ExecutableIdentity
    ) -> bool:
        self.calls.append("verify_image")
        return self.image_matches

    def resume(self, process: FakeProcess) -> None:
        self.calls.append("resume")

    def terminate_tree(self, job: object, process: FakeProcess) -> None:
        self.calls.append("terminate_tree")

    def kill_tree(self, job: object, process: FakeProcess) -> None:
        self.calls.append("kill_tree")
        process.returncode = 1

    def close_job(self, job: object) -> None:
        self.calls.append("close_job")
        if self.close_error:
            raise OSError("close failed")

    def query_job_accounting(self, job: object) -> JobCounters:
        self.calls.append("query_job_accounting")
        self.accounting_queries += 1
        if self.query_error:
            raise OSError("query failed")
        return self.accounting

    def terminate_process(self, process: FakeProcess) -> None:
        self.calls.append("terminate_process")

    def kill_process(self, process: FakeProcess) -> None:
        self.calls.append("kill_process")
        process.returncode = 1


def _identity(tmp_path: Path) -> ExecutableIdentity:
    path = tmp_path / "git.exe"
    path.write_bytes(b"git")
    return ExecutableIdentity(
        canonical_path=path,
        approved_root=tmp_path,
        sha256="a" * 64,
        file_identity="volume:file",
        publisher_thumbprint="B" * 40,
        owner_policy="windows-system-install",
    )


def test_runner_owns_exact_argv_environment_and_lifecycle(tmp_path: Path) -> None:
    backend = FakeBackend()
    trusted_path = "C" + ":" + "\\trusted"
    environment = {"PATH": trusted_path, "GIT_OPTIONAL_LOCKS": "0"}
    result = run_fixed_git_status_process(
        _identity(tmp_path),
        tmp_path,
        environment,
        timeout_seconds=10,
        backend=backend,
    )

    assert result.status == "pass"
    assert result.exit_code == 0
    assert result.stdout == b"## main\n"
    assert result.stderr == b""
    spawn = backend.calls[1]
    assert spawn == (
        "spawn",
        [str(tmp_path / "git.exe"), "status", "--short", "--branch"],
        tmp_path,
        environment,
    )
    assert backend.calls == [
        "create_job",
        spawn,
        "assign",
        "verify_image",
        "resume",
        "query_job_accounting",
        "close_job",
    ]
    assert result.to_dict()["job_accounting_passed"] is True
    assert result.to_dict()["job_active_processes"] == 0
    assert result.to_dict()["direct_child_reaped"] is True
    assert result.to_dict()["containment_closed"] is True


def test_image_mismatch_blocks_resume_and_closes_tree(tmp_path: Path) -> None:
    backend = FakeBackend(FakeProcess(returncode=None))
    backend.image_matches = False

    result = run_fixed_git_status_process(
        _identity(tmp_path),
        tmp_path,
        {"PATH": "trusted"},
        backend=backend,
    )

    assert result.status == "error"
    assert result.findings[0].rule_id == "execution.process-image-mismatch"
    assert "resume" not in backend.calls
    assert backend.calls[-4:] == [
        "terminate_tree",
        "kill_tree",
        "query_job_accounting",
        "close_job",
    ]


def test_output_limit_stops_tree_and_withholds_partial_bytes(tmp_path: Path) -> None:
    backend = FakeBackend(FakeProcess(stdout=b"x" * 65_537, returncode=None))

    result = run_fixed_git_status_process(
        _identity(tmp_path),
        tmp_path,
        {"PATH": "trusted"},
        backend=backend,
    )

    assert result.status == "blocked"
    assert result.findings[0].rule_id == "execution.output-too-large"
    assert result.stdout == b""
    assert result.stderr == b""
    assert "terminate_tree" in backend.calls
    assert "kill_tree" in backend.calls


def test_output_limit_is_enforced_even_when_child_already_exited(
    tmp_path: Path,
) -> None:
    backend = FakeBackend(FakeProcess(stdout=b"x" * 65_537, returncode=0))

    result = run_fixed_git_status_process(
        _identity(tmp_path),
        tmp_path,
        {"PATH": "trusted"},
        backend=backend,
    )

    assert result.status == "blocked"
    assert result.findings[0].rule_id == "execution.output-too-large"
    assert result.stdout == b""
    assert result.stderr == b""


def test_timeout_stops_tree_and_waits(tmp_path: Path) -> None:
    process = FakeProcess(returncode=None)
    backend = FakeBackend(process)

    result = run_fixed_git_status_process(
        _identity(tmp_path),
        tmp_path,
        {"PATH": "trusted"},
        timeout_seconds=0.01,
        backend=backend,
    )

    assert result.status == "error"
    assert result.findings[0].rule_id == "execution.process-timeout"
    assert "terminate_tree" in backend.calls
    assert "kill_tree" in backend.calls
    assert process.waited is True


def test_assignment_failure_terminates_uncontained_process(tmp_path: Path) -> None:
    process = FakeProcess(returncode=None)
    backend = FakeBackend(process)

    def fail_assign(job: object, child: FakeProcess) -> None:
        backend.calls.append("assign")
        raise OSError("assignment failed")

    backend.assign = fail_assign  # type: ignore[method-assign]
    result = run_fixed_git_status_process(
        _identity(tmp_path),
        tmp_path,
        {"PATH": "trusted"},
        backend=backend,
    )

    assert result.status == "error"
    assert "terminate_process" in backend.calls
    assert "kill_process" in backend.calls
    assert "terminate_tree" not in backend.calls
    assert backend.calls[-1] == "close_job"


def test_job_close_failure_withholds_success(tmp_path: Path) -> None:
    backend = FakeBackend()

    def fail_close(job: object) -> None:
        backend.calls.append("close_job")
        raise OSError("close failed")

    backend.close_job = fail_close  # type: ignore[method-assign]
    result = run_fixed_git_status_process(
        _identity(tmp_path),
        tmp_path,
        {"PATH": "trusted"},
        backend=backend,
    )

    assert result.status == "error"
    assert result.findings[0].rule_id == "execution.process-cleanup-failed"
    assert result.stdout == b""
    assert result.stderr == b""


def test_active_job_is_cleaned_and_requeried_before_release(tmp_path: Path) -> None:
    backend = FakeBackend()
    backend.accounting = JobCounters(2, 1, 0)

    def query(job: object) -> JobCounters:
        backend.calls.append("query_job_accounting")
        backend.accounting_queries += 1
        if backend.accounting_queries == 2:
            return JobCounters(2, 0, 1)
        return backend.accounting

    backend.query_job_accounting = query  # type: ignore[method-assign]
    result = run_fixed_git_status_process(_identity(tmp_path), tmp_path, {"PATH": "trusted"}, backend=backend)

    assert result.status == "pass", (result.to_dict(), backend.calls)
    assert backend.calls.count("query_job_accounting") == 2
    assert "terminate_tree" in backend.calls
    assert result.stdout == b"## main\n"


def test_accounting_query_failure_withholds_output(tmp_path: Path) -> None:
    backend = FakeBackend()
    backend.query_error = True
    result = run_fixed_git_status_process(_identity(tmp_path), tmp_path, {"PATH": "trusted"}, backend=backend)

    assert result.status == "error"
    assert result.stdout == b""
    assert result.stderr == b""


def test_invalid_accounting_counts_withhold_output(tmp_path: Path) -> None:
    backend = FakeBackend()
    backend.accounting = JobCounters(0, 0, 1)
    result = run_fixed_git_status_process(_identity(tmp_path), tmp_path, {"PATH": "trusted"}, backend=backend)

    assert result.status == "error"
    assert result.stdout == b""
    assert result.stderr == b""


def test_boolean_accounting_count_is_invalid(tmp_path: Path) -> None:
    backend = FakeBackend()
    backend.accounting = JobCounters(True, 0, 0)  # type: ignore[arg-type]
    result = run_fixed_git_status_process(_identity(tmp_path), tmp_path, {"PATH": "trusted"}, backend=backend)

    assert result.status == "error"


def test_wait_failure_withholds_output(tmp_path: Path) -> None:
    backend = FakeBackend(FakeProcess(wait_error=True))
    result = run_fixed_git_status_process(_identity(tmp_path), tmp_path, {"PATH": "trusted"}, backend=backend)

    assert result.status == "error"
    assert result.stdout == b""
    assert result.stderr == b""


def test_windows_query_returns_only_os_counters() -> None:
    class Query:
        def __call__(self, handle: object, info_class: int, pointer: object, size: int, returned: object) -> int:
            info = pointer._obj  # type: ignore[attr-defined]
            info.TotalProcesses = 3
            info.ActiveProcesses = 0
            info.TotalTerminatedProcesses = 2
            return 1

    class Kernel32:
        QueryInformationJobObject = Query()

    backend = object.__new__(WindowsProcessBackend)
    backend.kernel32 = Kernel32()
    counters = backend.query_job_accounting(1)

    assert counters == JobCounters(3, 0, 2)
    assert not hasattr(counters, "direct_child_reaped")


def test_finalization_joins_both_readers_before_query_and_close(
    tmp_path: Path, monkeypatch: object
) -> None:
    calls: list[object] = []
    process = FakeProcess(calls=calls)
    backend = FakeBackend(process)
    backend.calls = calls

    class Reader:
        def __init__(self, **kwargs: object) -> None:
            self.target = kwargs["target"]
            self.args = kwargs["args"]
            self.name = "reader"

        def start(self) -> None:
            self.target(*self.args)  # type: ignore[operator]

        def join(self, timeout: float | None = None) -> None:
            calls.append("reader_join")

        def is_alive(self) -> bool:
            return False

    monkeypatch.setattr("agent_runtime.fixed_process_runner.threading.Thread", Reader)
    result = run_fixed_git_status_process(_identity(tmp_path), tmp_path, {"PATH": "trusted"}, backend=backend)

    assert result.status == "pass"
    assert calls.index("wait") < calls.index("reader_join")
    assert calls.count("reader_join") == 2
    assert max(index for index, call in enumerate(calls) if call == "reader_join") < calls.index("query_job_accounting")
    assert calls.index("query_job_accounting") < calls.index("close_job")
    assert result.accounting == JobAccounting(True, 1, 0, 0, True, True)


def test_unexpected_exception_joins_readers_before_accounting_and_close(
    tmp_path: Path, monkeypatch: object
) -> None:
    calls: list[object] = []
    process = FakeProcess(returncode=None, calls=calls, poll_error=True)
    backend = FakeBackend(process)
    backend.calls = calls

    class Reader:
        def __init__(self, **kwargs: object) -> None:
            pass
        def start(self) -> None:
            pass
        def join(self, timeout: float | None = None) -> None:
            calls.append("reader_join")
        def is_alive(self) -> bool:
            return False

    monkeypatch.setattr("agent_runtime.fixed_process_runner.threading.Thread", Reader)
    result = run_fixed_git_status_process(_identity(tmp_path), tmp_path, {"PATH": "trusted"}, backend=backend)

    assert result.status == "error"
    assert calls.count("reader_join") >= 2
    assert max(index for index, call in enumerate(calls) if call == "reader_join") < calls.index("query_job_accounting")
    assert calls.index("query_job_accounting") < calls.index("close_job")


def test_reader_alive_is_finalization_error_and_withholds_output(
    tmp_path: Path, monkeypatch: object
) -> None:
    calls: list[object] = []
    backend = FakeBackend(FakeProcess(calls=calls))
    backend.calls = calls

    class Reader:
        def __init__(self, **kwargs: object) -> None:
            pass
        def start(self) -> None:
            pass
        def join(self, timeout: float | None = None) -> None:
            calls.append("reader_join")
        def is_alive(self) -> bool:
            return True

    monkeypatch.setattr("agent_runtime.fixed_process_runner.threading.Thread", Reader)
    result = run_fixed_git_status_process(_identity(tmp_path), tmp_path, {"PATH": "trusted"}, backend=backend)

    assert result.status == "error"
    assert result.stdout == b""
    assert result.stderr == b""
    assert max(index for index, call in enumerate(calls) if call == "reader_join") < calls.index("query_job_accounting")
    assert calls.index("query_job_accounting") < calls.index("close_job")


def test_fixed_result_projection_exposes_only_safe_accounting(tmp_path: Path) -> None:
    result = run_fixed_git_status_process(_identity(tmp_path), tmp_path, {"PATH": "trusted"}, backend=FakeBackend())

    public = result.to_dict()
    assert public["containment_closed"] is True
    assert "accounting" not in public
    assert "stdout" not in public
    assert "stderr" not in public


def test_unsupported_platform_is_unavailable(tmp_path: Path) -> None:
    class PosixBackend(FakeBackend):
        platform = "posix"

    result = run_fixed_git_status_process(
        _identity(tmp_path),
        tmp_path,
        {"PATH": "trusted"},
        backend=PosixBackend(),
    )

    assert result.status == "error"
    assert result.findings[0].rule_id == "execution.process-platform-unavailable"


def test_result_projection_never_contains_raw_output(tmp_path: Path) -> None:
    backend = FakeBackend(FakeProcess(stdout=b"## main\n?? secret.txt\n"))

    result = run_fixed_git_status_process(
        _identity(tmp_path),
        tmp_path,
        {"PATH": "trusted"},
        backend=backend,
    )

    assert "secret" not in str(result.to_dict())
    assert "stdout" not in result.to_dict()
    assert os.fspath(tmp_path) not in str(result.to_dict())
