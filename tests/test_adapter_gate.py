"""Tests for adapter gate check CLI."""

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


def _write_modified_envelope(tmp_path: Path, modifier) -> Path:
    """Return a fake root containing a modified copy of the example envelope."""
    fake_root = _setup_fake_root(tmp_path)
    envelope = json.loads(
        (ROOT / "adapters" / "execution-envelope.examples.json").read_text(encoding="utf-8")
    )
    modifier(envelope)
    env_file = fake_root / "envelope.json"
    env_file.write_text(json.dumps(envelope), encoding="utf-8")
    return fake_root


def _find_approval(env: dict[str, Any]) -> dict[str, Any]:
    return next(a for a in env["artifacts"] if a["artifact_type"] == "approval_record")


def _find_response(env: dict[str, Any]) -> dict[str, Any]:
    return next(a for a in env["artifacts"] if a["artifact_type"] == "adapter_response")


def test_adapter_gate_no_approval_needed_succeeded_evidence_pass(capsys, tmp_path):
    fake_root = _write_modified_envelope(tmp_path, lambda env: None)
    code = main([
        "--root", str(fake_root),
        "adapter", "gate", "check",
        "--file", "envelope.json",
        "--request-id", "req-20260703-002",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 0
    result = json.loads(captured.out)
    assert result["status"] == "pass"
    gate = result["gate"]
    assert gate["request_id"] == "req-20260703-002"
    assert gate["stage"] == "response"
    assert gate["approval_status"] == "pass"
    assert gate["response_status"] == "pass"
    assert gate["can_proceed"] is True
    assert gate["response"]["response_status"] == "succeeded"
    assert gate["response"]["evidence_count"] == 1
    assert "findings" not in result


def test_adapter_gate_pending_approval_needs_approval_stage_approval(capsys, tmp_path):
    fake_root = _write_modified_envelope(tmp_path, lambda env: None)
    code = main([
        "--root", str(fake_root),
        "adapter", "gate", "check",
        "--file", "envelope.json",
        "--request-id", "req-20260703-001",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 3
    result = json.loads(captured.out)
    assert result["status"] == "needs_approval"
    gate = result["gate"]
    assert gate["stage"] == "approval"
    assert gate["approval_status"] == "needs_approval"
    assert gate["response_status"] is None
    assert gate["can_proceed"] is False
    assert gate["approval"]["approval_status"] == "pending"
    assert any(f["rule_id"] == "approval-pending" for f in result["findings"])
    assert "response" not in gate


def test_adapter_gate_granted_missing_response_needs_input(capsys, tmp_path):
    def modify(env):
        _find_approval(env)["status"] = "granted"
        env["artifacts"] = [a for a in env["artifacts"] if a["artifact_type"] != "adapter_response"]

    fake_root = _write_modified_envelope(tmp_path, modify)
    code = main([
        "--root", str(fake_root),
        "adapter", "gate", "check",
        "--file", "envelope.json",
        "--request-id", "req-20260703-001",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 4
    result = json.loads(captured.out)
    assert result["status"] == "needs_input"
    gate = result["gate"]
    assert gate["stage"] == "response"
    assert gate["approval_status"] == "pass"
    assert gate["response_status"] == "needs_input"
    assert gate["can_proceed"] is False
    assert any(f["rule_id"] == "response-missing" for f in result["findings"])


def test_adapter_gate_granted_succeeded_evidence_pass(capsys, tmp_path):
    def modify(env):
        _find_approval(env)["status"] = "granted"
        _find_approval(env)["decided_at"] = "2026-07-03T11:00:00+08:00"
        _find_approval(env)["decided_by"] = "user"
        _find_response(env)["request_id"] = "req-20260703-001"

    fake_root = _write_modified_envelope(tmp_path, modify)
    code = main([
        "--root", str(fake_root),
        "adapter", "gate", "check",
        "--file", "envelope.json",
        "--request-id", "req-20260703-001",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 0
    result = json.loads(captured.out)
    assert result["status"] == "pass"
    gate = result["gate"]
    assert gate["stage"] == "response"
    assert gate["approval_status"] == "pass"
    assert gate["response_status"] == "pass"
    assert gate["can_proceed"] is True


def test_adapter_gate_denied_blocked_stage_approval(capsys, tmp_path):
    def modify(env):
        _find_approval(env)["status"] = "denied"
        _find_approval(env)["decided_at"] = "2026-07-03T11:00:00+08:00"
        _find_approval(env)["decided_by"] = "user"

    fake_root = _write_modified_envelope(tmp_path, modify)
    code = main([
        "--root", str(fake_root),
        "adapter", "gate", "check",
        "--file", "envelope.json",
        "--request-id", "req-20260703-001",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 2
    result = json.loads(captured.out)
    assert result["status"] == "blocked"
    gate = result["gate"]
    assert gate["stage"] == "approval"
    assert gate["approval_status"] == "blocked"
    assert gate["response_status"] is None
    assert gate["can_proceed"] is False
    assert any(f["rule_id"] == "approval-denied" for f in result["findings"])
    assert "response" not in gate


def test_adapter_gate_response_succeeded_no_evidence_blocked(capsys, tmp_path):
    def modify(env):
        _find_response(env)["evidence"] = []

    fake_root = _write_modified_envelope(tmp_path, modify)
    code = main([
        "--root", str(fake_root),
        "adapter", "gate", "check",
        "--file", "envelope.json",
        "--request-id", "req-20260703-002",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 2
    result = json.loads(captured.out)
    assert result["status"] == "blocked"
    gate = result["gate"]
    assert gate["stage"] == "response"
    assert gate["approval_status"] == "pass"
    assert gate["response_status"] == "blocked"
    assert gate["can_proceed"] is False
    assert gate["response"]["evidence_count"] == 0
    assert any(f["rule_id"] == "response-evidence-missing" for f in result["findings"])


def test_adapter_gate_unknown_request_needs_input(capsys, tmp_path):
    fake_root = _write_modified_envelope(tmp_path, lambda env: None)
    code = main([
        "--root", str(fake_root),
        "adapter", "gate", "check",
        "--file", "envelope.json",
        "--request-id", "req-20260703-999",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 4
    result = json.loads(captured.out)
    assert result["status"] == "needs_input"
    gate = result["gate"]
    assert gate["stage"] == "approval"
    assert gate["approval_status"] == "needs_input"
    assert gate["can_proceed"] is False
    assert any(f["rule_id"] == "approval-request-not-found" for f in result["findings"])


def test_adapter_gate_invalid_envelope_no_payload_summary(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    bad_file = fake_root / "envelope.json"
    bad_file.write_text("{not json", encoding="utf-8")
    code = main([
        "--root", str(fake_root),
        "adapter", "gate", "check",
        "--file", "envelope.json",
        "--request-id", "req-20260703-002",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 5
    result = json.loads(captured.out)
    assert result["status"] == "validation_failed"
    gate = result["gate"]
    assert gate["stage"] == "approval"
    assert gate["approval_status"] == "validation_failed"
    assert gate["can_proceed"] is False
    assert "approval" not in gate
    assert "response" not in gate
    assert any(f["rule_id"] == "invalid-json" for f in result["findings"])


def test_adapter_gate_outside_root(capsys, tmp_path):
    outside = tmp_path / "outside.json"
    outside.write_text("{}", encoding="utf-8")
    code = main([
        "--root", str(ROOT),
        "adapter", "gate", "check",
        "--file", str(outside),
        "--request-id", "req-20260703-002",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 1
    result = json.loads(captured.out)
    assert result["status"] == "error"
    assert result["gate"]["stage"] == "approval"
    assert any(f["rule_id"] == "path-outside-root" for f in result["findings"])


def test_adapter_gate_unsafe_file(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    env_file = fake_root / ".env.json"
    env_file.write_text("{}", encoding="utf-8")
    code = main([
        "--root", str(fake_root),
        "adapter", "gate", "check",
        "--file", ".env.json",
        "--request-id", "req-20260703-002",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 1
    result = json.loads(captured.out)
    assert result["status"] == "error"
    assert result["gate"]["stage"] == "approval"
    assert any(f["rule_id"] == "unsafe-envelope-file" for f in result["findings"])


def test_adapter_gate_human_output(capsys, tmp_path):
    fake_root = _write_modified_envelope(tmp_path, lambda env: None)
    code = main([
        "--root", str(fake_root),
        "adapter", "gate", "check",
        "--file", "envelope.json",
        "--request-id", "req-20260703-002",
    ])
    captured = capsys.readouterr()
    assert code == 0
    assert "PASS" in captured.out
    assert "stage=response" in captured.out
    assert "request_id=req-20260703-002" in captured.out
    assert "approval_status=pass" in captured.out
    assert "response_status=pass" in captured.out
    assert "can_proceed=True" in captured.out
    assert '"input"' not in captured.out
    assert '"remote"' not in captured.out


def test_adapter_gate_does_not_write_ledger(capsys, tmp_path):
    tasks_src = ROOT / "tasks" / "tasks.jsonl"
    events_src = ROOT / "tasks" / "events.jsonl"
    tasks_copy = tmp_path / "tasks.jsonl"
    events_copy = tmp_path / "events.jsonl"
    tasks_copy.write_bytes(tasks_src.read_bytes())
    events_copy.write_bytes(events_src.read_bytes())

    fake_root = _write_modified_envelope(tmp_path, lambda env: None)
    code = main([
        "--root", str(fake_root),
        "adapter", "gate", "check",
        "--file", "envelope.json",
        "--request-id", "req-20260703-002",
    ])
    assert code == 0
    assert tasks_src.read_bytes() == tasks_copy.read_bytes()
    assert events_src.read_bytes() == events_copy.read_bytes()
