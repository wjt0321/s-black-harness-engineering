from __future__ import annotations

import io
import os
from pathlib import Path

from agent_runtime.execution_trust import ExecutableIdentity
from agent_runtime.fixed_process_runner import run_fixed_git_status_process


class FakeProcess:
    def __init__(
        self,
        stdout: bytes = b"## main\n",
        stderr: bytes = b"",
        returncode: int | None = 0,
    ) -> None:
        self.stdout = io.BytesIO(stdout)
        self.stderr = io.BytesIO(stderr)
        self.returncode = returncode
        self.pid = 42
        self.waited = False

    def poll(self) -> int | None:
        return self.returncode

    def wait(self, timeout: float | None = None) -> int:
        self.waited = True
        if self.returncode is None:
            raise TimeoutError
        return self.returncode


class FakeBackend:
    platform = "windows"

    def __init__(self, process: FakeProcess | None = None) -> None:
        self.process = process or FakeProcess()
        self.calls: list[object] = []
        self.image_matches = True

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
        "close_job",
    ]


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
    assert backend.calls[-3:] == ["terminate_tree", "kill_tree", "close_job"]


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
