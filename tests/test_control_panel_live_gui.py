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


def test_live_gui_builds_selected_registered_start_without_operator_identifiers(monkeypatch) -> None:
    from datetime import UTC, datetime
    from agent_runtime import control_panel_live_gui as live_gui
    from agent_runtime.orchestration_control_panel_registered_work import RegisteredWorkCard

    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 7, 28, 7, 45, 12, 345678, tzinfo=UTC)

    monkeypatch.setattr(live_gui, "datetime", FixedDatetime)
    card = RegisteredWorkCard(
        card_id="acceptance-forward",
        title_zh="正向有限验收",
        summary_zh="安全摘要",
        task_id="task-20260703-001",
        collaboration_file="adapters/collaboration-plan.stage92-forward.json",
        goal="只输出一个安全 JSON 结论，不使用工具。",
        topology=("pi-local", "omp-local", "pi-local"),
    )

    assert live_gui.build_registered_start_chain_approval_command(card) == {
        "version": 1,
        "contract": "control-panel-approval/v1",
        "operation": "start_chain",
        "chain_id": "chain-20260728-acceptance-forward-074512345",
        "task_id": "task-20260703-001",
        "collaboration_file": "adapters/collaboration-plan.stage92-forward.json",
        "goal": "只输出一个安全 JSON 结论，不使用工具。",
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


def test_live_gui_row_refresh_preserves_selection_by_stable_first_column() -> None:
    from agent_runtime.control_panel_live_gui import _LiveControlPanelWindow

    class FakeTree:
        def __init__(self) -> None:
            self._rows = {"item-1": ("acceptance-forward", "正向自动验收")}
            self._selected = ("item-1",)
            self._next = 2

        def get_children(self) -> tuple[str, ...]:
            return tuple(self._rows)

        def delete(self, item: str) -> None:
            self._rows.pop(item)
            self._selected = tuple(selected for selected in self._selected if selected != item)

        def insert(self, _parent: str, _index: str, *, values: tuple[str, ...]) -> str:
            item = f"item-{self._next}"
            self._next += 1
            self._rows[item] = values
            return item

        def selection(self) -> tuple[str, ...]:
            return self._selected

        def item(self, item: str, option: str) -> tuple[str, ...]:
            assert option == "values"
            return self._rows[item]

        def selection_set(self, *items: str) -> None:
            self._selected = items

    table = FakeTree()

    _LiveControlPanelWindow._replace_rows(
        table,
        [("acceptance-forward", "正向自动验收"), ("acceptance-reverse", "反向自动验收")],
    )

    assert table.selection()
    assert table.item(table.selection()[0], "values")[0] == "acceptance-forward"


def test_live_gui_commit_worker_returns_result_without_blocking_gui_thread() -> None:
    from threading import Event

    from agent_runtime.control_panel_live_gui import _start_approval_commit_worker

    started = Event()
    release = Event()

    def commit() -> str:
        started.set()
        assert release.wait(timeout=1)
        return "pass"

    outcomes = _start_approval_commit_worker(commit)

    assert started.wait(timeout=1)
    assert outcomes.empty()
    release.set()
    assert outcomes.get(timeout=1) == ("result", "pass")


def test_live_gui_registered_card_preflight_checks_each_unique_host(monkeypatch, tmp_path: Path) -> None:
    from types import SimpleNamespace

    from agent_runtime import control_panel_live_gui as live_gui
    from agent_runtime.orchestration_control_panel_registered_work import RegisteredWorkCard

    seen: list[tuple[Path, str, str]] = []

    def fake_inspect(root: Path, evaluated_at: str, *, profile_id: str):
        seen.append((root, evaluated_at, profile_id))
        return SimpleNamespace(
            status="pass",
            observation_status="observed",
            evidence={"session_state": "open"},
        )

    monkeypatch.setattr(live_gui, "inspect_external_agent_live_status", fake_inspect)
    card = RegisteredWorkCard(
        card_id="acceptance-reverse",
        title_zh="反向有限验收",
        summary_zh="安全摘要",
        task_id="task-20260703-001",
        collaboration_file="adapters/collaboration-plan.stage92-reverse.json",
        goal="只输出一个安全 JSON 结论，不使用工具。",
        topology=("omp-local", "pi-local", "omp-local"),
    )

    assert live_gui.registered_card_preflight_failure(
        tmp_path,
        card,
        evaluated_at="2026-07-28T09:40:00.000Z",
    ) is None
    assert seen == [
        (tmp_path.resolve(), "2026-07-28T09:40:00.000Z", "omp-local"),
        (tmp_path.resolve(), "2026-07-28T09:40:00.000Z", "pi-local"),
    ]


def test_live_gui_registered_card_preflight_fails_before_start_when_handoff_host_is_not_ready(monkeypatch, tmp_path: Path) -> None:
    from types import SimpleNamespace

    from agent_runtime import control_panel_live_gui as live_gui
    from agent_runtime.orchestration_control_panel_registered_work import RegisteredWorkCard

    def fake_inspect(_root: Path, _evaluated_at: str, *, profile_id: str):
        return SimpleNamespace(
            status="pass" if profile_id == "omp-local" else "blocked",
            observation_status="observed" if profile_id == "omp-local" else "stale",
            evidence={"session_state": "open"},
        )

    monkeypatch.setattr(live_gui, "inspect_external_agent_live_status", fake_inspect)
    card = RegisteredWorkCard(
        card_id="acceptance-reverse",
        title_zh="反向有限验收",
        summary_zh="安全摘要",
        task_id="task-20260703-001",
        collaboration_file="adapters/collaboration-plan.stage92-reverse.json",
        goal="只输出一个安全 JSON 结论，不使用工具。",
        topology=("omp-local", "pi-local", "omp-local"),
    )

    assert live_gui.registered_card_preflight_failure(
        tmp_path,
        card,
        evaluated_at="2026-07-28T09:40:00.000Z",
    ) == "Pi 宿主未处于可受控派发的已打开、空闲且证据有效状态；未启动链路。"
