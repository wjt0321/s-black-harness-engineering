"""Schema and generic-entry guards for execution audit events."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest
from jsonschema import ValidationError, validate

from agent_runtime.doctor import SCHEMA_FILES, run_doctor
from agent_runtime.loader import load_schema

ROOT = Path(__file__).resolve().parents[1]

RESERVED_EVENT_TYPES = (
    "execution_attempt_started",
    "execution_succeeded",
    "execution_failed",
    "execution_cancelled",
)


def _metadata_for(event_type: str) -> dict[str, object]:
    metadata: dict[str, object] = {
        "writer_origin": "agent_runtime.execution_audit_writer",
        "writer_schema_version": "execution-audit/v1",
        "attempt_id": "attempt-20260717-001",
        "request_id": "req-20260717-001",
        "plan_hash": "sha256:" + "a" * 64,
        "adapter_id": "shell-local",
        "capability": "git_status",
        "operation": "git_status",
    }
    if event_type == "execution_attempt_started":
        metadata["phase"] = "pre_spawn_committed"
    else:
        metadata["started_event_id"] = "evt-20260717-001"
        if event_type == "execution_succeeded":
            metadata["phase"] = "post_run_validated"
            metadata["exit_code"] = 0
            metadata["guard_status"] = "pass"
            metadata["stdout_truncated"] = False
            metadata["stderr_truncated"] = False
        elif event_type == "execution_failed":
            metadata["phase"] = "spawn"
            metadata["failure_code"] = "spawn_failed"
        else:
            metadata["phase"] = "cancelled"
            metadata["failure_code"] = "operator_cancelled"
    return metadata


def _event(event_type: str) -> dict[str, object]:
    return {
        "event_id": "evt-20260717-002",
        "task_id": "task-20260717-001",
        "timestamp": "2026-07-17T10:00:00+08:00",
        "actor": "local-operator",
        "event_type": event_type,
        "message": "Execution audit lifecycle event.",
        "metadata": _metadata_for(event_type),
    }


@pytest.mark.parametrize("event_type", RESERVED_EVENT_TYPES)
def test_shared_event_schema_accepts_reserved_execution_types(event_type: str) -> None:
    schema = load_schema(ROOT, "tasks/event.schema.json")

    validate(instance=_event(event_type), schema=schema)


@pytest.mark.parametrize("event_type", RESERVED_EVENT_TYPES)
def test_dedicated_schema_accepts_each_execution_event_shape(event_type: str) -> None:
    schema = load_schema(ROOT, "tasks/execution-audit-event.schema.json")

    validate(instance=_event(event_type), schema=schema)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("actor", "cli"),
        ("writer_origin", "caller-supplied"),
        ("writer_schema_version", "execution-audit/v2"),
    ),
)
def test_dedicated_schema_rejects_wrong_fixed_provenance(
    field: str, value: str
) -> None:
    schema = load_schema(ROOT, "tasks/execution-audit-event.schema.json")
    candidate = _event("execution_attempt_started")
    if field == "actor":
        candidate[field] = value
    else:
        candidate["metadata"][field] = value

    with pytest.raises(ValidationError):
        validate(instance=candidate, schema=schema)


@pytest.mark.parametrize(
    "field",
    ("raw_stdout", "path", "environment"),
)
def test_dedicated_schema_rejects_extra_sensitive_metadata(field: str) -> None:
    schema = load_schema(ROOT, "tasks/execution-audit-event.schema.json")
    candidate = _event("execution_failed")
    candidate["metadata"][field] = "withheld-value"

    with pytest.raises(ValidationError):
        validate(instance=candidate, schema=schema)


def test_dedicated_schema_rejects_wrong_type_phase_pair() -> None:
    schema = load_schema(ROOT, "tasks/execution-audit-event.schema.json")
    candidate = _event("execution_succeeded")
    candidate["metadata"]["phase"] = "spawn"

    with pytest.raises(ValidationError):
        validate(instance=candidate, schema=schema)


def test_dedicated_schema_requires_terminal_started_event_reference() -> None:
    schema = load_schema(ROOT, "tasks/execution-audit-event.schema.json")
    candidate = deepcopy(_event("execution_cancelled"))
    del candidate["metadata"]["started_event_id"]

    with pytest.raises(ValidationError):
        validate(instance=candidate, schema=schema)


@pytest.mark.parametrize(
    "field",
    ("exit_code", "guard_status", "stdout_truncated", "stderr_truncated"),
)
def test_succeeded_schema_requires_closed_success_evidence(field: str) -> None:
    schema = load_schema(ROOT, "tasks/execution-audit-event.schema.json")
    candidate = deepcopy(_event("execution_succeeded"))
    del candidate["metadata"][field]

    with pytest.raises(ValidationError):
        validate(instance=candidate, schema=schema)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("exit_code", 1),
        ("guard_status", "failed"),
        ("stdout_truncated", True),
        ("stderr_truncated", True),
    ),
)
def test_succeeded_schema_rejects_contradictory_success_evidence(
    field: str, value: object
) -> None:
    schema = load_schema(ROOT, "tasks/execution-audit-event.schema.json")
    candidate = deepcopy(_event("execution_succeeded"))
    candidate["metadata"][field] = value

    with pytest.raises(ValidationError):
        validate(instance=candidate, schema=schema)


def test_succeeded_schema_rejects_failure_code() -> None:
    schema = load_schema(ROOT, "tasks/execution-audit-event.schema.json")
    candidate = deepcopy(_event("execution_succeeded"))
    candidate["metadata"]["failure_code"] = "contradictory_failure"

    with pytest.raises(ValidationError):
        validate(instance=candidate, schema=schema)


def test_succeeded_schema_rejects_nonzero_stderr_byte_count() -> None:
    schema = load_schema(ROOT, "tasks/execution-audit-event.schema.json")
    candidate = deepcopy(_event("execution_succeeded"))
    candidate["metadata"]["stderr_byte_count"] = 1

    with pytest.raises(ValidationError):
        validate(instance=candidate, schema=schema)


@pytest.mark.parametrize(
    "event_type",
    ("execution_failed", "execution_cancelled"),
)
def test_failed_and_cancelled_schema_require_failure_code(event_type: str) -> None:
    schema = load_schema(ROOT, "tasks/execution-audit-event.schema.json")
    candidate = deepcopy(_event(event_type))
    del candidate["metadata"]["failure_code"]

    with pytest.raises(ValidationError):
        validate(instance=candidate, schema=schema)


def test_doctor_registers_execution_audit_schema() -> None:
    assert "tasks/execution-audit-event.schema.json" in SCHEMA_FILES
    assert run_doctor(ROOT).status == "pass"
