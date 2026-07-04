"""Tests for adapter approval check CLI."""

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


def test_adapter_approval_check_granted(capsys, tmp_path):
    def modify(env):
        for artifact in env["artifacts"]:
            if artifact["artifact_type"] == "approval_record":
                artifact["status"] = "granted"
                artifact["decided_at"] = "2026-07-03T11:00:00+08:00"
                artifact["decided_by"] = "user"
                artifact["decision_ref"] = "decision-20260703-001"

    fake_root = _write_modified_envelope(tmp_path, modify)
    code = main([
        "--root", str(fake_root),
        "adapter", "approval", "check",
        "--file", "envelope.json",
        "--request-id", "req-20260703-001",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 0
    result = json.loads(captured.out)
    assert result["status"] == "pass"
    approval = result["approval"]
    assert approval["request_id"] == "req-20260703-001"
    assert approval["adapter_id"] == "github-cli"
    assert approval["operation"] == "git_push"
    assert approval["target"] == "origin/main"
    assert approval["requires_approval"] is True
    assert approval["approval_id"] == "appr-20260703-001"
    assert approval["approval_status"] == "granted"
    assert approval["decision_ref"] == "decision-20260703-001"
    assert "findings" not in result


def test_adapter_approval_check_pending(capsys, tmp_path):
    fake_root = _write_modified_envelope(tmp_path, lambda env: None)
    code = main([
        "--root", str(fake_root),
        "adapter", "approval", "check",
        "--file", "envelope.json",
        "--request-id", "req-20260703-001",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 3
    result = json.loads(captured.out)
    assert result["status"] == "needs_approval"
    approval = result["approval"]
    assert approval["requires_approval"] is True
    assert approval["approval_status"] == "pending"
    assert any(f["rule_id"] == "approval-pending" for f in result["findings"])


def test_adapter_approval_check_denied(capsys, tmp_path):
    def modify(env):
        for artifact in env["artifacts"]:
            if artifact["artifact_type"] == "approval_record":
                artifact["status"] = "denied"
                artifact["decided_at"] = "2026-07-03T11:00:00+08:00"
                artifact["decided_by"] = "user"

    fake_root = _write_modified_envelope(tmp_path, modify)
    code = main([
        "--root", str(fake_root),
        "adapter", "approval", "check",
        "--file", "envelope.json",
        "--request-id", "req-20260703-001",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 2
    result = json.loads(captured.out)
    assert result["status"] == "blocked"
    assert result["approval"]["approval_status"] == "denied"
    assert any(f["rule_id"] == "approval-denied" for f in result["findings"])


def test_adapter_approval_check_expired(capsys, tmp_path):
    def modify(env):
        for artifact in env["artifacts"]:
            if artifact["artifact_type"] == "approval_record":
                artifact["status"] = "expired"
                artifact["decided_at"] = "2026-07-03T11:00:00+08:00"

    fake_root = _write_modified_envelope(tmp_path, modify)
    code = main([
        "--root", str(fake_root),
        "adapter", "approval", "check",
        "--file", "envelope.json",
        "--request-id", "req-20260703-001",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 2
    result = json.loads(captured.out)
    assert result["status"] == "blocked"
    assert result["approval"]["approval_status"] == "expired"
    assert any(f["rule_id"] == "approval-expired" for f in result["findings"])


def test_adapter_approval_check_not_required(capsys, tmp_path):
    fake_root = _write_modified_envelope(tmp_path, lambda env: None)
    code = main([
        "--root", str(fake_root),
        "adapter", "approval", "check",
        "--file", "envelope.json",
        "--request-id", "req-20260703-002",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 0
    result = json.loads(captured.out)
    assert result["status"] == "pass"
    approval = result["approval"]
    assert approval["request_id"] == "req-20260703-002"
    assert approval["requires_approval"] is False
    assert approval["approval_id"] is None
    assert approval["approval_status"] is None
    assert "findings" not in result


def test_adapter_approval_check_unknown_request(capsys, tmp_path):
    fake_root = _write_modified_envelope(tmp_path, lambda env: None)
    code = main([
        "--root", str(fake_root),
        "adapter", "approval", "check",
        "--file", "envelope.json",
        "--request-id", "req-20260703-999",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 4
    result = json.loads(captured.out)
    assert result["status"] == "needs_input"
    assert result["approval"] == {"request_id": "req-20260703-999"}
    assert any(f["rule_id"] == "approval-request-not-found" for f in result["findings"])


def test_adapter_approval_check_invalid_envelope_no_summary(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    bad_file = fake_root / "envelope.json"
    bad_file.write_text("{not json", encoding="utf-8")
    code = main([
        "--root", str(fake_root),
        "adapter", "approval", "check",
        "--file", "envelope.json",
        "--request-id", "req-20260703-001",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 5
    result = json.loads(captured.out)
    assert result["status"] == "validation_failed"
    assert "approval" not in result
    assert any(f["rule_id"] == "invalid-json" for f in result["findings"])


def test_adapter_approval_check_schema_invalid_no_summary(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    bad_file = fake_root / "envelope.json"
    bad_file.write_text(
        json.dumps({"version": 1, "description": "bad", "artifacts": []}),
        encoding="utf-8",
    )
    code = main([
        "--root", str(fake_root),
        "adapter", "approval", "check",
        "--file", "envelope.json",
        "--request-id", "req-20260703-001",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 5
    result = json.loads(captured.out)
    assert result["status"] == "validation_failed"
    assert "approval" not in result
    assert '"description": "bad"' not in captured.out


def test_adapter_approval_check_outside_root(capsys, tmp_path):
    outside = tmp_path / "outside.json"
    outside.write_text("{}", encoding="utf-8")
    code = main([
        "--root", str(ROOT),
        "adapter", "approval", "check",
        "--file", str(outside),
        "--request-id", "req-20260703-001",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 1
    result = json.loads(captured.out)
    assert result["status"] == "error"
    assert any(f["rule_id"] == "path-outside-root" for f in result["findings"])


def test_adapter_approval_check_unsafe_file(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    env_file = fake_root / ".env.json"
    env_file.write_text("{}", encoding="utf-8")
    code = main([
        "--root", str(fake_root),
        "adapter", "approval", "check",
        "--file", ".env.json",
        "--request-id", "req-20260703-001",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 1
    result = json.loads(captured.out)
    assert result["status"] == "error"
    assert any(f["rule_id"] == "unsafe-envelope-file" for f in result["findings"])


def test_adapter_approval_check_human_output(capsys, tmp_path):
    def modify(env):
        for artifact in env["artifacts"]:
            if artifact["artifact_type"] == "approval_record":
                artifact["status"] = "granted"
                artifact["decision_ref"] = "decision-20260703-001"

    fake_root = _write_modified_envelope(tmp_path, modify)
    code = main([
        "--root", str(fake_root),
        "adapter", "approval", "check",
        "--file", "envelope.json",
        "--request-id", "req-20260703-001",
    ])
    captured = capsys.readouterr()
    assert code == 0
    assert "PASS" in captured.out
    assert "request_id=req-20260703-001" in captured.out
    assert "approval_status=granted" in captured.out
    assert "decision_ref=decision-20260703-001" in captured.out
    assert '"input"' not in captured.out
    assert '"remote"' not in captured.out


def test_adapter_approval_check_does_not_write_ledger(capsys, tmp_path):
    tasks_src = ROOT / "tasks" / "tasks.jsonl"
    events_src = ROOT / "tasks" / "events.jsonl"
    tasks_copy = tmp_path / "tasks.jsonl"
    events_copy = tmp_path / "events.jsonl"
    tasks_copy.write_bytes(tasks_src.read_bytes())
    events_copy.write_bytes(events_src.read_bytes())

    fake_root = _write_modified_envelope(tmp_path, lambda env: None)
    code = main([
        "--root", str(fake_root),
        "adapter", "approval", "check",
        "--file", "envelope.json",
        "--request-id", "req-20260703-001",
    ])
    assert code == 3
    assert tasks_src.read_bytes() == tasks_copy.read_bytes()
    assert events_src.read_bytes() == events_copy.read_bytes()
