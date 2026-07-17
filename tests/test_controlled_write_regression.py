"""Controlled-write regression test.

This test runs the full controlled-write chain in a temporary project root and
asserts that:

- task create dry-run -> commit -> event append dry-run -> commit works.
- post-commit read-only checks (task validate / check-ledger) pass.
- runtime report runs and does not leak title / event message.
- the repository's real task/event ledgers are not modified.

No new write permissions are introduced; the test only reuses existing commit
commands and tmp_path isolation.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from agent_runtime.cli import main
from agent_runtime.execution_audit_writer import (
    inspect_execution_attempt,
    record_execution_attempt_started,
    record_execution_terminal,
)

ROOT = Path(__file__).resolve().parents[1]


def _setup_fake_root(tmp_path: Path) -> Path:
    """Create a fake project root with the schemas and policies needed."""
    fake_root = tmp_path / "project"
    fake_root.mkdir(parents=True, exist_ok=True)

    for src_rel in (
        "tasks/task.schema.json",
        "tasks/event.schema.json",
        "tasks/execution-audit-event.schema.json",
        "adapters/execution-envelope.schema.json",
    ):
        src = ROOT / src_rel
        dst = fake_root / src_rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.exists():
            shutil.copyfile(src, dst)

    policy_src = ROOT / "policies"
    policy_dst = fake_root / "policies"
    policy_dst.mkdir(parents=True, exist_ok=True)
    for policy_file in policy_src.glob("*.sample.policy.json"):
        shutil.copyfile(policy_file, policy_dst / policy_file.name)

    return fake_root


def _write_json(path: Path, data: dict[str, object]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def _task(task_id: str) -> dict[str, object]:
    return {
        "id": task_id,
        "title": "controlled write regression task title",
        "status": "planned",
        "created_at": "2026-07-07T10:00:00+08:00",
        "updated_at": "2026-07-07T10:00:00+08:00",
        "created_by": "cli",
        "source": "cli",
        "assignee": "cli",
        "tags": ["regression"],
        "artifacts": [],
        "evidence": [],
    }


def _event(event_id: str, task_id: str) -> dict[str, object]:
    return {
        "event_id": event_id,
        "task_id": task_id,
        "timestamp": "2026-07-07T10:00:00+08:00",
        "actor": "cli",
        "event_type": "created",
        "from_status": None,
        "to_status": "planned",
        "message": "controlled write regression event message",
        "artifacts": [],
        "metadata": {},
    }


def _envelope(request_id: str, task_id: str) -> dict[str, object]:
    return {
        "version": 1,
        "description": "controlled write regression envelope",
        "artifacts": [
            {
                "artifact_type": "adapter_request",
                "request_id": request_id,
                "task_id": task_id,
                "adapter_id": "shell-local",
                "operation": "read_file",
                "actor": "cli",
                "target": "README.md",
                "input": {},
                "context": {
                    "source": "cli",
                    "policy_profile": "all",
                    "risk_level": "local",
                    "dry_run": True,
                    "requires_approval": False,
                },
                "preflight": {"status": "pass", "findings": []},
                "created_at": "2026-07-07T10:00:00+08:00",
            }
        ],
    }


def test_controlled_write_regression_does_not_touch_real_ledgers(tmp_path, monkeypatch, capsys):
    real_tasks = ROOT / "tasks" / "tasks.jsonl"
    real_events = ROOT / "tasks" / "events.jsonl"
    real_tasks_before = real_tasks.read_bytes() if real_tasks.is_file() else b""
    real_events_before = real_events.read_bytes() if real_events.is_file() else b""

    root = _setup_fake_root(tmp_path)
    task_id = "task-20260707-999"
    event_id = "evt-20260707-999"
    request_id = "req-20260707-999"

    tasks_dir = root / "tasks"
    tasks_dir.mkdir(exist_ok=True)
    tasks_file = tasks_dir / "tasks.jsonl"
    events_file = tasks_dir / "events.jsonl"
    tasks_file.write_text("", encoding="utf-8")
    events_file.write_text("", encoding="utf-8")

    _write_json(root / "candidate-task.json", _task(task_id))
    _write_json(root / "candidate-event.json", _event(event_id, task_id))
    _write_json(root / "envelope.json", _envelope(request_id, task_id))

    def _run(argv: list[str]) -> str:
        monkeypatch.setattr("sys.argv", ["agent-runtime", "--root", str(root), *argv])
        code = main()
        captured = capsys.readouterr()
        return captured.out, code

    # 1) task create dry-run
    out, code = _run(["runtime", "task", "create", "--file", "candidate-task.json", "--dry-run"])
    assert code == 0
    assert "would_create=False" in out
    assert tasks_file.read_text(encoding="utf-8") == ""

    # 2) task create commit
    out, code = _run(["runtime", "task", "create", "--file", "candidate-task.json", "--commit"])
    assert code == 0
    assert "committed=True" in out
    assert tasks_file.read_text(encoding="utf-8").count("\n") == 1

    # 3) event append dry-run
    out, code = _run(["runtime", "event", "append", "--file", "candidate-event.json", "--dry-run"])
    assert code == 0
    assert "would_append=False" in out
    assert events_file.read_text(encoding="utf-8") == ""

    # 4) event append commit
    out, code = _run(["runtime", "event", "append", "--file", "candidate-event.json", "--commit"])
    assert code == 0
    assert "committed=True" in out
    assert events_file.read_text(encoding="utf-8").count("\n") == 1

    # 5) post-commit read-only checks
    out, code = _run(["task", "validate", "--record-file", "tasks/tasks.jsonl", "--schema", "task"])
    assert code == 0
    out, code = _run(["task", "validate", "--record-file", "tasks/events.jsonl", "--schema", "event"])
    assert code == 0
    out, code = _run(["task", "check-ledger", "--tasks-file", "tasks/tasks.jsonl", "--events-file", "tasks/events.jsonl"])
    assert code == 0
    assert "PASS" in out

    # 6) runtime report
    out, code = _run([
        "runtime", "report",
        "--task-id", task_id,
        "--request-id", request_id,
        "--envelope", "envelope.json",
        "--tasks-file", "tasks/tasks.jsonl",
        "--events-file", "tasks/events.jsonl",
    ])
    assert code in {0, 3, 4}
    assert task_id in out
    # No sensitive free-text payload should leak.
    assert "controlled write regression task title" not in out
    assert "controlled write regression event message" not in out

    # Repository real ledgers must be unchanged.
    assert real_tasks.read_bytes() == real_tasks_before
    assert real_events.read_bytes() == real_events_before


def test_controlled_write_regression_event_import_does_not_touch_real_ledgers(
    tmp_path, monkeypatch, capsys
):
    """Run the controlled-write chain with runtime event import batch commit."""
    real_tasks = ROOT / "tasks" / "tasks.jsonl"
    real_events = ROOT / "tasks" / "events.jsonl"
    real_tasks_before = real_tasks.read_bytes() if real_tasks.is_file() else b""
    real_events_before = real_events.read_bytes() if real_events.is_file() else b""

    root = _setup_fake_root(tmp_path)
    task_id = "task-20260707-998"
    request_id = "req-20260707-998"

    tasks_dir = root / "tasks"
    tasks_dir.mkdir(exist_ok=True)
    tasks_file = tasks_dir / "tasks.jsonl"
    events_file = tasks_dir / "events.jsonl"
    tasks_file.write_text("", encoding="utf-8")
    events_file.write_text("", encoding="utf-8")

    _write_json(root / "candidate-task.json", _task(task_id))
    _write_json(root / "seed-event.json", _event("evt-20260707-998001", task_id))
    _write_json(root / "envelope.json", _envelope(request_id, task_id))

    def _run(argv: list[str]) -> tuple[str, int]:
        monkeypatch.setattr("sys.argv", ["agent-runtime", "--root", str(root), *argv])
        code = main()
        captured = capsys.readouterr()
        return captured.out, code

    # Seed task and one event so the ledger is non-empty for import dry-run.
    out, code = _run(["runtime", "task", "create", "--file", "candidate-task.json", "--commit"])
    assert code == 0, out
    out, code = _run(["runtime", "event", "append", "--file", "seed-event.json", "--commit"])
    assert code == 0, out
    assert tasks_file.read_text(encoding="utf-8").count("\n") == 1
    assert events_file.read_text(encoding="utf-8").count("\n") == 1

    # Update task snapshot to running so the upcoming status_changed event is consistent.
    task_record = json.loads(tasks_file.read_text(encoding="utf-8").strip())
    task_record["status"] = "running"
    tasks_file.write_text(json.dumps(task_record, ensure_ascii=False) + "\n", encoding="utf-8")

    # Build a two-event candidate batch.
    batch = [
        _event("evt-20260707-998002", task_id),
        _event("evt-20260707-998003", task_id),
    ]
    batch[0]["timestamp"] = "2026-07-07T10:01:00+08:00"
    batch[0]["event_type"] = "status_changed"
    batch[0]["from_status"] = "planned"
    batch[0]["to_status"] = "running"
    batch[1]["timestamp"] = "2026-07-07T10:02:00+08:00"
    batch[1]["event_type"] = "progress"
    batch[1]["from_status"] = "running"
    batch[1]["to_status"] = "running"

    candidate_import = root / "candidate-import-events.jsonl"
    candidate_import.write_text(
        "\n".join(json.dumps(e, ensure_ascii=False) for e in batch) + "\n",
        encoding="utf-8",
    )

    # 1) event import dry-run should pass and expose a plan_hash.
    out, code = _run(
        ["runtime", "event", "import", "--file", "candidate-import-events.jsonl", "--dry-run"]
    )
    assert code == 0, out
    assert "would_import=True" in out
    assert "plan_hash=sha256:" in out
    assert events_file.read_text(encoding="utf-8").count("\n") == 1

    # Capture the actual plan hash via JSON output.
    out_json, code = _run(
        [
            "runtime",
            "event",
            "import",
            "--file",
            "candidate-import-events.jsonl",
            "--dry-run",
            "--json",
        ]
    )
    assert code == 0
    dry_run_result = json.loads(out_json)
    plan_hash = dry_run_result["plan_hash"]
    assert plan_hash.startswith("sha256:")

    # 2) commit with the correct expected plan hash should append the batch.
    out, code = _run(
        [
            "runtime",
            "event",
            "import",
            "--file",
            "candidate-import-events.jsonl",
            "--commit",
            "--expected-plan-hash",
            plan_hash,
        ]
    )
    assert code == 0
    assert "committed=True" in out
    assert "freeze_check=pass" in out
    assert events_file.read_text(encoding="utf-8").count("\n") == 3

    # 3) Build a second candidate and capture its plan hash.
    batch2 = [_event("evt-20260707-998004", task_id)]
    batch2[0]["timestamp"] = "2026-07-07T10:03:00+08:00"
    batch2[0]["event_type"] = "progress"
    batch2[0]["from_status"] = "running"
    batch2[0]["to_status"] = "running"
    candidate_import2 = root / "candidate-import-events2.jsonl"
    candidate_import2.write_text(
        json.dumps(batch2[0], ensure_ascii=False) + "\n", encoding="utf-8"
    )

    out_json2, code = _run(
        [
            "runtime",
            "event",
            "import",
            "--file",
            "candidate-import-events2.jsonl",
            "--dry-run",
            "--json",
        ]
    )
    assert code == 0
    plan_hash2 = json.loads(out_json2)["plan_hash"]

    # Mutate the events ledger so plan_hash2 is now stale.
    events_file.write_text(
        events_file.read_text(encoding="utf-8")
        + json.dumps(_event("evt-20260707-998005", task_id), ensure_ascii=False)
        + "\n",
        encoding="utf-8",
    )
    events_after_mutation = events_file.read_bytes()

    # Commit with the stale plan hash must be blocked and must not modify the ledger.
    out, code = _run(
        [
            "runtime",
            "event",
            "import",
            "--file",
            "candidate-import-events2.jsonl",
            "--commit",
            "--expected-plan-hash",
            plan_hash2,
        ]
    )
    assert code == 2
    assert "plan-hash-mismatch" in out
    assert "freeze_check=failed" in out
    assert events_file.read_bytes() == events_after_mutation

    # 4) Post-commit read-only checks should still pass.
    out, code = _run(
        ["task", "validate", "--record-file", "tasks/events.jsonl", "--schema", "event"]
    )
    assert code == 0
    out, code = _run(
        [
            "task",
            "check-ledger",
            "--tasks-file",
            "tasks/tasks.jsonl",
            "--events-file",
            "tasks/events.jsonl",
        ]
    )
    assert code == 0
    assert "PASS" in out

    # 5) runtime report should succeed and stay sanitized.
    out, code = _run(
        [
            "runtime",
            "report",
            "--task-id",
            task_id,
            "--request-id",
            request_id,
            "--envelope",
            "envelope.json",
            "--tasks-file",
            "tasks/tasks.jsonl",
            "--events-file",
            "tasks/events.jsonl",
        ]
    )
    assert code in {0, 3, 4}
    assert task_id in out
    assert "controlled write regression task title" not in out
    assert "controlled write regression event message" not in out

    # 6) Task ledger must not be touched by event import commit.
    assert tasks_file.read_text(encoding="utf-8").count("\n") == 1

    # Repository real ledgers must be unchanged.
    assert real_tasks.read_bytes() == real_tasks_before
    assert real_events.read_bytes() == real_events_before


def test_controlled_write_regression_event_import_strict_freeze(
    tmp_path, monkeypatch, capsys
):
    """Run event import with --require-dry-run in a temporary project root."""
    real_tasks = ROOT / "tasks" / "tasks.jsonl"
    real_events = ROOT / "tasks" / "events.jsonl"
    real_tasks_before = real_tasks.read_bytes() if real_tasks.is_file() else b""
    real_events_before = real_events.read_bytes() if real_events.is_file() else b""

    root = _setup_fake_root(tmp_path)
    task_id = "task-20260707-997"
    request_id = "req-20260707-997"

    tasks_dir = root / "tasks"
    tasks_dir.mkdir(exist_ok=True)
    tasks_file = tasks_dir / "tasks.jsonl"
    events_file = tasks_dir / "events.jsonl"
    tasks_file.write_text("", encoding="utf-8")
    events_file.write_text("", encoding="utf-8")

    _write_json(root / "candidate-task.json", _task(task_id))
    _write_json(root / "envelope.json", _envelope(request_id, task_id))

    def _run(argv: list[str]) -> tuple[str, int]:
        monkeypatch.setattr("sys.argv", ["agent-runtime", "--root", str(root), *argv])
        code = main()
        captured = capsys.readouterr()
        return captured.out, code

    # Seed task and one created event, then move task snapshot to running.
    out, code = _run(["runtime", "task", "create", "--file", "candidate-task.json", "--commit"])
    assert code == 0, out
    seed_event = _event("evt-20260707-997001", task_id)
    _write_json(root / "seed-event.json", seed_event)
    out, code = _run(["runtime", "event", "append", "--file", "seed-event.json", "--commit"])
    assert code == 0, out
    task_record = json.loads(tasks_file.read_text(encoding="utf-8").strip())
    task_record["status"] = "running"
    tasks_file.write_text(json.dumps(task_record, ensure_ascii=False) + "\n", encoding="utf-8")

    # Build a two-event candidate batch.
    batch = [
        _event("evt-20260707-997002", task_id),
        _event("evt-20260707-997003", task_id),
    ]
    batch[0]["timestamp"] = "2026-07-07T10:01:00+08:00"
    batch[0]["event_type"] = "status_changed"
    batch[0]["from_status"] = "planned"
    batch[0]["to_status"] = "running"
    batch[1]["timestamp"] = "2026-07-07T10:02:00+08:00"
    batch[1]["event_type"] = "progress"
    batch[1]["from_status"] = "running"
    batch[1]["to_status"] = "running"

    candidate_import = root / "candidate-import-events.jsonl"
    candidate_import.write_text(
        "\n".join(json.dumps(e, ensure_ascii=False) for e in batch) + "\n",
        encoding="utf-8",
    )

    # 1) dry-run should pass and expose a plan_hash.
    out_json, code = _run(
        [
            "runtime",
            "event",
            "import",
            "--file",
            "candidate-import-events.jsonl",
            "--dry-run",
            "--json",
        ]
    )
    assert code == 0
    dry_run_result = json.loads(out_json)
    plan_hash = dry_run_result["plan_hash"]
    assert plan_hash.startswith("sha256:")

    # 2) commit with --require-dry-run and correct hash should append the batch.
    out, code = _run(
        [
            "runtime",
            "event",
            "import",
            "--file",
            "candidate-import-events.jsonl",
            "--commit",
            "--require-dry-run",
            "--expected-plan-hash",
            plan_hash,
        ]
    )
    assert code == 0, out
    assert "committed=True" in out
    assert "freeze_check=pass" in out
    assert events_file.read_text(encoding="utf-8").count("\n") == 3

    # 3) Build a second candidate and capture its plan hash.
    batch2 = [_event("evt-20260707-997004", task_id)]
    batch2[0]["timestamp"] = "2026-07-07T10:03:00+08:00"
    batch2[0]["event_type"] = "progress"
    batch2[0]["from_status"] = "running"
    batch2[0]["to_status"] = "running"
    candidate_import2 = root / "candidate-import-events2.jsonl"
    candidate_import2.write_text(
        json.dumps(batch2[0], ensure_ascii=False) + "\n", encoding="utf-8"
    )

    out_json2, code = _run(
        [
            "runtime",
            "event",
            "import",
            "--file",
            "candidate-import-events2.jsonl",
            "--dry-run",
            "--json",
        ]
    )
    assert code == 0
    plan_hash2 = json.loads(out_json2)["plan_hash"]

    # Mutate the candidate after dry-run to make the hash stale.
    mutated = dict(batch2[0])
    mutated["message"] = "mutated progress message"
    candidate_import2.write_text(
        json.dumps(mutated, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    events_after_mutation = events_file.read_bytes()

    # Commit with --require-dry-run and stale hash must be blocked.
    out, code = _run(
        [
            "runtime",
            "event",
            "import",
            "--file",
            "candidate-import-events2.jsonl",
            "--commit",
            "--require-dry-run",
            "--expected-plan-hash",
            plan_hash2,
        ]
    )
    assert code == 2
    assert "plan-hash-mismatch" in out
    assert "freeze_check=failed" in out
    assert "mutated progress message" not in out
    assert events_file.read_bytes() == events_after_mutation

    # 4) Post-commit read-only checks should still pass.
    out, code = _run(
        ["task", "validate", "--record-file", "tasks/events.jsonl", "--schema", "event"]
    )
    assert code == 0
    out, code = _run(
        [
            "task",
            "check-ledger",
            "--tasks-file",
            "tasks/tasks.jsonl",
            "--events-file",
            "tasks/events.jsonl",
        ]
    )
    assert code == 0
    assert "PASS" in out

    # 5) Task ledger must not be touched by event import commit.
    assert tasks_file.read_text(encoding="utf-8").count("\n") == 1

    # Repository real ledgers must be unchanged.
    assert real_tasks.read_bytes() == real_tasks_before
    assert real_events.read_bytes() == real_events_before


def test_execution_audit_writer_controlled_write_chain_is_isolated(
    tmp_path: Path,
) -> None:
    real_tasks = ROOT / "tasks" / "tasks.jsonl"
    real_events = ROOT / "tasks" / "events.jsonl"
    real_tasks_before = real_tasks.read_bytes() if real_tasks.is_file() else b""
    real_events_before = real_events.read_bytes() if real_events.is_file() else b""
    root = _setup_fake_root(tmp_path)
    task_id = "task-20260717-991"
    tasks_file = root / "tasks" / "tasks.jsonl"
    events_file = root / "tasks" / "events.jsonl"
    tasks_file.parent.mkdir(parents=True, exist_ok=True)
    tasks_file.write_text(
        json.dumps(
            {
                "id": task_id,
                "title": "execution audit regression",
                "status": "running",
                "created_at": "2026-07-17T01:00:00+00:00",
                "updated_at": "2026-07-17T01:00:00+00:00",
                "created_by": "cli",
                "source": "cli",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    events_file.write_text(
        json.dumps(
            {
                "event_id": "evt-20260717-991001",
                "task_id": task_id,
                "timestamp": "2026-07-17T01:00:00+00:00",
                "actor": "cli",
                "event_type": "created",
                "from_status": None,
                "to_status": "running",
                "message": "created",
                "metadata": {},
            }
        )
        + "\n",
        encoding="utf-8",
    )

    started = record_execution_attempt_started(
        root,
        task_id=task_id,
        request_id="req-20260717-991",
        plan_hash="sha256:" + "a" * 64,
        adapter_id="shell-local",
        capability="git_status",
        operation="git_status",
    )
    assert started.status == "pass"
    assert started.child_created is False
    terminal = record_execution_terminal(
        root,
        attempt_id=started.attempt_id,
        event_type="execution_failed",
        phase="audit",
        failure_code="executor_unavailable",
    )
    assert terminal.status == "pass"
    inspected = inspect_execution_attempt(root, started.attempt_id)
    assert inspected.state == "closed_failed"
    assert events_file.read_text(encoding="utf-8").count("\n") == 3
    assert real_tasks.read_bytes() == real_tasks_before
    assert real_events.read_bytes() == real_events_before
