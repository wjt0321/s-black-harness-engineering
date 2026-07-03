"""Policy checker: text, path, and action checks."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .loader import load_adapters, load_policies, normalize_path
from .result import Finding, CheckResult, coalesce_status


def _compile_pattern(regex: str) -> re.Pattern[str]:
    return re.compile(regex)


def _line_col(text: str, pos: int) -> tuple[int, int]:
    line = text.count("\n", 0, pos) + 1
    last_nl = text.rfind("\n", 0, pos)
    col = pos - last_nl
    return line, col


def check_text(root: Path, text: str, explicit_policy: Path | None = None) -> CheckResult:
    """Scan text for configured secret patterns."""
    policies = load_policies(root, explicit=explicit_policy)
    findings: list[Finding] = []
    seen: set[tuple[int, int, str]] = set()  # de-duplicate by (line, col, rule)

    for policy in policies:
        for pattern in policy.get("secret_patterns", []):
            if not pattern.get("enabled", True):
                continue
            regex = pattern["regex"]
            try:
                compiled = _compile_pattern(regex)
            except re.error as exc:
                findings.append(
                    Finding(
                        rule_id=pattern.get("id", "invalid-regex"),
                        severity="error",
                        action="error",
                        message=f"Invalid regex: {exc}",
                    )
                )
                continue
            for match in compiled.finditer(text):
                line, col = _line_col(text, match.start())
                key = (line, col, pattern["id"])
                if key in seen:
                    continue
                seen.add(key)
                findings.append(
                    Finding(
                        rule_id=pattern["id"],
                        severity=pattern.get("severity", "block"),
                        action=pattern.get("action", "deny"),
                        message=pattern.get("message", "Potential secret detected."),
                        line=line,
                        column=col,
                    )
                )

    if findings:
        return CheckResult(
            status="blocked",
            findings=findings,
            next_action="Redact matched content and run check again.",
        )
    return CheckResult(status="pass")


def _normalize_pattern(value: str) -> str:
    """Normalize a pattern string the same way target paths are normalized."""
    return normalize_path(value).lstrip("./").rstrip("/")


def _match_path_rule(rule: dict[str, Any], normalized: str, path: Path) -> bool:
    match = rule.get("match", {})
    if "path_prefix" in match:
        prefix = _normalize_pattern(match["path_prefix"]) + "/"
        if not normalized.startswith(prefix) and normalized != prefix.rstrip("/"):
            return False
    if "path_contains" in match:
        if not any(_normalize_pattern(part) in normalized for part in match["path_contains"]):
            return False
    if "name_patterns" in match:
        name = path.name
        if not any(re.search(pat, name) for pat in match["name_patterns"]):
            return False
    if "extensions" in match:
        if path.suffix.lower() not in {ext.lower() for ext in match["extensions"]}:
            return False
    if "keywords_deny" in match:
        lower = normalized.lower()
        if not any(kw.lower() in lower for kw in match["keywords_deny"]):
            return False
    return True


def _operation_mode(write: bool, delete: bool, read: bool) -> str:
    if delete:
        return "delete"
    if write:
        return "write"
    return "read"


def _severity_to_status(severity: str) -> str:
    """Map rule severity to check status."""
    return {"info": "warn", "warn": "warn", "block": "blocked"}.get(severity, "blocked")


def check_path(
    root: Path,
    target: str,
    read: bool = False,
    write: bool = False,
    delete: bool = False,
    explicit_policy: Path | None = None,
) -> CheckResult:
    """Check a target path against path_rules."""
    policies = load_policies(root, explicit=explicit_policy)
    normalized = normalize_path(target).lstrip("./")
    path_obj = Path(target)
    mode = _operation_mode(write=write, delete=delete, read=read)
    findings: list[Finding] = []

    for policy in policies:
        for rule in policy.get("path_rules", []):
            if not rule.get("enabled", True):
                continue
            if not _match_path_rule(rule, normalized, path_obj):
                continue

            constraints = rule.get("constraints", {})
            readonly = constraints.get("readonly", False)
            deny_directories = constraints.get("deny_directories", False)
            allow_extensions = constraints.get("allow_extensions")
            deny_extensions = constraints.get("deny_extensions")

            if mode in ("write", "delete") and readonly:
                findings.append(
                    Finding(
                        rule_id=rule["id"],
                        severity=rule.get("severity", "block"),
                        action=rule.get("action", "deny"),
                        message=rule.get("message", "Target path is read-only under current policy."),
                    )
                )
                continue

            if deny_directories and not path_obj.suffix:
                findings.append(
                    Finding(
                        rule_id=rule["id"],
                        severity=rule.get("severity", "block"),
                        action=rule.get("action", "deny"),
                        message=rule.get("message", "Directories are not allowed here."),
                    )
                )
                continue

            ext = path_obj.suffix.lower()
            if allow_extensions is not None and ext and ext not in {e.lower() for e in allow_extensions}:
                findings.append(
                    Finding(
                        rule_id=rule["id"],
                        severity=rule.get("severity", "block"),
                        action=rule.get("action", "deny"),
                        message=rule.get("message", f"Extension '{path_obj.suffix}' is not allowed here."),
                    )
                )
                continue

            if deny_extensions is not None and ext and ext in {e.lower() for e in deny_extensions}:
                findings.append(
                    Finding(
                        rule_id=rule["id"],
                        severity=rule.get("severity", "block"),
                        action=rule.get("action", "deny"),
                        message=rule.get("message", f"Extension '{path_obj.suffix}' is denied here."),
                    )
                )
                continue

    if findings:
        statuses = [_severity_to_status(f.severity) for f in findings]
        status = coalesce_status(statuses)
        if status == "pass":
            status = "blocked"  # a finding implies non-pass
        return CheckResult(
            status=status,
            findings=findings,
            next_action="Choose an allowed path or request explicit authorization.",
        )
    return CheckResult(status="pass")


def check_action(
    root: Path,
    adapter_id: str,
    operation: str,
    target: str | None = None,
    explicit_policy: Path | None = None,
) -> CheckResult:
    """Check an action descriptor against adapters and policy rules."""
    adapters_data = load_adapters(root)
    policies = load_policies(root, explicit=explicit_policy)

    adapter = next(
        (a for a in adapters_data.get("adapters", []) if a.get("id") == adapter_id),
        None,
    )
    if adapter is None:
        return CheckResult(
            status="error",
            findings=[
                Finding(
                    rule_id="adapter-not-found",
                    severity="error",
                    action="error",
                    message=f"Adapter '{adapter_id}' not found in registry.",
                )
            ],
            next_action="Register the adapter or check the adapter id.",
        )

    risk_level = adapter.get("risk_level", "local")
    requires_approval = adapter.get("requires_approval", False)

    # Simple heuristic rules from docs/09-policy-checker-poc-plan.md
    if risk_level == "external" or requires_approval:
        return CheckResult(
            status="needs_approval",
            findings=[
                Finding(
                    rule_id=f"{adapter_id}-approval",
                    severity="block",
                    action="require_user_approval",
                    message=f"{adapter_id}: this external operation requires explicit user approval.",
                )
            ],
            next_action="Ask for approval for this task, this target, this operation.",
        )

    # Check command rules for operation string matches
    for policy in policies:
        for rule in policy.get("command_rules", []):
            if not rule.get("enabled", True):
                continue
            try:
                compiled = re.compile(rule["regex"])
            except re.error:
                continue
            if compiled.search(operation) or (target and compiled.search(target)):
                return CheckResult(
                    status="blocked",
                    findings=[
                        Finding(
                            rule_id=rule["id"],
                            severity=rule.get("severity", "block"),
                            action=rule.get("action", "deny"),
                            message=rule.get("message", "Operation blocked by policy."),
                        )
                    ],
                    next_action="Review the blocked operation before proceeding.",
                )

    return CheckResult(status="pass")
