"""Tests for orchestration routing decision snapshot.

These tests verify that `orchestration route snapshot` and
`orchestration preflight --snapshot` produce deterministic, compact,
value-safe control-plane state projections from real routing/preflight
results without writing ledgers or executing adapters.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agent_runtime.cli import main
from agent_runtime.orchestration_routing_snapshot import (
    SCHEMA_VERSION,
    _canonical_json,
    _compute_snapshot_id,
)


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
        "description": "Snapshot test adapter registry",
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
        ],
    }
    adapters_file.write_text(json.dumps(registry, ensure_ascii=False), encoding="utf-8")


def _write_policy(fake_root: Path) -> None:
    """Write a minimal policy with one blocking command rule."""
    policies_dir = fake_root / "policies"
    policies_dir.mkdir(parents=True, exist_ok=True)
    policy = {
        "version": 1,
        "name": "test-policy",
        "command_rules": [
            {
                "id": "block-rm",
                "title": "Block recursive delete",
                "severity": "block",
                "action": "deny",
                "regex": r"\brm\s+-rf\b",
                "enabled": True,
                "message": "Recursive delete is blocked by test policy.",
            }
        ],
    }
    (policies_dir / "test.sample.policy.json").write_text(
        json.dumps(policy, ensure_ascii=False), encoding="utf-8"
    )


def _run_route_snapshot_json(
    capsys, fake_root: Path, capability: str, *extra: str
) -> tuple[int, dict[str, Any]]:
    """Run route snapshot with --json and return (code, parsed)."""
    code = main([
        "--root", str(fake_root),
        "orchestration", "route", "snapshot",
        "--capability", capability,
        *extra,
        "--json",
    ])
    captured = capsys.readouterr()
    return code, json.loads(captured.out)


def _run_preflight_snapshot_json(
    capsys, fake_root: Path, capability: str, *extra: str
) -> tuple[int, dict[str, Any]]:
    """Run preflight with --snapshot --json and return (code, parsed)."""
    code = main([
        "--root", str(fake_root),
        "orchestration", "preflight",
        "--capability", capability,
        "--snapshot",
        *extra,
        "--json",
    ])
    captured = capsys.readouterr()
    return code, json.loads(captured.out)


def test_route_snapshot_structure(capsys, tmp_path):
    """Route snapshot has stable schema, deterministic id, and routing layer."""
    fake_root = _setup_fake_root(tmp_path)
    _write_adapters(fake_root)

    code, result = _run_route_snapshot_json(capsys, fake_root, "light_coding")
    assert code == 0
    assert result["schema_version"] == "control-plane/routing-decision/v1"
    assert result["snapshot_id"].startswith("sha256:")
    assert result["status"] == "pass"

    routing = result["routing"]
    assert routing["requested_capability"] == "light_coding"
    assert routing["selected_adapter_id"] == "kimi-code-acp"
    assert routing["operation"] == "light_coding"
    assert routing["risk_level"] == "external"
    assert routing["requires_approval"] is True
    assert routing["requires_dry_run"] is True
    assert routing["routing_reason"]
    assert "omp-acp" in routing["fallback_adapter_ids"]

    assert result["constraints"]["adapter_kind"] == "acp_runner"
    assert result["source"] == {"task_id": None, "request_id": None}
    assert "guardrail" not in result


def test_route_snapshot_deterministic_json(capsys, tmp_path):
    """Same input against unchanged project produces byte-equivalent JSON."""
    fake_root = _setup_fake_root(tmp_path)
    _write_adapters(fake_root)

    _, first = _run_route_snapshot_json(capsys, fake_root, "light_coding")
    _, second = _run_route_snapshot_json(capsys, fake_root, "light_coding")

    first_bytes = json.dumps(first, ensure_ascii=False, sort_keys=True).encode("utf-8")
    second_bytes = json.dumps(second, ensure_ascii=False, sort_keys=True).encode("utf-8")
    assert first_bytes == second_bytes
    assert first["snapshot_id"] == second["snapshot_id"]


def test_preflight_snapshot_deterministic_json(capsys, tmp_path):
    """Preflight snapshot is deterministic for the same inputs."""
    fake_root = _setup_fake_root(tmp_path)
    _write_adapters(fake_root)

    _, first = _run_preflight_snapshot_json(
        capsys, fake_root, "read_file", "--adapter", "local-shell", "--operation", "read_file", "--target", "docs/06-adapter-layer.md"
    )
    _, second = _run_preflight_snapshot_json(
        capsys, fake_root, "read_file", "--adapter", "local-shell", "--operation", "read_file", "--target", "docs/06-adapter-layer.md"
    )

    first_bytes = json.dumps(first, ensure_ascii=False, sort_keys=True).encode("utf-8")
    second_bytes = json.dumps(second, ensure_ascii=False, sort_keys=True).encode("utf-8")
    assert first_bytes == second_bytes


def test_preflight_snapshot_includes_guardrail(capsys, tmp_path):
    """Preflight snapshot includes a layered, safe guardrail summary."""
    fake_root = _setup_fake_root(tmp_path)
    _write_adapters(fake_root)

    code, result = _run_preflight_snapshot_json(
        capsys, fake_root, "read_file", "--adapter", "local-shell", "--operation", "read_file", "--target", "docs/06-adapter-layer.md"
    )
    assert code == 0
    assert result["status"] == "pass"
    guardrail = result["guardrail"]
    assert guardrail["status"] == "pass"
    assert guardrail["finding_count"] == 0
    assert guardrail["blocking_rule_ids"] == []


def test_preflight_snapshot_guardrail_blocked(capsys, tmp_path):
    """Blocked guardrail is captured in the snapshot with rule ids only."""
    fake_root = _setup_fake_root(tmp_path)
    _write_adapters(fake_root)
    _write_policy(fake_root)

    code, result = _run_preflight_snapshot_json(
        capsys, fake_root, "local_command", "--adapter", "local-shell", "--operation", "rm -rf /tmp/x", "--target", "/tmp/x"
    )
    assert code == 2
    assert result["status"] == "blocked"
    guardrail = result["guardrail"]
    assert guardrail["status"] == "blocked"
    assert guardrail["finding_count"] >= 1
    assert "block-rm" in guardrail["blocking_rule_ids"]
    # Messages must not leak into the snapshot.
    snapshot_json = json.dumps(result)
    assert "Recursive delete" not in snapshot_json


def test_route_snapshot_blocked_status(capsys, tmp_path):
    """Blocked routing produces a valid snapshot with empty selected adapter."""
    fake_root = _setup_fake_root(tmp_path)
    _write_adapters(fake_root)

    code, result = _run_route_snapshot_json(
        capsys, fake_root, "git_push", "--adapter", "local-shell"
    )
    assert code == 2
    assert result["status"] == "blocked"
    assert result["routing"]["selected_adapter_id"] is None
    assert "local-shell" in result["routing"]["routing_reason"]


def test_route_snapshot_needs_input_status(capsys, tmp_path):
    """Unknown capability produces needs_input snapshot."""
    fake_root = _setup_fake_root(tmp_path)
    _write_adapters(fake_root)

    code, result = _run_route_snapshot_json(capsys, fake_root, "unknown_capability")
    assert code == 4
    assert result["status"] == "needs_input"
    assert result["routing"]["selected_adapter_id"] is None


def test_route_snapshot_explain_includes_trace(capsys, tmp_path):
    """--explain adds the decision trace to the snapshot."""
    fake_root = _setup_fake_root(tmp_path)
    _write_adapters(fake_root)

    code, result = _run_route_snapshot_json(
        capsys, fake_root, "light_coding", "--explain"
    )
    assert code == 0
    assert "trace" in result
    assert result["trace"]["capability"] == "light_coding"
    assert result["trace"]["selected"]["adapter_id"] == "kimi-code-acp"


def test_route_snapshot_default_no_trace(capsys, tmp_path):
    """Without --explain, snapshot has no trace field."""
    fake_root = _setup_fake_root(tmp_path)
    _write_adapters(fake_root)

    code, result = _run_route_snapshot_json(capsys, fake_root, "light_coding")
    assert code == 0
    assert "trace" not in result


def test_preflight_snapshot_routing_consistent_with_route(capsys, tmp_path):
    """Preflight snapshot routing layer matches route snapshot for same inputs."""
    fake_root = _setup_fake_root(tmp_path)
    _write_adapters(fake_root)

    _, route = _run_route_snapshot_json(
        capsys, fake_root, "read_file", "--adapter", "local-shell"
    )
    _, preflight = _run_preflight_snapshot_json(
        capsys, fake_root, "read_file", "--adapter", "local-shell", "--operation", "read_file", "--target", "docs/06-adapter-layer.md"
    )

    assert route["routing"]["selected_adapter_id"] == preflight["routing"]["selected_adapter_id"]
    assert route["routing"]["risk_level"] == preflight["routing"]["risk_level"]


def test_snapshot_no_sensitive_payload(capsys, tmp_path):
    """Snapshot JSON does not contain full schemas, inputs, or finding messages."""
    fake_root = _setup_fake_root(tmp_path)
    _write_adapters(fake_root)

    code, result = _run_route_snapshot_json(
        capsys, fake_root, "light_coding", "--explain"
    )
    assert code == 0
    snapshot_json = json.dumps(result)
    assert "input_schema" not in snapshot_json
    assert "output_schema" not in snapshot_json
    assert "properties" not in snapshot_json


def test_snapshot_source_mutation_changes_id(capsys, tmp_path):
    """Modifying the source registry changes the snapshot id and content."""
    fake_root = _setup_fake_root(tmp_path)
    _write_adapters(fake_root)

    _, first = _run_route_snapshot_json(capsys, fake_root, "light_coding")
    first_id = first["snapshot_id"]

    data = json.loads((fake_root / "adapters" / "adapters.sample.json").read_text(encoding="utf-8"))
    data["adapters"] = [a for a in data["adapters"] if a["id"] != "omp-acp"]
    (fake_root / "adapters" / "adapters.sample.json").write_text(
        json.dumps(data, ensure_ascii=False), encoding="utf-8"
    )

    _, second = _run_route_snapshot_json(capsys, fake_root, "light_coding")
    assert second["snapshot_id"] != first_id
    assert "omp-acp" not in second["routing"]["fallback_adapter_ids"]


def test_snapshot_readonly(capsys, tmp_path):
    """Snapshot commands do not mutate the project tree."""
    fake_root = _setup_fake_root(tmp_path)
    _write_adapters(fake_root)
    before_tree = sorted(str(p.relative_to(fake_root)) for p in fake_root.rglob("*"))
    before_bytes = (fake_root / "adapters" / "adapters.sample.json").read_bytes()

    main([
        "--root", str(fake_root),
        "orchestration", "route", "snapshot",
        "--capability", "light_coding",
        "--explain",
        "--json",
    ])
    main([
        "--root", str(fake_root),
        "orchestration", "preflight",
        "--capability", "read_file",
        "--adapter", "local-shell",
        "--operation", "read_file",
        "--target", "docs/06-adapter-layer.md",
        "--snapshot",
        "--json",
    ])

    after_tree = sorted(str(p.relative_to(fake_root)) for p in fake_root.rglob("*"))
    after_bytes = (fake_root / "adapters" / "adapters.sample.json").read_bytes()
    assert after_tree == before_tree
    assert after_bytes == before_bytes


def test_route_snapshot_human_readable_smoke(capsys, tmp_path):
    """Human-readable route snapshot output is compact and informative."""
    fake_root = _setup_fake_root(tmp_path)
    _write_adapters(fake_root)

    code = main([
        "--root", str(fake_root),
        "orchestration", "route", "snapshot",
        "--capability", "light_coding",
    ])
    captured = capsys.readouterr()
    assert code == 0
    assert "ROUTING DECISION SNAPSHOT" in captured.out
    assert "snapshot_id=sha256:" in captured.out
    assert "kimi-code-acp" in captured.out


def test_route_snapshot_source_identity(capsys, tmp_path):
    """task_id and request_id are preserved in the snapshot source."""
    fake_root = _setup_fake_root(tmp_path)
    _write_adapters(fake_root)

    code, result = _run_route_snapshot_json(
        capsys, fake_root, "light_coding", "--task-id", "task-001", "--request-id", "req-001"
    )
    assert code == 0
    assert result["source"] == {"task_id": "task-001", "request_id": "req-001"}


def test_preflight_snapshot_default_preflight_output_unchanged(capsys, tmp_path):
    """Without --snapshot, preflight still produces the legacy output shape."""
    fake_root = _setup_fake_root(tmp_path)
    _write_adapters(fake_root)

    code = main([
        "--root", str(fake_root),
        "orchestration", "preflight",
        "--capability", "read_file",
        "--adapter", "local-shell",
        "--operation", "read_file",
        "--target", "docs/06-adapter-layer.md",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 0
    result = json.loads(captured.out)
    assert "schema_version" not in result
    assert "snapshot_id" not in result
    assert result["route"]["selected_adapter_id"] == "local-shell"



def test_route_snapshot_routing_status(capsys, tmp_path):
    """routing object carries its own status from the route result."""
    fake_root = _setup_fake_root(tmp_path)
    _write_adapters(fake_root)

    code, result = _run_route_snapshot_json(capsys, fake_root, "light_coding")
    assert code == 0
    assert result["routing"]["status"] == "pass"
    assert result["status"] == "pass"


def test_route_snapshot_blocked_routing_status(capsys, tmp_path):
    """When routing is blocked, routing.status is blocked."""
    fake_root = _setup_fake_root(tmp_path)
    _write_adapters(fake_root)

    code, result = _run_route_snapshot_json(
        capsys, fake_root, "git_push", "--adapter", "local-shell"
    )
    assert code == 2
    assert result["routing"]["status"] == "blocked"
    assert result["status"] == "blocked"


def test_preflight_snapshot_layered_statuses(capsys, tmp_path):
    """routing.status, guardrail.status, and top-level status are layered correctly."""
    fake_root = _setup_fake_root(tmp_path)
    _write_adapters(fake_root)

    # routing passes, guardrail needs approval (external risk).
    code, result = _run_preflight_snapshot_json(
        capsys, fake_root, "git_push", "--operation", "git_push", "--target", "origin/main"
    )
    assert code == 3
    assert result["routing"]["status"] == "pass"
    assert result["guardrail"]["status"] == "needs_approval"
    assert result["status"] == "needs_approval"


def test_preflight_snapshot_layered_blocked(capsys, tmp_path):
    """routing passes but guardrail blocks: statuses are layered."""
    fake_root = _setup_fake_root(tmp_path)
    _write_adapters(fake_root)
    _write_policy(fake_root)

    code, result = _run_preflight_snapshot_json(
        capsys, fake_root, "local_command", "--adapter", "local-shell", "--operation", "rm -rf /tmp/x", "--target", "/tmp/x"
    )
    assert code == 2
    assert result["routing"]["status"] == "pass"
    assert result["guardrail"]["status"] == "blocked"
    assert result["status"] == "blocked"


def test_route_snapshot_id_hashes_final_payload(capsys, tmp_path):
    """snapshot_id is the sha256 of the canonical payload excluding snapshot_id."""
    fake_root = _setup_fake_root(tmp_path)
    _write_adapters(fake_root)

    _, result = _run_route_snapshot_json(capsys, fake_root, "light_coding", "--explain")

    payload = {
        "schema_version": result["schema_version"],
        "status": result["status"],
        "routing": result["routing"],
        "constraints": result["constraints"],
        "source": result["source"],
        "trace": result["trace"],
    }
    expected_id = _compute_snapshot_id(payload)
    assert result["snapshot_id"] == expected_id


def test_preflight_snapshot_id_hashes_final_payload(capsys, tmp_path):
    """preflight snapshot_id hashes the final payload without any nested snapshot_id."""
    fake_root = _setup_fake_root(tmp_path)
    _write_adapters(fake_root)

    _, result = _run_preflight_snapshot_json(
        capsys, fake_root, "read_file", "--adapter", "local-shell", "--operation", "read_file", "--target", "docs/06-adapter-layer.md"
    )

    payload = {
        "schema_version": result["schema_version"],
        "status": result["status"],
        "routing": result["routing"],
        "constraints": result["constraints"],
        "source": result["source"],
        "guardrail": result["guardrail"],
    }
    expected_id = _compute_snapshot_id(payload)
    assert result["snapshot_id"] == expected_id
    # Ensure no intermediate snapshot_id leaked into the JSON.
    assert json.dumps(result).count("sha256:") == 1
