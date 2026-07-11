"""Tests for the Stage 10 adapter capability registry projection."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from agent_runtime.adapter_registry import (
    AdapterMetadata,
    AdapterRegistry,
    TimeoutProfile,
    load_adapter_registry,
    project_adapter,
    validate_adapter_metadata,
)
from agent_runtime.loader import load_adapters


ROOT = Path(__file__).resolve().parents[1]


def _copy_file(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")


def _setup_root_with_adapters(tmp_path: Path, adapters_data: dict[str, Any] | None = None) -> Path:
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


def _resolve_pointer(data: dict[str, Any], pointer: str) -> Any:
    """Resolve a simple JSON Pointer against data loaded from adapters.sample.json."""
    # pointer looks like "adapters/adapters.sample.json#/adapters/0/input_schema"
    if "#" in pointer:
        _, path = pointer.split("#", 1)
    else:
        path = pointer
    parts = [p for p in path.split("/") if p]
    value = data
    for part in parts:
        if part.isdigit():
            value = value[int(part)]
        else:
            value = value[part]
    return value


def test_load_from_project_root_matches_sample() -> None:
    registry, findings, _next_action = load_adapter_registry(ROOT)
    assert registry is not None
    assert findings == []
    source = load_adapters(ROOT)
    source_ids = {entry["id"] for entry in source["adapters"]}
    projected_ids = {a.adapter_id for a in registry.list_adapters()}
    assert projected_ids == source_ids


def test_load_from_tmp_root_reflects_mutation(tmp_path: Path) -> None:
    fake_root = _setup_root_with_adapters(tmp_path)
    registry, _, _ = load_adapter_registry(fake_root)
    assert registry is not None
    assert registry.get_adapter("custom-adapter") is None

    # Mutate the source registry.
    data = json.loads((fake_root / "adapters" / "adapters.sample.json").read_text(encoding="utf-8"))
    data["adapters"].append({
        "id": "custom-adapter",
        "name": "Custom Adapter",
        "kind": "shell",
        "enabled": True,
        "capabilities": ["custom.cap"],
        "risk_level": "local",
        "requires_approval": False,
        "input_schema": {"type": "object", "required": ["command"], "properties": {"command": {"type": "string"}}},
        "output_schema": {"type": "object", "required": ["status"], "properties": {"status": {"type": "string"}}},
    })
    (fake_root / "adapters" / "adapters.sample.json").write_text(
        json.dumps(data, ensure_ascii=False), encoding="utf-8"
    )

    registry, _, _ = load_adapter_registry(fake_root)
    assert registry is not None
    custom = registry.get_adapter("custom-adapter")
    assert custom is not None
    assert custom.adapter_type == "tool"
    assert custom.capabilities == ["custom.cap"]
    assert custom.risk_level == "local"


def test_projected_ids_capabilities_risk_align_with_source(tmp_path: Path) -> None:
    fake_root = _setup_root_with_adapters(tmp_path)
    source = json.loads((fake_root / "adapters" / "adapters.sample.json").read_text(encoding="utf-8"))
    registry, _, _ = load_adapter_registry(fake_root)
    assert registry is not None

    source_entries = {entry["id"]: entry for entry in source["adapters"]}
    projected = {a.adapter_id: a for a in registry.list_adapters()}

    assert set(source_entries.keys()) == set(projected.keys())
    for adapter_id, metadata in projected.items():
        entry = source_entries[adapter_id]
        assert metadata.capabilities == entry["capabilities"]
        assert metadata.risk_level == entry["risk_level"]
        assert metadata.enabled == entry.get("enabled", True)


def test_schema_refs_point_to_source_entry_schemas(tmp_path: Path) -> None:
    fake_root = _setup_root_with_adapters(tmp_path)
    source = json.loads((fake_root / "adapters" / "adapters.sample.json").read_text(encoding="utf-8"))
    registry, _, _ = load_adapter_registry(fake_root)
    assert registry is not None

    for metadata in registry.list_adapters():
        entry = source["adapters"][metadata.source_index]
        assert metadata.adapter_id == entry["id"]
        assert _resolve_pointer(source, metadata.input_schema_ref) == entry["input_schema"]
        assert _resolve_pointer(source, metadata.output_schema_ref) == entry["output_schema"]
        assert "adapters.sample.json#/adapters/" in metadata.input_schema_ref
        assert "adapters.sample.json#/adapters/" in metadata.output_schema_ref


def test_disabled_entries_are_not_filtered(tmp_path: Path) -> None:
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
    fake_root = _setup_root_with_adapters(tmp_path, data)
    registry, _, _ = load_adapter_registry(fake_root)
    assert registry is not None
    ids = {a.adapter_id for a in registry.list_adapters()}
    assert ids == {"enabled-adapter", "disabled-adapter"}
    assert registry.get_adapter("disabled-adapter").enabled is False


def test_load_missing_registry_returns_error() -> None:
    fake_root = Path("/nonexistent/path/should/not/exist")
    registry, findings, next_action = load_adapter_registry(fake_root)
    assert registry is None
    assert any("not found" in f.message.lower() for f in findings)
    assert next_action is not None


def test_load_invalid_json_returns_error(tmp_path: Path) -> None:
    fake_root = tmp_path / "project"
    fake_root.mkdir()
    (fake_root / "adapters").mkdir()
    (fake_root / "adapters" / "adapters.sample.json").write_text("not json", encoding="utf-8")

    registry, findings, next_action = load_adapter_registry(fake_root)
    assert registry is None
    assert any(f.rule_id == "adapter-registry-invalid-json" for f in findings)
    assert "json" in next_action.lower()


def test_load_schema_validation_failure_returns_error(tmp_path: Path) -> None:
    fake_root = _setup_root_with_adapters(tmp_path)
    # Write a registry that is valid JSON but violates the schema.
    (fake_root / "adapters" / "adapters.sample.json").write_text(
        json.dumps({"version": 1, "adapters": []}, ensure_ascii=False), encoding="utf-8"
    )
    registry, findings, next_action = load_adapter_registry(fake_root)
    assert registry is None
    assert any(f.rule_id == "adapter-registry-schema-failed" for f in findings)
    assert "schema" in next_action.lower()


def test_load_malformed_adapters_field_returns_error(tmp_path: Path) -> None:
    fake_root = _setup_root_with_adapters(tmp_path, {"version": 1, "adapters": "not-a-list"})
    registry, findings, _next_action = load_adapter_registry(fake_root)
    assert registry is None
    assert any("not a list" in f.message for f in findings)


def test_load_project_validation_failure_returns_error(tmp_path: Path) -> None:
    fake_root = _setup_root_with_adapters(tmp_path, {
        "version": 1,
        "adapters": [
            {
                "id": "bad",
                "name": "Bad",
                "kind": "shell",
                "enabled": True,
                "capabilities": [],
                "risk_level": "local",
                "requires_approval": False,
                "input_schema": {"type": "object"},
                "output_schema": {"type": "object"},
            }
        ],
    })
    registry, findings, _next_action = load_adapter_registry(fake_root)
    assert registry is None
    assert any("capabilities" in f.message for f in findings)


def test_project_adapter_derivation() -> None:
    entry = {
        "id": "shell-local",
        "name": "Local Shell",
        "kind": "shell",
        "enabled": True,
        "capabilities": ["execute.local_command"],
        "risk_level": "local",
        "requires_approval": False,
        "input_schema": {"type": "object"},
        "output_schema": {"type": "object"},
    }
    metadata = project_adapter(entry, source_index=2)
    assert metadata.adapter_id == "shell-local"
    assert metadata.display_name == "Local Shell"
    assert metadata.adapter_type == "tool"
    assert metadata.enabled is True
    assert metadata.source_index == 2
    assert metadata.input_schema_ref == "adapters/adapters.sample.json#/adapters/2/input_schema"
    assert metadata.output_schema_ref == "adapters/adapters.sample.json#/adapters/2/output_schema"
    assert metadata.supports_session is False
    assert metadata.supports_background is False
    assert metadata.supports_approval_roundtrip is False
    assert metadata.supports_artifacts is True
    assert metadata.supports_cancel is True
    assert "pointer to" in metadata.derived["input_schema_ref"]
    assert "pointer to" in metadata.derived["output_schema_ref"]


def test_project_agent_adapter_derivation() -> None:
    entry = {
        "id": "kimi",
        "name": "Kimi",
        "kind": "acp_runner",
        "enabled": True,
        "capabilities": ["dispatch.agent.coding", "background_task"],
        "risk_level": "external",
        "requires_approval": False,
        "input_schema": {"type": "object"},
        "output_schema": {"type": "object"},
    }
    metadata = project_adapter(entry, source_index=0)
    assert metadata.adapter_type == "agent"
    assert metadata.supports_session is True
    assert metadata.supports_background is True
    assert metadata.supports_approval_roundtrip is True
    assert metadata.supports_artifacts is False


def test_project_service_adapter_derivation() -> None:
    entry = {
        "id": "lark",
        "name": "Lark",
        "kind": "lark",
        "enabled": True,
        "capabilities": ["publish.lark.message"],
        "risk_level": "external",
        "requires_approval": True,
        "input_schema": {"type": "object"},
        "output_schema": {"type": "object"},
    }
    metadata = project_adapter(entry, source_index=5)
    assert metadata.adapter_type == "service"
    assert metadata.supports_approval_roundtrip is True
    assert "requires_approval=True" in metadata.derived["supports_approval_roundtrip"]


def test_registry_stable_sort() -> None:
    entries = {
        "zeta": AdapterMetadata(
            adapter_id="zeta",
            display_name="Zeta",
            adapter_type="tool",
            capabilities=["cap.one"],
            risk_level="local",
            timeout_profile=TimeoutProfile(1, 1),
            input_schema_ref="in",
            output_schema_ref="out",
            source_index=0,
        ),
        "alpha": AdapterMetadata(
            adapter_id="alpha",
            display_name="Alpha",
            adapter_type="tool",
            capabilities=["cap.one"],
            risk_level="local",
            timeout_profile=TimeoutProfile(1, 1),
            input_schema_ref="in",
            output_schema_ref="out",
            source_index=1,
        ),
    }
    registry = AdapterRegistry(entries)
    ids = [a.adapter_id for a in registry.list_adapters()]
    assert ids == ["alpha", "zeta"]


def test_validate_adapter_metadata_detects_invalid_id() -> None:
    metadata = AdapterMetadata(
        adapter_id="Bad Id",
        display_name="Bad Id",
        adapter_type="tool",
        capabilities=["cap.one"],
        risk_level="local",
        timeout_profile=TimeoutProfile(1, 1),
        input_schema_ref="in",
        output_schema_ref="out",
        source_index=0,
    )
    errors = validate_adapter_metadata(metadata)
    assert any("adapter_id" in e for e in errors)


def test_validate_adapter_metadata_detects_timeout_violation() -> None:
    metadata = AdapterMetadata(
        adapter_id="bad-timeout",
        display_name="Bad Timeout",
        adapter_type="tool",
        capabilities=["cap.one"],
        risk_level="local",
        timeout_profile=TimeoutProfile(120, 60),
        input_schema_ref="in",
        output_schema_ref="out",
        source_index=0,
    )
    errors = validate_adapter_metadata(metadata)
    assert any("timeout" in e for e in errors)


def test_capability_index_is_deterministic(tmp_path: Path) -> None:
    fake_root = _setup_root_with_adapters(tmp_path)
    registry, _, _ = load_adapter_registry(fake_root)
    assert registry is not None
    index = registry.capability_index()
    for adapter_ids in index.values():
        assert adapter_ids == sorted(adapter_ids)
