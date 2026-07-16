"""Tests for the Stage 44 single-user real-execution readiness gate."""

from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path

import pytest
from jsonschema import ValidationError as JsonSchemaValidationError
from jsonschema import validate

from agent_runtime.cli import build_parser, main
from agent_runtime.doctor import SAMPLE_TO_SCHEMA, SCHEMA_FILES
from agent_runtime.orchestration_contract import build_contract_manifest

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "adapters" / "execution-readiness.sample.json"
SCHEMA = ROOT / "adapters" / "execution-readiness.schema.json"
TOOL = ROOT / "agent_runtime" / "orchestration_execution_readiness.py"
CHECK_IDS = [
    "profile_schema",
    "single_user_identity",
    "candidate_registry_alignment",
    "fixed_argv",
    "working_directory",
    "environment_allowlist",
    "bounded_process",
    "side_effect_boundary",
    "approval_binding_contract",
    "audit_contract",
    "executor_implementation",
    "approval_binding_implementation",
    "audit_writer_implementation",
]


def _nested_parser(parser: argparse.ArgumentParser, name: str) -> argparse.ArgumentParser:
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction) and name in action.choices:
            return action.choices[name]
    raise AssertionError(f"subparser not found: {name}")


def _run_json(capsys, root: Path = ROOT) -> tuple[int, dict[str, object]]:
    code = main([
        "--root", str(root),
        "orchestration", "execution", "readiness", "--json",
    ])
    captured = capsys.readouterr()
    assert captured.err == ""
    return code, json.loads(captured.out)


def _fake_root(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    for source in [
        PROFILE,
        SCHEMA,
        ROOT / "adapters" / "adapter.schema.json",
        ROOT / "adapters" / "adapters.sample.json",
        ROOT / "tasks" / "event.schema.json",
    ]:
        target = root / source.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())
    return root


def test_cli_surface_and_wrapper_are_frozen(capsys) -> None:
    parser = build_parser()
    execution = _nested_parser(_nested_parser(parser, "orchestration"), "execution")
    _nested_parser(execution, "readiness")

    code, result = _run_json(capsys)

    assert code == 2
    assert set(result) == {
        "status", "schema_version", "gate", "readiness", "source", "scope",
        "process_contract", "approval_binding", "audit_contract", "checks",
        "summary", "findings", "guarantees", "next_action",
    }
    assert result["status"] == "blocked"
    assert result["schema_version"] == "control-plane/single-user-execution-readiness/v1"
    assert result["gate"] == "single-user-real-execution-readiness/v1"
    assert result["readiness"] == "design_ready_implementation_blocked"


def test_single_user_identity_and_candidate_are_explicit(capsys) -> None:
    _, result = _run_json(capsys)

    assert result["scope"] == {
        "identity": {
            "mode": "single_user_local",
            "actor": "local-operator",
            "multi_user_authorization": False,
            "future_extension": "actor_context",
        },
        "candidate": {
            "adapter_id": "shell-local",
            "capability": "git_status",
            "operation": "git_status",
            "risk_level": "local",
        },
    }


def test_fixed_process_contract_is_safe_and_bounded(capsys) -> None:
    _, result = _run_json(capsys)

    assert result["process_contract"] == {
        "executable": "git",
        "argv": ["git", "status", "--short", "--branch"],
        "shell": False,
        "cwd": "project_root",
        "stdin": "closed",
        "environment": {
            "inherit_allowlist": ["PATH", "SYSTEMROOT", "WINDIR"],
            "set": {"GIT_OPTIONAL_LOCKS": "0"},
        },
        "timeout_seconds": 10,
        "max_timeout_seconds": 30,
        "max_stdout_bytes": 65536,
        "max_stderr_bytes": 65536,
        "retry_count": 0,
        "network_access": False,
        "writes_project_files": False,
        "background": False,
    }


def test_approval_and_audit_contracts_are_frozen(capsys) -> None:
    _, result = _run_json(capsys)

    assert result["approval_binding"] == {
        "required_for_approval_adapters": True,
        "bound_fields": [
            "adapter_id", "capability", "operation", "plan_hash",
            "request_id", "target_digest", "task_id",
        ],
        "decision_event_type": "approval_resolved",
        "recheck_before_spawn": True,
        "retry_reuses_approval": False,
    }
    assert result["audit_contract"] == {
        "event_types": [
            "execution_started", "execution_succeeded",
            "execution_failed", "execution_cancelled",
        ],
        "controlled_append": True,
        "rollback_on_failure": True,
        "stores_raw_stdout": False,
        "stores_raw_stderr": False,
    }


def test_checks_distinguish_design_readiness_from_implementation(capsys) -> None:
    _, result = _run_json(capsys)

    checks = result["checks"]
    assert [check["check_id"] for check in checks] == CHECK_IDS
    assert [check["status"] for check in checks] == ["pass"] * 10 + ["blocked"] * 3
    assert result["summary"] == {"total": 13, "pass": 10, "blocked": 3}
    assert {finding["rule_id"] for finding in result["findings"]} == {
        "execution-readiness-executor-unavailable",
        "execution-readiness-approval-binding-unavailable",
        "execution-readiness-audit-writer-unavailable",
    }
    assert "implement" in result["next_action"].lower()


def test_output_is_deterministic_read_only_and_value_safe(capsys, tmp_path) -> None:
    root = _fake_root(tmp_path)
    before = {
        path.relative_to(root): path.read_bytes()
        for path in root.rglob("*") if path.is_file()
    }

    first_code, first = _run_json(capsys, root)
    second_code, second = _run_json(capsys, root)

    assert first_code == second_code == 2
    assert first == second
    after = {
        path.relative_to(root): path.read_bytes()
        for path in root.rglob("*") if path.is_file()
    }
    assert after == before
    serialized = json.dumps(first, ensure_ascii=False)
    assert str(root) not in serialized
    assert ".env" not in serialized
    assert "READINESS_PRIVATE_SENTINEL" not in serialized
    assert first["guarantees"] == {
        "deterministic": True,
        "read_only": True,
        "single_user": True,
        "multi_user_authorization": False,
        "executes_processes": False,
        "executes_adapters": False,
        "reads_credentials": False,
        "writes_files": False,
        "writes_ledgers": False,
        "accesses_network": False,
    }


def test_registry_drift_is_blocked_without_leaking_values(capsys, tmp_path) -> None:
    root = _fake_root(tmp_path)
    registry_path = root / "adapters" / "adapters.sample.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    candidate = next(item for item in registry["adapters"] if item["id"] == "shell-local")
    candidate["capabilities"].remove("git_status")
    registry_path.write_text(json.dumps(registry), encoding="utf-8")

    code, result = _run_json(capsys, root)

    assert code == 2
    checks = {check["check_id"]: check for check in result["checks"]}
    assert checks["candidate_registry_alignment"]["status"] == "blocked"
    assert result["readiness"] == "contract_drift_blocked"


def test_malformed_profile_fails_safely(capsys, tmp_path) -> None:
    root = _fake_root(tmp_path)
    marker = "READINESS_PRIVATE_SENTINEL"
    profile_path = root / "adapters" / "execution-readiness.sample.json"
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    profile["unexpected"] = marker
    profile_path.write_text(json.dumps(profile), encoding="utf-8")

    code, result = _run_json(capsys, root)

    assert code == 5
    assert result["status"] == "validation_failed"
    assert marker not in json.dumps(result)
    assert {finding["rule_id"] for finding in result["findings"]} == {
        "execution-readiness-profile-invalid"
    }


def test_invalid_profile_schema_fails_without_leaking_values(capsys, tmp_path) -> None:
    root = _fake_root(tmp_path)
    marker = "READINESS_PRIVATE_SENTINEL"
    schema_path = root / "adapters" / "execution-readiness.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    schema["type"] = marker
    schema_path.write_text(json.dumps(schema), encoding="utf-8")

    code, result = _run_json(capsys, root)

    assert code == 5
    assert result["status"] == "validation_failed"
    assert marker not in json.dumps(result)
    assert {finding["rule_id"] for finding in result["findings"]} == {
        "execution-readiness-profile-invalid"
    }


def test_malformed_registry_root_fails_without_leaking_values(capsys, tmp_path) -> None:
    root = _fake_root(tmp_path)
    marker = "READINESS_PRIVATE_SENTINEL"
    registry_path = root / "adapters" / "adapters.sample.json"
    registry_path.write_text(json.dumps([marker]), encoding="utf-8")

    code, result = _run_json(capsys, root)

    assert code == 5
    assert result["status"] == "validation_failed"
    assert marker not in json.dumps(result)
    assert {finding["rule_id"] for finding in result["findings"]} == {
        "execution-readiness-registry-invalid"
    }


def test_invalid_event_schema_fails_without_leaking_values(capsys, tmp_path) -> None:
    root = _fake_root(tmp_path)
    marker = "READINESS_PRIVATE_SENTINEL"
    event_schema_path = root / "tasks" / "event.schema.json"
    event_schema = json.loads(event_schema_path.read_text(encoding="utf-8"))
    event_schema["type"] = marker
    event_schema_path.write_text(json.dumps(event_schema), encoding="utf-8")

    code, result = _run_json(capsys, root)

    assert code == 5
    assert result["status"] == "validation_failed"
    assert marker not in json.dumps(result)
    assert {finding["rule_id"] for finding in result["findings"]} == {
        "execution-readiness-event-schema-invalid"
    }


def test_event_schema_structure_drift_blocks_audit_contract(capsys, tmp_path) -> None:
    root = _fake_root(tmp_path)
    event_schema_path = root / "tasks" / "event.schema.json"
    event_schema = json.loads(event_schema_path.read_text(encoding="utf-8"))
    del event_schema["properties"]["event_type"]["enum"]
    event_schema_path.write_text(json.dumps(event_schema), encoding="utf-8")

    code, result = _run_json(capsys, root)

    assert code == 2
    checks = {check["check_id"]: check for check in result["checks"]}
    assert checks["audit_contract"]["status"] == "blocked"
    assert result["readiness"] == "contract_drift_blocked"


def test_event_schema_requires_event_type_for_audit_alignment(capsys, tmp_path) -> None:
    root = _fake_root(tmp_path)
    event_schema_path = root / "tasks" / "event.schema.json"
    event_schema = json.loads(event_schema_path.read_text(encoding="utf-8"))
    event_schema["required"].remove("event_type")
    event_schema_path.write_text(json.dumps(event_schema), encoding="utf-8")

    code, result = _run_json(capsys, root)

    assert code == 2
    checks = {check["check_id"]: check for check in result["checks"]}
    assert checks["audit_contract"]["status"] == "blocked"
    assert result["readiness"] == "contract_drift_blocked"


def test_event_schema_event_type_must_remain_string(capsys, tmp_path) -> None:
    root = _fake_root(tmp_path)
    event_schema_path = root / "tasks" / "event.schema.json"
    event_schema = json.loads(event_schema_path.read_text(encoding="utf-8"))
    event_schema["properties"]["event_type"]["type"] = "integer"
    event_schema_path.write_text(json.dumps(event_schema), encoding="utf-8")

    code, result = _run_json(capsys, root)

    assert code == 2
    checks = {check["check_id"]: check for check in result["checks"]}
    assert checks["audit_contract"]["status"] == "blocked"
    assert result["readiness"] == "contract_drift_blocked"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("requires_approval", True),
        ("enabled", False),
        ("kind", "github"),
        ("risk_level", "external"),
    ],
)
def test_candidate_registry_drift_is_blocked(
    capsys,
    tmp_path,
    field: str,
    value: object,
) -> None:
    root = _fake_root(tmp_path)
    registry_path = root / "adapters" / "adapters.sample.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    candidate = next(item for item in registry["adapters"] if item["id"] == "shell-local")
    candidate[field] = value
    registry_path.write_text(json.dumps(registry), encoding="utf-8")

    code, result = _run_json(capsys, root)

    assert code == 2
    checks = {check["check_id"]: check for check in result["checks"]}
    assert checks["candidate_registry_alignment"]["status"] == "blocked"
    assert result["readiness"] == "contract_drift_blocked"


def test_v1_profile_permanently_freezes_known_implementation_gaps() -> None:
    profile = json.loads(PROFILE.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    profile["implementation"]["executor"] = True

    with pytest.raises(JsonSchemaValidationError):
        validate(instance=profile, schema=schema)


def test_doctor_registers_readiness_schema_and_sample() -> None:
    assert "adapters/execution-readiness.schema.json" in SCHEMA_FILES
    assert (
        "adapters/execution-readiness.sample.json",
        "adapters/execution-readiness.schema.json",
    ) in SAMPLE_TO_SCHEMA


def test_contract_manifest_keeps_execution_unavailable_and_adds_readiness() -> None:
    entries = {
        entry.contract_id: entry
        for entry in build_contract_manifest().entries
    }

    readiness = entries["execution_readiness"]
    assert readiness.availability == "preview"
    assert readiness.access == "read_only"
    assert readiness.commands == (("orchestration", "execution", "readiness"),)
    assert "does not execute" in readiness.boundary.lower()
    execution = entries["external_execution_service_stack"]
    assert execution.availability == "unavailable"
    assert execution.commands == ()


def test_source_has_no_process_network_or_write_path() -> None:
    tree = ast.parse(TOOL.read_text(encoding="utf-8"))
    imports: set[str] = set()
    calls: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split(".")[0])
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute):
                calls.add(node.func.attr)
            elif isinstance(node.func, ast.Name):
                calls.add(node.func.id)

    assert not imports.intersection({"subprocess", "socket", "requests", "urllib", "http"})
    assert not calls.intersection({
        "write_text", "write_bytes", "open", "unlink", "rename",
        "run", "Popen", "system", "spawn", "exec",
    })
