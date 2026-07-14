"""Tests for orchestration contract requirement evaluation."""

from __future__ import annotations

import json

from agent_runtime.cli import main
from agent_runtime.orchestration_contract_check import check_contract_requirements


def _by_id(payload: dict[str, object]) -> dict[str, dict[str, object]]:
    requirements = payload["requirements"]
    assert isinstance(requirements, list)
    return {item["contract_id"]: item for item in requirements}


def test_contract_check_passes_stable_requirements_and_normalizes_ids() -> None:
    result = check_contract_requirements(
        ["task_read", "overview", "task_read", "run_read"],
    )
    payload = result.to_dict()

    assert result.exit_code() == 0
    assert payload["status"] == "pass"
    assert payload["schema_version"] == "control-plane/orchestration-contract-check/v1"
    assert payload["constraints"] == {
        "allow_preview": False,
        "max_access": "controlled_write",
    }
    assert [item["contract_id"] for item in payload["requirements"]] == [
        "overview",
        "run_read",
        "task_read",
    ]
    assert payload["summary"] == {
        "total_requirements": 3,
        "satisfied": 3,
        "unsatisfied": 0,
    }
    assert payload["next_action"]["code"] == "requirements_satisfied"


def test_contract_check_requires_at_least_one_requirement() -> None:
    result = check_contract_requirements([])

    assert result.status == "needs_input"
    assert result.exit_code() == 4
    assert result.requirements == ()
    assert result.next_action.code == "provide_requirements"
    assert result.to_dict()["summary"] == {
        "total_requirements": 0,
        "satisfied": 0,
        "unsatisfied": 0,
    }


def test_contract_check_requires_explicit_preview_opt_in() -> None:
    denied = check_contract_requirements(["run_plan"])
    allowed = check_contract_requirements(["run_plan"], allow_preview=True)

    assert denied.status == "needs_input"
    assert denied.exit_code() == 4
    assert denied.requirements[0].result == "preview_not_allowed"
    assert denied.next_action.code == "allow_preview_or_choose_stable"

    assert allowed.status == "pass"
    assert allowed.exit_code() == 0
    assert allowed.requirements[0].result == "satisfied"


def test_contract_check_distinguishes_unknown_and_unavailable() -> None:
    unknown = check_contract_requirements(["missing_contract"])
    unavailable = check_contract_requirements(["external_execution_service_stack"])

    assert unknown.status == "needs_input"
    assert unknown.exit_code() == 4
    assert unknown.requirements[0].availability is None
    assert unknown.requirements[0].access is None
    assert unknown.requirements[0].result == "unknown"
    assert unknown.next_action.code == "provide_known_contract_ids"

    assert unavailable.status == "blocked"
    assert unavailable.exit_code() == 2
    assert unavailable.requirements[0].result == "unavailable"
    assert unavailable.next_action.code == "choose_available_contract"


def test_contract_check_enforces_access_ceiling() -> None:
    result = check_contract_requirements(
        ["task_read", "task_submit"],
        max_access="read_only",
    )
    by_id = _by_id(result.to_dict())

    assert result.status == "blocked"
    assert result.exit_code() == 2
    assert by_id["task_read"]["result"] == "satisfied"
    assert by_id["task_submit"]["result"] == "access_exceeded"
    assert result.next_action.code == "raise_max_access_or_choose_read_only"


def test_contract_check_blocked_issue_takes_priority_but_keeps_all_results() -> None:
    result = check_contract_requirements(
        ["missing_contract", "external_execution_service_stack", "run_plan"],
    )
    by_id = _by_id(result.to_dict())

    assert result.status == "blocked"
    assert result.next_action.code == "choose_available_contract"
    assert by_id["missing_contract"]["result"] == "unknown"
    assert by_id["external_execution_service_stack"]["result"] == "unavailable"
    assert by_id["run_plan"]["result"] == "preview_not_allowed"
    assert result.to_dict()["summary"] == {
        "total_requirements": 3,
        "satisfied": 0,
        "unsatisfied": 3,
    }


def test_contract_check_cli_json_exit_code_is_deterministic_and_no_write(capsys, tmp_path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    marker = root / "marker.txt"
    marker.write_text("unchanged", encoding="utf-8")
    before = marker.read_bytes()
    args = [
        "--root",
        str(root),
        "orchestration",
        "contract",
        "check",
        "--require",
        "run_plan",
        "--json",
    ]

    first_code = main(args)
    first = capsys.readouterr().out
    second_code = main(args)
    second = capsys.readouterr().out

    assert first_code == 4
    assert second_code == 4
    assert first == second
    assert json.loads(first)["next_action"]["code"] == "allow_preview_or_choose_stable"
    assert marker.read_bytes() == before
    assert sorted(path.name for path in root.iterdir()) == ["marker.txt"]


def test_contract_check_cli_allows_preview_and_renders_human_output(capsys) -> None:
    code = main(
        [
            "orchestration",
            "contract",
            "check",
            "--require",
            "run_plan",
            "--allow-preview",
        ]
    )
    captured = capsys.readouterr()

    assert code == 0
    assert "CONTRACT CHECK PASS" in captured.out
    assert "run_plan satisfied preview read_only" in captured.out
    assert "Next: requirements_satisfied" in captured.out
