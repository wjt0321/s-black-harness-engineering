"""Bounded Windows process-tree runner for one fixed Git status argv."""

from __future__ import annotations

import ctypes
import os
import subprocess
import threading
import time
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import Path
from typing import Any, BinaryIO, Protocol

from .execution_trust import ExecutableIdentity, WindowsTrustBackend
from .result import CheckResult, Finding

_MAX_STREAM_BYTES = 65_536
_DEFAULT_TIMEOUT_SECONDS = 10.0
_MAX_TIMEOUT_SECONDS = 30.0
_TERMINATE_GRACE_SECONDS = 1.0


class ProcessLike(Protocol):
    stdout: BinaryIO | None
    stderr: BinaryIO | None
    pid: int

    def poll(self) -> int | None: ...

    def wait(self, timeout: float | None = None) -> int: ...


class ProcessBackend(Protocol):
    platform: str

    def create_job(self) -> object: ...

    def spawn(
        self,
        argv: list[str],
        *,
        cwd: Path,
        environment: dict[str, str],
    ) -> ProcessLike: ...

    def assign(self, job: object, process: ProcessLike) -> None: ...

    def verify_image(
        self, process: ProcessLike, identity: ExecutableIdentity
    ) -> bool: ...

    def resume(self, process: ProcessLike) -> None: ...

    def terminate_tree(self, job: object, process: ProcessLike) -> None: ...

    def kill_tree(self, job: object, process: ProcessLike) -> None: ...

    def terminate_process(self, process: ProcessLike) -> None: ...

    def kill_process(self, process: ProcessLike) -> None: ...

    def close_job(self, job: object) -> None: ...

    def query_job_accounting(self, job: object) -> "JobCounters": ...


@dataclass
class JobCounters:
    job_total_processes: int
    job_active_processes: int
    job_terminated_processes: int


@dataclass
class JobAccounting:
    job_accounting_passed: bool
    job_total_processes: int
    job_active_processes: int
    job_terminated_processes: int
    direct_child_reaped: bool
    containment_closed: bool


@dataclass
class FixedProcessResult(CheckResult):
    exit_code: int | None = None
    stdout: bytes = b""
    stderr: bytes = b""
    duration_bucket: str | None = None
    stdout_truncated: bool = False
    stderr_truncated: bool = False
    accounting: JobAccounting | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        if self.exit_code is not None:
            payload["exit_code"] = self.exit_code
        if self.duration_bucket is not None:
            payload["duration_bucket"] = self.duration_bucket
        payload["stdout_byte_count"] = len(self.stdout)
        payload["stderr_byte_count"] = len(self.stderr)
        payload["stdout_truncated"] = self.stdout_truncated
        payload["stderr_truncated"] = self.stderr_truncated
        if self.accounting is not None:
            payload.update(
                {
                    "job_accounting_passed": self.accounting.job_accounting_passed,
                    "job_total_processes": self.accounting.job_total_processes,
                    "job_active_processes": self.accounting.job_active_processes,
                    "job_terminated_processes": self.accounting.job_terminated_processes,
                    "direct_child_reaped": self.accounting.direct_child_reaped,
                    "containment_closed": self.accounting.containment_closed,
                }
            )
        return payload


def _finding(rule_id: str, message: str, *, blocked: bool = False) -> Finding:
    return Finding(
        rule_id,
        "block" if blocked else "error",
        "blocked" if blocked else "error",
        message,
    )


def _duration_bucket(elapsed: float) -> str:
    if elapsed < 1:
        return "lt-1s"
    if elapsed < 5:
        return "1-5s"
    if elapsed < 10:
        return "5-10s"
    return "10-30s"


def _read_bounded(
    stream: BinaryIO | None,
    target: bytearray,
    overflow: threading.Event,
) -> None:
    if stream is None:
        return
    try:
        while not overflow.is_set():
            chunk = stream.read(8_192)
            if not chunk:
                return
            if len(target) + len(chunk) > _MAX_STREAM_BYTES:
                target.clear()
                overflow.set()
                return
            target.extend(chunk)
    except OSError:
        overflow.set()


def _wait_quietly(process: ProcessLike, timeout: float | None = None) -> bool:
    try:
        process.wait(timeout=timeout)
        return True
    except (OSError, TimeoutError, subprocess.TimeoutExpired):
        return False


def _stop_tree(
    backend: ProcessBackend,
    job: object,
    process: ProcessLike,
) -> bool:
    try:
        backend.terminate_tree(job, process)
    except OSError:
        pass
    reaped = _wait_quietly(process, _TERMINATE_GRACE_SECONDS)
    if not reaped:
        try:
            backend.kill_tree(job, process)
        except OSError:
            pass
        reaped = _wait_quietly(process, _TERMINATE_GRACE_SECONDS)
    return reaped


def _stop_process(backend: ProcessBackend, process: ProcessLike) -> bool:
    try:
        backend.terminate_process(process)
    except OSError:
        pass
    reaped = _wait_quietly(process, _TERMINATE_GRACE_SECONDS)
    if not reaped:
        try:
            backend.kill_process(process)
        except OSError:
            pass
        reaped = _wait_quietly(process, _TERMINATE_GRACE_SECONDS)
    return reaped


def _valid_accounting(value: JobCounters) -> bool:
    counts = (
        value.job_total_processes,
        value.job_active_processes,
        value.job_terminated_processes,
    )
    return (
        all(type(count) is int and count >= 0 for count in counts)
        and value.job_terminated_processes <= value.job_total_processes
        and value.job_active_processes <= value.job_total_processes
        and value.job_active_processes + value.job_terminated_processes
        <= value.job_total_processes
    )


def run_fixed_git_status_process(
    identity: ExecutableIdentity,
    root: Path,
    environment: dict[str, str],
    *,
    timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
    backend: ProcessBackend | None = None,
) -> FixedProcessResult:
    """Run the internally owned Git status argv with bounded process-tree I/O."""
    active_backend = backend or (
        WindowsProcessBackend() if os.name == "nt" else UnsupportedProcessBackend()
    )
    if active_backend.platform != "windows":
        return FixedProcessResult(
            status="error",
            findings=[
                _finding(
                    "execution.process-platform-unavailable",
                    "Strong process-tree containment is unavailable on this platform.",
                )
            ],
            next_action="Use a platform with a completed fixed-runner implementation.",
        )
    if timeout_seconds <= 0 or timeout_seconds > _MAX_TIMEOUT_SECONDS:
        return FixedProcessResult(
            status="validation_failed",
            findings=[
                Finding(
                    "execution.process-timeout-invalid",
                    "error",
                    "validation_failed",
                    "The fixed process timeout is outside the allowed range.",
                )
            ],
        )
    argv = [
        str(identity.canonical_path),
        "status",
        "--short",
        "--branch",
    ]
    job: object | None = None
    process: ProcessLike | None = None
    started = time.monotonic()
    stdout = bytearray()
    stderr = bytearray()
    overflow = threading.Event()
    readers: list[threading.Thread] = []
    assigned = False
    direct_child_reaped = False

    def finish(result: FixedProcessResult) -> FixedProcessResult:
        nonlocal job, direct_child_reaped
        if job is None:
            return result
        if assigned and process is not None:
            if not direct_child_reaped:
                direct_child_reaped = _stop_tree(active_backend, job, process)
            for reader in readers:
                reader.join(_TERMINATE_GRACE_SECONDS)
            readers_alive = any(reader.is_alive() for reader in readers)
        else:
            if process is not None and not direct_child_reaped:
                direct_child_reaped = _stop_process(active_backend, process)
            for reader in readers:
                reader.join(_TERMINATE_GRACE_SECONDS)
            readers_alive = any(reader.is_alive() for reader in readers)
        if assigned and process is not None:
            accounting: JobCounters | None = None
            try:
                accounting = active_backend.query_job_accounting(job)
                if not _valid_accounting(accounting):
                    raise ValueError("invalid job accounting")
                if accounting.job_active_processes:
                    direct_child_reaped = _stop_tree(active_backend, job, process)
                    for reader in readers:
                        reader.join(_TERMINATE_GRACE_SECONDS)
                    readers_alive = any(reader.is_alive() for reader in readers)
                    accounting = active_backend.query_job_accounting(job)
                    if not _valid_accounting(accounting):
                        raise ValueError("invalid job accounting")
                if (
                    accounting.job_active_processes != 0
                    or not direct_child_reaped
                    or readers_alive
                ):
                    raise RuntimeError("job containment remained active")
                result.accounting = JobAccounting(
                    job_accounting_passed=True,
                    job_total_processes=accounting.job_total_processes,
                    job_active_processes=accounting.job_active_processes,
                    job_terminated_processes=accounting.job_terminated_processes,
                    direct_child_reaped=direct_child_reaped,
                    containment_closed=False,
                )
            except (OSError, RuntimeError, ValueError):
                if result.status == "pass":
                    result.status = "error"
                    result.findings = [
                        _finding(
                            "execution.process-accounting-failed",
                            "The fixed process containment accounting could not be validated.",
                        )
                    ]
                result.stdout = b""
                result.stderr = b""
                result.next_action = "Inspect process containment before retrying."
        elif assigned:
            if result.status == "pass":
                result.status = "error"
                result.findings = [
                    _finding(
                        "execution.process-accounting-failed",
                        "The fixed process containment accounting could not be validated.",
                    )
                ]
            result.stdout = b""
            result.stderr = b""
        try:
            active_backend.close_job(job)
        except OSError:
            result.status = "error"
            result.findings = [
                _finding(
                    "execution.process-cleanup-failed",
                    "The fixed process containment handle could not be safely closed.",
                )
            ]
            result.stdout = b""
            result.stderr = b""
            result.next_action = "Inspect process containment before retrying."
        else:
            if result.accounting is not None:
                result.accounting.containment_closed = True
        finally:
            job = None
        return result

    try:
        job = active_backend.create_job()
        process = active_backend.spawn(
            argv,
            cwd=root,
            environment=dict(environment),
        )
        active_backend.assign(job, process)
        assigned = True
        if not active_backend.verify_image(process, identity):
            return finish(FixedProcessResult(
                status="error",
                findings=[
                    _finding(
                        "execution.process-image-mismatch",
                        "The spawned process image does not match the trusted executable.",
                    )
                ],
                duration_bucket=_duration_bucket(time.monotonic() - started),
                next_action="Review and rotate the executable trust binding.",
            ))
        active_backend.resume(process)
        readers = [
            threading.Thread(
                target=_read_bounded,
                args=(process.stdout, stdout, overflow),
                daemon=True,
            ),
            threading.Thread(
                target=_read_bounded,
                args=(process.stderr, stderr, overflow),
                daemon=True,
            ),
        ]
        for reader in readers:
            reader.start()
        deadline = started + timeout_seconds
        while process.poll() is None and not overflow.is_set():
            if time.monotonic() >= deadline:
                stdout.clear()
                stderr.clear()
                return finish(FixedProcessResult(
                    status="error",
                    findings=[
                        _finding(
                            "execution.process-timeout",
                            "The fixed Git status process exceeded its timeout.",
                        )
                    ],
                    duration_bucket=_duration_bucket(time.monotonic() - started),
                    next_action="Inspect repository scale and retry explicitly.",
                ))
            time.sleep(0.01)
        if overflow.is_set():
            stdout.clear()
            stderr.clear()
            return finish(FixedProcessResult(
                status="blocked",
                findings=[
                    _finding(
                        "execution.output-too-large",
                        "Fixed Git status output exceeded the bounded stream limit.",
                        blocked=True,
                    )
                ],
                duration_bucket=_duration_bucket(time.monotonic() - started),
                stdout_truncated=True,
                stderr_truncated=True,
                next_action="Reduce repository status output before retrying.",
            ))
        exit_code = process.wait(timeout=_TERMINATE_GRACE_SECONDS)
        direct_child_reaped = True
        if overflow.is_set():
            stdout.clear()
            stderr.clear()
            return finish(FixedProcessResult(
                status="blocked",
                findings=[
                    _finding(
                        "execution.output-too-large",
                        "Fixed Git status output exceeded the bounded stream limit.",
                        blocked=True,
                    )
                ],
                duration_bucket=_duration_bucket(time.monotonic() - started),
                stdout_truncated=True,
                stderr_truncated=True,
                next_action="Reduce repository status output before retrying.",
            ))
        if any(reader.is_alive() for reader in readers):
            stdout.clear()
            stderr.clear()
            return finish(FixedProcessResult(
                status="error",
                findings=[
                    _finding(
                        "execution.process-stream-close-failed",
                        "Fixed process streams did not close after child exit.",
                    )
                ],
                duration_bucket=_duration_bucket(time.monotonic() - started),
            ))
        return finish(FixedProcessResult(
            status="pass",
            exit_code=exit_code,
            stdout=bytes(stdout),
            stderr=bytes(stderr),
            duration_bucket=_duration_bucket(time.monotonic() - started),
            next_action="Validate the bounded output protocol before release.",
        ))
    except KeyboardInterrupt:
        return finish(FixedProcessResult(
            status="blocked",
            findings=[
                _finding(
                    "execution.process-cancelled",
                    "The fixed Git status process was cancelled.",
                    blocked=True,
                )
            ],
            duration_bucket=_duration_bucket(time.monotonic() - started),
        ))
    except Exception:
        return finish(FixedProcessResult(
            status="error",
            findings=[
                _finding(
                    "execution.process-start-failed",
                    "The fixed Git status process could not be safely started.",
                )
            ],
            duration_bucket=_duration_bucket(time.monotonic() - started),
        ))
    finally:
        if job is not None:
            finish(FixedProcessResult(
                status="error",
                findings=[
                    _finding(
                        "execution.process-cleanup-failed",
                        "The fixed process containment handle could not be safely closed.",
                    )
                ],
            ))


class UnsupportedProcessBackend:
    platform = "unavailable"


class WindowsProcessBackend:
    """Windows suspended process + Job Object implementation."""

    platform = "windows"

    def __init__(self) -> None:
        self.kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    def create_job(self) -> object:
        class LargeInteger(ctypes.Structure):
            _fields_ = [("QuadPart", ctypes.c_longlong)]

        class BasicLimit(ctypes.Structure):
            _fields_ = [
                ("PerProcessUserTimeLimit", LargeInteger),
                ("PerJobUserTimeLimit", LargeInteger),
                ("LimitFlags", wintypes.DWORD),
                ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t),
                ("ActiveProcessLimit", wintypes.DWORD),
                ("Affinity", ctypes.c_size_t),
                ("PriorityClass", wintypes.DWORD),
                ("SchedulingClass", wintypes.DWORD),
            ]

        class IoCounters(ctypes.Structure):
            _fields_ = [
                ("ReadOperationCount", ctypes.c_ulonglong),
                ("WriteOperationCount", ctypes.c_ulonglong),
                ("OtherOperationCount", ctypes.c_ulonglong),
                ("ReadTransferCount", ctypes.c_ulonglong),
                ("WriteTransferCount", ctypes.c_ulonglong),
                ("OtherTransferCount", ctypes.c_ulonglong),
            ]

        class ExtendedLimit(ctypes.Structure):
            _fields_ = [
                ("BasicLimitInformation", BasicLimit),
                ("IoInfo", IoCounters),
                ("ProcessMemoryLimit", ctypes.c_size_t),
                ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t),
                ("PeakJobMemoryUsed", ctypes.c_size_t),
            ]

        self.kernel32.CreateJobObjectW.restype = wintypes.HANDLE
        handle = self.kernel32.CreateJobObjectW(None, None)
        if not handle:
            raise OSError("job creation failed")
        limits = ExtendedLimit()
        limits.BasicLimitInformation.LimitFlags = 0x00002000
        if not self.kernel32.SetInformationJobObject(
            handle,
            9,
            ctypes.byref(limits),
            ctypes.sizeof(limits),
        ):
            self.kernel32.CloseHandle(handle)
            raise OSError("job configuration failed")
        return int(handle)

    def spawn(
        self,
        argv: list[str],
        *,
        cwd: Path,
        environment: dict[str, str],
    ) -> subprocess.Popen[bytes]:
        return subprocess.Popen(
            argv,
            cwd=str(cwd),
            env=environment,
            shell=False,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=0x00000004 | 0x08000000,
            bufsize=0,
        )

    def assign(self, job: object, process: ProcessLike) -> None:
        handle = getattr(process, "_handle", None)
        if handle is None or not self.kernel32.AssignProcessToJobObject(
            wintypes.HANDLE(int(job)), wintypes.HANDLE(int(handle))
        ):
            raise OSError("job assignment failed")

    def verify_image(
        self, process: ProcessLike, identity: ExecutableIdentity
    ) -> bool:
        process_handle = getattr(process, "_handle", None)
        if process_handle is None or identity.native_handle is None:
            return False
        size = wintypes.DWORD(32_768)
        buffer = ctypes.create_unicode_buffer(size.value)
        if not self.kernel32.QueryFullProcessImageNameW(
            wintypes.HANDLE(int(process_handle)),
            0,
            buffer,
            ctypes.byref(size),
        ):
            return False
        actual_path = Path(buffer.value).resolve(strict=True)
        if os.path.normcase(str(actual_path)) != os.path.normcase(
            str(identity.canonical_path)
        ):
            return False
        actual_handle = WindowsTrustBackend._open_locked(actual_path)
        try:
            actual_file_identity, actual_digest = (
                WindowsTrustBackend._handle_identity_and_digest(actual_handle)
            )
        finally:
            self.kernel32.CloseHandle(wintypes.HANDLE(actual_handle))
        return (
            actual_file_identity == identity.file_identity
            and actual_digest == identity.sha256
        )

    @staticmethod
    def resume(process: ProcessLike) -> None:
        handle = getattr(process, "_handle", None)
        if handle is None:
            raise OSError("process handle unavailable")
        ntdll = ctypes.WinDLL("ntdll", use_last_error=True)
        status = ntdll.NtResumeProcess(wintypes.HANDLE(int(handle)))
        if status != 0:
            raise OSError("process resume failed")

    def terminate_tree(self, job: object, process: ProcessLike) -> None:
        if not self.kernel32.TerminateJobObject(
            wintypes.HANDLE(int(job)), 0xE0000001
        ):
            raise OSError("job terminate failed")

    def kill_tree(self, job: object, process: ProcessLike) -> None:
        if not self.kernel32.TerminateJobObject(
            wintypes.HANDLE(int(job)), 0xE0000002
        ):
            raise OSError("job kill failed")

    @staticmethod
    def terminate_process(process: ProcessLike) -> None:
        terminate = getattr(process, "terminate", None)
        if not callable(terminate):
            raise OSError("direct process termination unavailable")
        terminate()

    @staticmethod
    def kill_process(process: ProcessLike) -> None:
        kill = getattr(process, "kill", None)
        if not callable(kill):
            raise OSError("direct process kill unavailable")
        kill()

    def close_job(self, job: object) -> None:
        if not self.kernel32.CloseHandle(wintypes.HANDLE(int(job))):
            raise OSError("job close failed")

    def query_job_accounting(self, job: object) -> JobCounters:
        class BasicAccounting(ctypes.Structure):
            _fields_ = [
                ("TotalUserTime", ctypes.c_longlong),
                ("TotalKernelTime", ctypes.c_longlong),
                ("ThisPeriodTotalUserTime", ctypes.c_longlong),
                ("ThisPeriodTotalKernelTime", ctypes.c_longlong),
                ("TotalPageFaultCount", wintypes.DWORD),
                ("TotalProcesses", wintypes.DWORD),
                ("ActiveProcesses", wintypes.DWORD),
                ("TotalTerminatedProcesses", wintypes.DWORD),
            ]

        info = BasicAccounting()
        if not self.kernel32.QueryInformationJobObject(
            wintypes.HANDLE(int(job)),
            1,
            ctypes.byref(info),
            ctypes.sizeof(info),
            None,
        ):
            raise OSError("job accounting query failed")
        return JobCounters(
            job_total_processes=int(info.TotalProcesses),
            job_active_processes=int(info.ActiveProcesses),
            job_terminated_processes=int(info.TotalTerminatedProcesses),
        )
