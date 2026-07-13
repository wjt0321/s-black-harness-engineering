"""Tests for orchestration read-loop snapshot.

These tests verify that ``orchestration run --dry-run --snapshot`` projects a
stable, deterministic, value-safe read model bundling Run preview, candidate
Event summaries, and Report preview without writing ledgers or executing
adapters.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from agent_runtime.cli import main
from agent_runtime.orchestration_read_loop_snapshot import (
    SCHEMA_VERSION,
    OrchestrationReadLoopSnapshot,
    _canonical_json,
    _compute_snapshot_id,
    build_read_loop_snapshot,
)
from agent_runtime.orchestration_run_dry_run import RunDryRunResult, dry_run_run


ROOT = Path(__file__).resolve().parents[1]

TASK_ID = "task-20260709-001"
REQUEST_ID = "req-20260709-001"
VALID_ROUTING_SNAPSHOT_ID = "sha256:" + "a" * 64


def _setup_fake_root(tmp_path: Path) -> Path:
    """Create a fake project root with required schemas, registries and ledger."""
    fake_root = tmp_path / "project"
    fake_root.mkdir()

    for src in [
        ROOT / "adapters" / "execution-envelope.schema.json",
        ROOT / "tasks" / "event.schema.json",
        ROOT / "tasks" / "task.schema.json",
    ]:
        dst = fake_root / src.relative_to(ROOT)
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

    adapters_dir = fake_root / "adapters"
    adapters_dir.mkdir(parents=True, exist_ok=True)
    adapters_data = json.loads((ROOT / "adapters" / "adapters.sample.json").read_text(encoding="utf-8"))
    adapters_data["adapters"].append(
        {
            "id": "dummy-local",
            "name": "Dummy Local Reader",
            "kind": "dummy",
            "description": "Low-risk test adapter for read-loop snapshot tests.",
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

    policies_dir = fake_root / "policies"
    policies_dir.mkdir(parents=True, exist_ok=True)
    for policy_path in (ROOT / "policies").glob("*.sample.policy.json"):
        shutil.copy(policy_path, policies_dir / policy_path.name)

    tasks_dir = fake_root / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    task = {
        "id": TASK_ID,
        "title": "Read-loop snapshot test task",
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


def test_build_read_loop_snapshot_pass_structure(tmp_path: Path) -> None:
    """Pass dry-run produces planned run, event summaries and preview report."""
    fake_root = _setup_fake_root(tmp_path)
    dry_run = dry_run_run(
        fake_root,
        task_id=TASK_ID,
        request_id=REQUEST_ID,
        capability="read_file",
        operation="read_file",
        target="docs/06-adapter-layer.md",
    )
    snapshot = build_read_loop_snapshot(dry_run)

    assert isinstance(snapshot, OrchestrationReadLoopSnapshot)
    assert snapshot.schema_version == SCHEMA_VERSION
    assert snapshot.snapshot_id.startswith("sha256:")
    assert snapshot.status == "pass"

    run = snapshot.run
    assert run["status"] == "planned"
    assert run["gate_status"] == "ready"
    assert run["task_id"] == TASK_ID
    assert run["request_id"] == REQUEST_ID
    assert run["adapter_id"] == "dummy-local"
    assert run["capability"] == "read_file"
    assert run["operation"] == "read_file"
    assert run["mode"] == "dry-run"
    assert run["requires_approval"] is False
    assert run["requires_dry_run"] is False
    assert "plan_hash" in run

    assert len(snapshot.events) >= 1
    event_types = {e["event_type"] for e in snapshot.events}
    assert "run_planned" in event_types
    for event in snapshot.events:
        assert event["status"] == "planned"
        assert isinstance(event["metadata_keys"], list)

    report = snapshot.report
    assert report["status"] == "preview"
    assert report["candidate_event_count"] == len(snapshot.events)
    assert report["candidate_event_types"]["run_planned"] >= 1
    assert report["requires_approval"] is False
    assert report["next_action_code"] == "proceed_to_commit"
    assert report["evidence_candidate_count"] == 0
    assert report["evidence_candidate_type_counts"] == {}
    assert "next_action" in report

    assert snapshot.source == {
        "task_id": TASK_ID,
        "request_id": REQUEST_ID,
        "requested_capability": "read_file",
    }


def test_build_read_loop_snapshot_projects_evidence_candidates(tmp_path: Path) -> None:
    """Report preview exposes safe evidence candidate counts and type counts."""
    dry_run = RunDryRunResult(
        status="pass",
        task_id=TASK_ID,
        request_id=REQUEST_ID,
        requested_capability="read_file",
        route={"selected_adapter_id": "dummy-local", "operation": "read_file"},
        evidence_candidate_refs=[
            {"evidence_type": "dry_run_completed"},
            {"evidence_type": "path_check_passed"},
            {"evidence_type": "path_check_passed"},
        ],
    )

    snapshot = build_read_loop_snapshot(dry_run)

    assert snapshot.report["evidence_candidate_count"] == 3
    assert snapshot.report["evidence_candidate_type_counts"] == {
        "dry_run_completed": 1,
        "path_check_passed": 2,
    }


def test_build_read_loop_snapshot_needs_approval(tmp_path: Path) -> None:
    """needs_approval dry-run maps run status to planned but keeps top-level status."""
    fake_root = _setup_fake_root(tmp_path)
    dry_run = dry_run_run(
        fake_root,
        task_id=TASK_ID,
        request_id=REQUEST_ID,
        capability="git_push",
        operation="git_push",
        target="origin/main",
    )
    snapshot = build_read_loop_snapshot(dry_run)

    assert snapshot.status == "needs_approval"
    assert snapshot.run["status"] == "planned"
    assert snapshot.run["gate_status"] == "pending_approval"
    assert snapshot.run["requires_approval"] is True
    assert snapshot.report["requires_approval"] is True
    assert snapshot.report["gate_status"] == "pending_approval"
    assert snapshot.report["next_action_code"] == "blocked_wait_for_approval"
    assert "pending_approval" in snapshot.report["status_summary"]
    event_types = {e["event_type"] for e in snapshot.events}
    assert "approval_requested" in event_types
    assert "run_planned" in event_types


def test_build_read_loop_snapshot_blocked_structure(tmp_path: Path) -> None:
    """Blocked dry-run still produces a safe snapshot with empty candidates."""
    fake_root = _setup_fake_root(tmp_path)
    dry_run = dry_run_run(
        fake_root,
        task_id=TASK_ID,
        request_id=REQUEST_ID,
        capability="git_push",
        adapter_id="dummy-local",
        operation="git_push",
        target="origin/main",
    )
    snapshot = build_read_loop_snapshot(dry_run)

    assert snapshot.status == "blocked"
    assert snapshot.run["status"] == "blocked"
    assert snapshot.run["gate_status"] == "blocked"
    assert snapshot.report["gate_status"] == "blocked"
    assert snapshot.report["next_action_code"] == "needs_human_review"
    assert snapshot.run["adapter_id"] is None
    assert snapshot.events == []
    assert snapshot.report["status"] == "preview"
    assert snapshot.report["candidate_event_count"] == 0
    assert snapshot.report["artifact_candidate_count"] == 0


def test_build_read_loop_snapshot_needs_input_structure(tmp_path: Path) -> None:
    """needs_input dry-run propagates status and keeps report preview minimal."""
    fake_root = _setup_fake_root(tmp_path)
    dry_run = dry_run_run(
        fake_root,
        task_id=TASK_ID,
        request_id=REQUEST_ID,
        capability="git_push",
    )
    snapshot = build_read_loop_snapshot(dry_run)

    assert snapshot.status == "needs_input"
    assert snapshot.run["status"] == "needs_input"
    assert snapshot.report["next_action_code"] == "needs_input"
    assert snapshot.run["gate_status"] == "needs_input"
    assert snapshot.report["gate_status"] == "needs_input"
    assert snapshot.events == []


def test_build_read_loop_snapshot_needs_approval_is_not_ready(tmp_path: Path) -> None:
    """needs_approval run has gate_status=pending_approval, never ready."""
    fake_root = _setup_fake_root(tmp_path)
    dry_run = dry_run_run(
        fake_root,
        task_id=TASK_ID,
        request_id=REQUEST_ID,
        capability="git_push",
        operation="git_push",
        target="origin/main",
    )
    snapshot = build_read_loop_snapshot(dry_run)

    assert snapshot.status == "needs_approval"
    assert snapshot.run["status"] == "planned"
    assert snapshot.run["gate_status"] == "pending_approval"
    assert snapshot.report["gate_status"] == "pending_approval"
    assert snapshot.run["gate_status"] != "ready"
    assert "ready" not in snapshot.report["status_summary"]


def test_build_read_loop_snapshot_candidate_events_have_no_event_id_or_timestamp(tmp_path: Path) -> None:
    """Candidate events are clearly previews; they do not fabricate event ids or timestamps."""
    fake_root = _setup_fake_root(tmp_path)
    dry_run = dry_run_run(
        fake_root,
        task_id=TASK_ID,
        request_id=REQUEST_ID,
        capability="git_push",
        operation="git_push",
        target="origin/main",
    )
    snapshot = build_read_loop_snapshot(dry_run)

    assert len(snapshot.events) >= 2
    approval_requested = next(
        (e for e in snapshot.events if e["event_type"] == "approval_requested"), None
    )
    assert approval_requested is not None
    assert approval_requested["status"] == "planned"
    assert "event_id" not in approval_requested
    assert "timestamp" not in approval_requested
    for event in snapshot.events:
        assert "event_id" not in event
        assert "timestamp" not in event


def test_build_read_loop_snapshot_deterministic(tmp_path: Path) -> None:
    """Same dry-run inputs produce byte-equivalent snapshot JSON."""
    fake_root = _setup_fake_root(tmp_path)
    dry_run1 = dry_run_run(
        fake_root,
        task_id=TASK_ID,
        request_id=REQUEST_ID,
        capability="read_file",
        operation="read_file",
        target="docs/06-adapter-layer.md",
    )
    dry_run2 = dry_run_run(
        fake_root,
        task_id=TASK_ID,
        request_id=REQUEST_ID,
        capability="read_file",
        operation="read_file",
        target="docs/06-adapter-layer.md",
    )
    snapshot1 = build_read_loop_snapshot(dry_run1)
    snapshot2 = build_read_loop_snapshot(dry_run2)

    first = json.dumps(snapshot1.to_dict(), ensure_ascii=False, sort_keys=True).encode("utf-8")
    second = json.dumps(snapshot2.to_dict(), ensure_ascii=False, sort_keys=True).encode("utf-8")
    assert first == second
    assert snapshot1.snapshot_id == snapshot2.snapshot_id


def test_build_read_loop_snapshot_id_hashes_final_payload(tmp_path: Path) -> None:
    """snapshot_id is the sha256 of the canonical payload excluding snapshot_id."""
    fake_root = _setup_fake_root(tmp_path)
    dry_run = dry_run_run(
        fake_root,
        task_id=TASK_ID,
        request_id=REQUEST_ID,
        capability="read_file",
        operation="read_file",
        target="docs/06-adapter-layer.md",
    )
    snapshot = build_read_loop_snapshot(dry_run)

    payload = {k: v for k, v in snapshot.to_dict().items() if k != "snapshot_id"}
    expected_id = _compute_snapshot_id(payload)
    assert snapshot.snapshot_id == expected_id
    # Only one sha256 content id appears in the JSON.
    assert json.dumps(snapshot.to_dict()).count("sha256:") == 1


def test_build_read_loop_snapshot_source_mutation_changes_id(tmp_path: Path) -> None:
    """Changing the adapter registry changes the snapshot id."""
    fake_root = _setup_fake_root(tmp_path)
    dry_run1 = dry_run_run(
        fake_root,
        task_id=TASK_ID,
        request_id=REQUEST_ID,
        capability="read_file",
        operation="read_file",
        target="docs/06-adapter-layer.md",
    )
    snapshot1 = build_read_loop_snapshot(dry_run1)

    data = json.loads((fake_root / "adapters" / "adapters.sample.json").read_text(encoding="utf-8"))
    for adapter in data["adapters"]:
        if adapter["id"] == "dummy-local":
            adapter["risk_level"] = "external"
            adapter["requires_approval"] = True
    (fake_root / "adapters" / "adapters.sample.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    dry_run2 = dry_run_run(
        fake_root,
        task_id=TASK_ID,
        request_id=REQUEST_ID,
        capability="read_file",
        operation="read_file",
        target="docs/06-adapter-layer.md",
    )
    snapshot2 = build_read_loop_snapshot(dry_run2)

    assert snapshot2.snapshot_id != snapshot1.snapshot_id
    assert snapshot2.run["risk_level"] == "external"
    assert snapshot2.run["requires_approval"] is True


def test_build_read_loop_snapshot_no_sensitive_payload(tmp_path: Path) -> None:
    """Snapshot JSON does not leak target, schemas, inputs or finding messages."""
    fake_root = _setup_fake_root(tmp_path)
    secret_target = "origin/secret-branch-12345"
    dry_run = dry_run_run(
        fake_root,
        task_id=TASK_ID,
        request_id=REQUEST_ID,
        capability="git_push",
        operation="git_push",
        target=secret_target,
    )
    snapshot = build_read_loop_snapshot(dry_run)

    snapshot_json = json.dumps(snapshot.to_dict(), ensure_ascii=False)
    assert secret_target not in snapshot_json
    assert "input_schema" not in snapshot_json
    assert "output_schema" not in snapshot_json
    assert "properties" not in snapshot_json
    # Secret value is not present anywhere in the snapshot.
    assert secret_target not in snapshot_json


def test_build_read_loop_snapshot_with_routing_snapshot_id(tmp_path: Path) -> None:
    """Routing snapshot id is carried into run layer and plan hash."""
    fake_root = _setup_fake_root(tmp_path)
    dry_run = dry_run_run(
        fake_root,
        task_id=TASK_ID,
        request_id=REQUEST_ID,
        capability="read_file",
        operation="read_file",
        target="docs/06-adapter-layer.md",
        routing_snapshot_id=VALID_ROUTING_SNAPSHOT_ID,
    )
    snapshot = build_read_loop_snapshot(dry_run)

    assert snapshot.run["routing_snapshot_id"] == VALID_ROUTING_SNAPSHOT_ID
    base = dry_run_run(
        fake_root,
        task_id=TASK_ID,
        request_id=REQUEST_ID,
        capability="read_file",
        operation="read_file",
        target="docs/06-adapter-layer.md",
    )
    assert snapshot.run["plan_hash"] != base.plan_hash


def test_build_read_loop_snapshot_with_lineage(tmp_path: Path) -> None:
    """Retry/fallback lineage is projected into the run layer."""
    fake_root = _setup_fake_root(tmp_path)
    dry_run = dry_run_run(
        fake_root,
        task_id=TASK_ID,
        request_id="req-retry-001",
        capability="read_file",
        operation="read_file",
        target="docs/06-adapter-layer.md",
        retry_of=REQUEST_ID,
    )
    snapshot = build_read_loop_snapshot(dry_run)

    assert snapshot.run["lineage_type"] == "retry"
    assert snapshot.run["retry_of"] == REQUEST_ID
    assert snapshot.report["lineage_type"] == "retry"


def test_cli_dry_run_snapshot_json(capsys, tmp_path: Path) -> None:
    """CLI --dry-run --snapshot returns the read-loop snapshot JSON."""
    fake_root = _setup_fake_root(tmp_path)
    code = main(
        _base_args(fake_root, capability="read_file", operation="read_file", target="docs/06-adapter-layer.md")
        + ["--snapshot", "--json"]
    )
    captured = capsys.readouterr()
    result = json.loads(captured.out)
    assert code == 0
    assert result["schema_version"] == SCHEMA_VERSION
    assert result["snapshot_id"].startswith("sha256:")
    assert result["status"] == "pass"
    assert result["run"]["status"] == "planned"
    assert result["run"]["adapter_id"] == "dummy-local"
    assert result["report"]["status"] == "preview"
    assert result["report"]["evidence_candidate_count"] == 0
    assert result["report"]["evidence_candidate_type_counts"] == {}
    assert result["events"]


def test_cli_dry_run_snapshot_human_readable(capsys, tmp_path: Path) -> None:
    """CLI --dry-run --snapshot human output is compact and informative."""
    fake_root = _setup_fake_root(tmp_path)
    code = main(
        _base_args(fake_root, capability="read_file", operation="read_file", target="docs/06-adapter-layer.md")
        + ["--snapshot"]
    )
    captured = capsys.readouterr()
    assert code == 0
    assert "READ LOOP SNAPSHOT" in captured.out
    assert f"schema_version={SCHEMA_VERSION}" in captured.out
    assert "snapshot_id=sha256:" in captured.out
    assert "run: " in captured.out
    assert "events: count=" in captured.out
    assert "report: status=preview" in captured.out
    assert "evidence_candidate_count=0" in captured.out


def test_cli_dry_run_default_output_unchanged(capsys, tmp_path: Path) -> None:
    """Without --snapshot, run dry-run JSON output is unchanged."""
    fake_root = _setup_fake_root(tmp_path)
    code = main(
        _base_args(fake_root, capability="read_file", operation="read_file", target="docs/06-adapter-layer.md")
        + ["--json"]
    )
    captured = capsys.readouterr()
    result = json.loads(captured.out)
    assert code == 0
    assert "schema_version" not in result
    assert "snapshot_id" not in result
    assert result["status"] == "pass"
    assert "plan_hash" in result


def test_cli_commit_with_snapshot_blocked_and_no_writes(capsys, tmp_path: Path) -> None:
    """--commit --snapshot is rejected and performs no writes."""
    fake_root = _setup_fake_root(tmp_path)
    before_tasks = (fake_root / "tasks" / "tasks.jsonl").read_bytes()
    drafts_dir = fake_root / "drafts"
    events_file = fake_root / "tasks" / "events.jsonl"
    before_events = events_file.read_bytes() if events_file.exists() else b""

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
        "--snapshot",
        "--json",
    ]
    code = main(args)
    captured = capsys.readouterr()
    result = json.loads(captured.out)

    assert code == 2
    assert result["status"] == "blocked"
    assert result["findings"][0]["rule_id"] == "snapshot-not-supported-in-commit"
    assert (fake_root / "tasks" / "tasks.jsonl").read_bytes() == before_tasks
    assert not drafts_dir.exists() or list(drafts_dir.rglob("*.json")) == []
    assert not events_file.exists() or events_file.read_bytes() == before_events


def test_cli_dry_run_snapshot_blocked_structure(capsys, tmp_path: Path) -> None:
    """Snapshot CLI still returns a valid snapshot when routing is blocked."""
    fake_root = _setup_fake_root(tmp_path)
    code = main(
        _base_args(fake_root, capability="git_push", adapter="dummy-local", operation="git_push", target="origin/main")
        + ["--snapshot", "--json"]
    )
    captured = capsys.readouterr()
    result = json.loads(captured.out)
    assert code == 2
    assert result["status"] == "blocked"
    assert result["run"]["status"] == "blocked"
    assert result["run"]["adapter_id"] is None
    assert result["events"] == []
    assert result["report"]["candidate_event_count"] == 0


def test_cli_dry_run_snapshot_no_writes(capsys, tmp_path: Path) -> None:
    """Snapshot dry-run does not mutate the project tree."""
    fake_root = _setup_fake_root(tmp_path)
    before_tree = sorted(str(p.relative_to(fake_root)) for p in fake_root.rglob("*"))
    before_tasks = (fake_root / "tasks" / "tasks.jsonl").read_bytes()

    main(
        _base_args(fake_root, capability="read_file", operation="read_file", target="docs/06-adapter-layer.md")
        + ["--snapshot", "--json"]
    )

    after_tree = sorted(str(p.relative_to(fake_root)) for p in fake_root.rglob("*"))
    after_tasks = (fake_root / "tasks" / "tasks.jsonl").read_bytes()
    assert after_tree == before_tree
    assert after_tasks == before_tasks


def test_run_dry_run_result_to_dict_is_compatible_with_snapshot(tmp_path: Path) -> None:
    """build_read_loop_snapshot accepts the public RunDryRunResult from to_dict round-trip."""
    fake_root = _setup_fake_root(tmp_path)
    dry_run = dry_run_run(
        fake_root,
        task_id=TASK_ID,
        request_id=REQUEST_ID,
        capability="read_file",
        operation="read_file",
        target="docs/06-adapter-layer.md",
    )
    # Round-trip through to_dict ensures the snapshot builder only relies on
    # the public data contract of RunDryRunResult.
    d = dry_run.to_dict()
    restored = RunDryRunResult(
        status=d["status"],
        task_id=d["task_id"],
        request_id=d["request_id"],
        requested_capability=d["requested_capability"],
        mode=d["mode"],
        route=d["route"],
        preflight=d["preflight"],
        candidate_envelope_summary=d["candidate_envelope_summary"],
        candidate_events_summary=d["candidate_events_summary"],
        artifact_candidate_refs=d["artifact_candidate_refs"],
        evidence_candidate_refs=d["evidence_candidate_refs"],
        plan_hash=d.get("plan_hash"),
        constraints=d["constraints"],
        next_action=d.get("next_action"),
        lineage_type=d.get("lineage_type"),
        retry_of=d.get("retry_of"),
        fallback_from=d.get("fallback_from"),
        fallback_to=d.get("fallback_to"),
        routing_snapshot_id=d.get("routing_snapshot_id"),
    )
    snapshot = build_read_loop_snapshot(restored)
    assert snapshot.status == d["status"]
