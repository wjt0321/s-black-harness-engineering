"""Tests for the Stage 18 standalone Control Panel handoff consumer."""

from __future__ import annotations

import importlib
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
