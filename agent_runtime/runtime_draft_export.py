"""Dry-run and commit export for runtime plan envelope drafts.

This module implements the Controlled Write POC:

* ``runtime draft export --dry-run`` validates an envelope draft and prints a
  sanitized summary without writing the file.
* ``runtime draft export --commit`` writes the validated envelope to
  ``drafts/runtime/.../*.json`` and then re-validates / re-inspects the file.

No adapter execution, network access, messaging, or credential files are
involved.
"""

from __future__ import annotations

import importlib.util
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .loader import is_safe_to_read, normalize_path
from .policy import check_text
from .result import CheckResult, Finding
from .runtime_draft import (
    _build_draft_summary,
    _load_runtime_draft,
    _validate_envelope,
    inspect_runtime_draft,
    validate_runtime_draft,
)


# Reuse the public-scan rules from tools/public_scan.py without making ``tools``
# a package. The file is loaded once at import time because the rules are static.
_TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
_public_scan_spec = importlib.util.spec_from_file_location(
    "public_scan", _TOOLS_DIR / "public_scan.py"
)
_public_scan = importlib.util.module_from_spec(_public_scan_spec)
_public_scan_spec.loader.exec_module(_public_scan)
_PUBLIC_SCAN_RULES: list[dict[str, str]] = _public_scan.SCAN_RULES


@dataclass
class DraftExportResult:
    """Result of a draft export attempt (dry-run or commit)."""

    status: str
    source: str | None = None
    output: str | None = None
    would_write: bool = False
    committed: bool = False
    validation: str | None = None
    post_validate: str | None = None
    post_inspect: str | None = None
    artifact_counts: dict[str, int] = field(default_factory=dict)
    findings: list[Finding] = field(default_factory=list)
    next_action: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"status": self.status}
        if self.source is not None:
            d["source"] = self.source
        if self.output is not None:
            d["output"] = self.output
        d["would_write"] = self.would_write
        d["committed"] = self.committed
        if self.validation is not None:
            d["validation"] = self.validation
        if self.post_validate is not None:
            d["post_validate"] = self.post_validate
        if self.post_inspect is not None:
            d["post_inspect"] = self.post_inspect
        if self.artifact_counts:
            d["artifact_counts"] = self.artifact_counts
        if self.findings:
            d["findings"] = [f.to_dict() for f in self.findings]
        if self.next_action is not None:
            d["next_action"] = self.next_action
        return d


def _result_from_check_result(
    result: CheckResult, output: str | None = None
) -> DraftExportResult:
    """Convert a failing CheckResult into a DraftExportResult."""
    return DraftExportResult(
        status=result.status,
        output=output,
        findings=list(result.findings),
        next_action=result.next_action,
    )


def _validate_output_path(
    root: Path, output: str
) -> DraftExportResult | tuple[Path, str]:
    """Resolve and validate the output path.

    Returns ``(resolved_path, rel_path)`` on success, otherwise a blocked
    ``DraftExportResult``.
    """
    root = root.resolve()
    try:
        path = (root / output).resolve()
    except (OSError, ValueError):
        return DraftExportResult(
            status="blocked",
            output=output,
            findings=[
                Finding(
                    rule_id="output-path-invalid",
                    severity="block",
                    action="deny",
                    message="Output path is invalid.",
                )
            ],
            next_action="Provide a valid project-local .json output path.",
        )

    if path == root or root not in path.parents:
        return DraftExportResult(
            status="blocked",
            output=output,
            findings=[
                Finding(
                    rule_id="output-path-outside-root",
                    severity="block",
                    action="deny",
                    message="Output path must be inside the project root.",
                )
            ],
            next_action="Choose a path under the project root.",
        )

    rel_parts = path.relative_to(root).parts
    if ".." in rel_parts or any(str(part).startswith("..") for part in rel_parts):
        return DraftExportResult(
            status="blocked",
            output=output,
            findings=[
                Finding(
                    rule_id="output-path-escapes-root",
                    severity="block",
                    action="deny",
                    message="Output path must not escape the project root.",
                )
            ],
            next_action="Remove '..' segments from the output path.",
        )

    if path.suffix.lower() != ".json":
        return DraftExportResult(
            status="blocked",
            output=output,
            findings=[
                Finding(
                    rule_id="output-path-not-json",
                    severity="block",
                    action="deny",
                    message="Output file must use the .json extension.",
                )
            ],
            next_action="Change the output path to use .json.",
        )

    if not is_safe_to_read(path):
        return DraftExportResult(
            status="blocked",
            output=output,
            findings=[
                Finding(
                    rule_id="output-path-unsafe",
                    severity="block",
                    action="deny",
                    message="Output path points to a credential or unsafe file.",
                )
            ],
            next_action="Choose a safe .json file path.",
        )

    if any(part == ".git" for part in path.parts) or path.name.startswith(".git"):
        return DraftExportResult(
            status="blocked",
            output=output,
            findings=[
                Finding(
                    rule_id="output-path-points-to-git-internal",
                    severity="block",
                    action="deny",
                    message="Output path must not point to git internals.",
                )
            ],
            next_action="Choose a path outside .git/.",
        )

    if path.exists():
        return DraftExportResult(
            status="blocked",
            output=output,
            findings=[
                Finding(
                    rule_id="output-file-exists",
                    severity="block",
                    action="deny",
                    message="Output file already exists; overwrite is not allowed.",
                )
            ],
            next_action="Choose a new output path or remove the existing file first.",
        )

    rel_path = normalize_path(path.relative_to(root))
    return path, rel_path


def _validate_drafts_runtime_path(rel_output: str) -> DraftExportResult | None:
    """For commit mode, require the output to be under drafts/runtime/."""
    normalized = normalize_path(rel_output).lstrip("./").lower()
    if not normalized.startswith("drafts/runtime/"):
        return DraftExportResult(
            status="blocked",
            output=rel_output,
            findings=[
                Finding(
                    rule_id="output-path-not-in-drafts-runtime",
                    severity="block",
                    action="deny",
                    message="Commit output must be under drafts/runtime/.",
                )
            ],
            next_action="Choose an output path like drafts/runtime/<task-id>/<request-id>.envelope.json.",
        )
    return None


def _line_number(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


def _public_scan_text(text: str) -> list[Finding]:
    """Run public-release risk rules over a text string.

    Findings include the rule id and line number but never the matched text.
    """
    findings: list[Finding] = []
    for rule in _PUBLIC_SCAN_RULES:
        compiled = re.compile(rule["regex"])
        for match in compiled.finditer(text):
            line = _line_number(text, match.start())
            findings.append(
                Finding(
                    rule_id=rule["id"],
                    severity="block",
                    action="deny",
                    message=f"Public scan rule hit at line {line}: {rule['title']}",
                    line=line,
                )
            )
    return findings


def _scan_export_content(root: Path, envelope: dict[str, Any]) -> list[Finding]:
    """Run policy secret scan and public-release scan over the serialized envelope."""
    text = json.dumps(envelope, ensure_ascii=False, indent=2)
    findings: list[Finding] = []

    secret_result = check_text(root, text)
    for finding in secret_result.findings:
        # Override message so the matched secret is never echoed.
        finding.message = (
            f"Secret scan rule hit at line {finding.line or '?'}: "
            f"{finding.rule_id}"
        )
        findings.append(finding)

    findings.extend(_public_scan_text(text))
    return findings


def _write_envelope_file(path: Path, envelope: dict[str, Any]) -> DraftExportResult | None:
    """Serialize and write the envelope to path. Return error result on failure."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(envelope, ensure_ascii=False, indent=2) + "\n"
        path.write_text(text, encoding="utf-8")
    except OSError as exc:
        return DraftExportResult(
            status="error",
            output=normalize_path(path),
            findings=[
                Finding(
                    rule_id="write-failed",
                    severity="error",
                    action="error",
                    message=f"Could not write draft file: {exc}",
                )
            ],
            next_action="Check disk space and permissions.",
        )
    return None


def _rollback_file(path: Path, rel_output: str) -> DraftExportResult | None:
    """Delete a half-written file. Return error result if deletion fails."""
    try:
        path.unlink()
    except OSError as exc:
        return DraftExportResult(
            status="error",
            output=rel_output,
            findings=[
                Finding(
                    rule_id="rollback-failed",
                    severity="error",
                    action="error",
                    message=f"Post-write check failed and rollback failed: {exc}",
                )
            ],
            next_action="Manually remove the half-written draft file.",
        )
    return None


def _post_write_check(
    root: Path, rel_output: str
) -> DraftExportResult | tuple[str, str, dict[str, Any]]:
    """Validate and inspect the written file.

    Returns ``(post_validate, post_inspect, summary)`` on success, otherwise a
    failing ``DraftExportResult``.
    """
    validate_result = validate_runtime_draft(root, file=rel_output)
    if validate_result.status != "pass":
        return _result_from_check_result(validate_result, output=rel_output)

    inspect_result, summary = inspect_runtime_draft(root, file=rel_output)
    if inspect_result.status != "pass":
        return _result_from_check_result(inspect_result, output=rel_output)

    if summary is None:
        return DraftExportResult(
            status="error",
            output=rel_output,
            findings=[
                Finding(
                    rule_id="post-inspect-summary-missing",
                    severity="error",
                    action="error",
                    message="Post-write inspect did not produce a summary.",
                )
            ],
            next_action="Check the written draft file.",
        )

    return "pass", "pass", summary


def export_draft(
    root: Path,
    output: str,
    file: str | None = None,
    stdin: bool = False,
    commit: bool = False,
) -> DraftExportResult:
    """Dry-run or commit export an envelope draft to a project-local .json path.

    The function is read-only when ``commit=False``. When ``commit=True`` it
    writes a new file under ``drafts/runtime/...`` and then validates/inspects
    the written file, rolling back on failure.
    """
    loaded = _load_runtime_draft(root, file=file, stdin=stdin)
    if isinstance(loaded, CheckResult):
        return _result_from_check_result(loaded, output=output)

    envelope, source, outer = loaded
    validation_result = _validate_envelope(envelope, source, root)
    if validation_result.status != "pass":
        return _result_from_check_result(validation_result, output=output)

    path_guard = _validate_output_path(root, output)
    if isinstance(path_guard, DraftExportResult):
        return path_guard
    path, rel_output = path_guard

    if commit:
        drafts_guard = _validate_drafts_runtime_path(rel_output)
        if drafts_guard is not None:
            return drafts_guard

    scan_findings = _scan_export_content(root, envelope)
    if scan_findings:
        return DraftExportResult(
            status="blocked",
            source=source,
            output=rel_output,
            findings=scan_findings,
            next_action="Redact sensitive or public-release-risk content before exporting.",
        )

    summary = _build_draft_summary(envelope, source, outer=outer)

    if not commit:
        return DraftExportResult(
            status="pass",
            source=source,
            output=rel_output,
            would_write=False,
            validation="pass",
            artifact_counts=summary.get("artifact_counts", {}),
            next_action="Use --commit to persist the draft.",
        )

    # Commit path: write, then validate/inspect.
    if path.exists():
        return DraftExportResult(
            status="blocked",
            source=source,
            output=rel_output,
            findings=[
                Finding(
                    rule_id="output-file-exists",
                    severity="block",
                    action="deny",
                    message="Output file already exists; overwrite is not allowed.",
                )
            ],
            next_action="Choose a new output path or remove the existing file first.",
        )

    write_error = _write_envelope_file(path, envelope)
    if write_error is not None:
        return write_error

    post = _post_write_check(root, rel_output)
    if isinstance(post, DraftExportResult):
        rollback_error = _rollback_file(path, rel_output)
        if rollback_error is not None:
            return rollback_error
        post.source = source
        post.next_action = (
            "Draft was rolled back due to post-write check failure. "
            + (post.next_action or "")
        ).strip()
        return post

    post_validate, post_inspect, post_summary = post
    return DraftExportResult(
        status="pass",
        source=source,
        output=rel_output,
        committed=True,
        validation="pass",
        post_validate=post_validate,
        post_inspect=post_inspect,
        artifact_counts=post_summary.get("artifact_counts", {}),
        next_action="Draft committed; run runtime gate check before adapter execution.",
    )


def dry_run_export(
    root: Path,
    output: str,
    file: str | None = None,
    stdin: bool = False,
) -> DraftExportResult:
    """Dry-run export wrapper (kept for existing callers/tests)."""
    return export_draft(root, output, file=file, stdin=stdin, commit=False)
