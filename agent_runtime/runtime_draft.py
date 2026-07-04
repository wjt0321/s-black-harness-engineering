"""Read-only validation and inspection for runtime plan envelope drafts.

Supports two input shapes produced by ``runtime plan --draft-json``:

* Direct envelope: ``{"version": 1, "artifacts": [...]}``
* Outer wrapper: ``{"status": "...", "envelope_draft": {...}}``

The module never executes adapters, writes ledgers, accesses networks, or reads
credential files.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from jsonschema import validate, ValidationError as JsonSchemaValidationError

from .adapter_validation import (
    _check_envelope_consistency,
    _load_envelope,
    _safe_error_message,
    ENVELOPE_SCHEMA_PATH,
)
from .loader import load_schema
from .result import CheckResult, Finding


def _read_stdin() -> CheckResult | str:
    """Read raw JSON from stdin, returning it or a CheckResult on failure."""
    try:
        raw = sys.stdin.read()
    except OSError as exc:
        return CheckResult(
            status="error",
            findings=[
                Finding(
                    rule_id="stdin-read-error",
                    severity="error",
                    action="error",
                    message=f"Could not read stdin: {exc}",
                )
            ],
            next_action="Check stdin availability.",
        )

    if not raw.strip():
        return CheckResult(
            status="error",
            findings=[
                Finding(
                    rule_id="stdin-empty",
                    severity="error",
                    action="error",
                    message="Stdin input is empty.",
                )
            ],
            next_action="Provide a runtime draft JSON via stdin.",
        )
    return raw


def _extract_envelope(data: Any) -> tuple[dict[str, Any] | None, CheckResult | None]:
    """Extract the inner envelope from either a direct envelope or outer wrapper.

    Returns ``(envelope, None)`` on success, otherwise ``(None, CheckResult)``.
    """
    if not isinstance(data, dict):
        return None, CheckResult(
            status="validation_failed",
            findings=[
                Finding(
                    rule_id="invalid-envelope-shape",
                    severity="error",
                    action="error",
                    message="Runtime draft must be a JSON object.",
                )
            ],
            next_action="Provide a direct envelope or a runtime plan --draft-json wrapper.",
        )

    if "envelope_draft" in data:
        envelope = data["envelope_draft"]
        if not isinstance(envelope, dict):
            return None, CheckResult(
                status="validation_failed",
                findings=[
                    Finding(
                        rule_id="envelope-draft-not-object",
                        severity="error",
                        action="error",
                        message="envelope_draft must be a JSON object.",
                    )
                ],
                next_action="Check the runtime plan --draft-json output shape.",
            )
        if "version" not in envelope or "artifacts" not in envelope:
            return None, CheckResult(
                status="validation_failed",
                findings=[
                    Finding(
                        rule_id="envelope-draft-invalid",
                        severity="error",
                        action="error",
                        message="envelope_draft is missing required envelope fields.",
                    )
                ],
                next_action="Ensure envelope_draft contains version and artifacts.",
            )
        return envelope, None

    if "version" in data and "artifacts" in data:
        return data, None

    return None, CheckResult(
        status="validation_failed",
        findings=[
            Finding(
                rule_id="invalid-envelope-shape",
                severity="error",
                action="error",
                message="JSON does not contain a valid envelope or envelope_draft.",
            )
        ],
        next_action="Provide a direct envelope or a runtime plan --draft-json wrapper.",
    )


def _load_runtime_draft(
    root: Path,
    file: str | None = None,
    stdin: bool = False,
) -> tuple[dict[str, Any], str, dict[str, Any] | None] | CheckResult:
    """Load a runtime draft envelope and return (envelope, source, outer_wrapper).

    ``source`` is a root-relative path for files or ``"<stdin>"`` for stdin.
    ``outer_wrapper`` is the original outer JSON when ``envelope_draft`` was
    used; otherwise ``None``.
    """
    if file is not None and stdin:
        return CheckResult(
            status="error",
            findings=[
                Finding(
                    rule_id="conflicting-input-source",
                    severity="error",
                    action="error",
                    message="Provide either --file or --stdin, not both.",
                )
            ],
            next_action="Choose a single input source.",
        )

    if file is not None:
        loaded = _load_envelope(root, file)
        if isinstance(loaded, CheckResult):
            return loaded
        data, source = loaded
    elif stdin:
        raw = _read_stdin()
        if isinstance(raw, CheckResult):
            return raw
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            return CheckResult(
                status="validation_failed",
                findings=[
                    Finding(
                        rule_id="invalid-json",
                        severity="error",
                        action="error",
                        message=f"Invalid JSON from stdin: {exc.msg} at line {exc.lineno}, col {exc.colno}",
                        line=exc.lineno,
                        column=exc.colno,
                    )
                ],
                next_action="Fix the JSON syntax before validating.",
            )
        source = "<stdin>"
    else:
        return CheckResult(
            status="error",
            findings=[
                Finding(
                    rule_id="missing-input-source",
                    severity="error",
                    action="error",
                    message="Provide either --file or --stdin.",
                )
            ],
            next_action="Specify the runtime draft input source.",
        )

    outer = data if isinstance(data, dict) and "envelope_draft" in data else None
    envelope, error = _extract_envelope(data)
    if error is not None:
        return error
    return envelope, source, outer


def _validate_envelope(envelope: dict[str, Any], source: str, root: Path) -> CheckResult:
    """Run schema + consistency validation on an already-extracted envelope."""
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
                    message=f"{source}: {_safe_error_message(exc)}",
                )
            ],
            next_action="Fix the envelope draft structure before execution.",
        )

    consistency_result = _check_envelope_consistency(envelope, source)
    if consistency_result is not None:
        return consistency_result

    return CheckResult(
        status="pass",
        findings=[],
        next_action=f"Runtime draft from {source} passed schema and consistency validation.",
    )


def validate_runtime_draft(
    root: Path,
    file: str | None = None,
    stdin: bool = False,
) -> CheckResult:
    """Validate a runtime plan envelope draft.

    Validates the inner envelope against ``adapters/execution-envelope.schema.json``
    and runs the same cross-artifact consistency checks as ``adapter validate``.
    Returns a ``CheckResult`` with status ``pass`` or ``validation_failed``.
    """
    loaded = _load_runtime_draft(root, file=file, stdin=stdin)
    if isinstance(loaded, CheckResult):
        return loaded

    envelope, source, _outer = loaded
    return _validate_envelope(envelope, source, root)


def _artifact_summary(artifact: dict[str, Any]) -> dict[str, Any]:
    """Return a compact, draft-focused summary of an artifact."""
    artifact_type = artifact.get("artifact_type")
    if artifact_type == "adapter_request":
        context = artifact.get("context", {})
        preflight = artifact.get("preflight", {})
        return {
            "request_id": artifact.get("request_id"),
            "adapter_id": artifact.get("adapter_id"),
            "operation": artifact.get("operation"),
            "preflight_status": preflight.get("status"),
            "requires_approval": bool(context.get("requires_approval")),
            "risk_level": context.get("risk_level"),
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


def _build_draft_summary(
    envelope: dict[str, Any],
    source: str,
    outer: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a compact, value-safe summary of a runtime envelope draft."""
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
    task_id: str | None = None

    for artifact in artifacts:
        artifact_type = artifact.get("artifact_type", "unknown")
        artifact_counts[artifact_type] = artifact_counts.get(artifact_type, 0) + 1

        summary = _artifact_summary(artifact)
        if artifact_type == "adapter_request":
            requests.append(summary)
            if summary.get("requires_approval"):
                requires_approval_count += 1
            if task_id is None:
                task_id = artifact.get("task_id")
        elif artifact_type == "approval_record":
            approvals.append(summary)
            if summary.get("status") == "pending":
                pending_approval_count += 1
        elif artifact_type == "adapter_response":
            responses.append(summary)
            response_count += 1
            evidence_count += summary.get("evidence_count", 0)
        elif artifact_type == "execution_event":
            event_type = artifact.get("event_type", "unknown")
            event_counts[event_type] = event_counts.get(event_type, 0) + 1

    overall = {
        "requires_approval_count": requires_approval_count,
        "pending_approval_count": pending_approval_count,
        "response_count": response_count,
        "evidence_count": evidence_count,
    }

    result: dict[str, Any] = {
        "source": source,
        "version": envelope.get("version"),
        "description": envelope.get("description"),
        "artifact_counts": artifact_counts,
        "requests": requests,
        "approvals": approvals,
        "responses": responses,
        "events": event_counts,
        "overall": overall,
    }

    if outer is not None and outer.get("task_id") is not None:
        result["task_id"] = outer["task_id"]
    elif task_id is not None:
        result["task_id"] = task_id

    if outer is not None and outer.get("status") is not None:
        result["status"] = outer["status"]

    return result


def inspect_runtime_draft(
    root: Path,
    file: str | None = None,
    stdin: bool = False,
) -> tuple[CheckResult, dict[str, Any] | None]:
    """Inspect a runtime plan envelope draft and return a value-safe summary.

    The draft is loaded once, validated, and summarized. On validation failure
    the returned summary is ``None`` and the ``CheckResult`` carries the failure
    status. On success a compact summary is returned.
    """
    loaded = _load_runtime_draft(root, file=file, stdin=stdin)
    if isinstance(loaded, CheckResult):
        return loaded, None

    envelope, source, outer = loaded
    result = _validate_envelope(envelope, source, root)
    if result.status != "pass":
        return result, None

    summary = _build_draft_summary(envelope, source, outer=outer)
    return (
        CheckResult(
            status="pass",
            findings=[],
            next_action=f"Runtime draft from {source} inspected.",
        ),
        summary,
    )
