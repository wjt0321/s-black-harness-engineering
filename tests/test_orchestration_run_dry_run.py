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


RETRY_REQUEST_ID = "req-20260709-002"
FALLBACK_REQUEST_ID = "req-20260709-003"
SOURCE_REQUEST_ID = REQUEST_ID


def test_retry_dry_run_pass_has_lineage_and_plan_hash(tmp_path: Path) -> None:
    fake_root = _setup_fake_root(tmp_path)
    result = dry_run_run(
        fake_root,
        task_id=TASK_ID,
        request_id=RETRY_REQUEST_ID,
        capability="read_file",
        operation="read_file",
        target="docs/06-adapter-layer.md",
        retry_of=SOURCE_REQUEST_ID,
    )
    d = result.to_dict()
    assert d["status"] == "pass"
    assert d["lineage_type"] == "retry"
    assert d["retry_of"] == SOURCE_REQUEST_ID
    assert d["request_id"] == RETRY_REQUEST_ID
    assert "fallback_from" not in d
    assert "fallback_to" not in d
    assert "plan_hash" in d
    assert d["plan_hash"]


def test_fallback_dry_run_pass_routes_to_fallback_adapter(tmp_path: Path) -> None:
    fake_root = _setup_fake_root(tmp_path)
    result = dry_run_run(
        fake_root,
        task_id=TASK_ID,
        request_id=FALLBACK_REQUEST_ID,
        capability="read_file",
        operation="read_file",
        target="docs/06-adapter-layer.md",
        fallback_from=SOURCE_REQUEST_ID,
        fallback_to="dummy-local",
    )
    d = result.to_dict()
    assert d["status"] == "pass"
    assert d["lineage_type"] == "fallback"
    assert d["fallback_from"] == SOURCE_REQUEST_ID
    assert d["fallback_to"] == "dummy-local"
    assert d["request_id"] == FALLBACK_REQUEST_ID
    assert d["route"]["selected_adapter_id"] == "dummy-local"
    assert "retry_of" not in d
    assert "plan_hash" in d
    assert d["plan_hash"]


def test_retry_request_id_same_as_source_returns_validation_failed(tmp_path: Path) -> None:
    fake_root = _setup_fake_root(tmp_path)
    before = (fake_root / "tasks" / "tasks.jsonl").read_bytes()
    result = dry_run_run(
        fake_root,
        task_id=TASK_ID,
        request_id=SOURCE_REQUEST_ID,
        capability="read_file",
        operation="read_file",
        target="docs/06-adapter-layer.md",
        retry_of=SOURCE_REQUEST_ID,
    )
    assert result.status == "validation_failed"
    assert result.findings[0].rule_id == "lineage-request-id-must-differ"
    assert (fake_root / "tasks" / "tasks.jsonl").read_bytes() == before
    drafts_dir = fake_root / "drafts"
    assert not drafts_dir.exists() or list(drafts_dir.rglob("*.json")) == []


def test_fallback_request_id_same_as_source_returns_validation_failed(tmp_path: Path) -> None:
    fake_root = _setup_fake_root(tmp_path)
    result = dry_run_run(
        fake_root,
        task_id=TASK_ID,
        request_id=SOURCE_REQUEST_ID,
        capability="read_file",
        operation="read_file",
        target="docs/06-adapter-layer.md",
        fallback_from=SOURCE_REQUEST_ID,
        fallback_to="dummy-local",
    )
    assert result.status == "validation_failed"
    assert result.findings[0].rule_id == "lineage-request-id-must-differ"


def test_retry_and_fallback_mutually_exclusive(tmp_path: Path) -> None:
    fake_root = _setup_fake_root(tmp_path)
    result = dry_run_run(
        fake_root,
        task_id=TASK_ID,
        request_id=RETRY_REQUEST_ID,
        capability="read_file",
        operation="read_file",
        target="docs/06-adapter-layer.md",
        retry_of=SOURCE_REQUEST_ID,
        fallback_from=SOURCE_REQUEST_ID,
        fallback_to="dummy-local",
    )
    assert result.status == "validation_failed"
    assert result.findings[0].rule_id == "lineage-mutually-exclusive"


def test_fallback_to_without_fallback_from_returns_validation_failed(tmp_path: Path) -> None:
    fake_root = _setup_fake_root(tmp_path)
    result = dry_run_run(
        fake_root,
        task_id=TASK_ID,
        request_id=FALLBACK_REQUEST_ID,
        capability="read_file",
        operation="read_file",
        target="docs/06-adapter-layer.md",
        fallback_to="dummy-local",
    )
    assert result.status == "validation_failed"
    assert result.findings[0].rule_id == "fallback-to-requires-fallback-from"


def test_retry_dry_run_does_not_write_ledger_or_envelope(tmp_path: Path) -> None:
    fake_root = _setup_fake_root(tmp_path)
    before = (fake_root / "tasks" / "tasks.jsonl").read_bytes()
    result = dry_run_run(
        fake_root,
        task_id=TASK_ID,
        request_id=RETRY_REQUEST_ID,
        capability="read_file",
        operation="read_file",
        target="docs/06-adapter-layer.md",
        retry_of=SOURCE_REQUEST_ID,
    )
    assert result.status == "pass"
    assert (fake_root / "tasks" / "tasks.jsonl").read_bytes() == before
    drafts_dir = fake_root / "drafts"
    assert not drafts_dir.exists() or list(drafts_dir.rglob("*.json")) == []


def test_plan_hash_differs_with_lineage(tmp_path: Path) -> None:
    fake_root = _setup_fake_root(tmp_path)
    base = dry_run_run(
        fake_root,
        task_id=TASK_ID,
        request_id=RETRY_REQUEST_ID,
        capability="read_file",
        operation="read_file",
        target="docs/06-adapter-layer.md",
    )
    retry = dry_run_run(
        fake_root,
        task_id=TASK_ID,
        request_id=RETRY_REQUEST_ID,
        capability="read_file",
        operation="read_file",
        target="docs/06-adapter-layer.md",
        retry_of=SOURCE_REQUEST_ID,
    )
    assert base.plan_hash != retry.plan_hash


def test_cli_retry_dry_run_json_output(capsys, tmp_path: Path) -> None:
    fake_root = _setup_fake_root(tmp_path)
    args = [
        "--root", str(fake_root),
        "orchestration", "run",
        "--task-id", TASK_ID,
        "--request-id", RETRY_REQUEST_ID,
        "--capability", "read_file",
        "--operation", "read_file",
        "--target", "docs/06-adapter-layer.md",
        "--retry-of", SOURCE_REQUEST_ID,
        "--dry-run",
        "--json",
    ]
    code = main(args)
    captured = capsys.readouterr()
    result = json.loads(captured.out)
    assert code == 0
    assert result["status"] == "pass"
    assert result["lineage_type"] == "retry"
    assert result["retry_of"] == SOURCE_REQUEST_ID
    assert result["request_id"] == RETRY_REQUEST_ID
    assert "plan_hash" in result


def test_cli_fallback_dry_run_human_readable_smoke(capsys, tmp_path: Path) -> None:
    fake_root = _setup_fake_root(tmp_path)
    args = [
        "--root", str(fake_root),
        "orchestration", "run",
        "--task-id", TASK_ID,
        "--request-id", FALLBACK_REQUEST_ID,
        "--capability", "read_file",
        "--operation", "read_file",
        "--target", "docs/06-adapter-layer.md",
        "--fallback-from", SOURCE_REQUEST_ID,
        "--fallback-to", "dummy-local",
        "--dry-run",
    ]
    code = main(args)
    captured = capsys.readouterr()
    assert code == 0
    assert "RUN" in captured.out
    assert "lineage_type=fallback" in captured.out
    assert f"fallback_from={SOURCE_REQUEST_ID}" in captured.out
    assert "fallback_to=dummy-local" in captured.out
    assert "plan_hash" in captured.out


def test_fallback_to_overrides_adapter_id_in_direct_call(tmp_path: Path) -> None:
    """fallback_to must bind to effective adapter_id even when caller passes a different adapter_id."""
    fake_root = _setup_fake_root(tmp_path)
    # github-cli does not support read_file; without fallback_to this would be blocked.
    result = dry_run_run(
        fake_root,
        task_id=TASK_ID,
        request_id=FALLBACK_REQUEST_ID,
        capability="read_file",
        adapter_id="github-cli",
        operation="read_file",
        target="docs/06-adapter-layer.md",
        fallback_from=SOURCE_REQUEST_ID,
        fallback_to="dummy-local",
    )
    d = result.to_dict()
    assert d["status"] == "pass"
    assert d["lineage_type"] == "fallback"
    assert d["fallback_to"] == "dummy-local"
    assert d["route"]["selected_adapter_id"] == "dummy-local"


VALID_SNAPSHOT_ID = "sha256:" + "a" * 64
OTHER_SNAPSHOT_ID = "sha256:" + "b" * 64


def test_dry_run_with_routing_snapshot_id_injects_reference(tmp_path: Path) -> None:
    fake_root = _setup_fake_root(tmp_path)
    result = dry_run_run(
        fake_root,
        task_id=TASK_ID,
        request_id=REQUEST_ID,
        capability="read_file",
        operation="read_file",
        target="docs/06-adapter-layer.md",
        routing_snapshot_id=VALID_SNAPSHOT_ID,
    )
    d = result.to_dict()
    assert d["status"] == "pass"
    assert d["routing_snapshot_id"] == VALID_SNAPSHOT_ID
    # Candidate run artifact/refs carry the snapshot id.
    for ref in d["artifact_candidate_refs"]:
        assert ref["routing_snapshot_id"] == VALID_SNAPSHOT_ID
    # run_planned candidate event metadata keys include the snapshot id.
    run_planned = next(
        (e for e in d["candidate_events_summary"] if e["event_type"] == "run_planned"), None
    )
    assert run_planned is not None
    assert "routing_snapshot_id" in run_planned["metadata_keys"]


def test_dry_run_without_routing_snapshot_id_remains_compatible(tmp_path: Path) -> None:
    fake_root = _setup_fake_root(tmp_path)
    result = dry_run_run(
        fake_root,
        task_id=TASK_ID,
        request_id=REQUEST_ID,
        capability="read_file",
        operation="read_file",
        target="docs/06-adapter-layer.md",
    )
    d = result.to_dict()
    assert d["status"] == "pass"
    assert "routing_snapshot_id" not in d
    run_planned = next(
        (e for e in d["candidate_events_summary"] if e["event_type"] == "run_planned"), None
    )
    assert run_planned is not None
    assert "routing_snapshot_id" not in run_planned["metadata_keys"]
    for ref in d["artifact_candidate_refs"]:
        assert "routing_snapshot_id" not in ref


def test_dry_run_plan_hash_differs_with_routing_snapshot_id(tmp_path: Path) -> None:
    fake_root = _setup_fake_root(tmp_path)
    base = dry_run_run(
        fake_root,
        task_id=TASK_ID,
        request_id=REQUEST_ID,
        capability="read_file",
        operation="read_file",
        target="docs/06-adapter-layer.md",
    )
    with_snapshot = dry_run_run(
        fake_root,
        task_id=TASK_ID,
        request_id=REQUEST_ID,
        capability="read_file",
        operation="read_file",
        target="docs/06-adapter-layer.md",
        routing_snapshot_id=VALID_SNAPSHOT_ID,
    )
    assert base.plan_hash != with_snapshot.plan_hash


def test_dry_run_plan_hash_stable_with_same_routing_snapshot_id(tmp_path: Path) -> None:
    fake_root = _setup_fake_root(tmp_path)
    result1 = dry_run_run(
        fake_root,
        task_id=TASK_ID,
        request_id=REQUEST_ID,
        capability="read_file",
        operation="read_file",
        target="docs/06-adapter-layer.md",
        routing_snapshot_id=VALID_SNAPSHOT_ID,
    )
    result2 = dry_run_run(
        fake_root,
        task_id=TASK_ID,
        request_id=REQUEST_ID,
        capability="read_file",
        operation="read_file",
        target="docs/06-adapter-layer.md",
        routing_snapshot_id=VALID_SNAPSHOT_ID,
    )
    assert result1.plan_hash == result2.plan_hash


def test_dry_run_invalid_routing_snapshot_id_returns_needs_input(tmp_path: Path) -> None:
    fake_root = _setup_fake_root(tmp_path)
    result = dry_run_run(
        fake_root,
        task_id=TASK_ID,
        request_id=REQUEST_ID,
        capability="read_file",
        operation="read_file",
        target="docs/06-adapter-layer.md",
        routing_snapshot_id="not-a-valid-id",
    )
    assert result.status == "needs_input"
    assert result.findings[0].rule_id == "invalid-routing-snapshot-id"
    assert result.plan_hash is None


def test_dry_run_routing_snapshot_id_rejects_path_like_value(tmp_path: Path) -> None:
    fake_root = _setup_fake_root(tmp_path)
    result = dry_run_run(
        fake_root,
        task_id=TASK_ID,
        request_id=REQUEST_ID,
        capability="read_file",
        operation="read_file",
        target="docs/06-adapter-layer.md",
        routing_snapshot_id="drafts/runtime/task-001/snapshot.json",
    )
    assert result.status == "needs_input"
    assert result.findings[0].rule_id == "invalid-routing-snapshot-id"


def test_dry_run_invalid_routing_snapshot_id_does_not_echo_raw_value(tmp_path: Path) -> None:
    fake_root = _setup_fake_root(tmp_path)
    sensitive_id = "ghp_" + "X" * 36
    result = dry_run_run(
        fake_root,
        task_id=TASK_ID,
        request_id=REQUEST_ID,
        capability="read_file",
        operation="read_file",
        target="docs/06-adapter-layer.md",
        routing_snapshot_id=sensitive_id,
    )
    assert result.status == "needs_input"
    output = json.dumps(result.to_dict(), ensure_ascii=False)
    assert sensitive_id not in output
    assert "ghp_" not in output
    assert result.findings[0].message == "--routing-snapshot-id must match 'sha256:<64 lowercase hex chars>'."


def test_retry_dry_run_with_routing_snapshot_id(tmp_path: Path) -> None:
    fake_root = _setup_fake_root(tmp_path)
    result = dry_run_run(
        fake_root,
        task_id=TASK_ID,
        request_id=RETRY_REQUEST_ID,
        capability="read_file",
        operation="read_file",
        target="docs/06-adapter-layer.md",
        retry_of=SOURCE_REQUEST_ID,
        routing_snapshot_id=VALID_SNAPSHOT_ID,
    )
    d = result.to_dict()
    assert d["status"] == "pass"
    assert d["lineage_type"] == "retry"
    assert d["routing_snapshot_id"] == VALID_SNAPSHOT_ID


def test_fallback_dry_run_with_routing_snapshot_id(tmp_path: Path) -> None:
    fake_root = _setup_fake_root(tmp_path)
    result = dry_run_run(
        fake_root,
        task_id=TASK_ID,
        request_id=FALLBACK_REQUEST_ID,
        capability="read_file",
        operation="read_file",
        target="docs/06-adapter-layer.md",
        fallback_from=SOURCE_REQUEST_ID,
        fallback_to="dummy-local",
        routing_snapshot_id=VALID_SNAPSHOT_ID,
    )
    d = result.to_dict()
    assert d["status"] == "pass"
    assert d["lineage_type"] == "fallback"
    assert d["routing_snapshot_id"] == VALID_SNAPSHOT_ID


def test_cli_dry_run_with_routing_snapshot_id_json(capsys, tmp_path: Path) -> None:
    fake_root = _setup_fake_root(tmp_path)
    code = main(
        _base_args(fake_root, capability="read_file", operation="read_file", target="docs/06-adapter-layer.md")
        + ["--routing-snapshot-id", VALID_SNAPSHOT_ID, "--json"]
    )
    captured = capsys.readouterr()
    result = json.loads(captured.out)
    assert code == 0
    assert result["status"] == "pass"
    assert result["routing_snapshot_id"] == VALID_SNAPSHOT_ID
    assert "plan_hash" in result


def test_cli_dry_run_with_routing_snapshot_id_human(capsys, tmp_path: Path) -> None:
    fake_root = _setup_fake_root(tmp_path)
    code = main(
        _base_args(fake_root, capability="read_file", operation="read_file", target="docs/06-adapter-layer.md")
        + ["--routing-snapshot-id", VALID_SNAPSHOT_ID]
    )
    captured = capsys.readouterr()
    assert code == 0
    assert f"routing_snapshot_id={VALID_SNAPSHOT_ID}" in captured.out
    assert "plan_hash=" in captured.out


def test_cli_commit_with_routing_snapshot_id_blocked_and_no_writes(capsys, tmp_path: Path) -> None:
    fake_root = _setup_fake_root(tmp_path)
    args = [
        "--root", str(fake_root),
        "orchestration", "run",
        "--task-id", TASK_ID,
        "--request-id", REQUEST_ID,
        "--capability", "read_file",
        "--operation", "read_file",
        "--target", "docs/06-adapter-layer.md",
        "--commit",
        "--output", "drafts/runtime/task-001/test.envelope.json",
        "--expected-plan-hash", "sha256:any",
        "--events-file", "tasks/events.jsonl",
        "--routing-snapshot-id", VALID_SNAPSHOT_ID,
        "--json",
    ]
    before_tasks = (fake_root / "tasks" / "tasks.jsonl").read_bytes()
    drafts_dir = fake_root / "drafts"
    before_events = (fake_root / "tasks" / "events.jsonl").read_bytes() if (fake_root / "tasks" / "events.jsonl").exists() else b""

    code = main(args)
    captured = capsys.readouterr()
    result = json.loads(captured.out)

    assert code == 2  # blocked
    assert result["status"] == "blocked"
    assert result["findings"][0]["rule_id"] == "routing-snapshot-id-not-supported-in-commit"
    assert (fake_root / "tasks" / "tasks.jsonl").read_bytes() == before_tasks
    assert not drafts_dir.exists() or list(drafts_dir.rglob("*.json")) == []
    assert (
        not (fake_root / "tasks" / "events.jsonl").exists()
        or (fake_root / "tasks" / "events.jsonl").read_bytes() == before_events
    )
