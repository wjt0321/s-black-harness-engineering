"""Consistency tests across orchestration adapter list, route preview, and preflight.

These tests verify that the three read-only orchestration commands all consume
and reflect the same source-backed adapter registry data.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agent_runtime.cli import main


ROOT = Path(__file__).resolve().parents[1]


def _copy_file(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")


def _setup_fake_root(tmp_path: Path, adapters_data: dict[str, Any] | None = None) -> Path:
    """Create a fake project root with adapter registry and schema."""
    fake_root = tmp_path / "project"
    fake_root.mkdir()
    _copy_file(ROOT / "adapters" / "adapter.schema.json", fake_root / "adapters" / "adapter.schema.json")
    if adapters_data is None:
        _copy_file(ROOT / "adapters" / "adapters.sample.json", fake_root / "adapters" / "adapters.sample.json")
    else:
        (fake_root / "adapters" / "adapters.sample.json").write_text(
            json.dumps(adapters_data, ensure_ascii=False), encoding="utf-8"
        )
    return fake_root


def _load_source(fake_root: Path) -> dict[str, Any]:
    return json.loads((fake_root / "adapters" / "adapters.sample.json").read_text(encoding="utf-8"))


def _run_json(capsys, fake_root: Path, args: list[str]) -> tuple[int, dict[str, Any]]:
    code = main(["--root", str(fake_root), *args, "--json"])
    captured = capsys.readouterr()
    return code, json.loads(captured.out)


def _minimal_registry() -> dict[str, Any]:
    return {
        "version": 1,
        "description": "Consistency test registry",
        "adapters": [
            {
                "id": "local-shell",
                "name": "Local Shell",
                "kind": "shell",
                "description": "Local shell commands.",
                "enabled": True,
                "capabilities": ["local_command", "read_file"],
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
                "kind": "shell",
                "description": "Should be ignored by routing.",
                "enabled": False,
                "capabilities": ["local_command"],
                "risk_level": "local",
                "requires_approval": False,
                "input_schema": {"type": "object"},
                "output_schema": {"type": "object"},
            },
        ],
    }


def test_adapter_list_matches_source_ids_capabilities_and_risk(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path, _minimal_registry())
    source = _load_source(fake_root)
    source_entries = {entry["id"]: entry for entry in source["adapters"]}

    code, result = _run_json(capsys, fake_root, ["orchestration", "adapter", "list"])
    assert code == 0
    assert result["status"] == "pass"

    listed = {a["adapter_id"]: a for a in result["adapters"]}
    assert set(listed.keys()) == set(source_entries.keys())
    for adapter_id, summary in listed.items():
        entry = source_entries[adapter_id]
        assert summary["risk_level"] == entry["risk_level"]
        assert summary["capability_count"] == len(entry["capabilities"])
        assert summary["enabled"] == entry.get("enabled", True)


def test_route_preview_selected_adapter_matches_source(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path, _minimal_registry())
    source = _load_source(fake_root)
    source_entries = {entry["id"]: entry for entry in source["adapters"]}

    for capability, expected_adapter in [
        ("git_push", "github-cli"),
        ("local_command", "local-shell"),
    ]:
        code, result = _run_json(
            capsys, fake_root, ["orchestration", "route", "preview", "--capability", capability]
        )
        assert code == 0
        assert result["status"] == "pass"
        assert result["selected_adapter_id"] == expected_adapter
        entry = source_entries[expected_adapter]
        assert result["risk_level"] == entry["risk_level"]
        assert result["capability"] == capability
        assert capability in entry["capabilities"]


def test_preflight_route_summary_matches_source(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path, _minimal_registry())
    source = _load_source(fake_root)
    source_entries = {entry["id"]: entry for entry in source["adapters"]}

    code, result = _run_json(
        capsys,
        fake_root,
        [
            "orchestration",
            "preflight",
            "--capability",
            "git_push",
            "--operation",
            "git_push",
            "--target",
            "origin/main",
        ],
    )
    assert code == 3  # external capability requires approval
    assert result["status"] == "needs_approval"
    route = result["route"]
    assert route["selected_adapter_id"] == "github-cli"
    entry = source_entries["github-cli"]
    assert route["risk_level"] == entry["risk_level"]
    assert route["capability"] == "git_push"
    assert route["operation"] == "git_push"


def test_mutation_reflected_in_all_three_commands(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path, _minimal_registry())

    code, initial_list = _run_json(capsys, fake_root, ["orchestration", "adapter", "list"])
    assert code == 0
    assert "custom-adapter" not in {a["adapter_id"] for a in initial_list["adapters"]}

    data = _load_source(fake_root)
    data["adapters"].append({
        "id": "custom-adapter",
        "name": "Custom Adapter",
        "kind": "shell",
        "description": "Added during test.",
        "enabled": True,
        "capabilities": ["custom.capability"],
        "risk_level": "local",
        "requires_approval": False,
        "input_schema": {
            "type": "object",
            "required": ["command"],
            "properties": {"command": {"type": "string"}},
        },
        "output_schema": {"type": "object"},
    })
    (fake_root / "adapters" / "adapters.sample.json").write_text(
        json.dumps(data, ensure_ascii=False), encoding="utf-8"
    )

    code, mutated_list = _run_json(capsys, fake_root, ["orchestration", "adapter", "list"])
    assert code == 0
    ids = {a["adapter_id"] for a in mutated_list["adapters"]}
    assert "custom-adapter" in ids
    custom_summary = next(a for a in mutated_list["adapters"] if a["adapter_id"] == "custom-adapter")
    assert custom_summary["risk_level"] == "local"
    assert custom_summary["capability_count"] == 1

    code, route = _run_json(
        capsys,
        fake_root,
        ["orchestration", "route", "preview", "--capability", "custom.capability"],
    )
    assert code == 0
    assert route["status"] == "pass"
    assert route["selected_adapter_id"] == "custom-adapter"
    assert route["risk_level"] == "local"

    code, preflight = _run_json(
        capsys,
        fake_root,
        [
            "orchestration",
            "preflight",
            "--capability",
            "custom.capability",
            "--operation",
            "custom.capability",
            "--target",
            "test-target",
        ],
    )
    assert code == 0
    assert preflight["status"] == "pass"
    assert preflight["route"]["selected_adapter_id"] == "custom-adapter"
    assert preflight["route"]["risk_level"] == "local"


def test_disabled_entries_listed_but_not_routed(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path, _minimal_registry())

    code, result = _run_json(capsys, fake_root, ["orchestration", "adapter", "list"])
    assert code == 0
    ids = {a["adapter_id"]: a for a in result["adapters"]}
    assert "disabled-adapter" in ids
    assert ids["disabled-adapter"]["enabled"] is False

    code, route = _run_json(
        capsys, fake_root, ["orchestration", "route", "preview", "--capability", "local_command"]
    )
    assert code == 0
    assert route["status"] == "pass"
    assert route["selected_adapter_id"] == "local-shell"
    assert "disabled-adapter" not in {c["adapter_id"] for c in route.get("fallback_candidates", [])}

    code, preflight = _run_json(
        capsys,
        fake_root,
        [
            "orchestration",
            "preflight",
            "--capability",
            "local_command",
            "--operation",
            "local_command",
            "--target",
            "/tmp/test",
        ],
    )
    assert code == 0
    assert preflight["status"] == "pass"
    assert preflight["route"]["selected_adapter_id"] == "local-shell"


def test_missing_registry_safe_error(capsys, tmp_path):
    fake_root = tmp_path / "project"
    fake_root.mkdir()

    for args in [
        ["orchestration", "adapter", "list"],
        ["orchestration", "route", "preview", "--capability", "git_push"],
        [
            "orchestration",
            "preflight",
            "--capability",
            "git_push",
            "--operation",
            "git_push",
            "--target",
            "origin/main",
        ],
    ]:
        code, result = _run_json(capsys, fake_root, args)
        assert code != 0
        assert result["status"] == "error"
        assert any("not found" in f["message"].lower() for f in result["findings"])
        assert "traceback" not in capsys.readouterr().err.lower()


def test_invalid_json_safe_error(capsys, tmp_path):
    fake_root = tmp_path / "project"
    fake_root.mkdir()
    (fake_root / "adapters").mkdir()
    (fake_root / "adapters" / "adapters.sample.json").write_text("not json", encoding="utf-8")

    for args in [
        ["orchestration", "adapter", "list"],
        ["orchestration", "route", "preview", "--capability", "git_push"],
        [
            "orchestration",
            "preflight",
            "--capability",
            "git_push",
            "--operation",
            "git_push",
            "--target",
            "origin/main",
        ],
    ]:
        code, result = _run_json(capsys, fake_root, args)
        assert code != 0
        assert result["status"] == "error"
        assert any(f["rule_id"] == "adapter-registry-invalid-json" for f in result["findings"])


def test_no_files_written_by_read_only_commands(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path, _minimal_registry())
    before_tree = sorted(str(p.relative_to(fake_root)) for p in fake_root.rglob("*"))
    before_bytes = (fake_root / "adapters" / "adapters.sample.json").read_bytes()

    main([
        "--root", str(fake_root),
        "orchestration", "adapter", "list",
        "--json",
    ])
    main([
        "--root", str(fake_root),
        "orchestration", "route", "preview",
        "--capability", "git_push",
        "--json",
    ])
    main([
        "--root", str(fake_root),
        "orchestration", "preflight",
        "--capability", "git_push",
        "--operation", "git_push",
        "--target", "origin/main",
        "--json",
    ])

    after_tree = sorted(str(p.relative_to(fake_root)) for p in fake_root.rglob("*"))
    after_bytes = (fake_root / "adapters" / "adapters.sample.json").read_bytes()
    assert after_tree == before_tree
    assert after_bytes == before_bytes
