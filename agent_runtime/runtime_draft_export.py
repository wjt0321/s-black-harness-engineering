"""Read-only dry-run export for runtime plan envelope drafts.

This module implements the first step of the Controlled Write POC:
``runtime draft export --dry-run``. It validates an envelope draft, guards the
output path, scans the serialized envelope for secrets and public-release risks,
and returns a sanitized dry-run summary. It never writes the output file.
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
    """Result of a dry-run draft export attempt."""

    status: str
    source: str | None = None
    output: str | None = None
    would_write: bool = False
    validation: str | None = None
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
        if self.validation is not None:
            d["validation"] = self.validation
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


def dry_run_export(
    root: Path,
    output: str,
    file: str | None = None,
    stdin: bool = False,
) -> DraftExportResult:
    """Dry-run export an envelope draft to a project-local .json path.

    The function is read-only: it loads the draft, validates the envelope,
    guards the output path, scans the content for secrets and public-release
    risks, and returns a sanitized summary. It never writes the output file.
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
    _path, rel_output = path_guard

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
    return DraftExportResult(
        status="pass",
        source=source,
        output=rel_output,
        would_write=False,
        validation="pass",
        artifact_counts=summary.get("artifact_counts", {}),
        next_action="Use --commit to persist the draft (not yet implemented).",
    )
