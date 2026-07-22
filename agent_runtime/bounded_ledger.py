"""Bounded, identity-bound JSONL snapshots for execution audit validation."""

from __future__ import annotations

import json
import hashlib
import math
import os
from dataclasses import dataclass
from pathlib import Path
import stat
from typing import Any, BinaryIO

from .result import CheckResult, Finding


MAX_LEDGER_BYTES = 16 * 1024 * 1024
MAX_PHYSICAL_LINES = 50_000
MAX_PHYSICAL_LINE_BYTES = 64 * 1024
MAX_JSON_DEPTH = 32
_FILE_ATTRIBUTE_REPARSE_POINT = 0x400


class _DuplicateKeyError(ValueError):
    pass


def _reject_constant(_value: str) -> None:
    raise ValueError("non-finite JSON constant")


def _parse_finite_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError("non-finite JSON number")
    return parsed


@dataclass(frozen=True)
class BoundedLedgerSnapshot:
    """Complete validated records bound to one stable ledger identity."""

    records: tuple[dict[str, Any], ...]
    identity: tuple[int, int]
    byte_count: int
    physical_line_count: int
    record_count: int
    content_digest: str


class BoundedLedgerSession:
    """One locked descriptor and its current complete bounded snapshot."""

    def __init__(
        self,
        path: Path,
        handle: BinaryIO,
        *,
        exclusive: bool,
        unlock: Any,
    ) -> None:
        self.path = path
        self.handle = handle
        self.exclusive = exclusive
        self._unlock = unlock
        self._closed = False
        self.snapshot: BoundedLedgerSnapshot | CheckResult = self.refresh()

    def refresh(self) -> BoundedLedgerSnapshot | CheckResult:
        self.snapshot = _snapshot_handle(self.path, self.handle)
        return self.snapshot

    def verify_current(self) -> CheckResult:
        if not isinstance(self.snapshot, BoundedLedgerSnapshot):
            return self.snapshot
        try:
            return _final_verify_snapshot(self.path, self.handle, self.snapshot)
        except BaseException:  # Final verification must remain structured.
            return _failure(
                "bounded-ledger-final-verification-failed",
                "Execution audit ledger final verification could not complete.",
            )

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            self._unlock()
        finally:
            self.handle.close()

    def __enter__(self) -> BoundedLedgerSession:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


def _failure(rule_id: str, message: str, *, line: int | None = None) -> CheckResult:
    return CheckResult(
        status="validation_failed",
        findings=[
            Finding(
                rule_id=rule_id,
                severity="error",
                action="error",
                message=message,
                line=line,
            )
        ],
        next_action="Repair or compact the ledger before execution audit validation.",
    )


def _identity(stat_result: os.stat_result) -> tuple[int, int]:
    return stat_result.st_dev, stat_result.st_ino


def _version(stat_result: os.stat_result) -> tuple[int, int, int]:
    return (
        stat_result.st_size,
        stat_result.st_mtime_ns,
        stat_result.st_ctime_ns,
    )


def _is_safe_identity(stat_result: os.stat_result) -> bool:
    attributes = getattr(stat_result, "st_file_attributes", 0)
    return (
        stat.S_ISREG(stat_result.st_mode)
        and stat_result.st_nlink == 1
        and attributes & _FILE_ATTRIBUTE_REPARSE_POINT == 0
    )


def _path_identity(path: Path) -> tuple[int, int]:
    stat_result = path.lstat()
    if not _is_safe_identity(stat_result):
        raise OSError("unsafe ledger identity")
    return _identity(stat_result)


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateKeyError
        result[key] = value
    return result


def _json_depth(value: object) -> int:
    maximum = 0
    stack: list[tuple[object, int]] = [(value, 0)]
    while stack:
        current, depth = stack.pop()
        if isinstance(current, dict):
            maximum = max(maximum, depth)
            stack.extend((item, depth + 1) for item in current.values())
        elif isinstance(current, list):
            maximum = max(maximum, depth)
            stack.extend((item, depth + 1) for item in current)
    return maximum


def _contains_nonfinite_float(value: object) -> bool:
    stack = [value]
    while stack:
        current = stack.pop()
        if isinstance(current, float) and not math.isfinite(current):
            return True
        if isinstance(current, dict):
            stack.extend(current.values())
        elif isinstance(current, list):
            stack.extend(current)
    return False


def _digest_handle(handle: Any) -> str:
    digest = hashlib.sha256()
    handle.seek(0)
    remaining = MAX_LEDGER_BYTES + 1
    while remaining:
        chunk = handle.read(min(64 * 1024, remaining))
        if not chunk:
            break
        digest.update(chunk)
        remaining -= len(chunk)
    return digest.hexdigest()


def _open_windows_handle(path: Path, *, exclusive: bool) -> BinaryIO:
    import ctypes
    import msvcrt
    from ctypes import wintypes

    create_file = ctypes.windll.kernel32.CreateFileW
    create_file.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    create_file.restype = wintypes.HANDLE
    access = 0x80000000 | (0x40000000 if exclusive else 0)
    # Readers and the writer deny write/delete sharing for the full session.
    native = create_file(str(path), access, 0x00000001, None, 3, 0x80, None)
    if native == wintypes.HANDLE(-1).value:
        raise OSError(ctypes.get_last_error(), "ledger open failed")
    flags = os.O_BINARY | (os.O_RDWR if exclusive else os.O_RDONLY)
    try:
        fd = msvcrt.open_osfhandle(native, flags)
    except Exception:
        ctypes.windll.kernel32.CloseHandle(native)
        raise
    return os.fdopen(fd, "r+b" if exclusive else "rb")


def _lock_handle(
    handle: BinaryIO, *, exclusive: bool, blocking: bool
) -> Any:
    if os.name == "nt":
        import ctypes
        import msvcrt
        from ctypes import wintypes

        class OVERLAPPED(ctypes.Structure):
            _fields_ = [
                ("Internal", ctypes.c_void_p),
                ("InternalHigh", ctypes.c_void_p),
                ("Offset", wintypes.DWORD),
                ("OffsetHigh", wintypes.DWORD),
                ("hEvent", wintypes.HANDLE),
            ]

        overlapped = OVERLAPPED()
        flags = (0x00000002 if exclusive else 0) | (
            0 if blocking else 0x00000001
        )
        native = msvcrt.get_osfhandle(handle.fileno())
        if not ctypes.windll.kernel32.LockFileEx(
            native, flags, 0, 1, 0, ctypes.byref(overlapped)
        ):
            raise BlockingIOError("ledger lock unavailable")

        def _unlock() -> None:
            ctypes.windll.kernel32.UnlockFileEx(
                native, 0, 1, 0, ctypes.byref(overlapped)
            )

        return _unlock
    import fcntl

    operation = fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH
    if not blocking:
        operation |= fcntl.LOCK_NB
    fcntl.flock(handle.fileno(), operation)
    return lambda: fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def open_bounded_ledger_session(
    path: Path,
    *,
    exclusive: bool = False,
    blocking: bool = True,
) -> BoundedLedgerSession | CheckResult:
    """Open, lock, and snapshot one ledger for a complete consumer lifetime."""
    try:
        before = path.lstat()
    except OSError:
        return _failure(
            "bounded-ledger-read-failed", "Execution audit ledger could not be inspected."
        )
    if not _is_safe_identity(before):
        return _failure(
            "bounded-ledger-unsafe-identity",
            "Execution audit ledger must be regular, non-reparse, and single-link.",
        )
    try:
        handle = (
            _open_windows_handle(path, exclusive=exclusive)
            if os.name == "nt"
            else path.open("r+b" if exclusive else "rb")
        )
        try:
            unlock = _lock_handle(
                handle, exclusive=exclusive, blocking=blocking
            )
        except (OSError, BlockingIOError):
            handle.close()
            return CheckResult(
                status="blocked",
                findings=[
                    Finding(
                        rule_id="bounded-ledger-lock-unavailable",
                        severity="block",
                        action="deny",
                        message="Execution audit ledger lock is unavailable.",
                    )
                ],
                next_action="Retry after the current ledger consumer finishes.",
            )
    except OSError:
        return CheckResult(
            status="blocked",
            findings=[
                Finding(
                    rule_id="bounded-ledger-lock-unavailable",
                    severity="block",
                    action="deny",
                    message="Execution audit ledger lock is unavailable.",
                )
            ],
            next_action="Retry after the current ledger consumer finishes.",
        )
    try:
        session = BoundedLedgerSession(
            path, handle, exclusive=exclusive, unlock=unlock
        )
    except BaseException:
        try:
            unlock()
        finally:
            handle.close()
        raise
    if isinstance(session.snapshot, CheckResult):
        failure = session.snapshot
        session.close()
        return failure
    return session


def _snapshot_handle(
    path: Path, handle: BinaryIO
) -> BoundedLedgerSnapshot | CheckResult:
    try:
        before = path.lstat()
    except OSError:
        return _failure(
            "bounded-ledger-read-failed", "Execution audit ledger could not be inspected."
        )
    if not _is_safe_identity(before):
        return _failure(
            "bounded-ledger-unsafe-identity",
            "Execution audit ledger must be regular, non-reparse, and single-link.",
        )
    if before.st_size > MAX_LEDGER_BYTES:
        return _failure(
            "bounded-ledger-file-too-large", "Execution audit ledger exceeds its byte limit."
        )
    expected_identity = _identity(before)
    records: list[dict[str, Any]] = []
    physical_lines = 0
    byte_count = 0
    content_digest = hashlib.sha256()
    try:
        opened = os.fstat(handle.fileno())
        if not _is_safe_identity(opened) or _identity(opened) != expected_identity:
            return _failure(
                "bounded-ledger-identity-drift",
                "Execution audit ledger identity changed during snapshot.",
            )
        handle.seek(0)
        while True:
                raw_line = handle.readline(MAX_PHYSICAL_LINE_BYTES + 1)
                if not raw_line:
                    break
                physical_lines += 1
                byte_count += len(raw_line)
                content_digest.update(raw_line)
                if physical_lines > MAX_PHYSICAL_LINES:
                    return _failure(
                        "bounded-ledger-too-many-lines",
                        "Execution audit ledger exceeds its physical line limit.",
                    )
                if len(raw_line) > MAX_PHYSICAL_LINE_BYTES:
                    return _failure(
                        "bounded-ledger-line-too-large",
                        "Execution audit ledger contains an oversized physical line.",
                        line=physical_lines,
                    )
                if byte_count > MAX_LEDGER_BYTES:
                    return _failure(
                        "bounded-ledger-file-too-large",
                        "Execution audit ledger exceeds its byte limit.",
                    )
                try:
                    text = raw_line.decode("utf-8", errors="strict").strip()
                except UnicodeDecodeError:
                    return _failure(
                        "bounded-ledger-invalid-utf8",
                        "Execution audit ledger is not strict UTF-8.",
                        line=physical_lines,
                    )
                if not text:
                    continue
                try:
                    record = json.loads(
                        text,
                        object_pairs_hook=_reject_duplicate_keys,
                        parse_constant=_reject_constant,
                        parse_float=_parse_finite_float,
                    )
                except _DuplicateKeyError:
                    return _failure(
                        "bounded-ledger-duplicate-key",
                        "Execution audit ledger contains a duplicate JSON key.",
                        line=physical_lines,
                    )
                except (ValueError, RecursionError):
                    return _failure(
                        "bounded-ledger-invalid-json",
                        "Execution audit ledger contains invalid JSON.",
                        line=physical_lines,
                    )
                if not isinstance(record, dict):
                    return _failure(
                        "bounded-ledger-record-not-object",
                        "Execution audit ledger records must be JSON objects.",
                        line=physical_lines,
                    )
                if _contains_nonfinite_float(record):
                    return _failure(
                        "bounded-ledger-invalid-json",
                        "Execution audit ledger contains invalid JSON.",
                        line=physical_lines,
                    )
                if _json_depth(record) > MAX_JSON_DEPTH:
                    return _failure(
                        "bounded-ledger-json-too-deep",
                        "Execution audit ledger record exceeds its JSON depth limit.",
                        line=physical_lines,
                    )
                item = dict(record)
                item["_line_no"] = physical_lines
                records.append(item)
    except OSError:
        return _failure(
            "bounded-ledger-read-failed", "Execution audit ledger could not be read."
        )
    initial_digest = content_digest.hexdigest()
    candidate = BoundedLedgerSnapshot(
        records=tuple(records),
        identity=expected_identity,
        byte_count=byte_count,
        physical_line_count=physical_lines,
        record_count=len(records),
        content_digest=initial_digest,
    )
    try:
        verified = _final_verify_snapshot(path, handle, candidate)
    except BaseException:  # Fault-injected verifiers must not escape.
        return _failure(
            "bounded-ledger-final-verification-failed",
            "Execution audit ledger final verification could not complete.",
        )
    if verified.status != "pass":
        return verified
    return candidate


def _final_verify_snapshot(
    path: Path, handle: BinaryIO, snapshot: BoundedLedgerSnapshot
) -> CheckResult:
    """Perform the final same-handle/path identity, size, and content check."""
    try:
        handle_stat = os.fstat(handle.fileno())
        path_identity = _path_identity(path)
        if (
            not _is_safe_identity(handle_stat)
            or _identity(handle_stat) != snapshot.identity
            or path_identity != snapshot.identity
            or handle_stat.st_size != snapshot.byte_count
        ):
            return _failure(
                "bounded-ledger-identity-drift",
                "Execution audit ledger identity changed during final verification.",
            )
        version_before_digest = _version(handle_stat)
        if _digest_handle(handle) != snapshot.content_digest:
            return _failure(
                "bounded-ledger-content-drift",
                "Execution audit ledger content changed during final verification.",
            )
        final_stat = os.fstat(handle.fileno())
        if (
            not _is_safe_identity(final_stat)
            or _identity(final_stat) != snapshot.identity
            or _path_identity(path) != snapshot.identity
            or final_stat.st_size != snapshot.byte_count
            or _version(final_stat) != version_before_digest
        ):
            return _failure(
                "bounded-ledger-identity-drift",
                "Execution audit ledger identity changed during final verification.",
            )
    except BaseException:
        return _failure(
            "bounded-ledger-final-verification-failed",
            "Execution audit ledger final verification could not complete.",
        )
    return CheckResult(
        status="pass", next_action="Bounded ledger snapshot remains current."
    )


def snapshot_jsonl(path: Path) -> BoundedLedgerSnapshot | CheckResult:
    """Compatibility wrapper returning a detached snapshot after lock release."""
    opened = open_bounded_ledger_session(path)
    if isinstance(opened, CheckResult):
        return opened
    with opened as session:
        return session.snapshot


def snapshot_matches_handle(snapshot: BoundedLedgerSnapshot, handle: Any) -> bool:
    """Confirm that an open descriptor still contains the accepted snapshot."""
    try:
        current = os.fstat(handle.fileno())
        return (
            _is_safe_identity(current)
            and _identity(current) == snapshot.identity
            and current.st_size == snapshot.byte_count
            and _digest_handle(handle) == snapshot.content_digest
        )
    except OSError:
        return False


def snapshot_prefix_matches_handle(
    snapshot: BoundedLedgerSnapshot, handle: Any
) -> bool:
    """Confirm that an open descriptor retains the snapshot as its exact prefix."""
    try:
        digest = hashlib.sha256()
        handle.seek(0)
        remaining = snapshot.byte_count
        while remaining:
            chunk = handle.read(min(64 * 1024, remaining))
            if not chunk:
                return False
            digest.update(chunk)
            remaining -= len(chunk)
        return digest.hexdigest() == snapshot.content_digest
    except OSError:
        return False
