"""Tests for the Stage 29 filtered snapshot stdin consumer."""

from __future__ import annotations

import ast
import copy
import hashlib
import importlib.util
import io
import json
from functools import lru_cache
from pathlib import Path
import subprocess
import sys
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "codex_desktop_filtered_snapshot_consumer.py"
ENVELOPE = "adapters/execution-envelope.examples.json"
TASK_ID = "task-20260703-001"
REQUEST_ID = "req-20260703-001"
MAX_INPUT_BYTES = 1024 * 1024
MAX_OUTPUT_BYTES = 64 * 1024
EXPECTED_CHECKS = [
    "document_shape",
    "schema_version",
    "reader_status",
    "lifecycle",
    "guarantees",
    "source_scope_identity",
    "filter_identity",
    "representation_links",
    "view_identity",
    "safe_sections",
    "filter_semantics",
]
EXPECTED_RESULT_GUARANTEES = {
    "stdin_only": True,
    "read_only": True,
    "reads_filtered_snapshot": True,
    "writes_files": False,
    "accesses_network": False,
    "starts_service": False,
    "executes_reader": False,
    "executes_commands": False,
    "executes_adapters": False,
    "persists_input": False,
    "bounded_input": True,
    "bounded_output": True,
}


def _consumer():
    assert TOOL.is_file(), "Stage 29 consumer has not been implemented"
    spec = importlib.util.spec_from_file_location(
        "codex_desktop_filtered_snapshot_consumer",
        TOOL,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@lru_cache(maxsize=4)
def _reader_bytes(filter_flag: str, filter_value: str) -> bytes:
    process = subprocess.run(
        [
            sys.executable,
            "tools/codex_desktop_snapshot_json_reader.py",
            "--project-root",
            ".",
            "--representation",
            "snapshot-json",
            "--envelope",
            ENVELOPE,
            filter_flag,
            filter_value,
            "--json",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
    )
    assert process.returncode == 0
    assert process.stderr == b""
    return process.stdout


def _valid_document(*, task: bool = False) -> dict[str, Any]:
    if task:
        raw = _reader_bytes("--task-id", TASK_ID)
    else:
        raw = _reader_bytes("--request-id", REQUEST_ID)
    document = json.loads(raw)
    assert isinstance(document, dict)
    return copy.deepcopy(document)


def _canonical_id(payload: dict[str, Any]) -> str:
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(canonical).hexdigest()}"


def _rehash_view(document: dict[str, Any]) -> None:
    payload = document["representation"]["payload"]
    payload["view_id"] = _canonical_id(
        {key: value for key, value in payload.items() if key != "view_id"}
    )
    document["representation"]["view_id"] = payload["view_id"]


def _rehash_filter_and_view(document: dict[str, Any]) -> None:
    payload = document["representation"]["payload"]
    filter_id = _canonical_id(payload["filter"])
    document["source"]["filter_id"] = filter_id
    payload["source"]["filter_id"] = filter_id
    _rehash_view(document)


def _assert_failure(
    document: object,
    *,
    status: str,
    exit_code: int,
    failed_check: str,
    rule_id: str,
) -> dict[str, Any]:
    consumer = _consumer()
    result = consumer.validate_filtered_snapshot_document(document)
    payload = result.to_dict()
    assert result.status == status
    assert result.exit_code() == exit_code
    states = {item["check_id"]: item["status"] for item in payload["checks"]}
    assert states[failed_check] == "failed"
    assert rule_id in {item["rule_id"] for item in payload["findings"]}
    return payload


def test_consumer_accepts_real_request_filtered_v3() -> None:
    consumer = _consumer()
    document = _valid_document()

    result = consumer.validate_filtered_snapshot_document(document)
    payload = result.to_dict()

    assert result.status == "pass"
    assert result.exit_code() == 0
    assert list(payload) == [
        "status",
        "schema_version",
        "consumer",
        "source",
        "checks",
        "findings",
        "guarantees",
        "next_action",
    ]
    assert payload["schema_version"] == (
        "control-plane/filtered-snapshot-host-consumer-validation/v1"
    )
    assert payload["consumer"] == "codex-desktop-filtered-snapshot-consumer/v1"
    assert payload["source"] == {
        "base_snapshot_id": document["representation"]["base_snapshot_id"],
        "scope_id": document["source"]["scope_id"],
        "filter_id": document["source"]["filter_id"],
        "view_id": document["representation"]["view_id"],
    }
    assert payload["checks"] == [
        {"check_id": check_id, "status": "pass"}
        for check_id in EXPECTED_CHECKS
    ]
    assert payload["findings"] == []
    assert payload["guarantees"] == EXPECTED_RESULT_GUARANTEES
    assert payload["next_action"] == {
        "code": "accept_filtered_snapshot",
        "message": "The filtered snapshot passed local consumer validation.",
    }


def test_consumer_accepts_task_relation_closure_and_is_deterministic() -> None:
    consumer = _consumer()
    document = _valid_document(task=True)

    first = consumer.validate_filtered_snapshot_document(document).to_dict()
    second = consumer.validate_filtered_snapshot_document(document).to_dict()

    assert first == second
    assert first["status"] == "pass"
    serialized = json.dumps(first, ensure_ascii=False, sort_keys=True).encode("utf-8")
    assert len(serialized) <= MAX_OUTPUT_BYTES
    assert TASK_ID not in serialized.decode("utf-8")
    assert REQUEST_ID not in serialized.decode("utf-8")
    assert ENVELOPE not in serialized.decode("utf-8")


def test_consumer_rejects_unknown_document_field_without_echoing_value() -> None:
    document = _valid_document()
    marker = "PRIVATE_STAGE29_SENTINEL"
    document["unexpected"] = marker

    payload = _assert_failure(
        document,
        status="validation_failed",
        exit_code=5,
        failed_check="document_shape",
        rule_id="filtered-consumer-document-shape",
    )
    assert marker not in json.dumps(payload, ensure_ascii=False)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("schema_version", "control-plane/codex-desktop-snapshot-read/v4"),
        ("reader", "codex-desktop-filtered-envelope-snapshot-json-reader/v4"),
    ],
)
def test_consumer_blocks_unsupported_schema_or_reader(
    field: str,
    value: str,
) -> None:
    document = _valid_document()
    document[field] = value

    _assert_failure(
        document,
        status="blocked",
        exit_code=2,
        failed_check="schema_version",
        rule_id="filtered-consumer-unsupported-schema",
    )


@pytest.mark.parametrize("schema_location", ["payload", "filter"])
def test_consumer_blocks_unsupported_nested_schema(schema_location: str) -> None:
    document = _valid_document()
    payload = document["representation"]["payload"]
    if schema_location == "payload":
        payload["schema_version"] = "control-plane/filtered-envelope-snapshot/v2"
    else:
        payload["filter"]["schema_version"] = (
            "control-plane/envelope-snapshot-filter/v2"
        )
        _rehash_filter_and_view(document)

    _assert_failure(
        document,
        status="blocked",
        exit_code=2,
        failed_check="schema_version",
        rule_id="filtered-consumer-unsupported-schema",
    )


def test_consumer_blocks_non_ready_reader_before_payload_use() -> None:
    document = _valid_document()
    document["status"] = "blocked"

    _assert_failure(
        document,
        status="blocked",
        exit_code=2,
        failed_check="reader_status",
        rule_id="filtered-consumer-reader-not-ready",
    )


def test_consumer_rejects_lifecycle_drift() -> None:
    document = _valid_document()
    document["lifecycle"]["phases"][-1] = "not_closed"

    _assert_failure(
        document,
        status="validation_failed",
        exit_code=5,
        failed_check="lifecycle",
        rule_id="filtered-consumer-lifecycle-invalid",
    )


def test_consumer_blocks_unsafe_guarantee() -> None:
    document = _valid_document()
    document["guarantees"]["writes_files"] = True

    _assert_failure(
        document,
        status="blocked",
        exit_code=2,
        failed_check="guarantees",
        rule_id="filtered-consumer-guarantee-unsafe",
    )


def test_consumer_rejects_guarantee_shape_drift() -> None:
    document = _valid_document()
    del document["guarantees"]["writes_files"]

    _assert_failure(
        document,
        status="validation_failed",
        exit_code=5,
        failed_check="guarantees",
        rule_id="filtered-consumer-guarantee-shape",
    )


def test_consumer_rejects_scope_identity_mismatch() -> None:
    document = _valid_document()
    document["source"]["scope_id"] = "sha256:" + "0" * 64

    _assert_failure(
        document,
        status="validation_failed",
        exit_code=5,
        failed_check="source_scope_identity",
        rule_id="filtered-consumer-scope-id-mismatch",
    )


def test_consumer_rejects_filter_identity_mismatch() -> None:
    document = _valid_document()
    document["source"]["filter_id"] = "sha256:" + "0" * 64

    _assert_failure(
        document,
        status="validation_failed",
        exit_code=5,
        failed_check="filter_identity",
        rule_id="filtered-consumer-filter-id-mismatch",
    )


def test_consumer_rejects_base_snapshot_link_mismatch() -> None:
    document = _valid_document()
    document["representation"]["base_snapshot_id"] = "sha256:" + "0" * 64

    _assert_failure(
        document,
        status="validation_failed",
        exit_code=5,
        failed_check="representation_links",
        rule_id="filtered-consumer-representation-links",
    )


def test_consumer_rejects_view_identity_mismatch() -> None:
    document = _valid_document()
    document["representation"]["view_id"] = "sha256:" + "0" * 64

    _assert_failure(
        document,
        status="validation_failed",
        exit_code=5,
        failed_check="view_identity",
        rule_id="filtered-consumer-view-id-mismatch",
    )


@pytest.mark.parametrize("mutation", ["unknown_section", "count", "nested_value"])
def test_consumer_rejects_unsafe_section_shape(mutation: str) -> None:
    document = _valid_document()
    payload = document["representation"]["payload"]
    if mutation == "unknown_section":
        payload["sections"]["project"] = {"status": "pass"}
    elif mutation == "count":
        payload["summary"]["run_count"] += 1
    else:
        payload["sections"]["runs"]["runs"][0]["raw"] = {"secret": "x"}
    _rehash_view(document)

    _assert_failure(
        document,
        status="validation_failed",
        exit_code=5,
        failed_check="safe_sections",
        rule_id="filtered-consumer-safe-sections",
    )


def test_consumer_rejects_request_filter_semantics_mismatch() -> None:
    document = _valid_document()
    payload = document["representation"]["payload"]
    payload["sections"]["artifacts"]["artifacts"][0]["request_id"] = (
        "req-20260703-999"
    )
    _rehash_view(document)

    _assert_failure(
        document,
        status="validation_failed",
        exit_code=5,
        failed_check="filter_semantics",
        rule_id="filtered-consumer-filter-semantics",
    )


def test_consumer_rejects_task_relation_semantics_mismatch() -> None:
    document = _valid_document(task=True)
    payload = document["representation"]["payload"]
    approval = payload["sections"]["approvals"]["approvals"][0]
    approval["task_id"] = "task-20260703-999"
    approval["request_id"] = "req-20260703-999"
    _rehash_view(document)

    _assert_failure(
        document,
        status="validation_failed",
        exit_code=5,
        failed_check="filter_semantics",
        rule_id="filtered-consumer-filter-semantics",
    )


@pytest.mark.parametrize(
    ("raw", "status", "exit_code", "rule_id"),
    [
        (b"", "validation_failed", 5, "filtered-consumer-empty-input"),
        (b"\xff", "validation_failed", 5, "filtered-consumer-input-not-utf8"),
        (b"{", "validation_failed", 5, "filtered-consumer-invalid-json"),
        (b"[]", "validation_failed", 5, "filtered-consumer-document-shape"),
        (
            b'{"status":"ready","status":"blocked"}',
            "validation_failed",
            5,
            "filtered-consumer-duplicate-json-key",
        ),
        (
            b" " * (MAX_INPUT_BYTES + 1),
            "validation_failed",
            5,
            "filtered-consumer-input-too-large",
        ),
    ],
    ids=[
        "empty",
        "non-utf8",
        "invalid-json",
        "non-object",
        "duplicate-key",
        "too-large",
    ],
)
def test_consumer_stdin_gates(
    raw: bytes,
    status: str,
    exit_code: int,
    rule_id: str,
) -> None:
    consumer = _consumer()
    stdout = io.StringIO()

    actual_exit = consumer.main(stdin=io.BytesIO(raw), stdout=stdout)
    payload = json.loads(stdout.getvalue())

    assert actual_exit == exit_code
    assert payload["status"] == status
    assert rule_id in {item["rule_id"] for item in payload["findings"]}
    assert len(stdout.getvalue().encode("utf-8")) <= MAX_OUTPUT_BYTES


def test_consumer_rejects_command_line_input_arguments() -> None:
    process = subprocess.run(
        [sys.executable, str(TOOL), "private-snapshot.json"],
        cwd=ROOT,
        input=_reader_bytes("--request-id", REQUEST_ID),
        check=False,
        capture_output=True,
    )

    assert process.returncode == 5
    assert process.stderr == b""
    payload = json.loads(process.stdout)
    assert payload["status"] == "validation_failed"
    assert payload["source"] == {
        "base_snapshot_id": None,
        "scope_id": None,
        "filter_id": None,
        "view_id": None,
    }
    assert payload["findings"][0]["rule_id"] == (
        "filtered-consumer-arguments-not-supported"
    )
    assert "private-snapshot.json" not in process.stdout.decode("utf-8")


def test_consumer_real_stdio_pipeline() -> None:
    reader = subprocess.run(
        [
            sys.executable,
            "tools/codex_desktop_snapshot_json_reader.py",
            "--project-root",
            ".",
            "--representation",
            "snapshot-json",
            "--envelope",
            ENVELOPE,
            "--request-id",
            REQUEST_ID,
            "--json",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
    )
    consumer = subprocess.run(
        [sys.executable, str(TOOL)],
        cwd=ROOT,
        input=reader.stdout,
        check=False,
        capture_output=True,
    )

    assert reader.returncode == 0
    assert consumer.returncode == 0
    assert consumer.stderr == b""
    payload = json.loads(consumer.stdout)
    assert payload["status"] == "pass"
    assert payload["source"]["view_id"] == (
        _valid_document()["representation"]["view_id"]
    )


def test_consumer_source_has_no_forbidden_runtime_dependencies() -> None:
    assert TOOL.is_file(), "Stage 29 consumer has not been implemented"
    tree = ast.parse(TOOL.read_text(encoding="utf-8"))
    imported: set[str] = set()
    called_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            called_names.add(node.func.id)
    forbidden_modules = {
        "agent_runtime",
        "tools.control_panel_handoff_consumer",
        "tools.codex_desktop_snapshot_json_reader",
        "subprocess",
        "socket",
        "requests",
        "urllib",
    }
    assert all(
        not any(name == blocked or name.startswith(blocked + ".") for blocked in forbidden_modules)
        for name in imported
    )
    assert "open" not in called_names
    assert "Path" not in called_names
