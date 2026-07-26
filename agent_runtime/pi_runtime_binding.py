"""Review-bound local identity records for the Pi Node runtime chain.

This module never executes Node, Pi, npm, npx, or package scripts.  It only
hashes explicitly reviewed regular files before creating a machine-local record.
"""
from __future__ import annotations

import hashlib
import json
import os
import stat
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .result import CheckResult, Finding

_SCHEMA_VERSION = "pi-runtime-binding/v1"
_MAX_FILES = 2_048
_MAX_BYTES = 64 * 1024 * 1024
_MAX_RECORD_BYTES = 512 * 1024


def _finding(rule_id: str, message: str, *, blocked: bool = False) -> Finding:
    return Finding(rule_id, "block" if blocked else "error", "blocked" if blocked else "validation_failed", message)


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(64 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _default_path() -> Path:
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        raise OSError("local application data unavailable")
    return Path(local) / "agent-runtime" / "pi-runtime-binding-v1.json"


def _regular(path: Path) -> Path:
    resolved = path.resolve(strict=True)
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or path.is_symlink() or resolved != path.absolute():
        raise ValueError("unsafe file")
    return resolved


def _closure(root: Path) -> tuple[list[dict[str, object]], str]:
    root = root.resolve(strict=True)
    info = root.lstat()
    if not stat.S_ISDIR(info.st_mode) or root.is_symlink():
        raise ValueError("unsafe module root")
    entries: list[dict[str, object]] = []
    total = 0
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        if path.is_dir():
            if path.is_symlink():
                raise ValueError("reparse directory")
            continue
        resolved = _regular(path)
        if root not in resolved.parents:
            raise ValueError("module escape")
        size = resolved.stat().st_size
        total += size
        if len(entries) >= _MAX_FILES or total > _MAX_BYTES:
            raise ValueError("closure bounds")
        entries.append({"path": resolved.relative_to(root).as_posix(), "bytes": size, "sha256": _sha256_file(resolved)})
    if not entries:
        raise ValueError("empty closure")
    return entries, "sha256:" + hashlib.sha256(_canonical(entries)).hexdigest()


@dataclass
class PiRuntimeBindingResult(CheckResult):
    binding: dict[str, Any] | None = None
    binding_id: str | None = None
    closure_identity: str | None = None
    committed: bool = False

    def to_dict(self) -> dict[str, Any]:
        result = super().to_dict()
        for key in ("binding_id", "closure_identity"):
            value = getattr(self, key)
            if value:
                result[key] = value
        result["committed"] = self.committed
        return result


def _read(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    if len(raw) > _MAX_RECORD_BYTES or b"\0" in raw:
        raise ValueError("binding bounds")
    value = json.loads(raw.decode("utf-8"))
    if not isinstance(value, dict) or value.get("schema_version") != _SCHEMA_VERSION:
        raise ValueError("binding schema")
    claimed = value.get("binding_id")
    canonical = dict(value)
    canonical.pop("binding_id", None)
    expected = "sha256:" + hashlib.sha256(_canonical(canonical)).hexdigest()
    if claimed != expected:
        raise ValueError("binding identity")
    return value


def inspect_pi_runtime_binding(*, binding_path: Path | None = None) -> PiRuntimeBindingResult:
    try:
        binding = _read(binding_path or _default_path())
    except FileNotFoundError:
        return PiRuntimeBindingResult(status="blocked", findings=[_finding("pi-runtime-binding-missing", "No reviewed Pi runtime binding exists.", blocked=True)], next_action="Create a reviewed Pi runtime binding before enabling bound mode.")
    except (OSError, UnicodeDecodeError, ValueError, json.JSONDecodeError):
        return PiRuntimeBindingResult(status="validation_failed", findings=[_finding("pi-runtime-binding-invalid", "The Pi runtime binding is invalid.")], next_action="Recreate the reviewed Pi runtime binding.")
    return PiRuntimeBindingResult(status="pass", binding=binding, binding_id=binding["binding_id"], closure_identity=binding["closure_identity"], next_action="This record is binding-only; existing Pi execution remains unbound.")


def create_pi_runtime_binding(
    *, node_path: Path, cli_entry: Path, module_roots: Iterable[Path], commit: bool, replace: bool = False,
    expected_binding_id: str | None = None, binding_path: Path | None = None,
) -> PiRuntimeBindingResult:
    """Preview or atomically create a reviewed local binding without execution."""
    target = binding_path or _default_path()
    try:
        node = _regular(node_path)
        entry = _regular(cli_entry)
        roots = tuple(sorted({root.resolve(strict=True) for root in module_roots}, key=lambda item: str(item).casefold()))
        if not roots or not any(root == entry.parent or root in entry.parents for root in roots):
            raise ValueError("entry outside closure")
        modules: list[dict[str, object]] = []
        for root in roots:
            files, identity = _closure(root)
            modules.append({"root": str(root), "identity": identity, "files": files})
        closure_identity = "sha256:" + hashlib.sha256(_canonical(modules)).hexdigest()
    except (OSError, RuntimeError, ValueError):
        return PiRuntimeBindingResult(status="blocked", findings=[_finding("pi-runtime-binding-candidate-invalid", "Reviewed Node, CLI entry, or module closure is invalid.", blocked=True)], next_action="Provide regular contained files and finite module roots.")
    record: dict[str, Any] = {
        "schema_version": _SCHEMA_VERSION,
        "platform": "windows",
        "node": {"path": str(node), "sha256": _sha256_file(node)},
        "cli_entry": {"path": str(entry), "sha256": _sha256_file(entry)},
        "modules": modules,
        "closure_identity": closure_identity,
        "reviewer": {"actor": "local-operator", "reviewed_at": datetime.now(timezone.utc).isoformat(), "provenance": "explicit-cli-review"},
    }
    record["binding_id"] = "sha256:" + hashlib.sha256(_canonical(record)).hexdigest()
    if target.exists():
        existing = inspect_pi_runtime_binding(binding_path=target)
        if not replace:
            return PiRuntimeBindingResult(status="blocked", findings=[_finding("pi-runtime-binding-exists", "A Pi runtime binding already exists.", blocked=True)], next_action="Use explicit --replace after reviewing the current binding identity.")
        if existing.status != "pass" or expected_binding_id != existing.binding_id:
            return PiRuntimeBindingResult(status="blocked", findings=[_finding("pi-runtime-binding-rotation-review-required", "Binding rotation requires the current reviewed binding identity.", blocked=True)])
    result = PiRuntimeBindingResult(status="pass", binding=record, binding_id=record["binding_id"], closure_identity=closure_identity, next_action="Review identities and use --commit to persist this binding-only record.")
    if not commit:
        return result
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and not replace:
            raise FileExistsError(target)
        with tempfile.NamedTemporaryFile("wb", dir=target.parent, prefix=".pi-runtime-binding-", delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(_canonical(record))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
    except OSError:
        return PiRuntimeBindingResult(status="error", findings=[_finding("pi-runtime-binding-write-failed", "The reviewed Pi runtime binding could not be persisted.")])
    result.committed = True
    result.next_action = "Binding recorded; no Pi runner behavior has changed."
    return result
