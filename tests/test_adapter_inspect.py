"""Tests for adapter envelope inspect CLI."""

from __future__ import annotations

import json
from pathlib import Path

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


def test_adapter_inspect_examples_human(capsys):
    code = main([
        "--root", str(ROOT),
        "adapter", "inspect",
        "--file", "adapters/execution-envelope.examples.json",
    ])
    captured = capsys.readouterr()
    assert code == 0
    assert "PASS" in captured.out
    assert "Envelope: version=1" in captured.out
    assert "Artifact counts:" in captured.out
    assert "adapter_request=2" in captured.out
    assert "req-20260703-001" in captured.out
    assert "req-20260703-002" in captured.out
    # Must not echo the input payload or full artifact content.
    assert '"input"' not in captured.out
    assert '"remote"' not in captured.out
    assert '"branch"' not in captured.out


def test_adapter_inspect_json_output(capsys):
    code = main([
        "--root", str(ROOT),
        "adapter", "inspect",
        "--file", "adapters/execution-envelope.examples.json",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 0
    result = json.loads(captured.out)
    assert result["status"] == "pass"
    summary = result["summary"]
    assert summary["version"] == 1
    assert summary["description"]
    assert summary["artifact_counts"]["adapter_request"] == 2
    assert summary["artifact_counts"]["approval_record"] == 1
    assert summary["artifact_counts"]["adapter_response"] == 1
    assert summary["artifact_counts"]["execution_event"] == 2
    assert len(summary["requests"]) == 2
    assert summary["requests"][0]["request_id"] == "req-20260703-001"
    assert summary["requests"][0]["preflight_status"] == "needs_approval"
    assert summary["requests"][0]["requires_approval"] is True
    assert len(summary["approvals"]) == 1
    assert summary["approvals"][0]["approval_id"] == "appr-20260703-001"
    assert summary["approvals"][0]["status"] == "pending"
    assert len(summary["responses"]) == 1
    assert summary["responses"][0]["response_id"] == "resp-20260703-001"
    assert summary["responses"][0]["evidence_count"] == 1
    assert summary["events"]["approval_requested"] == 1
    assert summary["events"]["evidence_added"] == 1
    assert summary["overall"]["requires_approval_count"] == 1
    assert summary["overall"]["pending_approval_count"] == 1
    assert summary["overall"]["response_count"] == 1
    assert summary["overall"]["evidence_count"] == 1


def test_adapter_inspect_invalid_envelope_no_summary(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    bad_file = fake_root / "bad.json"
    bad_file.write_text("{not json", encoding="utf-8")
    code = main([
        "--root", str(fake_root),
        "adapter", "inspect",
        "--file", "bad.json",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 5
    result = json.loads(captured.out)
    assert result["status"] == "validation_failed"
    assert "summary" not in result


def test_adapter_inspect_schema_invalid_no_summary(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    bad_file = fake_root / "bad.json"
    bad_file.write_text(
        json.dumps({"version": 1, "description": "bad", "artifacts": []}),
        encoding="utf-8",
    )
    code = main([
        "--root", str(fake_root),
        "adapter", "inspect",
        "--file", "bad.json",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 5
    result = json.loads(captured.out)
    assert result["status"] == "validation_failed"
    assert "summary" not in result
    assert '"description": "bad"' not in captured.out


def test_adapter_inspect_outside_root(capsys, tmp_path):
    outside = tmp_path / "outside.json"
    outside.write_text("{}", encoding="utf-8")
    code = main([
        "--root", str(ROOT),
        "adapter", "inspect",
        "--file", str(outside),
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 1
    result = json.loads(captured.out)
    assert result["status"] == "error"
    assert "path-outside-root" in {f["rule_id"] for f in result["findings"]}


def test_adapter_inspect_unsafe_file(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    env_file = fake_root / ".env.json"
    env_file.write_text("{}", encoding="utf-8")
    code = main([
        "--root", str(fake_root),
        "adapter", "inspect",
        "--file", ".env.json",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 1
    result = json.loads(captured.out)
    assert result["status"] == "error"
    assert "unsafe-envelope-file" in {f["rule_id"] for f in result["findings"]}


def test_adapter_inspect_does_not_write_ledger(capsys, tmp_path):
    tasks_src = ROOT / "tasks" / "tasks.jsonl"
    events_src = ROOT / "tasks" / "events.jsonl"
    tasks_copy = tmp_path / "tasks.jsonl"
    events_copy = tmp_path / "events.jsonl"
    tasks_copy.write_bytes(tasks_src.read_bytes())
    events_copy.write_bytes(events_src.read_bytes())

    code = main([
        "--root", str(ROOT),
        "adapter", "inspect",
        "--file", "adapters/execution-envelope.examples.json",
    ])
    assert code == 0
    assert tasks_src.read_bytes() == tasks_copy.read_bytes()
    assert events_src.read_bytes() == events_copy.read_bytes()
