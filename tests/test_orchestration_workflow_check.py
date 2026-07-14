"""Tests for read-only Automation Workflow Plan drift validation."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from agent_runtime.cli import main
from agent_runtime.orchestration_workflow import build_automation_workflow_plan
from agent_runtime.orchestration_workflow_check import check_automation_workflow_plan

ROOT = Path(__file__).resolve().parents[1]


def _copy_automation_registry(target: Path) -> None:
    shutil.copytree(ROOT / "automation", target / "automation")


def _current_plan_id(root: Path, profile_id: str) -> str:
    return build_automation_workflow_plan(root, profile_id).to_dict()["plan_id"]


def test_workflow_check_passes_when_expected_plan_is_current() -> None:
    expected_plan_id = _current_plan_id(ROOT, "local-dry-run")

    result = check_automation_workflow_plan(
        ROOT,
        "local-dry-run",
        expected_plan_id,
    )
    payload = result.to_dict()

    assert result.status == "pass"
    assert result.exit_code() == 0
    assert payload["schema_version"] == "control-plane/automation-workflow-check/v1"
    assert payload["requested_profile_id"] == "local-dry-run"
    assert payload["expected_plan_id"] == expected_plan_id
    assert payload["current_plan_id"] == expected_plan_id
    assert payload["matches_current"] is True
    assert payload["drift"] == {
        "detected": False,
        "comparison_basis": "canonical_workflow_plan_projection",
        "cause": "none",
        "field_level_diff_available": False,
    }
    assert payload["current_plan"]["plan_id"] == expected_plan_id
    assert payload["next_action"]["code"] == "workflow_plan_current"


def test_workflow_check_blocks_when_profile_projection_drifted(tmp_path: Path) -> None:
    _copy_automation_registry(tmp_path)
    expected_plan_id = _current_plan_id(tmp_path, "ci-read-only")
    source_path = tmp_path / "automation" / "automation-profiles.sample.json"
    source = json.loads(source_path.read_text(encoding="utf-8"))
    source["profiles"][0]["description"] += " Updated."
    source_path.write_text(
        json.dumps(source, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    result = check_automation_workflow_plan(
        tmp_path,
        "ci-read-only",
        expected_plan_id,
    )
    payload = result.to_dict()

    assert result.status == "blocked"
    assert result.exit_code() == 2
    assert payload["current_plan_id"] != expected_plan_id
    assert payload["matches_current"] is False
    assert payload["drift"] == {
        "detected": True,
        "comparison_basis": "canonical_workflow_plan_projection",
        "cause": "content_hash_mismatch",
        "field_level_diff_available": False,
    }
    assert payload["findings"][0]["rule_id"] == "automation-workflow-plan-drift"
    assert expected_plan_id not in payload["findings"][0]["message"]
    assert payload["next_action"]["code"] == "regenerate_and_review_workflow_plan"


def test_workflow_check_rejects_invalid_expected_id_without_reading_registry(
    tmp_path: Path,
) -> None:
    result = check_automation_workflow_plan(
        tmp_path,
        "missing-profile",
        "sha256:any",
    )
    payload = result.to_dict()

    assert result.status == "needs_input"
    assert result.exit_code() == 4
    assert "expected_plan_id" not in payload
    assert "current_plan" not in payload
    assert "sha256:any" not in json.dumps(payload)
    assert payload["findings"][0]["rule_id"] == "invalid-automation-workflow-plan-id"
    assert payload["next_action"]["code"] == "provide_valid_workflow_plan_id"


def test_workflow_check_preserves_blocked_plan_details_without_drift_claim(
    tmp_path: Path,
) -> None:
    _copy_automation_registry(tmp_path)
    source_path = tmp_path / "automation" / "automation-profiles.sample.json"
    source = json.loads(source_path.read_text(encoding="utf-8"))
    source["profiles"].append(
        {
            "profile_id": "blocked-profile",
            "description": "Requires an unavailable capability.",
            "required_contracts": ["external_execution_service_stack"],
            "allow_preview": False,
            "max_access": "read_only",
        }
    )
    source_path.write_text(
        json.dumps(source, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    result = check_automation_workflow_plan(
        tmp_path,
        "blocked-profile",
        "sha256:" + "0" * 64,
    )
    payload = result.to_dict()

    assert result.status == "blocked"
    assert payload["current_plan"]["status"] == "blocked"
    assert payload["current_plan"]["contract_check"]["status"] == "blocked"
    assert "current_plan_id" not in payload
    assert "matches_current" not in payload
    assert "drift" not in payload
    assert payload["next_action"]["code"] == "choose_available_contract"
    human = result.render_human()
    assert "current_plan_id=" not in human
    assert "matches_current=" not in human


def test_workflow_check_propagates_unknown_profile_without_drift_claim() -> None:
    result = check_automation_workflow_plan(
        ROOT,
        "missing-profile",
        "sha256:" + "0" * 64,
    )
    payload = result.to_dict()

    assert result.status == "needs_input"
    assert payload["expected_plan_id"] == "sha256:" + "0" * 64
    assert "current_plan_id" not in payload
    assert "matches_current" not in payload
    assert "drift" not in payload
    assert payload["next_action"]["code"] == "choose_known_profile"


def test_workflow_check_json_is_deterministic_and_does_not_write(
    capsys,
    tmp_path: Path,
) -> None:
    _copy_automation_registry(tmp_path)
    expected_plan_id = _current_plan_id(tmp_path, "local-controlled-write")
    marker = tmp_path / "marker.txt"
    marker.write_text("unchanged", encoding="utf-8")
    before = {
        path.relative_to(tmp_path): path.read_bytes()
        for path in tmp_path.rglob("*")
        if path.is_file()
    }
    args = [
        "--root",
        str(tmp_path),
        "orchestration",
        "workflow",
        "check",
        "--profile-id",
        "local-controlled-write",
        "--expected-plan-id",
        expected_plan_id,
        "--json",
    ]

    first_code = main(args)
    first_output = capsys.readouterr().out
    second_code = main(args)
    second_output = capsys.readouterr().out

    assert first_code == 0
    assert second_code == 0
    assert first_output == second_output
    assert json.loads(first_output)["matches_current"] is True
    after = {
        path.relative_to(tmp_path): path.read_bytes()
        for path in tmp_path.rglob("*")
        if path.is_file()
    }
    assert after == before


def test_workflow_check_human_output_reports_match_and_drift(capsys) -> None:
    expected_plan_id = _current_plan_id(ROOT, "local-dry-run")
    pass_code = main(
        [
            "orchestration",
            "workflow",
            "check",
            "--profile-id",
            "local-dry-run",
            "--expected-plan-id",
            expected_plan_id,
        ]
    )
    pass_output = capsys.readouterr().out

    drift_code = main(
        [
            "orchestration",
            "workflow",
            "check",
            "--profile-id",
            "local-dry-run",
            "--expected-plan-id",
            "sha256:" + "0" * 64,
        ]
    )
    drift_output = capsys.readouterr().out

    assert pass_code == 0
    assert "AUTOMATION WORKFLOW CHECK PASS" in pass_output
    assert "matches_current=true" in pass_output
    assert "Next: workflow_plan_current" in pass_output
    assert drift_code == 2
    assert "AUTOMATION WORKFLOW CHECK BLOCKED" in drift_output
    assert "matches_current=false" in drift_output
    assert "automation-workflow-plan-drift" in drift_output
