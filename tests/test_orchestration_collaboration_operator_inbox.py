"""Tests for Stage 81 current operator inbox and approval collection."""

from __future__ import annotations

import json
from pathlib import Path

from agent_runtime.cli import main
from agent_runtime.orchestration_collaboration_operator_inbox import (
    inspect_collaboration_operator_inbox,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = "adapters/collaboration-operator-inbox.example.json"


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
        "collaboration-run-state-current.example.json",
        "collaboration-operator-inbox.schema.json",
    ):
        (adapters / name).write_bytes((ROOT / "adapters" / name).read_bytes())
    (adapters / "inbox.json").write_text(
        json.dumps(data, ensure_ascii=False), encoding="utf-8"
    )
    return root


def _rule_ids(result) -> set[str]:
    return {item.rule_id for item in result.findings}


def _action(result, action: str) -> dict:
    return next(item for item in result.actions if item["action"] == action)


def test_operator_inbox_projects_latest_run_and_pending_approvals() -> None:
    result = inspect_collaboration_operator_inbox(ROOT, FIXTURE)

    assert result.status == "pass"
    assert result.guarantees == {
        "deterministic": True,
        "read_only": True,
        "fixture_backed": True,
        "approval_evidence": "fixture",
        "current_state_only": True,
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
    assert result.current_run["status"] == "blocked"
    assert result.summary == {
        "action_count": 5,
        "eligible_count": 1,
        "blocked_count": 4,
        "pending_approval_count": 1,
        "approved_fixture_count": 4,
        "current_attempt_count": 3,
        "current_review_count": 0,
        "current_handoff_count": 0,
    }
    assert len(result.pending_approvals) == 1
    assert result.pending_approvals[0]["approval_id"] == "approval-changes-current-001"

    cancel = _action(result, "cancel")
    assert cancel["current_state"] == "blocked"
    assert cancel["action_eligible"] is True
    assert cancel["command_candidate"]["execution"] == "not_executed"
    assert cancel["execution_authorized"] is False
    assert "argv" not in cancel["command_candidate"]
    assert "cwd" not in cancel["command_candidate"]
    assert "env" not in cancel["command_candidate"]

    changes = _action(result, "request_changes")
    assert changes["approval_status"] == "pending"
    assert "approval_not_approved" in changes["blocked_reasons"]


def test_operator_inbox_rejects_path_escape() -> None:
    result = inspect_collaboration_operator_inbox(ROOT, "../outside.json")

    assert result.status == "validation_failed"
    assert _rule_ids(result) == {"collaboration-operator-inbox-path-escape"}


def test_operator_inbox_rejects_schema_failure(tmp_path: Path) -> None:
    data = _fixture_data()
    data["action_requests"][0]["action"] = "execute_shell"
    root = _project_root(tmp_path, data)

    result = inspect_collaboration_operator_inbox(root, "adapters/inbox.json")

    assert result.status == "validation_failed"
    assert _rule_ids(result) == {"collaboration-operator-inbox-schema-invalid"}


def test_operator_inbox_rejects_invalid_current_run(tmp_path: Path) -> None:
    data = _fixture_data()
    data["run_state_file"] = "adapters/missing-current-run.json"
    root = _project_root(tmp_path, data)

    result = inspect_collaboration_operator_inbox(root, "adapters/inbox.json")

    assert result.status == "validation_failed"
    assert "collaboration-operator-inbox-run-state-invalid" in _rule_ids(result)


def test_operator_inbox_blocks_historical_attempt_as_stale_target(tmp_path: Path) -> None:
    data = _fixture_data()
    request = next(
        item for item in data["action_requests"] if item["action"] == "retry"
    )
    request["target_id"] = "attempt-implement-1"
    approval = next(
        item for item in data["approvals"] if item["approval_id"] == request["approval_id"]
    )
    approval["binding"]["target_id"] = "attempt-implement-1"
    root = _project_root(tmp_path, data)

    result = inspect_collaboration_operator_inbox(root, "adapters/inbox.json")

    retry = _action(result, "retry")
    assert retry["blocked_reasons"] == ["target_not_current"]


def test_operator_inbox_blocks_approval_binding_mismatch(tmp_path: Path) -> None:
    data = _fixture_data()
    approval = next(
        item for item in data["approvals"]
        if item["approval_id"] == "approval-cancel-current-001"
    )
    approval["binding"]["expected_state"] = "ready"
    root = _project_root(tmp_path, data)

    result = inspect_collaboration_operator_inbox(root, "adapters/inbox.json")

    cancel = _action(result, "cancel")
    assert "approval_binding_mismatch" in cancel["blocked_reasons"]


def test_operator_inbox_blocks_recorded_and_duplicate_idempotency_keys(
    tmp_path: Path,
) -> None:
    baseline = inspect_collaboration_operator_inbox(ROOT, FIXTURE)
    cancel = _action(baseline, "cancel")
    data = _fixture_data()
    data["recorded_idempotency_keys"] = [cancel["idempotency_key"]]
    duplicate = dict(next(item for item in data["action_requests"] if item["action"] == "cancel"))
    duplicate["request_id"] = "request-cancel-duplicate"
    data["action_requests"].append(duplicate)
    duplicate["approval_id"] = "approval-cancel-current-001"
    root = _project_root(tmp_path, data)

    result = inspect_collaboration_operator_inbox(root, "adapters/inbox.json")

    rows = [item for item in result.actions if item["action"] == "cancel"]
    assert "command_already_recorded" in rows[0]["blocked_reasons"]
    assert "command_already_recorded" in rows[1]["blocked_reasons"]
    assert "command_duplicate_in_projection" in rows[1]["blocked_reasons"]


def test_operator_inbox_projection_is_deterministic() -> None:
    first = inspect_collaboration_operator_inbox(ROOT, FIXTURE).to_dict()
    second = inspect_collaboration_operator_inbox(ROOT, FIXTURE).to_dict()

    assert first == second
    assert first["inbox_projection_id"].startswith("sha256:")


def test_cli_operator_inbox_inspect_is_deterministic(capsys) -> None:
    args = [
        "orchestration", "collaboration", "inbox", "inspect",
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
    assert payload["summary"]["pending_approval_count"] == 1
    assert payload["guarantees"]["current_state_only"] is True
