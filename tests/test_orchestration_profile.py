"""Tests for source-backed orchestration automation profiles."""

from __future__ import annotations

import json
from pathlib import Path

from agent_runtime.cli import main
from agent_runtime.orchestration_profile import (
    check_automation_profile,
    inspect_automation_profile,
    list_automation_profiles,
)

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "automation" / "automation-profiles.schema.json"


def _write_registry(root: Path, profiles: list[dict[str, object]]) -> None:
    automation = root / "automation"
    automation.mkdir(parents=True, exist_ok=True)
    (automation / "automation-profiles.schema.json").write_text(
        SCHEMA.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (automation / "automation-profiles.sample.json").write_text(
        json.dumps(
            {
                "schema_version": "control-plane/automation-profiles/v1",
                "profiles": profiles,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _profile(
    profile_id: str,
    *,
    required_contracts: list[str],
    allow_preview: bool = False,
    max_access: str = "read_only",
    description: str = "Test automation profile.",
) -> dict[str, object]:
    return {
        "profile_id": profile_id,
        "description": description,
        "required_contracts": required_contracts,
        "allow_preview": allow_preview,
        "max_access": max_access,
    }


def test_profile_list_projects_source_backed_profiles_in_stable_order() -> None:
    result = list_automation_profiles(ROOT)
    payload = result.to_dict()

    assert result.status == "pass"
    assert result.exit_code() == 0
    assert payload["schema_version"] == "control-plane/automation-profile-list/v1"
    assert payload["source"] == "automation/automation-profiles.sample.json"
    assert [item["profile_id"] for item in payload["profiles"]] == [
        "ci-read-only",
        "local-controlled-write",
        "local-dry-run",
    ]
    assert payload["summary"] == {"total_profiles": 3}
    assert set(payload["profiles"][0]) == {
        "profile_id",
        "description",
        "requirement_count",
        "allow_preview",
        "max_access",
    }


def test_profile_inspect_returns_normalized_full_profile() -> None:
    result = inspect_automation_profile(ROOT, "local-dry-run")
    payload = result.to_dict()

    assert result.status == "pass"
    assert result.exit_code() == 0
    assert payload["schema_version"] == "control-plane/automation-profile/v1"
    assert payload["profile"]["profile_id"] == "local-dry-run"
    assert payload["profile"]["allow_preview"] is True
    assert payload["profile"]["max_access"] == "read_only"
    assert payload["profile"]["required_contracts"] == sorted(
        payload["profile"]["required_contracts"]
    )
    assert "run_plan" in payload["profile"]["required_contracts"]


def test_profile_check_reuses_requirement_gate_for_all_samples() -> None:
    for profile_id in ("ci-read-only", "local-dry-run", "local-controlled-write"):
        result = check_automation_profile(ROOT, profile_id)
        payload = result.to_dict()

        assert result.status == "pass"
        assert result.exit_code() == 0
        assert payload["schema_version"] == "control-plane/automation-profile-check/v1"
        assert payload["profile"]["profile_id"] == profile_id
        assert payload["contract_check"]["status"] == "pass"
        assert payload["next_action"]["code"] == "requirements_satisfied"


def test_profile_unknown_id_returns_needs_input() -> None:
    result = inspect_automation_profile(ROOT, "missing-profile")

    assert result.status == "needs_input"
    assert result.exit_code() == 4
    assert result.profile is None
    assert result.next_action["code"] == "choose_known_profile"
    assert "missing-profile" not in result.next_action["message"]


def test_profile_missing_registry_returns_validation_failed_without_traceback(tmp_path) -> None:
    result = list_automation_profiles(tmp_path)

    assert result.status == "validation_failed"
    assert result.exit_code() == 5
    assert result.profiles == ()
    assert result.findings[0].rule_id == "automation-profile-registry-unavailable"
    assert "automation/automation-profiles.sample.json" in result.findings[0].message


def test_profile_schema_failure_is_structured_and_safe(tmp_path) -> None:
    _write_registry(
        tmp_path,
        [
            _profile(
                "bad-profile",
                required_contracts=[],
            )
        ],
    )

    result = list_automation_profiles(tmp_path)

    assert result.status == "validation_failed"
    assert result.exit_code() == 5
    assert result.findings[0].rule_id == "automation-profile-schema-invalid"
    assert result.profiles == ()


def test_profile_duplicate_ids_are_rejected(tmp_path) -> None:
    _write_registry(
        tmp_path,
        [
            _profile("duplicate", required_contracts=["task_read"]),
            _profile(
                "duplicate",
                description="Second entry with the same id.",
                required_contracts=["overview"],
            ),
        ],
    )

    result = list_automation_profiles(tmp_path)

    assert result.status == "validation_failed"
    assert result.findings[0].rule_id == "duplicate-automation-profile-id"
    assert "duplicate" in result.findings[0].message


def test_profile_check_preserves_blocked_contract_decision(tmp_path) -> None:
    _write_registry(
        tmp_path,
        [
            _profile(
                "blocked-profile",
                required_contracts=["external_execution_service_stack"],
            )
        ],
    )

    result = check_automation_profile(tmp_path, "blocked-profile")
    payload = result.to_dict()

    assert result.status == "blocked"
    assert result.exit_code() == 2
    assert payload["contract_check"]["requirements"][0]["result"] == "unavailable"
    assert payload["next_action"]["code"] == "choose_available_contract"


def test_profile_cli_is_deterministic_and_no_write(capsys, tmp_path) -> None:
    _write_registry(
        tmp_path,
        [_profile("safe-profile", required_contracts=["overview", "task_read"])],
    )
    before = {
        path.relative_to(tmp_path): path.read_bytes()
        for path in tmp_path.rglob("*")
        if path.is_file()
    }
    args = [
        "--root",
        str(tmp_path),
        "orchestration",
        "profile",
        "check",
        "--profile-id",
        "safe-profile",
        "--json",
    ]

    first_code = main(args)
    first = capsys.readouterr().out
    second_code = main(args)
    second = capsys.readouterr().out

    assert first_code == 0
    assert second_code == 0
    assert first == second
    assert json.loads(first)["profile"]["profile_id"] == "safe-profile"
    after = {
        path.relative_to(tmp_path): path.read_bytes()
        for path in tmp_path.rglob("*")
        if path.is_file()
    }
    assert after == before


def test_profile_cli_list_and_inspect_human_output(capsys) -> None:
    list_code = main(["orchestration", "profile", "list"])
    list_output = capsys.readouterr().out
    inspect_code = main(
        [
            "orchestration",
            "profile",
            "inspect",
            "--profile-id",
            "ci-read-only",
        ]
    )
    inspect_output = capsys.readouterr().out

    assert list_code == 0
    assert "AUTOMATION PROFILES" in list_output
    assert "ci-read-only" in list_output
    assert inspect_code == 0
    assert "AUTOMATION PROFILE PASS" in inspect_output
    assert "profile_id=ci-read-only" in inspect_output
