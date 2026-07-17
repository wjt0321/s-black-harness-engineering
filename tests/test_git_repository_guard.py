from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from agent_runtime.git_repository_guard import (
    build_repository_guard,
    compare_repository_guards,
)


def _repo(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    (root / "agent_runtime").mkdir(parents=True)
    (root / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    git = root / ".git"
    (git / "refs" / "heads").mkdir(parents=True)
    (git / "objects" / "pack").mkdir(parents=True)
    (git / "info").mkdir(parents=True)
    (git / "logs").mkdir(parents=True)
    (git / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    (git / "config").write_text(
        "[core]\n\trepositoryformatversion = 0\n\tbare = false\n",
        encoding="utf-8",
    )
    (git / "index").write_bytes(b"DIRC\x00\x00\x00\x02\x00\x00\x00\x00")
    return root


def test_guard_accepts_minimal_contained_repository(tmp_path: Path) -> None:
    root = _repo(tmp_path)

    result = build_repository_guard(root)

    assert result.status == "pass"
    assert result.guard is not None
    assert result.guard.identity.startswith("sha256:")
    payload = result.guard.to_public_dict()
    assert payload == {
        "guard_evidence_passed": True,
        "no_write_contract": True,
        "filesystem_write_proof": False,
        "guard_identity": result.guard.identity,
    }
    assert str(root) not in json.dumps(payload)


def test_guard_allows_absent_optional_logs_directory(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    (root / ".git" / "logs").rmdir()

    result = build_repository_guard(root)

    assert result.status == "pass"
    assert result.guard is not None
    result.guard.close()


def test_guard_reads_metadata_only_through_bounded_handles(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _repo(tmp_path)

    def fail_path_read(*args: object, **kwargs: object) -> bytes:
        raise AssertionError("pathname read is forbidden")

    monkeypatch.setattr(Path, "read_bytes", fail_path_read)
    result = build_repository_guard(root)

    assert result.status == "pass"
    assert result.guard is not None
    result.guard.close()


def test_guard_rejects_oversized_config_before_read(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    config = root / ".git" / "config"
    with config.open("wb") as handle:
        handle.seek(256 * 1024)
        handle.write(b"x")

    result = build_repository_guard(root)

    assert result.status == "blocked"
    assert result.findings[0].rule_id == "execution.repository-guard-bounds-exceeded"


@pytest.mark.parametrize(
    ("relative", "rule_id"),
    [
        (".git/commondir", "execution.repository-indirection-blocked"),
        (".git/objects/info/alternates", "execution.object-alternate-blocked"),
        (".git/objects/info/http-alternates", "execution.object-alternate-blocked"),
        (".gitmodules", "execution.submodule-surface-blocked"),
        (".git/modules/marker", "execution.submodule-surface-blocked"),
        (".git/index.lock", "execution.repository-lock-present"),
    ],
)
def test_guard_blocks_frozen_repository_surfaces(
    tmp_path: Path, relative: str, rule_id: str
) -> None:
    root = _repo(tmp_path)
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("blocked", encoding="utf-8")

    result = build_repository_guard(root)

    assert result.status == "blocked"
    assert result.findings[0].rule_id == rule_id
    assert str(path) not in json.dumps(result.to_dict())


@pytest.mark.parametrize(
    "config",
    [
        "[include]\npath = ../outside\n",
        "[core]\nworktree = ../outside\n",
        "[core]\nexcludesFile = " + "C" + ":/secret\n",
        "[core]\nattributesFile = ../secret\n",
        "[credential]\nhelper = manager\n",
        "[filter \"x\"]\nprocess = secret-command\n",
        "[diff]\nexternal = secret-command\n",
        "[core]\nfsmonitor = true\n",
        "[core]\nrepositoryformatversion = 0\\\ncontinued\n",
    ],
)
def test_config_scanner_blocks_dangerous_or_unsupported_syntax(
    tmp_path: Path, config: str
) -> None:
    root = _repo(tmp_path)
    (root / ".git" / "config").write_text(config, encoding="utf-8")

    result = build_repository_guard(root)

    assert result.status == "blocked"
    assert result.findings[0].rule_id == "execution.repository-config-blocked"
    assert "secret" not in json.dumps(result.to_dict())


def test_symlink_and_hardlink_are_blocked_before_target_read(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    outside = tmp_path / "outside-secret"
    outside.write_text("do-not-read", encoding="utf-8")
    head = root / ".git" / "HEAD"
    head.unlink()
    try:
        head.symlink_to(outside)
    except OSError:
        pytest.skip("symlink creation is unavailable")

    result = build_repository_guard(root)

    assert result.status == "blocked"
    assert result.findings[0].rule_id == "execution.repository-containment-blocked"
    assert "do-not-read" not in json.dumps(result.to_dict())

    head.unlink()
    os.link(outside, head)
    hardlink = build_repository_guard(root)
    assert hardlink.status == "blocked"
    assert hardlink.findings[0].rule_id == "execution.repository-containment-blocked"


def test_critical_file_parent_symlink_is_blocked(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    outside = tmp_path / "outside-info"
    outside.mkdir()
    (outside / "exclude").write_text("do-not-read", encoding="utf-8")
    info = root / ".git" / "info"
    shutil_target = info
    for child in info.iterdir():
        child.unlink()
    info.rmdir()
    try:
        shutil_target.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("directory symlink creation is unavailable")

    result = build_repository_guard(root)

    assert result.status == "blocked"
    assert result.findings[0].rule_id == "execution.repository-containment-blocked"
    assert "do-not-read" not in json.dumps(result.to_dict())


def test_guard_detects_post_run_drift(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    before = build_repository_guard(root)
    assert before.guard is not None
    before.guard.close()
    (root / ".git" / "HEAD").write_text("ref: refs/heads/other\n", encoding="utf-8")
    after = build_repository_guard(root)
    assert after.guard is not None

    comparison = compare_repository_guards(before.guard, after.guard)
    after.guard.close()

    assert comparison.status == "blocked"
    assert comparison.findings[0].rule_id == "execution.repository-guard-drift"


def test_missing_markers_and_git_file_are_rejected(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    missing = build_repository_guard(root)
    assert missing.status == "validation_failed"

    (root / "agent_runtime").mkdir()
    (root / "pyproject.toml").write_text("", encoding="utf-8")
    (root / ".git").write_text("gitdir: elsewhere", encoding="utf-8")
    linked = build_repository_guard(root)
    assert linked.status == "blocked"
    assert linked.findings[0].rule_id == "execution.repository-indirection-blocked"
