"""Tests for bounded execution recovery inspection and fixed closure."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
from types import SimpleNamespace

import pytest

from agent_runtime import execution_audit_writer as audit_writer
from agent_runtime import orchestration_execution_recovery as recovery
from agent_runtime.cli import main
from agent_runtime.execution_audit_writer import record_execution_attempt_started
from agent_runtime.bounded_ledger import open_bounded_ledger_session


ROOT = Path(__file__).resolve().parents[1]
PLAN_HASH = "sha256:" + "a" * 64


@pytest.fixture
def project(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    for rel in (
        "tasks/task.schema.json",
        "tasks/event.schema.json",
        "tasks/execution-audit-event.schema.json",
        "tasks/execution-audit-event-v2.schema.json",
    ):
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / rel, target)
    policies = root / "policies"
    policies.mkdir()
    for source in (ROOT / "policies").glob("*.sample.policy.json"):
        shutil.copyfile(source, policies / source.name)
    task = {
        "id": "task-20260723-001",
        "title": "recovery test",
        "status": "running",
        "created_at": "2026-07-23T01:00:00+00:00",
        "updated_at": "2026-07-23T01:00:00+00:00",
        "created_by": "cli",
        "source": "cli",
    }
    (root / "tasks" / "tasks.jsonl").write_text(
        json.dumps(task) + "\n", encoding="utf-8"
    )
    created = {
        "event_id": "evt-20260723-001",
        "task_id": task["id"],
        "timestamp": "2026-07-23T01:00:00+00:00",
        "actor": "cli",
        "event_type": "created",
        "from_status": None,
        "to_status": "running",
        "message": "created",
        "metadata": {},
    }
    (root / "tasks" / "events.jsonl").write_text(
        json.dumps(created) + "\n", encoding="utf-8"
    )
    return root


def _started(root: Path, request_id: str = "req-20260723-001"):
    result = record_execution_attempt_started(
        root,
        task_id="task-20260723-001",
        request_id=request_id,
        plan_hash=PLAN_HASH,
        adapter_id="shell-local",
        capability="git_status",
        operation="git_status",
    )
    assert result.status == "pass"
    return result


def _events(root: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in (root / "tasks" / "events.jsonl").read_text(encoding="utf-8").splitlines()
    ]


def _assert_ledgers_immediately_reacquirable(root: Path) -> None:
    for name in ("events.jsonl", "tasks.jsonl"):
        opened = open_bounded_ledger_session(root / "tasks" / name, exclusive=True)
        assert not isinstance(opened, recovery.CheckResult)
        opened.close()


def test_list_open_returns_safe_deterministic_ledger_order(project: Path) -> None:
    first = _started(project, "req-20260723-001")
    second = _started(project, "req-20260723-002")

    result = recovery.list_open_execution_attempts(project)

    assert result.status == "pass"
    assert [item["attempt_id"] for item in result.attempts] == [
        first.attempt_id,
        second.attempt_id,
    ]
    assert set(result.attempts[0]) == {
        "attempt_id",
        "started_event_id",
        "task_id",
        "request_id",
        "plan_hash",
        "phase",
        "recovery_action",
    }
    assert result.attempts[0]["recovery_action"] == "close_outcome_unknown"
    assert result.lease_state in {
        "active",
        "available",
        "inactive",
        "missing",
        "unavailable",
        "invalid",
    }
    assert "timestamp" not in json.dumps(result.to_dict())
    assert "append_token" not in json.dumps(result.to_dict())


def test_list_open_orders_only_by_reserved_started_line(project: Path) -> None:
    first = _started(project, "req-20260723-001")
    second = _started(project, "req-20260723-002")
    events = _events(project)
    events[0]["metadata"] = {"attempt_id": second.attempt_id}
    (project / "tasks" / "events.jsonl").write_text(
        "".join(json.dumps(event) + "\n" for event in events), encoding="utf-8"
    )

    result = recovery.list_open_execution_attempts(project)

    assert result.status == "pass"
    assert [item["attempt_id"] for item in result.attempts] == [
        first.attempt_id,
        second.attempt_id,
    ]


def test_list_open_fails_closed_above_128_without_partial_results(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    items = [
        {
            "attempt_id": f"attempt-20260723-{index:03d}",
            "started_event_id": f"evt-20260723-{index + 1:03d}",
            "task_id": "task-20260723-001",
            "request_id": f"req-20260723-{index:03d}",
            "plan_hash": PLAN_HASH,
            "phase": "pre_spawn_committed",
            "recovery_action": "close_outcome_unknown",
        }
        for index in range(129)
    ]
    monkeypatch.setattr(recovery, "_validated_open_attempts", lambda *_args, **_kwargs: items)

    result = recovery.list_open_execution_attempts(project)

    assert result.status == "validation_failed"
    assert result.attempts == []
    assert result.findings[0].rule_id == "execution-recovery-open-limit-exceeded"


def test_inspect_open_attempt_exposes_only_unknown_withheld_semantics(project: Path) -> None:
    started = _started(project)

    result = recovery.inspect_open_execution_attempt(project, started.attempt_id)
    payload = result.to_dict()

    assert result.status == "pass"
    assert payload["state"] == "awaiting_terminal"
    assert payload["historical_process_outcome"] == "unknown"
    assert payload["automatic_retry_allowed"] is False
    assert payload["result_release_allowed"] is False
    assert payload["recovery_action"] == "close_outcome_unknown"


def test_recovery_sanitizes_validation_findings_without_lines_or_input(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    unsafe = "../private/ledger.jsonl secret-value"
    monkeypatch.setattr(
        recovery,
        "_validated_open_attempts",
        lambda *_args, **_kwargs: recovery.CheckResult(
            status="validation_failed",
            findings=[
                recovery.Finding(
                    rule_id="unsafe-source-rule",
                    severity="error",
                    action="error",
                    message=unsafe,
                    line=47,
                    column=9,
                )
            ],
            next_action=unsafe,
        ),
    )

    listed = recovery.list_open_execution_attempts(project).to_dict()
    invalid = recovery.inspect_open_execution_attempt(project, unsafe).to_dict()
    rendered = json.dumps({"listed": listed, "invalid": invalid})

    assert listed["findings"] == [
        {
            "rule_id": "execution-recovery-ledger-invalid",
            "severity": "error",
            "action": "error",
            "message": "Execution recovery ledger validation failed.",
        }
    ]
    assert invalid.get("attempt_id") is None
    assert invalid["findings"][0]["rule_id"] == "invalid-execution-recovery-attempt-id"
    assert unsafe not in rendered
    assert "47" not in rendered


def test_list_maps_session_cleanup_baseexception_to_safe_failure(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original_close = audit_writer.BoundedLedgerSession.close

    def failing_close(session):
        original_close(session)
        if session.path.name == "events.jsonl":
            raise RuntimeError("private list cleanup detail")

    monkeypatch.setattr(audit_writer.BoundedLedgerSession, "close", failing_close)

    result = recovery.list_open_execution_attempts(project)

    assert result.status == "error"
    assert result.attempts == []
    assert result.findings[0].rule_id == "execution-recovery-ledger-invalid"
    assert "private list cleanup detail" not in json.dumps(result.to_dict())


def test_inspect_closed_attempt_does_not_claim_unknown_open_semantics(project: Path) -> None:
    started = _started(project)
    preview = recovery.close_open_execution_attempt(
        project,
        attempt_id=started.attempt_id,
        expected_started_event_id=started.event_id,
        expected_plan_hash=PLAN_HASH,
    )
    assert preview.status == "pass"
    assert preview.committed is False

    missing = recovery.inspect_open_execution_attempt(project, "attempt-20260723-999")
    assert missing.state == "missing"
    assert "historical_process_outcome" not in missing.to_dict()


def test_close_preview_is_no_write_and_binds_expected_values(project: Path) -> None:
    started = _started(project)
    before = (project / "tasks" / "events.jsonl").read_bytes()

    result = recovery.close_open_execution_attempt(
        project,
        attempt_id=started.attempt_id,
        expected_started_event_id=started.event_id,
        expected_plan_hash=PLAN_HASH,
    )

    assert result.status == "pass"
    assert result.state == "awaiting_terminal"
    assert result.committed is False
    assert result.historical_process_outcome == "unknown"
    assert result.result_release_allowed is False
    assert (project / "tasks" / "events.jsonl").read_bytes() == before


def test_close_commit_appends_only_fixed_outcome_unknown_terminal(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    started = _started(project)
    lease = SimpleNamespace(
        status="pass",
        lease_state="active",
        validate=lambda: True,
        release=lambda: SimpleNamespace(status="pass", findings=[], next_action=None),
    )
    monkeypatch.setattr(recovery, "_acquire_recovery_lease", lambda _root: lease)

    result = recovery.close_open_execution_attempt(
        project,
        attempt_id=started.attempt_id,
        expected_started_event_id=started.event_id,
        expected_plan_hash=PLAN_HASH,
        commit=True,
    )

    assert result.status == "pass"
    assert result.state == "closed_failed"
    assert result.committed is True
    assert result.historical_process_outcome == "unknown"
    assert result.result_release_allowed is False
    terminal = _events(project)[-1]
    assert terminal["event_type"] == "execution_failed"
    assert terminal["metadata"]["phase"] == "audit"
    assert terminal["metadata"]["failure_code"] == "execution.recovery_outcome_unknown"
    assert terminal["metadata"]["guard_status"] == "not_run"
    forbidden = {
        "exit_code",
        "duration_bucket",
        "output_digest",
        "stdout_byte_count",
        "stderr_byte_count",
        "stdout_truncated",
        "stderr_truncated",
    }
    assert forbidden.isdisjoint(terminal["metadata"])


def test_recovery_writer_never_uses_unbounded_task_reread(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    started = _started(project)
    lease = SimpleNamespace(
        status="pass",
        lease_state="active",
        validate=lambda: True,
        release=lambda: SimpleNamespace(status="pass", findings=[], next_action=None),
    )
    monkeypatch.setattr(recovery, "_acquire_recovery_lease", lambda _root: lease)
    monkeypatch.setattr(
        audit_writer,
        "validate_records",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("unbounded task reread")
        ),
    )

    result = recovery.close_open_execution_attempt(
        project,
        attempt_id=started.attempt_id,
        expected_started_event_id=started.event_id,
        expected_plan_hash=PLAN_HASH,
        commit=True,
    )

    assert result.status == "pass"
    assert result.committed is True


def test_close_sanitizes_writer_validation_findings(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    started = _started(project)
    private_path = "C:" + "/private/events.jsonl raw ledger content"
    lease = SimpleNamespace(
        status="pass",
        lease_state="active",
        validate=lambda: True,
        release=lambda: SimpleNamespace(status="pass", findings=[], next_action=None),
    )
    monkeypatch.setattr(recovery, "_acquire_recovery_lease", lambda _root: lease)
    monkeypatch.setattr(
        recovery,
        "record_execution_recovery_terminal",
        lambda *_args, **_kwargs: audit_writer.ExecutionAuditWriteResult(
            status="validation_failed",
            attempt_id=started.attempt_id,
            findings=[
                recovery.Finding(
                    rule_id="private-writer-rule",
                    severity="error",
                    action="error",
                    message=private_path,
                    line=81,
                )
            ],
        ),
    )

    result = recovery.close_open_execution_attempt(
        project,
        attempt_id=started.attempt_id,
        expected_started_event_id=started.event_id,
        expected_plan_hash=PLAN_HASH,
        commit=True,
    )

    assert result.status == "validation_failed"
    assert result.findings[0].rule_id == "execution-recovery-ledger-invalid"
    rendered = json.dumps(result.to_dict())
    assert ("C:" + "/private") not in rendered
    assert "81" not in rendered


def test_close_maps_committed_writer_session_cleanup_failure(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    started = _started(project)
    lease = SimpleNamespace(
        status="pass",
        lease_state="active",
        validate=lambda: True,
        release=lambda: SimpleNamespace(status="pass", findings=[], next_action=None),
    )
    monkeypatch.setattr(recovery, "_acquire_recovery_lease", lambda _root: lease)
    original_close = audit_writer.BoundedLedgerSession.close

    def failing_close(session):
        original_close(session)
        if session.path.name == "events.jsonl" and session.exclusive:
            raise RuntimeError("private cleanup detail")

    monkeypatch.setattr(audit_writer.BoundedLedgerSession, "close", failing_close)

    result = recovery.close_open_execution_attempt(
        project,
        attempt_id=started.attempt_id,
        expected_started_event_id=started.event_id,
        expected_plan_hash=PLAN_HASH,
        commit=True,
    )

    assert result.status == "error"
    assert result.committed is True
    assert result.state == "closed_failed"
    assert result.findings[0].rule_id == "execution-audit-session-cleanup-failed"
    assert "private cleanup detail" not in json.dumps(result.to_dict())


def test_close_maps_lease_release_baseexception_after_committed_append(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    started = _started(project)

    def release():
        raise KeyboardInterrupt("private lease detail")

    lease = SimpleNamespace(
        status="pass",
        lease_state="active",
        validate=lambda: True,
        release=release,
    )
    monkeypatch.setattr(recovery, "_acquire_recovery_lease", lambda _root: lease)

    result = recovery.close_open_execution_attempt(
        project,
        attempt_id=started.attempt_id,
        expected_started_event_id=started.event_id,
        expected_plan_hash=PLAN_HASH,
        commit=True,
    )

    assert result.status == "error"
    assert result.committed is True
    assert result.state == "closed_failed"
    assert result.findings[0].rule_id == "execution-recovery-lease-release-failed"
    assert "private lease detail" not in json.dumps(result.to_dict())


def test_close_maps_lease_validation_baseexception_and_release_failure(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    started = _started(project)

    def validate():
        raise RuntimeError("private validation detail")

    def release():
        raise KeyboardInterrupt("private release detail")

    lease = SimpleNamespace(
        status="pass",
        lease_state="active",
        validate=validate,
        release=release,
    )
    monkeypatch.setattr(recovery, "_acquire_recovery_lease", lambda _root: lease)

    result = recovery.close_open_execution_attempt(
        project,
        attempt_id=started.attempt_id,
        expected_started_event_id=started.event_id,
        expected_plan_hash=PLAN_HASH,
        commit=True,
    )

    assert result.status == "error"
    assert result.committed is False
    assert result.state == "awaiting_terminal"
    assert result.findings[0].rule_id == "execution-recovery-lease-release-failed"
    rendered = json.dumps(result.to_dict())
    assert "private validation detail" not in rendered
    assert "private release detail" not in rendered


@pytest.mark.parametrize(
    ("started_id", "plan_hash", "rule_id"),
    (
        ("evt-20260723-999", PLAN_HASH, "execution-recovery-started-event-mismatch"),
        ("matching", "sha256:" + "b" * 64, "execution-recovery-plan-hash-mismatch"),
    ),
)
def test_close_rejects_stale_expected_binding_without_write(
    project: Path,
    started_id: str,
    plan_hash: str,
    rule_id: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    started = _started(project)
    if started_id == "matching":
        started_id = started.event_id
    before = (project / "tasks" / "events.jsonl").read_bytes()
    lease = SimpleNamespace(
        status="pass",
        lease_state="active",
        validate=lambda: True,
        release=lambda: SimpleNamespace(status="pass", findings=[], next_action=None),
    )
    monkeypatch.setattr(recovery, "_acquire_recovery_lease", lambda _root: lease)

    result = recovery.close_open_execution_attempt(
        project,
        attempt_id=started.attempt_id,
        expected_started_event_id=started_id,
        expected_plan_hash=plan_hash,
        commit=True,
    )

    assert result.status == "blocked"
    assert result.findings[0].rule_id == rule_id
    assert (project / "tasks" / "events.jsonl").read_bytes() == before


def test_recovery_terminal_plan_mismatch_releases_both_ledger_sessions(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    started = _started(project)
    captured: list[object] = []
    original_preflight = audit_writer._preflight_ledgers

    def tracking_preflight(*args, **kwargs):
        result = original_preflight(*args, **kwargs)
        if not isinstance(result, recovery.CheckResult):
            captured.extend((result[-1].event_session, result[-1].task_session))
        return result

    monkeypatch.setattr(audit_writer, "_preflight_ledgers", tracking_preflight)

    result = audit_writer.record_execution_recovery_terminal(
        project,
        attempt_id=started.attempt_id,
        expected_started_event_id=started.event_id,
        expected_plan_hash="sha256:" + "b" * 64,
    )

    assert result.status == "blocked"
    assert result.findings[0].rule_id == "execution-recovery-plan-hash-mismatch"
    assert len(captured) == 2
    assert all(session._closed for session in captured)
    _assert_ledgers_immediately_reacquirable(project)


def test_recovery_terminal_event_validation_failure_releases_both_sessions(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    started = _started(project)
    captured: list[object] = []
    original_preflight = audit_writer._preflight_ledgers

    def tracking_preflight(*args, **kwargs):
        result = original_preflight(*args, **kwargs)
        if not isinstance(result, recovery.CheckResult):
            captured.extend((result[-1].event_session, result[-1].task_session))
        return result

    monkeypatch.setattr(audit_writer, "_preflight_ledgers", tracking_preflight)
    monkeypatch.setattr(
        audit_writer,
        "_validate_event_object",
        lambda *_args, **_kwargs: recovery.CheckResult(
            status="validation_failed",
            findings=[
                recovery.Finding(
                    rule_id="injected-event-invalid",
                    severity="error",
                    action="error",
                    message="Injected event validation failure.",
                )
            ],
        ),
    )

    result = audit_writer.record_execution_recovery_terminal(
        project,
        attempt_id=started.attempt_id,
        expected_started_event_id=started.event_id,
        expected_plan_hash=PLAN_HASH,
    )

    assert result.status == "validation_failed"
    assert len(captured) == 2
    assert all(session._closed for session in captured)
    _assert_ledgers_immediately_reacquirable(project)


def test_recovery_terminal_rejection_closes_task_when_event_cleanup_raises(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    started = _started(project)
    captured: list[object] = []
    original_preflight = audit_writer._preflight_ledgers
    original_close = audit_writer.BoundedLedgerSession.close

    def tracking_preflight(*args, **kwargs):
        result = original_preflight(*args, **kwargs)
        if not isinstance(result, recovery.CheckResult):
            captured.extend((result[-1].event_session, result[-1].task_session))
        return result

    def failing_event_close(session):
        original_close(session)
        if session.path.name == "events.jsonl" and session.exclusive:
            raise RuntimeError("private event cleanup detail")

    monkeypatch.setattr(audit_writer, "_preflight_ledgers", tracking_preflight)
    monkeypatch.setattr(audit_writer.BoundedLedgerSession, "close", failing_event_close)

    result = audit_writer.record_execution_recovery_terminal(
        project,
        attempt_id=started.attempt_id,
        expected_started_event_id=started.event_id,
        expected_plan_hash="sha256:" + "b" * 64,
    )

    assert result.status == "error"
    assert result.findings[0].rule_id == "execution-audit-session-cleanup-failed"
    assert len(captured) == 2
    assert all(session._closed for session in captured)
    assert "private event cleanup detail" not in json.dumps(result.to_dict())


def test_recovery_cli_surface_and_json_preview(project: Path, capsys) -> None:
    started = _started(project)
    before = (project / "tasks" / "events.jsonl").read_bytes()

    code = main(
        [
            "--root",
            str(project),
            "orchestration",
            "execution",
            "recovery",
            "close-open",
            "--attempt-id",
            started.attempt_id,
            "--expected-started-event-id",
            started.event_id,
            "--expected-plan-hash",
            PLAN_HASH,
            "--json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["committed"] is False
    assert payload["historical_process_outcome"] == "unknown"
    assert (project / "tasks" / "events.jsonl").read_bytes() == before
