"""Tests for the v0.20 single-work-item dispatch proposal read model."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from agent_runtime.orchestration_acp_readiness import collect_acp_readiness
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


def _dispatch_with_evidence(tmp_path: Path, socket_id: str = "omp-acp") -> tuple[Path, str]:
    root, dispatch_path = _copy_dispatch(tmp_path, lambda data: None)
    for name in (
        "acp-runner-bindings.schema.json",
        "acp-runner-bindings.sample.json",
        "acp-runner-state-snapshot.schema.json",
        "acp-runner-state-snapshot.sample.json",
        "acp-readiness-evidence-v2.schema.json",
    ):
        (root / "adapters" / name).write_bytes((ROOT / "adapters" / name).read_bytes())
    collected = collect_acp_readiness(
        root,
        socket_id,
        "adapters/acp-runner-state-snapshot.sample.json",
        "2026-07-26T08:05:00Z",
        600,
    ).to_dict()
    (root / "adapters" / "evidence.json").write_text(
        json.dumps(collected["evidence"]), encoding="utf-8"
    )
    dispatch = json.loads((root / dispatch_path).read_text(encoding="utf-8"))
    dispatch["readiness_evidence_file"] = "adapters/evidence.json"
    dispatch["evaluated_at"] = "2026-07-26T08:05:00Z"
    (root / dispatch_path).write_text(json.dumps(dispatch), encoding="utf-8")
    return root, dispatch_path


def test_dispatch_binds_available_but_insufficient_evidence(tmp_path: Path) -> None:
    root, path = _dispatch_with_evidence(tmp_path)
    payload = inspect_collaboration_dispatch(root, path).to_dict()
    assert payload["status"] == "pass"
    assert payload["proposal"]["readiness_evidence"]["status"] == "available"
    assert payload["proposal"]["readiness_evidence"]["level"] == "runner_listed"
    assert payload["proposal"]["dispatch_eligible"] is False
    assert payload["proposal"]["blocked_reasons"] == [
        "readiness_insufficient",
        "execution_authority_unavailable",
    ]


def test_dispatch_rejects_expired_evidence(tmp_path: Path) -> None:
    root, path = _dispatch_with_evidence(tmp_path)
    dispatch = json.loads((root / path).read_text(encoding="utf-8"))
    dispatch["evaluated_at"] = "2026-07-26T08:10:01Z"
    (root / path).write_text(json.dumps(dispatch), encoding="utf-8")
    result = inspect_collaboration_dispatch(root, path)
    assert result.status == "validation_failed"
    assert result.findings[0].rule_id == "dispatch-readiness-expired"


def test_dispatch_rejects_tampered_evidence(tmp_path: Path) -> None:
    root, path = _dispatch_with_evidence(tmp_path)
    evidence_path = root / "adapters" / "evidence.json"
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    evidence["session_state"] = "open"
    evidence_path.write_text(json.dumps(evidence), encoding="utf-8")
    result = inspect_collaboration_dispatch(root, path)
    assert result.status == "validation_failed"
    assert result.findings[0].rule_id == "dispatch-readiness-tampered"


def test_dispatch_rejects_evidence_for_another_socket(tmp_path: Path) -> None:
    root, path = _dispatch_with_evidence(tmp_path, "kimi-code-acp")
    result = inspect_collaboration_dispatch(root, path)
    assert result.status == "validation_failed"
    assert result.findings[0].rule_id == "dispatch-readiness-socket-mismatch"


def test_dispatch_rejects_runner_binding_mismatch_with_valid_hash(tmp_path: Path) -> None:
    root, path = _dispatch_with_evidence(tmp_path)
    evidence_path = root / "adapters" / "evidence.json"
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    evidence["runner_id"] = "kimi_code"
    body = {key: value for key, value in evidence.items() if key != "evidence_id"}
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    evidence["evidence_id"] = f"sha256:{hashlib.sha256(canonical).hexdigest()}"
    evidence_path.write_text(json.dumps(evidence), encoding="utf-8")
    result = inspect_collaboration_dispatch(root, path)
    assert result.status == "validation_failed"
    assert result.findings[0].rule_id == "dispatch-readiness-runner-mismatch"


def test_dispatch_rejects_evaluation_before_evidence(tmp_path: Path) -> None:
    root, path = _dispatch_with_evidence(tmp_path)
    dispatch = json.loads((root / path).read_text(encoding="utf-8"))
    dispatch["evaluated_at"] = "2026-07-26T08:04:59Z"
    (root / path).write_text(json.dumps(dispatch), encoding="utf-8")
    result = inspect_collaboration_dispatch(root, path)
    assert result.status == "validation_failed"
    assert result.findings[0].rule_id == "dispatch-readiness-time-invalid"
