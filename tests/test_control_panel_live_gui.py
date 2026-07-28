from __future__ import annotations

from pathlib import Path


def test_live_panel_builds_fresh_read_only_snapshot_with_bounded_chain_collection(monkeypatch, tmp_path: Path) -> None:
    from agent_runtime import control_panel_live_gui as live_gui

    calls: list[dict[str, object]] = []

    class Snapshot:
        status = "pass"

        def to_dict(self):
            return {"status": "pass", "sections": {}, "source": {}, "summary": {}}

        def exit_code(self) -> int:
            return 0

    def fake_snapshot(root: Path, **kwargs: object) -> Snapshot:
        calls.append({"root": root, **kwargs})
        return Snapshot()

    monkeypatch.setattr(live_gui, "build_control_panel_snapshot", fake_snapshot)

    result = live_gui.build_live_control_panel_snapshot(
        tmp_path,
        evaluated_at="2026-07-28T12:00:05Z",
        chain_limit=12,
    )

    assert result.to_dict()["status"] == "pass"
    assert calls == [
        {
            "root": tmp_path.resolve(),
            "external_agent_evaluated_at": "2026-07-28T12:00:05Z",
            "external_agent_chain_limit": 12,
        }
    ]


def test_live_panel_rejects_out_of_bound_refresh_and_chain_limits() -> None:
    from agent_runtime.control_panel_live_gui import LiveControlPanelError, validate_live_control_panel_options

    assert validate_live_control_panel_options(refresh_seconds=5, chain_limit=20) == (5, 20)
    for refresh_seconds, chain_limit in ((1, 20), (61, 20), (5, 0), (5, 21)):
        try:
            validate_live_control_panel_options(
                refresh_seconds=refresh_seconds,
                chain_limit=chain_limit,
            )
        except LiveControlPanelError:
            continue
        raise AssertionError("invalid live panel options must fail closed")

def test_live_gui_builds_only_fixed_stage89_approval_command_shapes() -> None:
    from agent_runtime.control_panel_live_gui import (
        build_final_decision_approval_command,
        build_start_chain_approval_command,
    )

    assert build_start_chain_approval_command(
        chain_id="chain-stage91-001",
        task_id="task-stage91",
        collaboration_file="adapters/stage91-plan.json",
        goal="生成一个有界结论。",
    ) == {
        "version": 1,
        "contract": "control-panel-approval/v1",
        "operation": "start_chain",
        "chain_id": "chain-stage91-001",
        "task_id": "task-stage91",
        "collaboration_file": "adapters/stage91-plan.json",
        "goal": "生成一个有界结论。",
    }
    assert build_final_decision_approval_command(
        chain_id="chain-stage91-001",
        decision="approve",
        comment="证据已由操作者核对。",
    ) == {
        "version": 1,
        "contract": "control-panel-approval/v1",
        "operation": "final_decision",
        "chain_id": "chain-stage91-001",
        "decision": "approve",
        "comment": "证据已由操作者核对。",
    }

def test_live_gui_confirmation_summary_shows_only_bound_safe_fields() -> None:
    from agent_runtime.control_panel_live_gui import format_approval_confirmation
    from agent_runtime.orchestration_external_agent_chain import ExternalAgentChainResult

    result = ExternalAgentChainResult(
        "needs_approval",
        "chain-stage91-001",
        plan_hash="sha256:" + "a" * 64,
        approval_binding_id="sha256:" + "b" * 64,
        plan={
            "operation": "external-agent-chain.start",
            "goal_digest": "sha256:" + "c" * 64,
            "roles": {"planner": {"profile": "pi-local"}},
            "intent_template": {"goal": "绝不能显示的原始目标"},
        },
    )

    summary = format_approval_confirmation(result)

    assert "external-agent-chain.start" in summary
    assert "chain-stage91-001" in summary
    assert "sha256:" + "a" * 64 in summary
    assert "sha256:" + "b" * 64 in summary
    assert "绝不能显示的原始目标" not in summary


def test_live_gui_builds_registered_start_without_operator_identifiers(monkeypatch) -> None:
    from datetime import UTC, datetime
    from agent_runtime import control_panel_live_gui as live_gui

    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 7, 28, 7, 45, 12, 345678, tzinfo=UTC)

    monkeypatch.setattr(live_gui, "datetime", FixedDatetime)

    assert live_gui.build_registered_start_chain_approval_command() == {
        "version": 1,
        "contract": "control-panel-approval/v1",
        "operation": "start_chain",
        "chain_id": "chain-20260728-gui-forward-074512345",
        "task_id": "task-20260703-001",
        "collaboration_file": "adapters/collaboration-plan.stage91-gui-acceptance.json",
        "goal": "请仅输出一个 JSON 对象，字段 summary 为不超过 80 个中文字符的阶段91 GUI 自动串行验收结论；不要执行命令、不要使用工具。",
    }


def test_live_gui_auto_routes_only_a_single_pending_final_decision() -> None:
    from agent_runtime.control_panel_live_gui import pending_final_decision_chain_id

    assert pending_final_decision_chain_id({
        "sections": {
            "external_agent_chains": {
                "chains": [
                    {"chain_id": "chain-complete", "status": "approved"},
                    {"chain_id": "chain-final", "status": "awaiting_final_human_decision"},
                ]
            }
        }
    }) == "chain-final"
    assert pending_final_decision_chain_id({
        "sections": {
            "external_agent_chains": {
                "chains": [
                    {"chain_id": "chain-first", "status": "awaiting_final_human_decision"},
                    {"chain_id": "chain-second", "status": "awaiting_final_human_decision"},
                ]
            }
        }
    }) is None
