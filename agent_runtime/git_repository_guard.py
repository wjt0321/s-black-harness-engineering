"""Bounded lstat-first guard for the fixed Git status executor."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .result import CheckResult, Finding

_MAX_ENTRIES = 20_000
_MAX_DEPTH = 16
_MAX_PATH_BYTES = 1_048_576
_MAX_CONTENT_BYTES = 64 * 1024 * 1024
_MAX_CONFIG_BYTES = 256 * 1024
_REPARSE_POINT = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
_CRITICAL_FILES = (
    ".git/index",
    ".git/HEAD",
    ".git/packed-refs",
    ".git/logs/HEAD",
    ".git/config",
    ".git/config.worktree",
    ".git/info/exclude",
    ".git/info/attributes",
)
_TRAVERSE_DIRS = (
    ".git/refs",
    ".git/objects",
)
_BLOCKED_SURFACES = (
    (".git/commondir", "execution.repository-indirection-blocked"),
    (".git/objects/info/alternates", "execution.object-alternate-blocked"),
    (".git/objects/info/http-alternates", "execution.object-alternate-blocked"),
    (".gitmodules", "execution.submodule-surface-blocked"),
)
_SECTION_RE = re.compile(r'^\[([A-Za-z0-9.-]+)(?:\s+"[^"\r\n]*")?\]$')
_KEY_RE = re.compile(r"^([A-Za-z][A-Za-z0-9.-]*)\s*(?:=\s*(.*))?$")


@dataclass(frozen=True)
class RepositoryGuard:
    identity: str
    manifest: tuple[tuple[str, str, int, int, int, int, str], ...]
    _handles: tuple[int, ...] = field(default=(), compare=False, repr=False)

    def close(self) -> None:
        for handle in self._handles:
            try:
                os.close(handle)
            except OSError:
                pass

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "guard_evidence_passed": True,
            "no_write_contract": True,
            "filesystem_write_proof": False,
            "guard_identity": self.identity,
        }


@dataclass
class RepositoryGuardResult(CheckResult):
    guard: RepositoryGuard | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        payload["guard"] = (
            None if self.guard is None else self.guard.to_public_dict()
        )
        return payload


def _failure(status: str, rule_id: str, message: str) -> RepositoryGuardResult:
    severity = "block" if status == "blocked" else "error"
    return RepositoryGuardResult(
        status=status,
        findings=[Finding(rule_id, severity, status, message)],
        next_action="Use a direct, contained repository with supported Git metadata.",
    )


def _is_reparse(info: os.stat_result) -> bool:
    return bool(getattr(info, "st_file_attributes", 0) & _REPARSE_POINT)


def _regular_file(path: Path) -> os.stat_result | None:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return None
    if (
        not stat.S_ISREG(info.st_mode)
        or stat.S_ISLNK(info.st_mode)
        or _is_reparse(info)
        or info.st_nlink != 1
    ):
        raise ValueError("unsafe metadata file")
    return info


def _directory(path: Path) -> os.stat_result:
    info = path.lstat()
    if (
        not stat.S_ISDIR(info.st_mode)
        or stat.S_ISLNK(info.st_mode)
        or _is_reparse(info)
    ):
        raise ValueError("unsafe metadata directory")
    return info


def _path_present(path: Path) -> bool:
    try:
        path.lstat()
        return True
    except FileNotFoundError:
        return False


def _assert_parent_chain(
    root: Path,
    path: Path,
    lock_directory: Any,
) -> None:
    if path != root and root not in path.parents:
        raise ValueError("root escape")
    current = path.parent
    while current != root:
        lock_directory(current)
        current = current.parent


def _same_identity(left: os.stat_result, right: os.stat_result) -> bool:
    return (
        stat.S_IFMT(left.st_mode) == stat.S_IFMT(right.st_mode)
        and int(left.st_dev) == int(right.st_dev)
        and int(left.st_ino) == int(right.st_ino)
        and int(left.st_nlink) == int(right.st_nlink)
        and int(left.st_size) == int(right.st_size)
    )


def _open_file(path: Path, expected: os.stat_result, handles: list[int]) -> tuple[int, os.stat_result]:
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOINHERIT", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    if os.name == "nt":
        import ctypes
        import msvcrt
        from ctypes import wintypes

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
            raise OSError("guard file handle unavailable")
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
            not _same_identity(expected, current)
            or not stat.S_ISREG(current.st_mode)
            or current.st_nlink != 1
        ):
            raise ValueError("guard file identity drift")
    except Exception:
        os.close(descriptor)
        raise
    handles.append(descriptor)
    return descriptor, current


def _read_file(
    descriptor: int,
    size: int,
    *,
    per_file_limit: int,
    budget: list[int],
) -> bytes:
    if size > per_file_limit or budget[0] + size > _MAX_CONTENT_BYTES:
        raise OverflowError("content budget")
    os.lseek(descriptor, 0, os.SEEK_SET)
    chunks: list[bytes] = []
    read_total = 0
    while read_total < size:
        chunk = os.read(descriptor, min(65_536, size - read_total))
        if not chunk:
            raise FileNotFoundError("short guarded read")
        read_total += len(chunk)
        budget[0] += len(chunk)
        if read_total > per_file_limit or budget[0] > _MAX_CONTENT_BYTES:
            raise OverflowError("content budget")
        chunks.append(chunk)
    if os.read(descriptor, 1):
        raise ValueError("guard file grew during read")
    return b"".join(chunks)


def _digest_bytes(raw: bytes) -> str:
    hasher = hashlib.sha256()
    hasher.update(raw)
    return hasher.hexdigest()


def _entry(
    root: Path,
    path: Path,
    info: os.stat_result,
    kind: str,
    digest: str,
) -> tuple[str, str, int, int, int, int, str]:
    logical = path.relative_to(root).as_posix()
    return (
        logical,
        kind,
        int(info.st_dev),
        int(info.st_ino),
        int(info.st_nlink),
        int(info.st_size),
        f"{int(info.st_mtime_ns)}:{digest}",
    )


def _scan_config(raw: bytes) -> bool:
    if b"\x00" in raw:
        return False
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        return False
    section = ""
    seen: set[tuple[str, str]] = set()
    for raw_line in text.splitlines():
        if raw_line.endswith("\\"):
            return False
        line = raw_line.strip()
        if not line or line.startswith(("#", ";")):
            continue
        section_match = _SECTION_RE.fullmatch(line)
        if section_match:
            section = section_match.group(1).lower()
            if section in {"include", "includeif"}:
                return False
            continue
        key_match = _KEY_RE.fullmatch(line)
        if not section or key_match is None:
            return False
        key = key_match.group(1).lower()
        identity = (section, key)
        dangerous = (
            section in {"alias", "pager", "credential"}
            or (section == "filter" and key in {"clean", "smudge", "process"})
            or (section == "diff" and (key == "external" or key == "command"))
            or (section == "merge" and key == "driver")
            or (section == "interactive" and key == "difffilter")
            or (
                section == "core"
                and key
                in {
                    "fsmonitor",
                    "hookspath",
                    "sshcommand",
                    "pager",
                    "alternaterefscommand",
                    "worktree",
                    "excludesfile",
                    "attributesfile",
                }
            )
        )
        if dangerous or identity in seen:
            return False
        seen.add(identity)
    return True


def _index_has_gitlink(raw: bytes) -> bool:
    return b"\x00\x00\xe0\x00" in raw


def build_repository_guard(root: Path) -> RepositoryGuardResult:
    """Build a bounded pre/post manifest without following Git metadata links."""
    try:
        selector = root.lstat()
        if stat.S_ISLNK(selector.st_mode) or _is_reparse(selector):
            return _failure(
                "blocked",
                "execution.repository-containment-blocked",
                "The repository selector is not a direct directory.",
            )
        root = root.resolve(strict=True)
    except (OSError, RuntimeError):
        return _failure(
            "validation_failed",
            "execution.repository-root-invalid",
            "The project root could not be validated.",
        )
    try:
        _directory(root)
        project_marker = _regular_file(root / "pyproject.toml")
        _directory(root / "agent_runtime")
    except (OSError, ValueError):
        project_marker = None
    if project_marker is None:
        return _failure(
            "validation_failed",
            "execution.repository-root-invalid",
            "The project root is missing required project markers.",
        )
    git = root / ".git"
    if git.is_file():
        return _failure(
            "blocked",
            "execution.repository-indirection-blocked",
            "Linked worktree Git indirection is not supported.",
        )
    try:
        _directory(git)
    except (OSError, ValueError):
        return _failure(
            "blocked",
            "execution.repository-containment-blocked",
            "Git metadata is not a direct contained directory.",
        )
    for relative, rule_id in _BLOCKED_SURFACES:
        if _path_present(root / relative):
            return _failure(
                "blocked",
                rule_id,
                "The repository uses a Git metadata surface unavailable to v1.",
            )
    modules = git / "modules"
    if _path_present(modules):
        return _failure(
            "blocked",
            "execution.submodule-surface-blocked",
            "Submodule metadata is unavailable to v1.",
        )
    entries: list[tuple[str, str, int, int, int, int, str]] = []
    budget = [0]
    path_bytes = 0
    handles: list[int] = []
    locked_directories: set[str] = set()

    def lock_directory(path: Path) -> os.stat_result:
        key = os.path.normcase(str(path))
        info = _directory(path)
        if key in locked_directories:
            return info
        flags = (
            os.O_RDONLY
            | getattr(os, "O_BINARY", 0)
            | getattr(os, "O_NOINHERIT", 0)
            | getattr(os, "O_DIRECTORY", 0)
            | getattr(os, "O_NOFOLLOW", 0)
        )
        if os.name == "nt":
            import ctypes
            import msvcrt
            from ctypes import wintypes

            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.CreateFileW.restype = wintypes.HANDLE
            native = kernel32.CreateFileW(
                str(path),
                0x00000080,
                0x00000001,
                None,
                3,
                0x02000000 | 0x00200000,
                None,
            )
            if native == wintypes.HANDLE(-1).value:
                raise OSError("guard directory handle unavailable")
            try:
                descriptor = msvcrt.open_osfhandle(int(native), flags)
            except Exception:
                kernel32.CloseHandle(native)
                raise
        else:
            descriptor = os.open(path, flags)
        current = os.fstat(descriptor)
        if not _same_identity(info, current) or not stat.S_ISDIR(current.st_mode):
            os.close(descriptor)
            raise ValueError("guard directory identity drift")
        handles.append(descriptor)
        locked_directories.add(key)
        return current

    try:
        lock_directory(root)
        lock_directory(git)
        for relative in _CRITICAL_FILES:
            path = root / relative
            if not _path_present(path):
                continue
            _assert_parent_chain(root, path, lock_directory)
            info = _regular_file(path)
            if info is None:
                raise FileNotFoundError
            descriptor, current = _open_file(path, info, handles)
            limit = _MAX_CONFIG_BYTES if path.name.startswith("config") else _MAX_CONTENT_BYTES
            raw = _read_file(
                descriptor,
                current.st_size,
                per_file_limit=limit,
                budget=budget,
            )
            if path.name.endswith(".lock"):
                for handle in handles:
                    os.close(handle)
                return _failure(
                    "blocked",
                    "execution.repository-lock-present",
                    "A Git metadata lock is present.",
                )
            if path.name.startswith("config") and not _scan_config(raw):
                for handle in handles:
                    os.close(handle)
                return _failure(
                    "blocked",
                    "execution.repository-config-blocked",
                    "Repository config uses a blocked or unsupported surface.",
                )
            if relative == ".git/index" and _index_has_gitlink(raw):
                for handle in handles:
                    os.close(handle)
                return _failure(
                    "blocked",
                    "execution.submodule-surface-blocked",
                    "The Git index contains a submodule entry.",
                )
            digest = _digest_bytes(raw)
            entries.append(_entry(root, path, current, "file", digest))
        for lock in (git / "index.lock", git / "HEAD.lock", git / "config.lock", git / "packed-refs.lock"):
            if _path_present(lock):
                for handle in handles:
                    os.close(handle)
                return _failure(
                    "blocked",
                    "execution.repository-lock-present",
                    "A Git metadata lock is present.",
                )
        for relative in _TRAVERSE_DIRS:
            base = root / relative
            if not _path_present(base):
                continue
            _assert_parent_chain(root, base, lock_directory)
            lock_directory(base)
            stack = [(base, 0)]
            while stack:
                directory, depth = stack.pop()
                if depth > _MAX_DEPTH:
                    raise OverflowError("depth")
                directory_info = lock_directory(directory)
                entries.append(_entry(root, directory, directory_info, "directory", ""))
                with os.scandir(directory) as iterator:
                    children = sorted(iterator, key=lambda item: item.name)
                for child in children:
                    path = Path(child.path)
                    path_bytes += len(path.relative_to(root).as_posix().encode("utf-8"))
                    if (
                        len(entries) >= _MAX_ENTRIES
                        or path_bytes > _MAX_PATH_BYTES
                    ):
                        raise OverflowError("entry budget")
                    info = child.stat(follow_symlinks=False)
                    if (
                        child.is_symlink()
                        or _is_reparse(info)
                        or child.name.endswith(".lock")
                    ):
                        raise ValueError("unsafe traversal entry")
                    if stat.S_ISDIR(info.st_mode):
                        stack.append((path, depth + 1))
                    elif stat.S_ISREG(info.st_mode) and info.st_nlink == 1:
                        descriptor, current = _open_file(path, info, handles)
                        raw = _read_file(
                            descriptor,
                            current.st_size,
                            per_file_limit=_MAX_CONTENT_BYTES,
                            budget=budget,
                        )
                        entries.append(
                            _entry(root, path, current, "file", _digest_bytes(raw))
                        )
                    else:
                        raise ValueError("unsafe traversal entry")
    except FileNotFoundError:
        for handle in handles:
            os.close(handle)
        return _failure(
            "blocked",
            "execution.repository-guard-drift",
            "Git metadata changed during guard inspection.",
        )
    except (OSError, ValueError):
        for handle in handles:
            os.close(handle)
        return _failure(
            "blocked",
            "execution.repository-containment-blocked",
            "Git metadata containment could not be proven.",
        )
    except OverflowError:
        for handle in handles:
            os.close(handle)
        return _failure(
            "blocked",
            "execution.repository-guard-bounds-exceeded",
            "Git metadata exceeds the bounded v1 guard.",
        )
    canonical = json.dumps(sorted(entries), ensure_ascii=False, separators=(",", ":"))
    identity = "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return RepositoryGuardResult(
        status="pass",
        guard=RepositoryGuard(
            identity=identity,
            manifest=tuple(sorted(entries)),
            _handles=tuple(handles),
        ),
        next_action="Keep this guard for the post-run identity comparison.",
    )


def compare_repository_guards(
    before: RepositoryGuard,
    after: RepositoryGuard,
) -> CheckResult:
    if before.identity != after.identity or before.manifest != after.manifest:
        return CheckResult(
            status="blocked",
            findings=[
                Finding(
                    "execution.repository-guard-drift",
                    "block",
                    "blocked",
                    "Critical Git metadata changed during execution.",
                )
            ],
            next_action="Inspect the repository before retrying.",
        )
    return CheckResult(
        status="pass",
        next_action="Repository guard evidence is unchanged.",
    )
