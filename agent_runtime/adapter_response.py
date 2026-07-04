"""Read-only adapter response status checker.

This module checks whether a specific adapter_request inside an already
validated execution envelope has a recorded adapter_response, and reports the
response/evidence status. It does not execute adapters, write ledgers, access
networks, or read credential files.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .adapter_validation import _load_envelope, validate_envelope_file
from .result import CheckResult, Finding


@dataclass
class ResponseCheckResult:
    """Result of checking the response status for a single adapter request."""

    status: str
    response: dict[str, Any] = field(default_factory=dict)
    findings: list[Finding] = field(default_factory=list)
    next_action: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"status": self.status}
        if self.response:
            d["response"] = self.response
        if self.findings:
            d["findings"] = [f.to_dict() for f in self.findings]
        if self.next_action is not None:
            d["next_action"] = self.next_action
        return d


def _response_summary(
    request_id: str,
    request: dict[str, Any],
    response: dict[str, Any] | None,
) -> dict[str, Any]:
    """Build a compact, input-free response summary."""
    summary: dict[str, Any] = {
        "request_id": request_id,
        "adapter_id": request.get("adapter_id"),
        "operation": request.get("operation"),
        "target": request.get("target"),
    }

    if response is not None:
        summary["response_id"] = response.get("response_id")
        summary["response_status"] = response.get("status")
        summary["artifact_count"] = len(response.get("artifacts", []))
        summary["evidence_count"] = len(response.get("evidence", []))
        summary["raw_ref_present"] = response.get("raw_ref") is not None
    else:
        summary["response_id"] = None
        summary["response_status"] = None
        summary["artifact_count"] = 0
        summary["evidence_count"] = 0
        summary["raw_ref_present"] = False

    return summary


def _missing_response_result(
    request_id: str,
    request: dict[str, Any],
) -> ResponseCheckResult:
    """Return a needs_input result when the request has no adapter_response."""
    return ResponseCheckResult(
        status="needs_input",
        response=_response_summary(request_id, request, None),
        findings=[
            Finding(
                rule_id="response-missing",
                severity="warn",
                action="needs_input",
                message=f"Request {request_id} has no adapter_response recorded.",
            )
        ],
        next_action="Wait for or record the adapter response before checking status.",
    )


def check_adapter_response(
    root: Path,
    file: str,
    request_id: str,
) -> ResponseCheckResult:
    """Check whether ``request_id`` has a recorded adapter_response and evidence.

    The envelope file is validated (schema + consistency) first. If validation
    fails, the returned result uses the same status/findings/next_action as
    ``validate_envelope_file`` and contains no ``response`` summary.

    This function is read-only: it opens the file, validates the envelope, and
    inspects the artifacts. It never executes adapters, writes ledgers, accesses
    networks, or reads credential files.
    """
    validation = validate_envelope_file(root, file)
    if validation.status != "pass":
        return ResponseCheckResult(
            status=validation.status,
            response={},
            findings=validation.findings,
            next_action=validation.next_action,
        )

    loaded = _load_envelope(root, file)
    if isinstance(loaded, CheckResult):
        # Defensive: validation passed, but re-loading failed (e.g. race).
        return ResponseCheckResult(
            status=loaded.status,
            response={},
            findings=loaded.findings,
            next_action=loaded.next_action,
        )

    envelope, _rel_path = loaded
    artifacts = envelope.get("artifacts", [])

    requests: dict[str, dict[str, Any]] = {}
    responses_by_request: dict[str, dict[str, Any]] = {}

    for artifact in artifacts:
        artifact_type = artifact.get("artifact_type")
        if artifact_type == "adapter_request":
            rid = artifact.get("request_id")
            if rid:
                requests[rid] = artifact
        elif artifact_type == "adapter_response":
            rid = artifact.get("request_id")
            if rid:
                responses_by_request[rid] = artifact

    request = requests.get(request_id)
    if request is None:
        return ResponseCheckResult(
            status="needs_input",
            response={"request_id": request_id},
            findings=[
                Finding(
                    rule_id="response-request-not-found",
                    severity="error",
                    action="needs_input",
                    message=f"Request {request_id} not found in envelope.",
                )
            ],
            next_action="Provide a request_id that exists in the envelope.",
        )

    response = responses_by_request.get(request_id)
    if response is None:
        return _missing_response_result(request_id, request)

    status = response.get("status")
    summary = _response_summary(request_id, request, response)

    if status == "succeeded":
        if summary["evidence_count"] > 0:
            return ResponseCheckResult(
                status="pass",
                response=summary,
                next_action="Response succeeded and evidence is present.",
            )
        return ResponseCheckResult(
            status="blocked",
            response=summary,
            findings=[
                Finding(
                    rule_id="response-evidence-missing",
                    severity="block",
                    action="blocked",
                    message=f"Response {response.get('response_id')} succeeded but has no evidence.",
                )
            ],
            next_action="Add evidence to the adapter_response before proceeding.",
        )

    if status == "blocked":
        return ResponseCheckResult(
            status="blocked",
            response=summary,
            findings=[
                Finding(
                    rule_id="response-blocked",
                    severity="block",
                    action="blocked",
                    message=f"Response {response.get('response_id')} was blocked.",
                )
            ],
            next_action="Investigate the blocked response; do not proceed without resolution.",
        )

    if status == "failed":
        return ResponseCheckResult(
            status="blocked",
            response=summary,
            findings=[
                Finding(
                    rule_id="response-failed",
                    severity="block",
                    action="blocked",
                    message=f"Response {response.get('response_id')} failed.",
                )
            ],
            next_action="Investigate the failure and retry or correct the adapter request.",
        )

    if status == "needs_approval":
        return ResponseCheckResult(
            status="needs_approval",
            response=summary,
            findings=[
                Finding(
                    rule_id="response-needs-approval",
                    severity="warn",
                    action="needs_approval",
                    message=f"Response {response.get('response_id')} needs approval.",
                )
            ],
            next_action="Obtain approval before proceeding with this response.",
        )

    if status == "needs_input":
        return ResponseCheckResult(
            status="needs_input",
            response=summary,
            findings=[
                Finding(
                    rule_id="response-needs-input",
                    severity="warn",
                    action="needs_input",
                    message=f"Response {response.get('response_id')} needs input.",
                )
            ],
            next_action="Provide the missing input and retry the adapter request.",
        )

    if status == "skipped":
        return ResponseCheckResult(
            status="blocked",
            response=summary,
            findings=[
                Finding(
                    rule_id="response-skipped",
                    severity="block",
                    action="blocked",
                    message=f"Response {response.get('response_id')} was skipped.",
                )
            ],
            next_action="A skipped response cannot be used as evidence of completion.",
        )

    # Unknown response status should have been caught by schema validation.
    return ResponseCheckResult(
        status="validation_failed",
        response=summary,
        findings=[
            Finding(
                rule_id="response-status-unknown",
                severity="error",
                action="error",
                message=f"Response {response.get('response_id')} has unrecognized status {status}.",
            )
        ],
        next_action="Fix the adapter_response status in the envelope.",
    )
