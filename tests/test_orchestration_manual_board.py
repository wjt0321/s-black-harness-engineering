"""Tests for the operator-authored collaboration board fixture."""

from __future__ import annotations

import json
from pathlib import Path

from agent_runtime.orchestration_manual_board import inspect_manual_board

ROOT = Path(__file__).resolve().parents[1]
BOARD = "adapters/manual-collaboration-board.example.json"


def test_manual_board_projects_operator_authored_fixture() -> None:
    payload = inspect_manual_board(ROOT, BOARD).to_dict()
    assert payload["status"] == "pass"
    assert payload["guarantees"]["planning_mode"] == "manual"
    assert payload["guarantees"]["operator_authored"] is True
    assert payload["guarantees"]["executes_agents"] is False
    board = payload["board"]
    assert board["planned_by"] == "operator"
    assert board["board_state"] == "simulated_complete"
    assert [lane["socket_id"] for lane in board["lanes"]] == [
        "kimi-code-acp", "omp-acp", "claude-code-acp"
    ]
    assert all(lane["execution"] == "simulated" for lane in board["lanes"])
    assert all(action["enabled"] is False for action in board["operator_actions"])


def test_manual_board_is_deterministic() -> None:
    first = inspect_manual_board(ROOT, BOARD).to_dict()
    second = inspect_manual_board(ROOT, BOARD).to_dict()
    assert first == second
    assert first["board"]["board_id"].startswith("sha256:")


def _copy_board(tmp_path: Path, mutate) -> tuple[Path, str]:
    root = tmp_path / "project"
    (root / "adapters").mkdir(parents=True)
    for name in (
        "adapter.schema.json",
        "adapters.sample.json",
        "collaboration-plan.example.json",
        "manual-collaboration-board.schema.json",
        "manual-collaboration-board.example.json",
    ):
        (root / "adapters" / name).write_bytes((ROOT / "adapters" / name).read_bytes())
    data = json.loads((root / "adapters" / "manual-collaboration-board.example.json").read_text(encoding="utf-8"))
    mutate(data)
    (root / "adapters" / "board.json").write_text(json.dumps(data), encoding="utf-8")
    return root, "adapters/board.json"


def test_manual_board_rejects_missing_work_item(tmp_path: Path) -> None:
    root, path = _copy_board(tmp_path, lambda data: data["work_item_states"].pop())
    result = inspect_manual_board(root, path)
    assert result.status == "validation_failed"
    assert result.findings[0].rule_id == "manual-board-work-items-mismatch"


def test_manual_board_rejects_duplicate_work_item(tmp_path: Path) -> None:
    root, path = _copy_board(
        tmp_path,
        lambda data: data["work_item_states"].append(dict(data["work_item_states"][0])),
    )
    result = inspect_manual_board(root, path)
    assert result.status == "validation_failed"
    assert result.findings[0].rule_id == "manual-board-work-item-duplicate"


def test_manual_board_rejects_artifact_mismatch(tmp_path: Path) -> None:
    root, path = _copy_board(
        tmp_path,
        lambda data: data["work_item_states"][0].__setitem__("artifact_types", ["patch"]),
    )
    result = inspect_manual_board(root, path)
    assert result.status == "validation_failed"
    assert result.findings[0].rule_id == "manual-board-artifact-mismatch"


def test_manual_board_rejects_review_mismatch(tmp_path: Path) -> None:
    root, path = _copy_board(
        tmp_path,
        lambda data: data["work_item_states"][1].__setitem__("review_state", "not_required"),
    )
    result = inspect_manual_board(root, path)
    assert result.status == "validation_failed"
    assert result.findings[0].rule_id == "manual-board-review-mismatch"


def test_manual_board_rejects_timeline_gap(tmp_path: Path) -> None:
    root, path = _copy_board(
        tmp_path,
        lambda data: data["timeline"][1].__setitem__("sequence", 3),
    )
    result = inspect_manual_board(root, path)
    assert result.status == "validation_failed"
    assert result.findings[0].rule_id == "manual-board-timeline-sequence"


def test_manual_board_rejects_path_escape() -> None:
    result = inspect_manual_board(ROOT, "../board.json")
    assert result.status == "validation_failed"
    assert result.findings[0].rule_id == "manual-board-path-escape"
