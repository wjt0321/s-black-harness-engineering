"""Tests for Stage 70 passive Control Panel collaboration projection."""

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
PLAN = "adapters/collaboration-plan.example.json"
BASE_SECTIONS = [
    "overview",
    "tasks",
    "adapters",
    "automation",
    "runs",
    "approvals",
    "artifacts",
    "reports",
]


def _plan_data() -> dict:
    return json.loads((ROOT / PLAN).read_text(encoding="utf-8"))


def _project_root(tmp_path: Path, data: dict) -> Path:
    root = tmp_path / "project"
    (root / "adapters").mkdir(parents=True)
    for name in ("adapters.sample.json", "adapter.schema.json"):
        (root / "adapters" / name).write_bytes((ROOT / "adapters" / name).read_bytes())
    (root / "plans").mkdir()
    (root / "plans" / "plan.json").write_text(json.dumps(data), encoding="utf-8")
    return root


def test_snapshot_with_collaboration_file_projects_safe_plan() -> None:
    result = build_control_panel_snapshot(ROOT, collaboration_file=PLAN)
    payload = result.to_dict()

    assert result.status == "pass"
    assert result.exit_code() == 0
    assert list(payload["sections"]) == [*BASE_SECTIONS, "collaboration"]
    section = payload["sections"]["collaboration"]
    assert section["status"] == "pass"
    assert section["scope"] == "file"
    assert section["availability"] == "stable_limited"
    assert section["schema_version"] == "control-plane/collaboration-plan/v1"
    assert section["source"] == {"plan_file": PLAN}
    plan = section["plan"]
    assert plan["summary"]["socket_count"] == 3
    assert plan["summary"]["work_item_count"] == 3
    assert plan["summary"]["handoff_count"] == 2
    assert plan["summary"]["review_gate_count"] == 1
    assert plan["plan_id"].startswith("sha256:")
    assert plan["guarantees"] == {
        "deterministic": True,
        "read_only": True,
        "writes_files": False,
        "writes_ledgers": False,
        "accesses_network": False,
        "probes_socket_readiness": False,
        "readiness_evidence_collected": False,
        "executes_agents": False,
    }
    assert payload["source"] == {
        "envelope_file": None,
        "collaboration_file": PLAN,
    }
    assert payload["summary"]["section_statuses"]["collaboration"] == "pass"
    assert payload["guarantees"]["read_only"] is True


def test_snapshot_without_collaboration_file_preserves_existing_shape() -> None:
    payload = build_control_panel_snapshot(ROOT).to_dict()

    assert list(payload["sections"]) == BASE_SECTIONS
    assert payload["source"] == {"envelope_file": None}
    assert "collaboration" not in payload["summary"]["section_statuses"]
    assert "collaboration" not in json.dumps(payload)


def test_snapshot_collaboration_plan_is_deterministic_and_does_not_write(
    tmp_path: Path,
) -> None:
    marker = tmp_path / "marker.txt"
    marker.write_text("unchanged", encoding="utf-8")
    temp_before = {
        path.relative_to(tmp_path): path.read_bytes()
        for path in tmp_path.rglob("*")
        if path.is_file()
    }

    first = build_control_panel_snapshot(ROOT, collaboration_file=PLAN).to_dict()
    second = build_control_panel_snapshot(ROOT, collaboration_file=PLAN).to_dict()

    assert first == second
    temp_after = {
        path.relative_to(tmp_path): path.read_bytes()
        for path in tmp_path.rglob("*")
        if path.is_file()
    }
    assert temp_after == temp_before


def test_snapshot_missing_collaboration_file_fails_closed() -> None:
    missing = "adapters/missing-collaboration-plan.json"
    result = build_control_panel_snapshot(ROOT, collaboration_file=missing)
    payload = result.to_dict()

    assert result.status == "validation_failed"
    assert result.exit_code() != 0
    section = payload["sections"]["collaboration"]
    assert section["status"] == "validation_failed"
    assert section["scope"] == "file"
    assert "plan" not in section
    assert {finding["rule_id"] for finding in section["findings"]} == {
        "collaboration-plan-not-found"
    }
    assert payload["summary"]["section_statuses"]["collaboration"] == "validation_failed"
    serialized = json.dumps(payload, ensure_ascii=False)
    assert "traceback" not in serialized.lower()
    assert "credential" not in serialized.lower()


def test_snapshot_invalid_collaboration_plan_surfaces_findings(tmp_path: Path) -> None:
    data = _plan_data()
    data["socket_bindings"][0]["socket_id"] = "unknown-agent"
    root = _project_root(tmp_path, data)

    result = build_control_panel_snapshot(root, collaboration_file="plans/plan.json")
    payload = result.to_dict()

    section = payload["sections"]["collaboration"]
    assert section["status"] == "validation_failed"
    assert "plan" not in section
    rule_ids = {finding["rule_id"] for finding in section["findings"]}
    assert "collaboration-plan-socket-unknown" in rule_ids


def test_snapshot_collaboration_path_escape_fails_closed(tmp_path: Path) -> None:
    root = _project_root(tmp_path, _plan_data())
    result = build_control_panel_snapshot(root, collaboration_file="../outside.json")
    payload = result.to_dict()

    section = payload["sections"]["collaboration"]
    assert section["status"] == "validation_failed"
    assert section["findings"][0]["rule_id"] == "collaboration-plan-path-escape"
    assert payload["source"]["collaboration_file"] is None


def test_handoff_with_collaboration_file_binds_both_representations() -> None:
    payload = control_panel.build_control_panel_handoff(
        ROOT,
        collaboration_file=PLAN,
    ).to_dict()

    assert payload["status"] == "pass"
    assert payload["source"] == {
        "envelope_file": None,
        "collaboration_file": PLAN,
    }
    snapshot_argv = payload["snapshot"]["argv"]
    render_argv = payload["render"]["argv"]
    assert snapshot_argv[-3:] == ["--collaboration-file", PLAN, "--json"]
    assert render_argv[-2:] == ["--collaboration-file", PLAN]
    assert "--envelope" not in snapshot_argv
    assert "--envelope" not in render_argv


def test_handoff_without_collaboration_file_keeps_existing_argv() -> None:
    payload = control_panel.build_control_panel_handoff(ROOT).to_dict()

    assert payload["source"] == {"envelope_file": None}
    assert "--collaboration-file" not in payload["snapshot"]["argv"]
    assert "--collaboration-file" not in payload["render"]["argv"]


def test_html_renders_accessible_collaboration_graph_and_tables() -> None:
    payload = build_control_panel_snapshot(ROOT, collaboration_file=PLAN).to_dict()

    html = render_control_panel_html(payload)

    assert '<section class="panel-section" id="collaboration">' in html
    assert 'href="#collaboration"' in html
    assert 'role="img"' in html
    assert "<svg" in html
    assert "协作计划图" in html
    for socket_id in ("kimi-code-acp", "omp-acp", "claude-code-acp"):
        assert socket_id in html
    for work_item_id in ("plan", "implement", "review"):
        assert work_item_id in html
    assert "review-implementation" in html
    assert "协作 Agent 插座绑定" in html
    assert "协作路由说明" in html
    assert "explicit_plan_binding" in html
    assert "not_collected" in html
    assert "live_probe_performed" in html
    assert "协作工作项" in html
    assert "协作交接" in html
    assert "协作审阅门" in html


def test_html_collaboration_escapes_plan_strings(tmp_path: Path) -> None:
    data = _plan_data()
    data["work_items"][0]["work_item_id"] = '</svg><script>alert("x")</script>'
    data["work_items"][1]["depends_on"] = ['</svg><script>alert("x")</script>']
    data["handoffs"][0]["from_work_item_id"] = '</svg><script>alert("x")</script>'
    root = _project_root(tmp_path, data)
    payload = build_control_panel_snapshot(
        root, collaboration_file="plans/plan.json"
    ).to_dict()

    html = render_control_panel_html(payload)

    assert '</svg><script>alert("x")</script>' not in html
    assert "&lt;/svg&gt;&lt;script&gt;alert" in html


def test_html_collaboration_failure_shows_findings_without_graph() -> None:
    payload = build_control_panel_snapshot(
        ROOT,
        collaboration_file="adapters/missing-collaboration-plan.json",
    ).to_dict()

    html = render_control_panel_html(payload)

    assert '<section class="panel-section" id="collaboration">' in html
    assert "collaboration-plan-not-found" in html
    assert "<svg" not in html


def test_html_without_collaboration_file_omits_section() -> None:
    payload = build_control_panel_snapshot(ROOT).to_dict()

    html = render_control_panel_html(payload)

    assert 'id="collaboration"' not in html
    assert 'href="#collaboration"' not in html


def test_cli_snapshot_render_and_handoff_accept_collaboration_flag(capsys) -> None:
    snapshot_args = [
        "orchestration",
        "control-panel",
        "snapshot",
        "--collaboration-file",
        PLAN,
        "--json",
    ]
    first_code = main(snapshot_args)
    first_snapshot = capsys.readouterr().out
    second_code = main(snapshot_args)
    second_snapshot = capsys.readouterr().out
    assert first_code == second_code == 0
    assert first_snapshot == second_snapshot
    snapshot = json.loads(first_snapshot)
    assert snapshot["status"] == "pass"
    assert snapshot["sections"]["collaboration"]["status"] == "pass"

    render_args = [
        "orchestration",
        "control-panel",
        "render",
        "--collaboration-file",
        PLAN,
    ]
    first_render_code = main(render_args)
    first_html = capsys.readouterr().out
    second_render_code = main(render_args)
    second_html = capsys.readouterr().out
    assert first_render_code == second_render_code == 0
    assert first_html == second_html
    assert 'id="collaboration"' in first_html

    handoff_args = [
        "orchestration",
        "control-panel",
        "handoff",
        "--collaboration-file",
        PLAN,
        "--json",
    ]
    handoff_code = main(handoff_args)
    handoff = json.loads(capsys.readouterr().out)
    assert handoff_code == 0
    assert handoff["source"]["collaboration_file"] == PLAN
    assert handoff["snapshot"]["argv"][-3:] == ["--collaboration-file", PLAN, "--json"]


def test_cli_snapshot_rejects_invalid_collaboration_plan(capsys) -> None:
    code = main(
        [
            "orchestration",
            "control-panel",
            "snapshot",
            "--collaboration-file",
            "adapters/missing-collaboration-plan.json",
            "--json",
        ]
    )
    output = capsys.readouterr()
    payload = json.loads(output.out)

    assert code != 0
    assert payload["status"] == "validation_failed"
    assert payload["sections"]["collaboration"]["status"] == "validation_failed"
    assert output.err == ""
