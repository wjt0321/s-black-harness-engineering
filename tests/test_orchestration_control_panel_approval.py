from __future__ import annotations

from pathlib import Path

from agent_runtime.orchestration_external_agent_chain import ExternalAgentChainResult


def _start_command() -> dict[str, object]:
    return {
        "version": 1,
        "contract": "control-panel-approval/v1",
        "operation": "start_chain",
        "chain_id": "chain-stage91-001",
        "task_id": "task-stage91",
        "collaboration_file": "adapters/stage91-plan.json",
        "goal": "生成一个有界结论。",
    }


def test_control_panel_start_uses_strict_command_and_existing_one_time_binding(monkeypatch, tmp_path: Path) -> None:
    from agent_runtime import orchestration_control_panel_approval as approval

    calls: list[dict[str, object]] = []

    def preview(root: Path, **kwargs: object) -> ExternalAgentChainResult:
        calls.append({"kind": "preview", "root": root, **kwargs})
        return ExternalAgentChainResult(
            "needs_approval",
            "chain-stage91-001",
            approval_binding_id="sha256:" + "a" * 64,
            plan={"operation": "external-agent-chain.start"},
        )

    def execute(root: Path, **kwargs: object) -> ExternalAgentChainResult:
        calls.append({"kind": "commit", "root": root, **kwargs})
        return ExternalAgentChainResult("pass", "chain-stage91-001")

    monkeypatch.setattr(approval, "preview_chain_start", preview)
    monkeypatch.setattr(approval, "execute_chain_start", execute)
    command = _start_command()

    preview_result = approval.preview_control_panel_approval(
        tmp_path, command=command, evaluated_at="2026-07-28T12:00:00Z"
    )
    commit_result = approval.commit_control_panel_approval(
        tmp_path,
        command=command,
        approval_binding_id="sha256:" + "a" * 64,
        evaluated_at="2026-07-28T12:00:10Z",
    )

    assert preview_result.status == "needs_approval"
    assert commit_result.status == "pass"
    assert calls == [
        {
            "kind": "preview",
            "root": tmp_path.resolve(),
            "chain_id": "chain-stage91-001",
            "task_id": "task-stage91",
            "collaboration_file": "adapters/stage91-plan.json",
            "goal": "生成一个有界结论。",
            "evaluated_at": "2026-07-28T12:00:00Z",
        },
        {
            "kind": "commit",
            "root": tmp_path.resolve(),
            "chain_id": "chain-stage91-001",
            "task_id": "task-stage91",
            "collaboration_file": "adapters/stage91-plan.json",
            "goal": "生成一个有界结论。",
            "evaluated_at": "2026-07-28T12:00:10Z",
            "approval_binding_id": "sha256:" + "a" * 64,
            "commit": True,
        },
    ]


def test_control_panel_approval_rejects_unknown_or_incomplete_commands_without_calling_chain(monkeypatch, tmp_path: Path) -> None:
    from agent_runtime import orchestration_control_panel_approval as approval

    called = False

    def unexpected(*_args, **_kwargs):
        nonlocal called
        called = True
        raise AssertionError("chain operation must not be called")

    monkeypatch.setattr(approval, "preview_chain_start", unexpected)
    command = {**_start_command(), "unsafe": "argv override"}

    result = approval.preview_control_panel_approval(
        tmp_path, command=command, evaluated_at="2026-07-28T12:00:00Z"
    )

    assert result.status == "validation_failed"
    assert result.findings[0].rule_id == "control-panel-approval-command-invalid"
    assert called is False

def test_control_panel_final_decision_reuses_existing_one_time_review_binding(monkeypatch, tmp_path: Path) -> None:
    from agent_runtime import orchestration_control_panel_approval as approval

    calls: list[dict[str, object]] = []
    command = {
        "version": 1,
        "contract": "control-panel-approval/v1",
        "operation": "final_decision",
        "chain_id": "chain-stage91-001",
        "decision": "request_changes",
        "comment": "请根据审阅建议修改。",
    }

    def preview(root: Path, **kwargs: object) -> ExternalAgentChainResult:
        calls.append({"kind": "preview", "root": root, **kwargs})
        return ExternalAgentChainResult(
            "needs_approval",
            "chain-stage91-001",
            approval_binding_id="sha256:" + "b" * 64,
            plan={"operation": "external-agent-chain.final-human-decision"},
        )

    def commit(root: Path, **kwargs: object) -> ExternalAgentChainResult:
        calls.append({"kind": "commit", "root": root, **kwargs})
        return ExternalAgentChainResult("changes_requested", "chain-stage91-001")

    monkeypatch.setattr(approval, "preview_chain_final_decision", preview)
    monkeypatch.setattr(approval, "commit_chain_final_decision", commit)

    preview_result = approval.preview_control_panel_approval(
        tmp_path, command=command, evaluated_at="2026-07-28T12:05:00Z"
    )
    commit_result = approval.commit_control_panel_approval(
        tmp_path,
        command=command,
        approval_binding_id="sha256:" + "b" * 64,
        evaluated_at="2026-07-28T12:05:10Z",
    )

    assert preview_result.status == "needs_approval"
    assert commit_result.status == "changes_requested"
    assert calls == [
        {
            "kind": "preview",
            "root": tmp_path.resolve(),
            "chain_id": "chain-stage91-001",
            "decision": "request_changes",
            "comment": "请根据审阅建议修改。",
            "evaluated_at": "2026-07-28T12:05:00Z",
        },
        {
            "kind": "commit",
            "root": tmp_path.resolve(),
            "chain_id": "chain-stage91-001",
            "decision": "request_changes",
            "comment": "请根据审阅建议修改。",
            "evaluated_at": "2026-07-28T12:05:10Z",
            "approval_binding_id": "sha256:" + "b" * 64,
            "commit": True,
        },
    ]



def test_control_panel_approval_rejects_malformed_final_command_without_calling_chain(monkeypatch, tmp_path: Path) -> None:
    from agent_runtime import orchestration_control_panel_approval as approval

    calls: list[str] = []

    def unexpected(*_args, **_kwargs):
        calls.append("called")
        raise AssertionError("chain operation must not be called")

    monkeypatch.setattr(approval, "preview_chain_start", unexpected)
    monkeypatch.setattr(approval, "execute_chain_start", unexpected)
    monkeypatch.setattr(approval, "preview_chain_final_decision", unexpected)
    monkeypatch.setattr(approval, "commit_chain_final_decision", unexpected)
    command = {
        "version": 1,
        "contract": "control-panel-approval/v1",
        "operation": "final_decision",
        "chain_id": "chain-stage91-001",
        "decision": ["approve"],
        "comment": "not used",
    }

    preview = approval.preview_control_panel_approval(
        tmp_path, command=command, evaluated_at="2026-07-28T12:10:00Z"
    )
    commit = approval.commit_control_panel_approval(
        tmp_path,
        command=command,
        approval_binding_id="sha256:" + "c" * 64,
        evaluated_at="2026-07-28T12:10:10Z",
    )

    assert preview.status == "validation_failed"
    assert commit.status == "validation_failed"
    assert preview.chain_id == "chain-stage91-001"
    assert commit.chain_id == "chain-stage91-001"
    assert calls == []


def test_control_panel_approval_does_not_surface_non_string_chain_id(monkeypatch, tmp_path: Path) -> None:
    from agent_runtime import orchestration_control_panel_approval as approval

    def unexpected(*_args, **_kwargs):
        raise AssertionError("chain operation must not be called")

    monkeypatch.setattr(approval, "preview_chain_final_decision", unexpected)
    command = {
        "version": 1,
        "contract": "control-panel-approval/v1",
        "operation": "final_decision",
        "chain_id": 101,
        "decision": "approve",
        "comment": "not used",
    }

    result = approval.preview_control_panel_approval(
        tmp_path, command=command, evaluated_at="2026-07-28T12:12:00Z"
    )

    assert result.status == "validation_failed"
    assert result.chain_id == ""


def test_gui_confirmation_time_keeps_millisecond_precision(monkeypatch) -> None:
    from datetime import UTC, datetime
    from agent_runtime import control_panel_live_gui as live_gui

    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 7, 28, 7, 31, 43, 987654, tzinfo=UTC)

    monkeypatch.setattr(live_gui, "datetime", FixedDatetime)

    assert live_gui._current_utc_evaluated_at() == "2026-07-28T07:31:43.987Z"


def test_chain_role_time_keeps_millisecond_precision(monkeypatch) -> None:
    from datetime import datetime, timezone
    from agent_runtime import orchestration_external_agent_chain as chain

    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 7, 28, 7, 31, 43, 987654, tzinfo=timezone.utc)

    monkeypatch.setattr(chain, "datetime", FixedDatetime)

    assert chain._current_utc_evaluated_at() == "2026-07-28T07:31:43.987Z"



def test_control_panel_abandon_uses_the_single_fixed_pending_final_decision_envelope(monkeypatch, tmp_path: Path) -> None:
    from agent_runtime import orchestration_control_panel_approval as approval
    from agent_runtime.orchestration_external_agent_chain import ExternalAgentChainResult

    command = {
        "version": 1,
        "contract": "control-panel-approval/v1",
        "operation": "abandon_final_decision",
        "chain_id": "chain-stage93-001",
    }
    calls: list[tuple[str, object]] = []

    def preview(root: Path, *, chain_id: str):
        calls.append(("preview", (root, chain_id)))
        return ExternalAgentChainResult(
            "needs_approval",
            chain_id,
            approval_binding_id="sha256:" + "a" * 64,
            plan={"operation": "external-agent-chain.abandon-final-decision"},
        )

    def commit(root: Path, *, chain_id: str, approval_binding_id: str | None, commit: bool):
        calls.append(("commit", (root, chain_id, approval_binding_id, commit)))
        return ExternalAgentChainResult("pass", chain_id)

    monkeypatch.setattr(approval, "preview_abandon_chain_final_decision", preview)
    monkeypatch.setattr(approval, "abandon_chain_final_decision", commit)

    previewed = approval.preview_control_panel_approval(
        tmp_path,
        command=command,
        evaluated_at="2026-07-28T12:04:00.000Z",
    )
    committed = approval.commit_control_panel_approval(
        tmp_path,
        command=command,
        approval_binding_id="sha256:" + "a" * 64,
        evaluated_at="2026-07-28T12:04:01.000Z",
    )

    assert previewed.status == "needs_approval"
    assert committed.status == "pass"
    assert calls == [
        ("preview", (tmp_path.resolve(), "chain-stage93-001")),
        ("commit", (tmp_path.resolve(), "chain-stage93-001", "sha256:" + "a" * 64, True)),
    ]
