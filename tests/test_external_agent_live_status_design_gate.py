"""Stage 83 design-only external Agent live-status adapter tests."""

from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
ADAPTERS = ROOT / "adapters"
SNAPSHOT_SCHEMA = ADAPTERS / "external-agent-status-snapshot.schema.json"
SNAPSHOT_EXAMPLE = ADAPTERS / "external-agent-status-snapshot.example.json"
ADAPTER_SCHEMA = ADAPTERS / "external-agent-live-status-adapter.schema.json"
ADAPTER_EXAMPLE = ADAPTERS / "external-agent-live-status-adapter.example.json"
STAGE82_LIVE_SCHEMA = ADAPTERS / "external-agent-live-read-model.schema.json"
DOC = ROOT / "docs" / "archive" / "132-stage83-external-agent-read-only-live-status-adapter-design-gate.md"

FORBIDDEN_KEYS = {
    "argv", "cwd", "env", "environment", "command", "command_line", "shell",
    "prompt", "token", "credential", "secret", "endpoint", "url", "pid",
    "process_path", "session_id", "stdout", "stderr", "raw_output",
}
EXPECTED_FAILURE_CODES = {
    "status_source_missing",
    "status_source_not_regular",
    "status_source_indirection_blocked",
    "status_source_too_large",
    "status_source_unreadable",
    "status_source_schema_invalid",
    "status_snapshot_incomplete",
    "status_snapshot_replayed",
    "status_observation_from_future",
    "status_observation_expired",
    "status_identity_binding_mismatch",
    "status_producer_binding_missing",
    "status_producer_binding_drift",
    "status_target_not_observed",
    "status_unbound_session_observed",
    "status_projection_invalid",
}


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def keys(value: object) -> set[str]:
    result: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            result.add(key)
            result.update(keys(child))
    elif isinstance(value, list):
        for child in value:
            result.update(keys(child))
    return result


def test_stage83_schemas_are_valid_and_examples_conform() -> None:
    for schema_path, example_path in (
        (SNAPSHOT_SCHEMA, SNAPSHOT_EXAMPLE),
        (ADAPTER_SCHEMA, ADAPTER_EXAMPLE),
    ):
        schema = load(schema_path)
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(load(example_path))


def test_selected_surface_is_fixed_atomic_snapshot_for_one_agent() -> None:
    design = load(ADAPTER_EXAMPLE)
    assert design["design_status"] == "reader_implemented"
    assert design["selected_target"]["adapter_id"] == "omp-acp"
    assert design["selected_target"]["implementation_id"] == "omp-pi"
    surface = design["observation_surface"]
    assert surface["kind"] == "adapter_owned_atomic_snapshot"
    assert surface["production_relative_path"] == ".runtime/external-agent-status/omp-acp.v1.json"
    assert surface["path_override_allowed"] is False
    assert surface["max_bytes"] == 64 * 1024
    assert surface["ttl_default_seconds"] == 15
    assert surface["ttl_max_seconds"] == 60

    snapshot_schema = load(SNAPSHOT_SCHEMA)
    transport_kinds = snapshot_schema["properties"]["target"]["properties"]["transport"]["properties"]["kind"]["enum"]
    assert set(transport_kinds) == {"acp", "cli", "local_process"}


def test_reader_and_producer_boundaries_are_fail_closed() -> None:
    design = load(ADAPTER_EXAMPLE)
    reader = design["reader_policy"]
    assert reader == {
        "project_contained": True,
        "fixed_path_only": True,
        "regular_file_required": True,
        "symlink_allowed": False,
        "reparse_point_allowed": False,
        "hardlink_allowed": False,
        "stable_stat_before_after": True,
        "strict_utf8_json": True,
        "writes_files": False,
    }
    producer = design["producer_policy"]
    assert producer["owned_by_harness"] is False
    assert producer["reviewed_binding_required"] is True
    assert producer["atomic_temp_replace_required"] is True
    assert producer["partial_snapshot_accepted"] is False


def test_design_performs_no_live_probe_and_grants_no_authority() -> None:
    design = load(ADAPTER_EXAMPLE)
    assert all(value is False for value in design["safety"].values())
    snapshot = load(SNAPSHOT_EXAMPLE)
    assert snapshot["complete"] is True
    assert all(value is False for value in snapshot["producer_attestation"].values())
    assert not (keys(snapshot) & FORBIDDEN_KEYS)
    assert not (keys(design) & FORBIDDEN_KEYS)


def test_normalized_evidence_is_bound_but_never_ready() -> None:
    design = load(ADAPTER_EXAMPLE)
    evidence = design["protocol_example"]["normalized_evidence"]
    target = design["selected_target"]
    assert evidence["target"] == target
    assert evidence["observation_status"] == "observed"
    assert evidence["readiness_status"] == "unknown"
    assert evidence["readiness_level"] == "runner_listed"
    assert evidence["session_binding"] is None
    assert evidence["event_cursor"] is None
    assert evidence["sufficient_for_dispatch"] is False
    assert evidence["execution_authorized"] is False
    assert evidence["evidence_id"].startswith("sha256:")


def test_gui_mapping_is_compatible_and_never_maps_observed_to_ready() -> None:
    design = load(ADAPTER_EXAMPLE)
    mappings = {item["observation_status"]: item for item in design["gui_mapping"]}
    assert mappings["observed"]["agent_status"] == "unknown"
    assert mappings["observed"]["readiness_status"] == "unknown"
    assert mappings["observed"]["session_projection"] == "none"
    assert mappings["unavailable"]["agent_status"] == "disconnected"
    assert mappings["stale"]["agent_status"] == "stale"
    assert mappings["blocked"]["agent_status"] == "blocked"

    stage82 = load(STAGE82_LIVE_SCHEMA)
    allowed_agent = set(stage82["properties"]["agents"]["items"]["properties"]["status"]["enum"])
    allowed_readiness = set(stage82["properties"]["agents"]["items"]["properties"]["readiness"]["properties"]["status"]["enum"])
    assert {item["agent_status"] for item in mappings.values()} <= allowed_agent
    assert {item["readiness_status"] for item in mappings.values()} <= allowed_readiness


def test_failure_matrix_alternatives_and_stop_lines_are_frozen() -> None:
    design = load(ADAPTER_EXAMPLE)
    assert {item["code"] for item in design["failure_matrix"]} == EXPECTED_FAILURE_CODES
    assert design["alternatives"]["fixed_cli_status"]["decision"] == "deferred"
    assert design["alternatives"]["acp_handshake"]["decision"] == "deferred"
    assert design["implementation_gate"]["reader_implementation_authorized"] is True
    assert design["implementation_gate"]["producer_or_probe_authorized"] is False

    document = DOC.read_text(encoding="utf-8")
    for code in EXPECTED_FAILURE_CODES:
        assert f"`{code}`" in document
    for stop_line in (
        "不启动进程",
        "不连接 ACP",
        "不启动 session",
        "不发送 prompt",
        "不读取凭据",
        "不创建真实 snapshot",
        "不授予 dispatch authority",
    ):
        assert stop_line in document
