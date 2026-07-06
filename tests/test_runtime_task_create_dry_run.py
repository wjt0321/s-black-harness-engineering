"""Tests for runtime task create --dry-run.

All tests run in temporary directories and assert that no real ledger files
are modified.
"""

from __future__ import annotations

import io
import json
import shutil
from pathlib import Path

import pytest

from agent_runtime.cli import main
from agent_runtime.runtime_task_create import create_task_dry_run

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


def test_create_task_dry_run_pass(tmp_path):
    root = _setup_fake_root(tmp_path)
    task_id = "task-20260706-001"
    tasks_file = _write_tasks(root, _task("task-20260706-000"))
    candidate = _task(task_id, tags=["a", "b"], artifacts=["art1"], evidence=[{"type": "note", "description": "x", "ref": None}])

    result = create_task_dry_run(
        root,
        file=None,
        stdin=False,
        dry_run=True,
        tasks_file="tasks/tasks.jsonl",
        events_file="tasks/events.jsonl",
        candidate=candidate,
    )

    assert result.status == "pass"
    assert result.task_id == task_id
    assert result.task_status == "planned"
    assert result.title_present is True
    assert result.assignee_present is True
    assert result.tag_count == 2
    assert result.artifact_count == 1
    assert result.evidence_count == 1
    assert result.would_create is False
    assert result.ledger_check == "pass"
    assert tasks_file.read_text(encoding="utf-8").count("\n") == 1


def test_create_task_dry_run_pass_no_existing_events(tmp_path):
    root = _setup_fake_root(tmp_path)
    task_id = "task-20260706-001"
    _write_tasks(root)
    candidate = _task(task_id)

    result = create_task_dry_run(
        root,
        file=None,
        stdin=False,
        dry_run=True,
        tasks_file="tasks/tasks.jsonl",
        events_file="tasks/events.jsonl",
        candidate=candidate,
    )

    assert result.status == "pass"
    assert result.ledger_check == "pass"


def test_create_task_dry_run_schema_invalid(tmp_path):
    root = _setup_fake_root(tmp_path)
    _write_tasks(root)
    candidate = {"id": "task-20260706-001", "status": "planned"}

    result = create_task_dry_run(
        root,
        file=None,
        stdin=False,
        dry_run=True,
        tasks_file="tasks/tasks.jsonl",
        events_file="tasks/events.jsonl",
        candidate=candidate,
    )

    assert result.status == "validation_failed"
    assert any(f.rule_id == "task-schema-validation-failed" for f in result.findings)


def test_create_task_dry_run_candidate_not_object(tmp_path):
    root = _setup_fake_root(tmp_path)
    _write_tasks(root)

    result = create_task_dry_run(
        root,
        file=None,
        stdin=False,
        dry_run=True,
        tasks_file="tasks/tasks.jsonl",
        events_file="tasks/events.jsonl",
        candidate=["not", "an", "object"],
    )

    assert result.status in ("error", "validation_failed")
    assert any(
        f.rule_id in {"candidate-not-object", "task-schema-validation-failed"}
        for f in result.findings
    )


def test_create_task_dry_run_duplicate_task_id(tmp_path):
    root = _setup_fake_root(tmp_path)
    task_id = "task-20260706-001"
    _write_tasks(root, _task(task_id))
    candidate = _task(task_id, title="different title")

    result = create_task_dry_run(
        root,
        file=None,
        stdin=False,
        dry_run=True,
        tasks_file="tasks/tasks.jsonl",
        events_file="tasks/events.jsonl",
        candidate=candidate,
    )

    assert result.status == "validation_failed"
    assert any(f.rule_id == "duplicate-task-id" for f in result.findings)


def test_create_task_dry_run_secret_blocked(tmp_path):
    root = _setup_fake_root(tmp_path)
    _write_tasks(root)
    token = "ghp_" + "X" * 36
    candidate = _task("task-20260706-001", title=token)

    result = create_task_dry_run(
        root,
        file=None,
        stdin=False,
        dry_run=True,
        tasks_file="tasks/tasks.jsonl",
        events_file="tasks/events.jsonl",
        candidate=candidate,
    )

    assert result.status == "blocked"
    rendered = result.render_json()
    assert token not in rendered


def test_create_task_dry_run_public_scan_blocked(tmp_path):
    root = _setup_fake_root(tmp_path)
    _write_tasks(root)
    sensitive_path = "D:" + "/secret/path"
    candidate = _task("task-20260706-001", title=sensitive_path)

    result = create_task_dry_run(
        root,
        file=None,
        stdin=False,
        dry_run=True,
        tasks_file="tasks/tasks.jsonl",
        events_file="tasks/events.jsonl",
        candidate=candidate,
    )

    assert result.status == "blocked"
    rendered = result.render_json()
    assert sensitive_path not in rendered


def test_cli_file_dry_run_pass(tmp_path, monkeypatch, capsys):
    root = _setup_fake_root(tmp_path)
    task_id = "task-20260706-001"
    tasks_file = _write_tasks(root, _task("task-20260706-000"))
    candidate_file = root / "candidate.json"
    candidate_file.write_text(
        json.dumps(_task(task_id), ensure_ascii=False),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "sys.argv",
        ["agent-runtime", "--root", str(root), "runtime", "task", "create", "--file", str(candidate_file), "--dry-run"],
    )
    assert main() == 0
    captured = capsys.readouterr()
    assert "PASS" in captured.out
    assert tasks_file.read_text(encoding="utf-8").count("\n") == 1


def test_cli_stdin_dry_run_pass(tmp_path, monkeypatch, capsys):
    root = _setup_fake_root(tmp_path)
    task_id = "task-20260706-001"
    tasks_file = _write_tasks(root, _task("task-20260706-000"))
    payload = json.dumps(_task(task_id), ensure_ascii=False)

    monkeypatch.setattr("sys.stdin", io.StringIO(payload))
    monkeypatch.setattr(
        "sys.argv",
        ["agent-runtime", "--root", str(root), "runtime", "task", "create", "--stdin", "--dry-run"],
    )
    assert main() == 0
    captured = capsys.readouterr()
    assert "PASS" in captured.out
    assert tasks_file.read_text(encoding="utf-8").count("\n") == 1


def test_cli_missing_dry_run(tmp_path, monkeypatch, capsys):
    root = _setup_fake_root(tmp_path)
    _write_tasks(root)
    candidate_file = root / "candidate.json"
    candidate_file.write_text(json.dumps(_task("task-20260706-001"), ensure_ascii=False), encoding="utf-8")

    monkeypatch.setattr(
        "sys.argv",
        ["agent-runtime", "--root", str(root), "runtime", "task", "create", "--file", str(candidate_file)],
    )
    assert main() == 1
    captured = capsys.readouterr()
    assert "missing-dry-run" in captured.out


def test_cli_commit_not_implemented(tmp_path, monkeypatch, capsys):
    root = _setup_fake_root(tmp_path)
    _write_tasks(root)
    candidate_file = root / "candidate.json"
    candidate_file.write_text(json.dumps(_task("task-20260706-001"), ensure_ascii=False), encoding="utf-8")

    monkeypatch.setattr(
        "sys.argv",
        ["agent-runtime", "--root", str(root), "runtime", "task", "create", "--file", str(candidate_file), "--commit"],
    )
    assert main() == 1
    captured = capsys.readouterr()
    assert "commit-not-implemented" in captured.out


def test_cli_json_output_sanitized(tmp_path, monkeypatch, capsys):
    root = _setup_fake_root(tmp_path)
    task_id = "task-20260706-001"
    _write_tasks(root)
    title = "sensitive task title that must not leak"
    summary = "sensitive summary that must not leak"
    candidate_file = root / "candidate.json"
    candidate_file.write_text(
        json.dumps(
            {
                **_task(task_id, title=title),
                "summary": summary,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "sys.argv",
        ["agent-runtime", "--root", str(root), "runtime", "task", "create", "--file", str(candidate_file), "--dry-run", "--json"],
    )
    assert main() == 0
    captured = capsys.readouterr()
    out = json.loads(captured.out)
    assert out["status"] == "pass"
    assert out["title_present"] is True
    assert title not in captured.out
    assert summary not in captured.out


def test_cli_tasks_file_outside_root_blocked(tmp_path, monkeypatch, capsys):
    root = _setup_fake_root(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    outside_tasks = outside / "tasks.jsonl"
    outside_tasks.write_text("", encoding="utf-8")
    candidate_file = root / "candidate.json"
    candidate_file.write_text(json.dumps(_task("task-20260706-001"), ensure_ascii=False), encoding="utf-8")

    monkeypatch.setattr(
        "sys.argv",
        ["agent-runtime", "--root", str(root), "runtime", "task", "create", "--file", str(candidate_file), "--dry-run", "--tasks-file", str(outside_tasks)],
    )
    assert main() == 1
    captured = capsys.readouterr()
    assert "tasks-file-outside-root" in captured.out


def test_cli_unsafe_tasks_suffix_blocked(tmp_path, monkeypatch, capsys):
    root = _setup_fake_root(tmp_path)
    (root / "tasks").mkdir(exist_ok=True)
    bad_tasks = root / "tasks" / "tasks.txt"
    bad_tasks.write_text("", encoding="utf-8")
    candidate_file = root / "candidate.json"
    candidate_file.write_text(json.dumps(_task("task-20260706-001"), ensure_ascii=False), encoding="utf-8")

    monkeypatch.setattr(
        "sys.argv",
        ["agent-runtime", "--root", str(root), "runtime", "task", "create", "--file", str(candidate_file), "--dry-run", "--tasks-file", "tasks/tasks.txt"],
    )
    assert main() == 1
    captured = capsys.readouterr()
    assert "unsafe-tasks-file" in captured.out


def test_runtime_task_create_cli_outputs_safe_summary(capsys, tmp_path):
    root = _setup_fake_root(tmp_path)
    task_id = "task-20260706-001"
    _write_tasks(root, _task("task-20260706-000"))
    title = "Detailed private title should not appear"
    candidate = _task(task_id, title=title, tags=["x"], artifacts=["a"])
    candidate_file = root / "candidate.json"
    candidate_file.write_text(json.dumps(candidate), encoding="utf-8")

    code = main([
        "--root", str(root),
        "runtime", "task", "create",
        "--file", "candidate.json",
        "--dry-run",
    ])
    captured = capsys.readouterr()

    assert code == 0
    assert "PASS" in captured.out
    assert "task_id=task-20260706-001" in captured.out
    assert "status=planned" in captured.out
    assert "title_present=True" in captured.out
    assert "tag_count=1" in captured.out
    assert "artifact_count=1" in captured.out
    assert "would_create=False" in captured.out
    assert "ledger_check=pass" in captured.out
    assert "Detailed private title" not in captured.out
