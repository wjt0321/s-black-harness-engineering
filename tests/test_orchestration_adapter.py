"""Tests for orchestration adapter list/inspect read-only commands."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agent_runtime.cli import main
from agent_runtime.loader import load_adapters


ROOT = Path(__file__).resolve().parents[1]


def _copy_file(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")


def _setup_fake_root(tmp_path: Path, adapters_data: dict[str, Any] | None = None) -> Path:
    """Create a fake project root with adapters.sample.json and schema."""
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


def _resolve_pointer(source: dict[str, Any], pointer: str) -> Any:
    if "#" in pointer:
        _, path = pointer.split("#", 1)
    else:
        path = pointer
    parts = [p for p in path.split("/") if p]
    value = source
    for part in parts:
        value = value[int(part)] if part.isdigit() else value[part]
    return value


def test_adapter_list_json_output_structure(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)

    code = main([
        "--root", str(fake_root),
        "orchestration", "adapter", "list",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 0
    result = json.loads(captured.out)
    assert result["status"] == "pass"
    assert len(result["adapters"]) >= 3

    by_id = {a["adapter_id"]: a for a in result["adapters"]}
    assert "kimi-code-acp" in by_id
    assert "shell-local" in by_id
    assert "github-cli" in by_id

    shell = by_id["shell-local"]
    assert shell["display_name"] == "Local Shell"
    assert shell["adapter_type"] == "tool"
    assert shell["risk_level"] == "local"
    assert "enabled" in shell
    assert shell["capability_count"] >= 1


def test_adapter_list_matches_loader_entries(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)

    code = main([
        "--root", str(fake_root),
        "orchestration", "adapter", "list",
        "--json",
    ])
    captured = capsys.readouterr()
    result = json.loads(captured.out)
    assert result["status"] == "pass"

    source = load_adapters(fake_root)
    source_ids = {entry["id"] for entry in source["adapters"]}
    listed_ids = {a["adapter_id"] for a in result["adapters"]}
    assert listed_ids == source_ids


def test_adapter_list_human_readable_smoke(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)

    code = main([
        "--root", str(fake_root),
        "orchestration", "adapter", "list",
    ])
    captured = capsys.readouterr()
    assert code == 0
    assert "ADAPTER LIST" in captured.out
    assert "shell-local" in captured.out
    assert "enabled=" in captured.out


def test_adapter_list_stable_sort(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)

    code = main([
        "--root", str(fake_root),
        "orchestration", "adapter", "list",
        "--json",
    ])
    captured = capsys.readouterr()
    result = json.loads(captured.out)
    ids = [a["adapter_id"] for a in result["adapters"]]
    assert ids == sorted(ids)


def test_adapter_list_type_filter(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)

    code = main([
        "--root", str(fake_root),
        "orchestration", "adapter", "list",
        "--type", "agent",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 0
    result = json.loads(captured.out)
    assert all(a["adapter_type"] == "agent" for a in result["adapters"])


def test_adapter_list_risk_filter(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)

    code = main([
        "--root", str(fake_root),
        "orchestration", "adapter", "list",
        "--risk", "local",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 0
    result = json.loads(captured.out)
    assert all(a["risk_level"] == "local" for a in result["adapters"])


def test_adapter_list_capability_filter(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)

    code = main([
        "--root", str(fake_root),
        "orchestration", "adapter", "list",
        "--capability", "local_command",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 0
    result = json.loads(captured.out)
    ids = {a["adapter_id"] for a in result["adapters"]}
    assert "shell-local" in ids


def test_adapter_inspect_json_output_structure(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)

    code = main([
        "--root", str(fake_root),
        "orchestration", "adapter", "inspect",
        "shell-local",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 0
    result = json.loads(captured.out)
    assert result["status"] == "pass"
    adapter = result["adapter"]
    assert adapter["adapter_id"] == "shell-local"
    assert adapter["display_name"] == "Local Shell"
    assert adapter["adapter_type"] == "tool"
    assert "local_command" in adapter["capabilities"]
    assert "timeout_profile" in adapter
    assert adapter["timeout_profile"]["default_seconds"] > 0
    assert adapter["timeout_profile"]["max_seconds"] > 0
    assert "adapters.sample.json#/adapters/" in adapter["input_schema_ref"]
    assert "input_schema" in adapter["input_schema_ref"]
    assert "derived" in adapter
    assert "pointer to" in adapter["derived"]["input_schema_ref"]


def test_adapter_inspect_schema_refs_resolve_to_source_schemas(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    source = load_adapters(fake_root)

    code = main([
        "--root", str(fake_root),
        "orchestration", "adapter", "inspect",
        "github-cli",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 0
    adapter = json.loads(captured.out)["adapter"]
    assert adapter["adapter_id"] == "github-cli"

    source_entry = source["adapters"][adapter["source_index"]]
    assert source_entry["id"] == "github-cli"
    assert _resolve_pointer(source, adapter["input_schema_ref"]) == source_entry["input_schema"]
    assert _resolve_pointer(source, adapter["output_schema_ref"]) == source_entry["output_schema"]


def test_adapter_inspect_human_readable_smoke(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)

    code = main([
        "--root", str(fake_root),
        "orchestration", "adapter", "inspect",
        "kimi-code-acp",
    ])
    captured = capsys.readouterr()
    assert code == 0
    assert "ADAPTER INSPECT" in captured.out
    assert "kimi-code-acp" in captured.out
    assert "Kimi Code ACP" in captured.out
    assert "derived:" in captured.out


def test_adapter_inspect_unknown_id(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)

    code = main([
        "--root", str(fake_root),
        "orchestration", "adapter", "inspect",
        "does-not-exist",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code != 0
    result = json.loads(captured.out)
    assert result["status"] == "needs_input"
    assert "does-not-exist" in result["next_action"]


def test_adapter_list_reflects_source_mutation(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)

    code = main([
        "--root", str(fake_root),
        "orchestration", "adapter", "list",
        "--json",
    ])
    captured = capsys.readouterr()
    initial = json.loads(captured.out)
    assert "custom-adapter" not in {a["adapter_id"] for a in initial["adapters"]}

    data = json.loads((fake_root / "adapters" / "adapters.sample.json").read_text(encoding="utf-8"))
    data["adapters"].append({
        "id": "custom-adapter",
        "name": "Custom Adapter",
        "kind": "lark",
        "enabled": True,
        "capabilities": ["custom.capability"],
        "risk_level": "external",
        "requires_approval": True,
        "input_schema": {"type": "object"},
        "output_schema": {"type": "object"},
    })
    (fake_root / "adapters" / "adapters.sample.json").write_text(
        json.dumps(data, ensure_ascii=False), encoding="utf-8"
    )

    code = main([
        "--root", str(fake_root),
        "orchestration", "adapter", "list",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 0
    result = json.loads(captured.out)
    ids = {a["adapter_id"] for a in result["adapters"]}
    assert "custom-adapter" in ids


def test_adapter_list_includes_disabled_entries(capsys, tmp_path):
    data = {
        "version": 1,
        "adapters": [
            {
                "id": "enabled-adapter",
                "name": "Enabled",
                "kind": "shell",
                "enabled": True,
                "capabilities": ["cap.one"],
                "risk_level": "local",
                "requires_approval": False,
                "input_schema": {"type": "object"},
                "output_schema": {"type": "object"},
            },
            {
                "id": "disabled-adapter",
                "name": "Disabled",
                "kind": "shell",
                "enabled": False,
                "capabilities": ["cap.two"],
                "risk_level": "local",
                "requires_approval": False,
                "input_schema": {"type": "object"},
                "output_schema": {"type": "object"},
            },
        ],
    }
    fake_root = _setup_fake_root(tmp_path, data)

    code = main([
        "--root", str(fake_root),
        "orchestration", "adapter", "list",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code == 0
    result = json.loads(captured.out)
    ids = {a["adapter_id"] for a in result["adapters"]}
    assert ids == {"enabled-adapter", "disabled-adapter"}
    by_id = {a["adapter_id"]: a for a in result["adapters"]}
    assert by_id["disabled-adapter"]["enabled"] is False


def test_adapter_list_missing_registry(capsys, tmp_path):
    fake_root = tmp_path / "project"
    fake_root.mkdir()

    code = main([
        "--root", str(fake_root),
        "orchestration", "adapter", "list",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code != 0
    result = json.loads(captured.out)
    assert result["status"] == "error"
    assert any("not found" in f["message"].lower() for f in result["findings"])


def test_adapter_list_invalid_json(capsys, tmp_path):
    fake_root = tmp_path / "project"
    fake_root.mkdir()
    (fake_root / "adapters").mkdir()
    (fake_root / "adapters" / "adapters.sample.json").write_text("not json", encoding="utf-8")

    code = main([
        "--root", str(fake_root),
        "orchestration", "adapter", "list",
        "--json",
    ])
    captured = capsys.readouterr()
    assert code != 0
    result = json.loads(captured.out)
    assert result["status"] == "error"
    assert any(f["rule_id"] == "adapter-registry-invalid-json" for f in result["findings"])


def test_adapter_list_does_not_write_files(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    before = list(fake_root.rglob("*"))

    code = main([
        "--root", str(fake_root),
        "orchestration", "adapter", "list",
        "--json",
    ])
    assert code == 0
    assert list(fake_root.rglob("*")) == before


def test_adapter_inspect_does_not_write_files(capsys, tmp_path):
    fake_root = _setup_fake_root(tmp_path)
    before = list(fake_root.rglob("*"))

    code = main([
        "--root", str(fake_root),
        "orchestration", "adapter", "inspect",
        "github-cli",
        "--json",
    ])
    assert code == 0
    assert list(fake_root.rglob("*")) == before
