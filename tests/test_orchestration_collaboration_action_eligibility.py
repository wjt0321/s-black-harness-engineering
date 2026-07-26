"""Tests for Stage 80 operator action eligibility and approval binding."""

from __future__ import annotations

import json
from pathlib import Path

from agent_runtime.cli import main
from agent_runtime.orchestration_collaboration_action_eligibility import (
    inspect_collaboration_action_eligibility,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = "adapters/collaboration-action-eligibility.example.json"


def _fixture_data() -> dict:
    return json.loads((ROOT / FIXTURE).read_text(encoding="utf-8"))


def _project_root(tmp_path: Path, data: dict) -> Path:
    root = tmp_path / "project"
    adapters = root / "adapters"
    adapters.mkdir(parents=True)
    for name in (
        "adapters.sample.json",
        "adapter.schema.json",
        "collaboration-plan.example.json",
        "collaboration-run-state.schema.json",
        "collaboration-run-state.example.json",
        "collaboration-action-eligibility.schema.json",
    ):
        (adapters / name).write_bytes((ROOT / "adapters" / name).read_bytes())
    (adapters / "actions.json").write_text(json.dumps(data), encoding="utf-8")
    return root


def _rule_ids(result) -> set[str]:
    return {item.rule_id for item in result.findings}


def _action(result, action: str) -> dict:
    return next(item for item in result.actions if item["action"] == action)


def test_action_eligibility_projects_five_checkpoint_bound_actions() -> None:
    result = inspect_collaboration_action_eligibility(ROOT, FIXTURE)

    assert result.status == "pass"
    assert result.guarantees == {
        "deterministic": True,
        "read_only": True,
        "fixture_backed": True,
        "approval_evidence": "fixture",
        "execution_authorized": False,
        "dispatch_eligible": False,
        "execution": "not_executed",
        "executes_agents": False,
        "starts_sessions": False,
        "probes_readiness": False,
        "writes_files": False,
        "writes_ledgers": False,
        "accesses_network": False,
    }
    assert result.run["run_id"] == "collab-run-demo-001"
    assert result.summary == {
        "action_count": 5,
        "eligible_count": 5,
        "blocked_count": 0,
        "approved_fixture_count": 5,
        "recorded_idempotency_key_count": 0,
    }
    assert [item["action"] for item in result.actions] == [
        "approve_start", "cancel", "retry", "request_changes", "approve_handoff"
    ]
    expected_states = {
        "approve_start": "awaiting_approval",
        "cancel": "running",
        "retry": "changes_requested",
        "request_changes": "in_review",
        "approve_handoff": "ready",
    }
    for action, expected_state in expected_states.items():
        item = _action(result, action)
        assert item["current_state"] == expected_state
        assert item["action_eligible"] is True
        assert item["execution_authorized"] is False
        assert item["blocked_reasons"] == []
        candidate = item["command_candidate"]
        assert candidate["schema_version"] == "control-plane/collaboration-action-command-candidate/v1"
        assert candidate["candidate_id"].startswith("sha256:")
        assert candidate["idempotency_key"].startswith("sha256:")
        assert candidate["dispatch_eligible"] is False
        assert candidate["execution"] == "not_executed"
        assert "argv" not in candidate
        assert "cwd" not in candidate
        assert "env" not in candidate


def test_action_eligibility_rejects_path_escape() -> None:
    result = inspect_collaboration_action_eligibility(ROOT, "../outside.json")

    assert result.status == "validation_failed"
    assert _rule_ids(result) == {"collaboration-action-eligibility-path-escape"}


def test_action_eligibility_rejects_schema_failure(tmp_path: Path) -> None:
    data = _fixture_data()
    data["action_requests"][0]["action"] = "execute_shell"
    root = _project_root(tmp_path, data)

    result = inspect_collaboration_action_eligibility(root, "adapters/actions.json")

    assert result.status == "validation_failed"
    assert _rule_ids(result) == {"collaboration-action-eligibility-schema-invalid"}


def test_action_eligibility_rejects_invalid_run_source(tmp_path: Path) -> None:
    data = _fixture_data()
    data["run_state_file"] = "adapters/missing-run.json"
    root = _project_root(tmp_path, data)

    result = inspect_collaboration_action_eligibility(root, "adapters/actions.json")

    assert result.status == "validation_failed"
    assert "collaboration-action-eligibility-run-state-invalid" in _rule_ids(result)


def test_action_eligibility_rejects_duplicate_ids(tmp_path: Path) -> None:
    data = _fixture_data()
    data["approvals"][1]["approval_id"] = data["approvals"][0]["approval_id"]
    root = _project_root(tmp_path, data)

    result = inspect_collaboration_action_eligibility(root, "adapters/actions.json")

    assert "collaboration-action-eligibility-approval-id-duplicate" in _rule_ids(result)


def test_action_eligibility_blocks_checkpoint_out_of_range(tmp_path: Path) -> None:
    data = _fixture_data()
    data["action_requests"][0]["as_of_sequence"] = 999
    data["action_requests"][0]["expected_state"] = "awaiting_approval"
    data["approvals"][0]["binding"]["as_of_sequence"] = 999
    root = _project_root(tmp_path, data)

    result = inspect_collaboration_action_eligibility(root, "adapters/actions.json")

    item = _action(result, "approve_start")
    assert result.status == "pass"
    assert item["action_eligible"] is False
    assert item["blocked_reasons"] == ["checkpoint_out_of_range"]
    assert item["command_candidate"] is None


def test_action_eligibility_blocks_state_mismatch(tmp_path: Path) -> None:
    data = _fixture_data()
    data["action_requests"][0]["as_of_sequence"] = 4
    data["action_requests"][0]["expected_state"] = "awaiting_approval"
    data["approvals"][0]["binding"]["as_of_sequence"] = 4
    root = _project_root(tmp_path, data)

    result = inspect_collaboration_action_eligibility(root, "adapters/actions.json")

    item = _action(result, "approve_start")
    assert item["current_state"] == "running"
    assert item["blocked_reasons"] == ["target_state_mismatch"]


def test_action_eligibility_blocks_unapproved_fixture_approval(tmp_path: Path) -> None:
    data = _fixture_data()
    data["approvals"][1]["status"] = "pending"
    root = _project_root(tmp_path, data)

    result = inspect_collaboration_action_eligibility(root, "adapters/actions.json")

    item = _action(result, "cancel")
    assert item["approval_status"] == "pending"
    assert item["blocked_reasons"] == ["approval_not_approved"]


def test_action_eligibility_blocks_approval_binding_mismatch(tmp_path: Path) -> None:
    data = _fixture_data()
    data["approvals"][2]["binding"]["target_id"] = "attempt-plan-1"
    root = _project_root(tmp_path, data)

    result = inspect_collaboration_action_eligibility(root, "adapters/actions.json")

    item = _action(result, "retry")
    assert item["blocked_reasons"] == ["approval_binding_mismatch"]


def test_action_eligibility_blocks_recorded_idempotency_key(tmp_path: Path) -> None:
    baseline = inspect_collaboration_action_eligibility(ROOT, FIXTURE)
    retry_key = _action(baseline, "retry")["idempotency_key"]
    data = _fixture_data()
    data["recorded_idempotency_keys"] = [retry_key]
    root = _project_root(tmp_path, data)

    result = inspect_collaboration_action_eligibility(root, "adapters/actions.json")

    item = _action(result, "retry")
    assert item["blocked_reasons"] == ["command_already_recorded"]
    assert item["command_candidate"] is None


def test_action_eligibility_blocks_duplicate_command_in_same_projection(
    tmp_path: Path,
) -> None:
    data = _fixture_data()
    duplicate = dict(data["action_requests"][0])
    duplicate["request_id"] = "request-start-duplicate"
    data["action_requests"].append(duplicate)
    root = _project_root(tmp_path, data)

    result = inspect_collaboration_action_eligibility(root, "adapters/actions.json")

    duplicates = [
        item for item in result.actions if item["action"] == "approve_start"
    ]
    assert duplicates[0]["action_eligible"] is True
    assert duplicates[1]["action_eligible"] is False
    assert duplicates[1]["blocked_reasons"] == [
        "command_duplicate_in_projection"
    ]
    assert duplicates[1]["command_candidate"] is None


def test_action_eligibility_projection_is_deterministic() -> None:
    first = inspect_collaboration_action_eligibility(ROOT, FIXTURE).to_dict()
    second = inspect_collaboration_action_eligibility(ROOT, FIXTURE).to_dict()

    assert first == second
    assert first["action_projection_id"].startswith("sha256:")


def test_cli_action_eligibility_inspect_is_deterministic(capsys) -> None:
    args = [
        "orchestration", "collaboration", "action-eligibility", "inspect",
        "--file", FIXTURE, "--json",
    ]
    first_code = main(args)
    first = capsys.readouterr()
    second_code = main(args)
    second = capsys.readouterr()

    assert first_code == second_code == 0
    assert first.out == second.out
    assert first.err == second.err == ""
    payload = json.loads(first.out)
    assert payload["status"] == "pass"
    assert payload["summary"]["eligible_count"] == 5
    assert payload["guarantees"]["execution_authorized"] is False
