"""Tests for the Stage 79 collaboration run state Control Panel projection."""

from __future__ import annotations

import json
from pathlib import Path

from agent_runtime import orchestration_control_panel as control_panel
from agent_runtime.cli import main
from agent_runtime.orchestration_control_panel import (
    build_control_panel_snapshot,
    render_control_panel_html,
)

ROOT = Path(__file__).resolve().parents[1]
RUN_FILE = "adapters/collaboration-run-state.example.json"


def _fixture_data() -> dict:
    return json.loads((ROOT / RUN_FILE).read_text(encoding="utf-8"))


def _project_root(tmp_path: Path, data: dict) -> Path:
    root = tmp_path / "project"
    adapters = root / "adapters"
    adapters.mkdir(parents=True)
    for name in (
        "adapters.sample.json",
        "adapter.schema.json",
        "collaboration-plan.example.json",
        "collaboration-run-state.schema.json",
    ):
        (adapters / name).write_bytes((ROOT / "adapters" / name).read_bytes())
    (adapters / "run.json").write_text(json.dumps(data), encoding="utf-8")
    return root


def test_control_panel_projects_collaboration_run_state() -> None:
    payload = build_control_panel_snapshot(
        ROOT, collaboration_run_file=RUN_FILE
    ).to_dict()

    assert payload["status"] == "pass"
    assert payload["source"]["collaboration_run_file"] == RUN_FILE
    section = payload["sections"]["collaboration_run"]
    assert section["status"] == "pass"
    assert section["scope"] == "file"
    assert section["availability"] == "fixture"
    assert section["run"]["status"] == "completed"
    assert section["run"]["summary"]["retry_count"] == 1
    assert payload["summary"]["collaboration_run_status"] == "completed"


def test_control_panel_run_state_html_is_chinese_read_only_and_non_executing() -> None:
    payload = build_control_panel_snapshot(
        ROOT, collaboration_run_file=RUN_FILE
    ).to_dict()
    rendered = render_control_panel_html(payload)

    for expected in (
        'id="collaboration-run"',
        'href="#collaboration-run"',
        "协作 / 运行状态",
        "模拟协作运行",
        "工作项尝试历史",
        "当前尝试",
        "审阅决定",
        "交接状态",
        "产物回收",
        "运行事件时间线",
        "阻塞恢复次数",
        "changes_requested",
        "superseded",
        "dispatch_eligible=false",
        "execution=not_executed",
        "仅模拟 · 无执行权限",
    ):
        assert expected in rendered
    assert rendered.count('class="run-action" disabled') == 5
    assert "fetch(" not in rendered
    assert "XMLHttpRequest" not in rendered


def test_control_panel_handoff_preserves_collaboration_run_file() -> None:
    payload = control_panel.build_control_panel_handoff(
        ROOT, collaboration_run_file=RUN_FILE
    ).to_dict()

    assert payload["source"]["collaboration_run_file"] == RUN_FILE
    assert payload["snapshot"]["argv"][-3:] == [
        "--collaboration-run-file", RUN_FILE, "--json"
    ]
    assert payload["render"]["argv"][-2:] == [
        "--collaboration-run-file", RUN_FILE
    ]


def test_control_panel_without_run_file_preserves_existing_shape() -> None:
    payload = build_control_panel_snapshot(ROOT).to_dict()
    rendered = render_control_panel_html(payload)

    assert "collaboration_run" not in payload["sections"]
    assert "collaboration_run_file" not in payload["source"]
    assert 'id="collaboration-run"' not in rendered


def test_control_panel_run_state_failure_fails_closed() -> None:
    payload = build_control_panel_snapshot(
        ROOT, collaboration_run_file="adapters/missing-run.json"
    ).to_dict()
    rendered = render_control_panel_html(payload)

    assert payload["status"] == "validation_failed"
    assert payload["sections"]["collaboration_run"]["status"] == "validation_failed"
    assert "collaboration-run-state-unavailable" in rendered
    assert "运行事件时间线" not in rendered


def test_control_panel_run_state_escapes_fixture_labels(tmp_path: Path) -> None:
    data = _fixture_data()
    data["events"][0]["label"] = '<script>alert("run")</script>'
    root = _project_root(tmp_path, data)
    payload = build_control_panel_snapshot(
        root, collaboration_run_file="adapters/run.json"
    ).to_dict()

    rendered = render_control_panel_html(payload)

    assert '<script>alert("run")</script>' not in rendered
    assert "&lt;script&gt;alert" in rendered


def test_cli_control_panel_commands_accept_collaboration_run_file(capsys) -> None:
    snapshot_args = [
        "orchestration", "control-panel", "snapshot",
        "--collaboration-run-file", RUN_FILE, "--json",
    ]
    first_code = main(snapshot_args)
    first = capsys.readouterr()
    second_code = main(snapshot_args)
    second = capsys.readouterr()
    assert first_code == second_code == 0
    assert first.out == second.out
    assert first.err == second.err == ""
    assert json.loads(first.out)["sections"]["collaboration_run"]["status"] == "pass"

    render_code = main([
        "orchestration", "control-panel", "render",
        "--collaboration-run-file", RUN_FILE,
    ])
    rendered = capsys.readouterr()
    assert render_code == 0
    assert 'id="collaboration-run"' in rendered.out
    assert rendered.err == ""

    handoff_code = main([
        "orchestration", "control-panel", "handoff",
        "--collaboration-run-file", RUN_FILE, "--json",
    ])
    handoff = capsys.readouterr()
    assert handoff_code == 0
    assert json.loads(handoff.out)["source"]["collaboration_run_file"] == RUN_FILE
    assert handoff.err == ""
