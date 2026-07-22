from __future__ import annotations

import json
import os
import ctypes
import gc
import inspect
from pathlib import Path

import pytest

import agent_runtime.execution_lease as execution_lease

from agent_runtime.execution_lease import (
    ExecutionLeaseResult,
    _LeaseCapability,
    _PortableLeaseBackend,
    _WindowsLeaseBackend,
    _acquire_execution_lease_for_test,
    _native_handle_for_test,
    _inspect_execution_lease_for_test,
    _mutation_ace_flags_are_safe,
    acquire_execution_lease,
    default_execution_lease_path,
    inspect_execution_lease,
)


def _roots(tmp_path: Path) -> tuple[Path, Path]:
    project = tmp_path / "project"
    local = tmp_path / "local" / "agent-runtime"
    project.mkdir()
    local.mkdir(parents=True)
    return project, local


def _minimal_windows_lease_file(path: Path, backend: _WindowsLeaseBackend) -> None:
    backend._apply_minimal_permissions(path.parent)
    path.touch()
    backend._apply_minimal_permissions(path)


def test_default_path_is_fixed_and_separate_from_trust_binding(monkeypatch: pytest.MonkeyPatch) -> None:
    first = default_execution_lease_path()
    second = default_execution_lease_path()

    assert first == second
    assert first.name == "execution-lease-v1.lock"
    assert first.name != "execution-trust-v1.json"
    assert not str(first).startswith(str(Path.cwd()))


def test_public_lease_apis_expose_only_project_root() -> None:
    assert tuple(inspect.signature(acquire_execution_lease).parameters) == ("root",)
    assert tuple(inspect.signature(inspect_execution_lease).parameters) == ("root",)


def test_read_only_inspection_does_not_create_or_modify_lease(tmp_path: Path) -> None:
    project, local = _roots(tmp_path)
    path = local / "execution-lease-v1.lock"
    backend = _PortableLeaseBackend()

    missing = _inspect_execution_lease_for_test(project, lease_path=path, backend=backend)
    assert missing.status == "pass"
    assert missing.lease_state == "available"
    assert not path.exists()

    held = _acquire_execution_lease_for_test(project, lease_path=path, backend=backend)
    assert held.status == "pass"
    before = path.stat()
    active = _inspect_execution_lease_for_test(project, lease_path=path, backend=backend)
    after = path.stat()
    assert active.lease_state == "active"
    assert (before.st_ino, before.st_size, before.st_mtime_ns) == (
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
    )
    held.release()


def test_read_only_inspection_never_calls_exclusive_lock(tmp_path: Path) -> None:
    project, local = _roots(tmp_path)
    path = local / "execution-lease-v1.lock"

    class ObservationalBackend(_PortableLeaseBackend):
        def lock(self, handle: int) -> bool:
            raise AssertionError("inspection called exclusive lock")

    backend = ObservationalBackend()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"")

    result = _inspect_execution_lease_for_test(
        project, lease_path=path, backend=backend
    )

    assert result.status == "pass"
    assert result.lease_state == "available"

    holder = _acquire_execution_lease_for_test(
        project, lease_path=path, backend=_PortableLeaseBackend()
    )
    active = _inspect_execution_lease_for_test(
        project, lease_path=path, backend=backend
    )
    assert active.status == "pass"
    assert active.lease_state == "active"
    holder.release()


def test_atomic_creation_is_persistent_and_release_allows_reacquire(tmp_path: Path) -> None:
    project, local = _roots(tmp_path)
    path = local / "execution-lease-v1.lock"
    backend = _PortableLeaseBackend()

    first = _acquire_execution_lease_for_test(project, lease_path=path, backend=backend)
    assert first.status == "pass"
    first_identity = path.stat().st_ino
    assert path.read_bytes() == b""
    assert os.get_inheritable(_native_handle_for_test(first)) is False

    first.release()
    assert path.is_file()
    second = _acquire_execution_lease_for_test(project, lease_path=path, backend=backend)
    assert second.status == "pass"
    assert path.stat().st_ino == first_identity
    second.release()


def test_contention_is_nonblocking_and_value_safe(tmp_path: Path) -> None:
    project, local = _roots(tmp_path)
    path = local / "execution-lease-v1.lock"
    backend = _PortableLeaseBackend()
    first = _acquire_execution_lease_for_test(project, lease_path=path, backend=backend)

    second = _acquire_execution_lease_for_test(project, lease_path=path, backend=backend)

    assert second.status == "blocked"
    assert second.lease_state == "active"
    rendered = json.dumps(second.to_dict())
    assert str(path) not in rendered
    assert "handle" not in rendered.lower()
    assert "pid" not in rendered.lower()
    first.release()


def test_identity_replacement_after_lock_fails_without_removing_replacement(
    tmp_path: Path,
) -> None:
    project, local = _roots(tmp_path)
    path = local / "execution-lease-v1.lock"

    class ReplacingBackend(_PortableLeaseBackend):
        def lock(self, descriptor: int) -> bool:
            locked = super().lock(descriptor)
            replacement = path.with_suffix(".replacement")
            replacement.touch()
            os.replace(replacement, path)
            return locked

    result = _acquire_execution_lease_for_test(
        project,
        lease_path=path,
        backend=ReplacingBackend(),
    )

    assert result.status == "error"
    assert path.exists()
    assert _native_handle_for_test(result) is None


def test_result_exposes_no_native_or_path_state(tmp_path: Path) -> None:
    project, local = _roots(tmp_path)
    result = _acquire_execution_lease_for_test(
        project,
        lease_path=local / "execution-lease-v1.lock",
        backend=_PortableLeaseBackend(),
    )

    assert result.status == "pass"
    for name in ("native_handle", "_backend", "backend", "_path", "path", "_capability"):
        assert not hasattr(result, name)
        assert name not in repr(result)
    rendered = json.dumps(result.to_dict())
    assert "handle" not in rendered.lower()
    assert "backend" not in rendered.lower()
    assert str(local) not in rendered
    result.release()


def test_manual_capability_never_validates_without_registry_membership(tmp_path: Path) -> None:
    synthetic = ExecutionLeaseResult(status="pass", lease_state="active")
    path = tmp_path / "ordinary-file"
    descriptor = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    synthetic.native_handle = descriptor
    capability = _LeaseCapability(synthetic)

    from agent_runtime.execution_lease import _validate_lease_capability

    assert _validate_lease_capability(capability, tmp_path) is False
    os.close(descriptor)


def test_release_invalidates_registry_before_backend_unlock(tmp_path: Path) -> None:
    project, local = _roots(tmp_path)
    observed: list[bool] = []

    class ObservingBackend(_PortableLeaseBackend):
        def unlock(self, handle: int) -> None:
            from agent_runtime.execution_lease import _validate_lease_capability

            observed.append(_validate_lease_capability(capability, project))
            super().unlock(handle)

    lease = _acquire_execution_lease_for_test(
        project,
        lease_path=local / "execution-lease-v1.lock",
        backend=ObservingBackend(),
    )
    from agent_runtime.execution_lease import _held_lease_capability

    capability = _held_lease_capability(lease)
    assert capability is not None

    lease.release()

    assert observed == [False]


def test_gc_finalizer_releases_lock_and_allows_reacquire(tmp_path: Path) -> None:
    project, local = _roots(tmp_path)
    path = local / "execution-lease-v1.lock"
    backend = _PortableLeaseBackend()
    lease = _acquire_execution_lease_for_test(
        project,
        lease_path=path,
        backend=backend,
    )
    assert lease.status == "pass"

    del lease
    gc.collect()

    reacquired = _acquire_execution_lease_for_test(
        project,
        lease_path=path,
        backend=backend,
    )
    assert reacquired.status == "pass"
    reacquired.release()


def test_release_returns_error_on_unlock_failure_without_raising(tmp_path: Path) -> None:
    project, local = _roots(tmp_path)

    class UnlockFailureBackend(_PortableLeaseBackend):
        def __init__(self) -> None:
            self.unlock_calls = 0

        def unlock(self, handle: int) -> None:
            self.unlock_calls += 1
            raise OSError("unsafe raw detail")

        def close(self, handle: int) -> None:
            _PortableLeaseBackend.unlock(self, handle)
            super().close(handle)

    backend = UnlockFailureBackend()
    lease = _acquire_execution_lease_for_test(
        project,
        lease_path=local / "execution-lease-v1.lock",
        backend=backend,
    )

    released = lease.release()

    assert released.status == "error"
    assert released.findings[0].rule_id == "execution-lease-release-failed"
    assert "unsafe raw detail" not in json.dumps(released.to_dict())
    assert lease.validate() is False
    reacquired = _acquire_execution_lease_for_test(
        project,
        lease_path=local / "execution-lease-v1.lock",
        backend=backend,
    )
    assert reacquired.status == "pass"
    assert backend.unlock_calls == 1
    reacquired.release()


def test_close_failure_retains_cleanup_for_idempotent_retry(tmp_path: Path) -> None:
    project, local = _roots(tmp_path)

    class CloseFailureBackend(_PortableLeaseBackend):
        def __init__(self) -> None:
            self.close_calls = 0

        def close(self, handle: int) -> None:
            self.close_calls += 1
            if self.close_calls == 1:
                raise OSError("unsafe raw detail")
            super().close(handle)

    backend = CloseFailureBackend()
    lease = _acquire_execution_lease_for_test(
        project,
        lease_path=local / "execution-lease-v1.lock",
        backend=backend,
    )

    first = lease.release()
    second = lease.release()

    assert first.status == "error"
    assert first.findings[0].rule_id == "execution-lease-release-failed"
    assert second.status == "pass"
    assert backend.close_calls == 2


def test_gc_close_failure_is_retried_before_next_acquisition(tmp_path: Path) -> None:
    project, local = _roots(tmp_path)
    path = local / "execution-lease-v1.lock"

    class CloseFailureBackend(_PortableLeaseBackend):
        def __init__(self) -> None:
            self.close_calls = 0

        def close(self, handle: int) -> None:
            self.close_calls += 1
            if self.close_calls == 1:
                raise OSError("first close fails")
            super().close(handle)

    backend = CloseFailureBackend()
    lease = _acquire_execution_lease_for_test(
        project,
        lease_path=path,
        backend=backend,
    )
    del lease
    gc.collect()
    assert backend.close_calls == 1

    reacquired = _acquire_execution_lease_for_test(
        project,
        lease_path=path,
        backend=backend,
    )

    assert backend.close_calls == 2
    assert reacquired.status == "pass"
    reacquired.release()


def test_unresolved_pending_cleanup_blocks_before_new_open(tmp_path: Path) -> None:
    project, local = _roots(tmp_path)
    path = local / "execution-lease-v1.lock"

    class AlwaysCloseFailureBackend(_PortableLeaseBackend):
        def __init__(self) -> None:
            self.open_calls = 0
            self.lock_calls = 0

        def open(self, path: Path, *, create: bool, inspect: bool = False) -> int:
            self.open_calls += 1
            return super().open(path, create=create, inspect=inspect)

        def lock(self, handle: int) -> bool:
            self.lock_calls += 1
            return super().lock(handle)

        def close(self, handle: int) -> None:
            raise OSError("always close fails")

    backend = AlwaysCloseFailureBackend()
    lease = _acquire_execution_lease_for_test(
        project,
        lease_path=path,
        backend=backend,
    )
    assert lease.release().status == "error"
    opens_before = backend.open_calls
    locks_before = backend.lock_calls

    blocked = _acquire_execution_lease_for_test(
        project,
        lease_path=path,
        backend=backend,
    )

    assert blocked.status == "error"
    assert blocked.lease_state == "unavailable"
    assert blocked.findings[0].rule_id == "execution-lease-cleanup-pending"
    assert backend.open_calls == opens_before
    assert backend.lock_calls == locks_before


@pytest.mark.parametrize("operation", ["busy-close", "validation-unlock", "validation-close"])
def test_acquisition_cleanup_faults_return_safe_results(
    tmp_path: Path, operation: str
) -> None:
    project, local = _roots(tmp_path)
    path = local / "execution-lease-v1.lock"

    class FaultBackend(_PortableLeaseBackend):
        def __init__(self) -> None:
            self.close_calls = 0
            self.permission_checks = 0

        def lock(self, handle: int) -> bool:
            if operation == "busy-close":
                return False
            return super().lock(handle)

        def unlock(self, handle: int) -> None:
            if operation == "validation-unlock":
                raise OSError("raw unlock detail")
            return super().unlock(handle)

        def close(self, handle: int) -> None:
            self.close_calls += 1
            if operation in {"busy-close", "validation-close"}:
                raise OSError("raw close detail")
            return super().close(handle)

        def permissions_are_minimal(self, path: Path, handle: int) -> bool:
            self.permission_checks += 1
            if operation in {"validation-unlock", "validation-close"}:
                return self.permission_checks == 1
            return True

    result = _acquire_execution_lease_for_test(
        project,
        lease_path=path,
        backend=FaultBackend(),
    )

    assert result.status in {"blocked", "error"}
    rendered = json.dumps(result.to_dict())
    assert "raw unlock detail" not in rendered
    assert "raw close detail" not in rendered


def test_inspection_cleanup_fault_returns_safe_result(tmp_path: Path) -> None:
    project, local = _roots(tmp_path)
    path = local / "execution-lease-v1.lock"
    path.touch()

    class InspectCloseFailureBackend(_PortableLeaseBackend):
        def close(self, handle: int) -> None:
            raise OSError("raw inspect close detail")

    result = _inspect_execution_lease_for_test(
        project,
        lease_path=path,
        backend=InspectCloseFailureBackend(),
    )

    assert result.status == "error"
    assert result.lease_state == "unavailable"
    assert "raw inspect close detail" not in json.dumps(result.to_dict())


def test_permission_type_error_after_open_is_safely_closed(tmp_path: Path) -> None:
    project, local = _roots(tmp_path)

    class TypeErrorBackend(_PortableLeaseBackend):
        def __init__(self) -> None:
            self.unlock_calls = 0
            self.close_calls = 0

        def permissions_are_minimal(self, path: Path, handle: int) -> bool:
            raise TypeError("raw permission detail")

        def unlock(self, handle: int) -> None:
            self.unlock_calls += 1
            super().unlock(handle)

        def close(self, handle: int) -> None:
            self.close_calls += 1
            super().close(handle)

    backend = TypeErrorBackend()
    result = _acquire_execution_lease_for_test(
        project,
        lease_path=local / "execution-lease-v1.lock",
        backend=backend,
    )

    assert result.status == "error"
    assert backend.unlock_calls == 0
    assert backend.close_calls == 1
    assert "raw permission detail" not in json.dumps(result.to_dict())


def test_keyboard_interrupt_during_cleanup_still_closes_and_propagates(
    tmp_path: Path,
) -> None:
    project, local = _roots(tmp_path)

    class InterruptBackend(_PortableLeaseBackend):
        def __init__(self) -> None:
            self.close_calls = 0

        def unlock(self, handle: int) -> None:
            raise KeyboardInterrupt()

        def close(self, handle: int) -> None:
            self.close_calls += 1
            _PortableLeaseBackend.unlock(self, handle)
            super().close(handle)

    backend = InterruptBackend()
    lease = _acquire_execution_lease_for_test(
        project,
        lease_path=local / "execution-lease-v1.lock",
        backend=backend,
    )

    with pytest.raises(KeyboardInterrupt):
        lease.release()

    assert backend.close_calls == 1


def test_post_lock_cleanup_does_not_resolve_deleted_project_root(tmp_path: Path) -> None:
    project, local = _roots(tmp_path)

    class DeleteRootBackend(_PortableLeaseBackend):
        def __init__(self) -> None:
            self.permission_checks = 0
            self.unlock_calls = 0
            self.close_calls = 0

        def permissions_are_minimal(self, path: Path, handle: int) -> bool:
            self.permission_checks += 1
            if self.permission_checks == 2:
                project.rmdir()
                return False
            return True

        def unlock(self, handle: int) -> None:
            self.unlock_calls += 1
            super().unlock(handle)

        def close(self, handle: int) -> None:
            self.close_calls += 1
            super().close(handle)

    backend = DeleteRootBackend()
    result = _acquire_execution_lease_for_test(
        project,
        lease_path=local / "execution-lease-v1.lock",
        backend=backend,
    )

    assert result.status == "error"
    assert backend.unlock_calls == 1
    assert backend.close_calls == 1


def test_inspect_cleanup_does_not_resolve_deleted_project_root(tmp_path: Path) -> None:
    project, local = _roots(tmp_path)
    path = local / "execution-lease-v1.lock"
    path.touch()

    class DeleteRootBackend(_PortableLeaseBackend):
        def __init__(self) -> None:
            self.unlock_calls = 0
            self.close_calls = 0

        def inspect_state(self, path: Path, handle: int | None = None) -> str:
            project.rmdir()
            return super().inspect_state(path, handle)

        def unlock(self, handle: int) -> None:
            self.unlock_calls += 1
            super().unlock(handle)

        def close(self, handle: int) -> None:
            self.close_calls += 1
            super().close(handle)

    backend = DeleteRootBackend()
    result = _inspect_execution_lease_for_test(
        project,
        lease_path=path,
        backend=backend,
    )

    assert result.status == "pass"
    assert backend.unlock_calls == 0
    assert backend.close_calls == 1


@pytest.mark.parametrize("shape", ["directory", "symlink", "hardlink"])
def test_unsafe_existing_file_shape_is_rejected(tmp_path: Path, shape: str) -> None:
    project, local = _roots(tmp_path)
    path = local / "execution-lease-v1.lock"
    if shape == "directory":
        path.mkdir()
    elif shape == "symlink":
        target = local / "target"
        target.touch()
        try:
            path.symlink_to(target)
        except OSError:
            pytest.skip("symlink creation unavailable")
    else:
        path.touch()
        os.link(path, local / "second-link")

    result = _acquire_execution_lease_for_test(
        project,
        lease_path=path,
        backend=_PortableLeaseBackend(),
    )

    assert result.status == "error"
    assert result.findings[0].rule_id == "execution-lease-invalid"


def test_project_local_path_and_reparse_parent_are_rejected(tmp_path: Path) -> None:
    project, local = _roots(tmp_path)
    backend = _PortableLeaseBackend()

    overlap = _acquire_execution_lease_for_test(
        project,
        lease_path=project / "lease.lock",
        backend=backend,
    )
    assert overlap.status == "error"

    target = tmp_path / "real-parent"
    target.mkdir()
    linked = local / "linked"
    try:
        linked.symlink_to(target, target_is_directory=True)
    except OSError:
        pytest.skip("symlink creation unavailable")
    reparse = _acquire_execution_lease_for_test(
        project,
        lease_path=linked / "lease.lock",
        backend=backend,
    )
    assert reparse.status == "error"


def test_lease_location_family_cannot_contain_project_root(tmp_path: Path) -> None:
    local = tmp_path / "local"
    project = local / "nested-project"
    project.mkdir(parents=True)
    path = local / "execution-lease-v1.lock"

    result = _acquire_execution_lease_for_test(
        project,
        lease_path=path,
        backend=_PortableLeaseBackend(),
    )

    assert result.status == "error"
    assert not path.exists()


def test_permission_validation_fails_closed(tmp_path: Path) -> None:
    project, local = _roots(tmp_path)
    path = local / "execution-lease-v1.lock"

    class UnsafePermissionsBackend(_PortableLeaseBackend):
        def permissions_are_minimal(self, path: Path, handle: int) -> bool:
            return False

    result = _acquire_execution_lease_for_test(
        project,
        lease_path=path,
        backend=UnsafePermissionsBackend(),
    )

    assert result.status == "error"
    assert result.findings[0].rule_id == "execution-lease-invalid"

    inspected = _inspect_execution_lease_for_test(
        project,
        lease_path=path,
        backend=UnsafePermissionsBackend(),
    )
    assert inspected.status == "error"
    assert inspected.lease_state == "unavailable"


def test_posix_production_backend_is_unavailable_without_injection(tmp_path: Path) -> None:
    if os.name == "nt":
        pytest.skip("POSIX-only production boundary")
    project, _ = _roots(tmp_path)

    result = acquire_execution_lease(project)

    assert result.status == "error"
    assert result.lease_state == "unavailable"


def test_public_resolver_failure_returns_safe_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project, _ = _roots(tmp_path)

    def fail_resolver() -> Path:
        raise OSError("unsafe resolver detail")

    monkeypatch.setattr(execution_lease, "default_execution_lease_path", fail_resolver)

    acquired = acquire_execution_lease(project)
    inspected = inspect_execution_lease(project)

    assert acquired.status == "error"
    assert acquired.lease_state == "unavailable"
    assert inspected.status == "error"
    assert inspected.lease_state == "unavailable"
    assert "unsafe resolver detail" not in json.dumps(acquired.to_dict())
    assert "unsafe resolver detail" not in json.dumps(inspected.to_dict())


def test_production_backend_rejects_path_override(tmp_path: Path) -> None:
    project, local = _roots(tmp_path)
    path = local / "caller-selected.lock"

    with pytest.raises(TypeError):
        acquire_execution_lease(project, lease_path=path)
    with pytest.raises(TypeError):
        inspect_execution_lease(project, lease_path=path)
    assert not path.exists()


@pytest.mark.skipif(os.name != "nt", reason="Windows lease backend")
def test_windows_backend_binds_lock_to_path_identity(tmp_path: Path) -> None:
    project, local = _roots(tmp_path)
    path = local / "execution-lease-v1.lock"

    backend = _WindowsLeaseBackend()
    _minimal_windows_lease_file(path, backend)
    result = _acquire_execution_lease_for_test(
        project,
        lease_path=path,
        backend=backend,
    )

    assert result.status == "pass"
    assert result.validate() is True
    result.release()
    assert path.exists()


@pytest.mark.skipif(os.name != "nt", reason="Windows lease backend")
def test_windows_backend_contention_reports_active(tmp_path: Path) -> None:
    project, local = _roots(tmp_path)
    path = local / "execution-lease-v1.lock"
    backend = _WindowsLeaseBackend()
    _minimal_windows_lease_file(path, backend)
    first = _acquire_execution_lease_for_test(
        project,
        lease_path=path,
        backend=backend,
    )

    second = _acquire_execution_lease_for_test(
        project,
        lease_path=path,
        backend=_WindowsLeaseBackend(),
    )

    assert first.status == "pass"
    assert second.status == "blocked"
    assert second.lease_state == "active"
    first.release()


@pytest.mark.skipif(os.name != "nt", reason="Windows lease backend")
def test_windows_handle_is_noninheritable_and_denies_replace_delete(tmp_path: Path) -> None:
    project, local = _roots(tmp_path)
    path = local / "execution-lease-v1.lock"
    backend = _WindowsLeaseBackend()
    _minimal_windows_lease_file(path, backend)
    result = _acquire_execution_lease_for_test(
        project,
        lease_path=path,
        backend=backend,
    )
    assert result.status == "pass"
    native_handle = _native_handle_for_test(result)
    assert native_handle is not None

    flags = ctypes.c_ulong()
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    assert kernel32.GetHandleInformation(native_handle, ctypes.byref(flags))
    assert flags.value & 1 == 0
    replacement = local / "replacement.lock"
    replacement.touch()
    with pytest.raises(PermissionError):
        os.replace(replacement, path)
    with pytest.raises(PermissionError):
        path.unlink()

    result.release()
    os.replace(replacement, path)


@pytest.mark.skipif(os.name != "nt", reason="Windows lease backend")
def test_windows_first_use_atomically_creates_secured_parent_and_file(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    secured_ancestor = tmp_path / "secured-local"
    secured_ancestor.mkdir()
    backend = _WindowsLeaseBackend()
    backend._apply_minimal_permissions(secured_ancestor)
    path = secured_ancestor / "agent-runtime" / "execution-lease-v1.lock"
    assert not path.parent.exists()
    assert not path.exists()

    result = _acquire_execution_lease_for_test(
        project,
        lease_path=path,
        backend=backend,
    )

    assert result.status == "pass"
    assert path.parent.is_dir()
    assert path.is_file()
    native_handle = _native_handle_for_test(result)
    assert native_handle is not None
    assert backend.permissions_are_minimal(path, native_handle)
    result.release()

    inspected = _inspect_execution_lease_for_test(
        project,
        lease_path=path,
        backend=_WindowsLeaseBackend(),
    )
    assert inspected.status == "pass"
    assert inspected.lease_state == "available"


@pytest.mark.skipif(os.name != "nt", reason="Windows lease backend")
def test_windows_permission_check_frees_descriptor_with_null_owner_dacl(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = _WindowsLeaseBackend()
    freed: list[int] = []
    monkeypatch.setattr(
        backend,
        "_get_security_info",
        lambda handle: (None, None, 12345, 0x1000),
    )
    monkeypatch.setattr(
        backend,
        "_free_security_descriptor",
        lambda descriptor: freed.append(descriptor),
    )

    assert backend._handle_permissions_are_minimal(1, directory=False) is False
    assert freed == [12345]


@pytest.mark.skipif(os.name != "nt", reason="Windows lease backend")
def test_windows_permission_check_requires_protected_dacl(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = _WindowsLeaseBackend()
    monkeypatch.setattr(
        backend,
        "_get_security_info",
        lambda handle: (1, 2, 12345, 0),
    )
    monkeypatch.setattr(backend, "_free_security_descriptor", lambda descriptor: None)

    assert backend._handle_permissions_are_minimal(1, directory=False) is False


def test_mutation_ace_rejects_all_inheritance_flags() -> None:
    assert _mutation_ace_flags_are_safe(0) is True
    for flag in (0x01, 0x02, 0x04, 0x08, 0x10):
        assert _mutation_ace_flags_are_safe(flag) is False
