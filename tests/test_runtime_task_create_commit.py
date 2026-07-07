"""Tests for runtime task create --commit.

All destructive tests run in temporary directories and assert that failures do
not modify ledger files outside the expected append line.
"""

from __future__ import annotations

import io
import json
import shutil
from pathlib import Path
from unittest.mock import patch

import pytest

from agent_runtime.cli import main
from agent_runtime.runtime_task_create import create_task

ROOT = Path(__file__).resolve().parents[1]


def _setup_fake_root(tmp_path: Path) -> Path:
    """Create a fake project root with the schemas and policies needed."""
    fake_root = tmp_path / "project"
    fake_root.mkdir(parents=True, exist_ok=True)

    for src_rel in (
        "tasks/task.schema.json",
        "tasks/event.schema.json",
        "adapters/execution-envelope.schema.json",
    ):
        src = ROOT / src_rel
        dst = fake_root / src_rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.exists():
            shutil.copyfile(src, dst)

    policy_src = ROOT / "policies"
    policy_dst = fake_root / "policies"
    policy_dst.mkdir(parents=True, exist_ok=True)
    for policy_file in policy_src.glob("*.sample.policy.json"):
        shutil.copyfile(policy_file, policy_dst / policy_file.name)

    return fake_root


def _task(
    task_id: str,
    title: str = "test task",
    status: str = "planned",
    assignee: str | None = "cli",
    tags: list[str] | None = None,
    artifacts: list[str] | None = None,
    evidence: list[dict[str, str]] | None = None,
) -> dict[str, object]:
    return {
        "id": task_id,
        "title": title,
        "status": status,
        "created_at": "2026-07-06T10:00:00+08:00",
        "updated_at": "2026-07-06T10:00:00+08:00",
        "created_by": "cli",
        "source": "cli",
        "assignee": assignee,
        "tags": tags or [],
        "artifacts": artifacts or [],
        "evidence": evidence or [],
    }


def _write_tasks(root: Path, *tasks: dict[str, object]) -> Path:
    tasks_dir = root / "tasks"
    tasks_dir.mkdir(exist_ok=True)
    tasks_file = tasks_dir / "tasks.jsonl"
    lines = [json.dumps(t, ensure_ascii=False) for t in tasks]
    tasks_file.write_text("\n".join(lines) + "\n" if lines else "", encoding="utf-8")
    return tasks_file


def _candidate_file(root: Path, candidate: dict[str, object]) -> Path:
    candidate_file = root / "candidate.json"
    candidate_file.write_text(json.dumps(candidate, ensure_ascii=False), encoding="utf-8")
    return candidate_file


def test_commit_appends_one_line(tmp_path):
    root = _setup_fake_root(tmp_path)
    task_id = "task-20260706-002"
    tasks_file = _write_tasks(root, _task("task-20260706-001"))
    candidate = _task(task_id, tags=["a", "b"], artifacts=["art1"], evidence=[{"type": "note", "description": "x", "ref": None}])

    result = create_task(
        root,
        file=None,
        stdin=False,
        commit=True,
        tasks_file="tasks/tasks.jsonl",
        events_file="tasks/events.jsonl",
        candidate=candidate,
    )

    assert result.status == "pass"
    assert result.committed is True
    assert result.would_create is True
    assert result.post_validate == "pass"
    assert result.post_ledger_check == "pass"
    content = tasks_file.read_text(encoding="utf-8")
    assert content.count("\n") == 2
    assert '"id": "task-20260706-002"' in content


def test_commit_creates_new_ledger_file(tmp_path):
    root = _setup_fake_root(tmp_path)
    task_id = "task-20260706-001"
    tasks_dir = root / "tasks"
    tasks_dir.mkdir(exist_ok=True)
    tasks_file = tasks_dir / "tasks.jsonl"
    candidate = _task(task_id)

    result = create_task(
        root,
        file=None,
        stdin=False,
        commit=True,
        tasks_file="tasks/tasks.jsonl",
        events_file="tasks/events.jsonl",
        candidate=candidate,
    )

    assert result.status == "pass"
    assert result.committed is True
    assert tasks_file.is_file()
    content = tasks_file.read_text(encoding="utf-8")
    assert content.count("\n") == 1
    assert content.endswith("\n")


def test_commit_dry_run_does_not_write(tmp_path, monkeypatch, capsys):
    root = _setup_fake_root(tmp_path)
    task_id = "task-20260706-002"
    tasks_file = _write_tasks(root, _task("task-20260706-001"))
    candidate_file = _candidate_file(root, _task(task_id))

    monkeypatch.setattr(
        "sys.argv",
        ["agent-runtime", "--root", str(root), "runtime", "task", "create", "--file", str(candidate_file), "--dry-run"],
    )
    assert main() == 0
    captured = capsys.readouterr()
    assert "PASS" in captured.out
    assert tasks_file.read_text(encoding="utf-8").count("\n") == 1


def test_commit_dry_run_commit_mutually_exclusive(tmp_path, monkeypatch, capsys):
    root = _setup_fake_root(tmp_path)
    tasks_file = _write_tasks(root, _task("task-20260706-001"))
    candidate_file = _candidate_file(root, _task("task-20260706-002"))

    monkeypatch.setattr(
        "sys.argv",
        [
            "agent-runtime",
            "--root",
            str(root),
            "runtime",
            "task",
            "create",
            "--file",
            str(candidate_file),
            "--dry-run",
            "--commit",
        ],
    )
    assert main() == 1
    captured = capsys.readouterr()
    assert "dry-run-commit-mutually-exclusive" in captured.out
    assert tasks_file.read_text(encoding="utf-8").count("\n") == 1


def test_commit_missing_mode_error(tmp_path, monkeypatch, capsys):
    root = _setup_fake_root(tmp_path)
    _write_tasks(root, _task("task-20260706-001"))
    candidate_file = _candidate_file(root, _task("task-20260706-002"))

    monkeypatch.setattr(
        "sys.argv",
        ["agent-runtime", "--root", str(root), "runtime", "task", "create", "--file", str(candidate_file)],
    )
    assert main() == 1
    captured = capsys.readouterr()
    assert "missing-create-mode" in captured.out


def test_commit_schema_invalid_does_not_write(tmp_path):
    root = _setup_fake_root(tmp_path)
    task_id = "task-20260706-002"
    tasks_file = _write_tasks(root, _task("task-20260706-001"))
    candidate = {"id": task_id, "status": "planned"}

    result = create_task(
        root,
        file=None,
        stdin=False,
        commit=True,
        tasks_file="tasks/tasks.jsonl",
        events_file="tasks/events.jsonl",
        candidate=candidate,
    )

    assert result.status == "validation_failed"
    assert any(f.rule_id == "task-schema-validation-failed" for f in result.findings)
    assert tasks_file.read_text(encoding="utf-8").count("\n") == 1


def test_commit_duplicate_task_id_does_not_write(tmp_path):
    root = _setup_fake_root(tmp_path)
    task_id = "task-20260706-001"
    tasks_file = _write_tasks(root, _task(task_id))
    candidate = _task(task_id, title="different title")

    result = create_task(
        root,
        file=None,
        stdin=False,
        commit=True,
        tasks_file="tasks/tasks.jsonl",
        events_file="tasks/events.jsonl",
        candidate=candidate,
    )

    assert result.status == "validation_failed"
    assert any(f.rule_id == "duplicate-task-id" for f in result.findings)
    assert tasks_file.read_text(encoding="utf-8").count("\n") == 1


def test_commit_secret_blocked_does_not_write_or_leak(tmp_path):
    root = _setup_fake_root(tmp_path)
    task_id = "task-20260706-002"
    tasks_file = _write_tasks(root, _task("task-20260706-001"))
    token = "ghp_" + "X" * 36
    candidate = _task(task_id, title=token)

    result = create_task(
        root,
        file=None,
        stdin=False,
        commit=True,
        tasks_file="tasks/tasks.jsonl",
        events_file="tasks/events.jsonl",
        candidate=candidate,
    )

    assert result.status == "blocked"
    rendered = result.render_json()
    assert token not in rendered
    assert tasks_file.read_text(encoding="utf-8").count("\n") == 1


def test_commit_public_scan_blocked_does_not_write_or_leak(tmp_path):
    root = _setup_fake_root(tmp_path)
    task_id = "task-20260706-002"
    tasks_file = _write_tasks(root, _task("task-20260706-001"))
    # A Windows absolute path triggers the public scan rule without being a secret.
    # Build dynamically so the test source does not itself contain a scannable path.
    drive = "C:"
    public_match = drive + "\\\\" + "\\\\".join(["Users", "wxb", "workspace"])
    candidate = _task(task_id, title=public_match)

    result = create_task(
        root,
        file=None,
        stdin=False,
        commit=True,
        tasks_file="tasks/tasks.jsonl",
        events_file="tasks/events.jsonl",
        candidate=candidate,
    )

    assert result.status == "blocked"
    rendered = result.render_json()
    assert public_match not in rendered
    assert tasks_file.read_text(encoding="utf-8").count("\n") == 1


def test_commit_tasks_file_outside_root_blocked(tmp_path):
    root = _setup_fake_root(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    outside_tasks = outside / "tasks.jsonl"
    outside_tasks.write_text("", encoding="utf-8")
    candidate = _task("task-20260706-002")

    result = create_task(
        root,
        file=None,
        stdin=False,
        commit=True,
        tasks_file=str(outside_tasks),
        events_file="tasks/events.jsonl",
        candidate=candidate,
    )

    assert result.status == "error"
    assert any(f.rule_id == "tasks-file-outside-root" for f in result.findings)


def test_commit_tasks_file_suffix_not_jsonl_blocked(tmp_path):
    root = _setup_fake_root(tmp_path)
    (root / "tasks").mkdir(exist_ok=True)
    bad_tasks = root / "tasks" / "tasks.txt"
    bad_tasks.write_text("", encoding="utf-8")
    candidate = _task("task-20260706-002")

    result = create_task(
        root,
        file=None,
        stdin=False,
        commit=True,
        tasks_file="tasks/tasks.txt",
        events_file="tasks/events.jsonl",
        candidate=candidate,
    )

    assert result.status == "error"
    assert any(f.rule_id == "unsafe-tasks-file" for f in result.findings)


def test_commit_sample_ledger_blocked(tmp_path):
    root = _setup_fake_root(tmp_path)
    (root / "tasks").mkdir(exist_ok=True)
    sample = root / "tasks" / "examples.jsonl"
    sample.write_text("", encoding="utf-8")
    candidate = _task("task-20260706-002")

    result = create_task(
        root,
        file=None,
        stdin=False,
        commit=True,
        tasks_file="tasks/examples.jsonl",
        events_file="tasks/events.jsonl",
        candidate=candidate,
    )

    assert result.status == "error"
    assert any(f.rule_id == "sample-ledger-write-blocked" for f in result.findings)


def test_commit_examples_suffix_ledger_blocked(tmp_path):
    root = _setup_fake_root(tmp_path)
    (root / "tasks").mkdir(exist_ok=True)
    sample = root / "tasks" / "tasks.examples.jsonl"
    sample.write_text("", encoding="utf-8")
    candidate = _task("task-20260706-002")

    result = create_task(
        root,
        file=None,
        stdin=False,
        commit=True,
        tasks_file="tasks/tasks.examples.jsonl",
        events_file="tasks/events.jsonl",
        candidate=candidate,
    )

    assert result.status == "error"
    assert any(f.rule_id == "sample-ledger-write-blocked" for f in result.findings)


def test_commit_git_internals_path_blocked(tmp_path):
    root = _setup_fake_root(tmp_path)
    git_dir = root / ".git"
    git_dir.mkdir(exist_ok=True)
    candidate = _task("task-20260706-002")

    result = create_task(
        root,
        file=None,
        stdin=False,
        commit=True,
        tasks_file=".git/tasks.jsonl",
        events_file="tasks/events.jsonl",
        candidate=candidate,
    )

    assert result.status == "error"
    assert any(f.rule_id == "unsafe-tasks-file" for f in result.findings)


def test_commit_missing_trailing_newline_blocked(tmp_path):
    root = _setup_fake_root(tmp_path)
    task_id = "task-20260706-002"
    tasks_file = root / "tasks" / "tasks.jsonl"
    tasks_file.parent.mkdir(parents=True, exist_ok=True)
    # Deliberately omit trailing newline on the existing line.
    tasks_file.write_text(
        json.dumps(_task("task-20260706-001"), ensure_ascii=False),
        encoding="utf-8",
    )
    candidate = _task(task_id)

    result = create_task(
        root,
        file=None,
        stdin=False,
        commit=True,
        tasks_file="tasks/tasks.jsonl",
        events_file="tasks/events.jsonl",
        candidate=candidate,
    )

    assert result.status == "blocked"
    assert any(f.rule_id == "tasks-file-missing-trailing-newline" for f in result.findings)
    content = tasks_file.read_bytes()
    assert not content.endswith(b"\n")


def test_commit_post_check_failure_rolls_back(tmp_path):
    root = _setup_fake_root(tmp_path)
    task_id = "task-20260706-002"
    tasks_file = _write_tasks(root, _task("task-20260706-001"))
    candidate = _task(task_id)

    original_size = tasks_file.stat().st_size

    def _failing_validate(*args, **kwargs):
        from agent_runtime.result import CheckResult, Finding

        return CheckResult(
            status="validation_failed",
            findings=[Finding(rule_id="post-validate-failure", severity="error", action="error", message="simulated")],
            next_action="rollback",
        )

    with patch("agent_runtime.runtime_task_create.validate_records", side_effect=_failing_validate):
        result = create_task(
            root,
            file=None,
            stdin=False,
            commit=True,
            tasks_file="tasks/tasks.jsonl",
            events_file="tasks/events.jsonl",
            candidate=candidate,
        )

    assert result.status == "validation_failed"
    assert result.committed is False
    assert result.rolled_back is True
    assert tasks_file.stat().st_size == original_size
    assert tasks_file.read_text(encoding="utf-8").count("\n") == 1


def test_commit_rollback_failure_returns_error(tmp_path):
    root = _setup_fake_root(tmp_path)
    task_id = "task-20260706-002"
    tasks_file = _write_tasks(root, _task("task-20260706-001"))
    candidate = _task(task_id)

    def _failing_validate(*args, **kwargs):
        from agent_runtime.result import CheckResult, Finding

        return CheckResult(
            status="validation_failed",
            findings=[Finding(rule_id="post-validate-failure", severity="error", action="error", message="simulated")],
            next_action="rollback",
        )

    def _failing_rollback(*args, **kwargs):
        return False, "simulated rollback failure"

    with patch("agent_runtime.runtime_task_create.validate_records", side_effect=_failing_validate):
        with patch("agent_runtime.runtime_task_create._rollback_tasks_file", side_effect=_failing_rollback):
            result = create_task(
                root,
                file=None,
                stdin=False,
                commit=True,
                tasks_file="tasks/tasks.jsonl",
                events_file="tasks/events.jsonl",
                candidate=candidate,
            )

    assert result.status == "error"
    assert result.committed is False
    assert result.rolled_back is False
    assert result.rollback_error == "simulated rollback failure"


def test_commit_stdin_pass(tmp_path, monkeypatch, capsys):
    root = _setup_fake_root(tmp_path)
    task_id = "task-20260706-002"
    tasks_file = _write_tasks(root, _task("task-20260706-001"))
    payload = json.dumps(_task(task_id), ensure_ascii=False)

    monkeypatch.setattr("sys.stdin", io.StringIO(payload))
    monkeypatch.setattr(
        "sys.argv",
        ["agent-runtime", "--root", str(root), "runtime", "task", "create", "--stdin", "--commit"],
    )
    assert main() == 0
    captured = capsys.readouterr()
    assert "PASS" in captured.out
    assert "committed=True" in captured.out
    assert tasks_file.read_text(encoding="utf-8").count("\n") == 2


def test_commit_json_output_sanitized(tmp_path, monkeypatch, capsys):
    root = _setup_fake_root(tmp_path)
    task_id = "task-20260706-002"
    _write_tasks(root, _task("task-20260706-001"))
    title = "sensitive task title that must not leak"
    summary = "sensitive summary that must not leak"
    candidate_file = _candidate_file(
        root,
        {
            **_task(task_id, title=title),
            "summary": summary,
        },
    )

    monkeypatch.setattr(
        "sys.argv",
        ["agent-runtime", "--root", str(root), "runtime", "task", "create", "--file", str(candidate_file), "--commit", "--json"],
    )
    assert main() == 0
    captured = capsys.readouterr()
    out = json.loads(captured.out)
    assert out["status"] == "pass"
    assert out["committed"] is True
    assert out["title_present"] is True
    assert title not in captured.out
    assert summary not in captured.out


def test_commit_does_not_write_events_ledger(tmp_path):
    root = _setup_fake_root(tmp_path)
    task_id = "task-20260706-002"
    tasks_file = _write_tasks(root, _task("task-20260706-001"))
    events_file = root / "tasks" / "events.jsonl"
    candidate = _task(task_id)

    result = create_task(
        root,
        file=None,
        stdin=False,
        commit=True,
        tasks_file="tasks/tasks.jsonl",
        events_file="tasks/events.jsonl",
        candidate=candidate,
    )

    assert result.status == "pass"
    assert result.committed is True
    assert tasks_file.read_text(encoding="utf-8").count("\n") == 2
    assert not events_file.exists()


def test_commit_git_path_blocked(tmp_path):
    root = _setup_fake_root(tmp_path)
    git_dir = root / ".git"
    git_dir.mkdir()
    git_tasks = git_dir / "tasks.jsonl"
    git_tasks.write_text("", encoding="utf-8")
    candidate = _task("task-20260706-002")

    result = create_task(
        root,
        file=None,
        stdin=False,
        commit=True,
        tasks_file=".git/tasks.jsonl",
        events_file="tasks/events.jsonl",
        candidate=candidate,
    )

    assert result.status == "error"
    assert any(f.rule_id == "unsafe-tasks-file" for f in result.findings)
    assert not git_tasks.read_text(encoding="utf-8").endswith("task-20260706-002")


def test_commit_credential_path_blocked(tmp_path):
    root = _setup_fake_root(tmp_path)
    cred_dir = root / "credentials"
    cred_dir.mkdir()
    cred_tasks = cred_dir / "tasks.jsonl"
    cred_tasks.write_text("", encoding="utf-8")
    candidate = _task("task-20260706-002")

    result = create_task(
        root,
        file=None,
        stdin=False,
        commit=True,
        tasks_file="credentials/tasks.jsonl",
        events_file="tasks/events.jsonl",
        candidate=candidate,
    )

    assert result.status == "error"
    assert any(f.rule_id == "unsafe-tasks-file" for f in result.findings)
    assert cred_tasks.read_text(encoding="utf-8") == ""


def test_commit_env_file_blocked(tmp_path):
    root = _setup_fake_root(tmp_path)
    env_tasks = root / "tasks" / ".env.jsonl"
    env_tasks.parent.mkdir(parents=True, exist_ok=True)
    env_tasks.write_text("", encoding="utf-8")
    candidate = _task("task-20260706-002")

    result = create_task(
        root,
        file=None,
        stdin=False,
        commit=True,
        tasks_file="tasks/.env.jsonl",
        events_file="tasks/events.jsonl",
        candidate=candidate,
    )

    assert result.status == "error"
    assert any(f.rule_id == "unsafe-tasks-file" for f in result.findings)
    assert env_tasks.read_text(encoding="utf-8") == ""


def test_commit_sample_ledger_case_insensitive(tmp_path):
    root = _setup_fake_root(tmp_path)
    (root / "tasks").mkdir(exist_ok=True)
    sample = root / "tasks" / "examples.JSONL"
    sample.write_text("", encoding="utf-8")
    candidate = _task("task-20260706-002")

    result = create_task(
        root,
        file=None,
        stdin=False,
        commit=True,
        tasks_file="tasks/examples.JSONL",
        events_file="tasks/events.jsonl",
        candidate=candidate,
    )

    assert result.status == "error"
    assert any(f.rule_id == "sample-ledger-write-blocked" for f in result.findings)
    assert sample.read_text(encoding="utf-8") == ""
