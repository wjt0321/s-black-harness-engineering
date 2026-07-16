"""Stage 28 prerequisite contract for a future filtered snapshot host consumer."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ENVELOPE = "adapters/execution-envelope.examples.json"
REQUEST_ID = "req-20260703-001"
MAX_INPUT_BYTES = 1024 * 1024
EXPECTED_PHASES = [
    "created",
    "scoping",
    "producing",
    "validating",
    "reading",
    "filtering",
    "ready",
    "closed",
]
EXPECTED_GUARANTEES = {
    "requires_explicit_user_action": True,
    "one_shot": True,
    "read_only": True,
    "reads_snapshot_json": True,
    "reads_html": False,
    "writes_files": False,
    "accesses_network": False,
    "starts_service": False,
    "runs_fixed_read_processes": True,
    "executes_candidate_commands": False,
    "executes_adapters": False,
    "executes_descriptor_argv": False,
    "auto_retries": False,
    "bounded_output": True,
    "reads_envelope_scope": True,
    "writes_ledgers": False,
    "allows_arbitrary_paths": False,
    "scans_envelope_secrets": True,
    "filters_safe_summaries": True,
    "allows_arbitrary_queries": False,
    "persists_filtered_views": False,
}


class DuplicateJSONKeyError(ValueError):
    """Raised when reader stdout contains an ambiguous duplicate key."""


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateJSONKeyError(key)
        result[key] = value
    return result


def _canonical_id(payload: dict[str, Any]) -> str:
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(canonical).hexdigest()}"


def _reader_stdout() -> bytes:
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
            "--request-id",
            REQUEST_ID,
            "--json",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
    )
    assert process.returncode == 0
    assert process.stderr == b""
    return process.stdout


def _parse_strict(raw: bytes) -> dict[str, Any]:
    assert 0 < len(raw) <= MAX_INPUT_BYTES
    document = json.loads(
        raw.decode("utf-8"),
        object_pairs_hook=_reject_duplicate_keys,
    )
    assert isinstance(document, dict)
    return document


def test_filtered_v3_exposes_independently_verifiable_consumer_identity() -> None:
    document = _parse_strict(_reader_stdout())

    assert set(document) == {
        "status",
        "schema_version",
        "reader",
        "source",
        "lifecycle",
        "handoff",
        "representation",
        "findings",
        "guarantees",
        "next_action",
    }
    assert document["status"] == "ready"
    assert document["schema_version"] == (
        "control-plane/codex-desktop-snapshot-read/v3"
    )
    assert document["reader"] == (
        "codex-desktop-filtered-envelope-snapshot-json-reader/v3"
    )
    assert document["lifecycle"] == {
        "state": "closed",
        "phases": EXPECTED_PHASES,
    }
    assert document["findings"] == []
    assert document["guarantees"] == EXPECTED_GUARANTEES

    source = document["source"]
    handoff = document["handoff"]
    representation = document["representation"]
    filtered = representation["payload"]
    filter_document = filtered["filter"]
    summary = filtered["summary"]
    sections = filtered["sections"]

    assert set(source) == {
        "project_root",
        "relative_envelope",
        "envelope_content_id",
        "scope_id",
        "filter_id",
    }
    assert source["project_root"] == "project_root"
    assert source["relative_envelope"] == ENVELOPE
    assert set(handoff) == {"status", "exit_code", "source_handoff_id"}
    assert handoff["status"] == "pass"
    assert handoff["exit_code"] == 0
    assert set(representation) == {
        "status",
        "type",
        "media_type",
        "encoding",
        "exit_code",
        "base_snapshot_id",
        "view_id",
        "payload",
    }
    assert representation["status"] == "pass"
    assert representation["type"] == "snapshot-json"
    assert representation["media_type"] == "application/json; charset=utf-8"
    assert representation["encoding"] == "utf-8"
    assert representation["exit_code"] == 0
    assert set(filtered) == {
        "status",
        "schema_version",
        "source",
        "filter",
        "summary",
        "sections",
        "view_id",
    }
    assert filtered["status"] == "pass"
    assert filtered["schema_version"] == (
        "control-plane/filtered-envelope-snapshot/v1"
    )
    assert filter_document == {
        "schema_version": "control-plane/envelope-snapshot-filter/v1",
        "task_id": None,
        "request_id": REQUEST_ID,
    }
    assert set(summary) == {
        "matched",
        "run_count",
        "approval_count",
        "artifact_count",
        "section_statuses",
    }
    assert summary["matched"] is True
    assert summary["section_statuses"] == {
        "runs": "pass",
        "approvals": "pass",
        "artifacts": "pass",
        "reports": "unavailable",
    }
    assert summary["run_count"] == len(sections["runs"]["runs"])
    assert summary["approval_count"] == len(
        sections["approvals"]["approvals"]
    )
    assert summary["artifact_count"] == len(
        sections["artifacts"]["artifacts"]
    )

    assert source["scope_id"] == _canonical_id(
        {
            "relative_envelope": source["relative_envelope"],
            "envelope_content_id": source["envelope_content_id"],
        }
    )
    assert source["filter_id"] == _canonical_id(filter_document)
    assert filtered["source"] == {
        "base_snapshot_id": representation["base_snapshot_id"],
        "scope_id": source["scope_id"],
        "filter_id": source["filter_id"],
    }
    assert representation["view_id"] == filtered["view_id"]
    assert filtered["view_id"] == _canonical_id(
        {key: value for key, value in filtered.items() if key != "view_id"}
    )


def test_filtered_v3_consumer_input_is_bounded_deterministic_and_safe() -> None:
    first = _reader_stdout()
    second = _reader_stdout()
    document = _parse_strict(first)

    assert first == second
    filtered = document["representation"]["payload"]
    sections = filtered["sections"]
    assert set(sections) == {
        "runs",
        "approvals",
        "artifacts",
        "reports",
    }
    assert sections["reports"]["status"] == "unavailable"
    assert sections["reports"]["scope"] == "request"
    for run in sections["runs"]["runs"]:
        assert run["request_id"] == REQUEST_ID
    for approval in sections["approvals"]["approvals"]:
        assert approval["request_id"] == REQUEST_ID
    for artifact in sections["artifacts"]["artifacts"]:
        assert artifact["request_id"] == REQUEST_ID
        assert artifact["safe_to_preview"] is True

    serialized = first.decode("utf-8")
    assert str(ROOT.resolve()) not in serialized
    assert '"argv"' not in serialized
    assert '"input"' not in serialized
    assert "payload_refs" not in serialized
    assert "raw_ref" not in serialized
    assert "project_overview" not in serialized
    assert "adapter_registry" not in serialized
