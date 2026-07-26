from __future__ import annotations

import json
from pathlib import Path

from agent_runtime.pi_runtime_binding import (
    create_pi_runtime_binding,
    inspect_pi_runtime_binding,
)


def _fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    node = tmp_path / "Program Files" / "nodejs" / "node.exe"
    node.parent.mkdir(parents=True)
    node.write_bytes(b"node-v1")
    package = tmp_path / "npm" / "node_modules" / "@earendil-works" / "pi-coding-agent"
    entry = package / "dist" / "cli.js"
    entry.parent.mkdir(parents=True)
    entry.write_text("export {};", encoding="utf-8")
    (package / "package.json").write_text('{"name":"pi"}', encoding="utf-8")
    return node, entry, package


def test_preview_is_non_mutating_and_projects_only_identities(tmp_path: Path) -> None:
    node, entry, package = _fixture(tmp_path)
    binding = tmp_path / "local" / "pi-runtime-binding-v1.json"

    result = create_pi_runtime_binding(
        node_path=node, cli_entry=entry, module_roots=[package], commit=False, binding_path=binding
    )

    assert result.status == "pass"
    assert result.committed is False
    assert result.binding_id and result.binding_id.startswith("sha256:")
    assert result.closure_identity and result.closure_identity.startswith("sha256:")
    assert not binding.exists()
    assert "node-v1" not in json.dumps(result.to_dict())


def test_commit_creates_machine_local_record_and_inspection_is_read_only(tmp_path: Path) -> None:
    node, entry, package = _fixture(tmp_path)
    binding = tmp_path / "local" / "pi-runtime-binding-v1.json"

    created = create_pi_runtime_binding(
        node_path=node, cli_entry=entry, module_roots=[package], commit=True, binding_path=binding
    )
    inspected = inspect_pi_runtime_binding(binding_path=binding)

    assert created.status == "pass"
    assert created.committed is True
    assert inspected.status == "pass"
    assert inspected.binding_id == created.binding_id
    assert inspected.closure_identity == created.closure_identity
    payload = json.loads(binding.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "pi-runtime-binding/v1"
    assert payload["node"]["path"] == str(node)
    assert payload["cli_entry"]["path"] == str(entry)


def test_existing_binding_requires_explicit_reviewed_rotation(tmp_path: Path) -> None:
    node, entry, package = _fixture(tmp_path)
    binding = tmp_path / "local" / "pi-runtime-binding-v1.json"
    first = create_pi_runtime_binding(
        node_path=node, cli_entry=entry, module_roots=[package], commit=True, binding_path=binding
    )
    entry.write_text("export const version = 2;", encoding="utf-8")

    denied = create_pi_runtime_binding(
        node_path=node, cli_entry=entry, module_roots=[package], commit=True, binding_path=binding
    )
    wrong_review = create_pi_runtime_binding(
        node_path=node, cli_entry=entry, module_roots=[package], commit=True, replace=True,
        expected_binding_id="sha256:" + "0" * 64, binding_path=binding,
    )
    rotated = create_pi_runtime_binding(
        node_path=node, cli_entry=entry, module_roots=[package], commit=True, replace=True,
        expected_binding_id=first.binding_id, binding_path=binding,
    )

    assert denied.status == "blocked"
    assert denied.findings[0].rule_id == "pi-runtime-binding-exists"
    assert wrong_review.status == "blocked"
    assert wrong_review.findings[0].rule_id == "pi-runtime-binding-rotation-review-required"
    assert rotated.status == "pass"
    assert rotated.committed is True
    assert rotated.binding_id != first.binding_id


def test_candidate_rejects_entry_outside_closure_and_symlink(tmp_path: Path) -> None:
    node, entry, package = _fixture(tmp_path)
    other = tmp_path / "other"
    other.mkdir()
    result = create_pi_runtime_binding(
        node_path=node, cli_entry=entry, module_roots=[other], commit=False,
        binding_path=tmp_path / "binding.json",
    )
    assert result.status == "blocked"
    assert result.findings[0].rule_id == "pi-runtime-binding-candidate-invalid"

    link = tmp_path / "node-link.exe"
    try:
        link.symlink_to(node)
    except OSError:
        return
    unsafe = create_pi_runtime_binding(
        node_path=link, cli_entry=entry, module_roots=[package], commit=False,
        binding_path=tmp_path / "binding.json",
    )
    assert unsafe.status == "blocked"
    assert unsafe.findings[0].rule_id == "pi-runtime-binding-candidate-invalid"


def test_closure_drift_changes_preview_identity_without_mutating_existing_binding(tmp_path: Path) -> None:
    node, entry, package = _fixture(tmp_path)
    binding = tmp_path / "local" / "pi-runtime-binding-v1.json"
    first = create_pi_runtime_binding(
        node_path=node, cli_entry=entry, module_roots=[package], commit=True, binding_path=binding
    )
    (package / "dist" / "dependency.js").write_text("changed", encoding="utf-8")
    preview = create_pi_runtime_binding(
        node_path=node, cli_entry=entry, module_roots=[package], commit=False, binding_path=binding
    )

    assert preview.status == "blocked"
    assert preview.findings[0].rule_id == "pi-runtime-binding-exists"
    assert inspect_pi_runtime_binding(binding_path=binding).binding_id == first.binding_id
