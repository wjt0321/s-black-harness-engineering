"""Stage 42 prerequisite contract tests for validated Markdown presentation handoff."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
HOST_TOOL = ROOT / "tools" / "codex_desktop_filtered_snapshot_display_host.py"
ENVELOPE = "adapters/execution-envelope.examples.json"
REQUEST_ID = "req-20260703-001"
IDENTITY_KEYS = (
    "base_snapshot_id",
    "scope_id",
    "filter_id",
    "view_id",
    "content_id",
)


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate key: {key}")
        result[key] = value
    return result


def _run_host(*selectors: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        [
            sys.executable,
            str(HOST_TOOL),
            "--project-root",
            str(ROOT),
            "--envelope",
            ENVELOPE,
            *selectors,
            "--representation",
            "markdown",
            "--json",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        timeout=120,
    )


def _parse_single_object(stdout: bytes) -> dict[str, Any]:
    assert len(stdout) <= 128 * 1024
    text = stdout.decode("utf-8", errors="strict")
    decoder = json.JSONDecoder(object_pairs_hook=_reject_duplicate_keys)
    document, end = decoder.raw_decode(text)
    assert text[end:] in {"\n", "\r\n"}
    assert isinstance(document, dict)
    return document


def test_stage40_ready_result_is_a_complete_presentation_handoff_candidate() -> None:
    """Freeze the exact trust evidence a future presentation boundary must recheck."""
    completed = _run_host("--request-id", REQUEST_ID)

    assert completed.returncode == 0
    assert completed.stderr == b""
    document = _parse_single_object(completed.stdout)
    assert set(document) == {
        "status",
        "schema_version",
        "host",
        "source",
        "lifecycle",
        "display",
        "consumer",
        "representation",
        "findings",
        "guarantees",
        "next_action",
    }
    assert document["status"] == "ready"
    assert document["schema_version"] == (
        "control-plane/codex-desktop-filtered-snapshot-display-host/v1"
    )
    assert document["host"] == "codex-desktop-filtered-snapshot-display-host/v1"
    assert document["source"] == {"project_root": "project_root"}
    assert document["lifecycle"] == {
        "state": "closed",
        "phases": ["created", "displaying", "validating", "ready", "closed"],
    }
    assert document["display"]["status"] == "ready"
    assert document["display"]["exit_code"] == 0
    assert document["consumer"]["status"] == "pass"
    assert document["consumer"]["exit_code"] == 0
    assert document["findings"] == []
    assert document["next_action"]["code"] == "review_validated_markdown_display"

    representation = document["representation"]
    assert representation["status"] == "pass"
    assert representation["type"] == "markdown"
    assert representation["media_type"] == "text/markdown; charset=utf-8"
    assert representation["encoding"] == "utf-8"
    assert isinstance(representation["content"], str)
    assert representation["content"]

    identity = {key: representation[key] for key in IDENTITY_KEYS}
    assert document["display"]["source"] == identity
    assert document["consumer"]["source"] == identity
    expected_content_id = "sha256:" + hashlib.sha256(
        representation["content"].encode("utf-8")
    ).hexdigest()
    assert representation["content_id"] == expected_content_id

    guarantees = document["guarantees"]
    assert guarantees["read_only"] is True
    assert guarantees["validates_before_release"] is True
    assert guarantees["cross_checks_display_identity"] is True
    assert guarantees["withholds_content_until_pass"] is True
    assert guarantees["renders_markdown"] is False
    assert guarantees["persists_output"] is False
    assert guarantees["exports_output"] is False
    assert guarantees["writes_files"] is False
    assert guarantees["writes_ledgers"] is False
    assert guarantees["accesses_network"] is False
    assert guarantees["starts_service"] is False
    assert guarantees["executes_adapters"] is False


def test_stage40_non_ready_result_withholds_content_from_presentation() -> None:
    completed = _run_host()

    assert completed.returncode == 5
    assert completed.stderr == b""
    document = _parse_single_object(completed.stdout)
    assert document["status"] == "validation_failed"
    assert document["representation"]["status"] == "withheld"
    assert document["representation"]["content_id"] is None
    assert document["representation"]["content"] is None


def test_stage40_ready_candidate_is_deterministic_and_value_safe() -> None:
    first = _run_host("--request-id", REQUEST_ID)
    second = _run_host("--request-id", REQUEST_ID)

    assert first.returncode == second.returncode == 0
    assert first.stdout == second.stdout
    serialized = first.stdout.decode("utf-8")
    assert ENVELOPE not in serialized
    assert str(ROOT) not in serialized
    assert '"argv"' not in serialized
    assert "stderr" not in serialized
