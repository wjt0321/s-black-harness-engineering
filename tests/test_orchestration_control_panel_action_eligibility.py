"""Tests for Stage 80 action eligibility Control Panel projection."""

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
ACTION_FILE = "adapters/collaboration-action-eligibility.example.json"


def test_control_panel_projects_operator_action_eligibility() -> None:
    payload = build_control_panel_snapshot(
        ROOT, collaboration_action_file=ACTION_FILE
    ).to_dict()

    assert payload["status"] == "pass"
    assert payload["source"]["collaboration_action_file"] == ACTION_FILE
    section = payload["sections"]["collaboration_actions"]
    assert section["status"] == "pass"
    assert section["scope"] == "file"
    assert section["availability"] == "fixture"
    assert section["summary"]["eligible_count"] == 5
    assert payload["summary"]["eligible_operator_action_count"] == 5
    assert payload["summary"]["blocked_operator_action_count"] == 0


def test_control_panel_action_html_is_chinese_disabled_and_non_executing() -> None:
    payload = build_control_panel_snapshot(
        ROOT, collaboration_action_file=ACTION_FILE
    ).to_dict()
    rendered = render_control_panel_html(payload)

    for expected in (
        'id="collaboration-actions"',
        'href="#collaboration-actions"',
        "协作 / 操作资格",
        "操作者操作资格",
        "操作资格检查点",
        "审批绑定",
        "幂等命令候选",
        "资格不等于执行授权",
        "action_eligible=true",
        "execution_authorized=false",
        "dispatch_eligible=false",
        "execution=not_executed",
    ):
        assert expected in rendered
    assert rendered.count('class="action-eligibility-control" disabled') == 5
    assert "fetch(" not in rendered
    assert "XMLHttpRequest" not in rendered


def test_control_panel_action_handoff_preserves_fixture_path() -> None:
    payload = control_panel.build_control_panel_handoff(
        ROOT, collaboration_action_file=ACTION_FILE
    ).to_dict()

    assert payload["source"]["collaboration_action_file"] == ACTION_FILE
    assert payload["snapshot"]["argv"][-3:] == [
        "--collaboration-action-file", ACTION_FILE, "--json"
    ]
    assert payload["render"]["argv"][-2:] == [
        "--collaboration-action-file", ACTION_FILE
    ]


def test_control_panel_without_action_file_preserves_existing_shape() -> None:
    payload = build_control_panel_snapshot(ROOT).to_dict()
    rendered = render_control_panel_html(payload)

    assert "collaboration_actions" not in payload["sections"]
    assert "collaboration_action_file" not in payload["source"]
    assert 'id="collaboration-actions"' not in rendered


def test_control_panel_action_failure_fails_closed() -> None:
    payload = build_control_panel_snapshot(
        ROOT, collaboration_action_file="adapters/missing-actions.json"
    ).to_dict()
    rendered = render_control_panel_html(payload)

    assert payload["status"] == "validation_failed"
    assert payload["sections"]["collaboration_actions"]["status"] == "validation_failed"
    assert "collaboration-action-eligibility-unavailable" in rendered
    assert "操作资格检查点" not in rendered


def test_cli_control_panel_commands_accept_collaboration_action_file(capsys) -> None:
    snapshot_args = [
        "orchestration", "control-panel", "snapshot",
        "--collaboration-action-file", ACTION_FILE, "--json",
    ]
    first_code = main(snapshot_args)
    first = capsys.readouterr()
    second_code = main(snapshot_args)
    second = capsys.readouterr()
    assert first_code == second_code == 0
    assert first.out == second.out
    assert first.err == second.err == ""
    assert json.loads(first.out)["sections"]["collaboration_actions"]["status"] == "pass"

    render_code = main([
        "orchestration", "control-panel", "render",
        "--collaboration-action-file", ACTION_FILE,
    ])
    rendered = capsys.readouterr()
    assert render_code == 0
    assert 'id="collaboration-actions"' in rendered.out
    assert rendered.err == ""

    handoff_code = main([
        "orchestration", "control-panel", "handoff",
        "--collaboration-action-file", ACTION_FILE, "--json",
    ])
    handoff = capsys.readouterr()
    assert handoff_code == 0
    assert json.loads(handoff.out)["source"]["collaboration_action_file"] == ACTION_FILE
    assert handoff.err == ""
