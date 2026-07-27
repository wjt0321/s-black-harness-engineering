"""Stage 82 design-only external Agent adapter contract tests."""

from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
ADAPTERS = ROOT / "adapters"
DOC = ROOT / "docs" / "archive" / "131-stage82-external-agent-adapter-contract-and-mvp-boundary.md"
CONTRACT_SCHEMA = ADAPTERS / "external-agent-adapter-contract.schema.json"
CONTRACT_EXAMPLE = ADAPTERS / "external-agent-adapter-contract.example.json"
LIVE_SCHEMA = ADAPTERS / "external-agent-live-read-model.schema.json"
LIVE_EXAMPLE = ADAPTERS / "external-agent-live-read-model.example.json"

FORBIDDEN_EXECUTION_KEYS = {
    "argv",
    "cwd",
    "env",
    "environment",
    "shell",
    "command",
    "command_line",
    "executable",
}
EXPECTED_FAILURE_CODES = {
    "identity_binding_mismatch",
    "contract_version_unsupported",
    "capability_not_declared",
    "readiness_missing",
    "readiness_expired",
    "readiness_binding_drift",
    "session_mapping_conflict",
    "approval_missing",
    "approval_not_granted",
    "approval_expired",
    "approval_revoked",
    "approval_binding_drift",
    "expected_state_stale",
    "lease_unavailable",
    "idempotency_replay",
    "transport_unavailable",
    "dispatch_rejected",
    "event_duplicate_conflict",
    "event_sequence_gap",
    "transport_disconnected",
    "cancel_unsupported",
    "cancel_outcome_unknown",
    "artifact_integrity_failed",
    "review_contract_invalid",
    "terminal_audit_conflict",
}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def walk_keys(value: object) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            keys.add(key)
            keys.update(walk_keys(child))
    elif isinstance(value, list):
        for child in value:
            keys.update(walk_keys(child))
    return keys


def test_stage82_schemas_are_valid_and_examples_conform() -> None:
    for schema_path, example_path in (
        (CONTRACT_SCHEMA, CONTRACT_EXAMPLE),
        (LIVE_SCHEMA, LIVE_EXAMPLE),
    ):
        schema = load_json(schema_path)
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(load_json(example_path))


def test_contract_example_proves_transport_and_role_neutrality() -> None:
    contract = load_json(CONTRACT_EXAMPLE)
    assert contract["design_status"] == "design_only"
    assert contract["authority"]["dispatch_authority"] == "harness_only"
    assert all(value is False for value in contract["safety"].values())

    adapters = contract["adapters"]
    assert {item["identity"]["transport"]["kind"] for item in adapters} == {
        "acp",
        "cli",
        "local_process",
    }
    roles = {
        role
        for item in adapters
        for capability in item["capability_manifest"]["capabilities"]
        for role in capability["roles"]
    }
    assert roles == {"planner", "executor", "reviewer"}
    assert len({item["identity"]["adapter_id"] for item in adapters}) == len(adapters)


def test_dispatch_contract_is_structured_and_exactly_bound() -> None:
    contract = load_json(CONTRACT_EXAMPLE)
    dispatch = contract["protocol_examples"]["dispatch_envelope"]
    assert dispatch["fixture_only"] is True
    assert dispatch["execution_authorized"] is False
    assert dispatch["authorization_source"] == "harness_control_plane"
    assert dispatch["expected_state"]["run_projection_id"].startswith("sha256:")
    assert dispatch["readiness_evidence"]["evidence_id"].startswith("sha256:")
    assert dispatch["approval_evidence"]["status"] == "granted"
    assert dispatch["approval_evidence"]["target"]["attempt_id"] == dispatch["attempt_id"]
    assert dispatch["lease"]["lease_id"]
    assert dispatch["idempotency_key"].startswith("sha256:")
    assert not (walk_keys(dispatch) & FORBIDDEN_EXECUTION_KEYS)


def test_event_contract_is_ordered_deduplicated_and_terminal_once() -> None:
    contract = load_json(CONTRACT_EXAMPLE)
    events = contract["protocol_examples"]["ordered_events"]
    assert [event["sequence"] for event in events] == list(range(1, len(events) + 1))
    assert len({event["deduplication_key"] for event in events}) == len(events)
    assert sum(event["terminal"] for event in events) == 1
    assert events[-1]["event_type"] == "terminal_outcome_unknown"
    assert events[-1]["outcome"] == "outcome_unknown"
    assert events[-1]["reconciliation_required"] is True


def test_failure_matrix_and_stop_line_are_frozen() -> None:
    contract = load_json(CONTRACT_EXAMPLE)
    codes = {item["code"] for item in contract["failure_matrix"]}
    assert codes == EXPECTED_FAILURE_CODES

    document = DOC.read_text(encoding="utf-8")
    for code in EXPECTED_FAILURE_CODES:
        assert f"`{code}`" in document
    for stop_line in (
        "不调用 Agent",
        "不启动 session",
        "不读取真实 approval ledger",
        "不新增第三个真实 operation",
        "不实现网络 adapter",
    ):
        assert stop_line in document


def test_live_read_model_is_bounded_chinese_first_and_non_authorizing() -> None:
    model = load_json(LIVE_EXAMPLE)
    assert model["mode"] == "fixture"
    assert model["execution_authorized"] is False
    assert model["dispatch_enabled"] is False
    assert model["source"]["live_observation_performed"] is False
    assert model["source"]["real_approval_ledger_read"] is False
    assert {agent["transport"]["kind"] for agent in model["agents"]} == {
        "acp",
        "cli",
        "local_process",
    }
    assert all(agent["display_name_zh"] for agent in model["agents"])
    assert all(agent["status_label_zh"] for agent in model["agents"])
    assert all(event["safe_summary_zh"] for event in model["recent_events"])
    assert not (walk_keys(model) & FORBIDDEN_EXECUTION_KEYS)

    schema = load_json(LIVE_SCHEMA)
    arrays = schema["properties"]
    for field in ("agents", "work_items", "recent_events", "approvals", "artifacts", "recovery_items"):
        assert arrays[field]["maxItems"] <= 128
