"""Tests for bounded ACP runner-list readiness evidence collection."""

from __future__ import annotations

import json
from pathlib import Path

from agent_runtime.orchestration_acp_readiness import collect_acp_readiness

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = "adapters/acp-runner-state-snapshot.sample.json"
EVALUATED = "2026-07-26T08:05:00Z"


def test_collects_available_but_insufficient_evidence() -> None:
    payload = collect_acp_readiness(ROOT, "omp-acp", SNAPSHOT, EVALUATED, 600).to_dict()
    assert payload["status"] == "pass"
    evidence = payload["evidence"]
    assert evidence["runner_id"] == "omp"
    assert evidence["status"] == "available"
    assert evidence["level"] == "runner_listed"
    assert evidence["session_state"] == "closed"
    assert evidence["sufficient_for_dispatch"] is False
    assert payload["guarantees"]["opens_session"] is False
    assert payload["guarantees"]["invokes_model"] is False
    assert payload["guarantees"]["grants_execution_authority"] is False


def test_collection_is_deterministic() -> None:
    first = collect_acp_readiness(ROOT, "kimi-code-acp", SNAPSHOT, EVALUATED).to_dict()
    second = collect_acp_readiness(ROOT, "kimi-code-acp", SNAPSHOT, EVALUATED).to_dict()
    assert first == second
    assert first["evidence"]["evidence_id"].startswith("sha256:")


def test_expired_snapshot_becomes_unknown() -> None:
    payload = collect_acp_readiness(
        ROOT, "claude-code-acp", SNAPSHOT, "2026-07-26T08:20:01Z", 900
    ).to_dict()
    assert payload["status"] == "pass"
    assert payload["evidence"]["status"] == "unknown"
    assert payload["evidence"]["level"] == "runner_listed"
    assert payload["evidence"]["sufficient_for_dispatch"] is False


def _snapshot(tmp_path: Path, runners: list[dict[str, str]]) -> tuple[Path, str]:
    root = tmp_path / "project"
    (root / "adapters").mkdir(parents=True)
    for name in (
        "adapter.schema.json",
        "adapters.sample.json",
        "acp-runner-bindings.schema.json",
        "acp-runner-bindings.sample.json",
        "acp-runner-state-snapshot.schema.json",
        "acp-readiness-evidence-v2.schema.json",
    ):
        (root / "adapters" / name).write_bytes((ROOT / "adapters" / name).read_bytes())
    data = json.loads((ROOT / SNAPSHOT).read_text(encoding="utf-8"))
    data["runners"] = runners
    (root / "adapters" / "snapshot.json").write_text(json.dumps(data), encoding="utf-8")
    return root, "adapters/snapshot.json"


def test_missing_bound_runner_becomes_unknown(tmp_path: Path) -> None:
    root, snapshot = _snapshot(tmp_path, [{"runner_id": "kimi_code", "session_state": "closed"}])
    payload = collect_acp_readiness(root, "omp-acp", snapshot, EVALUATED).to_dict()
    assert payload["status"] == "pass"
    assert payload["evidence"]["status"] == "unknown"
    assert payload["evidence"]["level"] == "runner_missing"


def test_rejects_non_acp_socket() -> None:
    result = collect_acp_readiness(ROOT, "pi-cli", SNAPSHOT, EVALUATED)
    assert result.status == "validation_failed"
    assert result.findings[0].rule_id == "readiness-socket-ineligible"


def test_rejects_snapshot_path_escape() -> None:
    result = collect_acp_readiness(ROOT, "omp-acp", "../snapshot.json", EVALUATED)
    assert result.status == "validation_failed"
    assert result.findings[0].rule_id == "readiness-snapshot-invalid"


def test_rejects_invalid_ttl() -> None:
    result = collect_acp_readiness(ROOT, "omp-acp", SNAPSHOT, EVALUATED, 901)
    assert result.status == "validation_failed"
    assert result.findings[0].rule_id == "readiness-ttl-invalid"


def test_rejects_evaluation_before_observation() -> None:
    result = collect_acp_readiness(
        ROOT, "omp-acp", SNAPSHOT, "2026-07-26T07:59:59Z"
    )
    assert result.status == "validation_failed"
    assert result.findings[0].rule_id == "readiness-time-invalid"
