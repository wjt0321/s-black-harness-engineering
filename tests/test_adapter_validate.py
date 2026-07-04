"""Tests for adapter envelope validation CLI."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agent_runtime.cli import main


ROOT = Path(__file__).resolve().parents[1]


def _setup_fake_root(tmp_path: Path) -> Path:
    """Create a fake project root containing a copy of the envelope schema."""
    fake_root = tmp_path / "project"
    fake_root.mkdir()
    schema_src = ROOT / "adapters" / "execution-envelope.schema.json"
    schema_dst = fake_root / "adapters" / "execution-envelope.schema.json"
    schema_dst.parent.mkdir(parents=True, exist_ok=True)
    schema_dst.write_text(schema_src.read_text(encoding="utf-8"), encoding="utf-8")
    return fake_root


def test_adapter_validate_examples_pass(capsys):
    code = main([
        "--root", str(ROOT),
        "adapter", "validate",
        "--file", "adapters/execution-envelope.examples.json",
    ])
    captured = capsys.readouterr()
    assert code == 0
    assert "PASS" in captured.out
    assert "adapters/execution-envelope.examples.json" in captured.out


def test_adapter_validate_json_output(capsys):
    code = main([
        "--root", str(ROOT),
        "adapter", "validate",
        "--file", "adapters/execution-envelope.examples.json",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 0
    result = json.loads(captured.out)
    assert result["status"] == "pass"


def test_adapter_validate_invalid_json(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    bad_file = fake_root / "bad.json"
    bad_file.write_text("{not json", encoding="utf-8")
    code = main([
        "--root", str(fake_root),
        "adapter", "validate",
        "--file", "bad.json",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 5
    result = json.loads(captured.out)
    assert result["status"] == "validation_failed"
    assert "invalid-json" in {f["rule_id"] for f in result["findings"]}


def test_adapter_validate_schema_invalid(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    bad_file = fake_root / "bad.json"
    bad_file.write_text(
        json.dumps({"version": 1, "description": "bad", "artifacts": []}),
        encoding="utf-8",
    )
    code = main([
        "--root", str(fake_root),
        "adapter", "validate",
        "--file", "bad.json",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 5
    result = json.loads(captured.out)
    assert result["status"] == "validation_failed"
    assert "envelope-schema-validation-failed" in {f["rule_id"] for f in result["findings"]}
    # Must not echo the full envelope content.
    assert '"description": "bad"' not in captured.out


def test_adapter_validate_outside_root(capsys, tmp_path):
    outside = tmp_path / "outside.json"
    outside.write_text("{}", encoding="utf-8")
    code = main([
        "--root", str(ROOT),
        "adapter", "validate",
        "--file", str(outside),
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 1
    result = json.loads(captured.out)
    assert result["status"] == "error"
    assert "path-outside-root" in {f["rule_id"] for f in result["findings"]}


def test_adapter_validate_unsafe_file(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    env_file = fake_root / ".env.json"
    env_file.write_text("{}", encoding="utf-8")
    code = main([
        "--root", str(fake_root),
        "adapter", "validate",
        "--file", ".env.json",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 1
    result = json.loads(captured.out)
    assert result["status"] == "error"
    assert "unsafe-envelope-file" in {f["rule_id"] for f in result["findings"]}


def test_adapter_validate_not_json_extension(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    txt_file = fake_root / "envelope.txt"
    txt_file.write_text("{}", encoding="utf-8")
    code = main([
        "--root", str(fake_root),
        "adapter", "validate",
        "--file", "envelope.txt",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 1
    result = json.loads(captured.out)
    assert result["status"] == "error"
    assert "unsafe-envelope-file" in {f["rule_id"] for f in result["findings"]}


def _write_modified_envelope(tmp_path: Path, modifier) -> Path:
    """Return a fake root containing a modified copy of the example envelope."""
    fake_root = _setup_fake_root(tmp_path)
    envelope = json.loads((ROOT / "adapters" / "execution-envelope.examples.json").read_text(encoding="utf-8"))
    modifier(envelope)
    bad_file = fake_root / "envelope.json"
    bad_file.write_text(json.dumps(envelope), encoding="utf-8")
    return fake_root


def _assert_validation_failed(capsys, fake_root: Path, expected_rule_id: str) -> dict[str, Any]:
    code = main([
        "--root", str(fake_root),
        "adapter", "validate",
        "--file", "envelope.json",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 5
    result = json.loads(captured.out)
    assert result["status"] == "validation_failed"
    assert expected_rule_id in {f["rule_id"] for f in result["findings"]}
    return result


def test_adapter_validate_does_not_write_ledger(capsys, tmp_path):
    tasks_src = ROOT / "tasks" / "tasks.jsonl"
    events_src = ROOT / "tasks" / "events.jsonl"
    tasks_copy = tmp_path / "tasks.jsonl"
    events_copy = tmp_path / "events.jsonl"
    tasks_copy.write_bytes(tasks_src.read_bytes())
    events_copy.write_bytes(events_src.read_bytes())

    code = main([
        "--root", str(ROOT),
        "adapter", "validate",
        "--file", "adapters/execution-envelope.examples.json",
    ])
    assert code == 0
    assert tasks_src.read_bytes() == tasks_copy.read_bytes()
    assert events_src.read_bytes() == events_copy.read_bytes()


def test_adapter_validate_consistency_unknown_approval_request(capsys, tmp_path):
    def modify(env):
        for artifact in env["artifacts"]:
            if artifact["artifact_type"] == "approval_record":
                artifact["request_id"] = "req-20260703-999"
    fake_root = _write_modified_envelope(tmp_path, modify)
    _assert_validation_failed(capsys, fake_root, "approval-references-unknown-request")


def test_adapter_validate_consistency_unknown_response_request(capsys, tmp_path):
    def modify(env):
        for artifact in env["artifacts"]:
            if artifact["artifact_type"] == "adapter_response":
                artifact["request_id"] = "req-20260703-999"
    fake_root = _write_modified_envelope(tmp_path, modify)
    _assert_validation_failed(capsys, fake_root, "response-references-unknown-request")


def test_adapter_validate_consistency_unknown_event_request(capsys, tmp_path):
    def modify(env):
        for artifact in env["artifacts"]:
            if artifact["artifact_type"] == "execution_event":
                artifact["request_id"] = "req-20260703-999"
    fake_root = _write_modified_envelope(tmp_path, modify)
    _assert_validation_failed(capsys, fake_root, "event-references-unknown-request")


def test_adapter_validate_consistency_approval_scope_mismatch(capsys, tmp_path):
    def modify(env):
        for artifact in env["artifacts"]:
            if artifact["artifact_type"] == "approval_record":
                artifact["scope"]["target"] = "origin/other"
    fake_root = _write_modified_envelope(tmp_path, modify)
    _assert_validation_failed(capsys, fake_root, "approval-scope-mismatch")


def test_adapter_validate_consistency_needs_approval_missing_record(capsys, tmp_path):
    def modify(env):
        env["artifacts"] = [a for a in env["artifacts"] if a["artifact_type"] != "approval_record"]
    fake_root = _write_modified_envelope(tmp_path, modify)
    _assert_validation_failed(capsys, fake_root, "needs-approval-missing-record")


def test_adapter_validate_consistency_unknown_approval_id_in_event(capsys, tmp_path):
    def modify(env):
        for artifact in env["artifacts"]:
            if artifact["artifact_type"] == "execution_event" and artifact.get("event_type") == "approval_requested":
                artifact["metadata"]["approval_id"] = "appr-unknown-999"
    fake_root = _write_modified_envelope(tmp_path, modify)
    _assert_validation_failed(capsys, fake_root, "approval-requested-event-unknown-approval")


def test_adapter_validate_consistency_duplicate_request_id(capsys, tmp_path):
    def modify(env):
        requests = [a for a in env["artifacts"] if a["artifact_type"] == "adapter_request"]
        if len(requests) >= 2:
            requests[1]["request_id"] = requests[0]["request_id"]
    fake_root = _write_modified_envelope(tmp_path, modify)
    _assert_validation_failed(capsys, fake_root, "duplicate-request-id")
