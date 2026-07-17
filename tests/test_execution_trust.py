from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest

from agent_runtime.execution_trust import (
    ExecutableIdentity,
    create_execution_trust_binding,
    load_execution_trust_binding,
    sanitize_path,
    verify_execution_trust,
)
from agent_runtime.execution_trust import _authenticode_thumbprint


def _identity(path: Path) -> ExecutableIdentity:
    return ExecutableIdentity(
        canonical_path=path,
        approved_root=path.parents[1],
        sha256="a" * 64,
        file_identity="volume-1:file-2",
        publisher_thumbprint="B" * 40,
        owner_policy="windows-system-install",
    )


class FakeBackend:
    platform = "windows"

    def __init__(self, identity: ExecutableIdentity) -> None:
        self.identity = identity
        self.closed = False

    def discover(self, root: Path, path_value: str | None = None) -> ExecutableIdentity:
        return self.identity

    def acquire_verified(
        self, binding: dict[str, object], root: Path
    ) -> ExecutableIdentity:
        return self.identity


def test_sanitize_path_drops_unsafe_entries_and_is_deterministic(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    system = tmp_path / "System"
    system.mkdir()
    local = root / "bin"
    local.mkdir()

    result = sanitize_path(
        os.pathsep.join(
            [
                "",
                ".",
                "relative",
                str(local),
                str(system),
                str(system),
                str(tmp_path / "missing"),
            ]
        ),
        root,
        platform="windows",
        canonicalize=lambda path: system if path.name.lower() == "system" else path,
        allow_directory=lambda path: path == system,
    )

    assert result.directories == (system,)
    assert result.serialized == str(system)
    assert result.identity.startswith("sha256:")
    assert str(local) not in result.serialized


def test_sanitize_path_can_remove_actor_writable_directories(
    tmp_path: Path,
) -> None:
    root = tmp_path / "project"
    root.mkdir()
    trusted = tmp_path / "trusted"
    writable = tmp_path / "writable"
    trusted.mkdir()
    writable.mkdir()

    result = sanitize_path(
        os.pathsep.join([str(writable), str(trusted)]),
        root,
        platform="windows",
        allow_directory=lambda path: path == trusted,
    )

    assert result.directories == (trusted,)
    assert str(writable) not in result.serialized


def test_binding_create_requires_commit_and_never_writes_project(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    executable = tmp_path / "Program Files" / "Git" / "cmd" / "git.exe"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"git")
    binding_path = tmp_path / "local-app" / "execution-trust-v1.json"
    backend = FakeBackend(_identity(executable))

    preview = create_execution_trust_binding(
        root,
        expected_sha256="a" * 64,
        expected_publisher_thumbprint="B" * 40,
        commit=False,
        binding_path=binding_path,
        backend=backend,
    )
    assert preview.status == "pass"
    assert preview.committed is False
    assert not binding_path.exists()

    committed = create_execution_trust_binding(
        root,
        expected_sha256="a" * 64,
        expected_publisher_thumbprint="B" * 40,
        commit=True,
        binding_path=binding_path,
        backend=backend,
    )
    assert committed.status == "pass"
    assert committed.committed is True
    assert binding_path.is_file()
    assert not any(root.iterdir())
    payload = json.loads(binding_path.read_text(encoding="utf-8"))
    assert payload["reviewer"]["actor"] == "local-operator"
    assert payload["executable"]["canonical_path"] == str(executable)
    assert committed.to_dict().get("canonical_path") is None


def test_binding_location_rejects_project_overlap(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    executable = tmp_path / "Program Files" / "Git" / "cmd" / "git.exe"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"git")

    result = create_execution_trust_binding(
        root,
        expected_sha256="a" * 64,
        expected_publisher_thumbprint="B" * 40,
        commit=True,
        binding_path=root / "binding.json",
        backend=FakeBackend(_identity(executable)),
    )

    assert result.status == "error"
    assert not (root / "binding.json").exists()


def test_binding_rejects_unreviewed_values_and_existing_file(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    executable = tmp_path / "Program Files" / "Git" / "cmd" / "git.exe"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"git")
    binding_path = tmp_path / "binding.json"
    backend = FakeBackend(_identity(executable))

    mismatch = create_execution_trust_binding(
        root,
        expected_sha256="c" * 64,
        expected_publisher_thumbprint="B" * 40,
        commit=True,
        binding_path=binding_path,
        backend=backend,
    )
    assert mismatch.status == "blocked"
    assert mismatch.findings[0].rule_id == "execution-trust-review-mismatch"
    assert not binding_path.exists()

    binding_path.write_text("{}", encoding="utf-8")
    existing = create_execution_trust_binding(
        root,
        expected_sha256="a" * 64,
        expected_publisher_thumbprint="B" * 40,
        commit=True,
        binding_path=binding_path,
        backend=backend,
    )
    assert existing.status == "blocked"
    assert existing.findings[0].rule_id == "execution-trust-binding-exists"


def test_binding_replace_requires_explicit_flag_and_revalidates(
    tmp_path: Path,
) -> None:
    root = tmp_path / "project"
    root.mkdir()
    executable = tmp_path / "Program Files" / "Git" / "cmd" / "git.exe"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"git")
    binding_path = tmp_path / "binding.json"
    first = _identity(executable)
    created = create_execution_trust_binding(
        root,
        expected_sha256=first.sha256,
        expected_publisher_thumbprint=first.publisher_thumbprint,
        commit=True,
        binding_path=binding_path,
        backend=FakeBackend(first),
    )
    assert created.committed is True
    rotated = ExecutableIdentity(
        canonical_path=executable,
        approved_root=first.approved_root,
        sha256="d" * 64,
        file_identity="volume-1:file-3",
        publisher_thumbprint=first.publisher_thumbprint,
        owner_policy=first.owner_policy,
        path_identity="sha256:" + "9" * 64,
    )

    result = create_execution_trust_binding(
        root,
        expected_sha256=rotated.sha256,
        expected_publisher_thumbprint=rotated.publisher_thumbprint,
        commit=True,
        replace=True,
        binding_path=binding_path,
        backend=FakeBackend(rotated),
    )

    assert result.status == "pass"
    assert result.committed is True
    loaded = load_execution_trust_binding(binding_path)
    assert loaded.status == "pass"
    assert loaded.binding is not None
    assert loaded.binding["executable"]["sha256"] == rotated.sha256
    assert loaded.path_identity == rotated.path_identity


@pytest.mark.parametrize(
    "raw",
    [
        b"\xff",
        b'{"schema_version":"execution-trust-binding/v1","schema_version":"x"}',
        b"{}",
    ],
)
def test_binding_loader_is_strict_and_value_safe(tmp_path: Path, raw: bytes) -> None:
    path = tmp_path / "binding.json"
    path.write_bytes(raw)

    result = load_execution_trust_binding(path)

    assert result.status == "validation_failed"
    rendered = json.dumps(result.to_dict())
    assert str(path) not in rendered
    decoded = raw.decode("utf-8", errors="ignore")
    if decoded:
        assert decoded not in rendered


def test_verify_detects_identity_drift_without_revealing_path(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    executable = tmp_path / "Program Files" / "Git" / "cmd" / "git.exe"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"git")
    binding_path = tmp_path / "binding.json"
    original = _identity(executable)
    create_execution_trust_binding(
        root,
        expected_sha256=original.sha256,
        expected_publisher_thumbprint=original.publisher_thumbprint,
        commit=True,
        binding_path=binding_path,
        backend=FakeBackend(original),
    )
    drifted = ExecutableIdentity(
        canonical_path=executable,
        approved_root=original.approved_root,
        sha256="d" * 64,
        file_identity=original.file_identity,
        publisher_thumbprint=original.publisher_thumbprint,
        owner_policy=original.owner_policy,
    )

    result = verify_execution_trust(
        root,
        binding_path=binding_path,
        backend=FakeBackend(drifted),
    )

    assert result.status == "blocked"
    assert result.findings[0].rule_id == "execution-trust-identity-drift"
    assert str(executable) not in json.dumps(result.to_dict())


@pytest.mark.skipif(os.name != "nt" or shutil.which("git") is None, reason="signed Windows Git required")
def test_windows_authenticode_signer_thumbprint_is_extractable() -> None:
    thumbprint = _authenticode_thumbprint(Path(shutil.which("git") or ""))

    assert len(thumbprint) == 40
    assert all(char in "0123456789ABCDEF" for char in thumbprint)
