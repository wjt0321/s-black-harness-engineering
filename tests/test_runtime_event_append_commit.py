"""Tests for runtime event append --commit.

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
from agent_runtime.runtime_event_append import append_event

ROOT = Path(__file__).resolve().parents[1]


def _setup_fake_root(tmp_path: Path) -> Path:
    """Create a fake project root with the schemas and policies needed."""
    fake_root = tmp_path / "project"
    fake_root.mkdir(parents=True, exist_ok=True)

    for src_rel in (
        "tasks/event.schema.json",
        "tasks/task.schema.json",
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


def _candidate_file(root: Path, candidate: dict[str, object]) -> Path:
    candidate_file = root / "candidate.json"
    candidate_file.write_text(json.dumps(candidate, ensure_ascii=False), encoding="utf-8")
    return candidate_file


def test_commit_appends_one_line(tmp_path):
    root = _setup_fake_root(tmp_path)
    task_id = "task-20260705-001"
    _write_task(root, task_id, status="running")
    events_file = _write_events(
        root,
        _evt("evt-20260705-001", task_id, "created", None, "planned", "c", "2026-07-05T10:00:00+08:00"),
        _evt("evt-20260705-002", task_id, "status_changed", "planned", "running", "s", "2026-07-05T10:01:00+08:00"),
    )
    candidate = _evt("evt-20260705-003", task_id, "progress", "running", "running", "p", "2026-07-05T10:02:00+08:00")

    result = append_event(
        root,
        file=None,
        stdin=False,
        commit=True,
        tasks_file="tasks/tasks.jsonl",
        events_file="tasks/events.jsonl",
        envelope_file=None,
        candidate=candidate,
    )

    assert result.status == "pass"
    assert result.committed is True
    assert result.post_validate == "pass"
    assert result.post_ledger_check == "pass"
    assert result.would_append is True
    content = events_file.read_text(encoding="utf-8")
    assert content.count("\n") == 3
    assert '"event_id": "evt-20260705-003"' in content


def test_commit_with_envelope(tmp_path):
    root = _setup_fake_root(tmp_path)
    task_id = "task-20260705-001"
    _write_task(root, task_id, status="running")
    events_file = _write_events(
        root,
        _evt("evt-20260705-001", task_id, "created", None, "planned", "c", "2026-07-05T10:00:00+08:00"),
    )
    envelope_file = root / "envelope.json"
    envelope_file.write_text(
        json.dumps(
            {
                "version": 1,
                "description": "test envelope",
                "artifacts": [
                    {
                        "artifact_type": "adapter_request",
                        "request_id": "req-20260705-001",
                        "task_id": task_id,
                        "adapter_id": "github-cli",
                        "operation": "git_status",
                        "actor": "cli",
                        "target": "origin/main",
                        "input": {},
                        "context": {
                            "source": "cli",
                            "policy_profile": "all",
                            "risk_level": "local",
                            "dry_run": True,
                            "requires_approval": False,
                        },
                        "preflight": {"status": "pass", "findings": []},
                        "created_at": "2026-07-05T10:00:00+08:00",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    candidate = _evt("evt-20260705-002", task_id, "progress", "running", "running", "p", "2026-07-05T10:01:00+08:00")

    result = append_event(
        root,
        file=None,
        stdin=False,
        commit=True,
        tasks_file="tasks/tasks.jsonl",
        events_file="tasks/events.jsonl",
        envelope_file="envelope.json",
        candidate=candidate,
    )

    assert result.status == "pass"
    assert result.committed is True
    assert result.post_runtime_audit is not None
    assert events_file.read_text(encoding="utf-8").count("\n") == 2


def test_commit_dry_run_does_not_write(tmp_path, monkeypatch, capsys):
    root = _setup_fake_root(tmp_path)
    task_id = "task-20260705-001"
    _write_task(root, task_id, status="running")
    events_file = _write_events(
        root,
        _evt("evt-20260705-001", task_id, "created", None, "planned", "c", "2026-07-05T10:00:00+08:00"),
    )
    candidate_file = _candidate_file(
        root,
        _evt("evt-20260705-002", task_id, "status_changed", "planned", "running", "s", "2026-07-05T10:01:00+08:00"),
    )

    monkeypatch.setattr(
        "sys.argv",
        ["agent-runtime", "--root", str(root), "runtime", "event", "append", "--file", str(candidate_file), "--dry-run"],
    )
    assert main() == 0
    assert events_file.read_text(encoding="utf-8").count("\n") == 1


def test_commit_dry_run_commit_mutually_exclusive(tmp_path, monkeypatch, capsys):
    root = _setup_fake_root(tmp_path)
    task_id = "task-20260705-001"
    _write_task(root, task_id, status="running")
    candidate_file = _candidate_file(
        root,
        _evt("evt-20260705-002", task_id, "status_changed", "planned", "running", "s", "2026-07-05T10:01:00+08:00"),
    )

    monkeypatch.setattr(
        "sys.argv",
        [
            "agent-runtime",
            "--root",
            str(root),
            "runtime",
            "event",
            "append",
            "--file",
            str(candidate_file),
            "--dry-run",
            "--commit",
        ],
    )
    assert main() == 1
    captured = capsys.readouterr()
    assert "dry-run-commit-mutually-exclusive" in captured.out


def test_commit_missing_mode_error(tmp_path, monkeypatch, capsys):
    root = _setup_fake_root(tmp_path)
    task_id = "task-20260705-001"
    _write_task(root, task_id, status="running")
    candidate_file = _candidate_file(
        root,
        _evt("evt-20260705-002", task_id, "status_changed", "planned", "running", "s", "2026-07-05T10:01:00+08:00"),
    )

    monkeypatch.setattr(
        "sys.argv",
        ["agent-runtime", "--root", str(root), "runtime", "event", "append", "--file", str(candidate_file)],
    )
    assert main() == 1
    captured = capsys.readouterr()
    assert "missing-append-mode" in captured.out


def test_commit_schema_invalid_does_not_write(tmp_path):
    root = _setup_fake_root(tmp_path)
    task_id = "task-20260705-001"
    _write_task(root, task_id, status="running")
    events_file = _write_events(
        root,
        _evt("evt-20260705-001", task_id, "created", None, "planned", "c", "2026-07-05T10:00:00+08:00"),
    )
    candidate = {"event_id": "bad", "task_id": task_id}

    result = append_event(
        root,
        file=None,
        stdin=False,
        commit=True,
        tasks_file="tasks/tasks.jsonl",
        events_file="tasks/events.jsonl",
        candidate=candidate,
    )

    assert result.status == "validation_failed"
    assert any(f.rule_id == "event-schema-validation-failed" for f in result.findings)
    assert events_file.read_text(encoding="utf-8").count("\n") == 1


@pytest.mark.parametrize(
    "event_type",
    (
        "execution_attempt_started",
        "execution_succeeded",
        "execution_failed",
        "execution_cancelled",
    ),
)
@pytest.mark.parametrize("commit", (False, True))
def test_generic_append_blocks_reserved_execution_event_without_writing(
    tmp_path, event_type, commit
):
    root = _setup_fake_root(tmp_path)
    task_id = "task-20260705-001"
    _write_task(root, task_id, status="running")
    events_file = _write_events(
        root,
        _evt(
            "evt-20260705-001",
            task_id,
            "created",
            None,
            "planned",
            "c",
            "2026-07-05T10:00:00+08:00",
        ),
    )
    original_bytes = events_file.read_bytes()
    candidate = _evt(
        "evt-20260705-002",
        task_id,
        event_type,
        "running",
        "running",
        "reserved",
        "2026-07-05T10:01:00+08:00",
    )

    result = append_event(
        root,
        file=None,
        stdin=False,
        commit=commit,
        tasks_file="tasks/tasks.jsonl",
        events_file="tasks/events.jsonl",
        candidate=candidate,
    )

    assert result.status == "blocked"
    assert [finding.rule_id for finding in result.findings] == [
        "reserved-execution-event-type"
    ]
    assert events_file.read_bytes() == original_bytes


@pytest.mark.parametrize(
    "invalid_event_type",
    (
        ["withheld-event-type"],
        {"withheld-event-type": True},
    ),
)
def test_generic_append_non_string_event_type_is_value_safe_validation_failure(
    tmp_path, invalid_event_type
):
    root = _setup_fake_root(tmp_path)
    task_id = "task-20260705-001"
    _write_task(root, task_id, status="running")
    events_file = _write_events(
        root,
        _evt(
            "evt-20260705-001",
            task_id,
            "created",
            None,
            "planned",
            "c",
            "2026-07-05T10:00:00+08:00",
        ),
    )
    original_bytes = events_file.read_bytes()
    candidate = _evt(
        "evt-20260705-002",
        task_id,
        invalid_event_type,
        "running",
        "running",
        "invalid",
        "2026-07-05T10:01:00+08:00",
    )

    result = append_event(
        root,
        file=None,
        stdin=False,
        commit=True,
        tasks_file="tasks/tasks.jsonl",
        events_file="tasks/events.jsonl",
        candidate=candidate,
    )

    assert result.status == "validation_failed"
    assert [finding.rule_id for finding in result.findings] == [
        "event-schema-validation-failed"
    ]
    assert "withheld-event-type" not in result.render_json()
    assert events_file.read_bytes() == original_bytes


def test_commit_missing_task_does_not_write(tmp_path):
    root = _setup_fake_root(tmp_path)
    _write_task(root, "task-20260705-001", status="running")
    events_file = _write_events(
        root,
        _evt("evt-20260705-001", "task-20260705-001", "created", None, "planned", "c", "2026-07-05T10:00:00+08:00"),
    )
    candidate = _evt("evt-20260705-002", "task-20260705-999", "created", None, "planned", "c", "2026-07-05T10:01:00+08:00")

    result = append_event(
        root,
        file=None,
        stdin=False,
        commit=True,
        tasks_file="tasks/tasks.jsonl",
        events_file="tasks/events.jsonl",
        candidate=candidate,
    )

    assert result.status == "error"
    assert any(f.rule_id == "unknown-task-id" for f in result.findings)
    assert events_file.read_text(encoding="utf-8").count("\n") == 1


def test_commit_duplicate_event_id_does_not_write(tmp_path):
    root = _setup_fake_root(tmp_path)
    task_id = "task-20260705-001"
    _write_task(root, task_id, status="running")
    events_file = _write_events(
        root,
        _evt("evt-20260705-001", task_id, "created", None, "planned", "c", "2026-07-05T10:00:00+08:00"),
    )
    candidate = _evt("evt-20260705-001", task_id, "progress", "running", "running", "p", "2026-07-05T10:01:00+08:00")

    result = append_event(
        root,
        file=None,
        stdin=False,
        commit=True,
        tasks_file="tasks/tasks.jsonl",
        events_file="tasks/events.jsonl",
        candidate=candidate,
    )

    assert result.status == "validation_failed"
    assert any(f.rule_id == "duplicate-event-id" for f in result.findings)
    assert events_file.read_text(encoding="utf-8").count("\n") == 1


def test_commit_illegal_transition_does_not_write(tmp_path):
    root = _setup_fake_root(tmp_path)
    task_id = "task-20260705-001"
    _write_task(root, task_id, status="finished")
    events_file = _write_events(
        root,
        _evt("evt-20260705-001", task_id, "created", None, "planned", "c", "2026-07-05T10:00:00+08:00"),
        _evt("evt-20260705-002", task_id, "finished", "planned", "finished", "done", "2026-07-05T10:01:00+08:00"),
    )
    candidate = _evt("evt-20260705-003", task_id, "status_changed", "finished", "running", "back", "2026-07-05T10:02:00+08:00")

    result = append_event(
        root,
        file=None,
        stdin=False,
        commit=True,
        tasks_file="tasks/tasks.jsonl",
        events_file="tasks/events.jsonl",
        candidate=candidate,
    )

    assert result.status == "validation_failed"
    assert events_file.read_text(encoding="utf-8").count("\n") == 2


def test_commit_secret_blocked_does_not_write_or_leak(tmp_path):
    root = _setup_fake_root(tmp_path)
    task_id = "task-20260705-001"
    _write_task(root, task_id, status="running")
    events_file = _write_events(
        root,
        _evt("evt-20260705-001", task_id, "created", None, "planned", "c", "2026-07-05T10:00:00+08:00"),
    )
    token = "ghp_" + "X" * 36
    candidate = _evt("evt-20260705-002", task_id, "progress", "running", "running", token, "2026-07-05T10:01:00+08:00")

    result = append_event(
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
    assert events_file.read_text(encoding="utf-8").count("\n") == 1


def test_commit_public_scan_blocked_does_not_write_or_leak(tmp_path):
    root = _setup_fake_root(tmp_path)
    task_id = "task-20260705-001"
    _write_task(root, task_id, status="running")
    events_file = _write_events(
        root,
        _evt("evt-20260705-001", task_id, "created", None, "planned", "c", "2026-07-05T10:00:00+08:00"),
    )
    # A Windows absolute path triggers the public scan rule without being a secret.
    # Build dynamically so the test source does not itself contain a scannable path.
    drive = "C:"
    public_match = drive + "\\\\" + "\\\\".join(["Users", "wxb", "workspace"])
    candidate = _evt("evt-20260705-002", task_id, "progress", "running", "running", public_match, "2026-07-05T10:01:00+08:00")

    result = append_event(
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
    assert events_file.read_text(encoding="utf-8").count("\n") == 1


def test_commit_events_file_outside_root_blocked(tmp_path):
    root = _setup_fake_root(tmp_path)
    task_id = "task-20260705-001"
    _write_task(root, task_id, status="running")
    _write_events(
        root,
        _evt("evt-20260705-001", task_id, "created", None, "planned", "c", "2026-07-05T10:00:00+08:00"),
        _evt("evt-20260705-002", task_id, "status_changed", "planned", "running", "s", "2026-07-05T10:01:00+08:00"),
    )
    outside = tmp_path / "outside-events.jsonl"
    outside.write_text("", encoding="utf-8")
    candidate = _evt("evt-20260705-003", task_id, "progress", "running", "running", "p", "2026-07-05T10:02:00+08:00")

    result = append_event(
        root,
        file=None,
        stdin=False,
        commit=True,
        tasks_file="tasks/tasks.jsonl",
        events_file=str(outside),
        candidate=candidate,
    )

    assert result.status == "error"
    assert any(f.rule_id == "events-file-outside-root" for f in result.findings)


def test_commit_events_file_suffix_not_jsonl_blocked(tmp_path):
    root = _setup_fake_root(tmp_path)
    task_id = "task-20260705-001"
    _write_task(root, task_id, status="running")
    _write_events(
        root,
        _evt("evt-20260705-001", task_id, "created", None, "planned", "c", "2026-07-05T10:00:00+08:00"),
        _evt("evt-20260705-002", task_id, "status_changed", "planned", "running", "s", "2026-07-05T10:01:00+08:00"),
    )
    bad_file = root / "tasks" / "events.txt"
    bad_file.write_text("", encoding="utf-8")
    candidate = _evt("evt-20260705-003", task_id, "progress", "running", "running", "p", "2026-07-05T10:02:00+08:00")

    result = append_event(
        root,
        file=None,
        stdin=False,
        commit=True,
        tasks_file="tasks/tasks.jsonl",
        events_file="tasks/events.txt",
        candidate=candidate,
    )

    assert result.status == "error"
    assert any(f.rule_id == "unsafe-events-file" for f in result.findings)


def test_commit_events_parent_missing_blocked(tmp_path):
    root = _setup_fake_root(tmp_path)
    task_id = "task-20260705-001"
    _write_task(root, task_id, status="running")
    _write_events(
        root,
        _evt("evt-20260705-001", task_id, "created", None, "planned", "c", "2026-07-05T10:00:00+08:00"),
        _evt("evt-20260705-002", task_id, "status_changed", "planned", "running", "s", "2026-07-05T10:01:00+08:00"),
    )
    candidate = _evt("evt-20260705-003", task_id, "progress", "running", "running", "p", "2026-07-05T10:02:00+08:00")

    result = append_event(
        root,
        file=None,
        stdin=False,
        commit=True,
        tasks_file="tasks/tasks.jsonl",
        events_file="missing/events.jsonl",
        candidate=candidate,
    )

    assert result.status == "blocked"
    assert any(f.rule_id == "events-parent-missing" for f in result.findings)
    assert not (root / "missing").exists()


def test_commit_missing_trailing_newline_blocked(tmp_path):
    root = _setup_fake_root(tmp_path)
    task_id = "task-20260705-001"
    _write_task(root, task_id, status="running")
    events_file = root / "tasks" / "events.jsonl"
    events_file.parent.mkdir(parents=True, exist_ok=True)
    # Deliberately omit trailing newline.
    events_file.write_text(
        json.dumps(_evt("evt-20260705-001", task_id, "created", None, "planned", "c", "2026-07-05T10:00:00+08:00"))
        + "\n"
        + json.dumps(_evt("evt-20260705-002", task_id, "status_changed", "planned", "running", "s", "2026-07-05T10:01:00+08:00")),
        encoding="utf-8",
    )
    candidate = _evt("evt-20260705-003", task_id, "progress", "running", "running", "p", "2026-07-05T10:02:00+08:00")

    result = append_event(
        root,
        file=None,
        stdin=False,
        commit=True,
        tasks_file="tasks/tasks.jsonl",
        events_file="tasks/events.jsonl",
        candidate=candidate,
    )

    assert result.status == "blocked"
    assert any(f.rule_id == "events-file-missing-trailing-newline" for f in result.findings)
    content = events_file.read_bytes()
    assert not content.endswith(b"\n")


def test_commit_post_check_failure_rolls_back(tmp_path):
    root = _setup_fake_root(tmp_path)
    task_id = "task-20260705-001"
    _write_task(root, task_id, status="running")
    events_file = _write_events(
        root,
        _evt("evt-20260705-001", task_id, "created", None, "planned", "c", "2026-07-05T10:00:00+08:00"),
        _evt("evt-20260705-002", task_id, "status_changed", "planned", "running", "s", "2026-07-05T10:01:00+08:00"),
    )
    candidate = _evt("evt-20260705-003", task_id, "progress", "running", "running", "p", "2026-07-05T10:02:00+08:00")

    original_size = events_file.stat().st_size
    call_count = 0

    def _failing_validate(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        from agent_runtime.result import CheckResult, Finding

        # validate_records is only called during post-check, so fail the first invocation.
        if call_count >= 1:
            return CheckResult(
                status="validation_failed",
                findings=[Finding(rule_id="post-validate-failure", severity="error", action="error", message="simulated")],
                next_action="rollback",
            )
        from agent_runtime.task_validation import validate_records

        return validate_records(*args, **kwargs)

    with patch("agent_runtime.runtime_event_append.validate_records", side_effect=_failing_validate):
        result = append_event(
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
    assert events_file.stat().st_size == original_size
    assert events_file.read_text(encoding="utf-8").count("\n") == 2


def test_commit_stdin_pass(tmp_path, monkeypatch, capsys):
    root = _setup_fake_root(tmp_path)
    task_id = "task-20260705-001"
    _write_task(root, task_id, status="running")
    events_file = _write_events(
        root,
        _evt("evt-20260705-001", task_id, "created", None, "planned", "c", "2026-07-05T10:00:00+08:00"),
    )
    payload = json.dumps(
        _evt("evt-20260705-002", task_id, "status_changed", "planned", "running", "s", "2026-07-05T10:01:00+08:00"),
        ensure_ascii=False,
    )
    monkeypatch.setattr("sys.stdin", io.StringIO(payload))
    monkeypatch.setattr(
        "sys.argv",
        ["agent-runtime", "--root", str(root), "runtime", "event", "append", "--stdin", "--commit"],
    )
    assert main() == 0
    captured = capsys.readouterr()
    assert "PASS" in captured.out
    assert "committed=True" in captured.out
    assert events_file.read_text(encoding="utf-8").count("\n") == 2


def test_commit_json_output_sanitized(tmp_path, monkeypatch, capsys):
    root = _setup_fake_root(tmp_path)
    task_id = "task-20260705-001"
    _write_task(root, task_id, status="running")
    _write_events(
        root,
        _evt("evt-20260705-001", task_id, "created", None, "planned", "c", "2026-07-05T10:00:00+08:00"),
    )
    message = "progress message with sensitive details"
    candidate_file = _candidate_file(
        root,
        _evt("evt-20260705-002", task_id, "progress", "running", "running", message, "2026-07-05T10:01:00+08:00"),
    )

    monkeypatch.setattr(
        "sys.argv",
        [
            "agent-runtime",
            "--root",
            str(root),
            "runtime",
            "event",
            "append",
            "--file",
            str(candidate_file),
            "--commit",
            "--json",
        ],
    )
    assert main() == 0
    captured = capsys.readouterr()
    out = json.loads(captured.out)
    assert out["status"] == "pass"
    assert out["committed"] is True
    assert message not in captured.out
