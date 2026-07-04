"""Tests for runtime draft validate / inspect CLI."""

from __future__ import annotations

import io
import json
import shutil
from pathlib import Path
from typing import Any

from agent_runtime.cli import main


ROOT = Path(__file__).resolve().parents[1]


def _setup_fake_root(tmp_path: Path) -> Path:
    """Create a fake project root with the envelope schema and sample registries."""
    fake_root = tmp_path / "project"
    fake_root.mkdir(parents=True, exist_ok=True)

    for src_rel in (
        "adapters/execution-envelope.schema.json",
        "adapters/adapters.sample.json",
        "agents/agents.sample.json",
    ):
        src = ROOT / src_rel
        dst = fake_root / src_rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)

    policy_src = ROOT / "policies"
    policy_dst = fake_root / "policies"
    policy_dst.mkdir(parents=True, exist_ok=True)
    for policy_file in policy_src.glob("*.sample.policy.json"):
        shutil.copyfile(policy_file, policy_dst / policy_file.name)

    return fake_root


def _valid_envelope(
    task_id: str = "task-20260703-001",
    adapter_id: str = "shell-local",
    operation: str = "read_file",
    target: str = "docs/06-adapter-layer.md",
    preflight_status: str = "pass",
    requires_approval: bool = False,
) -> dict[str, Any]:
    """Return a minimal schema-valid envelope draft."""
    request_id = "req-20260703-001"
    envelope: dict[str, Any] = {
        "version": 1,
        "description": "Runtime plan envelope draft",
        "artifacts": [
            {
                "artifact_type": "adapter_request",
                "request_id": request_id,
                "task_id": task_id,
                "adapter_id": adapter_id,
                "operation": operation,
                "actor": "cli",
                "target": target,
                "input": {"operation": operation, "target": target},
                "context": {
                    "source": "cli",
                    "policy_profile": "all",
                    "risk_level": "local",
                    "dry_run": True,
                    "requires_approval": requires_approval,
                    "approval_id": None,
                    "payload_refs": [],
                },
                "preflight": {"status": preflight_status, "findings": []},
                "created_at": "2026-07-03T10:00:00+08:00",
            }
        ],
    }

    if requires_approval:
        approval_id = "appr-20260703-001"
        envelope["artifacts"][0]["context"]["approval_id"] = approval_id
        envelope["artifacts"].append(
            {
                "artifact_type": "approval_record",
                "approval_id": approval_id,
                "request_id": request_id,
                "status": "pending",
                "scope": {
                    "task_id": task_id,
                    "adapter_id": adapter_id,
                    "operation": operation,
                    "target": target,
                },
                "requested_at": "2026-07-03T10:00:01+08:00",
                "decided_at": None,
                "decided_by": None,
            }
        )
        envelope["artifacts"].append(
            {
                "artifact_type": "execution_event",
                "event_id": "evt-20260703-001",
                "task_id": task_id,
                "request_id": request_id,
                "timestamp": "2026-07-03T10:00:02+08:00",
                "actor": "cli",
                "event_type": "approval_requested",
                "message": "Approval requested before adapter execution.",
                "metadata": {
                    "approval_id": approval_id,
                    "adapter_id": adapter_id,
                    "operation": operation,
                    "target": target,
                    "preflight_status": preflight_status,
                },
            }
        )

    return envelope


def test_runtime_draft_validate_file_pass(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    draft_file = fake_root / "draft.json"
    draft_file.write_text(json.dumps(_valid_envelope()), encoding="utf-8")

    code = main([
        "--root", str(fake_root),
        "runtime", "draft", "validate",
        "--file", "draft.json",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 0
    result = json.loads(captured.out)
    assert result["status"] == "pass"
    assert "draft.json" in result["next_action"]


def test_runtime_draft_validate_stdin_pass(monkeypatch, capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(_valid_envelope())))

    code = main([
        "--root", str(fake_root),
        "runtime", "draft", "validate",
        "--stdin",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 0
    result = json.loads(captured.out)
    assert result["status"] == "pass"
    assert "<stdin>" in result["next_action"]


def test_runtime_draft_validate_outer_wrapper_pass(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    wrapper = {
        "status": "pass",
        "task_id": "task-20260703-001",
        "task_status": "running",
        "envelope_draft": _valid_envelope(),
    }
    draft_file = fake_root / "draft.json"
    draft_file.write_text(json.dumps(wrapper), encoding="utf-8")

    code = main([
        "--root", str(fake_root),
        "runtime", "draft", "validate",
        "--file", "draft.json",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 0
    result = json.loads(captured.out)
    assert result["status"] == "pass"


def test_runtime_draft_validate_schema_invalid(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    bad = {"version": 1, "description": "bad", "artifacts": []}
    draft_file = fake_root / "draft.json"
    draft_file.write_text(json.dumps(bad), encoding="utf-8")

    code = main([
        "--root", str(fake_root),
        "runtime", "draft", "validate",
        "--file", "draft.json",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 5
    result = json.loads(captured.out)
    assert result["status"] == "validation_failed"
    assert "envelope-schema-validation-failed" in {f["rule_id"] for f in result["findings"]}
    # Must not echo the full envelope content.
    assert '"description": "bad"' not in captured.out


def test_runtime_draft_validate_consistency_invalid(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    envelope = _valid_envelope(requires_approval=True)
    for artifact in envelope["artifacts"]:
        if artifact["artifact_type"] == "approval_record":
            artifact["request_id"] = "req-20260703-999"
    draft_file = fake_root / "draft.json"
    draft_file.write_text(json.dumps(envelope), encoding="utf-8")

    code = main([
        "--root", str(fake_root),
        "runtime", "draft", "validate",
        "--file", "draft.json",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 5
    result = json.loads(captured.out)
    assert result["status"] == "validation_failed"
    assert "approval-references-unknown-request" in {f["rule_id"] for f in result["findings"]}


def test_runtime_draft_inspect_summary(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    draft_file = fake_root / "draft.json"
    draft_file.write_text(json.dumps(_valid_envelope()), encoding="utf-8")

    code = main([
        "--root", str(fake_root),
        "runtime", "draft", "inspect",
        "--file", "draft.json",
    ])
    captured = capsys.readouterr()
    assert code == 0
    text = captured.out
    assert "PASS" in text
    assert "Source: draft.json" in text
    assert "Artifact counts:" in text
    assert "adapter_request=1" in text
    assert "req-20260703-001" in text
    assert "shell-local" in text
    assert "read_file" in text
    # Draft inspect must not echo target or input payload.
    assert "docs/06-adapter-layer.md" not in text
    assert '"input"' not in text


def test_runtime_draft_inspect_json(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    wrapper = {
        "status": "needs_approval",
        "task_id": "task-20260703-001",
        "envelope_draft": _valid_envelope(requires_approval=True),
    }
    draft_file = fake_root / "draft.json"
    draft_file.write_text(json.dumps(wrapper), encoding="utf-8")

    code = main([
        "--root", str(fake_root),
        "runtime", "draft", "inspect",
        "--file", "draft.json",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 0
    result = json.loads(captured.out)
    assert result["status"] == "pass"
    summary = result["summary"]
    assert summary["source"] == "draft.json"
    assert summary["task_id"] == "task-20260703-001"
    assert summary["status"] == "needs_approval"
    assert summary["artifact_counts"]["adapter_request"] == 1
    assert summary["artifact_counts"]["approval_record"] == 1
    assert summary["artifact_counts"]["execution_event"] == 1
    assert len(summary["requests"]) == 1
    request = summary["requests"][0]
    assert request["request_id"] == "req-20260703-001"
    assert request["requires_approval"] is True
    assert "target" not in request
    assert "input" not in request


def test_runtime_draft_validate_outside_root(capsys, tmp_path):
    outside = tmp_path / "outside.json"
    outside.write_text("{}", encoding="utf-8")
    code = main([
        "--root", str(ROOT),
        "runtime", "draft", "validate",
        "--file", str(outside),
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 1
    result = json.loads(captured.out)
    assert result["status"] == "error"
    assert "path-outside-root" in {f["rule_id"] for f in result["findings"]}


def test_runtime_draft_validate_unsafe_file(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    env_file = fake_root / ".env.json"
    env_file.write_text("{}", encoding="utf-8")
    code = main([
        "--root", str(fake_root),
        "runtime", "draft", "validate",
        "--file", ".env.json",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 1
    result = json.loads(captured.out)
    assert result["status"] == "error"
    assert "unsafe-envelope-file" in {f["rule_id"] for f in result["findings"]}


def test_runtime_draft_stdin_no_write(capsys, tmp_path, monkeypatch):
    tasks_src = ROOT / "tasks" / "tasks.jsonl"
    events_src = ROOT / "tasks" / "events.jsonl"
    tasks_copy = tmp_path / "tasks.jsonl"
    events_copy = tmp_path / "events.jsonl"
    tasks_copy.write_bytes(tasks_src.read_bytes())
    events_copy.write_bytes(events_src.read_bytes())

    fake_root = _setup_fake_root(tmp_path)
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(_valid_envelope())))

    code = main([
        "--root", str(fake_root),
        "runtime", "draft", "inspect",
        "--stdin",
    ])
    assert code == 0
    assert tasks_src.read_bytes() == tasks_copy.read_bytes()
    assert events_src.read_bytes() == events_copy.read_bytes()


def test_runtime_draft_safe_output_no_sensitive_values(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    envelope = _valid_envelope(requires_approval=True)
    # These values should not appear in validate/inspect output.
    envelope["artifacts"][0]["input"]["secret_hint"] = "ssh-rsa AAAAB3NzaC1"
    envelope["artifacts"][1]["decision_ref"] = "decision-12345"
    draft_file = fake_root / "draft.json"
    draft_file.write_text(json.dumps(envelope), encoding="utf-8")

    code = main([
        "--root", str(fake_root),
        "runtime", "draft", "inspect",
        "--file", "draft.json",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 0
    text = captured.out
    assert "ssh-rsa" not in text
    assert "AAAAB3NzaC1" not in text
    assert "decision-12345" not in text
    assert "decision_ref" not in text
    assert "raw_ref" not in text


def test_runtime_draft_validate_invalid_json(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    draft_file = fake_root / "draft.json"
    draft_file.write_text("{not json", encoding="utf-8")

    code = main([
        "--root", str(fake_root),
        "runtime", "draft", "validate",
        "--file", "draft.json",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 5
    result = json.loads(captured.out)
    assert result["status"] == "validation_failed"
    assert "invalid-json" in {f["rule_id"] for f in result["findings"]}
