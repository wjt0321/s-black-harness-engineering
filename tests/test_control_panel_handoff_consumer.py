"""Tests for the Stage 18 standalone Control Panel handoff consumer."""

from __future__ import annotations

import copy
import hashlib
import importlib
import json
from pathlib import Path

from agent_runtime.orchestration_control_panel import build_control_panel_handoff

ROOT = Path(__file__).resolve().parents[1]
ENVELOPE = "adapters/execution-envelope.examples.json"
EXPECTED_CHECKS = [
    "document_shape",
    "schema_version",
    "producer_status",
    "handoff_identity",
    "render_identity",
    "representations",
    "argv",
    "boundaries",
]


def test_reference_consumer_accepts_valid_handoff() -> None:
    consumer = importlib.import_module("tools.control_panel_handoff_consumer")
    handoff = build_control_panel_handoff(
        ROOT,
        envelope_file=ENVELOPE,
    ).to_dict()

    result = consumer.validate_handoff_document(handoff)
    payload = result.to_dict()

    assert result.status == "pass"
    assert result.exit_code() == 0
    assert list(payload) == [
        "status",
        "schema_version",
        "consumer",
        "source_handoff_id",
        "checks",
        "findings",
        "guarantees",
        "next_action",
    ]
    assert payload["schema_version"] == (
        "control-plane/control-panel-host-consumer-validation/v1"
    )
    assert payload["consumer"] == "local-reference-consumer/v1"
    assert payload["source_handoff_id"] == handoff["handoff_id"]
    assert payload["checks"] == [
        {"check_id": check_id, "status": "pass"}
        for check_id in EXPECTED_CHECKS
    ]
    assert payload["findings"] == []
    assert payload["guarantees"] == {
        "stdin_only": True,
        "read_only": True,
        "writes_files": False,
        "accesses_network": False,
        "reads_representations": False,
        "executes_commands": False,
        "executes_adapters": False,
        "starts_service": False,
    }
    assert payload["next_action"] == {
        "code": "accept_handoff",
        "message": "The handoff descriptor passed local reference validation.",
    }



def _consumer():
    return importlib.import_module("tools.control_panel_handoff_consumer")


def _valid_handoff() -> dict[str, object]:
    return build_control_panel_handoff(
        ROOT,
        envelope_file=ENVELOPE,
    ).to_dict()


def _canonical_id(payload: dict[str, object]) -> str:
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(canonical).hexdigest()}"


def _rehash_handoff(payload: dict[str, object]) -> None:
    without_id = {key: value for key, value in payload.items() if key != "handoff_id"}
    payload["handoff_id"] = _canonical_id(without_id)


def _assert_failure(
    payload: dict[str, object],
    *,
    status: str,
    exit_code: int,
    failed_check: str,
    rule_id: str,
) -> None:
    result = _consumer().validate_handoff_document(payload)
    result_payload = result.to_dict()

    assert result.status == status
    assert result.exit_code() == exit_code
    checks = {
        item["check_id"]: item["status"]
        for item in result_payload["checks"]
    }
    assert checks[failed_check] == "failed"
    assert rule_id in {
        finding["rule_id"] for finding in result_payload["findings"]
    }
    serialized = json.dumps(result_payload, ensure_ascii=False)
    assert ENVELOPE not in serialized
    assert "python" not in serialized


def test_reference_consumer_rejects_unknown_top_level_field() -> None:
    payload = _valid_handoff()
    payload["unexpected"] = "sentinel-do-not-echo"
    _rehash_handoff(payload)

    _assert_failure(
        payload,
        status="validation_failed",
        exit_code=5,
        failed_check="document_shape",
        rule_id="consumer-document-shape",
    )
    assert "sentinel-do-not-echo" not in json.dumps(
        _consumer().validate_handoff_document(payload).to_dict()
    )


def test_reference_consumer_rejects_missing_required_field() -> None:
    payload = _valid_handoff()
    del payload["render"]
    _rehash_handoff(payload)

    _assert_failure(
        payload,
        status="validation_failed",
        exit_code=5,
        failed_check="document_shape",
        rule_id="consumer-document-shape",
    )


def test_reference_consumer_rejects_wrong_nested_type() -> None:
    payload = _valid_handoff()
    payload["snapshot"]["scoped_unavailable"] = "not-a-list"
    _rehash_handoff(payload)

    _assert_failure(
        payload,
        status="validation_failed",
        exit_code=5,
        failed_check="document_shape",
        rule_id="consumer-document-shape",
    )


def test_reference_consumer_blocks_unsupported_schema() -> None:
    payload = _valid_handoff()
    payload["schema_version"] = "control-plane/control-panel-handoff/v2"
    _rehash_handoff(payload)

    _assert_failure(
        payload,
        status="blocked",
        exit_code=2,
        failed_check="schema_version",
        rule_id="consumer-unsupported-schema",
    )


def test_reference_consumer_rejects_handoff_identity_mismatch() -> None:
    payload = _valid_handoff()
    payload["handoff_id"] = "sha256:" + "0" * 64

    _assert_failure(
        payload,
        status="validation_failed",
        exit_code=5,
        failed_check="handoff_identity",
        rule_id="consumer-handoff-id-mismatch",
    )


def test_reference_consumer_rejects_render_identity_mismatch() -> None:
    payload = _valid_handoff()
    payload["render"]["render_id"] = "sha256:" + "0" * 64
    _rehash_handoff(payload)

    _assert_failure(
        payload,
        status="validation_failed",
        exit_code=5,
        failed_check="render_identity",
        rule_id="consumer-render-id-mismatch",
    )


def test_reference_consumer_rejects_representation_metadata_drift() -> None:
    payload = _valid_handoff()
    payload["snapshot"]["working_directory"] = "D:/private/workspace"
    _rehash_handoff(payload)

    _assert_failure(
        payload,
        status="validation_failed",
        exit_code=5,
        failed_check="representations",
        rule_id="consumer-representation-invalid",
    )
    assert "D:/private/workspace" not in json.dumps(
        _consumer().validate_handoff_document(payload).to_dict()
    )


def test_reference_consumer_rejects_absolute_source_path() -> None:
    payload = _valid_handoff()
    payload["source"]["envelope_file"] = "D:/private/envelope.json"
    _rehash_handoff(payload)

    _assert_failure(
        payload,
        status="validation_failed",
        exit_code=5,
        failed_check="representations",
        rule_id="consumer-representation-invalid",
    )


def test_reference_consumer_rejects_invalid_argv_shape() -> None:
    payload = _valid_handoff()
    payload["render"]["argv"] = ["python", 7]
    _rehash_handoff(payload)

    _assert_failure(
        payload,
        status="validation_failed",
        exit_code=5,
        failed_check="argv",
        rule_id="consumer-argv-invalid",
    )


def test_reference_consumer_blocks_unsafe_boundary() -> None:
    payload = _valid_handoff()
    payload["boundaries"]["executes_commands"] = True
    _rehash_handoff(payload)

    _assert_failure(
        payload,
        status="blocked",
        exit_code=2,
        failed_check="boundaries",
        rule_id="consumer-unsafe-boundary",
    )


def test_reference_consumer_blocks_producer_error_descriptor() -> None:
    payload = build_control_panel_handoff(
        ROOT,
        envelope_file="adapters/missing-envelope.json",
    ).to_dict()

    _assert_failure(
        payload,
        status="blocked",
        exit_code=2,
        failed_check="producer_status",
        rule_id="consumer-producer-not-pass",
    )
