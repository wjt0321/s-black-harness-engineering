from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from agent_runtime.agent_deck_mission_intake import submit_agent_deck_mission


NOW = datetime(2026, 7, 29, 12, 0, 0, tzinfo=timezone.utc)
REPO_ROOT = Path(__file__).resolve().parents[1]


def _prepare_root(tmp_path: Path) -> Path:
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    shutil.copy(REPO_ROOT / "tasks" / "task.schema.json", tasks / "task.schema.json")
    shutil.copy(REPO_ROOT / "tasks" / "event.schema.json", tasks / "event.schema.json")
    return tasks


def test_dry_run_builds_a_safe_formal_mission_without_writing(tmp_path: Path) -> None:
    _prepare_root(tmp_path)
    result = submit_agent_deck_mission(tmp_path, goal="为 Agent Deck 增加正式任务登记入口", dry_run=True, commit=False, now=NOW)
    assert result.status == "pass"
    assert result.task_id == "task-20260729-001"
    assert result.to_dict()["phase_label_zh"] == "待登记"
    assert result.to_dict()["goal_present"] is True
    assert not (tmp_path / "tasks" / "tasks.jsonl").exists()
    assert not (tmp_path / "tasks" / "events.jsonl").exists()


def test_commit_creates_one_task_and_one_created_event_with_no_user_supplied_identity(tmp_path: Path) -> None:
    _prepare_root(tmp_path)
    result = submit_agent_deck_mission(tmp_path, goal="为 Agent Deck 增加正式任务登记入口", dry_run=False, commit=True, now=NOW)
    assert result.status == "pass"
    assert result.task_id == "task-20260729-001"
    assert result.event_id is not None
    assert result.event_id.startswith("evt-20260729-")
    assert result.to_dict()["phase_label_zh"] == "等待主控 Agent 规划"
    task = json.loads((tmp_path / "tasks" / "tasks.jsonl").read_text(encoding="utf-8"))
    event = json.loads((tmp_path / "tasks" / "events.jsonl").read_text(encoding="utf-8"))
    assert task["id"] == result.task_id
    assert task["source"] == "agent-deck"
    assert task["created_by"] == "agent-deck-user"
    assert task["status"] == "planned"
    assert task["current_step"] == "等待主控 Agent 规划"
    assert event["task_id"] == result.task_id
    assert event["event_type"] == "created"


def test_intake_fails_closed_when_goal_cannot_be_scanned(monkeypatch, tmp_path: Path) -> None:
    from agent_runtime import agent_deck_mission_intake as intake

    class ScanResult:
        status = "blocked"

    monkeypatch.setattr(intake, "check_text", lambda *_args: ScanResult())
    result = intake.submit_agent_deck_mission(tmp_path, goal="不应进入账本的敏感目标", dry_run=True, commit=False, now=NOW)
    assert result.status == "blocked"
    assert result.findings[0].rule_id == "agent-deck-mission-goal-secret-scan"
    assert "敏感目标" not in json.dumps(result.to_dict(), ensure_ascii=False)


def test_intake_uses_next_daily_sequence_from_existing_tasks(tmp_path: Path) -> None:
    tasks = _prepare_root(tmp_path)
    (tasks / "tasks.jsonl").write_text(json.dumps({"id": "task-20260729-007", "title": "已有任务", "status": "planned", "created_at": "2026-07-29T08:00:00Z", "updated_at": "2026-07-29T08:00:00Z", "created_by": "test", "source": "test"}, ensure_ascii=False) + "\n", encoding="utf-8")
    result = submit_agent_deck_mission(tmp_path, goal="继续处理新的正式任务", dry_run=True, commit=False, now=NOW)
    assert result.status == "pass"
    assert result.task_id == "task-20260729-008"
