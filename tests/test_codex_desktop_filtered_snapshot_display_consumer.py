"""Tests for the Stage 37 filtered snapshot Markdown display consumer."""

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
from typing import Any, Callable

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "codex_desktop_filtered_snapshot_display_consumer.py"
DISPLAY_TOOL = ROOT / "tools" / "codex_desktop_filtered_snapshot_display.py"
ENVELOPE = "adapters/execution-envelope.examples.json"
TASK_ID = "task-20260703-001"
REQUEST_ID = "req-20260703-001"
EMPTY_REQUEST_ID = "req-20260703-999"
MAX_INPUT_BYTES = 64 * 1024
MAX_OUTPUT_BYTES = 64 * 1024
CHECKS = [
    "document_shape", "schema_version", "display_status", "lifecycle",
    "guarantees", "representation_metadata", "content_identity",
    "markdown_structure", "escaping_invariants", "view_coherence",
]
RESULT_GUARANTEES = {
    "stdin_only": True, "read_only": True, "validates_display_result": True,
    "recomputes_content_identity": True, "validates_markdown_grammar": True,
    "renders_markdown": False, "writes_files": False, "accesses_network": False,
    "starts_service": False, "executes_display": False, "executes_host": False,
    "executes_reader": False, "executes_commands": False,
    "executes_adapters": False, "persists_input": False,
    "bounded_input": True, "bounded_output": True,
}


def _consumer():
    assert TOOL.is_file(), "Stage 37 display consumer has not been implemented"
    spec = importlib.util.spec_from_file_location(
        "codex_desktop_filtered_snapshot_display_consumer", TOOL
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@lru_cache(maxsize=12)
def _display_bytes(*args: str) -> tuple[int, bytes]:
    process = subprocess.run(
        [sys.executable, str(DISPLAY_TOOL), *args, "--json"],
        cwd=ROOT, check=False, capture_output=True, timeout=60,
    )
    assert process.stderr == b""
    return process.returncode, process.stdout


def _args(*filters: str, envelope: str = ENVELOPE, root: Path = ROOT) -> tuple[str, ...]:
    return (
        "--project-root", str(root), "--envelope", envelope,
        *filters, "--representation", "markdown",
    )


def _document(*filters: str, envelope: str = ENVELOPE, root: Path = ROOT) -> dict[str, Any]:
    _, raw = _display_bytes(*_args(*filters, envelope=envelope, root=root))
    value = json.loads(raw)
    assert isinstance(value, dict)
    return copy.deepcopy(value)


def _ready_document(*filters: str) -> dict[str, Any]:
    document = _document(*(filters or ("--request-id", REQUEST_ID)))
    assert document["status"] == "ready"
    return document


def _set_content(document: dict[str, Any], mutate: Callable[[str], str]) -> None:
    representation = document["representation"]
    representation["content"] = mutate(representation["content"])
    representation["content_id"] = "sha256:" + hashlib.sha256(
        representation["content"].encode("utf-8")
    ).hexdigest()


def _validate(document: object):
    return _consumer().validate_display_document(document)


def _failed(document: object, check: str, rule_id: str) -> dict[str, Any]:
    result = _validate(document)
    payload = result.to_dict()
    assert result.status == "validation_failed"
    assert result.exit_code() == 5
    states = {item["check_id"]: item["status"] for item in payload["checks"]}
    assert states[check] == "failed"
    assert rule_id in {item["rule_id"] for item in payload["findings"]}
    serialized = json.dumps(payload)
    if isinstance(document, dict):
        content = document.get("representation", {}).get("content")
        if isinstance(content, str):
            assert content not in serialized
    return payload


def test_consumer_accepts_ready_request_and_emits_minimal_result() -> None:
    document = _ready_document("--request-id", REQUEST_ID)
    result = _validate(document)
    payload = result.to_dict()
    representation = document["representation"]

    assert result.status == "pass"
    assert result.exit_code() == 0
    assert list(payload) == [
        "status", "schema_version", "consumer", "source", "checks",
        "findings", "guarantees", "next_action",
    ]
    assert payload["schema_version"] == (
        "control-plane/filtered-snapshot-markdown-display-consumer-validation/v1"
    )
    assert payload["consumer"] == (
        "codex-desktop-filtered-snapshot-markdown-display-consumer/v1"
    )
    assert payload["source"] == {
        key: representation[key]
        for key in ("base_snapshot_id", "scope_id", "filter_id", "view_id", "content_id")
    }
    assert payload["checks"] == [
        {"check_id": check, "status": "pass"} for check in CHECKS
    ]
    assert payload["findings"] == []
    assert payload["guarantees"] == RESULT_GUARANTEES
    serialized = json.dumps(payload)
    assert document["representation"]["content"] not in serialized
    assert str(ROOT) not in serialized and ENVELOPE not in serialized


def test_consumer_accepts_task_and_and_and_legal_empty_view() -> None:
    documents = [
        _ready_document("--task-id", TASK_ID),
        _ready_document("--task-id", TASK_ID, "--request-id", REQUEST_ID),
        _ready_document("--request-id", EMPTY_REQUEST_ID),
    ]
    results = [_validate(document) for document in documents]

    assert [result.status for result in results] == ["pass", "pass", "pass"]
    assert all(result.exit_code() == 0 for result in results)
    empty_content = documents[-1]["representation"]["content"]
    assert "No matching runs." in empty_content
    assert results[-1].to_dict()["source"]["content_id"] == (
        documents[-1]["representation"]["content_id"]
    )


def test_consumer_maps_valid_non_ready_withheld_results() -> None:
    cases = [
        (_document("--request-id", REQUEST_ID, envelope="adapters/missing.json"), "blocked", 2),
        (_document("--request-id", "req-*"), "validation_failed", 5),
        (_document("--request-id", REQUEST_ID, root=ROOT / "missing"), "error", 1),
    ]
    for document, status, exit_code in cases:
        result = _validate(document)
        payload = result.to_dict()
        assert result.status == status
        assert result.exit_code() == exit_code
        assert payload["source"]["content_id"] is None
        assert payload["checks"] == [
            {"check_id": check, "status": "pass"} for check in CHECKS
        ]
        assert document["findings"][0]["message"] not in json.dumps(payload)


def test_consumer_rejects_content_hash_and_identity_link_drift() -> None:
    hash_drift = _ready_document()
    hash_drift["representation"]["content_id"] = "sha256:" + "0" * 64
    _failed(hash_drift, "content_identity", "display-consumer-content-identity")

    identity_drift = _ready_document()
    _set_content(
        identity_drift,
        lambda content: content.replace(
            identity_drift["representation"]["view_id"], "sha256:" + "0" * 64
        ),
    )
    _failed(identity_drift, "view_coherence", "display-consumer-view-coherence")


@pytest.mark.parametrize(
    ("raw", "status", "exit_code", "rule_id"),
    [
        (b"", "validation_failed", 5, "display-consumer-empty-input"),
        (b"\xff", "validation_failed", 5, "display-consumer-input-not-utf8"),
        (b"not-json", "validation_failed", 5, "display-consumer-invalid-json"),
        (b"[]", "validation_failed", 5, "display-consumer-document-shape"),
        (b'{"status":"ready","status":"error"}', "validation_failed", 5, "display-consumer-duplicate-json-key"),
        (b" " * (MAX_INPUT_BYTES + 1), "validation_failed", 5, "display-consumer-input-too-large"),
    ],
    ids=["empty", "non-utf8", "invalid-json", "non-object", "duplicate-key", "too-large"],
)
def test_consumer_stdin_gates(raw: bytes, status: str, exit_code: int, rule_id: str) -> None:
    consumer = _consumer()
    stdout = io.StringIO()
    actual = consumer.main(stdin=io.BytesIO(raw), stdout=stdout)
    payload = json.loads(stdout.getvalue())

    assert actual == exit_code
    assert payload["status"] == status
    assert rule_id in {item["rule_id"] for item in payload["findings"]}
    assert len(stdout.getvalue().encode("utf-8")) <= MAX_OUTPUT_BYTES


def test_consumer_rejects_wrapper_schema_status_lifecycle_and_guarantee_drift() -> None:
    mutations = [
        (lambda d: d.__setitem__("unexpected", True), "document_shape"),
        (lambda d: d.__setitem__("schema_version", "v2"), "schema_version"),
        (lambda d: d.__setitem__("display", "other/v1"), "schema_version"),
        (lambda d: d["host"].__setitem__("exit_code", 2), "display_status"),
        (lambda d: d["lifecycle"]["phases"].reverse(), "lifecycle"),
        (lambda d: d["guarantees"].__setitem__("writes_files", True), "guarantees"),
    ]
    for mutate, check in mutations:
        document = _ready_document()
        mutate(document)
        result = _validate(document).to_dict()
        states = {item["check_id"]: item["status"] for item in result["checks"]}
        assert result["status"] in {"blocked", "validation_failed"}
        assert states[check] == "failed"


def test_consumer_accepts_visible_escapes_but_rejects_raw_markdown_and_controls() -> None:
    safe = _ready_document()
    _set_content(
        safe,
        lambda content: content.replace(
            '- Message: `"Reports remain request-scoped and are not presented as a persistent collection."`',
            '- Message: `"\\u003cscript\\u003e\\u007c\\u0060tick\\u0060\\u0026"`',
        ),
    )
    assert _validate(safe).status == "pass"

    replacements = [
        ("unavailable", "<script>"),
        ("unavailable", "[x](https://example.invalid)"),
        ("unavailable", "raw|pipe"),
        ("unavailable", "raw`tick"),
        ("unavailable", "bad\x01control"),
    ]
    for old, new in replacements:
        document = _ready_document()
        _set_content(document, lambda content, old=old, new=new: content.replace(old, new, 1))
        result = _validate(document).to_dict()
        assert result["status"] == "validation_failed"
        assert any(item["status"] == "failed" for item in result["checks"])


def test_consumer_rejects_markdown_structure_and_coherence_drift() -> None:
    mutations = [
        lambda c: c.replace("## Overview", "## Arbitrary", 1),
        lambda c: c.replace("- Run Count: `1`", "- Run Count: `9`", 1),
        lambda c: c.replace("## Runs", "## Approvals", 1),
        lambda c: c.replace("- Matched: `true`", "- Matched: `false`", 1),
        lambda c: c.replace('- Reason: `"request_context_required"`', '- Reason: `"other"`', 1),
        lambda c: c + "extra text\n",
    ]
    for mutate in mutations:
        document = _ready_document()
        _set_content(document, mutate)
        result = _validate(document).to_dict()
        assert result["status"] == "validation_failed"

    empty = _ready_document("--request-id", EMPTY_REQUEST_ID)
    _set_content(empty, lambda c: c.replace("No matching runs.", "", 1))
    _failed(empty, "markdown_structure", "display-consumer-markdown-structure")


def test_consumer_main_is_deterministic_bounded_and_rejects_arguments() -> None:
    consumer = _consumer()
    raw = json.dumps(_ready_document(), ensure_ascii=False).encode("utf-8")
    outputs = []
    for _ in range(2):
        stdout = io.StringIO()
        assert consumer.main(stdin=io.BytesIO(raw), stdout=stdout) == 0
        outputs.append(stdout.getvalue())
    assert outputs[0] == outputs[1]
    assert len(outputs[0].encode("utf-8")) <= MAX_OUTPUT_BYTES

    stdout = io.StringIO()
    assert consumer.main(argv=["private-display.json"], stdin=io.BytesIO(raw), stdout=stdout) == 5
    payload = json.loads(stdout.getvalue())
    assert payload["findings"][0]["rule_id"] == "display-consumer-arguments-not-supported"
    assert "private-display.json" not in stdout.getvalue()


def test_consumer_real_display_stdio_pipeline() -> None:
    display = subprocess.run(
        [sys.executable, str(DISPLAY_TOOL), *_args("--request-id", REQUEST_ID), "--json"],
        cwd=ROOT, check=False, capture_output=True, timeout=60,
    )
    consumer = subprocess.run(
        [sys.executable, str(TOOL)], cwd=ROOT, input=display.stdout,
        check=False, capture_output=True, timeout=20,
    )
    payload = json.loads(consumer.stdout)

    assert display.returncode == 0
    assert consumer.returncode == 0
    assert consumer.stderr == b""
    assert payload["status"] == "pass"
    assert payload["source"]["content_id"] == json.loads(display.stdout)["representation"]["content_id"]


def test_consumer_source_has_no_process_file_network_or_runtime_dependencies() -> None:
    assert TOOL.is_file(), "Stage 37 display consumer has not been implemented"
    tree = ast.parse(TOOL.read_text(encoding="utf-8"))
    imported: set[str] = set()
    called_names: set[str] = set()
    called_attrs: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                called_names.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                called_attrs.add(node.func.attr)
    assert not ({"agent_runtime", "tools", "subprocess", "socket", "requests", "urllib"} & imported)
    assert not ({"open", "exec", "eval", "Path"} & called_names)
    assert not ({"read_text", "read_bytes", "write_text", "write_bytes", "unlink"} & called_attrs)
