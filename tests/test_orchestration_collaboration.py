"""Tests for deterministic read-only collaboration plan projection."""

from __future__ import annotations

import json
from pathlib import Path

from agent_runtime.cli import main
from agent_runtime.orchestration_collaboration import inspect_collaboration_plan

ROOT = Path(__file__).resolve().parents[1]


def _plan() -> dict:
    return {
        "parent_task_ref": "task-demo-001",
        "revision": 1,
        "socket_bindings": [
            {"socket_id": "kimi-code-acp", "role": "planner", "required_capabilities": ["light_coding"]},
            {"socket_id": "omp-acp", "role": "implementer", "required_capabilities": ["light_coding"]},
            {"socket_id": "claude-code-acp", "role": "reviewer", "required_capabilities": ["quality_review"]},
        ],
        "work_items": [
            {"work_item_id": "plan", "socket_id": "kimi-code-acp", "role": "planner", "depends_on": [], "expected_artifact_types": ["plan"], "review_required": False},
            {"work_item_id": "implement", "socket_id": "omp-acp", "role": "implementer", "depends_on": ["plan"], "expected_artifact_types": ["patch", "test_result"], "review_required": True},
            {"work_item_id": "review", "socket_id": "claude-code-acp", "role": "reviewer", "depends_on": ["implement"], "expected_artifact_types": ["review"], "review_required": False},
        ],
        "handoffs": [
            {"from_work_item_id": "plan", "to_work_item_id": "implement", "artifact_types": ["plan"]},
            {"from_work_item_id": "implement", "to_work_item_id": "review", "artifact_types": ["patch"]},
        ],
        "review_gates": [
            {"gate_id": "review-implementation", "after_work_item_ids": ["implement"], "review_role": "reviewer", "decision_options": ["approve", "request_changes"]},
        ],
    }


def _project_root(tmp_path: Path, data: dict | None = None) -> Path:
    root = tmp_path / "project"
    (root / "adapters").mkdir(parents=True)
    for name in ("adapters.sample.json", "adapter.schema.json"):
        (root / "adapters" / name).write_bytes((ROOT / "adapters" / name).read_bytes())
    (root / "plans").mkdir()
    (root / "plans" / "collaboration-plan.json").write_text(
        json.dumps(data or _plan()), encoding="utf-8"
    )
    return root


def test_collaboration_plan_is_deterministic_and_safe(tmp_path: Path) -> None:
    root = _project_root(tmp_path)
    first = inspect_collaboration_plan(root, "plans/collaboration-plan.json").to_dict()
    second = inspect_collaboration_plan(root, "plans/collaboration-plan.json").to_dict()
    assert first["status"] == "pass"
    assert first["plan"]["plan_id"] == second["plan"]["plan_id"]
    assert first["plan"]["guarantees"]["executes_agents"] is False
    explanations = first["plan"]["routing_explanations"]
    assert {item["invocation_mode"] for item in explanations} == {"acp_delegate"}
    assert all(item["selection_basis"] == "explicit_plan_binding" for item in explanations)
    assert all(item["capability_match"] is True for item in explanations)
    assert all(item["readiness_evidence"]["status"] == "not_collected" for item in explanations)
    assert all(item["readiness_evidence"]["live_probe_performed"] is False for item in explanations)


def test_collaboration_plan_cli_projects_a_valid_project_local_plan(capsys, tmp_path: Path) -> None:
    root = _project_root(tmp_path)
    code = main(["--root", str(root), "orchestration", "collaboration", "plan", "--file", "plans/collaboration-plan.json", "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["status"] == "pass"
    projected = payload["plan"]
    assert projected["summary"]["work_item_count"] == 3
    assert {item["socket_id"] for item in projected["socket_bindings"]} == {"kimi-code-acp", "omp-acp", "claude-code-acp"}
    assert projected["guarantees"]["executes_agents"] is False
    assert "selection_reason" not in json.dumps(projected)


def test_collaboration_plan_maps_readiness_contracts_by_invocation_family(tmp_path: Path) -> None:
    data = _plan()
    data["socket_bindings"] = [
        {"socket_id": "kimi-code-acp", "role": "planner", "required_capabilities": ["light_coding"]},
        {"socket_id": "pi-cli", "role": "implementer", "required_capabilities": ["cli_agent_print"]},
        {"socket_id": "qwenpaw-agent-api", "role": "reviewer", "required_capabilities": ["agent_call"]},
    ]
    data["work_items"][1]["socket_id"] = "pi-cli"
    data["work_items"][2]["socket_id"] = "qwenpaw-agent-api"
    root = _project_root(tmp_path, data)
    result = inspect_collaboration_plan(root, "plans/collaboration-plan.json").to_dict()
    explanations = {
        item["invocation_mode"]: item["readiness_evidence"]
        for item in result["plan"]["routing_explanations"]
    }
    assert explanations == {
        "acp_delegate": {
            "status": "not_collected",
            "contract": "socket-readiness/acp-session/v1",
            "live_probe_performed": False,
        },
        "local_cli": {
            "status": "not_collected",
            "contract": "socket-readiness/local-cli/v1",
            "live_probe_performed": False,
        },
        "agent_api": {
            "status": "not_collected",
            "contract": "socket-readiness/agent-api/v1",
            "live_probe_performed": False,
        },
    }


def test_collaboration_plan_rejects_unknown_socket_and_capability(tmp_path: Path) -> None:
    data = _plan()
    data["socket_bindings"][0]["socket_id"] = "unknown-agent"
    root = _project_root(tmp_path, data)
    result = inspect_collaboration_plan(root, "plans/collaboration-plan.json")
    assert result.status == "validation_failed"
    assert any(f.rule_id == "collaboration-plan-socket-unknown" for f in result.findings)


def test_collaboration_plan_rejects_cycles_and_invalid_handoff(tmp_path: Path) -> None:
    data = _plan()
    data["work_items"][0]["depends_on"] = ["review"]
    data["handoffs"][0]["artifact_types"] = ["review"]
    root = _project_root(tmp_path, data)
    result = inspect_collaboration_plan(root, "plans/collaboration-plan.json")
    rule_ids = {finding.rule_id for finding in result.findings}
    assert result.status == "validation_failed"
    assert "collaboration-plan-cycle" in rule_ids
    assert "collaboration-plan-handoff-artifact" in rule_ids


def test_collaboration_plan_requires_explicit_review_gate(tmp_path: Path) -> None:
    data = _plan()
    data["review_gates"] = []
    root = _project_root(tmp_path, data)
    result = inspect_collaboration_plan(root, "plans/collaboration-plan.json")
    assert result.status == "validation_failed"
    assert any(f.rule_id == "collaboration-plan-review-gate-missing" for f in result.findings)


def test_collaboration_plan_rejects_unsafe_free_form_fields(tmp_path: Path) -> None:
    data = _plan()
    data["work_items"][0]["prompt"] = "do not allow raw prompt content"
    root = _project_root(tmp_path, data)
    result = inspect_collaboration_plan(root, "plans/collaboration-plan.json")
    assert result.status == "validation_failed"
    assert any(f.rule_id == "collaboration-plan-unsafe-field" for f in result.findings)


def test_collaboration_plan_rejects_path_escape_and_writes_nothing(tmp_path: Path) -> None:
    root = _project_root(tmp_path)
    before = {path.relative_to(root): path.read_bytes() for path in root.rglob("*") if path.is_file()}
    result = inspect_collaboration_plan(root, "../outside.json")
    assert result.status == "validation_failed"
    assert result.findings[0].rule_id == "collaboration-plan-path-escape"
    after = {path.relative_to(root): path.read_bytes() for path in root.rglob("*") if path.is_file()}
    assert after == before


def test_collaboration_plan_allows_serial_reuse_of_one_socket_for_distinct_roles(tmp_path: Path) -> None:
    data = {
        "parent_task_ref": "task-stage89",
        "revision": 1,
        "socket_bindings": [
            {"socket_id": "pi-cli", "role": "planner", "required_capabilities": ["cli_agent_print"]},
            {"socket_id": "omp-acp", "role": "implementer", "required_capabilities": ["light_coding"]},
            {"socket_id": "pi-cli", "role": "reviewer", "required_capabilities": ["cli_agent_print"]},
        ],
        "work_items": [
            {"work_item_id": "plan", "socket_id": "pi-cli", "role": "planner", "depends_on": [], "expected_artifact_types": ["plan"], "review_required": False},
            {"work_item_id": "execute", "socket_id": "omp-acp", "role": "implementer", "depends_on": ["plan"], "expected_artifact_types": ["summary"], "review_required": True},
            {"work_item_id": "review", "socket_id": "pi-cli", "role": "reviewer", "depends_on": ["execute"], "expected_artifact_types": ["review"], "review_required": False},
        ],
        "handoffs": [
            {"from_work_item_id": "plan", "to_work_item_id": "execute", "artifact_types": ["plan"]},
            {"from_work_item_id": "execute", "to_work_item_id": "review", "artifact_types": ["summary"]},
        ],
        "review_gates": [{
            "gate_id": "review-execute", "after_work_item_ids": ["execute"],
            "review_role": "reviewer", "decision_options": ["approve", "request_changes"],
        }],
    }
    root = _project_root(tmp_path, data)

    result = inspect_collaboration_plan(root, "plans/collaboration-plan.json")

    assert result.status == "pass"
    assert [(item["socket_id"], item["role"]) for item in result.plan["socket_bindings"]] == [
        ("omp-acp", "implementer"), ("pi-cli", "planner"), ("pi-cli", "reviewer"),
    ]
