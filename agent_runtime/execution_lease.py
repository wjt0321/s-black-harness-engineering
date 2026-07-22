"""Machine-local single-flight lease for state-changing fixed execution."""

from __future__ import annotations

import ctypes
import os
import stat
import threading
import weakref
from contextlib import contextmanager
from ctypes import wintypes
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from .result import CheckResult, Finding

_LEASE_NAME = "execution-lease-v1.lock"
_REPARSE_POINT = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)


class LeaseBackend(Protocol):
    def ensure_parent(self, path: Path) -> None: ...

    def open(self, path: Path, *, create: bool, inspect: bool = False) -> int: ...

    def lock(self, handle: int) -> bool: ...

    def inspect_state(self, path: Path, handle: int | None = None) -> str: ...

    def unlock(self, handle: int) -> None: ...

    def close(self, handle: int) -> None: ...

    def stat(self, handle: int) -> os.stat_result: ...

    def permissions_are_minimal(self, path: Path, handle: int) -> bool: ...


class _LeaseBusyError(OSError):
    pass


class _LeaseCapability:
    __slots__ = ("_lease",)

    def __init__(self, lease: ExecutionLeaseResult) -> None:
        self._lease = lease


@dataclass(eq=False)
class ExecutionLeaseResult(CheckResult):
    __hash__ = object.__hash__
    __eq__ = object.__eq__

    lease_state: str = "unavailable"

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        payload["lease_state"] = self.lease_state
        return payload

    def validate(self) -> bool:
        return _validate_registered_lease(self)

    def release(self) -> CheckResult:
        return _release_registered_lease(self)


@dataclass
class _LeaseState:
    handle: int
    backend: LeaseBackend
    path: Path
    root: Path
    locked_active: bool = True
    unlock_done: bool = False
    close_done: bool = False
    cleanup_lock: threading.Lock = field(default_factory=threading.Lock)
    finalizer: weakref.finalize | None = None


_LEASE_REGISTRY: weakref.WeakKeyDictionary[ExecutionLeaseResult, _LeaseState] = (
    weakref.WeakKeyDictionary()
)
_LEASE_REGISTRY_LOCK = threading.RLock()
_PENDING_CLEANUPS: dict[int, _LeaseState] = {}


def default_execution_lease_path() -> Path:
    """Resolve the fixed production lease path without environment input."""
    if os.name != "nt":
        import pwd

        base = Path(pwd.getpwuid(os.getuid()).pw_dir) / ".config"
    else:
        folder_id = ctypes.c_byte * 16
        guid = folder_id.from_buffer_copy(
            bytes.fromhex("8527b3f1ba6fcf4f9d557b8e7f157091")
        )
        value = ctypes.c_wchar_p()
        shell32 = ctypes.WinDLL("shell32", use_last_error=True)
        ole32 = ctypes.WinDLL("ole32", use_last_error=True)
        result = shell32.SHGetKnownFolderPath(
            ctypes.byref(guid), 0, None, ctypes.byref(value)
        )
        if result != 0 or not value.value:
            raise OSError("known folder unavailable")
        try:
            base = Path(value.value)
        finally:
            ole32.CoTaskMemFree(value)
    return base / "agent-runtime" / _LEASE_NAME


def _finding(rule_id: str, message: str, *, blocked: bool = False) -> Finding:
    return Finding(
        rule_id,
        "block" if blocked else "error",
        "blocked" if blocked else "error",
        message,
    )


def _validate_location(path: Path, root: Path, *, allow_missing: bool) -> Path:
    target = Path(os.path.abspath(path))
    project = root.resolve(strict=True)
    try:
        common = Path(os.path.commonpath([str(project), str(target)]))
    except ValueError:
        common = None
    family = target.parent
    if common == project or family == project or family in project.parents:
        raise ValueError("project-local lease")
    current = target.parent
    found_existing = False
    while True:
        try:
            info = current.lstat()
            found_existing = True
            if (
                not stat.S_ISDIR(info.st_mode)
                or stat.S_ISLNK(info.st_mode)
                or (getattr(info, "st_file_attributes", 0) or 0) & _REPARSE_POINT
            ):
                raise ValueError("unsafe lease parent")
        except FileNotFoundError:
            if not allow_missing:
                raise ValueError("lease parent unavailable")
        if current == current.parent:
            break
        current = current.parent
    if not found_existing:
        raise ValueError("lease parent unavailable")
    return target


def _safe_file(info: os.stat_result) -> bool:
    return bool(
        stat.S_ISREG(info.st_mode)
        and not stat.S_ISLNK(info.st_mode)
        and not (getattr(info, "st_file_attributes", 0) or 0) & _REPARSE_POINT
        and info.st_nlink == 1
        and info.st_size == 0
    )


def _same_identity(first: os.stat_result, second: os.stat_result) -> bool:
    return (int(first.st_dev), int(first.st_ino), int(first.st_nlink)) == (
        int(second.st_dev),
        int(second.st_ino),
        int(second.st_nlink),
    )


def _mutation_ace_flags_are_safe(ace_flags: int) -> bool:
    return ace_flags & 0x1F == 0


def _held_lease_capability(result: ExecutionLeaseResult) -> _LeaseCapability | None:
    if _validate_registered_lease(result):
        return _LeaseCapability(result)
    return None


def _validate_lease_capability(capability: object, root: Path | None = None) -> bool:
    if not isinstance(capability, _LeaseCapability):
        return False
    return _validate_registered_lease(capability._lease, root=root)


def _validate_registered_lease(
    result: ExecutionLeaseResult,
    *,
    root: Path | None = None,
) -> bool:
    with _LEASE_REGISTRY_LOCK:
        state = _LEASE_REGISTRY.get(result)
        if state is None or not state.locked_active:
            return False
        try:
            if root is not None and state.root != root.resolve(strict=True):
                return False
            handle_info = state.backend.stat(state.handle)
            path_info = state.path.lstat()
            return bool(
                _safe_file(handle_info)
                and _safe_file(path_info)
                and _same_identity(handle_info, path_info)
                and state.backend.permissions_are_minimal(state.path, state.handle)
            )
        except (OSError, RuntimeError, ValueError):
            return False


def _release_registered_lease(result: ExecutionLeaseResult) -> CheckResult:
    with _LEASE_REGISTRY_LOCK:
        state = _LEASE_REGISTRY.get(result)
        if state is None:
            return CheckResult(status="pass")
        state.locked_active = False
    cleanup_result = _cleanup_state(state)
    if state.close_done:
        with _LEASE_REGISTRY_LOCK:
            _LEASE_REGISTRY.pop(result, None)
    return cleanup_result


def _cleanup_state(state: _LeaseState) -> CheckResult:
    findings: list[Finding] = []
    fatal: BaseException | None = None
    with state.cleanup_lock:
        if not state.unlock_done:
            try:
                state.backend.unlock(state.handle)
                state.unlock_done = True
            except Exception:
                findings.append(
                    _finding(
                        "execution-lease-release-failed",
                        "The machine-local execution lease could not be unlocked.",
                    )
                )
            except BaseException as exc:
                fatal = exc
        if not state.close_done:
            try:
                state.backend.close(state.handle)
                state.close_done = True
            except Exception:
                findings.append(
                    _finding(
                        "execution-lease-release-failed",
                        "The machine-local execution lease handle could not be closed.",
                    )
                )
            except BaseException as exc:
                if fatal is None:
                    fatal = exc
        if state.close_done and state.finalizer is not None:
            state.finalizer.detach()
        if state.close_done:
            state.unlock_done = True
    if fatal is not None:
        with _LEASE_REGISTRY_LOCK:
            if state.close_done:
                _PENDING_CLEANUPS.pop(id(state), None)
            else:
                _PENDING_CLEANUPS[id(state)] = state
        raise fatal
    if findings:
        with _LEASE_REGISTRY_LOCK:
            if state.close_done:
                _PENDING_CLEANUPS.pop(id(state), None)
            else:
                _PENDING_CLEANUPS[id(state)] = state
        return CheckResult(
            status="error",
            findings=findings,
            next_action="Retry machine-local lease cleanup before another state-changing action.",
        )
    with _LEASE_REGISTRY_LOCK:
        _PENDING_CLEANUPS.pop(id(state), None)
    return CheckResult(status="pass")


def _finalize_lease_state(state: _LeaseState) -> None:
    state.locked_active = False
    _cleanup_state(state)


def _retry_pending_cleanups(path: Path) -> CheckResult:
    with _LEASE_REGISTRY_LOCK:
        pending = [
            state for state in _PENDING_CLEANUPS.values() if state.path == path
        ]
    findings: list[Finding] = []
    for state in pending:
        result = _cleanup_state(state)
        if result.status != "pass":
            findings.extend(result.findings)
    if findings:
        return CheckResult(
            status="error",
            findings=[
                _finding(
                    "execution-lease-cleanup-pending",
                    "Prior machine-local execution lease cleanup remains incomplete.",
                )
            ],
            next_action="Repair pending lease cleanup before acquiring another lease.",
        )
    return CheckResult(status="pass")


def _cleanup_unregistered_handle(
    *,
    backend: LeaseBackend,
    handle: int,
    path: Path,
    resolved_root: Path,
    locked: bool,
) -> CheckResult:
    state = _LeaseState(
        handle=handle,
        backend=backend,
        path=path,
        root=resolved_root,
        locked_active=False,
        unlock_done=not locked,
    )
    return _cleanup_state(state)


def _native_handle_for_test(result: ExecutionLeaseResult) -> int | None:
    with _LEASE_REGISTRY_LOCK:
        state = _LEASE_REGISTRY.get(result)
        return None if state is None else state.handle


class _PortableLeaseBackend:
    """Injectable unit-test backend with process-local nonblocking locking."""

    _guard = threading.Lock()
    _locked: set[tuple[int, int]] = set()

    def ensure_parent(self, path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True, mode=0o700)

    def open(self, path: Path, *, create: bool, inspect: bool = False) -> int:
        flags = os.O_RDONLY if inspect else os.O_RDWR
        flags |= getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
        if create:
            try:
                return os.open(path, flags | os.O_CREAT | os.O_EXCL, 0o600)
            except FileExistsError:
                pass
        return os.open(path, flags)

    def lock(self, handle: int) -> bool:
        info = os.fstat(handle)
        identity = (int(info.st_dev), int(info.st_ino))
        with self._guard:
            if identity in self._locked:
                return False
            self._locked.add(identity)
        return True

    def inspect_state(self, path: Path, handle: int | None = None) -> str:
        info = path.stat() if handle is None else os.fstat(handle)
        identity = (int(info.st_dev), int(info.st_ino))
        with self._guard:
            return "active" if identity in self._locked else "available"

    def unlock(self, handle: int) -> None:
        info = os.fstat(handle)
        with self._guard:
            self._locked.discard((int(info.st_dev), int(info.st_ino)))

    def close(self, handle: int) -> None:
        os.close(handle)

    def stat(self, handle: int) -> os.stat_result:
        return os.fstat(handle)

    def permissions_are_minimal(self, path: Path, handle: int) -> bool:
        return True


class _WindowsLeaseBackend:
    def __init__(self) -> None:
        if os.name != "nt":
            raise OSError("platform unavailable")
        self.kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    def ensure_parent(self, path: Path) -> None:
        try:
            path.lstat()
            return
        except FileNotFoundError:
            pass
        if not path.parent.is_dir():
            raise OSError("lease ancestor unavailable")
        with self._minimal_security_attributes() as security:
            self.kernel32.CreateDirectoryW.argtypes = [
                wintypes.LPCWSTR,
                ctypes.c_void_p,
            ]
            self.kernel32.CreateDirectoryW.restype = wintypes.BOOL
            if not self.kernel32.CreateDirectoryW(str(path), ctypes.byref(security)):
                if ctypes.get_last_error() not in {80, 183}:
                    raise OSError("lease parent creation failed")

    def open(self, path: Path, *, create: bool, inspect: bool = False) -> int:
        desired = 0x80000000 if inspect else 0x80000000 | 0x40000000
        share = 0x00000001 if not inspect else 0x00000001 | 0x00000002 | 0x00000004
        self.kernel32.CreateFileW.restype = wintypes.HANDLE
        if create:
            with self._minimal_security_attributes() as security:
                handle = self.kernel32.CreateFileW(
                    str(path),
                    desired,
                    share,
                    ctypes.byref(security),
                    1,
                    0x00200000,
                    None,
                )
        else:
            handle = self.kernel32.CreateFileW(
                str(path), desired, share, None, 3, 0x00200000, None
            )
        if create and handle == wintypes.HANDLE(-1).value and ctypes.get_last_error() in {80, 183}:
            handle = self.kernel32.CreateFileW(
                str(path), desired, share, None, 3, 0x00200000, None
            )
        if handle == wintypes.HANDLE(-1).value:
            if ctypes.get_last_error() in {32, 33}:
                raise _LeaseBusyError("lease handle is busy")
            raise OSError("lease handle unavailable")
        if not self.kernel32.SetHandleInformation(wintypes.HANDLE(handle), 1, 0):
            self.kernel32.CloseHandle(handle)
            raise OSError("lease inheritance control failed")
        return int(handle)

    @contextmanager
    def _minimal_security_attributes(self) -> Any:
        class SecurityAttributes(ctypes.Structure):
            _fields_ = [
                ("length", wintypes.DWORD),
                ("security_descriptor", ctypes.c_void_p),
                ("inherit_handle", wintypes.BOOL),
            ]

        descriptor = self._minimal_security_descriptor()
        attributes = SecurityAttributes(
            ctypes.sizeof(SecurityAttributes), descriptor, False
        )
        try:
            yield attributes
        finally:
            self.kernel32.LocalFree.argtypes = [ctypes.c_void_p]
            self.kernel32.LocalFree.restype = ctypes.c_void_p
            self.kernel32.LocalFree(descriptor)

    def _minimal_security_descriptor(self) -> ctypes.c_void_p:
        class SidAndAttributes(ctypes.Structure):
            _fields_ = [("sid", ctypes.c_void_p), ("attributes", wintypes.DWORD)]

        class TokenUser(ctypes.Structure):
            _fields_ = [("user", SidAndAttributes)]

        advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
        self.kernel32.GetCurrentProcess.restype = wintypes.HANDLE
        advapi32.OpenProcessToken.argtypes = [
            wintypes.HANDLE,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.HANDLE),
        ]
        advapi32.OpenProcessToken.restype = wintypes.BOOL
        advapi32.GetTokenInformation.argtypes = [
            wintypes.HANDLE,
            wintypes.DWORD,
            ctypes.c_void_p,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
        ]
        advapi32.GetTokenInformation.restype = wintypes.BOOL
        advapi32.ConvertSidToStringSidW.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_wchar_p),
        ]
        advapi32.ConvertSidToStringSidW.restype = wintypes.BOOL
        advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW.argtypes = [
            wintypes.LPCWSTR,
            wintypes.DWORD,
            ctypes.POINTER(ctypes.c_void_p),
            ctypes.POINTER(wintypes.DWORD),
        ]
        advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW.restype = wintypes.BOOL
        token = wintypes.HANDLE()
        sid_string = ctypes.c_wchar_p()
        descriptor = ctypes.c_void_p()
        try:
            if not advapi32.OpenProcessToken(
                self.kernel32.GetCurrentProcess(), 0x0008, ctypes.byref(token)
            ):
                raise OSError("actor token unavailable")
            needed = wintypes.DWORD()
            advapi32.GetTokenInformation(token, 1, None, 0, ctypes.byref(needed))
            token_buffer = ctypes.create_string_buffer(needed.value)
            if not advapi32.GetTokenInformation(
                token, 1, token_buffer, needed, ctypes.byref(needed)
            ):
                raise OSError("actor identity unavailable")
            actor_sid = ctypes.cast(
                token_buffer, ctypes.POINTER(TokenUser)
            ).contents.user.sid
            if not actor_sid or not advapi32.ConvertSidToStringSidW(
                actor_sid, ctypes.byref(sid_string)
            ):
                raise OSError("actor SID unavailable")
            sddl = (
                f"O:{sid_string.value}D:P"
                f"(A;;FA;;;{sid_string.value})(A;;FA;;;SY)(A;;FA;;;BA)"
            )
            if not advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW(
                sddl, 1, ctypes.byref(descriptor), None
            ):
                raise OSError("lease security descriptor unavailable")
            return descriptor
        finally:
            if token.value:
                self.kernel32.CloseHandle(token)
            self.kernel32.LocalFree.argtypes = [ctypes.c_void_p]
            self.kernel32.LocalFree.restype = ctypes.c_void_p
            if sid_string.value:
                self.kernel32.LocalFree(sid_string)

    def lock(self, handle: int) -> bool:
        class Overlapped(ctypes.Structure):
            _fields_ = [
                ("Internal", ctypes.c_void_p),
                ("InternalHigh", ctypes.c_void_p),
                ("Offset", wintypes.DWORD),
                ("OffsetHigh", wintypes.DWORD),
                ("hEvent", wintypes.HANDLE),
            ]

        overlapped = Overlapped()
        if self.kernel32.LockFileEx(
            wintypes.HANDLE(handle), 0x00000002 | 0x00000001, 0, 1, 0, ctypes.byref(overlapped)
        ):
            return True
        if ctypes.get_last_error() in {32, 33, 158}:
            return False
        raise OSError("lease lock unavailable")

    def inspect_state(self, path: Path, handle: int | None = None) -> str:
        self.kernel32.CreateFileW.restype = wintypes.HANDLE
        probe = self.kernel32.CreateFileW(
            str(path), 0x80000000, 0, None, 3, 0x00200000, None
        )
        if probe == wintypes.HANDLE(-1).value:
            if ctypes.get_last_error() in {32, 33}:
                return "active"
            raise OSError("lease observation unavailable")
        try:
            return "available"
        finally:
            if not self.kernel32.CloseHandle(wintypes.HANDLE(probe)):
                raise OSError("lease observation cleanup failed")

    def unlock(self, handle: int) -> None:
        class Overlapped(ctypes.Structure):
            _fields_ = [("data", ctypes.c_byte * 32)]

        overlapped = Overlapped()
        if not self.kernel32.UnlockFileEx(
            wintypes.HANDLE(handle), 0, 1, 0, ctypes.byref(overlapped)
        ):
            raise OSError("lease unlock failed")

    def close(self, handle: int) -> None:
        if not self.kernel32.CloseHandle(wintypes.HANDLE(handle)):
            raise OSError("lease close failed")

    def stat(self, handle: int) -> os.stat_result:
        import msvcrt

        self.kernel32.GetCurrentProcess.restype = wintypes.HANDLE
        self.kernel32.DuplicateHandle.argtypes = [
            wintypes.HANDLE,
            wintypes.HANDLE,
            wintypes.HANDLE,
            ctypes.POINTER(wintypes.HANDLE),
            wintypes.DWORD,
            wintypes.BOOL,
            wintypes.DWORD,
        ]
        self.kernel32.DuplicateHandle.restype = wintypes.BOOL
        process = self.kernel32.GetCurrentProcess()
        duplicate = wintypes.HANDLE()
        if not self.kernel32.DuplicateHandle(
            process,
            wintypes.HANDLE(handle),
            process,
            ctypes.byref(duplicate),
            0,
            False,
            0x00000002,
        ):
            raise OSError("lease identity unavailable")
        descriptor = msvcrt.open_osfhandle(
            int(duplicate.value), os.O_RDONLY | getattr(os, "O_BINARY", 0)
        )
        try:
            return os.fstat(descriptor)
        finally:
            os.close(descriptor)

    def permissions_are_minimal(self, path: Path, handle: int) -> bool:
        parent_handle = self._open_parent_for_security(path.parent)
        try:
            return self._handle_permissions_are_minimal(
                parent_handle, directory=True
            ) and self._handle_permissions_are_minimal(handle, directory=False)
        finally:
            self.close(parent_handle)

    def _apply_minimal_permissions(self, path: Path) -> None:
        advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
        descriptor = self._minimal_security_descriptor()
        try:
            advapi32.SetFileSecurityW.argtypes = [
                wintypes.LPCWSTR,
                wintypes.DWORD,
                ctypes.c_void_p,
            ]
            advapi32.SetFileSecurityW.restype = wintypes.BOOL
            if not advapi32.SetFileSecurityW(
                str(path), 0x00000001 | 0x00000004 | 0x80000000, descriptor
            ):
                raise OSError("lease permissions unavailable")
        finally:
            self.kernel32.LocalFree.argtypes = [ctypes.c_void_p]
            self.kernel32.LocalFree.restype = ctypes.c_void_p
            if descriptor.value:
                self.kernel32.LocalFree(descriptor)

    def _open_parent_for_security(self, path: Path) -> int:
        self.kernel32.CreateFileW.restype = wintypes.HANDLE
        handle = self.kernel32.CreateFileW(
            str(path),
            0x00020000,
            0x00000001 | 0x00000002 | 0x00000004,
            None,
            3,
            0x02000000,
            None,
        )
        if handle == wintypes.HANDLE(-1).value:
            raise OSError("lease parent security unavailable")
        return int(handle)

    def _get_security_info(
        self, handle: int
    ) -> tuple[int | None, int | None, int | None, int | None]:
        advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
        advapi32.GetSecurityInfo.argtypes = [
            wintypes.HANDLE,
            wintypes.DWORD,
            wintypes.DWORD,
            ctypes.POINTER(ctypes.c_void_p),
            ctypes.POINTER(ctypes.c_void_p),
            ctypes.POINTER(ctypes.c_void_p),
            ctypes.POINTER(ctypes.c_void_p),
            ctypes.POINTER(ctypes.c_void_p),
        ]
        advapi32.GetSecurityInfo.restype = wintypes.DWORD
        owner = ctypes.c_void_p()
        dacl = ctypes.c_void_p()
        descriptor = ctypes.c_void_p()
        result = advapi32.GetSecurityInfo(
            wintypes.HANDLE(handle),
            1,
            0x00000001 | 0x00000004,
            ctypes.byref(owner),
            None,
            ctypes.byref(dacl),
            None,
            ctypes.byref(descriptor),
        )
        if result != 0:
            return None, None, None, None
        control = wintypes.WORD()
        revision = wintypes.DWORD()
        advapi32.GetSecurityDescriptorControl.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(wintypes.WORD),
            ctypes.POINTER(wintypes.DWORD),
        ]
        advapi32.GetSecurityDescriptorControl.restype = wintypes.BOOL
        control_value = None
        if descriptor.value and advapi32.GetSecurityDescriptorControl(
            descriptor, ctypes.byref(control), ctypes.byref(revision)
        ):
            control_value = int(control.value)
        return owner.value, dacl.value, descriptor.value, control_value

    def _free_security_descriptor(self, descriptor: int) -> None:
        self.kernel32.LocalFree.argtypes = [ctypes.c_void_p]
        self.kernel32.LocalFree.restype = ctypes.c_void_p
        self.kernel32.LocalFree(ctypes.c_void_p(descriptor))

    def _handle_permissions_are_minimal(self, handle: int, *, directory: bool) -> bool:
        class Acl(ctypes.Structure):
            _fields_ = [
                ("revision", ctypes.c_ubyte),
                ("reserved", ctypes.c_ubyte),
                ("size", wintypes.WORD),
                ("ace_count", wintypes.WORD),
                ("reserved2", wintypes.WORD),
            ]

        class SidAndAttributes(ctypes.Structure):
            _fields_ = [("sid", ctypes.c_void_p), ("attributes", wintypes.DWORD)]

        class TokenUser(ctypes.Structure):
            _fields_ = [("user", SidAndAttributes)]

        advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
        advapi32.OpenProcessToken.argtypes = [
            wintypes.HANDLE,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.HANDLE),
        ]
        advapi32.OpenProcessToken.restype = wintypes.BOOL
        advapi32.GetTokenInformation.argtypes = [
            wintypes.HANDLE,
            wintypes.DWORD,
            ctypes.c_void_p,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
        ]
        advapi32.GetTokenInformation.restype = wintypes.BOOL
        advapi32.EqualSid.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        advapi32.EqualSid.restype = wintypes.BOOL
        advapi32.CreateWellKnownSid.argtypes = [
            wintypes.DWORD,
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.POINTER(wintypes.DWORD),
        ]
        advapi32.CreateWellKnownSid.restype = wintypes.BOOL
        advapi32.GetAce.argtypes = [
            ctypes.c_void_p,
            wintypes.DWORD,
            ctypes.POINTER(ctypes.c_void_p),
        ]
        advapi32.GetAce.restype = wintypes.BOOL
        owner, dacl, descriptor, control = self._get_security_info(handle)
        if descriptor is None:
            return False
        token = wintypes.HANDLE()
        token_buffer = None
        sid_buffers: list[ctypes.Array[Any]] = []
        try:
            if owner is None or dacl is None or control is None:
                return False
            if not control & 0x1000:
                return False
            if not advapi32.OpenProcessToken(
                wintypes.HANDLE(self.kernel32.GetCurrentProcess()),
                0x0008,
                ctypes.byref(token),
            ):
                return False
            needed = wintypes.DWORD()
            advapi32.GetTokenInformation(token, 1, None, 0, ctypes.byref(needed))
            if needed.value == 0:
                return False
            token_buffer = ctypes.create_string_buffer(needed.value)
            if not advapi32.GetTokenInformation(
                token,
                1,
                token_buffer,
                needed,
                ctypes.byref(needed),
            ):
                return False
            actor_sid = ctypes.cast(
                token_buffer, ctypes.POINTER(TokenUser)
            ).contents.user.sid
            if not actor_sid or not advapi32.EqualSid(owner, actor_sid):
                return False

            allowed_sids = [actor_sid]
            for sid_type in (22, 26):
                size = wintypes.DWORD(68)
                buffer = ctypes.create_string_buffer(size.value)
                if not advapi32.CreateWellKnownSid(
                    sid_type, None, buffer, ctypes.byref(size)
                ):
                    return False
                sid_buffers.append(buffer)
                allowed_sids.append(ctypes.addressof(buffer))

            acl = ctypes.cast(dacl, ctypes.POINTER(Acl)).contents
            for index in range(acl.ace_count):
                ace = ctypes.c_void_p()
                if not advapi32.GetAce(dacl, index, ctypes.byref(ace)):
                    return False
                raw = ctypes.cast(ace, ctypes.POINTER(ctypes.c_ubyte))
                if raw[0] != 0:
                    return False
                mask = ctypes.c_uint32.from_address(ace.value + 4).value
                ace_flags = raw[1]
                sid = ctypes.c_void_p(ace.value + 8)
                matching = next(
                    (
                        candidate
                        for candidate in allowed_sids
                        if advapi32.EqualSid(sid, candidate)
                    ),
                    None,
                )
                mutation_rights = 0x500D0156
                if mask & mutation_rights and not _mutation_ace_flags_are_safe(
                    ace_flags
                ):
                    return False
                if matching is None and mask & mutation_rights:
                    return False
            return True
        finally:
            if token.value:
                self.kernel32.CloseHandle(token)
            self._free_security_descriptor(descriptor)


def _backend_or_default(backend: LeaseBackend | None) -> LeaseBackend:
    if backend is not None:
        return backend
    if os.name != "nt":
        raise OSError("platform unavailable")
    return _WindowsLeaseBackend()


def acquire_execution_lease(root: Path) -> ExecutionLeaseResult:
    try:
        lease_path = default_execution_lease_path()
    except (OSError, RuntimeError, ValueError):
        return ExecutionLeaseResult(
            status="error",
            lease_state="unavailable",
            findings=[
                _finding(
                    "execution-lease-unavailable",
                    "The machine-local execution lease location is unavailable.",
                )
            ],
            next_action="Repair the machine-local execution lease location.",
        )
    return _acquire_execution_lease_core(
        root,
        lease_path=lease_path,
        backend=None,
    )


def _acquire_execution_lease_for_test(
    root: Path,
    *,
    lease_path: Path,
    backend: LeaseBackend,
) -> ExecutionLeaseResult:
    return _acquire_execution_lease_core(root, lease_path=lease_path, backend=backend)


def _acquire_execution_lease_core(
    root: Path,
    *,
    lease_path: Path,
    backend: LeaseBackend | None,
) -> ExecutionLeaseResult:
    handle: int | None = None
    locked = False
    active: LeaseBackend | None = None
    path: Path | None = None
    resolved_root: Path | None = None
    try:
        pending = _retry_pending_cleanups(lease_path)
        if pending.status != "pass":
            return ExecutionLeaseResult(
                status="error",
                lease_state="unavailable",
                findings=list(pending.findings),
                next_action=pending.next_action,
            )
        active = _backend_or_default(backend)
        resolved_root = root.resolve(strict=True)
        path = _validate_location(lease_path, root, allow_missing=True)
        active.ensure_parent(path.parent)
        path = _validate_location(path, root, allow_missing=False)
        try:
            before = path.lstat()
            if not _safe_file(before):
                raise ValueError("unsafe lease file")
            handle = active.open(path, create=False)
        except FileNotFoundError:
            handle = active.open(path, create=True)
            before = path.lstat()
        os.set_inheritable(handle, False) if isinstance(active, _PortableLeaseBackend) else None
        opened = active.stat(handle)
        if (
            not _safe_file(opened)
            or not _same_identity(before, opened)
            or not active.permissions_are_minimal(path, handle)
        ):
            raise ValueError("lease identity drift")
        locked = active.lock(handle)
        if not locked:
            cleanup = _cleanup_unregistered_handle(
                backend=active,
                handle=handle,
                path=path,
                resolved_root=resolved_root,
                locked=False,
            )
            handle = None
            if cleanup.status != "pass":
                return ExecutionLeaseResult(
                    status="error",
                    lease_state="unavailable",
                    findings=list(cleanup.findings),
                    next_action=cleanup.next_action,
                )
            return ExecutionLeaseResult(
                status="blocked",
                lease_state="active",
                findings=[
                    _finding(
                        "execution-lease-active",
                        "Another state-changing execution action is active.",
                        blocked=True,
                    )
                ],
                next_action="Retry after the active execution action completes.",
            )
        after_handle = active.stat(handle)
        after_path = path.lstat()
        if (
            not _safe_file(after_handle)
            or not _safe_file(after_path)
            or not _same_identity(before, after_handle)
            or not _same_identity(after_handle, after_path)
            or not active.permissions_are_minimal(path, handle)
        ):
            raise ValueError("lease identity drift")
        result = ExecutionLeaseResult(
            status="pass",
            lease_state="active",
            next_action="Complete the state-changing action while holding the lease.",
        )
        with _LEASE_REGISTRY_LOCK:
            state = _LeaseState(
                handle=handle,
                backend=active,
                path=path,
                root=resolved_root,
            )
            _LEASE_REGISTRY[result] = state
            state.finalizer = weakref.finalize(
                result, _finalize_lease_state, state
            )
        return result
    except _LeaseBusyError:
        return ExecutionLeaseResult(
            status="blocked",
            lease_state="active",
            findings=[
                _finding(
                    "execution-lease-active",
                    "Another state-changing execution action is active.",
                    blocked=True,
                )
            ],
            next_action="Retry after the active execution action completes.",
        )
    except Exception:
        cleanup: CheckResult | None = None
        if (
            handle is not None
            and active is not None
            and path is not None
            and resolved_root is not None
        ):
            cleanup = _cleanup_unregistered_handle(
                backend=active,
                handle=handle,
                path=path,
                resolved_root=resolved_root,
                locked=locked,
            )
        return ExecutionLeaseResult(
            status="error",
            lease_state="unavailable",
            findings=(
                list(cleanup.findings)
                if cleanup is not None and cleanup.status != "pass"
                else [
                    _finding(
                        "execution-lease-invalid",
                        "The machine-local execution lease is unavailable or invalid.",
                    )
                ]
            ),
            next_action=(
                cleanup.next_action
                if cleanup is not None and cleanup.status != "pass"
                else "Repair the machine-local execution lease location."
            ),
        )
    except BaseException:
        if (
            handle is not None
            and active is not None
            and path is not None
            and resolved_root is not None
        ):
            _cleanup_unregistered_handle(
                backend=active,
                handle=handle,
                path=path,
                resolved_root=resolved_root,
                locked=locked,
            )
        raise


def inspect_execution_lease(root: Path) -> ExecutionLeaseResult:
    try:
        lease_path = default_execution_lease_path()
    except (OSError, RuntimeError, ValueError):
        return ExecutionLeaseResult(
            status="error",
            lease_state="unavailable",
            findings=[
                _finding(
                    "execution-lease-unavailable",
                    "The machine-local execution lease location is unavailable.",
                )
            ],
        )
    return _inspect_execution_lease_core(
        root,
        lease_path=lease_path,
        backend=None,
    )


def _inspect_execution_lease_for_test(
    root: Path,
    *,
    lease_path: Path,
    backend: LeaseBackend,
) -> ExecutionLeaseResult:
    return _inspect_execution_lease_core(root, lease_path=lease_path, backend=backend)


def _inspect_execution_lease_core(
    root: Path,
    *,
    lease_path: Path,
    backend: LeaseBackend | None,
) -> ExecutionLeaseResult:
    handle: int | None = None
    locked = False
    active: LeaseBackend | None = None
    path: Path | None = None
    resolved_root: Path | None = None
    result: ExecutionLeaseResult | None = None
    try:
        active = _backend_or_default(backend)
        resolved_root = root.resolve(strict=True)
        path = _validate_location(lease_path, root, allow_missing=True)
        try:
            before = path.lstat()
        except FileNotFoundError:
            return ExecutionLeaseResult(status="pass", lease_state="available")
        if not _safe_file(before):
            raise ValueError("unsafe lease file")
        state = active.inspect_state(path)
        if state not in {"available", "active"}:
            raise ValueError("invalid lease observation")
        handle = active.open(path, create=False, inspect=True)
        opened = active.stat(handle)
        if (
            not _same_identity(before, opened)
            or not active.permissions_are_minimal(path, handle)
        ):
            raise ValueError("lease identity drift")
        result = ExecutionLeaseResult(status="pass", lease_state=state)
    except _LeaseBusyError:
        result = ExecutionLeaseResult(status="pass", lease_state="active")
    except Exception:
        result = ExecutionLeaseResult(
            status="error",
            lease_state="unavailable",
            findings=[
                _finding(
                    "execution-lease-unavailable",
                    "The machine-local execution lease state is unavailable.",
                )
            ],
        )
    finally:
        if (
            handle is not None
            and active is not None
            and path is not None
            and resolved_root is not None
        ):
            cleanup = _cleanup_unregistered_handle(
                backend=active,
                handle=handle,
                path=path,
                resolved_root=resolved_root,
                locked=locked,
            )
            if cleanup.status != "pass":
                result = ExecutionLeaseResult(
                    status="error",
                    lease_state="unavailable",
                    findings=list(cleanup.findings),
                    next_action=cleanup.next_action,
                )
    return result or ExecutionLeaseResult(
        status="error",
        lease_state="unavailable",
        findings=[
            _finding(
                "execution-lease-unavailable",
                "The machine-local execution lease state is unavailable.",
            )
        ],
    )
