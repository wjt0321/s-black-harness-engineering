"""Tests for runtime draft export --commit."""

from __future__ import annotations

import io
import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from agent_runtime.cli import main
from agent_runtime.result import CheckResult, Finding


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


def test_commit_pass_writes_file(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    output_path = "drafts/runtime/task-001/req-001.envelope.json"
    draft_file = fake_root / "draft.json"
    draft_file.write_text(json.dumps(_valid_envelope()), encoding="utf-8")

    code = main([
        "--root", str(fake_root),
        "runtime", "draft", "export",
        "--file", "draft.json",
        "--output", output_path,
        "--commit",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 0
    result = json.loads(captured.out)
    assert result["status"] == "pass"
    assert result["committed"] is True
    assert result["post_validate"] == "pass"
    assert result["post_inspect"] == "pass"
    assert result["artifact_counts"]["adapter_request"] == 1

    written = fake_root / output_path
    assert written.exists()
    validate_code = main([
        "--root", str(fake_root),
        "runtime", "draft", "validate",
        "--file", output_path,
    ])
    assert validate_code == 0


def test_commit_creates_parent_dirs(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    output_path = "drafts/runtime/nested/deep/req-002.envelope.json"
    draft_file = fake_root / "draft.json"
    draft_file.write_text(json.dumps(_valid_envelope()), encoding="utf-8")

    code = main([
        "--root", str(fake_root),
        "runtime", "draft", "export",
        "--file", "draft.json",
        "--output", output_path,
        "--commit",
        "--json",
    ])
    assert code == 0
    assert (fake_root / output_path).exists()


def test_commit_dry_run_no_write(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    output_path = "drafts/runtime/task-001/req-001.envelope.json"
    draft_file = fake_root / "draft.json"
    draft_file.write_text(json.dumps(_valid_envelope()), encoding="utf-8")

    code = main([
        "--root", str(fake_root),
        "runtime", "draft", "export",
        "--file", "draft.json",
        "--output", output_path,
        "--dry-run",
        "--json",
    ])
    assert code == 0
    assert not (fake_root / output_path).exists()


def test_commit_dry_run_and_commit_exclusive(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    draft_file = fake_root / "draft.json"
    draft_file.write_text(json.dumps(_valid_envelope()), encoding="utf-8")

    code = main([
        "--root", str(fake_root),
        "runtime", "draft", "export",
        "--file", "draft.json",
        "--output", "drafts/runtime/out.json",
        "--dry-run",
        "--commit",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 1
    result = json.loads(captured.out)
    assert result["status"] == "error"
    assert "dry-run-commit-mutually-exclusive" in {f["rule_id"] for f in result["findings"]}


def test_commit_neither_flag_errors(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    draft_file = fake_root / "draft.json"
    draft_file.write_text(json.dumps(_valid_envelope()), encoding="utf-8")

    code = main([
        "--root", str(fake_root),
        "runtime", "draft", "export",
        "--file", "draft.json",
        "--output", "drafts/runtime/out.json",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 1
    result = json.loads(captured.out)
    assert result["status"] == "error"
    assert "missing-export-mode" in {f["rule_id"] for f in result["findings"]}


def test_commit_outside_drafts_runtime_blocked(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    draft_file = fake_root / "draft.json"
    draft_file.write_text(json.dumps(_valid_envelope()), encoding="utf-8")

    code = main([
        "--root", str(fake_root),
        "runtime", "draft", "export",
        "--file", "draft.json",
        "--output", "other.json",
        "--commit",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 2
    result = json.loads(captured.out)
    assert result["status"] == "blocked"
    assert "output-path-not-in-drafts-runtime" in {f["rule_id"] for f in result["findings"]}
    assert not (fake_root / "other.json").exists()


def test_commit_existing_output_blocked(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    output_path = "drafts/runtime/out.json"
    existing = fake_root / output_path
    existing.parent.mkdir(parents=True, exist_ok=True)
    existing.write_text("{}", encoding="utf-8")
    draft_file = fake_root / "draft.json"
    draft_file.write_text(json.dumps(_valid_envelope()), encoding="utf-8")

    code = main([
        "--root", str(fake_root),
        "runtime", "draft", "export",
        "--file", "draft.json",
        "--output", output_path,
        "--commit",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 2
    result = json.loads(captured.out)
    assert result["status"] == "blocked"
    assert "output-file-exists" in {f["rule_id"] for f in result["findings"]}
    assert existing.read_text(encoding="utf-8") == "{}"


def test_commit_schema_invalid_no_write(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    draft_file = fake_root / "draft.json"
    draft_file.write_text(json.dumps({"version": 1, "artifacts": []}), encoding="utf-8")

    code = main([
        "--root", str(fake_root),
        "runtime", "draft", "export",
        "--file", "draft.json",
        "--output", "drafts/runtime/out.json",
        "--commit",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 5
    result = json.loads(captured.out)
    assert result["status"] == "validation_failed"
    assert not (fake_root / "drafts" / "runtime" / "out.json").exists()


def test_commit_secret_blocked_no_write(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    envelope = _valid_envelope()
    token = "ghp_" + "X" * 36
    envelope["artifacts"][0]["target"] = token
    draft_file = fake_root / "draft.json"
    draft_file.write_text(json.dumps(envelope), encoding="utf-8")

    code = main([
        "--root", str(fake_root),
        "runtime", "draft", "export",
        "--file", "draft.json",
        "--output", "drafts/runtime/out.json",
        "--commit",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 2
    result = json.loads(captured.out)
    assert result["status"] == "blocked"
    assert "github-token" in {f["rule_id"] for f in result["findings"]}
    assert token not in captured.out
    assert not (fake_root / "drafts" / "runtime" / "out.json").exists()


def test_commit_public_scan_blocked_no_write(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    envelope = _valid_envelope()
    windows_path = "C:" + "\\Users\\foo\\secret.txt"
    envelope["artifacts"][0]["target"] = windows_path
    draft_file = fake_root / "draft.json"
    draft_file.write_text(json.dumps(envelope), encoding="utf-8")

    code = main([
        "--root", str(fake_root),
        "runtime", "draft", "export",
        "--file", "draft.json",
        "--output", "drafts/runtime/out.json",
        "--commit",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 2
    result = json.loads(captured.out)
    assert result["status"] == "blocked"
    assert "windows-absolute-path" in {f["rule_id"] for f in result["findings"]}
    assert windows_path not in captured.out
    assert not (fake_root / "drafts" / "runtime" / "out.json").exists()


def test_commit_post_validation_failure_rolls_back(monkeypatch, capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    output_path = "drafts/runtime/task-001/req-001.envelope.json"
    draft_file = fake_root / "draft.json"
    draft_file.write_text(json.dumps(_valid_envelope()), encoding="utf-8")

    failing_result = CheckResult(
        status="validation_failed",
        findings=[
            Finding(
                rule_id="post-check-failed",
                severity="error",
                action="error",
                message="Simulated post-write validation failure.",
            )
        ],
    )
    monkeypatch.setattr(
        "agent_runtime.runtime_draft_export.validate_runtime_draft",
        lambda _root, file: failing_result,
    )

    code = main([
        "--root", str(fake_root),
        "runtime", "draft", "export",
        "--file", "draft.json",
        "--output", output_path,
        "--commit",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 5
    result = json.loads(captured.out)
    assert result["status"] == "validation_failed"
    assert "post-check-failed" in {f["rule_id"] for f in result["findings"]}
    assert "rolled back" in result["next_action"].lower()
    assert not (fake_root / output_path).exists()
