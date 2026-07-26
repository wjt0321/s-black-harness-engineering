"""Tests for the v0.20 single-work-item dispatch proposal read model."""

from __future__ import annotations

import json
from pathlib import Path

from agent_runtime.orchestration_collaboration_dispatch import inspect_collaboration_dispatch

ROOT = Path(__file__).resolve().parents[1]
DISPATCH = "adapters/collaboration-dispatch.example.json"


def test_dispatch_example_is_plan_eligible_but_execution_blocked() -> None:
    result = inspect_collaboration_dispatch(ROOT, DISPATCH).to_dict()
    assert result["status"] == "pass"
    proposal = result["proposal"]
    assert proposal["work_item_id"] == "implement"
    assert proposal["socket_id"] == "omp-acp"
    assert proposal["plan_eligible"] is True
    assert proposal["dispatch_eligible"] is False
    assert proposal["execution"] == "not_executed"
    assert proposal["blocked_reasons"] == [
        "readiness_not_collected",
        "execution_authority_unavailable",
    ]
    assert result["guarantees"]["dispatches_work"] is False


def test_dispatch_projection_is_deterministic() -> None:
    first = inspect_collaboration_dispatch(ROOT, DISPATCH).to_dict()
    second = inspect_collaboration_dispatch(ROOT, DISPATCH).to_dict()
    assert first == second
    assert first["proposal"]["proposal_id"].startswith("sha256:")


def _copy_dispatch(tmp_path: Path, mutate) -> tuple[Path, str]:
    root = tmp_path / "project"
    (root / "adapters").mkdir(parents=True)
    for name in (
        "adapter.schema.json",
        "adapters.sample.json",
        "collaboration-plan.example.json",
        "collaboration-dispatch.schema.json",
        "collaboration-dispatch.example.json",
    ):
        (root / "adapters" / name).write_bytes((ROOT / "adapters" / name).read_bytes())
    data = json.loads((root / "adapters" / "collaboration-dispatch.example.json").read_text(encoding="utf-8"))
    mutate(data)
    (root / "adapters" / "dispatch.json").write_text(json.dumps(data), encoding="utf-8")
    return root, "adapters/dispatch.json"


def test_dispatch_rejects_plan_drift(tmp_path: Path) -> None:
    root, path = _copy_dispatch(tmp_path, lambda data: data.__setitem__("plan_id", "sha256:" + "0" * 64))
    result = inspect_collaboration_dispatch(root, path)
    assert result.status == "validation_failed"
    assert result.findings[0].rule_id == "dispatch-plan-drift"


def test_dispatch_rejects_socket_mismatch(tmp_path: Path) -> None:
    root, path = _copy_dispatch(tmp_path, lambda data: data.__setitem__("socket_id", "kimi-code-acp"))
    result = inspect_collaboration_dispatch(root, path)
    assert result.status == "validation_failed"
    assert result.findings[0].rule_id == "dispatch-socket-mismatch"


def test_dispatch_rejects_handoff_artifact_mismatch(tmp_path: Path) -> None:
    root, path = _copy_dispatch(tmp_path, lambda data: data.__setitem__("input_artifact_types", []))
    result = inspect_collaboration_dispatch(root, path)
    assert result.status == "validation_failed"
    assert result.findings[0].rule_id == "dispatch-input-artifact-mismatch"


def test_dispatch_rejects_path_escape() -> None:
    result = inspect_collaboration_dispatch(ROOT, "../dispatch.json")
    assert result.status == "validation_failed"
    assert result.findings[0].rule_id == "dispatch-path-escape"
