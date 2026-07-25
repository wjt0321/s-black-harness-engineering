"""Bounded Windows process-tree runner for the fixed Pi dry-run print argv (Stage 62).

Reuses the Stage 49 Job Object containment machinery but drops the executable
trust-image verification: the Pi entry point is an npm shim (``pi.cmd`` ->
``node .../cli.js``), not a single bindable executable. The trust gap is
declared explicitly in ``docs/110-pi-controlled-dry-run-adapter-contract.md``;
everything else (suspended spawn, KILL_ON_JOB_CLOSE job, bounded streams,
timeout, tree terminate/kill, no-orphan accounting) stays identical in shape.

POSIX remains unavailable; there is no degraded fallback.
"""

from __future__ import annotations

import os
import subprocess
import threading
import time
from pathlib import Path

from .fixed_process_runner import (
    FixedProcessResult,
    JobAccounting,
    JobCounters,
    ProcessBackend,
    ProcessLike,
    UnsupportedProcessBackend,
    WindowsProcessBackend,
    _stop_process,
    _stop_tree,
    _valid_accounting,
)
from .result import Finding

_MAX_STREAM_BYTES = 262_144
_DEFAULT_TIMEOUT_SECONDS = 60.0
_MIN_TIMEOUT_SECONDS = 5.0
_MAX_TIMEOUT_SECONDS = 120.0
_TERMINATE_GRACE_SECONDS = 1.0


def _duration_bucket(elapsed: float) -> str:
    if elapsed < 5:
        return "lt-5s"
    if elapsed < 15:
        return "5-15s"
    if elapsed < 60:
        return "15-60s"
    return "60-120s"


def _finding(rule_id: str, message: str, *, blocked: bool = False) -> Finding:
    return Finding(
        rule_id,
        "block" if blocked else "error",
        "blocked" if blocked else "error",
        message,
    )


def _read_bounded(
    stream: object,
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


def run_fixed_pi_print_process(
    argv: list[str],
    root: Path,
    environment: dict[str, str],
    *,
    timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
    backend: ProcessBackend | None = None,
) -> FixedProcessResult:
    """Run the internally owned fixed Pi print argv with bounded process-tree I/O."""
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
    if (
        timeout_seconds < _MIN_TIMEOUT_SECONDS
        or timeout_seconds > _MAX_TIMEOUT_SECONDS
    ):
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
                            "The fixed Pi print process exceeded its timeout.",
                        )
                    ],
                    duration_bucket=_duration_bucket(time.monotonic() - started),
                    next_action="Inspect model latency and retry explicitly.",
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
                        "Fixed Pi print output exceeded the bounded stream limit.",
                        blocked=True,
                    )
                ],
                duration_bucket=_duration_bucket(time.monotonic() - started),
                stdout_truncated=True,
                stderr_truncated=True,
                next_action="Reduce the expected model output before retrying.",
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
                        "Fixed Pi print output exceeded the bounded stream limit.",
                        blocked=True,
                    )
                ],
                duration_bucket=_duration_bucket(time.monotonic() - started),
                stdout_truncated=True,
                stderr_truncated=True,
                next_action="Reduce the expected model output before retrying.",
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
                    "The fixed Pi print process was cancelled.",
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
                    "The fixed Pi print process could not be safely started.",
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
