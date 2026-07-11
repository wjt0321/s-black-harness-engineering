"""Tests for orchestration route constraint flags.

These tests verify that `--preferred-adapter`, `--max-risk`,
`--require-background`, and `--require-artifacts` shape routing decisions and
are passed through to preflight. All commands exercised here are read-only.
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
        "description": "Constraint test adapter registry",
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
                "id": "webbridge",
                "name": "Web Bridge",
                "kind": "webbridge",
                "description": "External web requests.",
                "enabled": True,
                "capabilities": ["http_request"],
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
        ],
    }
    adapters_file.write_text(json.dumps(registry, ensure_ascii=False), encoding="utf-8")


def _run_route_preview_json(capsys, fake_root: Path, capability: str, *extra: str) -> tuple[int, dict[str, Any]]:
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


def _run_preflight_json(capsys, fake_root: Path, capability: str, *extra: str) -> tuple[int, dict[str, Any]]:
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


def test_default_route_unchanged(capsys, tmp_path):
    """Without constraint flags, routing selects the first source-order match and keeps legacy output."""
    fake_root = _setup_fake_root(tmp_path)
    _write_adapters(fake_root)

    code, result = _run_route_preview_json(capsys, fake_root, "light_coding")
    assert code == 0
    assert result["status"] == "pass"
    assert result["selected_adapter_id"] == "kimi-code-acp"
    assert result["capability"] == "light_coding"
    assert result["operation"] == "light_coding"
    assert result["risk_level"] == "external"
    # Default output must remain unchanged: no constraint-related fields.
    assert "routing_constraints" not in result["constraints"]
    assert "rejected_candidates" not in result["constraints"]
    assert "preferred_adapter_rejected" not in result["constraints"]
    assert result["routing_reason"] == (
        "Selected adapter 'kimi-code-acp' for capability 'light_coding' "
        "based on source order and capability match."
    )


def test_preferred_adapter_selected(capsys, tmp_path):
    """--preferred-adapter selects the requested adapter when it passes constraints."""
    fake_root = _setup_fake_root(tmp_path)
    _write_adapters(fake_root)

    code, result = _run_route_preview_json(
        capsys, fake_root, "light_coding", "--preferred-adapter", "claude-code-acp"
    )
    assert code == 0
    assert result["status"] == "pass"
    assert result["selected_adapter_id"] == "claude-code-acp"
    assert result["routing_reason"]
    assert "preferred" in result["routing_reason"].lower()
    constraints = result["constraints"]
    assert constraints["routing_constraints"]["preferred_adapter"] == "claude-code-acp"
    assert "preferred_adapter_rejected" not in constraints


def test_preferred_adapter_rejected_by_risk_then_fallback(capsys, tmp_path):
    """A preferred adapter rejected by --max-risk falls back to source order."""
    fake_root = _setup_fake_root(tmp_path)
    _write_adapters(fake_root)

    code, result = _run_route_preview_json(
        capsys,
        fake_root,
        "light_coding",
        "--preferred-adapter", "kimi-code-acp",
        "--max-risk", "local",
    )
    assert code == 0
    assert result["status"] == "pass"
    # omp-acp is the only local candidate; claude-code-acp is also external.
    assert result["selected_adapter_id"] == "omp-acp"
    assert result["risk_level"] == "local"
    constraints = result["constraints"]
    assert constraints["routing_constraints"]["preferred_adapter"] == "kimi-code-acp"
    assert constraints["preferred_adapter_rejected"]["adapter_id"] == "kimi-code-acp"
    rejected_ids = {c["adapter_id"] for c in constraints["rejected_candidates"]}
    assert "kimi-code-acp" in rejected_ids
    assert "claude-code-acp" in rejected_ids


def test_max_risk_filters_adapters(capsys, tmp_path):
    """--max-risk excludes adapters above the requested risk level."""
    fake_root = _setup_fake_root(tmp_path)
    _write_adapters(fake_root)

    code, result = _run_route_preview_json(capsys, fake_root, "light_coding", "--max-risk", "local")
    assert code == 0
    assert result["status"] == "pass"
    assert result["selected_adapter_id"] == "omp-acp"
    assert result["risk_level"] == "local"
    rejected = result["constraints"]["rejected_candidates"]
    rejected_ids = {c["adapter_id"] for c in rejected}
    assert rejected_ids == {"kimi-code-acp", "claude-code-acp"}
    for candidate in rejected:
        assert any("risk" in reason.lower() for reason in candidate["reasons"])


def test_require_background_filters(capsys, tmp_path):
    """--require-background keeps only adapters that support background execution."""
    fake_root = _setup_fake_root(tmp_path)
    _write_adapters(fake_root)

    code, result = _run_route_preview_json(
        capsys, fake_root, "light_coding", "--require-background"
    )
    assert code == 0
    assert result["status"] == "pass"
    assert result["selected_adapter_id"] == "kimi-code-acp"
    rejected = result["constraints"]["rejected_candidates"]
    rejected_ids = {c["adapter_id"] for c in rejected}
    assert rejected_ids == {"claude-code-acp", "omp-acp"}
    for candidate in rejected:
        assert any("background" in reason.lower() for reason in candidate["reasons"])


def test_require_artifacts_filters(capsys, tmp_path):
    """--require-artifacts keeps only tool/service adapters that support artifacts."""
    fake_root = _setup_fake_root(tmp_path)
    _write_adapters(fake_root)

    code, result = _run_route_preview_json(
        capsys, fake_root, "light_coding", "--require-artifacts"
    )
    assert code == 0
    assert result["status"] == "pass"
    assert result["selected_adapter_id"] == "omp-acp"
    rejected = result["constraints"]["rejected_candidates"]
    rejected_ids = {c["adapter_id"] for c in rejected}
    assert rejected_ids == {"kimi-code-acp", "claude-code-acp"}
    for candidate in rejected:
        assert any("artifact" in reason.lower() for reason in candidate["reasons"])


def test_all_candidates_blocked_by_constraints(capsys, tmp_path):
    """When no adapter satisfies the constraints, the result is blocked."""
    fake_root = _setup_fake_root(tmp_path)
    _write_adapters(fake_root)

    code, result = _run_route_preview_json(
        capsys, fake_root, "light_coding", "--max-risk", "local", "--require-background"
    )
    assert code == 2
    assert result["status"] == "blocked"
    assert result["selected_adapter_id"] is None
    assert result["routing_reason"]
    assert "rejected_candidates" in result["constraints"]
    rejected_ids = {c["adapter_id"] for c in result["constraints"]["rejected_candidates"]}
    assert rejected_ids == {"kimi-code-acp", "claude-code-acp", "omp-acp"}


def test_unknown_preferred_adapter_reported(capsys, tmp_path):
    """An unknown preferred adapter is reported without blocking source-order selection."""
    fake_root = _setup_fake_root(tmp_path)
    _write_adapters(fake_root)

    code, result = _run_route_preview_json(
        capsys, fake_root, "light_coding", "--preferred-adapter", "no-such-adapter"
    )
    assert code == 0
    assert result["status"] == "pass"
    assert result["selected_adapter_id"] == "kimi-code-acp"
    constraints = result["constraints"]
    assert constraints["preferred_adapter_rejected"]["adapter_id"] == "no-such-adapter"
    assert any(
        "capability" in reason.lower()
        for reason in constraints["preferred_adapter_rejected"]["reasons"]
    )


def test_preflight_passes_through_constraints(capsys, tmp_path):
    """Preflight applies the same constraints and aggregates routing with guardrails."""
    fake_root = _setup_fake_root(tmp_path)
    _write_adapters(fake_root)

    code, result = _run_preflight_json(
        capsys, fake_root, "light_coding", "--max-risk", "local"
    )
    assert code == 0
    assert result["status"] == "pass"
    assert result["route"]["selected_adapter_id"] == "omp-acp"
    assert result["route"]["risk_level"] == "local"
    assert result["effective_mode"] == "dry-run"
    assert result["requires_approval"] is False
    assert result["guardrail"]["status"] == "pass"
    assert result["constraints"]["routing_constraints"]["max_risk"] == "local"


def test_source_mutation_reflected(capsys, tmp_path):
    """Changes to the underlying registry are visible on the next read-only call."""
    fake_root = _setup_fake_root(tmp_path)
    _write_adapters(fake_root)

    code, result = _run_route_preview_json(capsys, fake_root, "light_coding", "--max-risk", "local")
    assert code == 0
    assert result["selected_adapter_id"] == "omp-acp"

    # Mutate source: raise omp-acp risk so no local candidate remains.
    data = json.loads((fake_root / "adapters" / "adapters.sample.json").read_text(encoding="utf-8"))
    for entry in data["adapters"]:
        if entry["id"] == "omp-acp":
            entry["risk_level"] = "external"
    (fake_root / "adapters" / "adapters.sample.json").write_text(
        json.dumps(data, ensure_ascii=False), encoding="utf-8"
    )

    code, result = _run_route_preview_json(capsys, fake_root, "light_coding", "--max-risk", "local")
    assert code == 2
    assert result["status"] == "blocked"
    assert result["selected_adapter_id"] is None


def test_no_files_written_by_read_only_commands(capsys, tmp_path):
    """Route preview and preflight do not mutate the project tree."""
    fake_root = _setup_fake_root(tmp_path)
    _write_adapters(fake_root)
    before_tree = sorted(str(p.relative_to(fake_root)) for p in fake_root.rglob("*"))
    before_bytes = (fake_root / "adapters" / "adapters.sample.json").read_bytes()

    main([
        "--root", str(fake_root),
        "orchestration", "route", "preview",
        "--capability", "light_coding",
        "--preferred-adapter", "claude-code-acp",
        "--max-risk", "external",
        "--json",
    ])
    main([
        "--root", str(fake_root),
        "orchestration", "preflight",
        "--capability", "light_coding",
        "--max-risk", "external",
        "--json",
    ])

    after_tree = sorted(str(p.relative_to(fake_root)) for p in fake_root.rglob("*"))
    after_bytes = (fake_root / "adapters" / "adapters.sample.json").read_bytes()
    assert after_tree == before_tree
    assert after_bytes == before_bytes


def test_default_preflight_unchanged(capsys, tmp_path):
    """Preflight without constraint flags keeps legacy route output shape."""
    fake_root = _setup_fake_root(tmp_path)
    _write_adapters(fake_root)

    code, result = _run_preflight_json(capsys, fake_root, "light_coding")
    assert code == 3  # external risk requires approval
    assert result["status"] == "needs_approval"
    route = result["route"]
    assert route["selected_adapter_id"] == "kimi-code-acp"
    assert "routing_constraints" not in route.get("constraints", {})
    assert "rejected_candidates" not in route.get("constraints", {})


def test_explicit_adapter_passes_constraints(capsys, tmp_path):
    """--adapter selects the explicit adapter when it passes constraints."""
    fake_root = _setup_fake_root(tmp_path)
    _write_adapters(fake_root)

    code, result = _run_route_preview_json(
        capsys, fake_root, "light_coding", "--adapter", "omp-acp", "--max-risk", "local"
    )
    assert code == 0
    assert result["status"] == "pass"
    assert result["selected_adapter_id"] == "omp-acp"
    assert result["risk_level"] == "local"


def test_explicit_adapter_rejected_by_max_risk(capsys, tmp_path):
    """--adapter blocked when it exceeds max-risk."""
    fake_root = _setup_fake_root(tmp_path)
    _write_adapters(fake_root)

    code, result = _run_route_preview_json(
        capsys, fake_root, "light_coding", "--adapter", "kimi-code-acp", "--max-risk", "local"
    )
    assert code == 2
    assert result["status"] == "blocked"
    assert result["selected_adapter_id"] is None
    assert "rejected_candidates" in result["constraints"]


def test_explicit_adapter_rejected_by_background(capsys, tmp_path):
    """--adapter blocked when it does not satisfy --require-background."""
    fake_root = _setup_fake_root(tmp_path)
    _write_adapters(fake_root)

    code, result = _run_route_preview_json(
        capsys, fake_root, "light_coding", "--adapter", "claude-code-acp", "--require-background"
    )
    assert code == 2
    assert result["status"] == "blocked"
    assert result["selected_adapter_id"] is None


def test_explicit_adapter_rejected_by_artifacts(capsys, tmp_path):
    """--adapter blocked when it does not satisfy --require-artifacts."""
    fake_root = _setup_fake_root(tmp_path)
    _write_adapters(fake_root)

    code, result = _run_route_preview_json(
        capsys, fake_root, "light_coding", "--adapter", "kimi-code-acp", "--require-artifacts"
    )
    assert code == 2
    assert result["status"] == "blocked"
    assert result["selected_adapter_id"] is None


def test_explicit_adapter_capability_mismatch(capsys, tmp_path):
    """--adapter blocked when it does not support the requested capability."""
    fake_root = _setup_fake_root(tmp_path)
    _write_adapters(fake_root)

    code, result = _run_route_preview_json(
        capsys, fake_root, "git_push", "--adapter", "kimi-code-acp"
    )
    assert code == 2
    assert result["status"] == "blocked"
    assert result["selected_adapter_id"] is None
