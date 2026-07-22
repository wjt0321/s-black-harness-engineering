"""Bounded execution-audit snapshot and v1/v2 compatibility tests."""

from __future__ import annotations

from copy import deepcopy
import json
import os
from pathlib import Path
import shutil

import pytest

from agent_runtime import bounded_ledger
from agent_runtime import execution_audit_writer as audit_writer
from agent_runtime.bounded_ledger import (
    MAX_LEDGER_BYTES,
    MAX_PHYSICAL_LINES,
    MAX_PHYSICAL_LINE_BYTES,
    BoundedLedgerSnapshot,
    BoundedLedgerSession,
    open_bounded_ledger_session,
    snapshot_jsonl,
)
from agent_runtime.doctor import SCHEMA_FILES, run_doctor
from agent_runtime.execution_audit_writer import (
    inspect_execution_attempt,
    validate_execution_audit_ledger,
)
from agent_runtime.task_validation import validate_records

ROOT = Path(__file__).resolve().parents[1]


def _write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def _assert_rejected_without_records(result, rule_id: str) -> None:
    assert not isinstance(result, BoundedLedgerSnapshot)
    assert result.status in {"error", "validation_failed"}
    assert [finding.rule_id for finding in result.findings] == [rule_id]
    assert "records" not in result.to_dict()


def test_bounded_snapshot_accepts_limits_and_strict_objects(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    value: object = "leaf"
    for _ in range(32):
        value = [value]
    _write(path, (json.dumps({"value": value}) + "\n").encode())

    result = snapshot_jsonl(path)

    assert isinstance(result, BoundedLedgerSnapshot)
    assert result.physical_line_count == 1
    assert result.record_count == 1
    assert result.records[0]["_line_no"] == 1


def test_read_session_blocks_exclusive_session_for_validation_lifetime(
    tmp_path: Path,
) -> None:
    path = tmp_path / "events.jsonl"
    _write(path, b'{"value":true}\n')

    opened = open_bounded_ledger_session(path, exclusive=False)
    assert isinstance(opened, BoundedLedgerSession)
    with opened as session:
        assert isinstance(session.snapshot, BoundedLedgerSnapshot)
        contended = open_bounded_ledger_session(
            path, exclusive=True, blocking=False
        )
        assert not isinstance(contended, BoundedLedgerSession)
        assert contended.status == "blocked"
        assert "handle" not in json.dumps(session.snapshot.__dict__)

    acquired = open_bounded_ledger_session(path, exclusive=True, blocking=False)
    assert isinstance(acquired, BoundedLedgerSession)
    acquired.close()


@pytest.mark.parametrize(
    ("content", "rule_id"),
    (
        (b'{"key":"\xff"}\n', "bounded-ledger-invalid-utf8"),
        (b'{"key":1,"key":2}\n', "bounded-ledger-duplicate-key"),
        (b'{not-json}\n', "bounded-ledger-invalid-json"),
        (b'[]\n', "bounded-ledger-record-not-object"),
    ),
)
def test_bounded_snapshot_rejects_ambiguous_input_without_partial_results(
    tmp_path: Path, content: bytes, rule_id: str
) -> None:
    path = tmp_path / "events.jsonl"
    _write(path, b'{"valid":true}\n' + content)

    result = snapshot_jsonl(path)

    _assert_rejected_without_records(result, rule_id)


def test_bounded_snapshot_maps_integer_digit_value_error_safely(
    tmp_path: Path,
) -> None:
    path = tmp_path / "events.jsonl"
    _write(path, b'{"value":' + b"9" * 5000 + b"}\n")

    result = snapshot_jsonl(path)

    _assert_rejected_without_records(result, "bounded-ledger-invalid-json")
    assert "5000" not in result.render_json()
    _write(path, b'{"value":1}\n')
    acquired = open_bounded_ledger_session(path, exclusive=True, blocking=False)
    assert isinstance(acquired, BoundedLedgerSession)
    acquired.close()


@pytest.mark.parametrize("constant", ["NaN", "Infinity", "-Infinity"])
def test_bounded_snapshot_rejects_non_finite_json_constants(
    tmp_path: Path, constant: str
) -> None:
    path = tmp_path / "events.jsonl"
    _write(path, f'{{"value":{constant}}}\n'.encode())

    result = snapshot_jsonl(path)

    _assert_rejected_without_records(result, "bounded-ledger-invalid-json")
    assert constant not in result.render_json()


@pytest.mark.parametrize("number", ["1e999", "-1e999"])
def test_bounded_snapshot_rejects_exponent_overflow(
    tmp_path: Path, number: str
) -> None:
    path = tmp_path / "events.jsonl"
    _write(path, f'{{"value":{number}}}\n'.encode())

    result = snapshot_jsonl(path)

    _assert_rejected_without_records(result, "bounded-ledger-invalid-json")
    assert number not in result.render_json()


@pytest.mark.parametrize(
    ("number", "expected"),
    [("1e3", 1000.0), ("-2.5e-2", -0.025), ("5e-324", 5e-324)],
)
def test_bounded_snapshot_accepts_finite_exponents(
    tmp_path: Path, number: str, expected: float
) -> None:
    path = tmp_path / "events.jsonl"
    _write(path, f'{{"value":{number}}}\n'.encode())

    result = snapshot_jsonl(path)

    assert isinstance(result, BoundedLedgerSnapshot)
    assert result.records[0]["value"] == expected


def test_session_construction_snapshot_baseexception_releases_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "events.jsonl"
    _write(path, b'{"value":true}\n')
    original_snapshot = bounded_ledger._snapshot_handle
    monkeypatch.setattr(
        bounded_ledger,
        "_snapshot_handle",
        lambda *args, **kwargs: (_ for _ in ()).throw(KeyboardInterrupt()),
    )

    with pytest.raises(KeyboardInterrupt):
        open_bounded_ledger_session(path)

    monkeypatch.setattr(bounded_ledger, "_snapshot_handle", original_snapshot)
    acquired = open_bounded_ledger_session(path, exclusive=True, blocking=False)
    assert isinstance(acquired, BoundedLedgerSession)
    acquired.close()


def test_final_verification_detects_same_size_content_version_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "events.jsonl"
    _write(path, b'{"value":"one"}\n')
    original_digest = bounded_ledger._digest_handle
    calls = 0

    def _changed_final_digest(handle):
        nonlocal calls
        calls += 1
        digest = original_digest(handle)
        return "0" * 64 if calls == 1 else digest

    monkeypatch.setattr(bounded_ledger, "_digest_handle", _changed_final_digest)

    result = snapshot_jsonl(path)

    _assert_rejected_without_records(result, "bounded-ledger-content-drift")


def test_final_verification_exception_is_structured_and_releases_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "events.jsonl"
    _write(path, b'{"value":true}\n')
    monkeypatch.setattr(
        bounded_ledger,
        "_final_verify_snapshot",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("withheld")),
    )

    result = snapshot_jsonl(path)

    _assert_rejected_without_records(
        result, "bounded-ledger-final-verification-failed"
    )
    assert "withheld" not in result.render_json()


def test_bounded_snapshot_rejects_file_over_16_mib(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    _write(path, b" " * (MAX_LEDGER_BYTES + 1))

    _assert_rejected_without_records(
        snapshot_jsonl(path), "bounded-ledger-file-too-large"
    )


def test_bounded_snapshot_rejects_more_than_50000_physical_lines(
    tmp_path: Path,
) -> None:
    path = tmp_path / "events.jsonl"
    _write(path, b"\n" * (MAX_PHYSICAL_LINES + 1))

    _assert_rejected_without_records(
        snapshot_jsonl(path), "bounded-ledger-too-many-lines"
    )


def test_bounded_snapshot_rejects_physical_line_over_64_kib(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    _write(path, b" " * (MAX_PHYSICAL_LINE_BYTES + 1) + b"\n")

    _assert_rejected_without_records(
        snapshot_jsonl(path), "bounded-ledger-line-too-large"
    )


def test_bounded_snapshot_rejects_json_depth_over_32(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    value: object = "leaf"
    for _ in range(33):
        value = [value]
    _write(path, (json.dumps({"value": value}) + "\n").encode())

    _assert_rejected_without_records(
        snapshot_jsonl(path), "bounded-ledger-json-too-deep"
    )


@pytest.mark.parametrize("shape", ["directory", "symlink", "hardlink"])
def test_bounded_snapshot_rejects_unsafe_file_identity(
    tmp_path: Path, shape: str
) -> None:
    path = tmp_path / "events.jsonl"
    if shape == "directory":
        path.mkdir()
    elif shape == "symlink":
        target = tmp_path / "target.jsonl"
        _write(target, b"{}\n")
        try:
            path.symlink_to(target)
        except OSError:
            pytest.skip("symlinks unavailable")
    else:
        target = tmp_path / "target.jsonl"
        _write(target, b"{}\n")
        os.link(target, path)

    _assert_rejected_without_records(
        snapshot_jsonl(path), "bounded-ledger-unsafe-identity"
    )


def test_bounded_snapshot_rejects_identity_drift_without_partial_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "events.jsonl"
    _write(path, b'{"first":1}\n')
    original = bounded_ledger._path_identity
    calls = 0

    def _replace_before_final_check(candidate: Path):
        nonlocal calls
        calls += 1
        if calls == 1:
            device, inode = original(candidate)
            return device, inode + 1
        return original(candidate)

    monkeypatch.setattr(bounded_ledger, "_path_identity", _replace_before_final_check)

    _assert_rejected_without_records(
        snapshot_jsonl(path), "bounded-ledger-identity-drift"
    )


def test_read_session_blocks_same_size_rewrite_before_acceptance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "events.jsonl"
    _write(path, b'{"value":"one"}\n')
    original_digest = bounded_ledger._digest_handle
    blocked: list[bool] = []

    def _rewrite_then_digest(handle):
        contended = open_bounded_ledger_session(
            path, exclusive=True, blocking=False
        )
        if not isinstance(contended, BoundedLedgerSession):
            blocked.append(True)
        else:
            contended.close()
        return original_digest(handle)

    monkeypatch.setattr(bounded_ledger, "_digest_handle", _rewrite_then_digest)

    result = snapshot_jsonl(path)

    assert isinstance(result, BoundedLedgerSnapshot)
    assert blocked == [True]
    assert result.records[0]["value"] == "one"


def test_read_session_blocks_same_size_rewrite_at_path_acceptance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "events.jsonl"
    _write(path, b'{"value":"one"}\n')
    original_identity = bounded_ledger._path_identity
    blocked: list[bool] = []

    def _rewrite_then_identity(candidate: Path):
        contended = open_bounded_ledger_session(
            path, exclusive=True, blocking=False
        )
        if not isinstance(contended, BoundedLedgerSession):
            blocked.append(True)
        else:
            contended.close()
        return original_identity(candidate)

    monkeypatch.setattr(bounded_ledger, "_path_identity", _rewrite_then_identity)

    result = snapshot_jsonl(path)

    assert isinstance(result, BoundedLedgerSnapshot)
    assert blocked == [True, True]
    assert result.records[0]["value"] == "one"


def test_audit_validator_does_not_resolve_away_symlink_identity(
    tmp_path: Path,
) -> None:
    root = tmp_path / "project"
    tasks = root / "tasks"
    tasks.mkdir(parents=True)
    target = tasks / "target.jsonl"
    _write(target, b"{}\n")
    try:
        (tasks / "events.jsonl").symlink_to(target)
    except OSError:
        pytest.skip("symlinks unavailable")

    result = validate_execution_audit_ledger(root)

    assert result.status == "validation_failed"
    assert [finding.rule_id for finding in result.findings] == [
        "bounded-ledger-unsafe-identity"
    ]


def _audit_event(
    event_type: str,
    *,
    version: str,
    event_id: str,
    attempt_id: str = "attempt-20260722-001",
) -> dict[str, object]:
    metadata: dict[str, object] = {
        "writer_origin": "agent_runtime.execution_audit_writer",
        "writer_schema_version": version,
        "append_token": "append-" + event_id,
        "attempt_id": attempt_id,
        "request_id": "req-20260722-001",
        "plan_hash": "sha256:" + "a" * 64,
        "adapter_id": "shell-local",
        "capability": "git_status",
        "operation": "git_status",
    }
    if event_type == "execution_attempt_started":
        metadata["phase"] = "pre_spawn_committed"
    else:
        metadata.update(
            {
                "started_event_id": "evt-20260722-001",
                "phase": "post_run_validated",
                "exit_code": 0,
                "guard_status": "pass",
                "stdout_truncated": False,
                "stderr_truncated": False,
                "stderr_byte_count": 0,
            }
        )
        if version == "execution-audit/v2":
            metadata.update(
                {
                    "job_accounting_passed": True,
                    "job_total_processes": 1,
                    "job_active_processes": 0,
                    "job_terminated_processes": 0,
                    "direct_child_reaped": True,
                    "containment_closed": True,
                }
            )
    return {
        "event_id": event_id,
        "task_id": "task-20260722-001",
        "timestamp": "2026-07-22T01:00:00+00:00",
        "actor": "local-operator",
        "event_type": event_type,
        "message": "Execution audit lifecycle event.",
        "metadata": metadata,
    }


def _audit_root(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    (root / "tasks").mkdir(parents=True)
    for name in (
        "task.schema.json",
        "event.schema.json",
        "execution-audit-event.schema.json",
        "execution-audit-event-v2.schema.json",
    ):
        shutil.copyfile(ROOT / "tasks" / name, root / "tasks" / name)
    task = {
        "id": "task-20260722-001",
        "title": "bounded audit test",
        "status": "running",
        "created_at": "2026-07-22T01:00:00+00:00",
        "updated_at": "2026-07-22T01:00:00+00:00",
        "created_by": "cli",
        "source": "cli",
    }
    (root / "tasks" / "tasks.jsonl").write_text(
        json.dumps(task) + "\n", encoding="utf-8"
    )
    return root


def _write_events(root: Path, events: list[dict[str, object]]) -> None:
    (root / "tasks" / "events.jsonl").write_text(
        "".join(json.dumps(event) + "\n" for event in events), encoding="utf-8"
    )


@pytest.mark.parametrize("version", ["execution-audit/v1", "execution-audit/v2"])
def test_audit_validator_accepts_complete_same_version_chains(
    tmp_path: Path, version: str
) -> None:
    root = _audit_root(tmp_path)
    _write_events(
        root,
        [
            _audit_event(
                "execution_attempt_started", version=version, event_id="evt-20260722-001"
            ),
            _audit_event(
                "execution_succeeded", version=version, event_id="evt-20260722-002"
            ),
        ],
    )

    assert validate_execution_audit_ledger(root).status == "pass"
    assert validate_records(root, "tasks/events.jsonl", "event").status == "pass"


def test_audit_validator_rejects_mixed_version_chain(tmp_path: Path) -> None:
    root = _audit_root(tmp_path)
    _write_events(
        root,
        [
            _audit_event(
                "execution_attempt_started",
                version="execution-audit/v1",
                event_id="evt-20260722-001",
            ),
            _audit_event(
                "execution_succeeded",
                version="execution-audit/v2",
                event_id="evt-20260722-002",
            ),
        ],
    )

    result = validate_execution_audit_ledger(root)

    assert result.status == "validation_failed"
    assert "execution-audit-version-mismatch" in {
        finding.rule_id for finding in result.findings
    }


def test_public_audit_validation_rejects_invalid_ordinary_event_value_safely(
    tmp_path: Path,
) -> None:
    root = _audit_root(tmp_path)
    sensitive = "ordinary-" + "x" * 40
    ordinary = {
        "event_id": "evt-20260722-900",
        "task_id": "task-20260722-001",
        "timestamp": "2026-07-22T01:00:00+00:00",
        "actor": sensitive,
        "event_type": "created",
        "from_status": None,
        "to_status": "running",
        "message": "created",
        "unexpected": True,
    }
    _write_events(root, [ordinary])

    result = validate_execution_audit_ledger(root)

    assert result.status == "validation_failed"
    assert "schema-validation-failed" in {finding.rule_id for finding in result.findings}
    assert sensitive not in result.render_json()


def test_audit_inspection_rejects_unknown_task_anywhere_value_safely(
    tmp_path: Path,
) -> None:
    root = _audit_root(tmp_path)
    started = _audit_event(
        "execution_attempt_started",
        version="execution-audit/v1",
        event_id="evt-20260722-001",
    )
    sensitive = "task-20260722-999"
    ordinary = {
        "event_id": "evt-20260722-900",
        "task_id": sensitive,
        "timestamp": "2026-07-22T02:00:00+00:00",
        "actor": "cli",
        "event_type": "progress",
        "message": "progress",
        "metadata": {},
    }
    _write_events(root, [started, ordinary])

    inspected = inspect_execution_attempt(root, "attempt-20260722-001")

    assert inspected.status == "validation_failed"
    assert inspected.state == "invalid"
    assert "unknown-task-id" in {finding.rule_id for finding in inspected.findings}
    assert sensitive not in inspected.render_json()


@pytest.mark.parametrize("consumer", ["validate", "inspect"])
def test_public_consumer_runs_final_session_verification(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, consumer: str
) -> None:
    root = _audit_root(tmp_path)
    _write_events(
        root,
        [
            _audit_event(
                "execution_attempt_started",
                version="execution-audit/v1",
                event_id="evt-20260722-001",
            )
        ],
    )
    original_verify = bounded_ledger._final_verify_snapshot
    calls = 0

    def _fail_after_projection(path: Path, handle, snapshot):
        nonlocal calls
        calls += 1
        if calls == 4:
            return bounded_ledger._failure(
                "bounded-ledger-content-drift",
                "Execution audit ledger content changed during final verification.",
            )
        return original_verify(path, handle, snapshot)

    monkeypatch.setattr(
        bounded_ledger, "_final_verify_snapshot", _fail_after_projection
    )

    result = (
        validate_execution_audit_ledger(root)
        if consumer == "validate"
        else inspect_execution_attempt(root, "attempt-20260722-001")
    )

    assert result.status == "validation_failed"
    assert "bounded-ledger-content-drift" in {
        finding.rule_id for finding in result.findings
    }
    if consumer == "inspect":
        assert result.state == "invalid"


@pytest.mark.parametrize("consumer", ["validate", "inspect"])
@pytest.mark.parametrize(
    "task_bytes",
    [
        b'{not-json}\n',
        b'{"id":"task-20260722-001","id":"task-20260722-999"}\n',
        b'[]\n',
    ],
    ids=["malformed-json", "duplicate-key", "non-object"],
)
def test_public_consumer_rejects_malformed_task_ledger_value_safely(
    tmp_path: Path,
    consumer: str,
    task_bytes: bytes,
) -> None:
    root = _audit_root(tmp_path)
    events_path = root / "tasks" / "events.jsonl"
    _write_events(
        root,
        [
            _audit_event(
                "execution_attempt_started",
                version="execution-audit/v1",
                event_id="evt-20260722-001",
            )
        ],
    )
    tasks_path = root / "tasks" / "tasks.jsonl"
    tasks_path.write_bytes(task_bytes)

    result = (
        validate_execution_audit_ledger(root)
        if consumer == "validate"
        else inspect_execution_attempt(root, "attempt-20260722-001")
    )

    assert result.status == "validation_failed"
    assert [finding.rule_id for finding in result.findings] == [
        "execution-audit-tasks-invalid"
    ]
    rendered = result.render_json()
    assert "not-json" not in rendered
    assert "task-20260722-999" not in rendered
    assert str(tasks_path) not in rendered
    acquired = open_bounded_ledger_session(
        events_path, exclusive=True, blocking=False
    )
    assert isinstance(acquired, BoundedLedgerSession)
    acquired.close()
    if consumer == "inspect":
        assert result.state == "invalid"


@pytest.mark.parametrize("consumer", ["validate", "inspect"])
def test_public_consumer_maps_task_loader_oserror_value_safely(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    consumer: str,
) -> None:
    root = _audit_root(tmp_path)
    events_path = root / "tasks" / "events.jsonl"
    _write_events(
        root,
        [
            _audit_event(
                "execution_attempt_started",
                version="execution-audit/v1",
                event_id="evt-20260722-001",
            )
        ],
    )
    original_open = audit_writer.open_bounded_ledger_session

    def _fail_tasks(path: Path, **kwargs):
        if path.name == "tasks.jsonl":
            raise OSError("withheld-task-path")
        return original_open(path, **kwargs)

    monkeypatch.setattr(
        "agent_runtime.execution_audit_writer.open_bounded_ledger_session",
        _fail_tasks,
    )

    result = (
        validate_execution_audit_ledger(root)
        if consumer == "validate"
        else inspect_execution_attempt(root, "attempt-20260722-001")
    )

    assert result.status == "error"
    assert [finding.rule_id for finding in result.findings] == [
        "execution-audit-tasks-read-failed"
    ]
    assert "withheld-task-path" not in result.render_json()
    acquired = original_open(events_path, exclusive=True, blocking=False)
    assert isinstance(acquired, BoundedLedgerSession)
    acquired.close()


@pytest.mark.parametrize(
    "field",
    (
        "job_accounting_passed",
        "job_total_processes",
        "job_active_processes",
        "job_terminated_processes",
        "direct_child_reaped",
        "containment_closed",
    ),
)
def test_v2_succeeded_requires_every_frozen_job_evidence_field(
    tmp_path: Path, field: str
) -> None:
    root = _audit_root(tmp_path)
    started = _audit_event(
        "execution_attempt_started",
        version="execution-audit/v2",
        event_id="evt-20260722-001",
    )
    terminal = _audit_event(
        "execution_succeeded",
        version="execution-audit/v2",
        event_id="evt-20260722-002",
    )
    del terminal["metadata"][field]
    _write_events(root, [started, terminal])

    result = validate_execution_audit_ledger(root)

    assert result.status == "validation_failed"
    assert "execution-audit-schema-validation-failed" in {
        finding.rule_id for finding in result.findings
    }


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("job_accounting_passed", False),
        ("job_active_processes", 1),
        ("direct_child_reaped", False),
        ("containment_closed", False),
        ("raw_job_handle", "withheld"),
    ),
)
def test_v2_succeeded_rejects_unsafe_or_nonready_job_evidence(
    tmp_path: Path, field: str, value: object
) -> None:
    root = _audit_root(tmp_path)
    terminal = _audit_event(
        "execution_succeeded",
        version="execution-audit/v2",
        event_id="evt-20260722-002",
    )
    terminal["metadata"][field] = value
    _write_events(
        root,
        [
            _audit_event(
                "execution_attempt_started",
                version="execution-audit/v2",
                event_id="evt-20260722-001",
            ),
            terminal,
        ],
    )

    assert validate_execution_audit_ledger(root).status == "validation_failed"


def test_v2_schema_is_registered_without_changing_frozen_v1() -> None:
    assert "tasks/execution-audit-event-v2.schema.json" in SCHEMA_FILES
    assert run_doctor(ROOT).status == "pass"


@pytest.mark.parametrize("event_type", ["execution_failed", "execution_cancelled"])
@pytest.mark.parametrize(
    "fields",
    [
        ["job_accounting_passed"],
        ["job_total_processes", "job_active_processes"],
        ["direct_child_reaped", "containment_closed"],
        [
            "job_accounting_passed",
            "job_total_processes",
            "job_active_processes",
            "job_terminated_processes",
            "direct_child_reaped",
        ],
    ],
)
def test_v2_failed_or_cancelled_rejects_partial_job_evidence(
    tmp_path: Path, event_type: str, fields: list[str]
) -> None:
    root = _audit_root(tmp_path)
    started = _audit_event(
        "execution_attempt_started",
        version="execution-audit/v2",
        event_id="evt-20260722-001",
    )
    terminal = _audit_event(
        event_type,
        version="execution-audit/v2",
        event_id="evt-20260722-002",
    )
    terminal["metadata"]["phase"] = "spawn" if event_type == "execution_failed" else "cancelled"
    terminal["metadata"]["failure_code"] = "operator_cancelled" if event_type == "execution_cancelled" else "spawn_failed"
    for field in (
        "job_accounting_passed",
        "job_total_processes",
        "job_active_processes",
        "job_terminated_processes",
        "direct_child_reaped",
        "containment_closed",
    ):
        terminal["metadata"].pop(field, None)
    for field in fields:
        terminal["metadata"][field] = {
            "job_accounting_passed": True,
            "job_total_processes": 1,
            "job_active_processes": 0,
            "job_terminated_processes": 0,
            "direct_child_reaped": True,
            "containment_closed": True,
        }[field]
    _write_events(root, [started, terminal])

    result = validate_execution_audit_ledger(root)

    assert result.status == "validation_failed"


@pytest.mark.parametrize("event_type", ["execution_failed", "execution_cancelled"])
@pytest.mark.parametrize("include_job_evidence", [False, True])
def test_v2_failed_or_cancelled_accepts_no_or_complete_job_evidence(
    tmp_path: Path, event_type: str, include_job_evidence: bool
) -> None:
    root = _audit_root(tmp_path)
    started = _audit_event(
        "execution_attempt_started",
        version="execution-audit/v2",
        event_id="evt-20260722-001",
    )
    terminal = _audit_event(
        event_type,
        version="execution-audit/v2",
        event_id="evt-20260722-002",
    )
    terminal["metadata"]["phase"] = "spawn" if event_type == "execution_failed" else "cancelled"
    terminal["metadata"]["failure_code"] = "operator_cancelled" if event_type == "execution_cancelled" else "spawn_failed"
    if not include_job_evidence:
        for field in (
            "job_accounting_passed",
            "job_total_processes",
            "job_active_processes",
            "job_terminated_processes",
            "direct_child_reaped",
            "containment_closed",
        ):
            terminal["metadata"].pop(field, None)
    _write_events(root, [started, terminal])

    assert validate_execution_audit_ledger(root).status == "pass"
