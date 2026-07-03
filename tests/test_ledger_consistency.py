"""Tests for cross-record ledger consistency checks."""

from pathlib import Path

from agent_runtime.cli import main
from agent_runtime.ledger_consistency import check_ledger_consistency


ROOT = Path(__file__).resolve().parents[1]


def _write_jsonl(tmp_path: Path, filename: str, lines: list[str]) -> Path:
    file_path = tmp_path / filename
    file_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return file_path


def _valid_task(task_id: str, status: str = "finished") -> str:
    return (
        f'{{"id":"{task_id}","title":"Test","status":"{status}",'
        f'"created_at":"2026-07-03T10:00:00+08:00","updated_at":"2026-07-03T10:00:00+08:00",'
        f'"created_by":"user","source":"cli"}}'
    )


def _valid_event(event_id: str, task_id: str, event_type: str, from_status: str | None, to_status: str | None, timestamp: str) -> str:
    from_part = "null" if from_status is None else f'"{from_status}"'
    to_part = "null" if to_status is None else f'"{to_status}"'
    return (
        f'{{"event_id":"{event_id}","task_id":"{task_id}","timestamp":"{timestamp}",'
        f'"actor":"user","event_type":"{event_type}","from_status":{from_part},'
        f'"to_status":{to_part},"message":"test"}}'
    )


def test_check_ledger_current_repo_passes():
    result = check_ledger_consistency(ROOT, "tasks/tasks.jsonl", "tasks/events.jsonl")
    assert result.status == "pass"


def test_check_ledger_unknown_task_id(tmp_path):
    tasks_file = _write_jsonl(tmp_path, "tasks.jsonl", [_valid_task("task-20260703-001")])
    events_file = _write_jsonl(
        tmp_path,
        "events.jsonl",
        [
            _valid_event("evt-20260703-001", "task-20260703-001", "created", None, "planned", "2026-07-03T10:00:00+08:00"),
            _valid_event("evt-20260703-002", "task-20260703-999", "created", None, "planned", "2026-07-03T10:01:00+08:00"),
        ],
    )
    result = check_ledger_consistency(tmp_path, "tasks.jsonl", "events.jsonl")
    assert result.status == "validation_failed"
    assert any(f.rule_id == "unknown-task-id" for f in result.findings)
    assert "task-20260703-999" in result.findings[0].message


def test_check_ledger_snapshot_status_mismatch(tmp_path):
    tasks_file = _write_jsonl(tmp_path, "tasks.jsonl", [_valid_task("task-20260703-001", status="running")])
    events_file = _write_jsonl(
        tmp_path,
        "events.jsonl",
        [
            _valid_event("evt-20260703-001", "task-20260703-001", "created", None, "planned", "2026-07-03T10:00:00+08:00"),
            _valid_event("evt-20260703-002", "task-20260703-001", "status_changed", "planned", "finished", "2026-07-03T10:05:00+08:00"),
        ],
    )
    result = check_ledger_consistency(tmp_path, "tasks.jsonl", "events.jsonl")
    assert result.status == "validation_failed"
    assert any(f.rule_id == "snapshot-status-mismatch" for f in result.findings)


def test_check_ledger_finished_then_running_fails(tmp_path):
    tasks_file = _write_jsonl(tmp_path, "tasks.jsonl", [_valid_task("task-20260703-001", status="running")])
    events_file = _write_jsonl(
        tmp_path,
        "events.jsonl",
        [
            _valid_event("evt-20260703-001", "task-20260703-001", "created", None, "planned", "2026-07-03T10:00:00+08:00"),
            _valid_event("evt-20260703-002", "task-20260703-001", "status_changed", "planned", "running", "2026-07-03T10:05:00+08:00"),
            _valid_event("evt-20260703-003", "task-20260703-001", "finished", "running", "finished", "2026-07-03T10:10:00+08:00"),
            _valid_event("evt-20260703-004", "task-20260703-001", "status_changed", "finished", "running", "2026-07-03T10:15:00+08:00"),
        ],
    )
    result = check_ledger_consistency(tmp_path, "tasks.jsonl", "events.jsonl")
    assert result.status == "validation_failed"
    assert any(f.rule_id == "terminal-status-reverted" for f in result.findings)


def test_check_ledger_events_sorted_by_timestamp(tmp_path):
    tasks_file = _write_jsonl(tmp_path, "tasks.jsonl", [_valid_task("task-20260703-001", status="finished")])
    events_file = _write_jsonl(
        tmp_path,
        "events.jsonl",
        [
            _valid_event("evt-20260703-003", "task-20260703-001", "finished", "running", "finished", "2026-07-03T10:10:00+08:00"),
            _valid_event("evt-20260703-001", "task-20260703-001", "created", None, "planned", "2026-07-03T10:00:00+08:00"),
            _valid_event("evt-20260703-002", "task-20260703-001", "status_changed", "planned", "running", "2026-07-03T10:05:00+08:00"),
        ],
    )
    result = check_ledger_consistency(tmp_path, "tasks.jsonl", "events.jsonl")
    assert result.status == "pass"


def test_check_ledger_created_from_status_not_null(tmp_path):
    tasks_file = _write_jsonl(tmp_path, "tasks.jsonl", [_valid_task("task-20260703-001", status="planned")])
    events_file = _write_jsonl(
        tmp_path,
        "events.jsonl",
        [
            _valid_event("evt-20260703-001", "task-20260703-001", "created", "planned", "planned", "2026-07-03T10:00:00+08:00"),
        ],
    )
    result = check_ledger_consistency(tmp_path, "tasks.jsonl", "events.jsonl")
    assert result.status == "validation_failed"
    assert any(f.rule_id == "created-from-status-not-null" for f in result.findings)


def test_check_ledger_first_event_not_created(tmp_path):
    tasks_file = _write_jsonl(tmp_path, "tasks.jsonl", [_valid_task("task-20260703-001", status="running")])
    events_file = _write_jsonl(
        tmp_path,
        "events.jsonl",
        [
            _valid_event("evt-20260703-002", "task-20260703-001", "status_changed", "planned", "running", "2026-07-03T10:05:00+08:00"),
        ],
    )
    result = check_ledger_consistency(tmp_path, "tasks.jsonl", "events.jsonl")
    assert result.status == "validation_failed"
    assert any(f.rule_id == "first-event-not-created" for f in result.findings)


def test_check_ledger_discontinuous_status(tmp_path):
    tasks_file = _write_jsonl(tmp_path, "tasks.jsonl", [_valid_task("task-20260703-001", status="running")])
    events_file = _write_jsonl(
        tmp_path,
        "events.jsonl",
        [
            _valid_event("evt-20260703-001", "task-20260703-001", "created", None, "planned", "2026-07-03T10:00:00+08:00"),
            _valid_event("evt-20260703-002", "task-20260703-001", "status_changed", "blocked", "running", "2026-07-03T10:05:00+08:00"),
        ],
    )
    result = check_ledger_consistency(tmp_path, "tasks.jsonl", "events.jsonl")
    assert result.status == "validation_failed"
    assert any(f.rule_id == "discontinuous-status" for f in result.findings)


def test_check_ledger_does_not_echo_full_record(tmp_path):
    task_line = (
        '{"id":"task-20260703-001","title":"UNIQUE_TASK_TITLE","status":"running",'
        '"created_at":"2026-07-03T10:00:00+08:00","updated_at":"2026-07-03T10:00:00+08:00",'
        '"created_by":"user","source":"cli"}'
    )
    tasks_file = _write_jsonl(tmp_path, "tasks.jsonl", [task_line])
    events_file = _write_jsonl(
        tmp_path,
        "events.jsonl",
        [
            '{"event_id":"evt-20260703-001","task_id":"task-20260703-001","timestamp":"2026-07-03T10:00:00+08:00",'
            '"actor":"user","event_type":"created","from_status":null,"to_status":"planned",'
            '"message":"UNIQUE_EVENT_MESSAGE"}',
            '{"event_id":"evt-20260703-002","task_id":"task-20260703-001","timestamp":"2026-07-03T10:05:00+08:00",'
            '"actor":"user","event_type":"status_changed","from_status":"planned","to_status":"finished",'
            '"message":"UNIQUE_EVENT_MESSAGE"}',
        ],
    )
    result = check_ledger_consistency(tmp_path, "tasks.jsonl", "events.jsonl")
    rendered = result.render_json()
    assert "UNIQUE_TASK_TITLE" not in rendered
    assert "UNIQUE_EVENT_MESSAGE" not in rendered


def test_cli_task_check_ledger_valid(capsys):
    code = main([
        "--root", str(ROOT),
        "task", "check-ledger",
        "--tasks-file", "tasks/tasks.jsonl",
        "--events-file", "tasks/events.jsonl",
    ])
    captured = capsys.readouterr()
    assert code == 0
    assert "PASS" in captured.out


def test_cli_task_check_ledger_invalid(capsys):
    code = main([
        "--root", str(ROOT),
        "task", "check-ledger",
        "--tasks-file", "tests/fixtures/ledger/tasks-valid.jsonl",
        "--events-file", "tests/fixtures/ledger/events-unknown-task.jsonl",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 5
    assert '"status": "validation_failed"' in captured.out
    assert "task-20260703-999" in captured.out
