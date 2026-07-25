"""Stage 52 Pi Coding Agent host preflight bridge.

One-shot stdin/stdout JSON bridge for a Pi TypeScript extension. The bridge
accepts a single bounded ``pi-bridge/preflight-request/v1`` document on stdin,
normalizes it, evaluates the request against the existing Harness policy
surface (``policy.check_path`` / ``policy.check_text`` / ``policy.check_action``)
and emits a single deterministic ``pi-bridge/preflight-response/v1`` document
with a stable decision: ``pass`` / ``needs_approval`` / ``blocked`` / ``invalid``.

Hard boundaries (v1):

- The bridge never executes the requested read/write/edit/bash tool.
- It does not read the target files, does not write files or ledgers, does not
  access the network, and does not start services.
- It never echoes input values: no paths, commands, or file contents appear in
  the response. Correlation happens through request/target SHA-256 digests.
- Any internal failure fails closed with decision ``blocked``.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, BinaryIO, TextIO

from .loader import is_safe_to_read
from .policy import check_action, check_path, check_text
from .result import CheckResult

REQUEST_SCHEMA_VERSION = "pi-bridge/preflight-request/v1"
RESPONSE_SCHEMA_VERSION = "pi-bridge/preflight-response/v1"
BRIDGE_ID = "pi-host-preflight-bridge/v1"
ADAPTER_ID = "pi-host"

MAX_INPUT_BYTES = 64 * 1024
MAX_JSON_DEPTH = 16
MAX_TARGET_CHARS = 4096
MAX_CONTENT_CHARS = 48 * 1024
MAX_EDIT_ENTRIES = 16
MAX_REQUEST_ID_CHARS = 128
MAX_FINDINGS = 64

TOOLS = ("read", "write", "edit", "bash")
_TOOL_INPUT_FIELDS: dict[str, frozenset[str]] = {
    "read": frozenset({"path"}),
    "write": frozenset({"path", "content"}),
    "edit": frozenset({"path", "edits"}),
    "bash": frozenset({"command"}),
}
_CONTENT_FIELDS = {"content"}
_EDIT_ENTRY_FIELDS = frozenset({"old_string", "new_string"})

_REQUEST_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")

_EXIT_CODES = {
    "pass": 0,
    "needs_approval": 3,
    "blocked": 2,
    "invalid": 5,
}

_GUARANTEES = {
    "executes_tools": False,
    "writes_files": False,
    "writes_ledgers": False,
    "accesses_network": False,
    "reads_target_files": False,
    "echoes_input_values": False,
}

_NEXT_ACTIONS = {
    "pass": ("proceed", "Preflight passed; the host may let the tool call proceed."),
    "needs_approval": (
        "request_user_approval",
        "Policy requires explicit user approval before this tool call may proceed.",
    ),
    "blocked": ("do_not_execute", "Policy blocks this tool call; do not execute it."),
    "invalid": ("fix_request", "The preflight request is malformed; fix it and retry the preflight."),
}


class DuplicateJSONKeyError(ValueError):
    """Raised when the request JSON contains a repeated object key."""


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateJSONKeyError
        result[key] = value
    return result


def _sha256_text(value: str) -> str:
    return f"sha256:{hashlib.sha256(value.encode('utf-8')).hexdigest()}"


def _canonical_hash(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return _sha256_text(canonical)


def _json_depth(value: Any, depth: int = 0) -> int:
    if isinstance(value, dict):
        if not value:
            return depth + 1
        return max(_json_depth(item, depth + 1) for item in value.values())
    if isinstance(value, list):
        if not value:
            return depth + 1
        return max(_json_depth(item, depth + 1) for item in value)
    return depth


def _finding(rule_id: str, message: str, *, severity: str = "block", action: str = "deny") -> dict[str, str]:
    return {"rule_id": rule_id, "severity": severity, "action": action, "message": message}


def _dedupe_findings(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Drop duplicate findings (same rule from multiple policies), keep order."""
    seen: set[tuple[str, str, str, str]] = set()
    unique: list[dict[str, Any]] = []
    for finding in findings:
        key = (
            str(finding.get("rule_id")),
            str(finding.get("severity")),
            str(finding.get("action")),
            str(finding.get("message")),
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(finding)
    return unique


def _response(
    decision: str,
    *,
    findings: list[dict[str, Any]],
    checks: list[dict[str, str]],
    request_id: str | None = None,
    request_hash: str | None = None,
    tool: str | None = None,
    target_hash: str | None = None,
) -> tuple[dict[str, Any], int]:
    code, message = _NEXT_ACTIONS[decision]
    payload: dict[str, Any] = {
        "schema_version": RESPONSE_SCHEMA_VERSION,
        "bridge": BRIDGE_ID,
        "decision": decision,
        "request_id": request_id,
        "request_hash": request_hash,
        "tool": tool,
        "target_hash": target_hash,
        "checks": checks,
        "findings": _dedupe_findings(findings)[:MAX_FINDINGS],
        "next_action": {"code": code, "message": message},
        "guarantees": dict(_GUARANTEES),
    }
    return payload, _EXIT_CODES[decision]


def _invalid(
    rule_id: str,
    message: str,
    *,
    checks: list[dict[str, str]] | None = None,
) -> tuple[dict[str, Any], int]:
    return _response(
        "invalid",
        findings=[_finding(rule_id, message)],
        checks=checks if checks is not None else [{"id": "input_gate", "status": "blocked"}],
    )


def _read_and_parse(raw: bytes) -> tuple[dict[str, Any] | None, tuple[dict[str, Any], int] | None]:
    """Bounded input gate: size, UTF-8, non-empty, JSON, duplicate keys, depth."""
    if len(raw) > MAX_INPUT_BYTES:
        return None, _invalid(
            "pi-bridge-input-too-large",
            "The preflight request exceeds the 64 KiB input limit.",
        )
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return None, _invalid(
            "pi-bridge-input-not-utf8",
            "The preflight request must be valid UTF-8.",
        )
    if not text.strip():
        return None, _invalid(
            "pi-bridge-empty-input",
            "The bridge requires one preflight request JSON document on stdin.",
        )
    try:
        document = json.loads(text, object_pairs_hook=_reject_duplicate_keys)
    except DuplicateJSONKeyError:
        return None, _invalid(
            "pi-bridge-duplicate-json-key",
            "The preflight request JSON contains a duplicate object key.",
        )
    except json.JSONDecodeError:
        return None, _invalid(
            "pi-bridge-invalid-json",
            "The preflight request is not valid JSON.",
        )
    if not isinstance(document, dict):
        return None, _invalid(
            "pi-bridge-invalid-shape",
            "The preflight request must be a single JSON object.",
        )
    if _json_depth(document) > MAX_JSON_DEPTH:
        return None, _invalid(
            "pi-bridge-json-too-deep",
            "The preflight request JSON nesting exceeds the depth limit.",
        )
    return document, None


def _validate_edit_entries(
    value: Any,
    gate_checks: list[dict[str, str]],
) -> tuple[dict[str, Any], int] | None:
    """Validate the edit tool's edits list; returns an error tuple or None."""
    if (
        not isinstance(value, list)
        or not value
        or len(value) > MAX_EDIT_ENTRIES
    ):
        return _invalid(
            "pi-bridge-invalid-field-value",
            "edits must be a non-empty list within the entry limit.",
            checks=gate_checks,
        )
    for entry in value:
        if not isinstance(entry, dict) or set(entry) != _EDIT_ENTRY_FIELDS:
            return _invalid(
                "pi-bridge-invalid-shape",
                "Each edits entry must be an object with exactly old_string and new_string.",
                checks=gate_checks,
            )
        for field_name in sorted(_EDIT_ENTRY_FIELDS):
            item = entry[field_name]
            if (
                not isinstance(item, str)
                or not item
                or len(item) > MAX_CONTENT_CHARS
                or "\x00" in item
            ):
                return _invalid(
                    "pi-bridge-invalid-field-value",
                    "edits entries must be non-empty, NUL-free strings within the size limit.",
                    checks=gate_checks,
                )
    return None


def _validate_shape(
    document: dict[str, Any],
) -> tuple[dict[str, Any] | None, tuple[dict[str, Any], int] | None]:
    """Strict request shape validation. Returns (normalized_request, error)."""
    gate_checks = [{"id": "input_gate", "status": "pass"}]

    allowed_keys = {"schema_version", "request_id", "tool", "input"}
    unknown = sorted(set(document) - allowed_keys)
    if unknown:
        return None, _invalid(
            "pi-bridge-unknown-field",
            "The preflight request contains unknown top-level fields.",
            checks=gate_checks,
        )

    if document.get("schema_version") != REQUEST_SCHEMA_VERSION:
        return None, _invalid(
            "pi-bridge-unsupported-schema-version",
            f"schema_version must be '{REQUEST_SCHEMA_VERSION}'.",
            checks=gate_checks,
        )

    request_id = document.get("request_id")
    if request_id is not None:
        if (
            not isinstance(request_id, str)
            or len(request_id) > MAX_REQUEST_ID_CHARS
            or not _REQUEST_ID_RE.fullmatch(request_id)
        ):
            return None, _invalid(
                "pi-bridge-invalid-request-id",
                "request_id must match [A-Za-z0-9._:-] and stay within 128 characters.",
                checks=gate_checks,
            )

    tool = document.get("tool")
    if not isinstance(tool, str) or tool not in _TOOL_INPUT_FIELDS:
        return None, _invalid(
            "pi-bridge-unknown-tool",
            "tool must be one of: read, write, edit, bash.",
            checks=gate_checks,
        )

    tool_input = document.get("input")
    if not isinstance(tool_input, dict):
        return None, _invalid(
            "pi-bridge-invalid-shape",
            "input must be an object with the tool-specific minimal fields.",
            checks=gate_checks,
        )

    expected = _TOOL_INPUT_FIELDS[tool]
    unknown_input = sorted(set(tool_input) - expected)
    if unknown_input:
        return None, _invalid(
            "pi-bridge-unknown-field",
            "input contains fields outside the tool-specific minimal set.",
            checks=gate_checks,
        )
    missing = sorted(expected - set(tool_input))
    if missing:
        return None, _invalid(
            "pi-bridge-missing-field",
            "input is missing required tool-specific fields.",
            checks=gate_checks,
        )

    for field_name in sorted(expected):
        value = tool_input[field_name]
        if field_name == "edits":
            edit_error = _validate_edit_entries(value, gate_checks)
            if edit_error is not None:
                return None, edit_error
            continue
        if not isinstance(value, str):
            return None, _invalid(
                "pi-bridge-invalid-field-type",
                "path, command and content fields must be strings.",
                checks=gate_checks,
            )
        limit = MAX_CONTENT_CHARS if field_name in _CONTENT_FIELDS else MAX_TARGET_CHARS
        if not value or len(value) > limit or "\x00" in value:
            return None, _invalid(
                "pi-bridge-invalid-field-value",
                "Fields must be non-empty, NUL-free and within the size limit.",
                checks=gate_checks,
            )

    normalized: dict[str, Any] = {
        "schema_version": REQUEST_SCHEMA_VERSION,
        "tool": tool,
        "input": {name: tool_input[name] for name in sorted(expected)},
    }
    if request_id is not None:
        normalized["request_id"] = request_id
    return normalized, None


def _target_basename(target: str) -> str:
    """Return the final path component for both POSIX and Windows style paths."""
    name = PurePosixPath(target).name
    return PureWindowsPath(name).name


def _is_sensitive_target(target: str) -> bool:
    return not is_safe_to_read(Path(_target_basename(target)))


def _safe_findings(result: CheckResult) -> list[dict[str, Any]]:
    """Project policy findings to value-safe fields only (no input echo)."""
    return [
        {
            "rule_id": finding.rule_id,
            "severity": finding.severity,
            "action": finding.action,
            "message": finding.message,
        }
        for finding in result.findings
    ]


def _evaluate(
    root: Path,
    tool: str,
    tool_input: dict[str, Any],
) -> tuple[str, list[dict[str, str]], list[dict[str, Any]]]:
    """Run the Harness policy surface for one normalized request.

    Returns (decision, checks, findings). Never raises; internal failures map
    to a fail-closed ``blocked`` decision.
    """
    checks: list[dict[str, str]] = [{"id": "input_gate", "status": "pass"}]
    findings: list[dict[str, Any]] = []

    target = tool_input.get("path") or tool_input.get("command") or ""

    if tool in {"read", "write", "edit"} and _is_sensitive_target(tool_input["path"]):
        checks.append({"id": "sensitive_target", "status": "blocked"})
        findings.append(
            _finding(
                "pi-bridge-sensitive-target",
                "The target is a credential or environment file class that the bridge never allows.",
            )
        )
        return "blocked", checks, findings
    checks.append({"id": "sensitive_target", "status": "pass"})

    try:
        results: list[tuple[str, CheckResult]] = []
        if tool in {"read", "write", "edit"}:
            path = tool_input["path"]
            results.append(
                (
                    "path_policy",
                    check_path(root, path, read=(tool == "read"), write=(tool in {"write", "edit"})),
                )
            )
            if tool == "write":
                results.append(("secret_scan", check_text(root, tool_input["content"])))
            if tool == "edit":
                edits = tool_input["edits"]
                payload_text = "\n".join(
                    piece
                    for entry in edits
                    for piece in (entry["old_string"], entry["new_string"])
                )
                results.append(("secret_scan", check_text(root, payload_text)))
        else:
            command = tool_input["command"]
            results.append(("secret_scan", check_text(root, command)))

        results.append(
            (
                "action_policy",
                check_action(root, ADAPTER_ID, tool, target=target),
            )
        )
    except Exception:  # noqa: BLE001 - fail closed without leaking internals
        checks.append({"id": "policy_evaluation", "status": "error"})
        findings.append(
            _finding(
                "pi-bridge-internal-error",
                "The bridge could not complete policy evaluation; failing closed.",
                severity="error",
                action="error",
            )
        )
        return "blocked", checks, findings

    rank = {
        "pass": 0,
        "warn": 1,
        "needs_input": 2,
        "needs_approval": 3,
        "blocked": 4,
        "validation_failed": 4,
        "error": 5,
    }
    worst = 0
    for check_id, result in results:
        status = result.status if result.status in rank else "error"
        checks.append({"id": check_id, "status": status})
        findings.extend(_safe_findings(result))
        worst = max(worst, rank[status])

    if worst >= rank["error"]:
        decision = "blocked"
        findings.append(
            _finding(
                "pi-bridge-policy-backend-error",
                "A policy backend reported an error; failing closed.",
                severity="error",
                action="error",
            )
        )
    elif worst >= rank["blocked"]:
        decision = "blocked"
    elif worst >= rank["needs_input"]:
        decision = "needs_approval"
    else:
        decision = "pass"
    return decision, checks, findings


def run_preflight_bridge(root: Path, raw: bytes) -> tuple[dict[str, Any], int]:
    """Evaluate one raw stdin payload and return (response_payload, exit_code).

    The function is deterministic and side-effect free: it only reads policy
    and adapter registry files under ``root``.
    """
    document, error = _read_and_parse(raw)
    if error is not None:
        return error
    assert document is not None

    normalized, error = _validate_shape(document)
    if error is not None:
        return error
    assert normalized is not None

    tool = normalized["tool"]
    tool_input = normalized["input"]
    request_id = normalized.get("request_id")
    request_hash = _canonical_hash(normalized)
    target = tool_input.get("path") or tool_input.get("command") or ""
    target_hash = _sha256_text(target)

    decision, checks, findings = _evaluate(root, tool, tool_input)
    return _response(
        decision,
        findings=findings,
        checks=checks,
        request_id=request_id,
        request_hash=request_hash,
        tool=tool,
        target_hash=target_hash,
    )


def run_preflight_bridge_io(root: Path, stdin: BinaryIO, stdout: TextIO) -> int:
    """Read one request from ``stdin``, write one JSON response to ``stdout``."""
    try:
        raw = stdin.read(MAX_INPUT_BYTES + 1)
    except OSError:
        raw = b""
    try:
        payload, exit_code = run_preflight_bridge(root, raw)
    except Exception:  # noqa: BLE001 - the bridge must always emit JSON
        payload, exit_code = _response(
            "blocked",
            findings=[
                _finding(
                    "pi-bridge-internal-error",
                    "The bridge hit an unexpected internal error; failing closed.",
                    severity="error",
                    action="error",
                )
            ],
            checks=[{"id": "input_gate", "status": "not_run"}],
        )
    json.dump(payload, stdout, ensure_ascii=False, indent=2)
    stdout.write("\n")
    return exit_code
