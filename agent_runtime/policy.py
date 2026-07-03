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


def check_text(
    root: Path,
    text: str,
    explicit_policy: Path | None = None,
    profile: str | None = None,
) -> CheckResult:
    """Scan text for configured secret patterns."""
    policies = load_policies(root, explicit=explicit_policy, profile=profile)
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
    profile: str | None = None,
) -> CheckResult:
    """Check a target path against path_rules."""
    policies = load_policies(root, explicit=explicit_policy, profile=profile)
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


def _action_status(action: str, severity: str) -> str:
    if action == "deny":
        return "blocked"
    if action == "require_user_approval":
        return "needs_approval"
    if action in {"require_secret_scan", "require_postflight"}:
        return "needs_input"
    return _severity_to_status(severity)


def _action_next_action(findings: list[Finding]) -> str | None:
    actions = {finding.action for finding in findings}
    steps: list[str] = []
    if "deny" in actions:
        steps.append("review or change the blocked operation")
    if "require_secret_scan" in actions:
        steps.append("run secret scan for the payload or diff")
    if "require_user_approval" in actions:
        steps.append("ask for approval for this task, target, and operation")
    if "require_postflight" in actions:
        steps.append("collect completion evidence or run postflight checks")
    if not steps:
        return None
    return "; ".join(steps) + "."


def _operation_aliases(adapter: dict[str, Any], operation: str) -> set[str]:
    aliases = {operation}
    kind = adapter.get("kind")
    if kind == "github":
        if operation in {"git_push", "push"}:
            aliases.add("git_push")
        if operation in {"issue_create", "issue_comment", "issue_edit", "gh_issue"}:
            aliases.add("gh_issue")
        if operation in {"pr_create", "pr_comment", "pr_edit", "gh_pr"}:
            aliases.add("gh_pr")
    if kind == "lark" and operation in {"send", "message_send", "card_send", "lark_message"}:
        aliases.add("lark_message")
    return aliases


def _is_completion_operation(operation: str) -> bool:
    return operation in {"finish", "finished", "mark_finished", "task_finish", "complete_task"}


def check_action(
    root: Path,
    adapter_id: str,
    operation: str,
    target: str | None = None,
    explicit_policy: Path | None = None,
    profile: str | None = None,
) -> CheckResult:
    """Check an action descriptor against adapters and policy rules."""
    adapters_data = load_adapters(root)
    policies = load_policies(root, explicit=explicit_policy, profile=profile)

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

    findings: list[Finding] = []
    risk_level = adapter.get("risk_level", "local")
    requires_approval = adapter.get("requires_approval", False)
    operation_aliases = _operation_aliases(adapter, operation)

    if risk_level == "external" or requires_approval:
        findings.append(
            Finding(
                rule_id=f"{adapter_id}-approval",
                severity="block",
                action="require_user_approval",
                message=f"{adapter_id}: this external operation requires explicit user approval.",
            )
        )

    for policy in policies:
        for rule in policy.get("command_rules", []):
            if not rule.get("enabled", True):
                continue
            try:
                compiled = re.compile(rule["regex"])
            except re.error:
                continue
            if compiled.search(operation) or (target and compiled.search(target)):
                findings.append(
                    Finding(
                        rule_id=rule["id"],
                        severity=rule.get("severity", "block"),
                        action=rule.get("action", "deny"),
                        message=rule.get("message", "Operation blocked by policy."),
                    )
                )

        for rule in policy.get("publish_rules", []):
            if not rule.get("enabled", True):
                continue
            applies_to = set(rule.get("applies_to", []))
            if not operation_aliases.intersection(applies_to):
                continue
            required_checks = ", ".join(rule.get("required_checks", []))
            suffix = f" Required checks: {required_checks}." if required_checks else ""
            findings.append(
                Finding(
                    rule_id=rule["id"],
                    severity=rule.get("severity", "block"),
                    action=rule.get("action", "require_secret_scan"),
                    message=rule.get("message", "Publishing action requires preflight checks.") + suffix,
                )
            )

        if _is_completion_operation(operation):
            for rule in policy.get("completion_rules", []):
                if not rule.get("enabled", True):
                    continue
                required_evidence = ", ".join(rule.get("required_evidence", []))
                suffix = f" Required evidence: {required_evidence}." if required_evidence else ""
                findings.append(
                    Finding(
                        rule_id=rule["id"],
                        severity=rule.get("severity", "warn"),
                        action=rule.get("action", "require_postflight"),
                        message=rule.get("message", "Completion requires evidence.") + suffix,
                    )
                )

    if findings:
        statuses = [_action_status(f.action, f.severity) for f in findings]
        return CheckResult(
            status=coalesce_status(statuses),
            findings=findings,
            next_action=_action_next_action(findings),
        )

    return CheckResult(status="pass")
