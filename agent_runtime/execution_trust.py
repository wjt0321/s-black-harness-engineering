"""Machine-local trust binding for the single fixed Git executor."""

from __future__ import annotations

import ctypes
import hashlib
import json
import os
import re
import stat
import tempfile
from ctypes import wintypes
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Protocol

from jsonschema import Draft202012Validator
from jsonschema import ValidationError as JsonSchemaValidationError
from jsonschema import validate

from .result import CheckResult, Finding
from .task_validation import DATE_TIME_FORMAT_CHECKER

_SCHEMA_VERSION = "execution-trust-binding/v1"
_MAX_BINDING_BYTES = 64 * 1024
_SHA_RE = re.compile(r"^[0-9a-f]{64}$")
_THUMBPRINT_RE = re.compile(r"^[0-9A-F]{40}$")
_REPARSE_POINT = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)


@dataclass(frozen=True)
class SanitizedPath:
    directories: tuple[Path, ...]
    serialized: str
    identity: str


@dataclass
class ExecutableIdentity:
    canonical_path: Path
    approved_root: Path
    sha256: str
    file_identity: str
    publisher_thumbprint: str
    owner_policy: str
    path_identity: str = "sha256:" + "0" * 64
    sanitized_path: str = ""
    native_handle: int | None = None

    def close(self) -> None:
        if self.native_handle is not None and os.name == "nt":
            ctypes.WinDLL("kernel32", use_last_error=True).CloseHandle(
                wintypes.HANDLE(self.native_handle)
            )
            self.native_handle = None


class TrustBackend(Protocol):
    platform: str

    def discover(
        self, root: Path, path_value: str | None = None
    ) -> ExecutableIdentity: ...

    def acquire_verified(
        self, binding: dict[str, object], root: Path
    ) -> ExecutableIdentity: ...


@dataclass
class TrustBindingResult(CheckResult):
    binding: dict[str, Any] | None = None
    binding_id: str | None = None
    executable_identity: str | None = None
    path_identity: str | None = None
    committed: bool = False

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        for key in ("binding_id", "executable_identity", "path_identity"):
            value = getattr(self, key)
            if value is not None:
                payload[key] = value
        payload["committed"] = self.committed
        return payload


@dataclass
class VerifiedTrustResult(CheckResult):
    identity: ExecutableIdentity | None = None
    binding_id: str | None = None
    executable_identity: str | None = None
    path_identity: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        for key in ("binding_id", "executable_identity", "path_identity"):
            value = getattr(self, key)
            if value is not None:
                payload[key] = value
        return payload


def _finding(rule_id: str, message: str, *, blocked: bool = False) -> Finding:
    return Finding(
        rule_id,
        "block" if blocked else "error",
        "blocked" if blocked else "validation_failed",
        message,
    )


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _identity_digest(identity: ExecutableIdentity) -> str:
    payload = {
        "approved_root": str(identity.approved_root),
        "file_identity": identity.file_identity,
        "owner_policy": identity.owner_policy,
        "publisher_thumbprint": identity.publisher_thumbprint,
        "sha256": identity.sha256,
    }
    return "sha256:" + hashlib.sha256(_canonical_json(payload)).hexdigest()


def sanitize_path(
    path_value: str,
    root: Path,
    *,
    platform: str | None = None,
    canonicalize: Callable[[Path], Path] | None = None,
    allow_directory: Callable[[Path], bool] | None = None,
) -> SanitizedPath:
    """Drop unsafe PATH entries and produce deterministic identity evidence."""
    platform = platform or ("windows" if os.name == "nt" else "posix")
    separator = ";" if platform == "windows" else ":"
    canonicalize = canonicalize or (lambda path: path.resolve(strict=True))
    root = root.resolve()
    seen: set[str] = set()
    directories: list[Path] = []
    for raw in path_value.split(separator):
        if not raw:
            continue
        candidate = Path(raw)
        if not candidate.is_absolute():
            continue
        try:
            canonical = canonicalize(candidate)
            info = canonical.lstat()
        except (OSError, RuntimeError):
            continue
        if (
            not stat.S_ISDIR(info.st_mode)
            or stat.S_ISLNK(info.st_mode)
            or getattr(info, "st_file_attributes", 0) & _REPARSE_POINT
            or canonical == root
            or root in canonical.parents
            or (allow_directory is not None and not allow_directory(canonical))
        ):
            continue
        key = os.path.normcase(str(canonical)) if platform == "windows" else str(canonical)
        if platform == "windows":
            key = key.casefold()
        if key in seen:
            continue
        seen.add(key)
        directories.append(canonical)
    serialized = separator.join(str(item) for item in directories)
    return SanitizedPath(
        directories=tuple(directories),
        serialized=serialized,
        identity="sha256:" + hashlib.sha256(serialized.encode("utf-8")).hexdigest(),
    )


def _default_binding_path() -> Path:
    if os.name != "nt":
        import pwd

        return (
            Path(pwd.getpwuid(os.getuid()).pw_dir)
            / ".config"
            / "agent-runtime"
            / "execution-trust-v1.json"
        )
    folder_id = ctypes.c_byte * 16
    raw_guid = bytes.fromhex("8527b3f1ba6fcf4f9d557b8e7f157091")
    guid = folder_id.from_buffer_copy(raw_guid)
    value = ctypes.c_wchar_p()
    shell32 = ctypes.WinDLL("shell32", use_last_error=True)
    ole32 = ctypes.WinDLL("ole32", use_last_error=True)
    result = shell32.SHGetKnownFolderPath(
        ctypes.byref(guid), 0, None, ctypes.byref(value)
    )
    if result != 0 or not value.value:
        raise OSError("known folder unavailable")
    try:
        return Path(value.value) / "agent-runtime" / "execution-trust-v1.json"
    finally:
        ole32.CoTaskMemFree(value)


def _schema() -> dict[str, Any]:
    path = Path(__file__).resolve().parents[1] / "adapters" / "execution-trust-binding.schema.json"
    with path.open("r", encoding="utf-8") as handle:
        schema = json.load(handle)
    Draft202012Validator.check_schema(schema)
    return schema


def _strict_json(raw: str) -> dict[str, Any]:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for key, item in items:
            if key in value:
                raise ValueError("duplicate key")
            value[key] = item
        return value

    loaded = json.loads(raw, object_pairs_hook=pairs)
    if not isinstance(loaded, dict):
        raise ValueError("object required")
    return loaded


def _validate_binding_location(
    path: Path,
    *,
    root: Path | None = None,
    allow_missing_parent: bool = False,
) -> Path:
    target = Path(os.path.abspath(path))
    if root is not None:
        project = root.resolve(strict=True)
        try:
            common = Path(os.path.commonpath([str(project), str(target)]))
        except ValueError:
            common = None
        if common is not None and common == project:
            raise ValueError("project-local binding")
    current = target.parent
    found_existing = False
    while True:
        try:
            info = current.lstat()
            found_existing = True
            if (
                not stat.S_ISDIR(info.st_mode)
                or stat.S_ISLNK(info.st_mode)
                or getattr(info, "st_file_attributes", 0) & _REPARSE_POINT
            ):
                raise ValueError("unsafe binding parent")
        except FileNotFoundError:
            if not allow_missing_parent:
                raise
        if current == current.parent:
            break
        current = current.parent
    if not found_existing:
        raise ValueError("binding parent unavailable")
    return target


def _read_binding_bytes(path: Path) -> bytes:
    info = path.lstat()
    if (
        not stat.S_ISREG(info.st_mode)
        or stat.S_ISLNK(info.st_mode)
        or getattr(info, "st_file_attributes", 0) & _REPARSE_POINT
        or info.st_nlink != 1
        or info.st_size > _MAX_BINDING_BYTES
    ):
        raise ValueError("unsafe binding file")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    if os.name == "nt":
        import msvcrt

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateFileW.restype = wintypes.HANDLE
        native = kernel32.CreateFileW(
            str(path),
            0x80000000,
            0x00000001,
            None,
            3,
            0x00200000,
            None,
        )
        if native == wintypes.HANDLE(-1).value:
            raise OSError("binding handle unavailable")
        try:
            descriptor = msvcrt.open_osfhandle(int(native), flags)
        except Exception:
            kernel32.CloseHandle(native)
            raise
    else:
        descriptor = os.open(path, flags)
    try:
        current = os.fstat(descriptor)
        if (
            int(current.st_dev) != int(info.st_dev)
            or int(current.st_ino) != int(info.st_ino)
            or int(current.st_size) != int(info.st_size)
        ):
            raise ValueError("binding identity drift")
        raw = os.read(descriptor, _MAX_BINDING_BYTES + 1)
        if len(raw) != info.st_size or os.read(descriptor, 1):
            raise ValueError("binding size drift")
        return raw
    finally:
        os.close(descriptor)


def load_execution_trust_binding(
    path: Path | None = None,
    *,
    root: Path | None = None,
) -> TrustBindingResult:
    try:
        binding_path = _validate_binding_location(
            path or _default_binding_path(),
            root=root,
        )
        raw = _read_binding_bytes(binding_path)
        if len(raw) > _MAX_BINDING_BYTES or b"\x00" in raw:
            raise ValueError("binding bounds")
        binding = _strict_json(raw.decode("utf-8", errors="strict"))
        validate(
            instance=binding,
            schema=_schema(),
            format_checker=DATE_TIME_FORMAT_CHECKER,
        )
        canonical = dict(binding)
        binding_id = canonical.pop("binding_id")
        expected = "sha256:" + hashlib.sha256(_canonical_json(canonical)).hexdigest()
        if binding_id != expected:
            raise ValueError("binding digest")
    except (
        OSError,
        UnicodeDecodeError,
        ValueError,
        json.JSONDecodeError,
        JsonSchemaValidationError,
    ):
        return TrustBindingResult(
            status="validation_failed",
            findings=[
                _finding(
                    "execution-trust-binding-invalid",
                    "The machine-local execution trust binding is invalid.",
                )
            ],
            next_action="Create a reviewed machine-local trust binding.",
        )
    executable = binding["executable"]
    executable_identity = "sha256:" + hashlib.sha256(
        _canonical_json(
            {
                key: executable[key]
                for key in (
                    "approved_root",
                    "file_identity",
                    "owner_policy",
                    "publisher_thumbprint",
                    "sha256",
                )
            }
        )
    ).hexdigest()
    return TrustBindingResult(
        status="pass",
        binding=binding,
        binding_id=binding["binding_id"],
        executable_identity=executable_identity,
        path_identity=binding["path_identity"],
        next_action="Verify the bound executable immediately before execution.",
    )


def _default_backend() -> TrustBackend:
    if os.name != "nt":
        raise OSError("platform unavailable")
    return WindowsTrustBackend()


def create_execution_trust_binding(
    root: Path,
    *,
    expected_sha256: str,
    expected_publisher_thumbprint: str,
    commit: bool,
    replace: bool = False,
    binding_path: Path | None = None,
    backend: TrustBackend | None = None,
) -> TrustBindingResult:
    if (
        _SHA_RE.fullmatch(expected_sha256) is None
        or _THUMBPRINT_RE.fullmatch(expected_publisher_thumbprint) is None
    ):
        return TrustBindingResult(
            status="validation_failed",
            findings=[
                _finding(
                    "execution-trust-review-invalid",
                    "Reviewed trust values must use canonical digest formats.",
                )
            ],
        )
    try:
        active_backend = backend or _default_backend()
        identity = active_backend.discover(root.resolve())
        target = _validate_binding_location(
            binding_path or _default_binding_path(),
            root=root,
            allow_missing_parent=True,
        )
    except (OSError, RuntimeError, ValueError):
        return TrustBindingResult(
            status="error",
            findings=[
                Finding(
                    "execution-trust-platform-unavailable",
                    "error",
                    "error",
                    "Trusted executable inspection is unavailable on this platform.",
                )
            ],
        )
    try:
        if (
            identity.sha256 != expected_sha256
            or identity.publisher_thumbprint != expected_publisher_thumbprint
        ):
            return TrustBindingResult(
                status="blocked",
                findings=[
                    _finding(
                        "execution-trust-review-mismatch",
                        "Reviewed trust values do not match the inspected executable.",
                        blocked=True,
                    )
                ],
            )
        binding: dict[str, Any] = {
            "schema_version": _SCHEMA_VERSION,
            "platform": active_backend.platform,
            "path_identity": identity.path_identity,
            "executable": {
                "canonical_path": str(identity.canonical_path),
                "approved_root": str(identity.approved_root),
                "sha256": identity.sha256,
                "file_identity": identity.file_identity,
                "publisher_thumbprint": identity.publisher_thumbprint,
                "owner_policy": identity.owner_policy,
            },
            "reviewer": {
                "actor": "local-operator",
                "reviewed_at": datetime.now(timezone.utc).isoformat(),
                "provenance": "explicit-cli-review",
            },
        }
        binding["binding_id"] = "sha256:" + hashlib.sha256(
            _canonical_json(binding)
        ).hexdigest()
        validate(
            instance=binding,
            schema=_schema(),
            format_checker=DATE_TIME_FORMAT_CHECKER,
        )
        result = TrustBindingResult(
            status="pass",
            binding_id=binding["binding_id"],
            executable_identity=_identity_digest(identity),
            path_identity=identity.path_identity,
            committed=False,
            next_action=(
                "Repeat with --commit after reviewing the machine executable evidence."
                if not commit
                else "Verify the binding before fixed execution."
            ),
        )
        if not commit:
            return result
        target_exists = False
        try:
            target.lstat()
            target_exists = True
        except FileNotFoundError:
            pass
        if target_exists and not replace:
            return TrustBindingResult(
                status="blocked",
                findings=[
                    _finding(
                        "execution-trust-binding-exists",
                        "A machine-local execution trust binding already exists.",
                        blocked=True,
                    )
                ],
                next_action="Remove or rotate the binding through explicit operator review.",
            )
        previous_bytes: bytes | None = None
        if target_exists:
            previous = load_execution_trust_binding(target, root=root)
            if previous.status != "pass":
                return TrustBindingResult(
                    status="blocked",
                    findings=[
                        _finding(
                            "execution-trust-binding-rotation-blocked",
                            "The existing trust binding must validate before rotation.",
                            blocked=True,
                        )
                    ],
                )
            previous_bytes = _read_binding_bytes(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        target = _validate_binding_location(target, root=root)
        data = _canonical_json(binding) + b"\n"
        temp_path: Path | None = None
        try:
            if target_exists:
                descriptor, temp_name = tempfile.mkstemp(
                    prefix=".execution-trust-",
                    suffix=".tmp",
                    dir=target.parent,
                )
                temp_path = Path(temp_name)
            else:
                descriptor = os.open(
                    target,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                    0o600,
                )
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            if temp_path is not None:
                os.replace(temp_path, target)
            loaded = load_execution_trust_binding(target, root=root)
            if loaded.status != "pass" or loaded.binding_id != binding["binding_id"]:
                if previous_bytes is None:
                    target.unlink(missing_ok=True)
                else:
                    rollback_descriptor, rollback_name = tempfile.mkstemp(
                        prefix=".execution-trust-rollback-",
                        suffix=".tmp",
                        dir=target.parent,
                    )
                    rollback_path = Path(rollback_name)
                    try:
                        with os.fdopen(rollback_descriptor, "wb") as handle:
                            handle.write(previous_bytes)
                            handle.flush()
                            os.fsync(handle.fileno())
                        os.replace(rollback_path, target)
                    finally:
                        rollback_path.unlink(missing_ok=True)
                return TrustBindingResult(
                    status="error",
                    findings=[
                        Finding(
                            "execution-trust-binding-postcheck-failed",
                            "error",
                            "error",
                            "The machine-local trust binding failed post-write validation.",
                        )
                    ],
                )
        except FileExistsError:
            return TrustBindingResult(
                status="blocked",
                findings=[
                    _finding(
                        "execution-trust-binding-exists",
                        "A machine-local execution trust binding already exists.",
                        blocked=True,
                    )
                ],
            )
        finally:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)
        result.committed = True
        return result
    finally:
        identity.close()


def verify_execution_trust(
    root: Path,
    *,
    binding_path: Path | None = None,
    backend: TrustBackend | None = None,
) -> VerifiedTrustResult:
    loaded = load_execution_trust_binding(binding_path, root=root)
    if loaded.status != "pass" or loaded.binding is None:
        return VerifiedTrustResult(
            status=loaded.status,
            findings=loaded.findings,
            next_action=loaded.next_action,
        )
    try:
        active_backend = backend or _default_backend()
        identity = active_backend.acquire_verified(loaded.binding, root.resolve())
    except (OSError, RuntimeError, ValueError):
        return VerifiedTrustResult(
            status="blocked",
            findings=[
                _finding(
                    "execution-trust-identity-drift",
                    "The trusted executable identity could not be re-established.",
                    blocked=True,
                )
            ],
            next_action="Review and rotate the machine-local trust binding.",
        )
    expected = loaded.binding["executable"]
    actual = {
        "canonical_path": str(identity.canonical_path),
        "approved_root": str(identity.approved_root),
        "sha256": identity.sha256,
        "file_identity": identity.file_identity,
        "publisher_thumbprint": identity.publisher_thumbprint,
        "owner_policy": identity.owner_policy,
    }
    if actual != expected or identity.path_identity != loaded.binding["path_identity"]:
        identity.close()
        return VerifiedTrustResult(
            status="blocked",
            findings=[
                _finding(
                    "execution-trust-identity-drift",
                    "The trusted executable identity changed.",
                    blocked=True,
                )
            ],
            next_action="Review and rotate the machine-local trust binding.",
        )
    return VerifiedTrustResult(
        status="pass",
        identity=identity,
        binding_id=loaded.binding_id,
        executable_identity=loaded.executable_identity,
        path_identity=loaded.path_identity,
        next_action="Keep the trusted executable handle open through process creation.",
    )


class WindowsTrustBackend:
    """Win32 trust inspection with a non-shareable executable handle."""

    platform = "windows"

    def discover(
        self, root: Path, path_value: str | None = None
    ) -> ExecutableIdentity:
        sanitized = sanitize_path(
            path_value if path_value is not None else os.environ.get("PATH", ""),
            root,
            platform="windows",
            allow_directory=lambda path: not self._is_writable(
                path, directory=True
            ),
        )
        for directory in sanitized.directories:
            candidate = directory / "git.exe"
            if candidate.is_file() and candidate.name.lower() == "git.exe":
                identity = self._inspect(
                    candidate,
                    sanitized.identity,
                    sanitized.serialized,
                )
                return identity
        raise OSError("git unavailable")

    def acquire_verified(
        self, binding: dict[str, object], root: Path
    ) -> ExecutableIdentity:
        return self.discover(root)

    def _inspect(
        self,
        path: Path,
        path_identity: str,
        sanitized_path: str,
    ) -> ExecutableIdentity:
        canonical = path.resolve(strict=True)
        if canonical.name.lower() != "git.exe":
            raise OSError("invalid executable")
        info = canonical.lstat()
        if (
            not stat.S_ISREG(info.st_mode)
            or stat.S_ISLNK(info.st_mode)
            or getattr(info, "st_file_attributes", 0) & _REPARSE_POINT
        ):
            raise OSError("unsafe executable")
        approved_root = canonical.parents[1]
        for parent in (approved_root, *reversed(approved_root.parents)):
            parent_info = parent.lstat()
            if (
                stat.S_ISLNK(parent_info.st_mode)
                or getattr(parent_info, "st_file_attributes", 0) & _REPARSE_POINT
            ):
                raise OSError("unsafe parent")
        if self._is_writable(canonical, directory=False):
            raise OSError("writable executable")
        current = canonical.parent
        while True:
            if self._is_writable(current, directory=True):
                raise OSError("writable parent")
            if current == approved_root:
                break
            current = current.parent
        current = approved_root.parent
        while True:
            if self._is_writable(
                current,
                directory=True,
                replacement_only=True,
            ):
                raise OSError("replaceable approved root")
            if current == current.parent:
                break
            current = current.parent
        handle = self._open_locked(canonical)
        try:
            file_identity, sha256 = self._handle_identity_and_digest(handle)
            thumbprint = self._verify_authenticode(canonical, handle)
            return ExecutableIdentity(
                canonical_path=canonical,
                approved_root=approved_root,
                sha256=sha256,
                file_identity=file_identity,
                publisher_thumbprint=thumbprint,
                owner_policy="windows-system-install",
                path_identity=path_identity,
                sanitized_path=sanitized_path,
                native_handle=handle,
            )
        except Exception:
            ctypes.WinDLL("kernel32", use_last_error=True).CloseHandle(
                wintypes.HANDLE(handle)
            )
            raise

    @staticmethod
    def _open_locked(path: Path) -> int:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateFileW.argtypes = [
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.LPVOID,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.HANDLE,
        ]
        kernel32.CreateFileW.restype = wintypes.HANDLE
        handle = kernel32.CreateFileW(
            str(path),
            0x80000000,
            0x00000001,
            None,
            3,
            0x00200000,
            None,
        )
        if handle == wintypes.HANDLE(-1).value:
            raise OSError("executable handle unavailable")
        return int(handle)

    @staticmethod
    def _handle_identity_and_digest(handle: int) -> tuple[str, str]:
        class FileInfo(ctypes.Structure):
            _fields_ = [
                ("attributes", wintypes.DWORD),
                ("created", wintypes.FILETIME),
                ("accessed", wintypes.FILETIME),
                ("written", wintypes.FILETIME),
                ("volume_serial", wintypes.DWORD),
                ("size_high", wintypes.DWORD),
                ("size_low", wintypes.DWORD),
                ("link_count", wintypes.DWORD),
                ("file_index_high", wintypes.DWORD),
                ("file_index_low", wintypes.DWORD),
            ]

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        info = FileInfo()
        if not kernel32.GetFileInformationByHandle(
            wintypes.HANDLE(handle), ctypes.byref(info)
        ):
            raise OSError("file identity unavailable")
        if info.attributes & 0x400:
            raise OSError("reparse executable")
        identity = (
            f"{info.volume_serial:08x}:"
            f"{info.file_index_high:08x}{info.file_index_low:08x}"
        )
        size = (info.size_high << 32) | info.size_low
        if size > 64 * 1024 * 1024:
            raise OSError("executable too large")
        position = ctypes.c_longlong(0)
        if not kernel32.SetFilePointerEx(
            wintypes.HANDLE(handle), 0, ctypes.byref(position), 0
        ):
            raise OSError("executable seek failed")
        hasher = hashlib.sha256()
        remaining = size
        buffer = ctypes.create_string_buffer(65_536)
        while remaining:
            requested = min(remaining, len(buffer))
            read = wintypes.DWORD()
            if not kernel32.ReadFile(
                wintypes.HANDLE(handle),
                buffer,
                requested,
                ctypes.byref(read),
                None,
            ):
                raise OSError("executable read failed")
            if read.value == 0:
                raise OSError("short executable read")
            hasher.update(buffer.raw[: read.value])
            remaining -= read.value
        return identity, hasher.hexdigest()

    @staticmethod
    def _is_writable(
        path: Path,
        *,
        directory: bool,
        replacement_only: bool = False,
    ) -> bool:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateFileW.restype = wintypes.HANDLE
        flags = 0x02000000 if directory else 0x00200000
        if directory and replacement_only:
            rights = (0x0040, 0x00040000, 0x00080000)
        elif directory:
            rights = (0x0002, 0x0004, 0x0040, 0x00010000, 0x00040000, 0x00080000)
        else:
            rights = (0x0002, 0x0004, 0x00010000, 0x00040000, 0x00080000)
        for desired in rights:
            ctypes.set_last_error(0)
            handle = kernel32.CreateFileW(
                str(path),
                desired,
                0x00000001 | 0x00000002 | 0x00000004,
                None,
                3,
                flags,
                None,
            )
            if handle != wintypes.HANDLE(-1).value:
                kernel32.CloseHandle(handle)
                return True
            error = ctypes.get_last_error()
            if error != 5:
                raise OSError("writable access check failed")
        return False

    @staticmethod
    def _verify_authenticode(path: Path, handle: int) -> str:
        # WinVerifyTrust performs signature and chain validation without UI or
        # network retrieval. Certificate extraction remains bound to the same
        # signed file and returns only its SHA-1 certificate thumbprint.
        class GUID(ctypes.Structure):
            _fields_ = [
                ("Data1", wintypes.DWORD),
                ("Data2", wintypes.WORD),
                ("Data3", wintypes.WORD),
                ("Data4", ctypes.c_ubyte * 8),
            ]

        class WinTrustFileInfo(ctypes.Structure):
            _fields_ = [
                ("cbStruct", wintypes.DWORD),
                ("pcwszFilePath", wintypes.LPCWSTR),
                ("hFile", wintypes.HANDLE),
                ("pgKnownSubject", ctypes.POINTER(GUID)),
            ]

        class WinTrustData(ctypes.Structure):
            _fields_ = [
                ("cbStruct", wintypes.DWORD),
                ("pPolicyCallbackData", wintypes.LPVOID),
                ("pSIPClientData", wintypes.LPVOID),
                ("dwUIChoice", wintypes.DWORD),
                ("fdwRevocationChecks", wintypes.DWORD),
                ("dwUnionChoice", wintypes.DWORD),
                ("pFile", ctypes.POINTER(WinTrustFileInfo)),
                ("dwStateAction", wintypes.DWORD),
                ("hWVTStateData", wintypes.HANDLE),
                ("pwszURLReference", wintypes.LPCWSTR),
                ("dwProvFlags", wintypes.DWORD),
                ("dwUIContext", wintypes.DWORD),
                ("pSignatureSettings", wintypes.LPVOID),
            ]

        action = GUID(
            0x00AAC56B,
            0xCD44,
            0x11D0,
            (ctypes.c_ubyte * 8)(0x8C, 0xC2, 0x00, 0xC0, 0x4F, 0xC2, 0x95, 0xEE),
        )
        file_info = WinTrustFileInfo(
            ctypes.sizeof(WinTrustFileInfo),
            str(path),
            wintypes.HANDLE(handle),
            None,
        )
        data = WinTrustData(
            ctypes.sizeof(WinTrustData),
            None,
            None,
            2,
            0,
            1,
            ctypes.pointer(file_info),
            0,
            None,
            None,
            0x00001000,
            0,
            None,
        )
        wintrust = ctypes.WinDLL("wintrust", use_last_error=True)
        status = wintrust.WinVerifyTrust(
            None, ctypes.byref(action), ctypes.byref(data)
        )
        if status != 0:
            raise OSError("authenticode verification failed")
        # The reviewed publisher is additionally pinned in the external
        # binding. Use the certificate thumbprint reported by PowerShell-compatible
        # CryptQueryObject extraction in the next platform layer.
        return _authenticode_thumbprint(path)


def _authenticode_thumbprint(path: Path) -> str:
    """Extract the embedded signer certificate thumbprint with CryptoAPI."""
    # Keep the implementation small and fail closed: CryptQueryObject must
    # expose an embedded PKCS#7 store with exactly one matching signer cert.
    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    encoding = wintypes.DWORD()
    content = wintypes.DWORD()
    format_type = wintypes.DWORD()
    store = wintypes.HANDLE()
    message = wintypes.HANDLE()
    context = wintypes.LPVOID()
    if not crypt32.CryptQueryObject(
        1,
        wintypes.LPCWSTR(str(path)),
        0x00000400,
        0x00000002,
        0,
        ctypes.byref(encoding),
        ctypes.byref(content),
        ctypes.byref(format_type),
        ctypes.byref(store),
        ctypes.byref(message),
        ctypes.byref(context),
    ):
        raise OSError("signer store unavailable")

    class Blob(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_ubyte))]

    class Algorithm(ctypes.Structure):
        _fields_ = [("pszObjId", ctypes.c_char_p), ("Parameters", Blob)]

    class Attributes(ctypes.Structure):
        _fields_ = [("cAttr", wintypes.DWORD), ("rgAttr", wintypes.LPVOID)]

    class SignerInfo(ctypes.Structure):
        _fields_ = [
            ("dwVersion", wintypes.DWORD),
            ("Issuer", Blob),
            ("SerialNumber", Blob),
            ("HashAlgorithm", Algorithm),
            ("HashEncryptionAlgorithm", Algorithm),
            ("EncryptedHash", Blob),
            ("AuthAttrs", Attributes),
            ("UnauthAttrs", Attributes),
        ]

    size = wintypes.DWORD()
    try:
        if not crypt32.CryptMsgGetParam(message, 6, 0, None, ctypes.byref(size)):
            raise OSError("signer info unavailable")
        buffer = ctypes.create_string_buffer(size.value)
        if not crypt32.CryptMsgGetParam(
            message, 6, 0, buffer, ctypes.byref(size)
        ):
            raise OSError("signer info unavailable")
        signer = ctypes.cast(buffer, ctypes.POINTER(SignerInfo)).contents

        class CertInfo(ctypes.Structure):
            _fields_ = [
                ("dwVersion", wintypes.DWORD),
                ("SerialNumber", Blob),
                ("SignatureAlgorithm", Algorithm),
                ("Issuer", Blob),
            ]

        class CertContext(ctypes.Structure):
            _fields_ = [
                ("dwCertEncodingType", wintypes.DWORD),
                ("pbCertEncoded", ctypes.POINTER(ctypes.c_ubyte)),
                ("cbCertEncoded", wintypes.DWORD),
                ("pCertInfo", ctypes.POINTER(CertInfo)),
                ("hCertStore", wintypes.HANDLE),
            ]

        crypt32.CertEnumCertificatesInStore.restype = ctypes.POINTER(CertContext)
        current = ctypes.POINTER(CertContext)()
        matches: list[str] = []
        issuer = bytes(
            ctypes.string_at(signer.Issuer.pbData, signer.Issuer.cbData)
        )
        serial = bytes(
            ctypes.string_at(signer.SerialNumber.pbData, signer.SerialNumber.cbData)
        )
        while True:
            current = crypt32.CertEnumCertificatesInStore(store, current)
            if not current:
                break
            cert = current.contents
            info = cert.pCertInfo.contents
            cert_issuer = bytes(
                ctypes.string_at(info.Issuer.pbData, info.Issuer.cbData)
            )
            cert_serial = bytes(
                ctypes.string_at(info.SerialNumber.pbData, info.SerialNumber.cbData)
            )
            if cert_issuer == issuer and cert_serial == serial:
                encoded = bytes(
                    ctypes.string_at(cert.pbCertEncoded, cert.cbCertEncoded)
                )
                matches.append(hashlib.sha1(encoded).hexdigest().upper())
        if len(matches) != 1:
            raise OSError("ambiguous signer certificate")
        return matches[0]
    finally:
        if message:
            crypt32.CryptMsgClose(message)
        if store:
            crypt32.CertCloseStore(store, 0)
