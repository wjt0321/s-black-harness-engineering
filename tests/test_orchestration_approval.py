"""Tests for orchestration approval list/get read-only commands."""

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


def _make_envelope() -> dict[str, Any]:
    """Build a valid envelope with two approvals and matching requests."""
    return {
        "version": 1,
        "description": "Approval test envelope",
        "artifacts": [
            {
                "artifact_type": "adapter_request",
                "request_id": "req-20260709-001",
                "task_id": "task-20260709-001",
                "adapter_id": "shell-local",
                "operation": "read_file",
                "actor": "test",
                "target": "docs/06-adapter-layer.md",
                "input": {"path": "docs/06-adapter-layer.md"},
                "context": {
                    "source": "cli",
                    "policy_profile": "s-black",
                    "risk_level": "local",
                    "dry_run": True,
                    "requires_approval": False,
                    "approval_id": None,
                    "payload_refs": [],
                    "capability": "inspect.repo",
                },
                "preflight": {"status": "pass", "findings": []},
                "created_at": "2026-07-09T10:00:00+08:00",
            },
            {
                "artifact_type": "adapter_request",
                "request_id": "req-20260709-002",
                "task_id": "task-20260709-002",
                "adapter_id": "github-cli",
                "operation": "git_push",
                "actor": "test",
                "target": "origin/main",
                "input": {"remote": "origin", "branch": "main"},
                "context": {
                    "source": "cli",
                    "policy_profile": "s-black",
                    "risk_level": "external",
                    "dry_run": True,
                    "requires_approval": True,
                    "approval_id": "appr-20260709-002",
                    "payload_refs": [],
                },
                "preflight": {
                    "status": "needs_approval",
                    "findings": [
                        {
                            "rule_id": "github-cli-approval",
                            "severity": "block",
                            "action": "require_user_approval",
                            "message": "External publish operation requires explicit approval.",
                        }
                    ],
                },
                "created_at": "2026-07-09T10:10:00+08:00",
            },
            {
                "artifact_type": "approval_record",
                "approval_id": "appr-20260709-002",
                "request_id": "req-20260709-002",
                "status": "pending",
                "scope": {
                    "task_id": "task-20260709-002",
                    "adapter_id": "github-cli",
                    "operation": "git_push",
                    "target": "origin/main",
                },
                "requested_at": "2026-07-09T10:10:01+08:00",
                "decided_at": None,
                "decided_by": None,
                "decision_ref": None,
            },
            {
                "artifact_type": "adapter_request",
                "request_id": "req-20260709-003",
                "task_id": "task-20260709-003",
                "adapter_id": "lark-message",
                "operation": "send_message",
                "actor": "test",
                "target": "user-001",
                "input": {"content": "hello"},
                "context": {
                    "source": "cli",
                    "policy_profile": "s-black",
                    "risk_level": "external",
                    "dry_run": False,
                    "requires_approval": True,
                    "approval_id": "appr-20260709-003",
                    "payload_refs": [],
                    "capability": "notify.user",
                },
                "preflight": {
                    "status": "needs_approval",
                    "findings": [],
                },
                "created_at": "2026-07-09T10:20:00+08:00",
            },
            {
                "artifact_type": "approval_record",
                "approval_id": "appr-20260709-003",
                "request_id": "req-20260709-003",
                "status": "granted",
                "scope": {
                    "task_id": "task-20260709-003",
                    "adapter_id": "lark-message",
                    "operation": "send_message",
                    "target": "user-001",
                },
                "requested_at": "2026-07-09T10:20:01+08:00",
                "decided_at": "2026-07-09T10:21:00+08:00",
                "decided_by": "user-admin",
                "decision_ref": "decision-20260709-003",
            },
        ],
    }


def test_approval_list_json_output_structure(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    envelope = _make_envelope()
    envelope_path = fake_root / "drafts" / "runtime" / "approval.envelope.json"
    envelope_path.parent.mkdir(parents=True, exist_ok=True)
    envelope_path.write_text(json.dumps(envelope, ensure_ascii=False), encoding="utf-8")

    code = main([
        "--root", str(fake_root),
        "orchestration", "approval", "list",
        "--envelope", str(envelope_path),
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 0
    result = json.loads(captured.out)
    assert result["status"] == "pass"
    assert len(result["approvals"]) == 2

    by_id = {a["approval_id"]: a for a in result["approvals"]}
    appr2 = by_id["appr-20260709-002"]
    assert appr2["request_id"] == "req-20260709-002"
    assert appr2["task_id"] == "task-20260709-002"
    assert appr2["adapter_id"] == "github-cli"
    assert appr2["operation"] == "git_push"
    assert appr2["target"] == "origin/main"
    assert appr2["status"] == "pending"
    assert appr2["requested_at"] == "2026-07-09T10:10:01+08:00"
    assert appr2["resolved_at"] == ""
    assert appr2["resolver"] == ""

    appr3 = by_id["appr-20260709-003"]
    assert appr3["status"] == "granted"
    assert appr3["resolved_at"] == "2026-07-09T10:21:00+08:00"
    assert appr3["resolver"] == "user-admin"


def test_approval_list_human_readable_smoke(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    envelope = _make_envelope()
    envelope_path = fake_root / "drafts" / "runtime" / "approval.envelope.json"
    envelope_path.parent.mkdir(parents=True, exist_ok=True)
    envelope_path.write_text(json.dumps(envelope, ensure_ascii=False), encoding="utf-8")

    code = main([
        "--root", str(fake_root),
        "orchestration", "approval", "list",
        "--envelope", str(envelope_path),
    ])
    captured = capsys.readouterr()
    assert code == 0
    assert "APPROVAL LIST" in captured.out
    assert "appr-20260709-002" in captured.out
    assert "appr-20260709-003" in captured.out


def test_approval_list_status_filter(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    envelope = _make_envelope()
    envelope_path = fake_root / "drafts" / "runtime" / "approval.envelope.json"
    envelope_path.parent.mkdir(parents=True, exist_ok=True)
    envelope_path.write_text(json.dumps(envelope, ensure_ascii=False), encoding="utf-8")

    code = main([
        "--root", str(fake_root),
        "orchestration", "approval", "list",
        "--envelope", str(envelope_path),
        "--status", "granted",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 0
    result = json.loads(captured.out)
    assert len(result["approvals"]) == 1
    assert result["approvals"][0]["approval_id"] == "appr-20260709-003"


def test_approval_get_json_output_structure(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    envelope = _make_envelope()
    envelope_path = fake_root / "drafts" / "runtime" / "approval.envelope.json"
    envelope_path.parent.mkdir(parents=True, exist_ok=True)
    envelope_path.write_text(json.dumps(envelope, ensure_ascii=False), encoding="utf-8")

    code = main([
        "--root", str(fake_root),
        "orchestration", "approval", "get",
        "--approval-id", "appr-20260709-003",
        "--envelope", str(envelope_path),
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 0
    result = json.loads(captured.out)
    assert result["status"] == "pass"
    approval = result["approval"]
    assert approval["approval_id"] == "appr-20260709-003"
    assert approval["status"] == "granted"
    assert approval["scope"]["task_id"] == "task-20260709-003"
    assert approval["resolved_at"] == "2026-07-09T10:21:00+08:00"
    assert approval["resolver"] == "user-admin"
    assert "decision_ref" not in approval

    related = result["related_request"]
    assert related["request_id"] == "req-20260709-003"
    assert related["capability"] == "notify.user"
    assert related["risk_level"] == "external"
    assert "input" not in related


def test_approval_get_human_readable_smoke(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    envelope = _make_envelope()
    envelope_path = fake_root / "drafts" / "runtime" / "approval.envelope.json"
    envelope_path.parent.mkdir(parents=True, exist_ok=True)
    envelope_path.write_text(json.dumps(envelope, ensure_ascii=False), encoding="utf-8")

    code = main([
        "--root", str(fake_root),
        "orchestration", "approval", "get",
        "--approval-id", "appr-20260709-002",
        "--envelope", str(envelope_path),
    ])
    captured = capsys.readouterr()
    assert code == 0
    assert "APPROVAL GET" in captured.out
    assert "appr-20260709-002" in captured.out
    assert "github-cli" in captured.out


def test_approval_get_not_found(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    envelope = _make_envelope()
    envelope_path = fake_root / "drafts" / "runtime" / "approval.envelope.json"
    envelope_path.parent.mkdir(parents=True, exist_ok=True)
    envelope_path.write_text(json.dumps(envelope, ensure_ascii=False), encoding="utf-8")

    code = main([
        "--root", str(fake_root),
        "orchestration", "approval", "get",
        "--approval-id", "appr-missing",
        "--envelope", str(envelope_path),
        "--json",
    ])
    captured = capsys.readouterr()
    assert code != 0
    result = json.loads(captured.out)
    assert result["status"] == "needs_input"


def test_approval_missing_envelope(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)

    code = main([
        "--root", str(fake_root),
        "orchestration", "approval", "list",
        "--envelope", "drafts/runtime/nonexistent.envelope.json",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code != 0
    result = json.loads(captured.out)
    assert result["status"] == "error"


def test_approval_invalid_envelope(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    envelope_path = fake_root / "drafts" / "runtime" / "approval.envelope.json"
    envelope_path.parent.mkdir(parents=True, exist_ok=True)
    envelope_path.write_text('{"invalid": true}', encoding="utf-8")

    code = main([
        "--root", str(fake_root),
        "orchestration", "approval", "list",
        "--envelope", str(envelope_path),
        "--json",
    ])
    captured = capsys.readouterr()
    assert code != 0
    result = json.loads(captured.out)
    assert result["status"] == "validation_failed"


def test_approval_list_does_not_write_files(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    envelope = _make_envelope()
    envelope_path = fake_root / "drafts" / "runtime" / "approval.envelope.json"
    envelope_path.parent.mkdir(parents=True, exist_ok=True)
    envelope_path.write_text(json.dumps(envelope, ensure_ascii=False), encoding="utf-8")
    envelope_before = envelope_path.read_bytes()

    code = main([
        "--root", str(fake_root),
        "orchestration", "approval", "list",
        "--envelope", str(envelope_path),
        "--json",
    ])
    assert code == 0
    assert envelope_path.read_bytes() == envelope_before


def test_approval_get_does_not_write_files(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    envelope = _make_envelope()
    envelope_path = fake_root / "drafts" / "runtime" / "approval.envelope.json"
    envelope_path.parent.mkdir(parents=True, exist_ok=True)
    envelope_path.write_text(json.dumps(envelope, ensure_ascii=False), encoding="utf-8")
    envelope_before = envelope_path.read_bytes()

    code = main([
        "--root", str(fake_root),
        "orchestration", "approval", "get",
        "--approval-id", "appr-20260709-002",
        "--envelope", str(envelope_path),
        "--json",
    ])
    assert code == 0
    assert envelope_path.read_bytes() == envelope_before
