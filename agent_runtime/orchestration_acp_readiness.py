"""Bounded read-only ACP runner readiness evidence collection."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, SchemaError, ValidationError, validate

from .loader import normalize_path
from .orchestration_socket import get_socket
from .result import EXIT_ERROR, EXIT_PASS, EXIT_VALIDATION_FAILED, Finding

BINDINGS_FILE = "adapters/acp-runner-bindings.sample.json"
BINDINGS_SCHEMA = "adapters/acp-runner-bindings.schema.json"
SNAPSHOT_SCHEMA = "adapters/acp-runner-state-snapshot.schema.json"
EVIDENCE_SCHEMA = "adapters/acp-readiness-evidence-v2.schema.json"
SCHEMA_VERSION = "control-plane/acp-readiness-collection/v1"
_MAX_BYTES = 64 * 1024
_MAX_TTL_SECONDS = 900


def _finding(rule_id: str, message: str) -> Finding:
    return Finding(rule_id=rule_id, severity="block", action="deny", message=message)


def _parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timezone required")
    return parsed.astimezone(timezone.utc)


def _load_json(root: Path, relative: str) -> tuple[dict[str, Any] | None, str | None]:
    base = root.resolve()
    path = (base / relative).resolve()
    if path == base or base not in path.parents or path.suffix.lower() != ".json":
        return None, "path"
    try:
        if not path.is_file() or path.stat().st_size > _MAX_BYTES:
            return None, "unavailable"
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None, "unreadable"
    return (value, None) if isinstance(value, dict) else (None, "malformed")


def _schema(root: Path, relative: str) -> dict[str, Any]:
    value = json.loads((root / relative).read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(value)
    return value


@dataclass(frozen=True)
class AcpReadinessResult:
    status: str
    source_file: str | None = None
    evidence: dict[str, Any] | None = None
    findings: tuple[Finding, ...] = ()

    def exit_code(self) -> int:
        if self.status == "pass":
            return EXIT_PASS
        if self.status == "validation_failed":
            return EXIT_VALIDATION_FAILED
        return EXIT_ERROR

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "status": self.status,
            "schema_version": SCHEMA_VERSION,
            "guarantees": {
                "deterministic": True,
                "read_only": True,
                "starts_runner": False,
                "opens_session": False,
                "sends_prompt": False,
                "invokes_model": False,
                "reads_credentials": False,
                "accesses_network": False,
                "writes_files": False,
                "grants_execution_authority": False,
            },
        }
        if self.source_file:
            payload["source"] = {"snapshot_file": self.source_file}
        if self.evidence:
            payload["evidence"] = self.evidence
        if self.findings:
            payload["findings"] = [item.to_dict() for item in self.findings]
        payload["next_action"] = {
            "code": "bind_readiness_evidence" if self.status == "pass" else "fix_readiness_input",
            "message": "Evidence may be inspected or bound; it does not authorize dispatch.",
        }
        return payload


def collect_acp_readiness(
    root: Path,
    socket_id: str,
    snapshot_file: str,
    evaluated_at: str,
    ttl_seconds: int = 300,
) -> AcpReadinessResult:
    """Collect runner-list evidence without contacting or starting a runner."""
    if ttl_seconds < 1 or ttl_seconds > _MAX_TTL_SECONDS:
        return AcpReadinessResult("validation_failed", findings=(_finding("readiness-ttl-invalid", "TTL must be between 1 and 900 seconds."),))
    snapshot, error = _load_json(root, snapshot_file)
    if error or snapshot is None:
        return AcpReadinessResult("validation_failed", findings=(_finding("readiness-snapshot-invalid", "Snapshot must be project-local bounded JSON."),))
    bindings, binding_error = _load_json(root, BINDINGS_FILE)
    try:
        validate(snapshot, _schema(root, SNAPSHOT_SCHEMA))
        validate(bindings, _schema(root, BINDINGS_SCHEMA))
        observed = _parse_time(snapshot["observed_at"])
        evaluated = _parse_time(evaluated_at)
    except (OSError, json.JSONDecodeError, SchemaError, ValidationError, ValueError, TypeError):
        return AcpReadinessResult("validation_failed", findings=(_finding("readiness-contract-invalid", "Readiness schema, binding, or timestamp validation failed."),))
    if binding_error or bindings is None:
        return AcpReadinessResult("validation_failed", findings=(_finding("readiness-bindings-invalid", "ACP runner bindings are unavailable."),))
    if evaluated < observed:
        return AcpReadinessResult("validation_failed", findings=(_finding("readiness-time-invalid", "Evaluation time cannot precede observation time."),))

    socket_result = get_socket(root, socket_id)
    socket = socket_result.socket
    if socket is None or socket.get("invocation_mode") != "acp_delegate" or not socket.get("enabled"):
        return AcpReadinessResult("validation_failed", findings=(_finding("readiness-socket-ineligible", "Socket must be an enabled ACP delegate."),))
    binding = next((item for item in bindings["bindings"] if item["socket_id"] == socket_id), None)
    if binding is None:
        return AcpReadinessResult("validation_failed", findings=(_finding("readiness-binding-missing", "Socket has no ACP runner binding."),))
    runner = next((item for item in snapshot["runners"] if item["runner_id"] == binding["runner_id"]), None)
    expires = observed + timedelta(seconds=ttl_seconds)
    available = runner is not None and evaluated <= expires
    body = {
        "version": 2,
        "contract": "socket-readiness/acp-session/v1",
        "socket_id": socket_id,
        "runner_id": binding["runner_id"],
        "status": "available" if available else "unknown",
        "level": "runner_listed" if runner is not None else "runner_missing",
        "observed_at": snapshot["observed_at"],
        "evaluated_at": evaluated_at,
        "expires_at": expires.isoformat().replace("+00:00", "Z"),
        "session_state": runner["session_state"] if runner is not None else "not_observed",
        "sufficient_for_dispatch": False,
        "probe_actions": snapshot["probe_actions"],
    }
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    evidence = {**body, "evidence_id": f"sha256:{hashlib.sha256(canonical).hexdigest()}"}
    try:
        validate(evidence, _schema(root, EVIDENCE_SCHEMA))
    except (OSError, json.JSONDecodeError, SchemaError, ValidationError):
        return AcpReadinessResult("error", findings=(_finding("readiness-evidence-invalid", "Generated readiness evidence failed its contract."),))
    return AcpReadinessResult("pass", normalize_path(Path(snapshot_file)), evidence)
