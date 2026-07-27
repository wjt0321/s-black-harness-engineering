from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import pytest

from agent_runtime.orchestration_single_work_item_execution import (
    _implementation_digest,
    build_single_work_item_execution_plan,
    execute_single_work_item,
)
from agent_runtime.result import CheckResult

ROOT = Path(__file__).resolve().parents[1]


def _project(
    tmp_path: Path,
    profile: str = "omp-local",
    *,
    review_required: bool = False,
    include_review_gate: bool = True,
) -> tuple[Path, Path]:
    root = tmp_path / "project"
    root.mkdir()
    shutil.copytree(ROOT / "adapters", root / "adapters")
    shutil.copytree(ROOT / "policies", root / "policies")
    shutil.copytree(ROOT / "integrations", root / "integrations")
    shutil.copytree(ROOT / ".pi", root / ".pi")
    shutil.copytree(ROOT / ".omp", root / ".omp")
    (root / "tasks").mkdir()
    (root / "tasks/tasks.jsonl").write_text(
        '{"id":"task-stage87","title":"阶段87验收","status":"running","created_at":"2026-07-27T10:00:00+08:00","updated_at":"2026-07-27T10:00:00+08:00","created_by":"maintainer","source":"cli","assignee":"orchestrator","priority":"normal","tags":[],"current_step":"执行一个工作项","summary":"测试","artifacts":[],"evidence":[],"blocked_reason":null,"blocked_message":null,"failure_reason":null,"next_action":"等待结果","parent_id":null}\n',
        encoding="utf-8",
    )
    (root / "tasks/events.jsonl").write_text("", encoding="utf-8")
    socket_id = "omp-acp" if profile == "omp-local" else "pi-cli"
    capability = "light_coding" if profile == "omp-local" else "cli_agent_print"
    plan = {
        "parent_task_ref": "task-stage87",
        "revision": 1,
        "socket_bindings": ([{"socket_id": socket_id, "role": "implementer", "required_capabilities": [capability]}]
                            + ([{"socket_id": "claude-code-acp", "role": "reviewer", "required_capabilities": ["quality_review"]}]
                               if review_required else [])),
        "work_items": [{
            "work_item_id": "implement",
            "socket_id": socket_id,
            "role": "implementer",
            "depends_on": [],
            "expected_artifact_types": ["test_result"],
            "review_required": review_required,
        }],
        "handoffs": [],
        "review_gates": ([{
            "gate_id": "review-implementation",
            "after_work_item_ids": ["implement"],
            "review_role": "reviewer",
            "decision_options": ["approve", "request_changes"],
        }] if review_required and include_review_gate else []),
    }
    (root / "adapters/stage87-plan.json").write_text(json.dumps(plan), encoding="utf-8")
    request = {
        "version": 1,
        "task_id": "task-stage87",
        "request_id": "request-stage87-001",
        "collaboration_file": "adapters/stage87-plan.json",
        "work_item_id": "implement",
        "target_profile": profile,
        "instruction": "只回复：阶段87受控执行验收通过。不要使用工具。",
        "input_artifacts": [],
        "timeout_seconds": 30,
        "result_max_bytes": 8192,
    }
    request_path = root / "adapters/stage87-request.json"
    request_path.write_text(json.dumps(request), encoding="utf-8")
    return root, request_path


def _live_status(profile: str = "omp-local", *, state: str = "open", observation: str = "observed"):
    return SimpleNamespace(
        status="pass",
        observation_status=observation,
        evidence={
            "evidence_id": "sha256:" + "1" * 64,
            "source_snapshot_id": "sha256:" + "2" * 64,
            "observed_at": "2026-07-27T12:00:00Z",
            "expires_at": "2026-07-27T12:00:15Z",
            "target": {"agent_id": profile, "adapter_id": f"{profile}-status"},
            "session_state": state,
            "source_integrity": {"generation": 7, "producer_binding_valid": True, "stable_read": True, "complete": True},
        },
        findings=(),
    )


def _host_success(profile: str = "omp-local", output: str = "阶段87受控执行验收通过。") -> dict[str, object]:
    encoded = output.encode("utf-8")
    import hashlib

    return {
        "version": 2,
        "contract": "external-agent-single-work-item-result/v2",
        "status": "succeeded",
        "request_id": "request-stage87-001",
        "target_profile": profile,
        "completed_at": "2026-07-27T12:00:09Z",
        "output": output,
        "output_bytes": len(encoded),
        "output_digest": "sha256:" + hashlib.sha256(encoded).hexdigest(),
        "events": [
            {"sequence": 1, "event_type": "request_claimed", "occurred_at": "2026-07-27T12:00:05Z"},
            {"sequence": 2, "event_type": "host_turn_dispatched", "occurred_at": "2026-07-27T12:00:06Z"},
            {"sequence": 3, "event_type": "host_turn_started", "occurred_at": "2026-07-27T12:00:07Z"},
            {"sequence": 4, "event_type": "host_turn_completed", "occurred_at": "2026-07-27T12:00:09Z"},
        ],
        "artifacts": [],
    }


def test_preview_returns_stable_one_time_approval_binding(tmp_path: Path) -> None:
    root, request_path = _project(tmp_path)
    services = {"inspect_status": lambda *_args, **_kwargs: _live_status()}

    first = build_single_work_item_execution_plan(
        root, request_path.relative_to(root).as_posix(), "2026-07-27T12:00:05Z", services=services
    )
    second = build_single_work_item_execution_plan(
        root, request_path.relative_to(root).as_posix(), "2026-07-27T12:00:06Z", services=services
    )

    assert first.status == "needs_approval"
    assert first.approval_binding_id == second.approval_binding_id
    assert first.plan is not None
    assert first.plan["operation"] == "external-agent.single-work-item"
    assert first.plan["target_profile"] == "omp-local"
    assert first.plan["instruction_digest"].startswith("sha256:")
    assert "instruction" not in first.to_dict()["plan"]
    assert first.to_dict()["guarantees"]["starts_agent_process"] is False


def test_preview_fails_closed_when_target_session_is_not_open(tmp_path: Path) -> None:
    root, request_path = _project(tmp_path)
    result = build_single_work_item_execution_plan(
        root,
        request_path.relative_to(root).as_posix(),
        "2026-07-27T12:00:05Z",
        services={"inspect_status": lambda *_args, **_kwargs: _live_status(state="closed")},
    )
    assert result.status == "blocked"
    assert [item.rule_id for item in result.findings] == ["single-work-item-session-not-open"]


def test_preview_rejects_profile_socket_mismatch(tmp_path: Path) -> None:
    root, request_path = _project(tmp_path, profile="omp-local")
    request = json.loads(request_path.read_text(encoding="utf-8"))
    request["target_profile"] = "pi-local"
    request_path.write_text(json.dumps(request), encoding="utf-8")
    result = build_single_work_item_execution_plan(
        root,
        request_path.relative_to(root).as_posix(),
        "2026-07-27T12:00:05Z",
        services={"inspect_status": lambda *_args, **_kwargs: _live_status("pi-local")},
    )
    assert result.status == "validation_failed"
    assert [item.rule_id for item in result.findings] == ["single-work-item-socket-profile-mismatch"]


def test_commit_requires_exact_preview_binding_before_any_write(tmp_path: Path) -> None:
    root, request_path = _project(tmp_path)
    called: list[str] = []
    services = {
        "inspect_status": lambda *_args, **_kwargs: _live_status(),
        "acquire_lease": lambda *_args, **_kwargs: called.append("lease"),
    }
    result = execute_single_work_item(
        root,
        request_path.relative_to(root).as_posix(),
        "2026-07-27T12:00:05Z",
        approval_binding_id="sha256:" + "0" * 64,
        commit=True,
        services=services,
    )
    assert result.status == "blocked"
    assert [item.rule_id for item in result.findings] == ["single-work-item-approval-binding-mismatch"]
    assert called == []
    assert not (root / ".runtime").exists()


@dataclass
class _Lease(CheckResult):
    released: bool = False
    def validate(self) -> bool:
        return True
    def release(self) -> CheckResult:
        self.released = True
        return CheckResult(status="pass")


def test_commit_records_started_then_terminal_and_releases_safe_result(tmp_path: Path) -> None:
    root, request_path = _project(tmp_path)
    preview_services = {"inspect_status": lambda *_args, **_kwargs: _live_status()}
    preview = build_single_work_item_execution_plan(
        root, request_path.relative_to(root).as_posix(), "2026-07-27T12:00:05Z", services=preview_services
    )
    calls: list[str] = []
    terminal_kwargs: dict[str, object] = {}
    dispatched_payload: dict[str, object] = {}
    lease = _Lease(status="pass")

    def started(*_args, **_kwargs):
        calls.append("started")
        return SimpleNamespace(status="pass", committed=True, attempt_id="attempt-stage87-001", event_id="evt-stage87-001", findings=[])

    def exchange(_root, payload, *_args, **_kwargs):
        calls.append("exchange")
        dispatched_payload.update(payload)
        return _host_success()

    def terminal(*_args, **kwargs):
        calls.append("terminal")
        terminal_kwargs.update(kwargs)
        return SimpleNamespace(status="pass", committed=True, event_id="evt-stage87-002", findings=[])

    services = {
        "inspect_status": lambda *_args, **_kwargs: _live_status(),
        "acquire_lease": lambda *_args, **_kwargs: lease,
        "record_started": started,
        "exchange": exchange,
        "scan_text": lambda *_args, **_kwargs: CheckResult(status="pass"),
        "record_terminal": terminal,
        "request_already_used": lambda *_args, **_kwargs: False,
    }
    result = execute_single_work_item(
        root,
        request_path.relative_to(root).as_posix(),
        "2026-07-27T12:00:05Z",
        approval_binding_id=preview.approval_binding_id,
        commit=True,
        services=services,
    )
    assert result.status == "pass"
    assert result.output == "阶段87受控执行验收通过。"
    assert calls == ["started", "exchange", "terminal"]
    assert lease.released is True
    assert result.audit["state"] == "closed_succeeded"
    assert terminal_kwargs["phase"] == "post_run_validated"
    assert terminal_kwargs["guard_status"] == "pass"
    assert terminal_kwargs["job_accounting_passed"] is True
    assert terminal_kwargs["job_total_processes"] == 0
    assert terminal_kwargs["job_active_processes"] == 0
    assert terminal_kwargs["job_terminated_processes"] == 0
    assert terminal_kwargs["direct_child_reaped"] is True
    assert terminal_kwargs["containment_closed"] is True
    assert dispatched_payload["timeout_seconds"] == 30
    assert result.evidence["status"] == "pass"
    assert result.evidence["artifact"]["artifact_type"] == "test_result"
    assert result.evidence["review"]["status"] == "not_required"


def test_failed_exchange_uses_schema_compatible_terminal_audit(tmp_path: Path) -> None:
    root, request_path = _project(tmp_path)
    status_service = {"inspect_status": lambda *_args, **_kwargs: _live_status()}
    preview = build_single_work_item_execution_plan(
        root, request_path.relative_to(root).as_posix(), "2026-07-27T12:00:05Z", services=status_service
    )
    lease = _Lease(status="pass")
    terminal_kwargs: dict[str, object] = {}

    def terminal(*_args, **kwargs):
        terminal_kwargs.update(kwargs)
        return SimpleNamespace(status="pass", committed=True, event_id="evt-stage87-002", findings=[])

    services = {
        **status_service,
        "acquire_lease": lambda *_args, **_kwargs: lease,
        "record_started": lambda *_args, **_kwargs: SimpleNamespace(
            status="pass", committed=True, attempt_id="attempt-stage87-001", findings=[]
        ),
        "exchange": lambda *_args, **_kwargs: {
            "status": "blocked",
            "failure_code": "mailbox-request-invalid",
            "artifacts": [],
        },
        "record_terminal": terminal,
        "request_already_used": lambda *_args, **_kwargs: False,
    }
    result = execute_single_work_item(
        root,
        request_path.relative_to(root).as_posix(),
        "2026-07-27T12:00:05Z",
        approval_binding_id=preview.approval_binding_id,
        commit=True,
        services=services,
    )
    assert result.status == "blocked"
    assert terminal_kwargs["event_type"] == "execution_failed"
    assert terminal_kwargs["phase"] == "child"
    assert terminal_kwargs["guard_status"] == "failed"



def test_request_replay_is_blocked_before_started_audit(tmp_path: Path) -> None:
    root, request_path = _project(tmp_path)
    status_service = {"inspect_status": lambda *_args, **_kwargs: _live_status()}
    preview = build_single_work_item_execution_plan(
        root, request_path.relative_to(root).as_posix(), "2026-07-27T12:00:05Z", services=status_service
    )
    calls: list[str] = []
    services = {
        **status_service,
        "request_already_used": lambda *_args, **_kwargs: True,
        "acquire_lease": lambda *_args, **_kwargs: calls.append("lease"),
    }
    result = execute_single_work_item(
        root,
        request_path.relative_to(root).as_posix(),
        "2026-07-27T12:00:05Z",
        approval_binding_id=preview.approval_binding_id,
        commit=True,
        services=services,
    )
    assert result.status == "blocked"
    assert [item.rule_id for item in result.findings] == ["single-work-item-request-replayed"]
    assert calls == []


def test_preview_requires_exactly_one_review_gate_for_reviewed_work_item(tmp_path: Path) -> None:
    root, request_path = _project(tmp_path, review_required=True, include_review_gate=False)
    result = build_single_work_item_execution_plan(
        root,
        request_path.relative_to(root).as_posix(),
        "2026-07-27T12:00:05Z",
        services={"inspect_status": lambda *_args, **_kwargs: _live_status()},
    )

    assert result.status == "validation_failed"
    assert [item.rule_id for item in result.findings] in (["single-work-item-collaboration-invalid"], ["single-work-item-review-gate-invalid"])


def test_reviewed_execution_is_archived_as_pending_review(tmp_path: Path) -> None:
    root, request_path = _project(tmp_path, review_required=True)
    status_service = {"inspect_status": lambda *_args, **_kwargs: _live_status()}
    preview = build_single_work_item_execution_plan(
        root, request_path.relative_to(root).as_posix(), "2026-07-27T12:00:05Z", services=status_service
    )
    assert preview.plan["review_gate_id"] == "review-implementation"
    lease = _Lease(status="pass")
    services = {
        **status_service,
        "acquire_lease": lambda *_args, **_kwargs: lease,
        "record_started": lambda *_args, **_kwargs: SimpleNamespace(
            status="pass", committed=True, attempt_id="attempt-stage88-review-001", findings=[]
        ),
        "exchange": lambda *_args, **_kwargs: _host_success(),
        "scan_text": lambda *_args, **_kwargs: CheckResult(status="pass"),
        "record_terminal": lambda *_args, **_kwargs: SimpleNamespace(status="pass", committed=True, findings=[]),
        "request_already_used": lambda *_args, **_kwargs: False,
    }

    result = execute_single_work_item(
        root,
        request_path.relative_to(root).as_posix(),
        "2026-07-27T12:00:05Z",
        approval_binding_id=preview.approval_binding_id,
        commit=True,
        services=services,
    )

    assert result.status == "pass"
    assert result.evidence["review"] == {
        "required": True,
        "gate_id": "review-implementation",
        "status": "pending",
    }
    assert result.next_action == "在中文控制面查看真实事件和结果产物，然后提交人工审阅。"


def test_terminal_audit_failure_leaves_recoverable_pending_evidence(tmp_path: Path) -> None:
    root, request_path = _project(tmp_path)
    status_service = {"inspect_status": lambda *_args, **_kwargs: _live_status()}
    preview = build_single_work_item_execution_plan(
        root, request_path.relative_to(root).as_posix(), "2026-07-27T12:00:05Z", services=status_service
    )
    services = {
        **status_service,
        "acquire_lease": lambda *_args, **_kwargs: _Lease(status="pass"),
        "record_started": lambda *_args, **_kwargs: SimpleNamespace(
            status="pass", committed=True, attempt_id="attempt-stage88-pending-001", findings=[]
        ),
        "exchange": lambda *_args, **_kwargs: _host_success(),
        "scan_text": lambda *_args, **_kwargs: CheckResult(status="pass"),
        "record_terminal": lambda *_args, **_kwargs: SimpleNamespace(
            status="error", committed=False, findings=[]
        ),
        "request_already_used": lambda *_args, **_kwargs: False,
    }

    result = execute_single_work_item(
        root,
        request_path.relative_to(root).as_posix(),
        "2026-07-27T12:00:05Z",
        approval_binding_id=preview.approval_binding_id,
        commit=True,
        services=services,
    )

    assert result.status == "error"
    pending_files = list((root / ".runtime/external-agent-evidence/v1/pending").glob("*.json"))
    assert len(pending_files) == 1
    assert list((root / ".runtime/external-agent-evidence/v1/attempts").glob("*/manifest.json")) == []


def test_commit_retries_only_future_snapshot_race_before_dispatch(tmp_path: Path) -> None:
    root, request_path = _project(tmp_path)
    calls = {"status": 0, "exchange": 0}

    def status(*_args, **_kwargs):
        calls["status"] += 1
        if calls["status"] == 2:
            from agent_runtime.result import Finding
            return SimpleNamespace(
                status="blocked", observation_status="invalid", evidence=None,
                findings=(Finding(
                    rule_id="status_observation_from_future", severity="block", action="deny",
                    message="观察时间晚于评估时间。",
                ),),
            )
        return _live_status()

    preview = build_single_work_item_execution_plan(
        root, request_path.relative_to(root).as_posix(), "2026-07-27T12:00:05Z",
        services={"inspect_status": status},
    )
    services = {
        "inspect_status": status,
        "acquire_lease": lambda *_args, **_kwargs: _Lease(status="pass"),
        "record_started": lambda *_args, **_kwargs: SimpleNamespace(
            status="pass", committed=True, attempt_id="attempt-stage88-race-001", findings=[]
        ),
        "exchange": lambda *_args, **_kwargs: (calls.__setitem__("exchange", calls["exchange"] + 1) or _host_success()),
        "scan_text": lambda *_args, **_kwargs: CheckResult(status="pass"),
        "record_terminal": lambda *_args, **_kwargs: SimpleNamespace(status="pass", committed=True, findings=[]),
        "request_already_used": lambda *_args, **_kwargs: False,
    }

    result = execute_single_work_item(
        root, request_path.relative_to(root).as_posix(), "2026-07-27T12:00:05Z",
        approval_binding_id=preview.approval_binding_id, commit=True, services=services,
    )

    assert result.status == "pass"
    assert calls["status"] == 4
    assert calls["exchange"] == 1

def test_python_implementation_digest_is_line_ending_stable(tmp_path: Path) -> None:
    source_dispatcher = (ROOT / "integrations/pi_omp_live_status/controlled_dispatch.cjs").read_bytes().replace(b"\r\n", b"\n")
    source_extension = (ROOT / ".pi/extensions/s-black-live-status.ts").read_bytes().replace(b"\r\n", b"\n")
    digests = []
    for name, newline in (("lf", b"\n"), ("crlf", b"\r\n")):
        root = tmp_path / name
        dispatcher = root / "integrations/pi_omp_live_status/controlled_dispatch.cjs"
        extension = root / ".pi/extensions/s-black-live-status.ts"
        dispatcher.parent.mkdir(parents=True)
        extension.parent.mkdir(parents=True)
        dispatcher.write_bytes(source_dispatcher.replace(b"\n", newline))
        extension.write_bytes(source_extension.replace(b"\n", newline))
        digests.append(_implementation_digest(root, Path(".pi/extensions/s-black-live-status.ts")))
    assert digests[0] == digests[1]
