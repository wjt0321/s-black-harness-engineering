"""Schema and generic-entry guards for execution audit events."""

from __future__ import annotations

from copy import deepcopy
import json
import os
from pathlib import Path
import shutil

import pytest
from jsonschema import ValidationError, validate

from agent_runtime import execution_audit_writer as audit_writer
from agent_runtime.doctor import SCHEMA_FILES, run_doctor
from agent_runtime.execution_audit_writer import (
    inspect_execution_attempt,
    record_execution_attempt_started,
    record_execution_terminal,
    validate_execution_audit_ledger,
)
from agent_runtime.loader import load_schema
from agent_runtime.result import CheckResult, Finding

ROOT = Path(__file__).resolve().parents[1]

RESERVED_EVENT_TYPES = (
    "execution_attempt_started",
    "execution_succeeded",
    "execution_failed",
    "execution_cancelled",
)


def _metadata_for(event_type: str) -> dict[str, object]:
    metadata: dict[str, object] = {
        "writer_origin": "agent_runtime.execution_audit_writer",
        "writer_schema_version": "execution-audit/v1",
        "append_token": "append-20260717-001",
        "attempt_id": "attempt-20260717-001",
        "request_id": "req-20260717-001",
        "plan_hash": "sha256:" + "a" * 64,
        "adapter_id": "shell-local",
        "capability": "git_status",
        "operation": "git_status",
    }
    if event_type == "execution_attempt_started":
        metadata["phase"] = "pre_spawn_committed"
    else:
        metadata["started_event_id"] = "evt-20260717-001"
        if event_type == "execution_succeeded":
            metadata["phase"] = "post_run_validated"
            metadata["exit_code"] = 0
            metadata["guard_status"] = "pass"
            metadata["stdout_truncated"] = False
            metadata["stderr_truncated"] = False
        elif event_type == "execution_failed":
            metadata["phase"] = "spawn"
            metadata["failure_code"] = "spawn_failed"
        else:
            metadata["phase"] = "cancelled"
            metadata["failure_code"] = "operator_cancelled"
    return metadata


def _event(event_type: str) -> dict[str, object]:
    return {
        "event_id": "evt-20260717-002",
        "task_id": "task-20260717-001",
        "timestamp": "2026-07-17T10:00:00+08:00",
        "actor": "local-operator",
        "event_type": event_type,
        "message": "Execution audit lifecycle event.",
        "metadata": _metadata_for(event_type),
    }


@pytest.mark.parametrize("event_type", RESERVED_EVENT_TYPES)
def test_shared_event_schema_accepts_reserved_execution_types(event_type: str) -> None:
    schema = load_schema(ROOT, "tasks/event.schema.json")

    validate(instance=_event(event_type), schema=schema)


@pytest.mark.parametrize("event_type", RESERVED_EVENT_TYPES)
def test_dedicated_schema_accepts_each_execution_event_shape(event_type: str) -> None:
    schema = load_schema(ROOT, "tasks/execution-audit-event.schema.json")

    validate(instance=_event(event_type), schema=schema)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("actor", "cli"),
        ("writer_origin", "caller-supplied"),
        ("writer_schema_version", "execution-audit/v2"),
    ),
)
def test_dedicated_schema_rejects_wrong_fixed_provenance(
    field: str, value: str
) -> None:
    schema = load_schema(ROOT, "tasks/execution-audit-event.schema.json")
    candidate = _event("execution_attempt_started")
    if field == "actor":
        candidate[field] = value
    else:
        candidate["metadata"][field] = value

    with pytest.raises(ValidationError):
        validate(instance=candidate, schema=schema)


@pytest.mark.parametrize(
    "field",
    ("raw_stdout", "path", "environment"),
)
def test_dedicated_schema_rejects_extra_sensitive_metadata(field: str) -> None:
    schema = load_schema(ROOT, "tasks/execution-audit-event.schema.json")
    candidate = _event("execution_failed")
    candidate["metadata"][field] = "withheld-value"

    with pytest.raises(ValidationError):
        validate(instance=candidate, schema=schema)


def test_dedicated_schema_rejects_wrong_type_phase_pair() -> None:
    schema = load_schema(ROOT, "tasks/execution-audit-event.schema.json")
    candidate = _event("execution_succeeded")
    candidate["metadata"]["phase"] = "spawn"

    with pytest.raises(ValidationError):
        validate(instance=candidate, schema=schema)


def test_dedicated_schema_requires_terminal_started_event_reference() -> None:
    schema = load_schema(ROOT, "tasks/execution-audit-event.schema.json")
    candidate = deepcopy(_event("execution_cancelled"))
    del candidate["metadata"]["started_event_id"]

    with pytest.raises(ValidationError):
        validate(instance=candidate, schema=schema)


@pytest.mark.parametrize(
    "field",
    ("exit_code", "guard_status", "stdout_truncated", "stderr_truncated"),
)
def test_succeeded_schema_requires_closed_success_evidence(field: str) -> None:
    schema = load_schema(ROOT, "tasks/execution-audit-event.schema.json")
    candidate = deepcopy(_event("execution_succeeded"))
    del candidate["metadata"][field]

    with pytest.raises(ValidationError):
        validate(instance=candidate, schema=schema)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("exit_code", 1),
        ("guard_status", "failed"),
        ("stdout_truncated", True),
        ("stderr_truncated", True),
    ),
)
def test_succeeded_schema_rejects_contradictory_success_evidence(
    field: str, value: object
) -> None:
    schema = load_schema(ROOT, "tasks/execution-audit-event.schema.json")
    candidate = deepcopy(_event("execution_succeeded"))
    candidate["metadata"][field] = value

    with pytest.raises(ValidationError):
        validate(instance=candidate, schema=schema)


def test_succeeded_schema_rejects_failure_code() -> None:
    schema = load_schema(ROOT, "tasks/execution-audit-event.schema.json")
    candidate = deepcopy(_event("execution_succeeded"))
    candidate["metadata"]["failure_code"] = "contradictory_failure"

    with pytest.raises(ValidationError):
        validate(instance=candidate, schema=schema)


def test_succeeded_schema_rejects_nonzero_stderr_byte_count() -> None:
    schema = load_schema(ROOT, "tasks/execution-audit-event.schema.json")
    candidate = deepcopy(_event("execution_succeeded"))
    candidate["metadata"]["stderr_byte_count"] = 1

    with pytest.raises(ValidationError):
        validate(instance=candidate, schema=schema)


@pytest.mark.parametrize(
    "event_type",
    ("execution_failed", "execution_cancelled"),
)
def test_failed_and_cancelled_schema_require_failure_code(event_type: str) -> None:
    schema = load_schema(ROOT, "tasks/execution-audit-event.schema.json")
    candidate = deepcopy(_event(event_type))
    del candidate["metadata"]["failure_code"]

    with pytest.raises(ValidationError):
        validate(instance=candidate, schema=schema)


def test_doctor_registers_execution_audit_schema() -> None:
    assert "tasks/execution-audit-event.schema.json" in SCHEMA_FILES
    assert run_doctor(ROOT).status == "pass"


def _setup_writer_root(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    root.mkdir()
    for rel in (
        "tasks/task.schema.json",
        "tasks/event.schema.json",
        "tasks/execution-audit-event.schema.json",
        "tasks/execution-audit-event-v2.schema.json",
    ):
        destination = root / rel
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / rel, destination)
    policies = root / "policies"
    policies.mkdir()
    for source in (ROOT / "policies").glob("*.sample.policy.json"):
        shutil.copyfile(source, policies / source.name)
    task = {
        "id": "task-20260717-001",
        "title": "audit writer test",
        "status": "running",
        "created_at": "2026-07-17T01:00:00+00:00",
        "updated_at": "2026-07-17T01:00:00+00:00",
        "created_by": "cli",
        "source": "cli",
    }
    tasks_file = root / "tasks" / "tasks.jsonl"
    tasks_file.write_text(json.dumps(task) + "\n", encoding="utf-8")
    created = {
        "event_id": "evt-20260717-001",
        "task_id": task["id"],
        "timestamp": "2026-07-17T01:00:00+00:00",
        "actor": "cli",
        "event_type": "created",
        "from_status": None,
        "to_status": "running",
        "message": "created",
        "metadata": {},
    }
    events_file = root / "tasks" / "events.jsonl"
    events_file.write_text(json.dumps(created) + "\n", encoding="utf-8")
    return root


def _record_started(root: Path):
    return record_execution_attempt_started(
        root,
        task_id="task-20260717-001",
        request_id="req-20260717-001",
        plan_hash="sha256:" + "a" * 64,
        adapter_id="shell-local",
        capability="git_status",
        operation="git_status",
    )


def _read_events(root: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in (root / "tasks" / "events.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line
    ]


@pytest.mark.parametrize(
    "fault",
    (
        "invalid-started-event",
        "terminal-preflight-rejection",
        "append-construction-failure",
    ),
)
def test_paired_sessions_close_independently_for_all_writer_rejections(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fault: str
) -> None:
    root = _setup_writer_root(tmp_path)
    started = None
    if fault == "terminal-preflight-rejection":
        started = _record_started(root)
        assert started.status == "pass"

    captured: list[object] = []
    original_preflight = audit_writer._preflight_ledgers
    original_close = audit_writer.BoundedLedgerSession.close

    def tracking_preflight(*args, **kwargs):
        result = original_preflight(*args, **kwargs)
        if not isinstance(result, CheckResult):
            captured.extend(
                (result[-1].event_session, result[-1].task_session)
            )
        return result

    def failing_first_close(session):
        original_close(session)
        if session.path.name == "events.jsonl":
            raise RuntimeError("private first cleanup failure")

    monkeypatch.setattr(audit_writer, "_preflight_ledgers", tracking_preflight)
    monkeypatch.setattr(
        audit_writer.BoundedLedgerSession, "close", failing_first_close
    )

    if fault == "invalid-started-event":
        monkeypatch.setattr(
            audit_writer,
            "_validate_event_object",
            lambda *_args, **_kwargs: CheckResult(
                status="validation_failed",
                findings=[Finding("injected-invalid", "error", "error", "invalid")],
            ),
        )
        result = _record_started(root)
    elif fault == "terminal-preflight-rejection":
        result = audit_writer.record_execution_recovery_terminal(
            root,
            attempt_id=started.attempt_id,
            expected_started_event_id=started.event_id,
            expected_plan_hash="sha256:" + "b" * 64,
        )
    else:
        original_dumps = audit_writer.json.dumps

        def fail_event_serialization(value, *args, **kwargs):
            if isinstance(value, dict) and value.get("event_type") == "execution_attempt_started":
                raise RuntimeError("private append construction failure")
            return original_dumps(value, *args, **kwargs)

        monkeypatch.setattr(
            audit_writer.json,
            "dumps",
            fail_event_serialization,
        )
        result = _record_started(root)

    assert result.status == "error"
    assert result.findings[0].rule_id == "execution-audit-session-cleanup-failed"
    assert len(captured) == 2
    assert all(session._closed for session in captured)
    assert "private" not in json.dumps(result.to_dict())

    monkeypatch.setattr(audit_writer.BoundedLedgerSession, "close", original_close)
    for name in ("events.jsonl", "tasks.jsonl"):
        opened = audit_writer.open_bounded_ledger_session(
            root / "tasks" / name, exclusive=True
        )
        assert not isinstance(opened, CheckResult)
        opened.close()


@pytest.mark.parametrize(
    ("failure", "propagates"),
    ((RuntimeError("private event open failure"), False), (KeyboardInterrupt(), True)),
)
def test_event_session_acquisition_failure_closes_task_session(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: BaseException,
    propagates: bool,
) -> None:
    root = _setup_writer_root(tmp_path)
    captured_tasks: list[object] = []
    original_open = audit_writer.open_bounded_ledger_session

    def failing_event_open(path: Path, *args, **kwargs):
        if path.name == "events.jsonl":
            raise failure
        opened = original_open(path, *args, **kwargs)
        if path.name == "tasks.jsonl" and not isinstance(opened, CheckResult):
            captured_tasks.append(opened)
        return opened

    monkeypatch.setattr(
        audit_writer, "open_bounded_ledger_session", failing_event_open
    )

    if propagates:
        with pytest.raises(KeyboardInterrupt):
            _record_started(root)
    else:
        result = _record_started(root)
        assert result.status == "error"
        assert result.findings[0].rule_id == "execution-audit-session-open-failed"
        assert "private event open failure" not in json.dumps(result.to_dict())

    assert len(captured_tasks) == 1
    assert captured_tasks[0]._closed is True

    monkeypatch.setattr(
        audit_writer, "open_bounded_ledger_session", original_open
    )
    opened = original_open(root / "tasks" / "tasks.jsonl", exclusive=True)
    assert not isinstance(opened, CheckResult)
    opened.close()


def test_append_runtime_error_is_structured_rolled_back_and_reacquirable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _setup_writer_root(tmp_path)
    before = (root / "tasks" / "events.jsonl").read_bytes()
    captured: list[object] = []
    original_preflight = audit_writer._preflight_ledgers

    def tracking_preflight(*args, **kwargs):
        result = original_preflight(*args, **kwargs)
        if not isinstance(result, CheckResult):
            captured.extend(
                (result[-1].event_session, result[-1].task_session)
            )
        return result

    monkeypatch.setattr(audit_writer, "_preflight_ledgers", tracking_preflight)
    monkeypatch.setattr(
        audit_writer,
        "_append_event_line",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            RuntimeError("private append failure")
        ),
    )

    result = _record_started(root)

    assert result.status == "error"
    assert result.findings[0].rule_id == "execution-audit-write-failed"
    assert result.rolled_back is True
    assert (root / "tasks" / "events.jsonl").read_bytes() == before
    assert "private append failure" not in json.dumps(result.to_dict())
    assert len(captured) == 2
    assert all(session._closed for session in captured)

    for name in ("events.jsonl", "tasks.jsonl"):
        opened = audit_writer.open_bounded_ledger_session(
            root / "tasks" / name, exclusive=True
        )
        assert not isinstance(opened, CheckResult)
        opened.close()


def test_started_and_recovery_use_bounded_task_snapshot_without_find_task(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _setup_writer_root(tmp_path)
    monkeypatch.setattr(
        audit_writer,
        "find_task",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("unbounded task lookup")
        ),
    )

    started = _record_started(root)
    assert started.status == "pass"
    terminal = audit_writer.record_execution_recovery_terminal(
        root,
        attempt_id=started.attempt_id,
        expected_started_event_id=started.event_id,
        expected_plan_hash="sha256:" + "a" * 64,
    )

    assert terminal.status == "pass"
    assert terminal.committed is True


def test_started_rejects_unknown_task_from_bounded_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _setup_writer_root(tmp_path)
    monkeypatch.setattr(
        audit_writer,
        "find_task",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("unbounded task lookup")
        ),
    )

    result = record_execution_attempt_started(
        root,
        task_id="task-20260717-999",
        request_id="req-20260717-999",
        plan_hash="sha256:" + "a" * 64,
        adapter_id="shell-local",
        capability="git_status",
        operation="git_status",
    )

    assert result.status == "error"
    assert result.findings[0].rule_id == "unknown-task-id"


def test_started_writer_appends_fixed_safe_event(tmp_path: Path) -> None:
    root = _setup_writer_root(tmp_path)

    result = _record_started(root)

    assert result.status == "pass"
    assert result.committed is True
    assert result.child_created is False
    assert result.audit_incomplete is False
    assert result.event_id.startswith("evt-")
    assert result.attempt_id.startswith("attempt-")
    event = _read_events(root)[-1]
    assert event["event_id"] == result.event_id
    assert event["actor"] == "local-operator"
    assert event["event_type"] == "execution_attempt_started"
    assert event["message"] == "Execution attempt audit started."
    assert event["metadata"] == {
        "writer_origin": "agent_runtime.execution_audit_writer",
        "writer_schema_version": "execution-audit/v1",
        "append_token": event["metadata"]["append_token"],
        "attempt_id": result.attempt_id,
        "request_id": "req-20260717-001",
        "plan_hash": "sha256:" + "a" * 64,
        "adapter_id": "shell-local",
        "capability": "git_status",
        "operation": "git_status",
        "phase": "pre_spawn_committed",
    }
    assert event["metadata"]["append_token"].startswith("append-")
    rendered = result.render_json()
    assert "audit writer test" not in rendered
    assert "raw_stdout" not in rendered
    assert event["metadata"]["append_token"] not in rendered


@pytest.mark.parametrize(
    ("overrides", "rule_id"),
    (
        ({"task_id": "task-20260717-999"}, "unknown-task-id"),
        ({"plan_hash": "sha256:not-a-digest"}, "invalid-plan-hash"),
        ({"request_id": "../request"}, "invalid-execution-audit-token"),
    ),
)
def test_started_writer_rejects_invalid_identity_without_write(
    tmp_path: Path, overrides: dict[str, str], rule_id: str
) -> None:
    root = _setup_writer_root(tmp_path)
    events_path = root / "tasks" / "events.jsonl"
    before = events_path.read_bytes()
    args = {
        "task_id": "task-20260717-001",
        "request_id": "req-20260717-001",
        "plan_hash": "sha256:" + "a" * 64,
        "adapter_id": "shell-local",
        "capability": "git_status",
        "operation": "git_status",
    }
    args.update(overrides)

    result = record_execution_attempt_started(root, **args)

    assert result.status in {"error", "validation_failed"}
    assert [finding.rule_id for finding in result.findings] == [rule_id]
    assert events_path.read_bytes() == before


@pytest.mark.parametrize(
    ("events_file", "rule_id"),
    (
        ("../events.jsonl", "events-file-outside-root"),
        ("tasks/events.txt", "unsafe-events-file"),
        ("tasks/missing.jsonl", "events-file-not-found"),
    ),
)
def test_started_writer_rejects_missing_or_unsafe_ledger(
    tmp_path: Path, events_file: str, rule_id: str
) -> None:
    root = _setup_writer_root(tmp_path)

    result = record_execution_attempt_started(
        root,
        task_id="task-20260717-001",
        request_id="req-20260717-001",
        plan_hash="sha256:" + "a" * 64,
        adapter_id="shell-local",
        capability="git_status",
        operation="git_status",
        events_file=events_file,
    )

    assert result.status == "error"
    assert [finding.rule_id for finding in result.findings] == [rule_id]


def test_started_writer_requires_existing_trailing_newline(tmp_path: Path) -> None:
    root = _setup_writer_root(tmp_path)
    path = root / "tasks" / "events.jsonl"
    path.write_bytes(path.read_bytes().rstrip(b"\n"))
    before = path.read_bytes()

    result = _record_started(root)

    assert result.status == "blocked"
    assert [finding.rule_id for finding in result.findings] == [
        "events-file-missing-trailing-newline"
    ]
    assert path.read_bytes() == before


def test_started_writer_newline_preflight_read_failure_is_structured(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _setup_writer_root(tmp_path)
    monkeypatch.setattr(
        "agent_runtime.execution_audit_writer._has_trailing_newline",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("withheld")),
    )

    result = _record_started(root)

    assert result.status == "error"
    assert [finding.rule_id for finding in result.findings] == [
        "events-file-read-failed"
    ]
    assert "withheld" not in result.render_json()


def test_started_writer_post_check_failure_rolls_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _setup_writer_root(tmp_path)
    path = root / "tasks" / "events.jsonl"
    before = path.read_bytes()

    monkeypatch.setattr(
        "agent_runtime.execution_audit_writer._post_check",
        lambda *args, **kwargs: CheckResult(
            status="validation_failed",
            findings=[
                Finding(
                    rule_id="simulated-post-check",
                    severity="error",
                    action="error",
                    message="simulated",
                )
            ],
        ),
    )

    result = _record_started(root)

    assert result.status == "validation_failed"
    assert result.committed is False
    assert result.rolled_back is True
    assert path.read_bytes() == before


def test_writer_preflight_uses_bounded_event_snapshot_for_validation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _setup_writer_root(tmp_path)
    original_validate_records = audit_writer.validate_records
    monkeypatch.setattr(
        "agent_runtime.execution_audit_writer.validate_records",
        lambda root, record_file, schema_type: pytest.fail(
            "event validation must use bounded snapshot records"
        )
        if schema_type == "event"
        else original_validate_records(root, record_file, schema_type),
    )
    result = _record_started(root)

    assert result.status == "pass"


def test_started_writer_write_failure_rolls_back_partial_boundary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _setup_writer_root(tmp_path)
    path = root / "tasks" / "events.jsonl"
    before = path.read_bytes()

    def _partial_write_then_fail(handle, line: bytes) -> None:
        handle.seek(0, os.SEEK_END)
        handle.write(line[:17])
        handle.flush()
        raise audit_writer._AppendWriteError(17)

    monkeypatch.setattr(
        "agent_runtime.execution_audit_writer._append_event_line",
        _partial_write_then_fail,
    )

    result = _record_started(root)

    assert result.status == "error"
    assert result.committed is False
    assert result.rolled_back is True
    assert [finding.rule_id for finding in result.findings] == [
        "execution-audit-write-failed"
    ]
    assert "withheld" not in result.render_json()
    assert path.read_bytes() == before


def test_exclusive_session_blocks_concurrent_append_during_post_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _setup_writer_root(tmp_path)
    path = root / "tasks" / "events.jsonl"
    concurrent = {
        "event_id": "evt-20260717-999",
        "task_id": "task-20260717-001",
        "timestamp": "2026-07-17T10:00:00+00:00",
        "actor": "cli",
        "event_type": "progress",
        "from_status": "running",
        "to_status": "running",
        "message": "concurrent",
        "metadata": {},
    }

    blocked: list[bool] = []
    original_post_check = audit_writer._post_check

    def _concurrent_then_check(*args, **kwargs):
        contended = audit_writer.open_bounded_ledger_session(
            path, exclusive=True, blocking=False
        )
        if not isinstance(contended, audit_writer.BoundedLedgerSession):
            blocked.append(True)
        else:
            contended.close()
        return original_post_check(*args, **kwargs)

    monkeypatch.setattr(
        "agent_runtime.execution_audit_writer._post_check",
        _concurrent_then_check,
    )

    result = _record_started(root)

    assert result.status == "pass"
    assert blocked == [True]
    assert not any(event["event_id"] == concurrent["event_id"] for event in _read_events(root))


def test_append_token_prevents_equal_payload_from_claiming_rollback_ownership(
    tmp_path: Path,
) -> None:
    root = _setup_writer_root(tmp_path)
    path = root / "tasks" / "events.jsonl"
    expected = _event("execution_attempt_started")
    expected["metadata"]["append_token"] = "append-current"
    concurrent = deepcopy(expected)
    concurrent["metadata"]["append_token"] = "append-concurrent"
    expected_line = (
        json.dumps(expected, ensure_ascii=False, separators=(",", ":")) + "\n"
    ).encode("utf-8")
    concurrent_line = (
        json.dumps(concurrent, ensure_ascii=False, separators=(",", ":")) + "\n"
    ).encode("utf-8")

    opened = audit_writer.open_bounded_ledger_session(path, exclusive=True)
    assert isinstance(opened, audit_writer.BoundedLedgerSession)
    with opened as session:
        snapshot = session.snapshot
        assert isinstance(snapshot, audit_writer.BoundedLedgerSnapshot)
        original_size, identity = audit_writer._ledger_boundary(path, session.handle)
        audit_writer._append_event_line(session.handle, concurrent_line)
        rolled_back, error = audit_writer._rollback_events_file(
                session.handle,
                path,
                original_size,
                identity,
                expected_line,
                0,
                snapshot,
            )

    assert rolled_back is False
    assert error == "concurrent-ledger-change"
    assert path.read_bytes().endswith(concurrent_line)


def test_rollback_does_not_claim_byte_identical_append_without_owned_count(
    tmp_path: Path,
) -> None:
    root = _setup_writer_root(tmp_path)
    path = root / "tasks" / "events.jsonl"
    event = _event("execution_attempt_started")
    line = (
        json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n"
    ).encode("utf-8")

    opened = audit_writer.open_bounded_ledger_session(path, exclusive=True)
    assert isinstance(opened, audit_writer.BoundedLedgerSession)
    with opened as session:
        snapshot = session.snapshot
        assert isinstance(snapshot, audit_writer.BoundedLedgerSnapshot)
        original_size, identity = audit_writer._ledger_boundary(path, session.handle)
        audit_writer._append_event_line(session.handle, line)
        rolled_back, error = audit_writer._rollback_events_file(
                session.handle,
                path,
                original_size,
                identity,
                line,
                0,
                snapshot,
            )

    assert rolled_back is False
    assert error == "concurrent-ledger-change"
    assert path.read_bytes().endswith(line)


def test_success_path_rejects_file_identity_replacement_before_append(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _setup_writer_root(tmp_path)
    path = root / "tasks" / "events.jsonl"
    before = path.read_bytes()

    def _replace_then_write(handle, line: bytes) -> None:
        replacement = path.with_name("replacement.jsonl")
        replacement.write_bytes(before)
        os.replace(replacement, path)
        handle.seek(0, os.SEEK_END)
        handle.write(line)
        handle.flush()
        os.fsync(handle.fileno())

    monkeypatch.setattr(
        "agent_runtime.execution_audit_writer._append_event_line",
        _replace_then_write,
    )

    result = _record_started(root)

    assert result.status == "error"
    assert result.committed is False
    assert not any(
        event["event_type"] == "execution_attempt_started"
        for event in _read_events(root)
    )


def test_exclusive_session_blocks_identity_replacement_during_event_validation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _setup_writer_root(tmp_path)
    path = root / "tasks" / "events.jsonl"
    before = path.read_bytes()
    original_validate = audit_writer._validate_event_object

    blocked: list[bool] = []

    def _validate_then_replace(project_root: Path, event: dict[str, object]):
        result = original_validate(project_root, event)
        contended = audit_writer.open_bounded_ledger_session(
            path, exclusive=True, blocking=False
        )
        if not isinstance(contended, audit_writer.BoundedLedgerSession):
            blocked.append(True)
        else:
            contended.close()
        return result

    monkeypatch.setattr(
        "agent_runtime.execution_audit_writer._validate_event_object",
        _validate_then_replace,
    )

    result = _record_started(root)

    assert result.status == "pass"
    assert blocked == [True]


def test_exclusive_session_blocks_same_size_rewrite_before_append(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _setup_writer_root(tmp_path)
    path = root / "tasks" / "events.jsonl"
    before = path.read_bytes()
    original_validate = audit_writer._validate_event_object

    blocked: list[bool] = []

    def _validate_then_rewrite(project_root: Path, event: dict[str, object]):
        result = original_validate(project_root, event)
        contended = audit_writer.open_bounded_ledger_session(
            path, exclusive=True, blocking=False
        )
        if not isinstance(contended, audit_writer.BoundedLedgerSession):
            blocked.append(True)
        else:
            contended.close()
        return result

    monkeypatch.setattr(
        "agent_runtime.execution_audit_writer._validate_event_object",
        _validate_then_rewrite,
    )

    result = _record_started(root)

    assert result.status == "pass"
    assert blocked == [True]


def test_writer_holds_exclusive_session_before_event_construction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _setup_writer_root(tmp_path)
    path = root / "tasks" / "events.jsonl"
    original_validate = audit_writer._validate_event_object
    contention_status: list[str] = []

    def _validate_under_lock(project_root: Path, event: dict[str, object]):
        contended = audit_writer.open_bounded_ledger_session(
            path, exclusive=True, blocking=False
        )
        contention_status.append(
            "acquired"
            if isinstance(contended, audit_writer.BoundedLedgerSession)
            else contended.status
        )
        if isinstance(contended, audit_writer.BoundedLedgerSession):
            contended.close()
        return original_validate(project_root, event)

    monkeypatch.setattr(
        "agent_runtime.execution_audit_writer._validate_event_object",
        _validate_under_lock,
    )

    result = _record_started(root)

    assert result.status == "pass"
    assert contention_status == ["blocked"]


def test_writer_closes_exclusive_session_when_event_construction_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _setup_writer_root(tmp_path)
    path = root / "tasks" / "events.jsonl"
    original_close = audit_writer.BoundedLedgerSession.close
    closed: list[bool] = []

    def _record_close(session):
        closed.append(True)
        original_close(session)

    monkeypatch.setattr(audit_writer.BoundedLedgerSession, "close", _record_close)
    monkeypatch.setattr(
        "agent_runtime.execution_audit_writer._validate_event_object",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("withheld")),
    )

    with pytest.raises(RuntimeError):
        _record_started(root)

    assert closed == [True, True]
    acquired = audit_writer.open_bounded_ledger_session(
        path, exclusive=True, blocking=False
    )
    assert isinstance(acquired, audit_writer.BoundedLedgerSession)
    acquired.close()


def test_started_writer_rollback_failure_is_explicit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _setup_writer_root(tmp_path)
    monkeypatch.setattr(
        "agent_runtime.execution_audit_writer._post_check",
        lambda *args, **kwargs: CheckResult(
            status="validation_failed",
            findings=[
                Finding(
                    rule_id="simulated-post-check",
                    severity="error",
                    action="error",
                    message="simulated",
                )
            ],
        ),
    )
    monkeypatch.setattr(
        "agent_runtime.execution_audit_writer._rollback_events_file",
        lambda *args, **kwargs: (False, "withheld"),
    )

    result = _record_started(root)

    assert result.status == "error"
    assert result.rolled_back is False
    assert result.rollback_error == "rollback-failed"
    assert any(
        finding.rule_id == "execution-audit-rollback-failed"
        for finding in result.findings
    )
    assert "withheld" not in result.render_json()


def test_started_writer_stat_failure_is_structured(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _setup_writer_root(tmp_path)
    monkeypatch.setattr(
        "agent_runtime.execution_audit_writer._ledger_boundary",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("withheld")),
    )

    result = _record_started(root)

    assert result.status == "error"
    assert result.committed is False
    assert result.rolled_back is False
    assert [finding.rule_id for finding in result.findings] == [
        "execution-audit-ledger-stat-failed"
    ]
    assert "withheld" not in result.render_json()


def test_started_scan_failure_does_not_echo_untrusted_request_id(
    tmp_path: Path,
) -> None:
    root = _setup_writer_root(tmp_path)
    sensitive = "sk-" + "a" * 32

    result = record_execution_attempt_started(
        root,
        task_id="task-20260717-001",
        request_id=sensitive,
        plan_hash="sha256:" + "a" * 64,
        adapter_id="shell-local",
        capability="git_status",
        operation="git_status",
    )

    assert result.status == "blocked"
    assert sensitive not in result.render_json()
    assert result.request_id is None
    assert result.event_id is None
    assert result.attempt_id is None


def test_invalid_task_ledger_is_rejected_without_value_leak(tmp_path: Path) -> None:
    root = _setup_writer_root(tmp_path)
    sensitive = "sk-" + "b" * 32
    task = json.loads(
        (root / "tasks" / "tasks.jsonl").read_text(encoding="utf-8").strip()
    )
    task["status"] = sensitive
    (root / "tasks" / "tasks.jsonl").write_text(
        json.dumps(task) + "\n", encoding="utf-8"
    )

    result = _record_started(root)

    assert result.status == "validation_failed"
    assert sensitive not in result.render_json()
    assert any(
        finding.rule_id == "schema-validation-failed"
        for finding in result.findings
    )


@pytest.mark.parametrize(
    ("event_type", "kwargs", "expected_phase", "expected_state"),
    (
        (
            "execution_succeeded",
            {
                "exit_code": 0,
                "guard_status": "pass",
                "stdout_truncated": False,
                "stderr_truncated": False,
                "stderr_byte_count": 0,
            },
            "post_run_validated",
            "closed_succeeded",
        ),
        (
            "execution_failed",
            {"phase": "spawn", "failure_code": "spawn_failed"},
            "spawn",
            "closed_failed",
        ),
        (
            "execution_cancelled",
            {"failure_code": "operator_cancelled"},
            "cancelled",
            "closed_cancelled",
        ),
    ),
)
def test_terminal_writer_closes_attempt_and_recovery_state(
    tmp_path: Path,
    event_type: str,
    kwargs: dict[str, object],
    expected_phase: str,
    expected_state: str,
) -> None:
    root = _setup_writer_root(tmp_path)
    started = _record_started(root)

    terminal = record_execution_terminal(
        root,
        attempt_id=started.attempt_id,
        event_type=event_type,
        **kwargs,
    )

    assert terminal.status == "pass"
    assert terminal.committed is True
    assert terminal.audit_incomplete is False
    event = _read_events(root)[-1]
    assert event["event_type"] == event_type
    assert event["metadata"]["phase"] == expected_phase
    assert event["metadata"]["started_event_id"] == started.event_id
    inspected = inspect_execution_attempt(root, started.attempt_id)
    assert inspected.status == "pass"
    assert inspected.state == expected_state
    assert inspected.terminal_event_id == terminal.event_id


def test_open_attempt_is_valid_and_awaiting_terminal(tmp_path: Path) -> None:
    root = _setup_writer_root(tmp_path)
    started = _record_started(root)

    validated = validate_execution_audit_ledger(root)
    inspected = inspect_execution_attempt(root, started.attempt_id)

    assert validated.status == "pass"
    assert inspected.status == "pass"
    assert inspected.state == "awaiting_terminal"
    assert inspected.recovery_action == "record_terminal_audit"


def test_missing_attempt_needs_input(tmp_path: Path) -> None:
    root = _setup_writer_root(tmp_path)

    inspected = inspect_execution_attempt(root, "attempt-20260717-999")
    terminal = record_execution_terminal(
        root,
        attempt_id="attempt-20260717-999",
        event_type="execution_failed",
        phase="audit",
        failure_code="missing_started",
    )

    assert inspected.status == "needs_input"
    assert inspected.state == "missing"
    assert terminal.status == "needs_input"
    assert [finding.rule_id for finding in terminal.findings] == [
        "execution-attempt-not-found"
    ]


def test_duplicate_terminal_is_blocked_without_write(tmp_path: Path) -> None:
    root = _setup_writer_root(tmp_path)
    started = _record_started(root)
    first = record_execution_terminal(
        root,
        attempt_id=started.attempt_id,
        event_type="execution_failed",
        phase="spawn",
        failure_code="spawn_failed",
    )
    assert first.status == "pass"
    path = root / "tasks" / "events.jsonl"
    before = path.read_bytes()

    second = record_execution_terminal(
        root,
        attempt_id=started.attempt_id,
        event_type="execution_cancelled",
        failure_code="operator_cancelled",
    )

    assert second.status == "blocked"
    assert [finding.rule_id for finding in second.findings] == [
        "execution-attempt-already-closed"
    ]
    assert path.read_bytes() == before


def test_terminal_post_check_failure_preserves_started(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _setup_writer_root(tmp_path)
    started = _record_started(root)
    path = root / "tasks" / "events.jsonl"
    before = path.read_bytes()

    monkeypatch.setattr(
        "agent_runtime.execution_audit_writer._post_check",
        lambda *args, **kwargs: CheckResult(
            status="validation_failed",
            findings=[
                Finding(
                    rule_id="simulated-terminal-post-check",
                    severity="error",
                    action="error",
                    message="simulated",
                )
            ],
        ),
    )

    terminal = record_execution_terminal(
        root,
        attempt_id=started.attempt_id,
        event_type="execution_failed",
        phase="audit",
        failure_code="audit_failed",
    )

    assert terminal.status == "validation_failed"
    assert terminal.committed is False
    assert terminal.rolled_back is True
    assert terminal.audit_incomplete is True
    assert path.read_bytes() == before
    inspected = inspect_execution_attempt(root, started.attempt_id)
    assert inspected.state == "awaiting_terminal"


def test_post_check_exception_is_structured_and_rolls_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _setup_writer_root(tmp_path)
    path = root / "tasks" / "events.jsonl"
    before = path.read_bytes()
    monkeypatch.setattr(
        "agent_runtime.execution_audit_writer._post_check",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("withheld")),
    )

    result = _record_started(root)

    assert result.status == "error"
    assert result.rolled_back is True
    assert result.committed is False
    assert path.read_bytes() == before
    assert [finding.rule_id for finding in result.findings] == [
        "execution-audit-post-check-failed"
    ]
    assert "withheld" not in result.render_json()


def test_exclusive_session_blocks_append_after_passing_post_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _setup_writer_root(tmp_path)
    path = root / "tasks" / "events.jsonl"
    original_post_check = audit_writer._post_check

    blocked: list[bool] = []

    def _pass_then_drift(*args, **kwargs):
        result = original_post_check(*args, **kwargs)
        contended = audit_writer.open_bounded_ledger_session(
            path, exclusive=True, blocking=False
        )
        if not isinstance(contended, audit_writer.BoundedLedgerSession):
            blocked.append(True)
        else:
            contended.close()
        return result

    monkeypatch.setattr(
        "agent_runtime.execution_audit_writer._post_check",
        _pass_then_drift,
    )

    result = _record_started(root)

    assert result.status == "pass"
    assert blocked == [True]


def test_exclusive_session_blocks_same_size_prefix_rewrite_during_acceptance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _setup_writer_root(tmp_path)
    path = root / "tasks" / "events.jsonl"
    original_verify = audit_writer._verify_owned_append
    calls = 0
    blocked: list[bool] = []

    def _rewrite_prefix_then_verify(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            contended = audit_writer.open_bounded_ledger_session(
                path, exclusive=True, blocking=False
            )
            if not isinstance(contended, audit_writer.BoundedLedgerSession):
                blocked.append(True)
            else:
                contended.close()
        return original_verify(*args, **kwargs)

    monkeypatch.setattr(
        "agent_runtime.execution_audit_writer._verify_owned_append",
        _rewrite_prefix_then_verify,
    )

    result = _record_started(root)

    assert result.status == "pass"
    assert blocked == [True]


def test_terminal_partial_write_failure_preserves_started(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _setup_writer_root(tmp_path)
    started = _record_started(root)
    path = root / "tasks" / "events.jsonl"
    before = path.read_bytes()

    def _partial_write_then_fail(handle, line: bytes) -> None:
        handle.seek(0, os.SEEK_END)
        handle.write(line[:13])
        raise audit_writer._AppendWriteError(13)

    monkeypatch.setattr(
        "agent_runtime.execution_audit_writer._append_event_line",
        _partial_write_then_fail,
    )

    result = record_execution_terminal(
        root,
        attempt_id=started.attempt_id,
        event_type="execution_failed",
        phase="audit",
        failure_code="audit_failed",
    )

    assert result.status == "error"
    assert result.rolled_back is True
    assert result.audit_incomplete is True
    assert path.read_bytes() == before


def test_terminal_rollback_failure_is_explicit_and_preserves_open_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _setup_writer_root(tmp_path)
    started = _record_started(root)
    monkeypatch.setattr(
        "agent_runtime.execution_audit_writer._post_check",
        lambda *args, **kwargs: CheckResult(
            status="validation_failed",
            findings=[
                Finding(
                    rule_id="simulated-post-check",
                    severity="error",
                    action="error",
                    message="simulated",
                )
            ],
        ),
    )
    monkeypatch.setattr(
        "agent_runtime.execution_audit_writer._rollback_events_file",
        lambda *args, **kwargs: (False, "withheld"),
    )

    result = record_execution_terminal(
        root,
        attempt_id=started.attempt_id,
        event_type="execution_failed",
        phase="audit",
        failure_code="audit_failed",
    )

    assert result.status == "error"
    assert result.rolled_back is False
    assert result.audit_incomplete is True
    assert result.rollback_error == "rollback-failed"
    assert any(
        finding.rule_id == "execution-audit-rollback-failed"
        for finding in result.findings
    )
    assert "withheld" not in result.render_json()


def test_audit_validator_rejects_terminal_only_chain(tmp_path: Path) -> None:
    root = _setup_writer_root(tmp_path)
    terminal = _event("execution_failed")
    terminal["metadata"]["attempt_id"] = "attempt-20260717-777"
    with (root / "tasks" / "events.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(terminal) + "\n")

    result = validate_execution_audit_ledger(root)
    inspected = inspect_execution_attempt(root, "attempt-20260717-777")

    assert result.status == "validation_failed"
    assert any(
        finding.rule_id == "execution-audit-missing-started"
        for finding in result.findings
    )
    assert inspected.status == "validation_failed"
    assert inspected.state == "invalid"


def test_persisted_audit_secret_is_blocked_and_not_projected(tmp_path: Path) -> None:
    root = _setup_writer_root(tmp_path)
    sensitive = "sk-" + "c" * 32
    persisted = _event("execution_attempt_started")
    persisted["metadata"]["request_id"] = sensitive
    with (root / "tasks" / "events.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(persisted) + "\n")

    validated = validate_execution_audit_ledger(root)
    inspected = inspect_execution_attempt(
        root, persisted["metadata"]["attempt_id"]
    )

    assert validated.status == "validation_failed"
    assert sensitive not in validated.render_json()
    assert inspected.state == "invalid"
    assert sensitive not in inspected.render_json()
    assert inspected.request_id is None


def test_inspection_validates_entire_audit_ledger_before_missing_projection(
    tmp_path: Path,
) -> None:
    root = _setup_writer_root(tmp_path)
    sensitive = "sk-" + "d" * 32
    persisted = _event("execution_attempt_started")
    persisted["metadata"]["request_id"] = sensitive
    with (root / "tasks" / "events.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(persisted) + "\n")

    inspected = inspect_execution_attempt(root, "attempt-20260717-999")

    assert inspected.status == "validation_failed"
    assert inspected.state == "invalid"
    assert sensitive not in inspected.render_json()


def test_inspection_does_not_trust_a_second_path_based_validation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _setup_writer_root(tmp_path)
    sensitive = "sk-" + "e" * 32
    persisted = _event("execution_attempt_started")
    persisted["metadata"]["request_id"] = sensitive
    with (root / "tasks" / "events.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(persisted) + "\n")
    monkeypatch.setattr(
        "agent_runtime.execution_audit_writer.validate_execution_audit_ledger",
        lambda *args, **kwargs: CheckResult(status="pass"),
    )

    inspected = inspect_execution_attempt(
        root, persisted["metadata"]["attempt_id"]
    )

    assert inspected.status == "validation_failed"
    assert inspected.state == "invalid"
    assert sensitive not in inspected.render_json()


def test_audit_validator_enforces_timestamp_format(tmp_path: Path) -> None:
    root = _setup_writer_root(tmp_path)
    persisted = _event("execution_attempt_started")
    persisted["timestamp"] = "not-a-date-time"
    with (root / "tasks" / "events.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(persisted) + "\n")

    result = validate_execution_audit_ledger(root)

    assert result.status == "validation_failed"
    assert any(
        finding.rule_id == "execution-audit-schema-validation-failed"
        for finding in result.findings
    )


@pytest.mark.parametrize(
    ("duplicate_kind", "rule_id"),
    (
        ("started", "execution-audit-duplicate-started"),
        ("terminal", "execution-audit-duplicate-terminal"),
    ),
)
def test_audit_validator_rejects_duplicate_lifecycle_events(
    tmp_path: Path, duplicate_kind: str, rule_id: str
) -> None:
    root = _setup_writer_root(tmp_path)
    started = _record_started(root)
    if duplicate_kind == "terminal":
        terminal = record_execution_terminal(
            root,
            attempt_id=started.attempt_id,
            event_type="execution_failed",
            phase="spawn",
            failure_code="spawn_failed",
        )
        assert terminal.status == "pass"
    events = _read_events(root)
    source = (
        next(
            event
            for event in events
            if event["event_type"] == "execution_attempt_started"
        )
        if duplicate_kind == "started"
        else events[-1]
    )
    duplicate = deepcopy(source)
    duplicate["event_id"] = "evt-20260717-900"
    duplicate["timestamp"] = "2026-07-17T09:00:00+00:00"
    with (root / "tasks" / "events.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(duplicate) + "\n")

    result = validate_execution_audit_ledger(root)

    assert result.status == "validation_failed"
    assert any(finding.rule_id == rule_id for finding in result.findings)


def test_audit_validator_rejects_terminal_identity_mismatch(tmp_path: Path) -> None:
    root = _setup_writer_root(tmp_path)
    started = _record_started(root)
    terminal = record_execution_terminal(
        root,
        attempt_id=started.attempt_id,
        event_type="execution_failed",
        phase="spawn",
        failure_code="spawn_failed",
    )
    assert terminal.status == "pass"
    events = _read_events(root)
    events[-1]["metadata"]["request_id"] = "req-20260717-999"
    (root / "tasks" / "events.jsonl").write_text(
        "\n".join(json.dumps(event) for event in events) + "\n",
        encoding="utf-8",
    )

    result = validate_execution_audit_ledger(root)
    inspected = inspect_execution_attempt(root, started.attempt_id)

    assert result.status == "validation_failed"
    assert any(
        finding.rule_id == "execution-audit-identity-mismatch"
        for finding in result.findings
    )
    assert inspected.state == "invalid"


def test_audit_validator_rejects_terminal_before_started(tmp_path: Path) -> None:
    root = _setup_writer_root(tmp_path)
    started = _event("execution_attempt_started")
    terminal = _event("execution_failed")
    terminal["event_id"] = "evt-20260717-003"
    terminal["metadata"]["started_event_id"] = started["event_id"]
    terminal["timestamp"] = "2026-07-17T09:00:00+00:00"
    started["timestamp"] = "2026-07-17T10:00:00+00:00"
    path = root / "tasks" / "events.jsonl"
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(terminal) + "\n")
        fh.write(json.dumps(started) + "\n")

    result = validate_execution_audit_ledger(root)

    assert result.status == "validation_failed"
    assert any(
        finding.rule_id == "execution-audit-terminal-before-started"
        for finding in result.findings
    )


def test_audit_validator_rejects_started_reference_mismatch(tmp_path: Path) -> None:
    root = _setup_writer_root(tmp_path)
    started = _record_started(root)
    terminal = record_execution_terminal(
        root,
        attempt_id=started.attempt_id,
        event_type="execution_failed",
        phase="spawn",
        failure_code="spawn_failed",
    )
    assert terminal.status == "pass"
    events = _read_events(root)
    events[-1]["metadata"]["started_event_id"] = "evt-20260717-999"
    (root / "tasks" / "events.jsonl").write_text(
        "\n".join(json.dumps(event) for event in events) + "\n",
        encoding="utf-8",
    )

    result = validate_execution_audit_ledger(root)

    assert result.status == "validation_failed"
    assert any(
        finding.rule_id == "execution-audit-started-reference-mismatch"
        for finding in result.findings
    )


def test_audit_validator_rejects_duplicate_append_provenance(
    tmp_path: Path,
) -> None:
    root = _setup_writer_root(tmp_path)
    started = _record_started(root)
    terminal = record_execution_terminal(
        root,
        attempt_id=started.attempt_id,
        event_type="execution_failed",
        phase="spawn",
        failure_code="spawn_failed",
    )
    assert terminal.status == "pass"
    events = _read_events(root)
    events[-1]["metadata"]["append_token"] = events[-2]["metadata"]["append_token"]
    (root / "tasks" / "events.jsonl").write_text(
        "\n".join(json.dumps(event) for event in events) + "\n",
        encoding="utf-8",
    )

    result = validate_execution_audit_ledger(root)

    assert result.status == "validation_failed"
    assert any(
        finding.rule_id == "duplicate-execution-audit-append-token"
        for finding in result.findings
    )


@pytest.mark.parametrize(
    ("api", "kwargs"),
    (
        ("started", {"plan_hash": None}),
        ("inspect", {"attempt_id": None}),
        ("terminal", {"event_type": ["execution_failed"]}),
        ("terminal", {"output_digest": None}),
    ),
)
def test_writer_public_apis_return_structured_errors_for_invalid_types(
    tmp_path: Path, api: str, kwargs: dict[str, object]
) -> None:
    root = _setup_writer_root(tmp_path)
    if api == "started":
        result = record_execution_attempt_started(
            root,
            task_id="task-20260717-001",
            request_id="req-20260717-001",
            plan_hash=kwargs["plan_hash"],
            adapter_id="shell-local",
            capability="git_status",
            operation="git_status",
        )
    elif api == "inspect":
        result = inspect_execution_attempt(root, kwargs["attempt_id"])
    else:
        started = _record_started(root)
        terminal_args = {
            "attempt_id": started.attempt_id,
            "event_type": "execution_failed",
            "phase": "audit",
            "failure_code": "audit_failed",
        }
        terminal_args.update(kwargs)
        if "output_digest" in kwargs:
            terminal_args["output_digest"] = 123
        result = record_execution_terminal(root, **terminal_args)

    assert result.status == "validation_failed"
    assert result.findings


@pytest.mark.parametrize(
    ("event_type", "phase"),
    (
        ("execution_succeeded", "spawn"),
        ("execution_cancelled", "audit"),
    ),
)
def test_terminal_writer_rejects_conflicting_fixed_phase(
    tmp_path: Path, event_type: str, phase: str
) -> None:
    root = _setup_writer_root(tmp_path)
    started = _record_started(root)
    kwargs: dict[str, object] = {}
    if event_type == "execution_succeeded":
        kwargs = {
            "exit_code": 0,
            "guard_status": "pass",
            "stdout_truncated": False,
            "stderr_truncated": False,
        }
    else:
        kwargs = {"failure_code": "operator_cancelled"}

    result = record_execution_terminal(
        root,
        attempt_id=started.attempt_id,
        event_type=event_type,
        phase=phase,
        **kwargs,
    )

    assert result.status == "validation_failed"
    assert [finding.rule_id for finding in result.findings] == [
        "execution-terminal-phase-mismatch"
    ]


def test_task_event_validation_applies_dedicated_execution_schema(
    tmp_path: Path,
) -> None:
    root = _setup_writer_root(tmp_path)
    invalid = _event("execution_attempt_started")
    invalid["actor"] = "cli"
    with (root / "tasks" / "events.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(invalid) + "\n")

    from agent_runtime.task_validation import validate_records

    result = validate_records(root, "tasks/events.jsonl", "event")

    assert result.status == "validation_failed"
    assert any(
        finding.rule_id == "execution-audit-schema-validation-failed"
        for finding in result.findings
    )


def test_writer_source_has_no_execution_or_network_imports() -> None:
    source = (
        ROOT / "agent_runtime" / "execution_audit_writer.py"
    ).read_text(encoding="utf-8")

    for forbidden in ("import subprocess", "import socket", "import requests"):
        assert forbidden not in source
