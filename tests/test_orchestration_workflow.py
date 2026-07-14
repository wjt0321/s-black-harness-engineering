"""Tests for deterministic read-only Automation Workflow Plan projection."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from agent_runtime.cli import main
from agent_runtime.orchestration_contract import build_contract_manifest
from agent_runtime.orchestration_workflow import build_automation_workflow_plan

ROOT = Path(__file__).resolve().parents[1]


def _copy_automation_registry(target: Path) -> None:
    shutil.copytree(ROOT / "automation", target / "automation")


def test_workflow_plan_projects_profile_requirements_from_contract_manifest() -> None:
    result = build_automation_workflow_plan(ROOT, "local-dry-run")
    payload = result.to_dict()

    assert result.status == "pass"
    assert payload["schema_version"] == "control-plane/automation-workflow-plan/v1"
    assert payload["requested_profile_id"] == "local-dry-run"
    assert payload["profile"]["profile_id"] == "local-dry-run"
    assert payload["contract_check"]["status"] == "pass"
    assert payload["summary"] == {
        "total_steps": 9,
        "phase_counts": {
            "discovery": 3,
            "inspect": 1,
            "decide": 2,
            "prepare": 2,
            "controlled_write": 0,
            "observe": 1,
            "capability": 0,
        },
        "preview_steps": 3,
        "controlled_write_steps": 0,
    }
    assert [(step["phase"], step["contract_id"]) for step in payload["steps"]] == [
        ("discovery", "automation_profile_check"),
        ("discovery", "contract_discovery"),
        ("discovery", "contract_requirement_gate"),
        ("inspect", "task_read"),
        ("decide", "routing_preflight"),
        ("decide", "routing_preflight_snapshot"),
        ("prepare", "read_loop_snapshot"),
        ("prepare", "run_plan"),
        ("observe", "report_generate"),
    ]

    entries = {entry.contract_id: entry for entry in build_contract_manifest().entries}
    for step in payload["steps"]:
        entry = entries[step["contract_id"]]
        assert step["candidate_commands"] == [list(command) for command in entry.commands]
        assert step["required_flags"] == list(entry.key_flags)
        assert step["availability"] == entry.availability
        assert step["access"] == entry.access
        assert step["boundary"] == entry.boundary
        assert step["status"] == "planned"
        assert step["execution"] == "not_executed"


def test_workflow_plan_keeps_controlled_write_as_unexecuted_candidates() -> None:
    result = build_automation_workflow_plan(ROOT, "local-controlled-write")
    payload = result.to_dict()

    assert result.status == "pass"
    assert payload["summary"]["controlled_write_steps"] == 3
    controlled = [step for step in payload["steps"] if step["access"] == "controlled_write"]
    assert [step["contract_id"] for step in controlled] == [
        "approval_resolve",
        "run_commit",
        "task_submit",
    ]
    assert all("--commit" in step["required_flags"] for step in controlled)
    assert all(step["execution"] == "not_executed" for step in controlled)
    assert payload["guarantees"] == {
        "deterministic": True,
        "ephemeral": True,
        "writes_files": False,
        "writes_ledgers": False,
        "accesses_network": False,
        "executes_commands": False,
        "executes_adapters": False,
    }


def test_workflow_plan_propagates_profile_gate_failure_without_steps(tmp_path: Path) -> None:
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
    source_path.write_text(json.dumps(source, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    result = build_automation_workflow_plan(tmp_path, "blocked-profile")
    payload = result.to_dict()

    assert result.status == "blocked"
    assert result.exit_code() == 2
    assert payload["contract_check"]["status"] == "blocked"
    assert payload["steps"] == []
    assert payload["summary"]["total_steps"] == 0
    assert payload["next_action"]["code"] == "choose_available_contract"


def test_workflow_plan_unknown_profile_needs_input_without_steps() -> None:
    result = build_automation_workflow_plan(ROOT, "missing-profile")
    payload = result.to_dict()

    assert result.status == "needs_input"
    assert result.exit_code() == 4
    assert payload["requested_profile_id"] == "missing-profile"
    assert "profile" not in payload
    assert "contract_check" not in payload
    assert payload["steps"] == []
    assert payload["next_action"]["code"] == "choose_known_profile"


def test_workflow_plan_id_and_json_are_content_deterministic(tmp_path: Path) -> None:
    _copy_automation_registry(tmp_path)

    first = build_automation_workflow_plan(tmp_path, "ci-read-only").to_dict()
    second = build_automation_workflow_plan(tmp_path, "ci-read-only").to_dict()
    assert first == second
    assert first["plan_id"].startswith("sha256:")
    assert len(first["plan_id"]) == 71

    source_path = tmp_path / "automation" / "automation-profiles.sample.json"
    source = json.loads(source_path.read_text(encoding="utf-8"))
    source["profiles"][0]["description"] += " Updated."
    source_path.write_text(json.dumps(source, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    changed = build_automation_workflow_plan(tmp_path, "ci-read-only").to_dict()
    assert changed["plan_id"] != first["plan_id"]


def test_workflow_plan_cli_json_is_deterministic_and_does_not_write(capsys, tmp_path: Path) -> None:
    _copy_automation_registry(tmp_path)
    marker = tmp_path / "marker.txt"
    marker.write_text("unchanged", encoding="utf-8")
    before = {path.relative_to(tmp_path): path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()}
    args = [
        "--root",
        str(tmp_path),
        "orchestration",
        "workflow",
        "plan",
        "--profile-id",
        "local-dry-run",
        "--json",
    ]

    first_code = main(args)
    first_output = capsys.readouterr().out
    second_code = main(args)
    second_output = capsys.readouterr().out

    assert first_code == 0
    assert second_code == 0
    assert first_output == second_output
    assert json.loads(first_output)["status"] == "pass"
    after = {path.relative_to(tmp_path): path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()}
    assert after == before


def test_workflow_plan_cli_human_output_is_compact(capsys) -> None:
    code = main(
        [
            "orchestration",
            "workflow",
            "plan",
            "--profile-id",
            "local-controlled-write",
        ]
    )
    captured = capsys.readouterr()

    assert code == 0
    assert "AUTOMATION WORKFLOW PLAN PASS" in captured.out
    assert "profile_id=local-controlled-write" in captured.out
    assert "controlled_write:run_commit" in captured.out
    assert "execution=not_executed" in captured.out
    assert "Next: review_workflow_plan" in captured.out
