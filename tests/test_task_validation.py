"""Tests for task/event ledger preflight validation."""

from pathlib import Path

import pytest

from agent_runtime.cli import main
from agent_runtime.task_validation import validate_records


ROOT = Path(__file__).resolve().parents[1]


def _prepare_schema_root(tmp_path: Path) -> Path:
    schema_dir = tmp_path / "tasks"
    schema_dir.mkdir(parents=True, exist_ok=True)
    (schema_dir / "task.schema.json").write_text(
        (ROOT / "tasks" / "task.schema.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (schema_dir / "event.schema.json").write_text(
        (ROOT / "tasks" / "event.schema.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    return tmp_path


def _write_record(root: Path, filename: str, content: str) -> Path:
    record_file = root / filename
    record_file.parent.mkdir(parents=True, exist_ok=True)
    record_file.write_text(content, encoding="utf-8")
    return record_file


def test_validate_valid_task_jsonl(tmp_path):
    root = _prepare_schema_root(tmp_path)
    _write_record(
        root,
        "tasks/tasks.jsonl",
        '{"id":"task-20260703-001","title":"Test","status":"planned",'
        '"created_at":"2026-07-03T00:00:00+08:00","updated_at":"2026-07-03T00:00:00+08:00",'
        '"created_by":"user","source":"cli"}\n',
    )
    result = validate_records(root, "tasks/tasks.jsonl", "task")
    assert result.status == "pass"
    assert not result.findings


def test_validate_invalid_task_missing_required_field(tmp_path):
    root = _prepare_schema_root(tmp_path)
    _write_record(
        root,
        "tasks/tasks.jsonl",
        '{"id":"task-20260703-002","status":"planned",'
        '"created_at":"2026-07-03T00:00:00+08:00","updated_at":"2026-07-03T00:00:00+08:00",'
        '"created_by":"user","source":"cli"}\n',
    )
    result = validate_records(root, "tasks/tasks.jsonl", "task")
    assert result.status == "validation_failed"
    finding = result.findings[0]
    assert finding.line == 1
    assert "task" in finding.message
    assert "title" in finding.message
    assert "task-20260703-002" not in finding.message


def test_validate_invalid_task_bad_enum_value(tmp_path):
    root = _prepare_schema_root(tmp_path)
    _write_record(
        root,
        "tasks/tasks.jsonl",
        '{"id":"task-20260703-003","title":"Test","status":"unknown",'
        '"created_at":"2026-07-03T00:00:00+08:00","updated_at":"2026-07-03T00:00:00+08:00",'
        '"created_by":"user","source":"cli"}\n',
    )
    result = validate_records(root, "tasks/tasks.jsonl", "task")
    assert result.status == "validation_failed"
    finding = result.findings[0]
    assert finding.line == 1
    assert "status" in finding.message or "enum" in finding.message


def test_validate_valid_event_jsonl(tmp_path):
    root = _prepare_schema_root(tmp_path)
    _write_record(
        root,
        "tasks/events.jsonl",
        '{"event_id":"evt-20260703-001","task_id":"task-20260703-001",'
        '"timestamp":"2026-07-03T00:00:00+08:00","actor":"user","event_type":"created",'
        '"message":"created"}\n',
    )
    result = validate_records(root, "tasks/events.jsonl", "event")
    assert result.status == "pass"


@pytest.mark.parametrize("event_type", ["run_planned", "run_draft_exported", "run_blocked", "approval_resolved"])
def test_validate_run_lifecycle_event_types(tmp_path, event_type):
    root = _prepare_schema_root(tmp_path)
    _write_record(
        root,
        "tasks/events.jsonl",
        '{"event_id":"evt-20260703-003","task_id":"task-20260703-001",'
        '"timestamp":"2026-07-03T00:00:00+08:00","actor":"cli",'
        f'"event_type":"{event_type}","message":"lifecycle event"}}\n',
    )
    result = validate_records(root, "tasks/events.jsonl", "event")
    assert result.status == "pass"


def test_validate_invalid_event_missing_required_field(tmp_path):
    root = _prepare_schema_root(tmp_path)
    _write_record(
        root,
        "tasks/events.jsonl",
        '{"event_id":"evt-20260703-002","task_id":"task-20260703-001",'
        '"timestamp":"2026-07-03T00:00:00+08:00","event_type":"created",'
        '"message":"missing actor"}\n',
    )
    result = validate_records(root, "tasks/events.jsonl", "event")
    assert result.status == "validation_failed"
    finding = result.findings[0]
    assert finding.line == 1
    assert "actor" in finding.message


def test_validate_json_syntax_error_reports_line_number(tmp_path):
    root = _prepare_schema_root(tmp_path)
    _write_record(
        root,
        "tasks/tasks.jsonl",
        '{"id":"task-20260703-004","title":"OK","status":"planned",'
        '"created_at":"2026-07-03T00:00:00+08:00","updated_at":"2026-07-03T00:00:00+08:00",'
        '"created_by":"user","source":"cli"}\n'
        '{this is not valid json}\n',
    )
    result = validate_records(root, "tasks/tasks.jsonl", "task")
    assert result.status == "validation_failed"
    assert any(f.line == 2 for f in result.findings)
    assert any("invalid JSON" in f.message for f in result.findings)


def test_validate_rejects_path_outside_root(tmp_path):
    root = _prepare_schema_root(tmp_path / "root")
    outside_file = tmp_path / "outside.jsonl"
    outside_file.write_text('{"id":"task-20260703-005"}\n', encoding="utf-8")
    result = validate_records(root, str(outside_file), "task")
    assert result.status == "error"
    assert result.findings[0].rule_id == "path-outside-root"


def test_validate_rejects_non_jsonl_file(tmp_path):
    root = _prepare_schema_root(tmp_path)
    _write_record(root, "tasks/tasks.txt", "{}\n")
    result = validate_records(root, "tasks/tasks.txt", "task")
    assert result.status == "error"
    assert result.findings[0].rule_id == "unsafe-record-file"


def test_validate_unsupported_schema_type(tmp_path):
    root = _prepare_schema_root(tmp_path)
    result = validate_records(root, "tasks/tasks.jsonl", "unknown")
    assert result.status == "error"


def test_validate_file_not_found(tmp_path):
    root = _prepare_schema_root(tmp_path)
    result = validate_records(root, "tasks/does-not-exist.jsonl", "task")
    assert result.status == "error"


def test_cli_task_validate_valid(capsys):
    code = main([
        "--root", str(ROOT),
        "task", "validate",
        "--record-file", "tasks/examples.jsonl",
        "--schema", "task",
    ])
    captured = capsys.readouterr()
    assert code == 0
    assert "PASS" in captured.out


def test_cli_task_validate_invalid(capsys):
    code = main([
        "--root", str(ROOT),
        "task", "validate",
        "--record-file", "tests/fixtures/invalid-task.jsonl",
        "--schema", "task",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 5
    assert '"status": "validation_failed"' in captured.out
    assert "bad-id" not in captured.out


def test_cli_task_validate_json_syntax_error(capsys):
    code = main([
        "--root", str(ROOT),
        "task", "validate",
        "--record-file", "tests/fixtures/invalid-event-json.jsonl",
        "--schema", "event",
    ])
    captured = capsys.readouterr()
    assert code == 5
    assert "VALIDATION_FAILED" in captured.out
    assert "Line 1" in captured.out
