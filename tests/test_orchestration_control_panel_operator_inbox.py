"""Tests for Stage 81 current operator inbox Control Panel projection."""

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
INBOX_FILE = "adapters/collaboration-operator-inbox.example.json"


def test_control_panel_projects_current_operator_inbox() -> None:
    payload = build_control_panel_snapshot(
        ROOT, collaboration_inbox_file=INBOX_FILE
    ).to_dict()

    assert payload["status"] == "pass"
    assert payload["source"]["collaboration_inbox_file"] == INBOX_FILE
    section = payload["sections"]["collaboration_inbox"]
    assert section["status"] == "pass"
    assert section["scope"] == "file"
    assert section["availability"] == "fixture"
    assert section["current_run"]["status"] == "blocked"
    assert section["summary"]["pending_approval_count"] == 1
    assert section["summary"]["eligible_count"] == 1
    assert payload["summary"]["current_inbox_pending_approval_count"] == 1
    assert payload["summary"]["current_inbox_eligible_count"] == 1


def test_control_panel_current_inbox_html_is_chinese_disabled_and_non_executing() -> None:
    payload = build_control_panel_snapshot(
        ROOT, collaboration_inbox_file=INBOX_FILE
    ).to_dict()
    rendered = render_control_panel_html(payload)

    for expected in (
        'id="collaboration-inbox"',
        'href="#collaboration-inbox"',
        "协作 / 当前待办",
        "当前操作者待办",
        "当前运行状态",
        "当前操作资格",
        "待处理审批",
        "当前待办不是执行授权",
        "action_eligible=true",
        "target_not_current",
        "execution_authorized=false",
        "dispatch_eligible=false",
        "execution=not_executed",
    ):
        assert expected in rendered
    assert rendered.count('class="operator-inbox-control" disabled') == 5
    assert "fetch(" not in rendered
    assert "XMLHttpRequest" not in rendered


def test_control_panel_inbox_handoff_preserves_fixture_path() -> None:
    payload = control_panel.build_control_panel_handoff(
        ROOT, collaboration_inbox_file=INBOX_FILE
    ).to_dict()

    assert payload["source"]["collaboration_inbox_file"] == INBOX_FILE
    assert payload["snapshot"]["argv"][-3:] == [
        "--collaboration-inbox-file", INBOX_FILE, "--json"
    ]
    assert payload["render"]["argv"][-2:] == [
        "--collaboration-inbox-file", INBOX_FILE
    ]


def test_control_panel_without_inbox_file_preserves_existing_shape() -> None:
    payload = build_control_panel_snapshot(ROOT).to_dict()
    rendered = render_control_panel_html(payload)

    assert "collaboration_inbox" not in payload["sections"]
    assert "collaboration_inbox_file" not in payload["source"]
    assert 'id="collaboration-inbox"' not in rendered


def test_control_panel_inbox_failure_fails_closed() -> None:
    payload = build_control_panel_snapshot(
        ROOT, collaboration_inbox_file="adapters/missing-inbox.json"
    ).to_dict()
    rendered = render_control_panel_html(payload)

    assert payload["status"] == "validation_failed"
    assert payload["sections"]["collaboration_inbox"]["status"] == "validation_failed"
    assert "collaboration-operator-inbox-unavailable" in rendered
    assert "当前运行状态" not in rendered


def test_cli_control_panel_commands_accept_collaboration_inbox_file(capsys) -> None:
    snapshot_args = [
        "orchestration", "control-panel", "snapshot",
        "--collaboration-inbox-file", INBOX_FILE, "--json",
    ]
    first_code = main(snapshot_args)
    first = capsys.readouterr()
    second_code = main(snapshot_args)
    second = capsys.readouterr()
    assert first_code == second_code == 0
    assert first.out == second.out
    assert first.err == second.err == ""
    assert json.loads(first.out)["sections"]["collaboration_inbox"]["status"] == "pass"

    render_code = main([
        "orchestration", "control-panel", "render",
        "--collaboration-inbox-file", INBOX_FILE,
    ])
    rendered = capsys.readouterr()
    assert render_code == 0
    assert 'id="collaboration-inbox"' in rendered.out
    assert rendered.err == ""

    handoff_code = main([
        "orchestration", "control-panel", "handoff",
        "--collaboration-inbox-file", INBOX_FILE, "--json",
    ])
    handoff = capsys.readouterr()
    assert handoff_code == 0
    assert json.loads(handoff.out)["source"]["collaboration_inbox_file"] == INBOX_FILE
    assert handoff.err == ""
