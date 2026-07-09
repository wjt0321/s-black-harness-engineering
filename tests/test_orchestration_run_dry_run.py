"""Tests for orchestration run --dry-run read-only command."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from agent_runtime.cli import main
from agent_runtime.orchestration_run_dry_run import RunDryRunResult, dry_run_run


ROOT = Path(__file__).resolve().parents[1]

TASK_ID = "task-20260709-001"
REQUEST_ID = "req-20260709-001"


def _setup_fake_root(tmp_path: Path) -> Path:
    """Create a fake project root with required schemas and registries."""
    fake_root = tmp_path / "project"
    fake_root.mkdir()

    # Schemas
    for src in [
        ROOT / "adapters" / "execution-envelope.schema.json",
        ROOT / "tasks" / "event.schema.json",
        ROOT / "tasks" / "task.schema.json",
    ]:
        dst = fake_root / src.relative_to(ROOT)
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

    # Adapters registry — copy sample and append a low-risk test adapter so that
    # dry-run can reach a "pass" preflight state without changing policies.
    adapters_dir = fake_root / "adapters"
    adapters_dir.mkdir(parents=True, exist_ok=True)
    adapters_data = json.loads((ROOT / "adapters" / "adapters.sample.json").read_text(encoding="utf-8"))
    adapters_data["adapters"].append(
        {
            "id": "dummy-local",
            "name": "Dummy Local Reader",
            "kind": "dummy",
            "description": "Low-risk test adapter for run dry-run tests.",
            "enabled": True,
            "capabilities": ["read_file"],
            "risk_level": "local",
            "requires_approval": False,
            "input_schema": {
                "type": "object",
                "required": ["operation", "target"],
                "properties": {
                    "operation": {"type": "string"},
                    "target": {"type": "string"},
                },
            },
            "output_schema": {"type": "object"},
            "preflight_checks": ["policy_check"],
            "postflight_checks": [],
        }
    )
    (adapters_dir / "adapters.sample.json").write_text(
        json.dumps(adapters_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # Policies
    policies_dir = fake_root / "policies"
    policies_dir.mkdir(parents=True, exist_ok=True)
    for policy_path in (ROOT / "policies").glob("*.sample.policy.json"):
        shutil.copy(policy_path, policies_dir / policy_path.name)

    # Task ledger
    tasks_dir = fake_root / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    task = {
        "id": TASK_ID,
        "title": "Run dry-run test task",
        "status": "running",
        "created_at": "2026-07-09T10:00:00+08:00",
        "updated_at": "2026-07-09T10:00:00+08:00",
        "created_by": "cli",
        "source": "cli",
        "assignee": "orchestrator",
        "requested_capability": "git_push",
    }
    (tasks_dir / "tasks.jsonl").write_text(
        json.dumps(task, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    return fake_root


def _base_args(fake_root: Path, **extra: str) -> list[str]:
    args = [
        "--root", str(fake_root),
        "orchestration", "run",
        "--task-id", TASK_ID,
        "--request-id", REQUEST_ID,
        "--capability", "git_push",
        "--dry-run",
    ]
    for key, value in extra.items():
        args.append(f"--{key.replace('_', '-')}")
        args.append(value)
    return args


def test_dry_run_local_pass_json_structure(tmp_path: Path) -> None:
    fake_root = _setup_fake_root(tmp_path)
    result = dry_run_run(
        fake_root,
        task_id=TASK_ID,
        request_id=REQUEST_ID,
        capability="read_file",
        operation="read_file",
        target="docs/06-adapter-layer.md",
    )
    assert isinstance(result, RunDryRunResult)
    d = result.to_dict()
    assert d["status"] == "pass"
    assert d["task_id"] == TASK_ID
    assert d["request_id"] == REQUEST_ID
    assert d["requested_capability"] == "read_file"
    assert d["mode"] == "dry-run"
    assert d["route"]["selected_adapter_id"] == "dummy-local"
    assert d["preflight"]["status"] == "pass"
    assert "plan_hash" in d
    assert d["candidate_envelope_summary"]["artifact_count"] >= 1
    assert d["candidate_events_summary"]
    assert d["artifact_candidate_refs"]
    assert d["evidence_candidate_refs"] == []
    assert "next_action" in d


def test_dry_run_external_needs_approval_has_plan_hash(tmp_path: Path) -> None:
    fake_root = _setup_fake_root(tmp_path)
    result = dry_run_run(
        fake_root,
        task_id=TASK_ID,
        request_id=REQUEST_ID,
        capability="git_push",
        operation="git_push",
        target="origin/main",
    )
    d = result.to_dict()
    assert d["status"] == "needs_approval"
    assert "plan_hash" in d
    assert d["candidate_envelope_summary"]["requires_approval"] is True
    assert d["candidate_events_summary"]
    # approval_requested event should appear in candidate events.
    event_types = {e["event_type"] for e in d["candidate_events_summary"]}
    assert "approval_requested" in event_types
    assert "run_planned" in event_types


def test_dry_run_missing_operation_returns_needs_input(tmp_path: Path) -> None:
    fake_root = _setup_fake_root(tmp_path)
    result = dry_run_run(
        fake_root,
        task_id=TASK_ID,
        request_id=REQUEST_ID,
        capability="git_push",
    )
    assert result.status == "needs_input"
    assert result.candidate_envelope_summary == {}
    assert result.artifact_candidate_refs == []


def test_dry_run_missing_target_returns_needs_input(tmp_path: Path) -> None:
    fake_root = _setup_fake_root(tmp_path)
    result = dry_run_run(
        fake_root,
        task_id=TASK_ID,
        request_id=REQUEST_ID,
        capability="git_push",
        operation="git_push",
    )
    assert result.status == "needs_input"


def test_dry_run_explicit_adapter_not_supported_returns_blocked(tmp_path: Path) -> None:
    fake_root = _setup_fake_root(tmp_path)
    result = dry_run_run(
        fake_root,
        task_id=TASK_ID,
        request_id=REQUEST_ID,
        capability="git_push",
        adapter_id="shell-local",
        operation="git_push",
        target="origin/main",
    )
    assert result.status == "blocked"
    assert result.route.get("fallback_candidates")


def test_dry_run_task_not_found_returns_error(tmp_path: Path) -> None:
    fake_root = _setup_fake_root(tmp_path)
    result = dry_run_run(
        fake_root,
        task_id="task-20260709-999",
        request_id=REQUEST_ID,
        capability="git_push",
        operation="git_push",
        target="origin/main",
    )
    assert result.status == "error"


def test_dry_run_terminal_task_preserves_runtime_plan_blocked_status(tmp_path: Path) -> None:
    fake_root = _setup_fake_root(tmp_path)
    task = {
        "id": TASK_ID,
        "title": "Finished task",
        "status": "finished",
        "created_at": "2026-07-09T10:00:00+08:00",
        "updated_at": "2026-07-09T10:00:00+08:00",
        "created_by": "cli",
        "source": "cli",
        "assignee": "orchestrator",
        "requested_capability": "git_push",
    }
    tasks_file = fake_root / "tasks" / "tasks.jsonl"
    tasks_file.write_text(json.dumps(task, ensure_ascii=False) + "\n", encoding="utf-8")

    result = dry_run_run(
        fake_root,
        task_id=TASK_ID,
        request_id=REQUEST_ID,
        capability="git_push",
        operation="git_push",
        target="origin/main",
    )

    assert result.status == "blocked"
    assert result.plan_hash is None
    assert result.candidate_envelope_summary == {}
    assert result.findings[0].rule_id == "task-terminal"


def test_dry_run_plan_hash_stable_for_same_inputs(tmp_path: Path) -> None:
    fake_root = _setup_fake_root(tmp_path)
    result1 = dry_run_run(
        fake_root,
        task_id=TASK_ID,
        request_id=REQUEST_ID,
        capability="git_push",
        operation="git_push",
        target="origin/main",
    )
    result2 = dry_run_run(
        fake_root,
        task_id=TASK_ID,
        request_id=REQUEST_ID,
        capability="git_push",
        operation="git_push",
        target="origin/main",
    )
    assert result1.plan_hash == result2.plan_hash


def test_dry_run_does_not_write_ledger_or_envelope(tmp_path: Path) -> None:
    fake_root = _setup_fake_root(tmp_path)
    before = (fake_root / "tasks" / "tasks.jsonl").read_bytes()

    result = dry_run_run(
        fake_root,
        task_id=TASK_ID,
        request_id=REQUEST_ID,
        capability="git_push",
        operation="git_push",
        target="origin/main",
    )
    assert result.status == "needs_approval"

    assert (fake_root / "tasks" / "tasks.jsonl").read_bytes() == before
    # No new envelope draft should be created.
    drafts_dir = fake_root / "drafts"
    assert not drafts_dir.exists() or list(drafts_dir.rglob("*.json")) == []


def test_dry_run_output_does_not_expose_target_or_secret(tmp_path: Path) -> None:
    fake_root = _setup_fake_root(tmp_path)
    secret_target = "origin/secret-branch-12345"
    result = dry_run_run(
        fake_root,
        task_id=TASK_ID,
        request_id=REQUEST_ID,
        capability="git_push",
        operation="git_push",
        target=secret_target,
    )
    d = result.to_dict()
    output = json.dumps(d, ensure_ascii=False)
    assert secret_target not in output
    assert "decision_ref" not in output
    assert "payload_refs" not in output


def test_cli_dry_run_json_output(capsys, tmp_path: Path) -> None:
    fake_root = _setup_fake_root(tmp_path)
    code = main(_base_args(fake_root, operation="git_push", target="origin/main") + ["--json"])
    captured = capsys.readouterr()
    result = json.loads(captured.out)
    assert code == 3  # needs_approval exit code
    assert result["status"] == "needs_approval"
    assert result["request_id"] == REQUEST_ID
    assert "plan_hash" in result


def test_cli_dry_run_human_readable_smoke(capsys, tmp_path: Path) -> None:
    fake_root = _setup_fake_root(tmp_path)
    code = main(_base_args(fake_root, capability="read_file", operation="read_file", target="docs/06-adapter-layer.md"))
    captured = capsys.readouterr()
    assert code == 0
    assert "RUN" in captured.out
    assert TASK_ID in captured.out
    assert REQUEST_ID in captured.out
    assert "plan_hash" in captured.out


def test_cli_commit_returns_needs_input(capsys, tmp_path: Path) -> None:
    fake_root = _setup_fake_root(tmp_path)
    args = _base_args(fake_root, capability="read_file", operation="read_file", target="docs/06-adapter-layer.md")
    # Replace --dry-run with --commit
    args = [a for a in args if a != "--dry-run"] + ["--commit"]
    code = main(args)
    captured = capsys.readouterr()
    assert code == 4  # needs_input
    assert "--output" in captured.out and "--expected-plan-hash" in captured.out


def test_cli_missing_required_args(capsys, tmp_path: Path) -> None:
    fake_root = _setup_fake_root(tmp_path)
    # Omit --capability and --request-id
    args = ["--root", str(fake_root), "orchestration", "run", "--task-id", TASK_ID, "--dry-run"]
    code = main(args)
    captured = capsys.readouterr()
    assert code == 4  # needs_input
    assert "Missing required arguments" in captured.out
