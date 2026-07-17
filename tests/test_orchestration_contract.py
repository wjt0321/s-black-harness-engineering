"""Tests for the machine-readable orchestration contract manifest."""

from __future__ import annotations

import json

from agent_runtime.cli import main
from agent_runtime.orchestration_contract import build_contract_manifest


EXPECTED_CONTRACT_IDS = [
    "adapter_registry",
    "approval_read",
    "approval_resolve",
    "artifact_read",
    "automation_profile_check",
    "automation_profile_read",
    "automation_workflow_check",
    "automation_workflow_plan",
    "contract_discovery",
    "contract_requirement_gate",
    "control_panel_read",
    "execution_readiness",
    "execution_trust_binding",
    "external_execution_service_stack",
    "fixed_git_status_execution",
    "orchestration_artifact_export",
    "overview",
    "persistent_run_report_collection",
    "read_loop_snapshot",
    "report_generate",
    "routing_preflight",
    "routing_preflight_snapshot",
    "run_commit",
    "run_plan",
    "run_read",
    "task_read",
    "task_submit",
]


def test_contract_manifest_freezes_v1_shape_and_availability_counts() -> None:
    manifest = build_contract_manifest().to_dict()

    assert manifest["status"] == "pass"
    assert manifest["schema_version"] == "control-plane/orchestration-contract/v1"
    assert manifest["consumer"] == "cli-automation"
    assert manifest["summary"] == {
        "total_entries": 27,
        "stable": 10,
        "stable_limited": 7,
        "preview": 7,
        "unavailable": 3,
    }
    assert [entry["contract_id"] for entry in manifest["entries"]] == EXPECTED_CONTRACT_IDS
    assert manifest["guarantees"] == {
        "deterministic": True,
        "read_only_discovery": True,
        "writes_files": False,
        "accesses_network": False,
        "executes_adapters": False,
    }


def test_control_panel_contract_includes_host_handoff_without_new_capability() -> None:
    entries = {
        entry["contract_id"]: entry
        for entry in build_contract_manifest().to_dict()["entries"]
    }

    control_panel = entries["control_panel_read"]
    assert control_panel["commands"] == [
        ["orchestration", "control-panel", "handoff"],
        ["orchestration", "control-panel", "render"],
        ["orchestration", "control-panel", "snapshot"],
    ]
    assert control_panel["key_flags"] == ["--envelope"]
    assert "host handoff" in control_panel["boundary"]


def test_execution_trust_contract_requires_explicit_rotation_flag() -> None:
    entries = {
        entry["contract_id"]: entry
        for entry in build_contract_manifest().to_dict()["entries"]
    }

    assert "--replace" in entries["execution_trust_binding"]["key_flags"]
    assert "--timeout-seconds" in entries["fixed_git_status_execution"]["key_flags"]
    assert "Generic adapter execution" in entries["external_execution_service_stack"]["boundary"]


def test_contract_manifest_entries_have_safe_deterministic_boundaries() -> None:
    entries = build_contract_manifest().to_dict()["entries"]

    for entry in entries:
        assert set(entry) == {
            "contract_id",
            "availability",
            "access",
            "commands",
            "key_flags",
            "boundary",
        }
        assert entry["availability"] in {
            "stable",
            "stable_limited",
            "preview",
            "unavailable",
        }
        assert entry["access"] in {"read_only", "controlled_write", "unavailable"}
        assert entry["commands"] == sorted(entry["commands"])
        assert entry["key_flags"] == sorted(entry["key_flags"])
        assert entry["boundary"]

        if entry["availability"] == "unavailable":
            assert entry["commands"] == []
            assert entry["access"] == "unavailable"
        else:
            assert entry["commands"]
            assert all(command[0] == "orchestration" for command in entry["commands"])


def test_contract_inspect_json_is_deterministic_and_does_not_write(capsys, tmp_path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    marker = root / "marker.txt"
    marker.write_text("unchanged", encoding="utf-8")
    before = {path.relative_to(root): path.read_bytes() for path in root.rglob("*") if path.is_file()}

    args = [
        "--root",
        str(root),
        "orchestration",
        "contract",
        "inspect",
        "--json",
    ]
    first_code = main(args)
    first = capsys.readouterr().out
    second_code = main(args)
    second = capsys.readouterr().out

    assert first_code == 0
    assert second_code == 0
    assert first == second
    assert json.loads(first)["schema_version"] == "control-plane/orchestration-contract/v1"
    after = {path.relative_to(root): path.read_bytes() for path in root.rglob("*") if path.is_file()}
    assert after == before


def test_contract_inspect_human_output_is_compact(capsys) -> None:
    code = main(["orchestration", "contract", "inspect"])
    captured = capsys.readouterr()

    assert code == 0
    assert "ORCHESTRATION CONTRACT" in captured.out
    assert "schema_version=control-plane/orchestration-contract/v1" in captured.out
    assert "total_entries=27" in captured.out
    assert "run_plan preview read_only orchestration run" in captured.out
    assert "external_execution_service_stack unavailable unavailable -" in captured.out
