"""阶段 85：外部智能体状态采集方案设计评审契约测试。"""

from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator, validate

from agent_runtime.orchestration_contract import build_contract_manifest

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "adapters/external-agent-status-collector-design.schema.json"
EXAMPLE = ROOT / "adapters/external-agent-status-collector-design.example.json"
FACT_SOURCE = ROOT / "docs/archive/134-stage85-external-agent-status-collection-design-review.md"

EXPECTED_FAILURE_CODES = {
    "collector_host_hook_unverified",
    "collector_identity_unbound",
    "collector_host_not_running",
    "collector_registry_unavailable",
    "collector_source_ambiguous",
    "collector_lease_unavailable",
    "collector_existing_snapshot_invalid",
    "collector_generation_conflict",
    "collector_temp_path_unsafe",
    "collector_snapshot_too_large",
    "collector_snapshot_validation_failed",
    "collector_atomic_replace_failed",
    "collector_postcheck_failed",
    "collector_cleanup_failed",
    "collector_side_effect_boundary_violated",
}


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_collection_design_schema_and_fixture_are_strict_and_valid() -> None:
    schema = load(SCHEMA)
    example = load(EXAMPLE)
    Draft202012Validator.check_schema(schema)
    validate(example, schema)
    assert schema["additionalProperties"] is False
    assert example["contract"] == "external-agent-status-collector-design/v1"
    assert example["design_status"] == "complete_implementation_blocked"


def test_selected_approach_is_host_owned_passive_publication() -> None:
    design = load(EXAMPLE)
    selected = design["selected_approach"]
    assert selected == {
        "approach_id": "host_owned_passive_atomic_publisher",
        "owner": "external_agent_host",
        "host_id": "qwenpaw-host",
        "source": "existing_in_memory_runner_registry",
        "trigger": "event_driven_with_bounded_heartbeat",
        "heartbeat_seconds": 5,
        "requires_verified_host_hook": True,
        "active_probe": False,
        "starts_new_process": False,
        "opens_new_connection": False,
    }


def test_publication_contract_is_fixed_atomic_and_single_writer() -> None:
    publication = load(EXAMPLE)["publication"]
    assert publication["snapshot_relative_path"] == ".runtime/external-agent-status/omp-acp.v1.json"
    assert publication["temp_relative_path"] == ".runtime/external-agent-status/.omp-acp.v1.json.tmp"
    assert publication["lease_relative_path"] == ".runtime/external-agent-status/omp-acp.v1.publisher.lock"
    assert publication["max_bytes"] == 65536
    assert publication["ttl_seconds"] == 15
    assert publication["single_writer_required"] is True
    assert publication["atomic_temp_replace_required"] is True
    assert publication["fsync_before_replace"] is True
    assert publication["post_replace_validation"] is True
    assert publication["overwrite_invalid_existing_snapshot"] is False
    assert publication["generation_rule"] == "previous_valid_generation_plus_one"


def test_design_keeps_all_runtime_side_effects_unimplemented_and_non_authorizing() -> None:
    design = load(EXAMPLE)
    safety = design["safety"]
    assert safety == {
        "implementation_present": False,
        "starts_process": False,
        "connects_acp": False,
        "opens_session": False,
        "sends_prompt": False,
        "invokes_model": False,
        "reads_credentials": False,
        "accesses_network": False,
        "creates_background_service": False,
        "writes_snapshot_when_implemented": True,
        "writes_harness_ledger": False,
        "grants_execution_authority": False,
        "enables_dispatch": False,
    }
    gate = design["implementation_gate"]
    assert gate["design_complete"] is True
    assert gate["implementation_authorized"] is False
    assert gate["real_observation_authorized"] is False
    assert gate["requires_explicit_user_authorization"] is True
    assert len(gate["missing_evidence"]) >= 5


def test_trust_model_admits_current_binding_is_only_a_placeholder() -> None:
    design = load(EXAMPLE)
    trust = design["trust"]
    assert trust["current_binding_status"] == "placeholder_unobserved"
    assert trust["content_binding_is_process_attestation"] is False
    assert trust["sufficient_for_dispatch"] is False
    assert trust["required_before_implementation"] == [
        "verified_host_hook_name_and_version",
        "observed_publisher_package_version_and_digest",
        "reviewed_write_directory_acl_and_owner",
        "crash_recovery_and_atomic_replace_test_harness",
        "explicit_implementation_authorization",
    ]


def test_active_probe_alternatives_remain_deferred_or_rejected() -> None:
    alternatives = {
        item["approach_id"]: item
        for item in load(EXAMPLE)["alternatives"]
    }
    assert alternatives["harness_fixed_cli_status"]["decision"] == "deferred"
    assert alternatives["harness_acp_handshake"]["decision"] == "deferred"
    assert alternatives["standalone_polling_service"]["decision"] == "rejected"
    assert alternatives["host_owned_passive_atomic_publisher"]["decision"] == "selected_but_blocked"


def test_failure_matrix_and_stop_line_are_complete() -> None:
    design = load(EXAMPLE)
    assert {item["code"] for item in design["failure_matrix"]} == EXPECTED_FAILURE_CODES
    document = FACT_SOURCE.read_text(encoding="utf-8")
    assert "# 134 — 阶段 85：外部智能体状态采集方案设计评审" in document
    assert "不实现状态采集器" in document
    assert "不启动外部智能体" in document
    assert "不连接 ACP" in document
    assert "不读取凭据" in document
    assert "不写 Harness ledger" in document


def test_no_status_publisher_or_probe_command_is_exposed() -> None:
    commands = {
        command
        for entry in build_contract_manifest().entries
        for command in entry.commands
    }
    assert ("orchestration", "external-agent", "status", "publish") not in commands
    assert ("orchestration", "external-agent", "status", "probe") not in commands
    assert ("orchestration", "external-agent", "status", "inspect") in commands


def test_active_user_facing_docs_do_not_use_the_old_mixed_title() -> None:
    files = [
        ROOT / "README.md",
        ROOT / "docs/000-stage-digest.md",
        ROOT / "docs/02-roadmap.md",
        ROOT / "tasks/handoff-2026-07-27.md",
    ]
    for path in files:
        text = path.read_text(encoding="utf-8")
        assert "external Agent status producer/probe design gate" not in text


def test_stage84_reader_binding_remains_non_authorizing_placeholder() -> None:
    binding = load(ROOT / "adapters/external-agent-live-status-binding.json")
    assert binding["expected_producer"]["producer_version"] == "design-unobserved"
    assert binding["producer_or_probe_authorized"] is False
    assert binding["dispatch_authorized"] is False
