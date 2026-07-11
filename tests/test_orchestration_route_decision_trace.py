"""Tests for orchestration route decision trace (--explain).

These tests verify that `--explain` exposes a deterministic, compact trace of
the routing decision without leaking schemas or sensitive payloads, and that
default output remains unchanged.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agent_runtime.cli import main


ROOT = Path(__file__).resolve().parents[1]


def _setup_fake_root(tmp_path: Path) -> Path:
    """Create a fake project root with adapter registry and schema."""
    fake_root = tmp_path / "project"
    fake_root.mkdir()
    schema_src = ROOT / "adapters" / "execution-envelope.schema.json"
    schema_dst = fake_root / "adapters" / "execution-envelope.schema.json"
    schema_dst.parent.mkdir(parents=True, exist_ok=True)
    schema_dst.write_text(schema_src.read_text(encoding="utf-8"), encoding="utf-8")
    return fake_root


def _write_adapters(fake_root: Path) -> None:
    """Write a registry with multiple adapters sharing the light_coding capability."""
    adapters_file = fake_root / "adapters" / "adapters.sample.json"
    adapters_file.parent.mkdir(parents=True, exist_ok=True)
    registry = {
        "version": 1,
        "description": "Decision trace test adapter registry",
        "adapters": [
            {
                "id": "local-shell",
                "name": "Local Shell",
                "kind": "shell",
                "description": "Local shell commands.",
                "enabled": True,
                "capabilities": ["local_command", "git_status", "read_file"],
                "risk_level": "local",
                "requires_approval": False,
                "input_schema": {
                    "type": "object",
                    "required": ["command"],
                    "properties": {"command": {"type": "string"}},
                },
                "output_schema": {"type": "object"},
                "preflight_checks": ["policy_check"],
            },
            {
                "id": "kimi-code-acp",
                "name": "Kimi Code ACP",
                "kind": "acp_runner",
                "description": "Agent coding adapter with background support.",
                "enabled": True,
                "capabilities": ["light_coding", "background_task"],
                "risk_level": "external",
                "requires_approval": True,
                "input_schema": {
                    "type": "object",
                    "required": ["operation"],
                    "properties": {"operation": {"type": "string"}},
                },
                "output_schema": {"type": "object"},
                "preflight_checks": ["policy_check", "secret_scan", "user_approval"],
            },
            {
                "id": "claude-code-acp",
                "name": "Claude Code ACP",
                "kind": "acp_runner",
                "description": "Agent coding adapter without background support.",
                "enabled": True,
                "capabilities": ["light_coding"],
                "risk_level": "external",
                "requires_approval": True,
                "input_schema": {
                    "type": "object",
                    "required": ["operation"],
                    "properties": {"operation": {"type": "string"}},
                },
                "output_schema": {"type": "object"},
                "preflight_checks": ["policy_check", "secret_scan", "user_approval"],
            },
            {
                "id": "omp-acp",
                "name": "OMP ACP",
                "kind": "cli_tool",
                "description": "Local tool coding adapter.",
                "enabled": True,
                "capabilities": ["light_coding"],
                "risk_level": "local",
                "requires_approval": False,
                "input_schema": {
                    "type": "object",
                    "required": ["operation"],
                    "properties": {"operation": {"type": "string"}},
                },
                "output_schema": {"type": "object"},
                "preflight_checks": ["policy_check"],
            },
            {
                "id": "github-cli",
                "name": "GitHub CLI",
                "kind": "github",
                "description": "GitHub operations.",
                "enabled": True,
                "capabilities": ["git_push", "issue_ops"],
                "risk_level": "external",
                "requires_approval": True,
                "input_schema": {
                    "type": "object",
                    "required": ["operation"],
                    "properties": {"operation": {"type": "string"}},
                },
                "output_schema": {"type": "object"},
                "preflight_checks": ["policy_check", "secret_scan", "user_approval"],
            },
            {
                "id": "disabled-adapter",
                "name": "Disabled Adapter",
                "kind": "test",
                "description": "Should be ignored.",
                "enabled": False,
                "capabilities": ["light_coding"],
                "risk_level": "local",
                "requires_approval": False,
                "input_schema": {"type": "object"},
                "output_schema": {"type": "object"},
            },
        ],
    }
    adapters_file.write_text(json.dumps(registry, ensure_ascii=False), encoding="utf-8")


def _run_route_preview_json(
    capsys, fake_root: Path, capability: str, *extra: str
) -> tuple[int, dict[str, Any]]:
    """Run route preview with --json and return (code, parsed)."""
    code = main([
        "--root", str(fake_root),
        "orchestration", "route", "preview",
        "--capability", capability,
        *extra,
        "--json",
    ])
    captured = capsys.readouterr()
    return code, json.loads(captured.out)


def _run_preflight_json(
    capsys, fake_root: Path, capability: str, *extra: str
) -> tuple[int, dict[str, Any]]:
    """Run preflight with --json and return (code, parsed)."""
    code = main([
        "--root", str(fake_root),
        "orchestration", "preflight",
        "--capability", capability,
        *extra,
        "--json",
    ])
    captured = capsys.readouterr()
    return code, json.loads(captured.out)


def test_default_route_no_trace(capsys, tmp_path):
    """Without --explain, route preview output must not contain decision_trace."""
    fake_root = _setup_fake_root(tmp_path)
    _write_adapters(fake_root)

    code, result = _run_route_preview_json(capsys, fake_root, "light_coding")
    assert code == 0
    assert "decision_trace" not in result


def test_default_preflight_no_trace(capsys, tmp_path):
    """Without --explain, preflight route summary must not contain decision_trace."""
    fake_root = _setup_fake_root(tmp_path)
    _write_adapters(fake_root)

    code, result = _run_preflight_json(
        capsys, fake_root, "light_coding", "--max-risk", "local"
    )
    assert code == 0
    assert "decision_trace" not in result["route"]


def test_explain_route_trace_structure(capsys, tmp_path):
    """--explain exposes matched, rejected, eligible, selected, and fallback."""
    fake_root = _setup_fake_root(tmp_path)
    _write_adapters(fake_root)

    code, result = _run_route_preview_json(
        capsys, fake_root, "light_coding", "--explain"
    )
    assert code == 0
    trace = result["decision_trace"]
    assert trace["capability"] == "light_coding"

    matched_ids = {c["adapter_id"] for c in trace["matched_candidates"]}
    assert matched_ids == {"kimi-code-acp", "claude-code-acp", "omp-acp"}
    for c in trace["matched_candidates"]:
        assert "input_schema" not in c
        assert "declares capability 'light_coding' and is enabled" in c["reason"]
        assert isinstance(c["source_index"], int)

    assert trace["rejected_candidates"] == []
    eligible_ids = {c["adapter_id"] for c in trace["eligible_candidates"]}
    assert eligible_ids == matched_ids

    assert trace["selected"]["adapter_id"] == "kimi-code-acp"
    assert "source order" in trace["selected"]["reason"]

    fallback_ids = {c["adapter_id"] for c in trace["fallback_candidates"]}
    assert fallback_ids == {"claude-code-acp", "omp-acp"}


def test_explain_rejected_by_max_risk(capsys, tmp_path):
    """Trace records the exact constraint that rejected each candidate."""
    fake_root = _setup_fake_root(tmp_path)
    _write_adapters(fake_root)

    code, result = _run_route_preview_json(
        capsys, fake_root, "light_coding", "--max-risk", "local", "--explain"
    )
    assert code == 0
    trace = result["decision_trace"]

    rejected = {c["adapter_id"]: c["reasons"] for c in trace["rejected_candidates"]}
    assert "kimi-code-acp" in rejected
    assert any("risk" in reason.lower() for reason in rejected["kimi-code-acp"])
    assert "claude-code-acp" in rejected

    eligible_ids = {c["adapter_id"] for c in trace["eligible_candidates"]}
    assert eligible_ids == {"omp-acp"}
    assert trace["selected"]["adapter_id"] == "omp-acp"


def test_explain_preferred_adapter_rejected_then_fallback(capsys, tmp_path):
    """Preferred adapter appears in rejected list when it fails constraints."""
    fake_root = _setup_fake_root(tmp_path)
    _write_adapters(fake_root)

    code, result = _run_route_preview_json(
        capsys,
        fake_root,
        "light_coding",
        "--preferred-adapter", "kimi-code-acp",
        "--max-risk", "local",
        "--explain",
    )
    assert code == 0
    trace = result["decision_trace"]
    assert trace["selected"]["adapter_id"] == "omp-acp"
    assert result["constraints"]["preferred_adapter_rejected"]["adapter_id"] == "kimi-code-acp"


def test_explain_explicit_adapter_blocked(capsys, tmp_path):
    """Explicit --adapter rejected by constraints leaves selected empty in trace."""
    fake_root = _setup_fake_root(tmp_path)
    _write_adapters(fake_root)

    code, result = _run_route_preview_json(
        capsys,
        fake_root,
        "light_coding",
        "--adapter", "kimi-code-acp",
        "--max-risk", "local",
        "--explain",
    )
    assert code == 2
    trace = result["decision_trace"]
    assert trace["selected"]["adapter_id"] == ""
    assert "rejected" in trace["selected"]["reason"].lower()


def test_explain_no_matching_capability(capsys, tmp_path):
    """Trace is present but empty when no adapter supports the capability."""
    fake_root = _setup_fake_root(tmp_path)
    _write_adapters(fake_root)

    code, result = _run_route_preview_json(
        capsys, fake_root, "unknown_capability", "--explain"
    )
    assert code != 0
    trace = result["decision_trace"]
    assert trace["capability"] == "unknown_capability"
    assert trace["matched_candidates"] == []
    assert trace["eligible_candidates"] == []
    assert trace["selected"]["adapter_id"] == ""


def test_explain_preflight_reuses_route_trace(capsys, tmp_path):
    """Preflight --explain exposes the same decision_trace as route preview."""
    fake_root = _setup_fake_root(tmp_path)
    _write_adapters(fake_root)

    _, route_result = _run_route_preview_json(
        capsys, fake_root, "light_coding", "--max-risk", "external", "--explain"
    )
    _, preflight_result = _run_preflight_json(
        capsys, fake_root, "light_coding", "--max-risk", "external", "--explain"
    )

    assert route_result["decision_trace"] == preflight_result["route"]["decision_trace"]


def test_explain_source_mutation_reflected(capsys, tmp_path):
    """Modifying the source registry is reflected in the next trace."""
    fake_root = _setup_fake_root(tmp_path)
    _write_adapters(fake_root)

    code, result = _run_route_preview_json(
        capsys, fake_root, "light_coding", "--explain"
    )
    assert code == 0
    before_ids = {c["adapter_id"] for c in result["decision_trace"]["matched_candidates"]}
    assert "omp-acp" in before_ids

    data = json.loads((fake_root / "adapters" / "adapters.sample.json").read_text(encoding="utf-8"))
    data["adapters"] = [a for a in data["adapters"] if a["id"] != "omp-acp"]
    (fake_root / "adapters" / "adapters.sample.json").write_text(
        json.dumps(data, ensure_ascii=False), encoding="utf-8"
    )

    code, result = _run_route_preview_json(
        capsys, fake_root, "light_coding", "--explain"
    )
    assert code == 0
    after_ids = {c["adapter_id"] for c in result["decision_trace"]["matched_candidates"]}
    assert "omp-acp" not in after_ids


def test_explain_no_schema_dump(capsys, tmp_path):
    """Trace must not contain full input/output schemas or payload."""
    fake_root = _setup_fake_root(tmp_path)
    _write_adapters(fake_root)

    code, result = _run_route_preview_json(
        capsys, fake_root, "light_coding", "--explain"
    )
    assert code == 0
    trace_json = json.dumps(result["decision_trace"])
    assert "input_schema" not in trace_json
    assert "output_schema" not in trace_json
    assert "properties" not in trace_json


def test_explain_disabled_adapter_not_in_trace(capsys, tmp_path):
    """Disabled adapters must not appear in matched candidates."""
    fake_root = _setup_fake_root(tmp_path)
    _write_adapters(fake_root)

    code, result = _run_route_preview_json(
        capsys, fake_root, "light_coding", "--explain"
    )
    assert code == 0
    matched_ids = {c["adapter_id"] for c in result["decision_trace"]["matched_candidates"]}
    assert "disabled-adapter" not in matched_ids


def test_explain_readonly(capsys, tmp_path):
    """Explain commands do not mutate the project tree."""
    fake_root = _setup_fake_root(tmp_path)
    _write_adapters(fake_root)
    before_tree = sorted(str(p.relative_to(fake_root)) for p in fake_root.rglob("*"))
    before_bytes = (fake_root / "adapters" / "adapters.sample.json").read_bytes()

    main([
        "--root", str(fake_root),
        "orchestration", "route", "preview",
        "--capability", "light_coding",
        "--explain",
        "--json",
    ])
    main([
        "--root", str(fake_root),
        "orchestration", "preflight",
        "--capability", "light_coding",
        "--explain",
        "--json",
    ])

    after_tree = sorted(str(p.relative_to(fake_root)) for p in fake_root.rglob("*"))
    after_bytes = (fake_root / "adapters" / "adapters.sample.json").read_bytes()
    assert after_tree == before_tree
    assert after_bytes == before_bytes


def test_explain_human_readable_smoke(capsys, tmp_path):
    """Human-readable --explain output contains DECISION TRACE section."""
    fake_root = _setup_fake_root(tmp_path)
    _write_adapters(fake_root)

    code = main([
        "--root", str(fake_root),
        "orchestration", "route", "preview",
        "--capability", "light_coding",
        "--explain",
    ])
    captured = capsys.readouterr()
    assert code == 0
    assert "DECISION TRACE" in captured.out
    assert "matched candidates:" in captured.out
    assert "kimi-code-acp" in captured.out
