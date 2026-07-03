"""Read-only validation for adapter execution envelope JSON files."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import validate, ValidationError as JsonSchemaValidationError

from .loader import is_safe_to_read, load_schema, normalize_path
from .result import CheckResult, Finding


ENVELOPE_SCHEMA_PATH = "adapters/execution-envelope.schema.json"


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


def validate_envelope_file(
    root: Path,
    file: str,
) -> CheckResult:
    """Validate an adapter execution envelope JSON file against its schema.

    This function is read-only: it opens the file, validates the envelope, and
    returns a result. It never executes adapters, writes ledgers, or reads
    credential files.
    """
    schema = load_schema(root, ENVELOPE_SCHEMA_PATH)
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
        with open(path, "r", encoding="utf-8") as fh:
            raw = fh.read()
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

    return CheckResult(
        status="pass",
        findings=[],
        next_action=f"Envelope {rel_path} passed schema validation.",
    )
