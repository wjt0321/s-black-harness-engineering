"""Tests for runtime event import --dry-run.

All tests run in temporary directories and assert that no real ledger files
are modified.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from agent_runtime.cli import main
from agent_runtime.runtime_event_import import import_events_dry_run

ROOT = Path(__file__).resolve().parents[1]


def _setup_fake_root(tmp_path: Path) -> Path:
    """Create a fake project root with the schemas and policies needed."""
    fake_root = tmp_path / "project"
    fake_root.mkdir(parents=True, exist_ok=True)

    for src_rel in (
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


def _evt(event_id, task_id, event_type, from_status, to_status, message, timestamp):
    return {
        "event_id": event_id,
        "task_id": task_id,
        "timestamp": timestamp,
        "actor": "cli",
        "event_type": event_type,
        "from_status": from_status,
        "to_status": to_status,
        "message": message,
        "artifacts": [],
        "metadata": {},
    }


def _write_task(root: Path, task_id: str, status: str = "running") -> Path:
    tasks_dir = root / "tasks"
    tasks_dir.mkdir(exist_ok=True)
    tasks_file = tasks_dir / "tasks.jsonl"
    tasks_file.write_text(
        json.dumps(
            {
                "id": task_id,
                "title": "test task",
                "status": status,
                "assignee": "cli",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return tasks_file


def _write_events(root: Path, *events) -> Path:
    events_file = root / "tasks" / "events.jsonl"
    events_file.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(e, ensure_ascii=False) for e in events]
    events_file.write_text("\n".join(lines) + "\n" if lines else "", encoding="utf-8")
    return events_file


def _write_candidates(root: Path, filename: str, *events, blank_lines: int = 0) -> Path:
    candidates_file = root / filename
    lines = [json.dumps(e, ensure_ascii=False) for e in events]
    for _ in range(blank_lines):
        lines.append("")
    candidates_file.write_text("\n".join(lines) + "\n" if lines else "", encoding="utf-8")
    return candidates_file


def test_import_event_dry_run_pass(tmp_path):
    root = _setup_fake_root(tmp_path)
    task_id = "task-20260707-001"
    _write_task(root, task_id, status="running")
    events_file = _write_events(
        root,
        _evt("evt-20260707-001", task_id, "created", None, "planned", "c", "2026-07-07T10:00:00+08:00"),
    )
    candidates_file = _write_candidates(
        root,
        "candidates.jsonl",
        _evt("evt-20260707-002", task_id, "status_changed", "planned", "running", "s", "2026-07-07T10:01:00+08:00"),
    )

    result = import_events_dry_run(
        root,
        file="candidates.jsonl",
        tasks_file="tasks/tasks.jsonl",
        events_file="tasks/events.jsonl",
    )

    assert result.status == "pass"
    assert result.source == "candidates.jsonl"
    assert result.event_count == 1
    assert result.blank_line_count == 0
    assert result.task_count == 1
    assert result.event_type_counts == {"status_changed": 1}
    assert result.candidate_event_ids_present == ["evt-20260707-002"]
    assert result.would_import is True
    assert result.ledger_check == "pass"
    assert events_file.read_text(encoding="utf-8").count("\n") == 1


def _write_tasks(root: Path, *tasks) -> Path:
    tasks_dir = root / "tasks"
    tasks_dir.mkdir(exist_ok=True)
    tasks_file = tasks_dir / "tasks.jsonl"
    lines = [json.dumps(t, ensure_ascii=False) for t in tasks]
    tasks_file.write_text("\n".join(lines) + "\n" if lines else "", encoding="utf-8")
    return tasks_file


def test_import_event_dry_run_multiple_events_and_tasks(tmp_path):
    root = _setup_fake_root(tmp_path)
    task_a = "task-20260707-001"
    task_b = "task-20260707-002"
    _write_tasks(
        root,
        {"id": task_a, "title": "task a", "status": "running", "assignee": "cli"},
        {"id": task_b, "title": "task b", "status": "planned", "assignee": "cli"},
    )
    _write_events(
        root,
        _evt("evt-20260707-001", task_a, "created", None, "planned", "c", "2026-07-07T10:00:00+08:00"),
        _evt("evt-20260707-002", task_a, "status_changed", "planned", "running", "s", "2026-07-07T10:00:01+08:00"),
        _evt("evt-20260707-003", task_b, "created", None, "planned", "c", "2026-07-07T10:00:00+08:00"),
    )
    candidates_file = _write_candidates(
        root,
        "candidates.jsonl",
        _evt("evt-20260707-004", task_a, "progress", "running", "running", "p", "2026-07-07T10:01:00+08:00"),
        _evt("evt-20260707-005", task_b, "assigned", "planned", "planned", "a", "2026-07-07T10:02:00+08:00"),
    )

    result = import_events_dry_run(
        root,
        file="candidates.jsonl",
        tasks_file="tasks/tasks.jsonl",
        events_file="tasks/events.jsonl",
    )

    assert result.status == "pass"
    assert result.event_count == 2
    assert result.task_count == 2
    assert result.event_type_counts == {"progress": 1, "assigned": 1}
    assert result.would_import is True


def test_import_event_dry_run_file_not_found(tmp_path):
    root = _setup_fake_root(tmp_path)
    result = import_events_dry_run(root, file="missing.jsonl")
    assert result.status == "error"
    assert any(f.rule_id == "candidate-not-found" for f in result.findings)


def test_import_event_dry_run_outside_root(tmp_path):
    root = _setup_fake_root(tmp_path)
    outside = tmp_path / "outside.jsonl"
    outside.write_text("{}", encoding="utf-8")
    result = import_events_dry_run(root, file=str(outside))
    assert result.status == "error"
    assert any(f.rule_id == "candidate-outside-root" for f in result.findings)


def test_import_event_dry_run_wrong_suffix(tmp_path):
    root = _setup_fake_root(tmp_path)
    bad = root / "candidates.txt"
    bad.write_text("{}", encoding="utf-8")
    result = import_events_dry_run(root, file="candidates.txt")
    assert result.status == "error"
    assert any(f.rule_id == "unsafe-candidate-file" for f in result.findings)


def test_import_event_dry_run_git_path(tmp_path):
    root = _setup_fake_root(tmp_path)
    git_dir = root / ".git"
    git_dir.mkdir()
    bad = git_dir / "candidates.jsonl"
    bad.write_text("{}", encoding="utf-8")
    result = import_events_dry_run(root, file=".git/candidates.jsonl")
    assert result.status == "error"
    assert any(f.rule_id == "unsafe-candidate-file" for f in result.findings)


def test_import_event_dry_run_invalid_json(tmp_path):
    root = _setup_fake_root(tmp_path)
    task_id = "task-20260707-001"
    _write_task(root, task_id)
    candidates = root / "candidates.jsonl"
    candidates.write_text("this is not json\n", encoding="utf-8")

    result = import_events_dry_run(root, file="candidates.jsonl")
    assert result.status == "validation_failed"
    assert any(f.rule_id == "invalid-json" and f.line == 1 for f in result.findings)


def test_import_event_dry_run_not_object(tmp_path):
    root = _setup_fake_root(tmp_path)
    task_id = "task-20260707-001"
    _write_task(root, task_id)
    candidates = root / "candidates.jsonl"
    candidates.write_text("[1, 2, 3]\n", encoding="utf-8")

    result = import_events_dry_run(root, file="candidates.jsonl")
    assert result.status == "validation_failed"
    assert any(f.rule_id == "candidate-not-object" for f in result.findings)


def test_import_event_dry_run_schema_invalid(tmp_path):
    root = _setup_fake_root(tmp_path)
    task_id = "task-20260707-001"
    _write_task(root, task_id)
    candidates = root / "candidates.jsonl"
    candidates.write_text(json.dumps({"event_id": "bad", "task_id": task_id}) + "\n", encoding="utf-8")

    result = import_events_dry_run(root, file="candidates.jsonl")
    assert result.status == "validation_failed"
    assert any(f.rule_id == "event-schema-validation-failed" for f in result.findings)


def test_import_event_dry_run_duplicate_within_candidates(tmp_path):
    root = _setup_fake_root(tmp_path)
    task_id = "task-20260707-001"
    _write_task(root, task_id)
    dup_id = "evt-20260707-002"
    candidates = _write_candidates(
        root,
        "candidates.jsonl",
        _evt(dup_id, task_id, "progress", "running", "running", "p1", "2026-07-07T10:01:00+08:00"),
        _evt(dup_id, task_id, "progress", "running", "running", "p2", "2026-07-07T10:02:00+08:00"),
    )

    result = import_events_dry_run(root, file="candidates.jsonl")
    assert result.status == "validation_failed"
    assert any(
        f.rule_id == "duplicate-candidate-event-id" and f.line == 2
        for f in result.findings
    )


def test_import_event_dry_run_duplicate_with_existing_ledger(tmp_path):
    root = _setup_fake_root(tmp_path)
    task_id = "task-20260707-001"
    _write_task(root, task_id)
    _write_events(
        root,
        _evt("evt-20260707-001", task_id, "created", None, "planned", "c", "2026-07-07T10:00:00+08:00"),
    )
    _write_candidates(
        root,
        "candidates.jsonl",
        _evt("evt-20260707-001", task_id, "status_changed", "planned", "running", "s", "2026-07-07T10:01:00+08:00"),
    )

    result = import_events_dry_run(root, file="candidates.jsonl")
    assert result.status == "validation_failed"
    assert any(f.rule_id == "duplicate-event-id" for f in result.findings)


def test_import_event_dry_run_unknown_task(tmp_path):
    root = _setup_fake_root(tmp_path)
    _write_task(root, "task-20260707-001")
    _write_candidates(
        root,
        "candidates.jsonl",
        _evt("evt-20260707-002", "task-20260707-999", "created", None, "planned", "c", "2026-07-07T10:01:00+08:00"),
    )

    result = import_events_dry_run(root, file="candidates.jsonl")
    assert result.status == "validation_failed"
    assert any(f.rule_id == "unknown-task-id" for f in result.findings)


def test_import_event_dry_run_illegal_status_transition(tmp_path):
    root = _setup_fake_root(tmp_path)
    task_id = "task-20260707-001"
    _write_task(root, task_id, status="finished")
    _write_events(
        root,
        _evt("evt-20260707-001", task_id, "created", None, "planned", "c", "2026-07-07T10:00:00+08:00"),
        _evt("evt-20260707-002", task_id, "finished", "planned", "finished", "done", "2026-07-07T10:01:00+08:00"),
    )
    _write_candidates(
        root,
        "candidates.jsonl",
        _evt("evt-20260707-003", task_id, "status_changed", "finished", "running", "back", "2026-07-07T10:02:00+08:00"),
    )

    result = import_events_dry_run(root, file="candidates.jsonl")
    assert result.status == "validation_failed"
    assert any(f.rule_id == "terminal-status-reverted" for f in result.findings)


def test_import_event_dry_run_secret_blocked(tmp_path):
    root = _setup_fake_root(tmp_path)
    task_id = "task-20260707-001"
    _write_task(root, task_id)
    token = "ghp_" + "X" * 36
    _write_candidates(
        root,
        "candidates.jsonl",
        _evt("evt-20260707-002", task_id, "progress", "running", "running", token, "2026-07-07T10:01:00+08:00"),
    )

    result = import_events_dry_run(root, file="candidates.jsonl")
    assert result.status == "blocked"
    rendered = result.render_json()
    assert token not in rendered


def test_import_event_dry_run_public_scan_blocked(tmp_path):
    root = _setup_fake_root(tmp_path)
    task_id = "task-20260707-001"
    _write_task(root, task_id)
    # Construct a Windows absolute path dynamically so the test source does not
    # itself trigger the repository public scan.
    sensitive_path = "C:" + "\\secret.txt"
    _write_candidates(
        root,
        "candidates.jsonl",
        _evt("evt-20260707-002", task_id, "progress", "running", "running", "report at " + sensitive_path, "2026-07-07T10:01:00+08:00"),
    )

    result = import_events_dry_run(root, file="candidates.jsonl")
    assert result.status == "blocked"
    rendered = result.render_json()
    assert sensitive_path not in rendered
    assert any(
        f.rule_id == "windows-absolute-path" and "Public scan rule hit" in f.message
        for f in result.findings
    )


def test_import_event_dry_run_blank_lines_ignored(tmp_path):
    root = _setup_fake_root(tmp_path)
    task_id = "task-20260707-001"
    _write_task(root, task_id)
    _write_events(
        root,
        _evt("evt-20260707-001", task_id, "created", None, "planned", "c", "2026-07-07T10:00:00+08:00"),
    )
    candidates = root / "candidates.jsonl"
    lines = [
        "",
        json.dumps(_evt("evt-20260707-002", task_id, "progress", "running", "running", "p", "2026-07-07T10:01:00+08:00")),
        "",
        "",
    ]
    candidates.write_text("\n".join(lines) + "\n", encoding="utf-8")

    result = import_events_dry_run(root, file="candidates.jsonl")
    assert result.status == "pass"
    assert result.event_count == 1
    assert result.blank_line_count == 3


def test_import_event_dry_run_does_not_modify_ledgers(tmp_path):
    root = _setup_fake_root(tmp_path)
    task_id = "task-20260707-001"
    _write_task(root, task_id, status="running")
    events_file = _write_events(
        root,
        _evt("evt-20260707-001", task_id, "created", None, "planned", "c", "2026-07-07T10:00:00+08:00"),
        _evt("evt-20260707-002", task_id, "status_changed", "planned", "running", "s", "2026-07-07T10:01:00+08:00"),
    )
    original_events = events_file.read_text(encoding="utf-8")
    _write_candidates(
        root,
        "candidates.jsonl",
        _evt("evt-20260707-003", task_id, "progress", "running", "running", "p", "2026-07-07T10:02:00+08:00"),
    )

    result = import_events_dry_run(root, file="candidates.jsonl")
    assert result.status == "pass"
    assert events_file.read_text(encoding="utf-8") == original_events


def test_cli_import_event_dry_run_pass(tmp_path, monkeypatch, capsys):
    root = _setup_fake_root(tmp_path)
    task_id = "task-20260707-001"
    _write_task(root, task_id, status="running")
    events_file = _write_events(
        root,
        _evt("evt-20260707-001", task_id, "created", None, "planned", "c", "2026-07-07T10:00:00+08:00"),
    )
    _write_candidates(
        root,
        "candidates.jsonl",
        _evt("evt-20260707-002", task_id, "status_changed", "planned", "running", "s", "2026-07-07T10:01:00+08:00"),
    )

    monkeypatch.setattr(
        "sys.argv",
        [
            "agent-runtime",
            "--root",
            str(root),
            "runtime",
            "event",
            "import",
            "--file",
            "candidates.jsonl",
            "--dry-run",
        ],
    )
    assert main() == 0
    captured = capsys.readouterr()
    assert "PASS" in captured.out
    assert "would_import=True" in captured.out
    assert events_file.read_text(encoding="utf-8").count("\n") == 1


def test_cli_import_event_dry_run_missing_dry_run(tmp_path, monkeypatch, capsys):
    root = _setup_fake_root(tmp_path)
    task_id = "task-20260707-001"
    _write_task(root, task_id)
    _write_candidates(
        root,
        "candidates.jsonl",
        _evt("evt-20260707-002", task_id, "created", None, "planned", "c", "2026-07-07T10:01:00+08:00"),
    )

    monkeypatch.setattr(
        "sys.argv",
        [
            "agent-runtime",
            "--root",
            str(root),
            "runtime",
            "event",
            "import",
            "--file",
            "candidates.jsonl",
        ],
    )
    assert main() == 1
    captured = capsys.readouterr()
    assert "missing-dry-run" in captured.out


def test_cli_import_event_dry_run_json_output_sanitized(tmp_path, monkeypatch, capsys):
    root = _setup_fake_root(tmp_path)
    task_id = "task-20260707-001"
    _write_task(root, task_id, status="running")
    _write_events(
        root,
        _evt("evt-20260707-001", task_id, "created", None, "planned", "c", "2026-07-07T10:00:00+08:00"),
    )
    message = "detailed progress message should not appear"
    _write_candidates(
        root,
        "candidates.jsonl",
        _evt("evt-20260707-002", task_id, "progress", "running", "running", message, "2026-07-07T10:01:00+08:00"),
    )

    monkeypatch.setattr(
        "sys.argv",
        [
            "agent-runtime",
            "--root",
            str(root),
            "runtime",
            "event",
            "import",
            "--file",
            "candidates.jsonl",
            "--dry-run",
            "--json",
        ],
    )
    assert main() == 0
    captured = capsys.readouterr()
    out = json.loads(captured.out)
    assert out["status"] == "pass"
    assert out["would_import"] is True
    assert message not in captured.out


def test_import_event_dry_run_duplicate_existing_id_line_number_after_filtered_lines(tmp_path):
    root = _setup_fake_root(tmp_path)
    task_id = "task-20260707-001"
    _write_task(root, task_id)
    _write_events(
        root,
        _evt("evt-20260707-001", task_id, "created", None, "planned", "c", "2026-07-07T10:00:00+08:00"),
    )
    candidates = root / "candidates.jsonl"
    lines = [
        "",  # line 1: blank
        "not json",  # line 2: invalid JSON
        "[1, 2, 3]",  # line 3: not an object
        json.dumps({"event_id": "bad", "task_id": task_id}),  # line 4: schema invalid
        # line 5: valid candidate, will be retained
        json.dumps(_evt("evt-20260707-002", task_id, "progress", "running", "running", "p1", "2026-07-07T10:01:00+08:00")),
        # line 6: duplicates existing ledger event_id
        json.dumps(_evt("evt-20260707-001", task_id, "progress", "running", "running", "p2", "2026-07-07T10:02:00+08:00")),
    ]
    candidates.write_text("\n".join(lines) + "\n", encoding="utf-8")

    result = import_events_dry_run(root, file="candidates.jsonl")
    assert result.status == "validation_failed"
    dup_findings = [f for f in result.findings if f.rule_id == "duplicate-event-id"]
    assert len(dup_findings) == 1
    assert dup_findings[0].line == 6


def test_import_event_dry_run_unknown_task_line_number_after_filtered_lines(tmp_path):
    root = _setup_fake_root(tmp_path)
    _write_task(root, "task-20260707-001")
    candidates = root / "candidates.jsonl"
    lines = [
        "",  # line 1: blank
        "not json",  # line 2: invalid JSON
        json.dumps({"event_id": "bad", "task_id": "task-20260707-001"}),  # line 3: schema invalid
        # line 4: valid candidate referencing unknown task
        json.dumps(_evt("evt-20260707-002", "task-20260707-999", "created", None, "planned", "c", "2026-07-07T10:01:00+08:00")),
    ]
    candidates.write_text("\n".join(lines) + "\n", encoding="utf-8")

    result = import_events_dry_run(root, file="candidates.jsonl")
    assert result.status == "validation_failed"
    unknown_findings = [f for f in result.findings if f.rule_id == "unknown-task-id"]
    assert len(unknown_findings) == 1
    assert unknown_findings[0].line == 4
