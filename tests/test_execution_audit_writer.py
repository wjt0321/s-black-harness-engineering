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


def test_rollback_refuses_to_remove_a_concurrent_append(
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

    def _concurrent_then_fail(*args, **kwargs):
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(concurrent) + "\n")
        return CheckResult(
            status="validation_failed",
            findings=[
                Finding(
                    rule_id="simulated-post-check",
                    severity="error",
                    action="error",
                    message="simulated",
                )
            ],
        )

    monkeypatch.setattr(
        "agent_runtime.execution_audit_writer._post_check",
        _concurrent_then_fail,
    )

    result = _record_started(root)

    assert result.status == "error"
    assert result.rolled_back is False
    assert result.rollback_error == "concurrent-ledger-change"
    events = _read_events(root)
    assert any(event["event_id"] == concurrent["event_id"] for event in events)
    assert any(
        event["event_type"] == "execution_attempt_started" for event in events
    )


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

    with path.open("r+b") as handle:
        audit_writer._lock_ledger(handle)
        try:
            original_size, identity = audit_writer._ledger_boundary(path, handle)
            audit_writer._append_event_line(handle, concurrent_line)
            rolled_back, error = audit_writer._rollback_events_file(
                handle,
                path,
                original_size,
                identity,
                expected_line,
                0,
            )
        finally:
            audit_writer._unlock_ledger(handle)

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

    with path.open("r+b") as handle:
        audit_writer._lock_ledger(handle)
        try:
            original_size, identity = audit_writer._ledger_boundary(path, handle)
            audit_writer._append_event_line(handle, line)
            rolled_back, error = audit_writer._rollback_events_file(
                handle,
                path,
                original_size,
                identity,
                line,
                0,
            )
        finally:
            audit_writer._unlock_ledger(handle)

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


def test_preflight_identity_is_bound_before_event_validation_returns(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _setup_writer_root(tmp_path)
    path = root / "tasks" / "events.jsonl"
    before = path.read_bytes()
    original_validate = audit_writer._validate_event_object

    def _validate_then_replace(project_root: Path, event: dict[str, object]):
        result = original_validate(project_root, event)
        replacement = path.with_name("replacement.jsonl")
        replacement.write_bytes(before)
        os.replace(replacement, path)
        return result

    monkeypatch.setattr(
        "agent_runtime.execution_audit_writer._validate_event_object",
        _validate_then_replace,
    )

    result = _record_started(root)

    assert result.status == "error"
    assert result.committed is False
    assert [finding.rule_id for finding in result.findings] == [
        "execution-audit-preflight-drift"
    ]
    assert path.read_bytes() == before


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


def test_commit_rejects_bytes_appended_after_passing_post_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _setup_writer_root(tmp_path)
    path = root / "tasks" / "events.jsonl"
    original_post_check = audit_writer._post_check

    def _pass_then_drift(*args, **kwargs):
        result = original_post_check(*args, **kwargs)
        with path.open("ab") as handle:
            handle.write(b"not-json\n")
        return result

    monkeypatch.setattr(
        "agent_runtime.execution_audit_writer._post_check",
        _pass_then_drift,
    )

    result = _record_started(root)

    assert result.status == "error"
    assert result.committed is False
    assert result.rolled_back is False
    assert result.rollback_error == "concurrent-ledger-change"
    assert path.read_bytes().endswith(b"not-json\n")


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
