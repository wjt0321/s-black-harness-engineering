"""Read-only validation for adapter execution envelope JSON files."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import validate, ValidationError as JsonSchemaValidationError

from .loader import is_safe_to_read, load_schema, normalize_path
from .result import CheckResult, Finding


ENVELOPE_SCHEMA_PATH = "adapters/execution-envelope.schema.json"


def _load_envelope(
    root: Path,
    file: str,
) -> tuple[dict[str, Any], str] | CheckResult:
    """Resolve, safety-check, and read an envelope JSON file.

    Returns the parsed envelope and its root-relative path, or a
    ``CheckResult`` when the file cannot be loaded safely.
    """
    root = root.resolve()
    path = (root / file).resolve()

    if path != root and root not in path.parents:
        return CheckResult(
            status="error",
            findings=[
                Finding(
                    rule_id="path-outside-root",
                    severity="error",
                    action="error",
                    message="Envelope file must be inside the project root.",
                )
            ],
            next_action="Choose a project-local envelope JSON file.",
        )

    rel_path = normalize_path(path.relative_to(root))

    if not is_safe_to_read(path) or path.suffix.lower() != ".json":
        return CheckResult(
            status="error",
            findings=[
                Finding(
                    rule_id="unsafe-envelope-file",
                    severity="error",
                    action="error",
                    message="Envelope file must be a safe JSON file.",
                )
            ],
            next_action="Choose a project-local envelope JSON file.",
        )

    if not path.is_file():
        return CheckResult(
            status="error",
            findings=[
                Finding(
                    rule_id="file-not-found",
                    severity="error",
                    action="error",
                    message=f"Envelope file not found: {rel_path}",
                )
            ],
            next_action="Check the envelope file path.",
        )

    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        return CheckResult(
            status="error",
            findings=[
                Finding(
                    rule_id="read-error",
                    severity="error",
                    action="error",
                    message=f"Could not read {rel_path}: {exc}",
                )
            ],
            next_action="Check file permissions.",
        )

    try:
        envelope = json.loads(raw)
    except json.JSONDecodeError as exc:
        return CheckResult(
            status="validation_failed",
            findings=[
                Finding(
                    rule_id="invalid-json",
                    severity="error",
                    action="error",
                    message=f"Invalid JSON in {rel_path}: {exc.msg} at line {exc.lineno}, col {exc.colno}",
                    line=exc.lineno,
                    column=exc.colno,
                )
            ],
            next_action="Fix the JSON syntax before validating.",
        )

    return envelope, rel_path


def _safe_error_message(exc: JsonSchemaValidationError) -> str:
    """Return a short, value-free validation error summary."""
    path = ".".join(str(part) for part in exc.path) if exc.path else "(root)"
    validator = exc.validator or "schema"

    if validator == "required":
        parts = exc.message.split("'")
        field = parts[1] if len(parts) >= 2 else path
        return f"required field missing: {field} at {path}"
    if validator == "enum":
        return f"value not in allowed enum at {path}"
    if validator == "type":
        return f"type mismatch at {path}"
    if validator == "pattern":
        return f"pattern mismatch at {path}"
    if validator == "additionalProperties":
        return f"unexpected field at {path}"
    if validator == "format":
        return f"format error at {path}"
    if validator == "oneOf":
        return f"artifact does not match any allowed shape at {path}"
    if validator == "const":
        return f"constant value mismatch at {path}"

    return f"validation failed at {path}"


def _check_envelope_consistency(
    envelope: dict[str, Any],
    rel_path: str,
) -> CheckResult | None:
    """Check cross-artifact references inside an already schema-valid envelope.

    Returns None when no consistency issues are found, otherwise a
    CheckResult with status ``validation_failed``.
    """
    artifacts = envelope.get("artifacts", [])

    requests: dict[str, dict[str, Any]] = {}
    request_ids_seen: set[str] = set()
    approvals: dict[str, dict[str, Any]] = {}

    for artifact in artifacts:
        artifact_type = artifact.get("artifact_type")
        if artifact_type == "adapter_request":
            request_id = artifact.get("request_id")
            if request_id in request_ids_seen:
                return CheckResult(
                    status="validation_failed",
                    findings=[
                        Finding(
                            rule_id="duplicate-request-id",
                            severity="error",
                            action="error",
                            message=f"{rel_path}: duplicate adapter_request.request_id {request_id}",
                        )
                    ],
                    next_action="Ensure every adapter_request has a unique request_id.",
                )
            request_ids_seen.add(request_id)
            requests[request_id] = artifact
        elif artifact_type == "approval_record":
            approval_id = artifact.get("approval_id")
            approvals[approval_id] = artifact

    findings: list[Finding] = []

    def _finding(rule_id: str, message: str) -> Finding:
        return Finding(
            rule_id=rule_id,
            severity="error",
            action="error",
            message=message,
        )

    for artifact in artifacts:
        artifact_type = artifact.get("artifact_type")
        if artifact_type == "approval_record":
            request_id = artifact.get("request_id")
            if request_id not in requests:
                findings.append(
                    _finding(
                        "approval-references-unknown-request",
                        f"{rel_path}: approval_record {artifact.get('approval_id')} references unknown request_id {request_id}",
                    )
                )
                continue
            request = requests[request_id]
            scope = artifact.get("scope", {})
            for field in ("task_id", "adapter_id", "operation", "target"):
                if scope.get(field) != request.get(field):
                    findings.append(
                        _finding(
                            "approval-scope-mismatch",
                            f"{rel_path}: approval_record {artifact.get('approval_id')} scope.{field} does not match adapter_request {request_id}",
                        )
                    )
        elif artifact_type == "adapter_response":
            request_id = artifact.get("request_id")
            if request_id not in requests:
                findings.append(
                    _finding(
                        "response-references-unknown-request",
                        f"{rel_path}: adapter_response {artifact.get('response_id')} references unknown request_id {request_id}",
                    )
                )
        elif artifact_type == "execution_event":
            request_id = artifact.get("request_id")
            if request_id not in requests:
                findings.append(
                    _finding(
                        "event-references-unknown-request",
                        f"{rel_path}: execution_event {artifact.get('event_id')} references unknown request_id {request_id}",
                    )
                )
            if artifact.get("event_type") == "approval_requested":
                approval_id = artifact.get("metadata", {}).get("approval_id")
                if approval_id is not None and approval_id not in approvals:
                    findings.append(
                        _finding(
                            "approval-requested-event-unknown-approval",
                            f"{rel_path}: execution_event {artifact.get('event_id')} metadata.approval_id references unknown approval_record {approval_id}",
                        )
                    )

    for request_id, request in requests.items():
        context = request.get("context", {})
        preflight = request.get("preflight", {})
        if context.get("requires_approval") and preflight.get("status") == "needs_approval":
            has_approval = any(
                a.get("request_id") == request_id
                and a.get("status") in ("pending", "granted")
                for a in approvals.values()
            )
            if not has_approval:
                findings.append(
                    _finding(
                        "needs-approval-missing-record",
                        f"{rel_path}: adapter_request {request_id} requires approval but has no pending/granted approval_record",
                    )
                )

    if findings:
        return CheckResult(
            status="validation_failed",
            findings=findings,
            next_action="Fix envelope artifact references and approval coverage before execution.",
        )
    return None


def validate_envelope_file(
    root: Path,
    file: str,
) -> CheckResult:
    """Validate an adapter execution envelope JSON file against its schema.

    This function is read-only: it opens the file, validates the envelope, and
    returns a result. It never executes adapters, writes ledgers, or reads
    credential files.
    """
    loaded = _load_envelope(root, file)
    if isinstance(loaded, CheckResult):
        return loaded

    envelope, rel_path = loaded
    schema = load_schema(root, ENVELOPE_SCHEMA_PATH)

    try:
        validate(instance=envelope, schema=schema)
    except JsonSchemaValidationError as exc:
        return CheckResult(
            status="validation_failed",
            findings=[
                Finding(
                    rule_id="envelope-schema-validation-failed",
                    severity="error",
                    action="error",
                    message=f"{rel_path}: {_safe_error_message(exc)}",
                )
            ],
            next_action="Fix the envelope structure before execution.",
        )

    consistency_result = _check_envelope_consistency(envelope, rel_path)
    if consistency_result is not None:
        return consistency_result

    return CheckResult(
        status="pass",
        findings=[],
        next_action=f"Envelope {rel_path} passed schema and consistency validation.",
    )


def _artifact_summary(artifact: dict[str, Any]) -> dict[str, Any]:
    """Return a compact, value-safe summary of an artifact."""
    artifact_type = artifact.get("artifact_type")
    if artifact_type == "adapter_request":
        context = artifact.get("context", {})
        preflight = artifact.get("preflight", {})
        return {
            "request_id": artifact.get("request_id"),
            "adapter_id": artifact.get("adapter_id"),
            "operation": artifact.get("operation"),
            "target": artifact.get("target"),
            "preflight_status": preflight.get("status"),
            "requires_approval": bool(context.get("requires_approval")),
        }
    if artifact_type == "approval_record":
        return {
            "approval_id": artifact.get("approval_id"),
            "request_id": artifact.get("request_id"),
            "status": artifact.get("status"),
        }
    if artifact_type == "adapter_response":
        return {
            "response_id": artifact.get("response_id"),
            "request_id": artifact.get("request_id"),
            "status": artifact.get("status"),
            "evidence_count": len(artifact.get("evidence", [])),
        }
    return {}


def _build_envelope_summary(envelope: dict[str, Any]) -> dict[str, Any]:
    """Build a compact summary of a validated envelope."""
    artifacts = envelope.get("artifacts", [])

    artifact_counts: dict[str, int] = {}
    requests: list[dict[str, Any]] = []
    approvals: list[dict[str, Any]] = []
    responses: list[dict[str, Any]] = []
    event_counts: dict[str, int] = {}

    requires_approval_count = 0
    pending_approval_count = 0
    response_count = 0
    evidence_count = 0

    for artifact in artifacts:
        artifact_type = artifact.get("artifact_type", "unknown")
        artifact_counts[artifact_type] = artifact_counts.get(artifact_type, 0) + 1

        summary = _artifact_summary(artifact)
        if artifact_type == "adapter_request":
            requests.append(summary)
            if summary["requires_approval"]:
                requires_approval_count += 1
        elif artifact_type == "approval_record":
            approvals.append(summary)
            if summary["status"] == "pending":
                pending_approval_count += 1
        elif artifact_type == "adapter_response":
            responses.append(summary)
            response_count += 1
            evidence_count += summary["evidence_count"]
        elif artifact_type == "execution_event":
            event_type = artifact.get("event_type", "unknown")
            event_counts[event_type] = event_counts.get(event_type, 0) + 1

    overall = {
        "requires_approval_count": requires_approval_count,
        "pending_approval_count": pending_approval_count,
        "response_count": response_count,
        "evidence_count": evidence_count,
    }

    return {
        "version": envelope.get("version"),
        "description": envelope.get("description"),
        "artifact_counts": artifact_counts,
        "requests": requests,
        "approvals": approvals,
        "responses": responses,
        "events": event_counts,
        "overall": overall,
    }


def inspect_envelope_file(
    root: Path,
    file: str,
) -> tuple[CheckResult, dict[str, Any] | None]:
    """Inspect an adapter execution envelope JSON file and return a summary.

    The file is validated first (schema + consistency). If validation fails,
    the returned summary is ``None`` and the ``CheckResult`` carries the same
    status/exit code as ``validate_envelope_file``. On success, a compact,
    value-safe summary is returned alongside a passing ``CheckResult``.

    This function is read-only and never executes adapters, writes ledgers, or
    reads credential files.
    """
    result = validate_envelope_file(root, file)
    if result.status != "pass":
        return result, None

    loaded = _load_envelope(root, file)
    if isinstance(loaded, CheckResult):
        return loaded, None

    envelope, rel_path = loaded
    summary = _build_envelope_summary(envelope)
    return (
        CheckResult(
            status="pass",
            findings=[],
            next_action=f"Envelope {rel_path} inspected.",
        ),
        summary,
    )
