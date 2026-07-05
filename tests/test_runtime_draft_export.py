"""Tests for runtime draft export --dry-run."""

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


def test_export_stdin_dry_run_pass_no_write(monkeypatch, capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    output_path = "drafts/runtime/task-001/req-001.envelope.json"
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(_valid_envelope())))

    code = main([
        "--root", str(fake_root),
        "runtime", "draft", "export",
        "--stdin",
        "--output", output_path,
        "--dry-run",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 0
    result = json.loads(captured.out)
    assert result["status"] == "pass"
    assert result["source"] == "<stdin>"
    assert result["output"] == output_path
    assert result["would_write"] is False
    assert result["validation"] == "pass"
    assert result["artifact_counts"]["adapter_request"] == 1
    assert not (fake_root / output_path).exists()


def test_export_file_wrapper_dry_run_pass(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    wrapper = {
        "status": "pass",
        "task_id": "task-20260703-001",
        "task_status": "running",
        "envelope_draft": _valid_envelope(),
    }
    draft_file = fake_root / "draft.json"
    draft_file.write_text(json.dumps(wrapper), encoding="utf-8")
    output_path = "drafts/runtime/task-001/req-001.envelope.json"

    code = main([
        "--root", str(fake_root),
        "runtime", "draft", "export",
        "--file", "draft.json",
        "--output", output_path,
        "--dry-run",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 0
    result = json.loads(captured.out)
    assert result["status"] == "pass"
    assert result["source"] == "draft.json"
    assert result["artifact_counts"]["adapter_request"] == 1
    assert not (fake_root / output_path).exists()


def test_export_schema_invalid(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    bad = {"version": 1, "description": "bad", "artifacts": []}
    draft_file = fake_root / "draft.json"
    draft_file.write_text(json.dumps(bad), encoding="utf-8")

    code = main([
        "--root", str(fake_root),
        "runtime", "draft", "export",
        "--file", "draft.json",
        "--output", "drafts/runtime/out.json",
        "--dry-run",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 5
    result = json.loads(captured.out)
    assert result["status"] == "validation_failed"
    assert "envelope-schema-validation-failed" in {f["rule_id"] for f in result["findings"]}
    # Must not echo the full envelope content.
    assert '"description": "bad"' not in captured.out


def test_export_consistency_invalid(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    envelope = _valid_envelope(requires_approval=True)
    for artifact in envelope["artifacts"]:
        if artifact["artifact_type"] == "approval_record":
            artifact["request_id"] = "req-20260703-999"
    draft_file = fake_root / "draft.json"
    draft_file.write_text(json.dumps(envelope), encoding="utf-8")

    code = main([
        "--root", str(fake_root),
        "runtime", "draft", "export",
        "--file", "draft.json",
        "--output", "drafts/runtime/out.json",
        "--dry-run",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 5
    result = json.loads(captured.out)
    assert result["status"] == "validation_failed"
    assert "approval-references-unknown-request" in {f["rule_id"] for f in result["findings"]}


def test_export_path_escape_blocked(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    draft_file = fake_root / "draft.json"
    draft_file.write_text(json.dumps(_valid_envelope()), encoding="utf-8")

    code = main([
        "--root", str(fake_root),
        "runtime", "draft", "export",
        "--file", "draft.json",
        "--output", "../outside.json",
        "--dry-run",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 2
    result = json.loads(captured.out)
    assert result["status"] == "blocked"
    assert "output-path-outside-root" in {f["rule_id"] for f in result["findings"]}


def test_export_wrong_suffix_blocked(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    draft_file = fake_root / "draft.json"
    draft_file.write_text(json.dumps(_valid_envelope()), encoding="utf-8")

    code = main([
        "--root", str(fake_root),
        "runtime", "draft", "export",
        "--file", "draft.json",
        "--output", "drafts/runtime/out.txt",
        "--dry-run",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 2
    result = json.loads(captured.out)
    assert result["status"] == "blocked"
    assert "output-path-not-json" in {f["rule_id"] for f in result["findings"]}


def test_export_existing_file_blocked(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    draft_file = fake_root / "draft.json"
    draft_file.write_text(json.dumps(_valid_envelope()), encoding="utf-8")
    existing = fake_root / "drafts" / "runtime" / "out.json"
    existing.parent.mkdir(parents=True, exist_ok=True)
    existing.write_text("{}", encoding="utf-8")

    code = main([
        "--root", str(fake_root),
        "runtime", "draft", "export",
        "--file", "draft.json",
        "--output", "drafts/runtime/out.json",
        "--dry-run",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 2
    result = json.loads(captured.out)
    assert result["status"] == "blocked"
    assert "output-file-exists" in {f["rule_id"] for f in result["findings"]}
    # Existing file must not be touched even in dry-run.
    assert existing.read_text(encoding="utf-8") == "{}"


def test_export_secret_pattern_blocked(capsys, tmp_path):
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
        "--dry-run",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 2
    result = json.loads(captured.out)
    assert result["status"] == "blocked"
    assert "github-token" in {f["rule_id"] for f in result["findings"]}
    # Full token must not appear in output.
    assert token not in captured.out


def test_export_public_scan_blocked(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    envelope = _valid_envelope()
    # Build the Windows path dynamically so the test source itself does not
    # trigger the public scan windows-absolute-path rule.
    windows_path = "C:" + "\\Users\\foo\\secret.txt"
    envelope["artifacts"][0]["target"] = windows_path
    draft_file = fake_root / "draft.json"
    draft_file.write_text(json.dumps(envelope), encoding="utf-8")

    code = main([
        "--root", str(fake_root),
        "runtime", "draft", "export",
        "--file", "draft.json",
        "--output", "drafts/runtime/out.json",
        "--dry-run",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 2
    result = json.loads(captured.out)
    assert result["status"] == "blocked"
    assert "windows-absolute-path" in {f["rule_id"] for f in result["findings"]}
    assert windows_path not in captured.out


def test_export_json_no_sensitive_values(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    envelope = _valid_envelope(requires_approval=True)
    envelope["artifacts"].append(
        {
            "artifact_type": "adapter_response",
            "response_id": "resp-20260703-001",
            "request_id": "req-20260703-001",
            "status": "succeeded",
            "message": "Adapter execution succeeded.",
            "artifacts": [],
            "evidence": [
                {
                    "type": "file",
                    "description": "Secret evidence description here",
                    "ref": "ref-12345",
                }
            ],
            "raw_ref": "raw-ref-12345",
            "error": None,
            "finished_at": "2026-07-03T11:00:00+08:00",
        }
    )
    envelope["artifacts"][1]["decision_ref"] = "decision-12345"
    draft_file = fake_root / "draft.json"
    draft_file.write_text(json.dumps(envelope), encoding="utf-8")

    code = main([
        "--root", str(fake_root),
        "runtime", "draft", "export",
        "--file", "draft.json",
        "--output", "drafts/runtime/out.json",
        "--dry-run",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 0
    text = captured.out
    assert "docs/06-adapter-layer.md" not in text
    assert '"input"' not in text
    assert "Secret evidence description here" not in text
    assert "raw-ref-12345" not in text
    assert "decision-12345" not in text
    assert "decision_ref" not in text
    assert "raw_ref" not in text
