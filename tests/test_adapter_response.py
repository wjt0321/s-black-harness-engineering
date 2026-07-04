"""Tests for adapter response check CLI."""

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


def _find_response(env: dict[str, Any]) -> dict[str, Any]:
    return next(a for a in env["artifacts"] if a["artifact_type"] == "adapter_response")


def _set_response_status(env: dict[str, Any], status: str) -> None:
    response = _find_response(env)
    response["status"] = status


def test_adapter_response_check_succeeded_with_evidence_pass(capsys, tmp_path):
    fake_root = _write_modified_envelope(tmp_path, lambda env: None)
    code = main([
        "--root", str(fake_root),
        "adapter", "response", "check",
        "--file", "envelope.json",
        "--request-id", "req-20260703-002",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 0
    result = json.loads(captured.out)
    assert result["status"] == "pass"
    response = result["response"]
    assert response["request_id"] == "req-20260703-002"
    assert response["adapter_id"] == "shell-local"
    assert response["operation"] == "read_file"
    assert response["target"] == "docs/06-adapter-layer.md"
    assert response["response_id"] == "resp-20260703-001"
    assert response["response_status"] == "succeeded"
    assert response["artifact_count"] == 1
    assert response["evidence_count"] == 1
    assert response["raw_ref_present"] is False
    assert "findings" not in result


def test_adapter_response_check_succeeded_no_evidence_blocked(capsys, tmp_path):
    def modify(env):
        _find_response(env)["evidence"] = []

    fake_root = _write_modified_envelope(tmp_path, modify)
    code = main([
        "--root", str(fake_root),
        "adapter", "response", "check",
        "--file", "envelope.json",
        "--request-id", "req-20260703-002",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 2
    result = json.loads(captured.out)
    assert result["status"] == "blocked"
    response = result["response"]
    assert response["response_status"] == "succeeded"
    assert response["evidence_count"] == 0
    assert any(f["rule_id"] == "response-evidence-missing" for f in result["findings"])


def test_adapter_response_check_missing_response_needs_input(capsys, tmp_path):
    def modify(env):
        env["artifacts"] = [a for a in env["artifacts"] if a["artifact_type"] != "adapter_response"]

    fake_root = _write_modified_envelope(tmp_path, modify)
    code = main([
        "--root", str(fake_root),
        "adapter", "response", "check",
        "--file", "envelope.json",
        "--request-id", "req-20260703-002",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 4
    result = json.loads(captured.out)
    assert result["status"] == "needs_input"
    response = result["response"]
    assert response["request_id"] == "req-20260703-002"
    assert response["response_status"] is None
    assert response["evidence_count"] == 0
    assert any(f["rule_id"] == "response-missing" for f in result["findings"])


def test_adapter_response_check_unknown_request_needs_input(capsys, tmp_path):
    fake_root = _write_modified_envelope(tmp_path, lambda env: None)
    code = main([
        "--root", str(fake_root),
        "adapter", "response", "check",
        "--file", "envelope.json",
        "--request-id", "req-20260703-999",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 4
    result = json.loads(captured.out)
    assert result["status"] == "needs_input"
    assert result["response"] == {"request_id": "req-20260703-999"}
    assert any(f["rule_id"] == "response-request-not-found" for f in result["findings"])


def test_adapter_response_check_blocked(capsys, tmp_path):
    fake_root = _write_modified_envelope(tmp_path, lambda env: _set_response_status(env, "blocked"))
    code = main([
        "--root", str(fake_root),
        "adapter", "response", "check",
        "--file", "envelope.json",
        "--request-id", "req-20260703-002",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 2
    result = json.loads(captured.out)
    assert result["status"] == "blocked"
    assert result["response"]["response_status"] == "blocked"
    assert any(f["rule_id"] == "response-blocked" for f in result["findings"])


def test_adapter_response_check_failed(capsys, tmp_path):
    fake_root = _write_modified_envelope(tmp_path, lambda env: _set_response_status(env, "failed"))
    code = main([
        "--root", str(fake_root),
        "adapter", "response", "check",
        "--file", "envelope.json",
        "--request-id", "req-20260703-002",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 2
    result = json.loads(captured.out)
    assert result["status"] == "blocked"
    assert result["response"]["response_status"] == "failed"
    assert any(f["rule_id"] == "response-failed" for f in result["findings"])


def test_adapter_response_check_needs_approval(capsys, tmp_path):
    fake_root = _write_modified_envelope(tmp_path, lambda env: _set_response_status(env, "needs_approval"))
    code = main([
        "--root", str(fake_root),
        "adapter", "response", "check",
        "--file", "envelope.json",
        "--request-id", "req-20260703-002",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 3
    result = json.loads(captured.out)
    assert result["status"] == "needs_approval"
    assert result["response"]["response_status"] == "needs_approval"
    assert any(f["rule_id"] == "response-needs-approval" for f in result["findings"])


def test_adapter_response_check_needs_input(capsys, tmp_path):
    fake_root = _write_modified_envelope(tmp_path, lambda env: _set_response_status(env, "needs_input"))
    code = main([
        "--root", str(fake_root),
        "adapter", "response", "check",
        "--file", "envelope.json",
        "--request-id", "req-20260703-002",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 4
    result = json.loads(captured.out)
    assert result["status"] == "needs_input"
    assert result["response"]["response_status"] == "needs_input"
    assert any(f["rule_id"] == "response-needs-input" for f in result["findings"])


def test_adapter_response_check_skipped(capsys, tmp_path):
    fake_root = _write_modified_envelope(tmp_path, lambda env: _set_response_status(env, "skipped"))
    code = main([
        "--root", str(fake_root),
        "adapter", "response", "check",
        "--file", "envelope.json",
        "--request-id", "req-20260703-002",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 2
    result = json.loads(captured.out)
    assert result["status"] == "blocked"
    assert result["response"]["response_status"] == "skipped"
    assert any(f["rule_id"] == "response-skipped" for f in result["findings"])


def test_adapter_response_check_invalid_envelope_no_summary(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    bad_file = fake_root / "envelope.json"
    bad_file.write_text("{not json", encoding="utf-8")
    code = main([
        "--root", str(fake_root),
        "adapter", "response", "check",
        "--file", "envelope.json",
        "--request-id", "req-20260703-002",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 5
    result = json.loads(captured.out)
    assert result["status"] == "validation_failed"
    assert "response" not in result
    assert any(f["rule_id"] == "invalid-json" for f in result["findings"])


def test_adapter_response_check_schema_invalid_no_summary(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    bad_file = fake_root / "envelope.json"
    bad_file.write_text(
        json.dumps({"version": 1, "description": "bad", "artifacts": []}),
        encoding="utf-8",
    )
    code = main([
        "--root", str(fake_root),
        "adapter", "response", "check",
        "--file", "envelope.json",
        "--request-id", "req-20260703-002",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 5
    result = json.loads(captured.out)
    assert result["status"] == "validation_failed"
    assert "response" not in result
    assert '"description": "bad"' not in captured.out


def test_adapter_response_check_outside_root(capsys, tmp_path):
    outside = tmp_path / "outside.json"
    outside.write_text("{}", encoding="utf-8")
    code = main([
        "--root", str(ROOT),
        "adapter", "response", "check",
        "--file", str(outside),
        "--request-id", "req-20260703-002",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 1
    result = json.loads(captured.out)
    assert result["status"] == "error"
    assert any(f["rule_id"] == "path-outside-root" for f in result["findings"])


def test_adapter_response_check_unsafe_file(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    env_file = fake_root / ".env.json"
    env_file.write_text("{}", encoding="utf-8")
    code = main([
        "--root", str(fake_root),
        "adapter", "response", "check",
        "--file", ".env.json",
        "--request-id", "req-20260703-002",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 1
    result = json.loads(captured.out)
    assert result["status"] == "error"
    assert any(f["rule_id"] == "unsafe-envelope-file" for f in result["findings"])


def test_adapter_response_check_human_output(capsys, tmp_path):
    fake_root = _write_modified_envelope(tmp_path, lambda env: None)
    code = main([
        "--root", str(fake_root),
        "adapter", "response", "check",
        "--file", "envelope.json",
        "--request-id", "req-20260703-002",
    ])
    captured = capsys.readouterr()
    assert code == 0
    assert "PASS" in captured.out
    assert "request_id=req-20260703-002" in captured.out
    assert "response_status=succeeded" in captured.out
    assert "evidence_count=1" in captured.out
    assert "raw_ref_present=False" in captured.out
    assert '"input"' not in captured.out
    assert '"remote"' not in captured.out


def test_adapter_response_check_does_not_write_ledger(capsys, tmp_path):
    tasks_src = ROOT / "tasks" / "tasks.jsonl"
    events_src = ROOT / "tasks" / "events.jsonl"
    tasks_copy = tmp_path / "tasks.jsonl"
    events_copy = tmp_path / "events.jsonl"
    tasks_copy.write_bytes(tasks_src.read_bytes())
    events_copy.write_bytes(events_src.read_bytes())

    fake_root = _write_modified_envelope(tmp_path, lambda env: None)
    code = main([
        "--root", str(fake_root),
        "adapter", "response", "check",
        "--file", "envelope.json",
        "--request-id", "req-20260703-002",
    ])
    assert code == 0
    assert tasks_src.read_bytes() == tasks_copy.read_bytes()
    assert events_src.read_bytes() == events_copy.read_bytes()
