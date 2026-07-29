from __future__ import annotations

from pathlib import Path


def test_agent_deck_snapshot_projects_live_members_and_pending_members(
    monkeypatch, tmp_path: Path
) -> None:
    from agent_runtime import agent_deck_projection as projection

    class FakePanel:
        status = "pass"

        def to_dict(self):
            return {
                "status": "pass",
                "snapshot_id": "sha256:" + "a" * 64,
                "sections": {
                    "external_agents": {
                        "status": "pass",
                        "evaluated_at": "2026-07-29T09:00:00Z",
                        "agents": [
                            {
                                "agent_id": "pi-local",
                                "display_name_zh": "Pi",
                                "status": "idle",
                                "status_label_zh": "空闲",
                                "readiness": {"status": "ready", "safe_summary_zh": "Pi 已就绪。"},
                                "safe_summary_zh": "Pi 已就绪。",
                            },
                            {
                                "agent_id": "omp-local",
                                "display_name_zh": "OMP",
                                "status": "busy",
                                "status_label_zh": "执行中",
                                "readiness": {"status": "ready", "safe_summary_zh": "OMP 正在处理工作项。"},
                                "safe_summary_zh": "OMP 正在处理工作项。",
                            },
                        ],
                    },
                    "external_agent_chains": {"chains": []},
                },
                "guarantees": {"read_only": True, "accesses_network": False},
            }

    class Inbox:
        def to_safe_dict(self):
            return {"status": "pass", "cards": []}

    monkeypatch.setattr(projection, "build_live_control_panel_snapshot", lambda *_args, **_kwargs: FakePanel())
    monkeypatch.setattr(projection, "load_registered_work_inbox", lambda *_args, **_kwargs: Inbox())

    result = projection.build_agent_deck_snapshot(tmp_path, evaluated_at="2026-07-29T09:00:00Z").to_dict()

    assert result["schema_version"] == "agent-deck/read-model/v1"
    assert result["source_mode"] == "runtime"
    assert [agent["id"] for agent in result["agents"]] == ["pi-local", "omp-local", "codex-cli", "claude-code", "kimi-code"]
    assert result["agents"][0]["integration_status"] == "live"
    assert result["agents"][1]["status"] == "busy"
    assert result["agents"][2] == {
        "id": "codex-cli",
        "name_zh": "Codex CLI",
        "role_zh": "待接入成员",
        "integration_status": "not_integrated",
        "status": "unknown",
        "status_label_zh": "待接入",
        "safe_summary_zh": "尚未接入真实状态或执行能力。",
    }
    assert result["guarantees"]["read_only"] is True
    assert "raw_prompt" not in str(result)


def test_agent_deck_snapshot_fails_closed_for_invalid_limit(monkeypatch, tmp_path: Path) -> None:
    from agent_runtime import agent_deck_projection as projection

    result = projection.build_agent_deck_snapshot(tmp_path, evaluated_at="2026-07-29T09:00:00Z", chain_limit=21)
    assert result.status == "validation_failed"
    assert result.to_dict()["findings"][0]["rule_id"] == "agent-deck-chain-limit-invalid"


def test_agent_deck_snapshot_marks_missing_live_member_unavailable(monkeypatch, tmp_path: Path) -> None:
    from agent_runtime import agent_deck_projection as projection

    class FakePanel:
        status = "pass"
        def to_dict(self):
            return {"status": "pass", "snapshot_id": "sha256:" + "b" * 64, "sections": {"external_agents": {"agents": []}, "external_agent_chains": {"chains": []}}, "guarantees": {"read_only": True, "accesses_network": False}}

    class Inbox:
        def to_safe_dict(self): return {"status": "pass", "cards": []}

    monkeypatch.setattr(projection, "build_live_control_panel_snapshot", lambda *_args, **_kwargs: FakePanel())
    monkeypatch.setattr(projection, "load_registered_work_inbox", lambda *_args, **_kwargs: Inbox())
    agents = projection.build_agent_deck_snapshot(tmp_path, evaluated_at="2026-07-29T09:00:00Z").to_dict()["agents"]
    assert agents[0]["status"] == "unavailable"
    assert agents[0]["status_label_zh"] == "不可用"

def test_agent_deck_snapshot_projects_a_bounded_safe_task_queue(monkeypatch, tmp_path: Path) -> None:
    from agent_runtime import agent_deck_projection as projection

    class FakePanel:
        status = "pass"

        def to_dict(self):
            return {
                "status": "pass",
                "snapshot_id": "sha256:" + "c" * 64,
                "sections": {
                    "external_agents": {"agents": []},
                    "external_agent_chains": {"chains": []},
                },
                "guarantees": {"read_only": True, "accesses_network": False},
            }

    class Inbox:
        def to_safe_dict(self):
            return {"status": "pass", "cards": []}

    tasks = [
        {
            "id": "task-20260729-001",
            "title": "实现任务工作区",
            "status": "in_progress",
            "assignee": "orchestrator",
            "updated_at": "2026-07-29T11:30:00Z",
            "summary": "must not project",
            "artifacts": ["must-not-project.py"],
            "evidence": [{"description": "must not project"}],
        },
        {
            "id": "task-20260729-002",
            "title": "sensitive-title",
            "status": "finished",
            "assignee": "",
            "updated_at": "2026-07-29T11:31:00Z",
        },
    ] + [
        {
            "id": f"task-20260728-{index:03d}",
            "title": f"历史任务 {index}",
            "status": "finished",
            "assignee": "orchestrator",
            "updated_at": "2026-07-28T11:00:00Z",
        }
        for index in range(3, 16)
    ]
    monkeypatch.setattr(projection, "build_live_control_panel_snapshot", lambda *_args, **_kwargs: FakePanel())
    class ScanResult:
        def __init__(self, status: str):
            self.status = status

    monkeypatch.setattr(projection, "load_registered_work_inbox", lambda *_args, **_kwargs: Inbox())
    monkeypatch.setattr(projection, "load_tasks", lambda *_args, **_kwargs: tasks)
    monkeypatch.setattr(projection, "check_text", lambda _root, value: ScanResult("blocked" if value.startswith("sensitive-") else "pass"))

    payload = projection.build_agent_deck_snapshot(tmp_path, evaluated_at="2026-07-29T12:00:00Z").to_dict()

    assert len(payload["task_queue"]) == 12
    assert payload["task_queue"][0]["title_zh"] == "任务内容已隐藏"
    assert next(item for item in payload["task_queue"] if item["task_id"] == "task-20260729-001") == {
        "task_id": "task-20260729-001",
        "title_zh": "实现任务工作区",
        "status": "in_progress",
        "status_label_zh": "进行中",
        "assignee_label_zh": "已分配",
        "updated_at": "2026-07-29T11:30:00Z",
    }
    assert "must not project" not in str(payload)
    assert "must-not-project.py" not in str(payload)
