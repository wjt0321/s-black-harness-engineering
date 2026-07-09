"""Tests for orchestration artifact list/get read-only commands."""

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
    """Build a valid envelope with mixed artifact types."""
    return {
        "version": 1,
        "description": "Artifact test envelope",
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
            {
                "artifact_type": "execution_event",
                "event_id": "evt-20260709-003",
                "task_id": "task-20260709-001",
                "request_id": "req-20260709-001",
                "timestamp": "2026-07-09T10:06:00+08:00",
                "actor": "runtime",
                "event_type": "adapter_response_recorded",
                "message": "Response recorded.",
                "metadata": {},
            },
        ],
    }


def test_artifact_list_json_output_structure(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    envelope = _make_envelope()
    envelope_path = fake_root / "drafts" / "runtime" / "artifact.envelope.json"
    envelope_path.parent.mkdir(parents=True, exist_ok=True)
    envelope_path.write_text(json.dumps(envelope, ensure_ascii=False), encoding="utf-8")

    code = main([
        "--root", str(fake_root),
        "orchestration", "artifact", "list",
        "--envelope", str(envelope_path),
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 0
    result = json.loads(captured.out)
    assert result["status"] == "pass"
    assert len(result["artifacts"]) == 5

    by_id = {a["artifact_id"]: a for a in result["artifacts"]}
    req = by_id["req-20260709-001"]
    assert req["artifact_type"] == "adapter_request"
    assert req["task_id"] == "task-20260709-001"
    assert req["request_id"] == "req-20260709-001"
    assert req["producer"] == "shell-local"
    assert req["summary"] == "read_file on docs/06-adapter-layer.md"
    assert req["safe_to_preview"] is True

    resp = by_id["resp-20260709-001"]
    assert resp["artifact_type"] == "adapter_response"
    assert resp["request_id"] == "req-20260709-001"
    assert resp["summary"] == "status=succeeded"

    appr = by_id["appr-20260709-002"]
    assert appr["artifact_type"] == "approval_record"
    assert appr["task_id"] == "task-20260709-002"

    evt = by_id["evt-20260709-003"]
    assert evt["artifact_type"] == "execution_event"
    assert evt["summary"] == "adapter_response_recorded"


def test_artifact_list_human_readable_smoke(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    envelope = _make_envelope()
    envelope_path = fake_root / "drafts" / "runtime" / "artifact.envelope.json"
    envelope_path.parent.mkdir(parents=True, exist_ok=True)
    envelope_path.write_text(json.dumps(envelope, ensure_ascii=False), encoding="utf-8")

    code = main([
        "--root", str(fake_root),
        "orchestration", "artifact", "list",
        "--envelope", str(envelope_path),
    ])
    captured = capsys.readouterr()
    assert code == 0
    assert "ARTIFACT LIST" in captured.out
    assert "req-20260709-001" in captured.out
    assert "resp-20260709-001" in captured.out


def test_artifact_list_type_filter(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    envelope = _make_envelope()
    envelope_path = fake_root / "drafts" / "runtime" / "artifact.envelope.json"
    envelope_path.parent.mkdir(parents=True, exist_ok=True)
    envelope_path.write_text(json.dumps(envelope, ensure_ascii=False), encoding="utf-8")

    code = main([
        "--root", str(fake_root),
        "orchestration", "artifact", "list",
        "--envelope", str(envelope_path),
        "--type", "execution_event",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 0
    result = json.loads(captured.out)
    assert len(result["artifacts"]) == 1
    assert result["artifacts"][0]["artifact_id"] == "evt-20260709-003"


def test_artifact_list_request_id_filter(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    envelope = _make_envelope()
    envelope_path = fake_root / "drafts" / "runtime" / "artifact.envelope.json"
    envelope_path.parent.mkdir(parents=True, exist_ok=True)
    envelope_path.write_text(json.dumps(envelope, ensure_ascii=False), encoding="utf-8")

    code = main([
        "--root", str(fake_root),
        "orchestration", "artifact", "list",
        "--envelope", str(envelope_path),
        "--request-id", "req-20260709-001",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 0
    result = json.loads(captured.out)
    assert len(result["artifacts"]) == 3
    ids = {a["artifact_id"] for a in result["artifacts"]}
    assert ids == {"req-20260709-001", "resp-20260709-001", "evt-20260709-003"}


def test_artifact_get_json_output_structure(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    envelope = _make_envelope()
    envelope_path = fake_root / "drafts" / "runtime" / "artifact.envelope.json"
    envelope_path.parent.mkdir(parents=True, exist_ok=True)
    envelope_path.write_text(json.dumps(envelope, ensure_ascii=False), encoding="utf-8")

    code = main([
        "--root", str(fake_root),
        "orchestration", "artifact", "get",
        "--artifact-id", "resp-20260709-001",
        "--envelope", str(envelope_path),
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 0
    result = json.loads(captured.out)
    assert result["status"] == "pass"
    artifact = result["artifact"]
    assert artifact["artifact_id"] == "resp-20260709-001"
    assert artifact["artifact_type"] == "adapter_response"
    assert artifact["metadata"]["status"] == "succeeded"
    assert artifact["metadata"]["artifact_count"] == 0
    assert artifact["metadata"]["evidence_count"] == 0
    assert artifact["metadata"]["has_raw_ref"] is False
    assert "input" not in artifact["metadata"]

    related = result["related_request"]
    assert related["request_id"] == "req-20260709-001"
    assert related["capability"] == "inspect.repo"
    assert "input" not in related


def test_artifact_get_human_readable_smoke(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    envelope = _make_envelope()
    envelope_path = fake_root / "drafts" / "runtime" / "artifact.envelope.json"
    envelope_path.parent.mkdir(parents=True, exist_ok=True)
    envelope_path.write_text(json.dumps(envelope, ensure_ascii=False), encoding="utf-8")

    code = main([
        "--root", str(fake_root),
        "orchestration", "artifact", "get",
        "--artifact-id", "req-20260709-001",
        "--envelope", str(envelope_path),
    ])
    captured = capsys.readouterr()
    assert code == 0
    assert "ARTIFACT GET" in captured.out
    assert "req-20260709-001" in captured.out
    assert "shell-local" in captured.out


def test_artifact_get_not_found(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    envelope = _make_envelope()
    envelope_path = fake_root / "drafts" / "runtime" / "artifact.envelope.json"
    envelope_path.parent.mkdir(parents=True, exist_ok=True)
    envelope_path.write_text(json.dumps(envelope, ensure_ascii=False), encoding="utf-8")

    code = main([
        "--root", str(fake_root),
        "orchestration", "artifact", "get",
        "--artifact-id", "artifact-missing",
        "--envelope", str(envelope_path),
        "--json",
    ])
    captured = capsys.readouterr()
    assert code != 0
    result = json.loads(captured.out)
    assert result["status"] == "needs_input"


def test_artifact_missing_envelope(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)

    code = main([
        "--root", str(fake_root),
        "orchestration", "artifact", "list",
        "--envelope", "drafts/runtime/nonexistent.envelope.json",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code != 0
    result = json.loads(captured.out)
    assert result["status"] == "error"


def test_artifact_invalid_envelope(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    envelope_path = fake_root / "drafts" / "runtime" / "artifact.envelope.json"
    envelope_path.parent.mkdir(parents=True, exist_ok=True)
    envelope_path.write_text('{"invalid": true}', encoding="utf-8")

    code = main([
        "--root", str(fake_root),
        "orchestration", "artifact", "list",
        "--envelope", str(envelope_path),
        "--json",
    ])
    captured = capsys.readouterr()
    assert code != 0
    result = json.loads(captured.out)
    assert result["status"] == "validation_failed"


def test_artifact_list_does_not_write_files(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    envelope = _make_envelope()
    envelope_path = fake_root / "drafts" / "runtime" / "artifact.envelope.json"
    envelope_path.parent.mkdir(parents=True, exist_ok=True)
    envelope_path.write_text(json.dumps(envelope, ensure_ascii=False), encoding="utf-8")
    envelope_before = envelope_path.read_bytes()

    code = main([
        "--root", str(fake_root),
        "orchestration", "artifact", "list",
        "--envelope", str(envelope_path),
        "--json",
    ])
    assert code == 0
    assert envelope_path.read_bytes() == envelope_before


def test_artifact_get_does_not_write_files(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    envelope = _make_envelope()
    envelope_path = fake_root / "drafts" / "runtime" / "artifact.envelope.json"
    envelope_path.parent.mkdir(parents=True, exist_ok=True)
    envelope_path.write_text(json.dumps(envelope, ensure_ascii=False), encoding="utf-8")
    envelope_before = envelope_path.read_bytes()

    code = main([
        "--root", str(fake_root),
        "orchestration", "artifact", "get",
        "--artifact-id", "req-20260709-001",
        "--envelope", str(envelope_path),
        "--json",
    ])
    assert code == 0
    assert envelope_path.read_bytes() == envelope_before
