from __future__ import annotations

import json
import os
import shutil
import inspect
from pathlib import Path

import pytest

from agent_runtime.execution_trust import (
    ExecutableIdentity,
    load_execution_trust_binding,
    sanitize_path,
    verify_execution_trust,
)
from agent_runtime.execution_trust import (
    _authenticode_thumbprint,
    _create_execution_trust_binding_for_test as create_execution_trust_binding,
    _create_execution_trust_binding_core,
)
import agent_runtime.execution_trust as execution_trust
from agent_runtime.execution_lease import (
    ExecutionLeaseResult,
    _LeaseCapability,
    _PortableLeaseBackend,
    _acquire_execution_lease_for_test,
    _inspect_execution_lease_for_test,
)


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


class CandidateUnavailableBackend:
    platform = "windows"

    def discover(self, root: Path, path_value: str | None = None) -> ExecutableIdentity:
        raise ValueError("unsafe candidate detail")


class FakeLease:
    status = "pass"
    findings: list[object] = []
    next_action = None

    def __init__(self, calls: list[str]) -> None:
        self.calls = calls

    def release(self) -> None:
        self.calls.append("lease-release")


def _test_lease(root: Path, calls: list[str] | None = None):
    if calls is not None:
        calls.append("lease-acquire")
    lease = _acquire_execution_lease_for_test(
        root,
        lease_path=root.parent / "lease-local" / "execution-lease-v1.lock",
        backend=_PortableLeaseBackend(),
    )
    if calls is not None:
        release = lease.release

        def tracked_release():
            result = release()
            calls.append("lease-release")
            return result

        lease.release = tracked_release
    return lease


@pytest.fixture(autouse=True)
def _fake_production_lease(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        execution_trust,
        "acquire_execution_lease",
        _test_lease,
    )


def test_public_trust_binding_api_has_no_lease_bypass() -> None:
    parameters = inspect.signature(
        execution_trust.create_execution_trust_binding
    ).parameters

    assert "lease_path" not in parameters
    assert "lease_backend" not in parameters
    assert "lease_acquire" not in parameters
    assert "_lease_held" not in parameters
    assert "binding_path" not in parameters
    assert "backend" not in parameters
    assert "expected_binding_id" in parameters
    assert "expected_executable_identity" in parameters
    assert "expected_path_identity" in parameters


def test_trust_mutation_core_rejects_missing_lease_capability(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    executable = tmp_path / "Program Files" / "Git" / "cmd" / "git.exe"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"git")
    binding_path = tmp_path / "binding.json"

    result = _create_execution_trust_binding_core(
        root,
        expected_sha256="a" * 64,
        expected_publisher_thumbprint="B" * 40,
        commit=True,
        replace=False,
        binding_path=binding_path,
        backend=FakeBackend(_identity(executable)),
        lease_capability=None,
    )

    assert result.status == "error"
    assert result.findings[0].rule_id == "execution-lease-capability-invalid"
    assert not binding_path.exists()


def test_trust_core_rejects_manually_constructed_unlocked_capability(
    tmp_path: Path,
) -> None:
    root = tmp_path / "project"
    root.mkdir()
    executable = tmp_path / "Program Files" / "Git" / "cmd" / "git.exe"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"git")
    binding_path = tmp_path / "binding.json"
    synthetic = ExecutionLeaseResult(status="pass", lease_state="active")
    path = tmp_path / "ordinary-file"
    descriptor = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    synthetic.native_handle = descriptor
    capability = _LeaseCapability(synthetic)

    result = _create_execution_trust_binding_core(
        root,
        expected_sha256="a" * 64,
        expected_publisher_thumbprint="B" * 40,
        commit=True,
        replace=False,
        binding_path=binding_path,
        backend=FakeBackend(_identity(executable)),
        lease_capability=capability,
    )

    assert result.status == "error"
    assert result.findings[0].rule_id == "execution-lease-capability-invalid"
    assert not binding_path.exists()
    os.close(descriptor)

def test_sanitize_path_drops_unsafe_entries_and_is_deterministic(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    system = tmp_path / "System"
    system.mkdir()
    local = root / "bin"
    local.mkdir()

    result = sanitize_path(
        ";".join(
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
        ";".join([str(writable), str(trusted)]),
        root,
        platform="windows",
        allow_directory=lambda path: path == trusted,
    )

    assert result.directories == (trusted,)
    assert str(writable) not in result.serialized


def test_binding_create_requires_commit_and_never_writes_project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "project"
    root.mkdir()
    executable = tmp_path / "Program Files" / "Git" / "cmd" / "git.exe"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"git")
    binding_path = tmp_path / "local-app" / "execution-trust-v1.json"
    backend = FakeBackend(_identity(executable))
    created = None
    calls: list[str] = []

    def acquire_lease(root: Path) -> FakeLease:
        return _test_lease(root, calls)

    monkeypatch.setattr(execution_trust, "acquire_execution_lease", acquire_lease)

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
    assert calls == []

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
    assert calls == ["lease-acquire", "lease-release"]


@pytest.mark.parametrize("replace", [False, True])
def test_committed_binding_remains_committed_when_final_lease_release_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    replace: bool,
) -> None:
    root = tmp_path / "project"
    root.mkdir()
    executable = tmp_path / "Program Files" / "Git" / "cmd" / "git.exe"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"git")
    binding_path = tmp_path / "binding.json"
    backend = FakeBackend(_identity(executable))
    created = None
    if replace:
        created = create_execution_trust_binding(
            root,
            expected_sha256="a" * 64,
            expected_publisher_thumbprint="B" * 40,
            commit=True,
            binding_path=binding_path,
            backend=backend,
        )
        assert created.committed is True

    class CloseFailureBackend(_PortableLeaseBackend):
        def close(self, handle: int) -> None:
            raise OSError("unsafe raw detail")

    monkeypatch.setattr(
        execution_trust,
        "acquire_execution_lease",
        lambda project: _acquire_execution_lease_for_test(
            project,
            lease_path=tmp_path / "failing-lease" / "execution-lease-v1.lock",
            backend=CloseFailureBackend(),
        ),
    )

    result = create_execution_trust_binding(
        root,
        expected_sha256="a" * 64,
        expected_publisher_thumbprint="B" * 40,
        commit=True,
        replace=replace,
        expected_binding_id=created.binding_id if created is not None else None,
        expected_executable_identity=(
            execution_trust._identity_digest(backend.identity) if replace else None
        ),
        expected_path_identity=backend.identity.path_identity if replace else None,
        binding_path=binding_path,
        backend=backend,
    )

    assert result.status == "error"
    assert result.committed is True
    assert result.findings[0].rule_id == "execution-lease-release-failed"
    assert binding_path.is_file()


def test_committed_binding_remains_committed_when_final_lease_validation_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "project"
    root.mkdir()
    executable = tmp_path / "Program Files" / "Git" / "cmd" / "git.exe"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"git")
    binding_path = tmp_path / "binding.json"
    backend = FakeBackend(_identity(executable))
    lease = _test_lease(root)
    monkeypatch.setattr(lease, "validate", lambda: False)
    monkeypatch.setattr(execution_trust, "acquire_execution_lease", lambda project: lease)

    result = create_execution_trust_binding(
        root,
        expected_sha256="a" * 64,
        expected_publisher_thumbprint="B" * 40,
        commit=True,
        binding_path=binding_path,
        backend=backend,
    )

    assert result.status == "error"
    assert result.committed is True
    assert result.findings[0].rule_id == "execution-lease-identity-drift"
    assert binding_path.is_file()


def test_trust_wrapper_releases_after_unexpected_core_exception(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "project"
    root.mkdir()
    lease = _test_lease(root)
    release = lease.release
    released = {"value": False}

    def tracked_release():
        released["value"] = True
        return release()

    monkeypatch.setattr(lease, "release", tracked_release)
    monkeypatch.setattr(execution_trust, "acquire_execution_lease", lambda project: lease)
    monkeypatch.setattr(
        execution_trust,
        "_create_execution_trust_binding_core",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("raw core detail")),
    )

    result = create_execution_trust_binding(
        root,
        expected_sha256="a" * 64,
        expected_publisher_thumbprint="B" * 40,
        commit=True,
    )

    assert result.status == "error"
    assert released["value"] is True
    assert result.findings[0].rule_id == "execution-trust-core-failed"
    assert "raw core detail" not in json.dumps(result.to_dict())
    reacquired = _test_lease(root)
    assert reacquired.status == "pass"
    reacquired.release()


@pytest.mark.parametrize("core_raises", [False, True])
def test_trust_wrapper_releases_when_validation_raises(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    core_raises: bool,
) -> None:
    root = tmp_path / "project"
    root.mkdir()
    executable = tmp_path / "Program Files" / "Git" / "cmd" / "git.exe"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"git")
    binding_path = tmp_path / "binding.json"
    lease = _test_lease(root)
    release = lease.release
    released = {"value": False}

    def validate():
        raise TypeError("raw validate detail")

    def tracked_release():
        released["value"] = True
        return release()

    monkeypatch.setattr(lease, "validate", validate)
    monkeypatch.setattr(lease, "release", tracked_release)
    monkeypatch.setattr(execution_trust, "acquire_execution_lease", lambda project: lease)
    if core_raises:
        monkeypatch.setattr(
            execution_trust,
            "_create_execution_trust_binding_core",
            lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("raw core detail")),
        )

    result = create_execution_trust_binding(
        root,
        expected_sha256="a" * 64,
        expected_publisher_thumbprint="B" * 40,
        commit=True,
        binding_path=binding_path,
        backend=FakeBackend(_identity(executable)),
    )

    assert result.status == "error"
    assert released["value"] is True
    assert "execution-lease-validation-failed" in [
        finding.rule_id for finding in result.findings
    ]
    assert "raw validate detail" not in json.dumps(result.to_dict())
    if not core_raises:
        assert result.committed is True


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
        expected_binding_id=created.binding_id,
        expected_executable_identity=execution_trust._identity_digest(rotated),
        expected_path_identity=rotated.path_identity,
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


def test_replace_commit_requires_all_review_identities_before_lease(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "project"
    root.mkdir()
    monkeypatch.setattr(
        execution_trust,
        "acquire_execution_lease",
        lambda project: (_ for _ in ()).throw(AssertionError("lease acquired")),
    )

    result = create_execution_trust_binding(
        root,
        expected_sha256="a" * 64,
        expected_publisher_thumbprint="B" * 40,
        expected_binding_id=None,
        expected_executable_identity="sha256:" + "c" * 64,
        expected_path_identity="sha256:" + "d" * 64,
        replace=True,
        commit=True,
    )

    assert result.status == "validation_failed"
    assert result.findings[0].rule_id == "execution-trust-rotation-review-required"


def test_replace_commit_rechecks_old_binding_before_candidate_discovery(
    tmp_path: Path,
) -> None:
    root = tmp_path / "project"
    root.mkdir()
    executable = tmp_path / "Git" / "git.exe"
    executable.parent.mkdir()
    executable.write_bytes(b"git")
    binding_path = tmp_path / "binding.json"
    original = _identity(executable)
    created = create_execution_trust_binding(
        root,
        expected_sha256=original.sha256,
        expected_publisher_thumbprint=original.publisher_thumbprint,
        commit=True,
        binding_path=binding_path,
        backend=FakeBackend(original),
    )
    before = binding_path.read_bytes()

    class DiscoveryMustNotRun(FakeBackend):
        def discover(
            self, root: Path, path_value: str | None = None
        ) -> ExecutableIdentity:
            raise AssertionError("candidate discovery ran")

    result = create_execution_trust_binding(
        root,
        expected_sha256=original.sha256,
        expected_publisher_thumbprint=original.publisher_thumbprint,
        expected_binding_id="sha256:" + "f" * 64,
        expected_executable_identity=created.executable_identity,
        expected_path_identity=created.path_identity,
        replace=True,
        commit=True,
        binding_path=binding_path,
        backend=DiscoveryMustNotRun(original),
    )

    assert result.status == "blocked"
    assert result.findings[0].rule_id == "execution-trust-binding-review-mismatch"
    assert binding_path.read_bytes() == before


@pytest.mark.parametrize(
    ("expected_executable_identity", "expected_path_identity"),
    [
        ("sha256:" + "f" * 64, None),
        (None, "sha256:" + "f" * 64),
    ],
)
def test_replace_commit_requires_exact_candidate_identities(
    tmp_path: Path,
    expected_executable_identity: str | None,
    expected_path_identity: str | None,
) -> None:
    root = tmp_path / "project"
    root.mkdir()
    executable = tmp_path / "Git" / "git.exe"
    executable.parent.mkdir()
    executable.write_bytes(b"git")
    binding_path = tmp_path / "binding.json"
    original = _identity(executable)
    created = create_execution_trust_binding(
        root,
        expected_sha256=original.sha256,
        expected_publisher_thumbprint=original.publisher_thumbprint,
        commit=True,
        binding_path=binding_path,
        backend=FakeBackend(original),
    )
    candidate = _identity(executable)
    candidate.sha256 = "d" * 64
    candidate.path_identity = "sha256:" + "e" * 64

    result = create_execution_trust_binding(
        root,
        expected_sha256=candidate.sha256,
        expected_publisher_thumbprint=candidate.publisher_thumbprint,
        expected_binding_id=created.binding_id,
        expected_executable_identity=(
            expected_executable_identity or execution_trust._identity_digest(candidate)
        ),
        expected_path_identity=expected_path_identity or candidate.path_identity,
        replace=True,
        commit=True,
        binding_path=binding_path,
        backend=FakeBackend(candidate),
    )

    assert result.status == "blocked"
    assert result.findings[0].rule_id == "execution-trust-review-mismatch"


def test_reviewed_replace_commit_rotates_exact_candidate_under_lease(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "project"
    root.mkdir()
    executable = tmp_path / "Git" / "git.exe"
    executable.parent.mkdir()
    executable.write_bytes(b"git")
    binding_path = tmp_path / "binding.json"
    original = _identity(executable)
    created = create_execution_trust_binding(
        root,
        expected_sha256=original.sha256,
        expected_publisher_thumbprint=original.publisher_thumbprint,
        commit=True,
        binding_path=binding_path,
        backend=FakeBackend(original),
    )
    candidate = _identity(executable)
    candidate.sha256 = "d" * 64
    candidate.file_identity = "volume-1:file-3"
    candidate.path_identity = "sha256:" + "e" * 64
    calls: list[str] = []

    def acquire(project: Path):
        return _test_lease(project, calls)

    monkeypatch.setattr(execution_trust, "acquire_execution_lease", acquire)
    result = create_execution_trust_binding(
        root,
        expected_sha256=candidate.sha256,
        expected_publisher_thumbprint=candidate.publisher_thumbprint,
        expected_binding_id=created.binding_id,
        expected_executable_identity=execution_trust._identity_digest(candidate),
        expected_path_identity=candidate.path_identity,
        replace=True,
        commit=True,
        binding_path=binding_path,
        backend=FakeBackend(candidate),
    )

    assert result.status == "pass"
    assert result.committed is True
    assert result.executable_identity == execution_trust._identity_digest(candidate)
    assert result.path_identity == candidate.path_identity
    assert calls == ["lease-acquire", "lease-release"]


def test_replace_commit_preserves_valid_binding_replaced_during_discovery(
    tmp_path: Path,
) -> None:
    root = tmp_path / "project"
    root.mkdir()
    executable = tmp_path / "Git" / "git.exe"
    executable.parent.mkdir()
    executable.write_bytes(b"git")
    binding_path = tmp_path / "binding.json"
    adversarial_path = tmp_path / "adversarial.json"
    original = _identity(executable)
    created = create_execution_trust_binding(
        root,
        expected_sha256=original.sha256,
        expected_publisher_thumbprint=original.publisher_thumbprint,
        commit=True,
        binding_path=binding_path,
        backend=FakeBackend(original),
    )
    adversarial_identity = _identity(executable)
    adversarial_identity.sha256 = "c" * 64
    adversarial = create_execution_trust_binding(
        root,
        expected_sha256=adversarial_identity.sha256,
        expected_publisher_thumbprint=adversarial_identity.publisher_thumbprint,
        commit=True,
        binding_path=adversarial_path,
        backend=FakeBackend(adversarial_identity),
    )
    adversarial_bytes = adversarial_path.read_bytes()
    candidate = _identity(executable)
    candidate.sha256 = "d" * 64
    candidate.file_identity = "volume-1:file-3"
    candidate.path_identity = "sha256:" + "e" * 64
    close_calls = 0

    def close() -> None:
        nonlocal close_calls
        close_calls += 1

    candidate.close = close

    class ReplacingBackend(FakeBackend):
        def discover(
            self, root: Path, path_value: str | None = None
        ) -> ExecutableIdentity:
            os.replace(adversarial_path, binding_path)
            return self.identity

    result = create_execution_trust_binding(
        root,
        expected_sha256=candidate.sha256,
        expected_publisher_thumbprint=candidate.publisher_thumbprint,
        expected_binding_id=created.binding_id,
        expected_executable_identity=execution_trust._identity_digest(candidate),
        expected_path_identity=candidate.path_identity,
        replace=True,
        commit=True,
        binding_path=binding_path,
        backend=ReplacingBackend(candidate),
    )

    assert result.status in {"blocked", "error"}
    assert result.findings[0].rule_id == "execution-trust-binding-review-mismatch"
    assert result.committed is False
    assert binding_path.read_bytes() == adversarial_bytes
    assert load_execution_trust_binding(binding_path).binding_id == adversarial.binding_id
    assert close_calls == 1


def test_first_create_postwrite_load_exception_retains_candidate_for_inspection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "project"
    root.mkdir()
    executable = tmp_path / "Program Files" / "Git" / "cmd" / "git.exe"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"git")
    binding_path = tmp_path / "binding.json"
    monkeypatch.setattr(
        execution_trust,
        "load_execution_trust_binding",
        lambda *args, **kwargs: (_ for _ in ()).throw(TypeError("raw postload")),
    )

    result = create_execution_trust_binding(
        root,
        expected_sha256="a" * 64,
        expected_publisher_thumbprint="B" * 40,
        commit=True,
        binding_path=binding_path,
        backend=FakeBackend(_identity(executable)),
    )

    assert result.status == "error"
    assert result.committed is True
    assert result.rolled_back is False
    assert result.mutation_incomplete is True
    assert binding_path.is_file()
    assert "raw postload" not in json.dumps(result.to_dict())


def test_rotation_postwrite_load_exception_retains_candidate_for_inspection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "project"
    root.mkdir()
    executable = tmp_path / "Program Files" / "Git" / "cmd" / "git.exe"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"git")
    binding_path = tmp_path / "binding.json"
    original = _identity(executable)
    created = create_execution_trust_binding(
        root,
        expected_sha256=original.sha256,
        expected_publisher_thumbprint=original.publisher_thumbprint,
        commit=True,
        binding_path=binding_path,
        backend=FakeBackend(original),
    )
    assert created.committed is True
    previous = binding_path.read_bytes()
    real_load = execution_trust.load_execution_trust_binding
    calls = 0

    def fail_postload(*args: object, **kwargs: object):
        nonlocal calls
        calls += 1
        if calls > 1:
            raise TypeError("raw postload")
        return real_load(*args, **kwargs)

    monkeypatch.setattr(execution_trust, "load_execution_trust_binding", fail_postload)
    rotated = _identity(executable)
    rotated.sha256 = "d" * 64

    result = create_execution_trust_binding(
        root,
        expected_sha256=rotated.sha256,
        expected_publisher_thumbprint=rotated.publisher_thumbprint,
        commit=True,
        replace=True,
        expected_binding_id=created.binding_id,
        expected_executable_identity=execution_trust._identity_digest(rotated),
        expected_path_identity=rotated.path_identity,
        binding_path=binding_path,
        backend=FakeBackend(rotated),
    )

    assert result.status == "error"
    assert result.rolled_back is False
    assert result.committed is True
    assert result.mutation_incomplete is True
    assert binding_path.read_bytes() != previous


def test_postwrite_exception_does_not_rollback_concurrent_replacement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "project"
    root.mkdir()
    executable = tmp_path / "Program Files" / "Git" / "cmd" / "git.exe"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"git")
    binding_path = tmp_path / "binding.json"
    concurrent = b"concurrent replacement\n"

    def replace_then_raise(*args: object, **kwargs: object):
        replacement = binding_path.with_suffix(".concurrent")
        replacement.write_bytes(concurrent)
        os.replace(replacement, binding_path)
        raise TypeError("raw postload")

    monkeypatch.setattr(
        execution_trust, "load_execution_trust_binding", replace_then_raise
    )

    result = create_execution_trust_binding(
        root,
        expected_sha256="a" * 64,
        expected_publisher_thumbprint="B" * 40,
        commit=True,
        binding_path=binding_path,
        backend=FakeBackend(_identity(executable)),
    )

    assert result.status == "error"
    assert result.rolled_back is False
    assert result.mutation_incomplete is True
    assert result.committed is True
    assert binding_path.read_bytes() == concurrent
    assert "blind" not in (result.next_action or "").lower()


def test_postwrite_identity_capture_failure_preserves_unproven_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "project"
    root.mkdir()
    executable = tmp_path / "Program Files" / "Git" / "cmd" / "git.exe"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"git")
    binding_path = tmp_path / "binding.json"
    original_lstat = Path.lstat

    def fail_installed_binding_lstat(path: Path):
        if path == binding_path and path.is_file():
            raise OSError("raw identity failure")
        return original_lstat(path)

    monkeypatch.setattr(Path, "lstat", fail_installed_binding_lstat)

    result = create_execution_trust_binding(
        root,
        expected_sha256="a" * 64,
        expected_publisher_thumbprint="B" * 40,
        commit=True,
        binding_path=binding_path,
        backend=FakeBackend(_identity(executable)),
    )

    assert result.status == "error"
    assert result.committed is True
    assert result.rolled_back is False
    assert result.mutation_incomplete is True
    assert binding_path.is_file()
    assert "raw identity failure" not in json.dumps(result.to_dict())


def test_identity_close_exception_preserves_committed_binding_truth(
    tmp_path: Path,
) -> None:
    root = tmp_path / "project"
    root.mkdir()
    executable = tmp_path / "Program Files" / "Git" / "cmd" / "git.exe"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"git")
    binding_path = tmp_path / "binding.json"
    identity = _identity(executable)

    def fail_close() -> None:
        raise OSError("raw identity close")

    identity.close = fail_close
    result = create_execution_trust_binding(
        root,
        expected_sha256=identity.sha256,
        expected_publisher_thumbprint=identity.publisher_thumbprint,
        commit=True,
        binding_path=binding_path,
        backend=FakeBackend(identity),
    )

    assert result.status == "error"
    assert result.committed is True
    assert result.binding_id is not None
    assert result.findings[-1].rule_id == "execution-trust-identity-close-failed"
    assert binding_path.is_file()
    assert "raw identity close" not in json.dumps(result.to_dict())


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


def _inspect_for_test(
    root: Path,
    binding_path: Path,
    backend: object,
    *,
    lease_state: str = "available",
):
    return execution_trust._inspect_execution_trust_for_test(
        root,
        binding_path=binding_path,
        backend=backend,
        inspect_lease=lambda project: ExecutionLeaseResult(
            status="pass", lease_state=lease_state
        ),
    )


def test_trust_inspection_reports_missing_and_projects_candidate_review_identities(
    tmp_path: Path,
) -> None:
    root = tmp_path / "project"
    root.mkdir()
    executable = tmp_path / "Program Files" / "Git" / "cmd" / "git.exe"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"git")
    binding_path = tmp_path / "machine-local" / "binding.json"

    result = _inspect_for_test(
        root, binding_path, FakeBackend(_identity(executable))
    )

    assert result.status == "pass"
    assert result.state == "missing"
    assert result.binding_id is None
    assert result.executable_identity.startswith("sha256:")
    assert result.path_identity.startswith("sha256:")
    assert result.lease_state == "available"
    assert not binding_path.exists()


def test_trust_inspection_does_not_create_binding_or_lease(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    executable = tmp_path / "Git" / "git.exe"
    executable.parent.mkdir()
    executable.write_bytes(b"git")
    binding_path = tmp_path / "machine-local" / "binding.json"
    lease_path = tmp_path / "lease-local" / "execution-lease-v1.lock"

    result = execution_trust._inspect_execution_trust_for_test(
        root,
        binding_path=binding_path,
        backend=FakeBackend(_identity(executable)),
        inspect_lease=lambda project: _inspect_execution_lease_for_test(
            project,
            lease_path=lease_path,
            backend=_PortableLeaseBackend(),
        ),
    )

    assert result.status == "pass"
    assert result.state == "missing"
    assert result.lease_state == "available"
    assert not binding_path.exists()
    assert not lease_path.exists()


def test_trust_inspection_reports_current_without_revealing_sensitive_values(
    tmp_path: Path,
) -> None:
    root = tmp_path / "project"
    root.mkdir()
    executable = tmp_path / "Program Files" / "Git" / "cmd" / "git.exe"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"git")
    binding_path = tmp_path / "machine-local" / "binding.json"
    identity = _identity(executable)
    created = create_execution_trust_binding(
        root,
        expected_sha256=identity.sha256,
        expected_publisher_thumbprint=identity.publisher_thumbprint,
        commit=True,
        binding_path=binding_path,
        backend=FakeBackend(identity),
    )
    before = binding_path.read_bytes()

    result = _inspect_for_test(
        root, binding_path, FakeBackend(_identity(executable)), lease_state="active"
    )
    payload = result.to_dict()
    rendered = json.dumps(payload)

    assert result.status == "pass"
    assert result.state == "current"
    assert result.binding_id == created.binding_id
    assert result.lease_state == "active"
    assert payload["schema_version"] == "control-plane/execution-trust-inspection/v1"
    assert set(payload) <= {
        "schema_version",
        "status",
        "state",
        "checks",
        "findings",
        "next_action",
        "binding_id",
        "executable_identity",
        "path_identity",
        "lease_state",
    }
    for sensitive in (
        str(binding_path),
        str(executable),
        str(identity.approved_root),
        identity.publisher_thumbprint,
        "local-operator",
    ):
        assert sensitive not in rendered
    assert binding_path.read_bytes() == before


def test_trust_inspection_close_failure_withholds_current_projection(
    tmp_path: Path,
) -> None:
    root = tmp_path / "project"
    root.mkdir()
    executable = tmp_path / "Program Files" / "Git" / "cmd" / "git.exe"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"git")
    binding_path = tmp_path / "machine-local" / "binding.json"
    identity = _identity(executable)
    create_execution_trust_binding(
        root,
        expected_sha256=identity.sha256,
        expected_publisher_thumbprint=identity.publisher_thumbprint,
        commit=True,
        binding_path=binding_path,
        backend=FakeBackend(identity),
    )
    candidate = _identity(executable)
    close_calls = 0

    def close() -> None:
        nonlocal close_calls
        close_calls += 1
        raise OSError("raw close detail " + str(executable))

    candidate.close = close

    result = _inspect_for_test(root, binding_path, FakeBackend(candidate))
    rendered = json.dumps(result.to_dict())

    assert result.status == "error"
    assert result.state in {"candidate_unavailable", "invalid"}
    assert result.findings[0].rule_id == "execution-trust-identity-close-failed"
    assert result.binding_id is None
    assert result.executable_identity is None
    assert result.path_identity is None
    assert close_calls == 1
    assert "raw close detail" not in rendered
    assert str(executable) not in rendered


def test_trust_inspection_reports_drifted_candidate_identities(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    executable = tmp_path / "Git" / "git.exe"
    executable.parent.mkdir()
    executable.write_bytes(b"git")
    binding_path = tmp_path / "machine-local" / "binding.json"
    original = _identity(executable)
    created = create_execution_trust_binding(
        root,
        expected_sha256=original.sha256,
        expected_publisher_thumbprint=original.publisher_thumbprint,
        commit=True,
        binding_path=binding_path,
        backend=FakeBackend(original),
    )
    candidate = _identity(executable)
    candidate.sha256 = "d" * 64
    candidate.file_identity = "windows-file:changed"
    candidate.path_identity = "sha256:" + "e" * 64

    result = _inspect_for_test(root, binding_path, FakeBackend(candidate))

    assert result.status == "blocked"
    assert result.state == "drifted"
    assert result.binding_id == created.binding_id
    assert result.executable_identity == execution_trust._identity_digest(candidate)
    assert result.path_identity == candidate.path_identity
    assert result.checks["executable_identity_matches"] is False
    assert result.checks["path_identity_matches"] is False


def test_trust_inspection_reports_invalid_without_candidate_discovery(
    tmp_path: Path,
) -> None:
    root = tmp_path / "project"
    root.mkdir()
    binding_path = tmp_path / "binding.json"
    private_path = "C:" + "/secret"
    binding_path.write_text(json.dumps({"private_path": private_path}), encoding="utf-8")
    backend = CandidateUnavailableBackend()

    result = _inspect_for_test(root, binding_path, backend)

    assert result.status == "validation_failed"
    assert result.state == "invalid"
    assert result.executable_identity is None
    assert result.path_identity is None
    assert private_path not in json.dumps(result.to_dict())


def test_trust_inspection_distinguishes_candidate_and_platform_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "project"
    root.mkdir()
    binding_path = tmp_path / "binding.json"

    candidate = _inspect_for_test(root, binding_path, CandidateUnavailableBackend())
    monkeypatch.setattr(
        execution_trust,
        "_default_backend",
        lambda: (_ for _ in ()).throw(OSError("unsafe platform detail")),
    )
    platform = _inspect_for_test(root, binding_path, None)

    assert candidate.status == "blocked"
    assert candidate.state == "candidate_unavailable"
    assert platform.status == "blocked"
    assert platform.state == "platform_unavailable"
    rendered = json.dumps([candidate.to_dict(), platform.to_dict()])
    assert "unsafe candidate detail" not in rendered
    assert "unsafe platform detail" not in rendered


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
