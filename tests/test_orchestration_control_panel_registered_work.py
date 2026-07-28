from __future__ import annotations

import json
from pathlib import Path


def _write_inbox(root: Path, cards: list[dict[str, object]]) -> None:
    adapters = root / "adapters"
    adapters.mkdir()
    (adapters / "control-panel-registered-work-inbox.json").write_text(
        json.dumps(
            {
                "version": 1,
                "contract": "control-panel-registered-work-inbox/v1",
                "cards": cards,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def _card(card_id: str = "acceptance-forward") -> dict[str, object]:
    return {
        "card_id": card_id,
        "title_zh": "正向有限验收",
        "summary_zh": "Pi 规划、OMP 执行、Pi 审阅；最终由操作者决定。",
        "task_id": "task-20260703-001",
        "collaboration_file": "adapters/collaboration-plan.stage92-forward.json",
        "goal": "只输出一个安全 JSON 结论，不使用工具。",
        "topology": ["pi-local", "omp-local", "pi-local"],
    }


def test_registered_work_inbox_reads_only_fixed_cards(tmp_path: Path) -> None:
    from agent_runtime.orchestration_control_panel_registered_work import load_registered_work_inbox

    _write_inbox(tmp_path, [_card(), _card("acceptance-reverse")])

    result = load_registered_work_inbox(tmp_path)

    assert result.status == "pass"
    assert [card.card_id for card in result.cards] == ["acceptance-forward", "acceptance-reverse"]
    assert result.cards[0].task_id == "task-20260703-001"
    assert result.cards[0].goal not in result.to_safe_dict()["cards"][0].values()


def test_registered_work_inbox_fails_closed_for_unsafe_or_unknown_card_fields(tmp_path: Path) -> None:
    from agent_runtime.orchestration_control_panel_registered_work import load_registered_work_inbox

    unsafe = _card()
    unsafe["collaboration_file"] = "../outside.json"
    unsafe["argv"] = "--unsafe"
    _write_inbox(tmp_path, [unsafe])

    result = load_registered_work_inbox(tmp_path)

    assert result.status == "validation_failed"
    assert result.cards == ()
    assert result.findings[0].rule_id == "control-panel-registered-work-invalid"


def test_project_registered_cards_bind_valid_collaboration_plans() -> None:
    from agent_runtime.orchestration_collaboration import inspect_collaboration_plan
    from agent_runtime.orchestration_control_panel_registered_work import load_registered_work_inbox

    root = Path(__file__).resolve().parents[1]
    inbox = load_registered_work_inbox(root)

    assert inbox.status == "pass"
    assert {card.card_id for card in inbox.cards} == {"acceptance-forward", "acceptance-reverse"}
    for card in inbox.cards:
        plan = inspect_collaboration_plan(root, card.collaboration_file)
        assert plan.status == "pass"
        assert plan.plan is not None
        assert plan.plan["parent_task_ref"] == card.task_id
