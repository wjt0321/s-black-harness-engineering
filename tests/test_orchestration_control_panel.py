"""Tests for Stage 16/17 Control Panel representations and host handoff."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from agent_runtime import orchestration_control_panel as control_panel
from agent_runtime.cli import main
from agent_runtime.orchestration_control_panel import (
    build_control_panel_snapshot,
    render_control_panel_html,
)

ROOT = Path(__file__).resolve().parents[1]
ENVELOPE = "adapters/execution-envelope.examples.json"
EXPECTED_SECTIONS = [
    "overview",
    "tasks",
    "adapters",
    "automation",
    "runs",
    "approvals",
    "artifacts",
    "reports",
]


def _files(root: Path) -> dict[Path, bytes]:
    return {
        path.relative_to(root): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


def test_control_panel_handoff_freezes_v1_shape_and_representation_identities() -> None:
    snapshot = build_control_panel_snapshot(ROOT, envelope_file=ENVELOPE).to_dict()

    result = control_panel.build_control_panel_handoff(
        ROOT,
        envelope_file=ENVELOPE,
    )
    payload = result.to_dict()

    assert result.status == "pass"
    assert result.exit_code() == 0
    assert list(payload) == [
        "status",
        "schema_version",
        "handoff_id",
        "source",
        "snapshot",
        "render",
        "boundaries",
        "findings",
        "next_action",
    ]
    assert payload["schema_version"] == "control-plane/control-panel-handoff/v1"
    assert payload["source"] == snapshot["source"]
    assert payload["snapshot"] == {
        "snapshot_id": snapshot["snapshot_id"],
        "schema_version": snapshot["schema_version"],
        "media_type": "application/json; charset=utf-8",
        "encoding": "utf-8",
        "working_directory": "project_root",
        "scoped_unavailable": [
            {
                "section": "reports",
                "scope": "request",
                "reason": "request_context_required",
            }
        ],
        "argv": [
            "python",
            "-m",
            "agent_runtime.cli",
            "orchestration",
            "control-panel",
            "snapshot",
            "--envelope",
            ENVELOPE,
            "--json",
        ],
    }
    render_identity = {
        "snapshot_id": snapshot["snapshot_id"],
        "renderer_version": "control-plane/control-panel-html/v1",
    }
    assert payload["render"] == {
        "render_id": _canonical_id(render_identity),
        "renderer_version": "control-plane/control-panel-html/v1",
        "media_type": "text/html; charset=utf-8",
        "encoding": "utf-8",
        "working_directory": "project_root",
        "self_contained": True,
        "argv": [
            "python",
            "-m",
            "agent_runtime.cli",
            "orchestration",
            "control-panel",
            "render",
            "--envelope",
            ENVELOPE,
        ],
    }
    assert payload["boundaries"] == {
        "read_only": True,
        "writes_files": False,
        "writes_ledgers": False,
        "accesses_network": False,
        "starts_service": False,
        "executes_commands": False,
        "executes_adapters": False,
    }
    assert payload["findings"] == []
    assert payload["next_action"]["code"] == "read_control_panel_representation"

    without_id = {key: value for key, value in payload.items() if key != "handoff_id"}
    assert payload["handoff_id"] == _canonical_id(without_id)
    serialized = json.dumps(payload, ensure_ascii=False)
    assert "<!doctype html>" not in serialized.lower()
    assert "<script" not in serialized.lower()


def test_control_panel_handoff_without_envelope_exposes_scoped_boundaries() -> None:
    payload = control_panel.build_control_panel_handoff(ROOT).to_dict()

    assert payload["status"] == "pass"
    assert payload["source"] == {"envelope_file": None}
    assert payload["snapshot"]["scoped_unavailable"] == [
        {"section": "runs", "scope": "envelope", "reason": "envelope_required"},
        {
            "section": "approvals",
            "scope": "envelope",
            "reason": "envelope_required",
        },
        {
            "section": "artifacts",
            "scope": "envelope",
            "reason": "envelope_required",
        },
        {
            "section": "reports",
            "scope": "request",
            "reason": "request_context_required",
        },
    ]
    assert "--envelope" not in payload["snapshot"]["argv"]
    assert "--envelope" not in payload["render"]["argv"]


def test_control_panel_handoff_normalizes_absolute_project_paths() -> None:
    absolute_envelope = str((ROOT / ENVELOPE).resolve())

    snapshot = build_control_panel_snapshot(
        ROOT, envelope_file=absolute_envelope
    ).to_dict()
    payload = control_panel.build_control_panel_handoff(
        ROOT, envelope_file=absolute_envelope
    ).to_dict()

    assert snapshot["source"] == {"envelope_file": ENVELOPE}
    assert payload["source"] == snapshot["source"]
    assert payload["snapshot"]["snapshot_id"] == snapshot["snapshot_id"]
    assert absolute_envelope not in json.dumps(payload, ensure_ascii=False)
    assert ENVELOPE in payload["snapshot"]["argv"]
    assert ENVELOPE in payload["render"]["argv"]


def test_control_panel_handoff_invalid_envelope_fails_safely(capsys) -> None:
    missing = "adapters/missing-envelope.json"
    result = control_panel.build_control_panel_handoff(ROOT, envelope_file=missing)
    payload = result.to_dict()

    assert result.status == "error"
    assert result.exit_code() != 0
    assert {finding["rule_id"] for finding in payload["findings"]} == {
        "file-not-found"
    }
    assert payload["next_action"]["code"] == "fix_control_panel_sources"
    serialized = json.dumps(payload, ensure_ascii=False)
    assert "credential" not in serialized.lower()
    assert "traceback" not in serialized.lower()

    code = main(
        [
            "orchestration",
            "control-panel",
            "handoff",
            "--envelope",
            missing,
            "--json",
        ]
    )
    output = capsys.readouterr()
    assert code != 0
    assert json.loads(output.out)["status"] == "error"
    assert output.err == ""


def test_control_panel_handoff_is_deterministic_and_does_not_write(tmp_path: Path) -> None:
    marker = tmp_path / "marker.txt"
    marker.write_text("unchanged", encoding="utf-8")
    before = _files(ROOT)
    temp_before = _files(tmp_path)

    first = control_panel.build_control_panel_handoff(
        ROOT, envelope_file=ENVELOPE
    ).to_dict()
    second = control_panel.build_control_panel_handoff(
        ROOT, envelope_file=ENVELOPE
    ).to_dict()
    without_envelope = control_panel.build_control_panel_handoff(ROOT).to_dict()

    assert first == second
    assert first["render"]["render_id"] != without_envelope["render"]["render_id"]
    assert _files(ROOT) == before
    assert _files(tmp_path) == temp_before


def test_control_panel_handoff_cli_json_and_human_outputs_are_compact(capsys) -> None:
    args = [
        "orchestration",
        "control-panel",
        "handoff",
        "--envelope",
        ENVELOPE,
        "--json",
    ]
    first_code = main(args)
    first = capsys.readouterr().out
    second_code = main(args)
    second = capsys.readouterr().out

    assert first_code == second_code == 0
    assert first == second
    assert json.loads(first)["schema_version"] == (
        "control-plane/control-panel-handoff/v1"
    )

    human_code = main(["orchestration", "control-panel", "handoff"])
    human = capsys.readouterr().out
    assert human_code == 0
    assert "CONTROL PANEL HANDOFF PASS" in human
    assert "handoff_id=sha256:" in human
    assert "snapshot_id=sha256:" in human
    assert "render_id=sha256:" in human


def _canonical_id(payload: dict[str, object]) -> str:
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(canonical).hexdigest()}"


def test_control_panel_snapshot_without_envelope_is_honest_and_read_only() -> None:
    result = build_control_panel_snapshot(ROOT)
    payload = result.to_dict()

    assert result.status == "pass"
    assert result.exit_code() == 0
    assert payload["schema_version"] == "control-plane/control-panel-snapshot/v1"
    assert payload["snapshot_id"].startswith("sha256:")
    assert len(payload["snapshot_id"]) == 71
    canonical_payload = {
        key: value for key, value in payload.items() if key != "snapshot_id"
    }
    canonical = json.dumps(
        canonical_payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    assert payload["snapshot_id"] == f"sha256:{hashlib.sha256(canonical).hexdigest()}"
    assert payload["source"] == {"envelope_file": None}
    assert list(payload["sections"]) == EXPECTED_SECTIONS
    assert payload["sections"]["overview"]["status"] == "pass"
    assert payload["sections"]["tasks"]["status"] == "pass"
    assert payload["sections"]["adapters"]["status"] == "pass"
    assert payload["sections"]["automation"]["status"] == "pass"
    for section in ("runs", "approvals", "artifacts"):
        assert payload["sections"][section]["status"] == "unavailable"
        assert payload["sections"][section]["reason"] == "envelope_required"
    assert payload["sections"]["reports"]["status"] == "unavailable"
    assert payload["sections"]["reports"]["scope"] == "request"
    assert payload["summary"]["total_tasks"] == len(
        payload["sections"]["tasks"]["tasks"]
    )
    assert payload["summary"]["total_adapters"] == len(
        payload["sections"]["adapters"]["adapters"]
    )
    sockets = payload["sections"]["adapters"]["agent_sockets"]
    assert payload["summary"]["agent_socket_count"] == len(sockets)
    assert {socket["socket_id"] for socket in sockets} >= {
        "pi-cli", "kimi-code-acp", "claude-code-acp", "omp-acp"
    }
    assert all(socket["availability"] == "declared" for socket in sockets)
    assert payload["summary"]["run_count"] == 0
    assert payload["guarantees"] == {
        "deterministic": True,
        "read_only": True,
        "writes_files": False,
        "writes_ledgers": False,
        "accesses_network": False,
        "executes_commands": False,
        "executes_adapters": False,
        "starts_service": False,
    }


def test_control_panel_snapshot_with_envelope_reuses_existing_read_models() -> None:
    payload = build_control_panel_snapshot(ROOT, envelope_file=ENVELOPE).to_dict()

    assert payload["status"] == "pass"
    assert payload["source"] == {"envelope_file": ENVELOPE}
    assert payload["sections"]["runs"]["status"] == "pass"
    assert payload["sections"]["approvals"]["status"] == "pass"
    assert payload["sections"]["artifacts"]["status"] == "pass"
    assert payload["summary"]["run_count"] == len(
        payload["sections"]["runs"]["runs"]
    )
    assert payload["summary"]["pending_approval_count"] == sum(
        item["status"] == "pending"
        for item in payload["sections"]["approvals"]["approvals"]
    )
    assert payload["summary"]["artifact_count"] == len(
        payload["sections"]["artifacts"]["artifacts"]
    )
    assert payload["sections"]["automation"]["contract_summary"]["total_entries"] >= 1
    assert payload["summary"]["automation_profile_count"] == len(
        payload["sections"]["automation"]["profiles"]
    )


def test_control_panel_snapshot_invalid_envelope_promotes_safe_failure() -> None:
    payload = build_control_panel_snapshot(
        ROOT,
        envelope_file="adapters/missing-envelope.json",
    ).to_dict()

    assert payload["status"] == "error"
    for section in ("runs", "approvals", "artifacts"):
        assert payload["sections"][section]["status"] == "error"
    assert payload["findings"]
    assert {finding["rule_id"] for finding in payload["findings"]} == {
        "file-not-found"
    }
    serialized = json.dumps(payload)
    assert "credential" not in serialized.lower()
    assert payload["next_action"]["code"] == "fix_control_panel_sources"


def test_control_panel_snapshot_is_deterministic_and_does_not_write(tmp_path: Path) -> None:
    marker = tmp_path / "marker.txt"
    marker.write_text("unchanged", encoding="utf-8")
    before = _files(ROOT)
    temp_before = _files(tmp_path)

    first = build_control_panel_snapshot(ROOT, envelope_file=ENVELOPE).to_dict()
    second = build_control_panel_snapshot(ROOT, envelope_file=ENVELOPE).to_dict()

    assert first == second
    assert _files(ROOT) == before
    assert _files(tmp_path) == temp_before


def test_control_panel_html_is_self_contained_accessible_and_escaped() -> None:
    payload = build_control_panel_snapshot(ROOT, envelope_file=ENVELOPE).to_dict()
    payload["sections"]["tasks"]["tasks"][0]["title"] = (
        '</script><script>alert("panel")</script>'
    )

    html = render_control_panel_html(payload)

    assert html.startswith("<!doctype html>")
    assert '<html lang="zh-CN">' in html
    assert "S-BLACK / 控制台" in html
    assert 'href="#main"' in html
    assert 'aria-label="全局过滤"' in html
    assert "prefers-reduced-motion" in html
    assert "Content-Security-Policy" in html
    assert "http://" not in html
    assert "https://" not in html
    assert "fetch(" not in html
    assert "WebSocket" not in html
    assert "<script src=" not in html
    assert '</script><script>alert("panel")</script>' not in html
    assert "&lt;/script&gt;&lt;script&gt;alert" in html
    assert "data-search-row" in html
    assert "执行" not in html or "不执行" in html


def test_control_panel_cli_snapshot_and_render_are_deterministic(capsys) -> None:
    snapshot_args = [
        "orchestration",
        "control-panel",
        "snapshot",
        "--envelope",
        ENVELOPE,
        "--json",
    ]
    first_code = main(snapshot_args)
    first_snapshot = capsys.readouterr().out
    second_code = main(snapshot_args)
    second_snapshot = capsys.readouterr().out

    render_args = [
        "orchestration",
        "control-panel",
        "render",
        "--envelope",
        ENVELOPE,
    ]
    first_render_code = main(render_args)
    first_html = capsys.readouterr().out
    second_render_code = main(render_args)
    second_html = capsys.readouterr().out

    assert first_code == second_code == 0
    assert first_snapshot == second_snapshot
    assert json.loads(first_snapshot)["status"] == "pass"
    assert first_render_code == second_render_code == 0
    assert first_html == second_html
    assert first_html.startswith("<!doctype html>")


def test_control_panel_snapshot_human_output_is_compact(capsys) -> None:
    code = main(["orchestration", "control-panel", "snapshot"])
    output = capsys.readouterr().out

    assert code == 0
    assert "CONTROL PANEL SNAPSHOT PASS" in output
    assert "snapshot_id=sha256:" in output
    assert "tasks=" in output
    assert "runs=0" in output
    assert "runs=unavailable" in output


def test_control_panel_projects_blocked_dispatch_eligibility() -> None:
    dispatch = "adapters/collaboration-dispatch.example.json"
    payload = build_control_panel_snapshot(ROOT, dispatch_file=dispatch).to_dict()

    section = payload["sections"]["dispatch"]
    assert section["status"] == "pass"
    assert section["availability"] == "experimental"
    assert section["proposal"]["dispatch_eligible"] is False
    assert section["proposal"]["execution"] == "not_executed"
    assert section["proposal"]["blocked_reasons"] == [
        "readiness_not_collected",
        "execution_authority_unavailable",
    ]
    rendered = render_control_panel_html(payload)
    assert "可派发" in rendered
    assert "not_executed" in rendered
    assert "readiness_not_collected" in rendered
    assert "execution_authority_unavailable" in rendered


def test_control_panel_renders_bound_readiness_evidence() -> None:
    dispatch = "adapters/collaboration-dispatch-with-readiness.example.json"
    payload = build_control_panel_snapshot(ROOT, dispatch_file=dispatch).to_dict()

    proposal = payload["sections"]["dispatch"]["proposal"]
    assert proposal["dispatch_eligible"] is False
    assert proposal["readiness_evidence"]["status"] == "available"
    assert proposal["readiness_evidence"]["level"] == "runner_listed"
    assert proposal["blocked_reasons"] == [
        "readiness_insufficient",
        "execution_authority_unavailable",
    ]
    rendered = render_control_panel_html(payload)
    assert "runner_listed" in rendered
    assert proposal["readiness_evidence"]["evidence_id"] in rendered
    assert "readiness_insufficient" in rendered


def test_control_panel_handoff_preserves_dispatch_file() -> None:
    dispatch = "adapters/collaboration-dispatch.example.json"
    payload = control_panel.build_control_panel_handoff(
        ROOT, dispatch_file=dispatch
    ).to_dict()

    assert payload["source"]["dispatch_file"] == dispatch
    assert payload["snapshot"]["argv"][-3:] == ["--dispatch-file", dispatch, "--json"]
    assert payload["render"]["argv"][-2:] == ["--dispatch-file", dispatch]


def test_control_panel_projects_operator_authored_manual_board() -> None:
    board_file = "adapters/manual-collaboration-board.example.json"
    payload = build_control_panel_snapshot(ROOT, manual_board_file=board_file).to_dict()

    section = payload["sections"]["manual_board"]
    assert section["status"] == "pass"
    assert section["availability"] == "fixture"
    assert section["guarantees"]["planning_mode"] == "manual"
    assert section["board"]["planned_by"] == "operator"
    assert [lane["socket_id"] for lane in section["board"]["lanes"]] == [
        "kimi-code-acp", "omp-acp", "claude-code-acp"
    ]


def test_control_panel_manual_board_html_keeps_simulation_boundary() -> None:
    board_file = "adapters/manual-collaboration-board.example.json"
    payload = build_control_panel_snapshot(ROOT, manual_board_file=board_file).to_dict()
    rendered = render_control_panel_html(payload)

    assert 'id="manual-board"' in rendered
    assert "操作者人工编排" in rendered
    assert rendered.count("仅为模拟展示 · 未启动任何 Agent 对话") == 3
    assert rendered.count('class="board-action" disabled') == 6
    assert "交接与产物时间线" in rendered


def test_control_panel_handoff_preserves_manual_board_file() -> None:
    board_file = "adapters/manual-collaboration-board.example.json"
    payload = control_panel.build_control_panel_handoff(
        ROOT, manual_board_file=board_file
    ).to_dict()

    assert payload["source"]["manual_board_file"] == board_file
    assert payload["snapshot"]["argv"][-3:] == ["--manual-board-file", board_file, "--json"]
    assert payload["render"]["argv"][-2:] == ["--manual-board-file", board_file]


def test_control_panel_defaults_to_chinese_with_annotated_technical_terms() -> None:
    board_file = "adapters/manual-collaboration-board.example.json"
    collaboration_file = "adapters/collaboration-plan.example.json"
    payload = build_control_panel_snapshot(
        ROOT,
        collaboration_file=collaboration_file,
        manual_board_file=board_file,
    ).to_dict()
    rendered = render_control_panel_html(payload)

    for expected in (
        "总览 / 项目状态",
        "任务总数（total_tasks）",
        "安全只读模型（read model）",
        "账本（ledger）",
        "服务（service）",
        "任务 / 账本快照",
        "适配器（Adapter）/ 能力注册表",
        "Agent 插座（Socket）ID",
        "协作 / 计划投影",
        "协作 / 人工看板",
        "规划者（planner）",
        "审阅者（reviewer）",
        "模拟完成（simulated_complete）",
        "批准开始（approve_start）",
        "代码补丁（patch）",
        "测试结果（test_result）",
        "可见",
    ):
        assert expected in rendered
    for forbidden in (
        "OPERATOR AUTHORED",
        "Manual task split",
        "Operator controls",
        "Handoff and artifact timeline",
        "${visible}/${rows.length} visible",
    ):
        assert forbidden not in rendered


def test_manual_plan_editor_is_local_pending_and_non_executing() -> None:
    board_file = "adapters/manual-collaboration-board.example.json"
    payload = build_control_panel_snapshot(ROOT, manual_board_file=board_file).to_dict()
    rendered = render_control_panel_html(payload)

    assert 'id="manual-plan-editor"' in rendered
    assert "人工计划草稿编辑器" in rendered
    assert "任务标题" in rendered
    assert "角色由当前 Agent 插座绑定决定" in rendered
    assert "仅浏览器内存" in rendered
    assert "待人工确认 · 不可派发" in rendered
    assert "不会写入项目文件、不会访问网络、不会调用 Agent" in rendered
    assert "operator_confirmed" in rendered
    assert "dispatch_eligible=false" in rendered
    assert "execution=not_executed" in rendered
    assert "fetch(" not in rendered
    assert "XMLHttpRequest" not in rendered


def test_manual_plan_candidate_requires_validation_and_explicit_confirmation() -> None:
    board_file = "adapters/manual-collaboration-board.example.json"
    payload = build_control_panel_snapshot(ROOT, manual_board_file=board_file).to_dict()
    rendered = render_control_panel_html(payload)

    for expected in (
        'id="draft-state"',
        "编辑中 · 不可派发",
        "校验通过 · 等待人工确认",
        "已人工确认 · 仅可导出",
        'id="draft-validate"',
        'id="draft-confirm"',
        'id="draft-copy"',
        'id="draft-download"',
        'id="draft-filename"',
        'id="draft-validation-results"',
        "operator_confirmed",
        "resetDraftState",
        "validateCandidate",
    ):
        assert expected in rendered

    assert 'id="draft-confirm" type="button" disabled' in rendered
    assert 'id="draft-copy" type="button" disabled' in rendered
    assert 'id="draft-download" type="button" disabled' in rendered
    assert 'class="draft-depends" aria-label="依赖工作项，多个值用逗号分隔" value=""' in rendered
    assert "dispatch_eligible=false" in rendered
    assert "execution=not_executed" in rendered


def test_manual_plan_export_uses_existing_contract_and_user_triggered_browser_apis() -> None:
    board_file = "adapters/manual-collaboration-board.example.json"
    payload = build_control_panel_snapshot(ROOT, manual_board_file=board_file).to_dict()
    rendered = render_control_panel_html(payload)

    for expected in (
        'data-role="planner"',
        'data-role="implementer"',
        'data-role="reviewer"',
        "socket_bindings:",
        "work_items:",
        "handoffs:",
        "review_gates:",
        "required_capabilities: []",
        "URL.createObjectURL",
        "navigator.clipboard",
        "application/json",
        "collaboration-plan-",
    ):
        assert expected in rendered

    for forbidden in (
        "fetch(",
        "XMLHttpRequest",
        "localStorage",
        "sessionStorage",
        "dispatch_eligible:",
        "execution:",
    ):
        assert forbidden not in rendered
