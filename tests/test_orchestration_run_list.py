"""Tests for orchestration run list read-only command."""

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
    """Build a valid envelope with two adapter requests."""
    return {
        "version": 1,
        "description": "Run list test envelope",
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
                "artifact_type": "adapter_response",
                "response_id": "resp-20260709-001",
                "request_id": "req-20260709-001",
                "status": "succeeded",
                "message": "Read completed.",
                "artifacts": [],
                "evidence": [],
                "raw_ref": None,
                "error": None,
                "finished_at": "2026-07-09T10:05:00+08:00",
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
        ],
    }


def test_run_list_json_output_structure(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    envelope = _make_envelope()
    envelope_path = fake_root / "drafts" / "runtime" / "run-list.envelope.json"
    envelope_path.parent.mkdir(parents=True, exist_ok=True)
    envelope_path.write_text(json.dumps(envelope, ensure_ascii=False), encoding="utf-8")

    code = main([
        "--root", str(fake_root),
        "orchestration", "run", "list",
        "--envelope", str(envelope_path),
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 0
    result = json.loads(captured.out)
    assert result["status"] == "pass"
    assert len(result["runs"]) == 2

    by_id = {run["request_id"]: run for run in result["runs"]}
    run1 = by_id["req-20260709-001"]
    assert run1["task_id"] == "task-20260709-001"
    assert run1["adapter_id"] == "shell-local"
    assert run1["operation"] == "read_file"
    assert run1["capability"] == "inspect.repo"
    assert run1["mode"] == "dry-run"
    assert run1["status"] == "succeeded"
    assert run1["started_at"] == "2026-07-09T10:00:00+08:00"
    assert run1["ended_at"] == "2026-07-09T10:05:00+08:00"

    run2 = by_id["req-20260709-002"]
    assert run2["task_id"] == "task-20260709-002"
    assert run2["status"] == "needs_approval"
    assert run2["ended_at"] == ""


def test_run_list_human_readable_smoke(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    envelope = _make_envelope()
    envelope_path = fake_root / "drafts" / "runtime" / "run-list.envelope.json"
    envelope_path.parent.mkdir(parents=True, exist_ok=True)
    envelope_path.write_text(json.dumps(envelope, ensure_ascii=False), encoding="utf-8")

    code = main([
        "--root", str(fake_root),
        "orchestration", "run", "list",
        "--envelope", str(envelope_path),
    ])
    captured = capsys.readouterr()
    assert code == 0
    assert "RUN LIST" in captured.out
    assert "req-20260709-001" in captured.out
    assert "req-20260709-002" in captured.out


def test_run_list_missing_envelope(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)

    code = main([
        "--root", str(fake_root),
        "orchestration", "run", "list",
        "--envelope", "drafts/runtime/nonexistent.envelope.json",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code != 0
    result = json.loads(captured.out)
    assert result["status"] == "error"


def test_run_list_invalid_envelope(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    envelope_path = fake_root / "drafts" / "runtime" / "run-list.envelope.json"
    envelope_path.parent.mkdir(parents=True, exist_ok=True)
    envelope_path.write_text("{\"invalid\": true}", encoding="utf-8")

    code = main([
        "--root", str(fake_root),
        "orchestration", "run", "list",
        "--envelope", str(envelope_path),
        "--json",
    ])
    captured = capsys.readouterr()
    assert code != 0
    result = json.loads(captured.out)
    assert result["status"] == "validation_failed"


def test_run_list_task_id_filter(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    envelope = _make_envelope()
    envelope_path = fake_root / "drafts" / "runtime" / "run-list.envelope.json"
    envelope_path.parent.mkdir(parents=True, exist_ok=True)
    envelope_path.write_text(json.dumps(envelope, ensure_ascii=False), encoding="utf-8")

    code = main([
        "--root", str(fake_root),
        "orchestration", "run", "list",
        "--envelope", str(envelope_path),
        "--task-id", "task-20260709-001",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 0
    result = json.loads(captured.out)
    assert len(result["runs"]) == 1
    assert result["runs"][0]["request_id"] == "req-20260709-001"


def test_run_list_does_not_write_files(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    envelope = _make_envelope()
    envelope_path = fake_root / "drafts" / "runtime" / "run-list.envelope.json"
    envelope_path.parent.mkdir(parents=True, exist_ok=True)
    envelope_path.write_text(json.dumps(envelope, ensure_ascii=False), encoding="utf-8")
    envelope_before = envelope_path.read_bytes()

    code = main([
        "--root", str(fake_root),
        "orchestration", "run", "list",
        "--envelope", str(envelope_path),
        "--json",
    ])
    assert code == 0
    assert envelope_path.read_bytes() == envelope_before
