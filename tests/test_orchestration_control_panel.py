"""Tests for the Stage 16 read-only Control Panel snapshot and HTML."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

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
    assert "S-BLACK / CONTROL PLANE" in html
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
