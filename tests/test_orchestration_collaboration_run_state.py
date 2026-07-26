"""Tests for the Stage 79 fixture-backed collaboration run state model."""

from __future__ import annotations

import json
from pathlib import Path

from agent_runtime.cli import main
from agent_runtime.orchestration_collaboration_run_state import inspect_collaboration_run_state

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = "adapters/collaboration-run-state.example.json"


def _fixture_data() -> dict:
    return json.loads((ROOT / FIXTURE).read_text(encoding="utf-8"))


def _files(root: Path) -> dict[Path, bytes]:
    return {
        path.relative_to(root): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


def _project_root(tmp_path: Path, data: dict) -> Path:
    root = tmp_path / "project"
    adapters = root / "adapters"
    adapters.mkdir(parents=True)
    for name in (
        "adapters.sample.json",
        "adapter.schema.json",
        "collaboration-plan.example.json",
        "collaboration-run-state.schema.json",
    ):
        (adapters / name).write_bytes((ROOT / "adapters" / name).read_bytes())
    (adapters / "run.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return root


def _rule_ids(result) -> set[str]:
    return {item.rule_id for item in result.findings}


def test_run_state_fixture_projects_deterministic_read_only_history() -> None:
    before = _files(ROOT)
    first = inspect_collaboration_run_state(ROOT, FIXTURE)
    second = inspect_collaboration_run_state(ROOT, FIXTURE)

    assert first.status == second.status == "pass"
    assert first.exit_code() == 0
    assert first.to_dict() == second.to_dict()
    assert _files(ROOT) == before

    payload = first.to_dict()
    assert payload["schema_version"] == "control-plane/collaboration-run-state/v1"
    assert payload["source"] == {"collaboration_run_file": FIXTURE}
    assert payload["guarantees"] == {
        "deterministic": True,
        "read_only": True,
        "fixture_backed": True,
        "dispatch_eligible": False,
        "execution": "not_executed",
        "executes_agents": False,
        "starts_sessions": False,
        "probes_readiness": False,
        "writes_files": False,
        "writes_ledgers": False,
        "accesses_network": False,
    }
    run = payload["run"]
    assert run["status"] == "completed"
    assert run["dispatch_eligible"] is False
    assert run["execution"] == "not_executed"
    assert run["summary"] == {
        "work_item_count": 3,
        "attempt_count": 4,
        "retry_count": 1,
        "review_count": 2,
        "handoff_count": 2,
        "artifact_count": 5,
        "event_count": 56,
        "blocked_recovery_count": 1,
    }
    assert run["current_attempts"]["implement"] == "attempt-implement-2"
    assert [item["attempt_number"] for item in run["attempts"] if item["work_item_id"] == "implement"] == [1, 2]
    assert [item["status"] for item in run["reviews"]] == ["changes_requested", "approved"]
    assert all(not item["enabled"] for item in run["operator_actions"])
    assert run["run_projection_id"].startswith("sha256:")


def test_run_state_rejects_path_escape() -> None:
    result = inspect_collaboration_run_state(ROOT, "../outside.json")

    assert result.status == "validation_failed"
    assert _rule_ids(result) == {"collaboration-run-state-path-escape"}


def test_run_state_rejects_schema_failure(tmp_path: Path) -> None:
    data = _fixture_data()
    data["run_state"] = "mystery"
    root = _project_root(tmp_path, data)

    result = inspect_collaboration_run_state(root, "adapters/run.json")

    assert result.status == "validation_failed"
    assert _rule_ids(result) == {"collaboration-run-state-schema-invalid"}


def test_run_state_rejects_unknown_work_item(tmp_path: Path) -> None:
    data = _fixture_data()
    data["work_item_attempts"][0]["work_item_id"] = "missing"
    root = _project_root(tmp_path, data)

    result = inspect_collaboration_run_state(root, "adapters/run.json")

    assert "collaboration-run-state-work-item-unknown" in _rule_ids(result)


def test_run_state_rejects_non_contiguous_attempt_numbers(tmp_path: Path) -> None:
    data = _fixture_data()
    data["work_item_attempts"][2]["attempt_number"] = 3
    root = _project_root(tmp_path, data)

    result = inspect_collaboration_run_state(root, "adapters/run.json")

    assert "collaboration-run-state-attempt-sequence" in _rule_ids(result)


def test_run_state_rejects_non_contiguous_event_sequence(tmp_path: Path) -> None:
    data = _fixture_data()
    data["events"][10]["sequence"] = 99
    root = _project_root(tmp_path, data)

    result = inspect_collaboration_run_state(root, "adapters/run.json")

    assert "collaboration-run-state-event-sequence" in _rule_ids(result)


def test_run_state_rejects_invalid_or_post_terminal_transition(tmp_path: Path) -> None:
    data = _fixture_data()
    data["events"].append({
        "sequence": 49,
        "event_id": "event-post-terminal",
        "event_type": "run_started",
        "entity_type": "run",
        "entity_id": data["run_id"],
        "from_state": "completed",
        "to_state": "running",
        "label": "Invalid post-terminal transition",
    })
    root = _project_root(tmp_path, data)

    result = inspect_collaboration_run_state(root, "adapters/run.json")

    assert "collaboration-run-state-transition-invalid" in _rule_ids(result)


def test_run_state_rejects_projection_state_mismatch(tmp_path: Path) -> None:
    data = _fixture_data()
    data["work_item_attempts"][0]["status"] = "failed"
    root = _project_root(tmp_path, data)

    result = inspect_collaboration_run_state(root, "adapters/run.json")

    assert "collaboration-run-state-projection-mismatch" in _rule_ids(result)


def test_run_state_rejects_artifact_contract_mismatch(tmp_path: Path) -> None:
    data = _fixture_data()
    data["artifacts"][0]["artifact_type"] = "patch"
    root = _project_root(tmp_path, data)

    result = inspect_collaboration_run_state(root, "adapters/run.json")

    assert "collaboration-run-state-artifact-contract" in _rule_ids(result)


def test_run_state_rejects_review_contract_mismatch(tmp_path: Path) -> None:
    data = _fixture_data()
    data["reviews"][1]["gate_id"] = "missing-gate"
    root = _project_root(tmp_path, data)

    result = inspect_collaboration_run_state(root, "adapters/run.json")

    assert "collaboration-run-state-review-contract" in _rule_ids(result)


def test_run_state_rejects_handoff_contract_mismatch(tmp_path: Path) -> None:
    data = _fixture_data()
    data["handoffs"][0]["to_work_item_id"] = "review"
    root = _project_root(tmp_path, data)

    result = inspect_collaboration_run_state(root, "adapters/run.json")

    assert "collaboration-run-state-handoff-contract" in _rule_ids(result)


def test_completed_run_requires_completed_latest_attempts(tmp_path: Path) -> None:
    data = _fixture_data()
    data["run_state"] = "completed"
    data["work_item_attempts"][-1]["status"] = "running"
    root = _project_root(tmp_path, data)

    result = inspect_collaboration_run_state(root, "adapters/run.json")

    assert "collaboration-run-state-completion-incomplete" in _rule_ids(result)


def test_cli_run_state_inspect_is_deterministic(capsys) -> None:
    args = [
        "orchestration", "collaboration", "run-state", "inspect",
        "--file", FIXTURE, "--json",
    ]
    first_code = main(args)
    first = capsys.readouterr()
    second_code = main(args)
    second = capsys.readouterr()

    assert first_code == second_code == 0
    assert first.out == second.out
    assert first.err == second.err == ""
    payload = json.loads(first.out)
    assert payload["status"] == "pass"
    assert payload["run"]["status"] == "completed"
    assert payload["run"]["execution"] == "not_executed"
