"""Read-only recovery lineage aggregation for orchestration runs.

The projection consumes existing run lifecycle event metadata.  It does not
scan draft directories, write ledgers, persist snapshots, or execute adapters.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .tasks import load_events


_SCHEMA_VERSION = "control-plane/recovery-lineage/v1"
_RUN_EVENT_TYPES = {"run_planned", "run_draft_exported", "run_blocked"}
_METADATA_KEYS = (
    "plan_hash",
    "adapter_id",
    "envelope_path",
    "lineage_type",
    "retry_of",
    "fallback_from",
    "fallback_to",
)


@dataclass
class RecoveryLineageResult:
    """Safe, deterministic recovery lineage read model."""

    status: str
    task_id: str
    focus_request_id: str
    root_request_id: str | None = None
    latest_request_id: str | None = None
    leaf_request_ids: list[str] = field(default_factory=list)
    effective_plan_hash: str | None = None
    attempt_count: int = 0
    requests: list[dict[str, Any]] = field(default_factory=list)
    issues: list[dict[str, Any]] = field(default_factory=list)
    schema_version: str = _SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "status": self.status,
            "task_id": self.task_id,
            "focus_request_id": self.focus_request_id,
            "root_request_id": self.root_request_id,
            "latest_request_id": self.latest_request_id,
            "leaf_request_ids": self.leaf_request_ids,
            "effective_plan_hash": self.effective_plan_hash,
            "attempt_count": self.attempt_count,
            "requests": self.requests,
            "issues": self.issues,
        }


def _issue(code: str, **safe_ids: str) -> dict[str, Any]:
    issue: dict[str, Any] = {"code": code}
    issue.update({key: value for key, value in safe_ids.items() if value})
    return issue


def _merge_request_events(
    events: list[dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], set[str]]:
    records: dict[str, dict[str, Any]] = {}
    conflicts: set[str] = set()

    for event in events:
        if event.get("event_type") not in _RUN_EVENT_TYPES:
            continue
        metadata = event.get("metadata")
        if not isinstance(metadata, dict):
            continue
        request_id = metadata.get("request_id")
        task_id = event.get("task_id")
        if not isinstance(request_id, str) or not request_id:
            continue
        if not isinstance(task_id, str) or not task_id:
            continue

        incoming: dict[str, Any] = {"request_id": request_id, "task_id": task_id}
        for key in _METADATA_KEYS:
            value = metadata.get(key)
            if value is not None:
                incoming[key] = value

        current = records.setdefault(
            request_id,
            {
                "request_id": request_id,
                "task_id": task_id,
                "event_types": set(),
            },
        )
        current["event_types"].add(event.get("event_type"))

        if current.get("task_id") != task_id:
            conflicts.add(request_id)
            continue
        for key in _METADATA_KEYS:
            value = incoming.get(key)
            if value is None:
                continue
            existing = current.get(key)
            if existing is not None and existing != value:
                conflicts.add(request_id)
            else:
                current[key] = value

    return records, conflicts


def _parent_id(record: dict[str, Any]) -> str | None:
    if record.get("lineage_type") == "retry":
        return record.get("retry_of")
    if record.get("lineage_type") == "fallback":
        return record.get("fallback_from")
    return None


def _lineage_shape_issue(record: dict[str, Any]) -> dict[str, Any] | None:
    request_id = record["request_id"]
    lineage_type = record.get("lineage_type")
    retry_of = record.get("retry_of")
    fallback_from = record.get("fallback_from")
    fallback_to = record.get("fallback_to")

    valid = False
    if lineage_type is None:
        valid = retry_of is None and fallback_from is None and fallback_to is None
    elif lineage_type == "retry":
        valid = bool(retry_of) and fallback_from is None and fallback_to is None
    elif lineage_type == "fallback":
        valid = bool(fallback_from) and bool(fallback_to) and retry_of is None
    if valid:
        return None
    return _issue("invalid_lineage_shape", request_id=request_id)


def _safe_request_summary(record: dict[str, Any], *, is_root: bool) -> dict[str, Any]:
    relationship = "root" if is_root else record.get("lineage_type", "unknown")
    summary: dict[str, Any] = {
        "request_id": record["request_id"],
        "relationship": relationship,
        "status": (
            "blocked" if "run_blocked" in record.get("event_types", set()) else "planned"
        ),
    }
    parent = _parent_id(record)
    if parent is not None:
        summary["parent_request_id"] = parent
    for key in ("adapter_id", "plan_hash", "fallback_to"):
        value = record.get(key)
        if value is not None:
            summary[key] = value
    return summary


def aggregate_recovery_lineage(
    root: Path,
    *,
    task_id: str,
    request_id: str,
    events_file: str | None = None,
) -> RecoveryLineageResult:
    """Aggregate the recovery chain containing ``request_id`` from lifecycle events."""
    events = load_events(root, explicit_file=events_file)
    records, conflicts = _merge_request_events(events)

    focus = records.get(request_id)
    if focus is None or focus.get("task_id") != task_id:
        return RecoveryLineageResult(
            status="validation_failed",
            task_id=task_id,
            focus_request_id=request_id,
            issues=[_issue("focus_request_not_found", request_id=request_id)],
        )
    if request_id in conflicts:
        return RecoveryLineageResult(
            status="validation_failed",
            task_id=task_id,
            focus_request_id=request_id,
            issues=[_issue("conflicting_request_metadata", request_id=request_id)],
        )

    # Resolve the ancestor path and root without relying on timestamps.
    ancestor_ids: list[str] = []
    seen: set[str] = set()
    current = focus
    while True:
        current_id = current["request_id"]
        if current_id in seen:
            return RecoveryLineageResult(
                status="validation_failed",
                task_id=task_id,
                focus_request_id=request_id,
                issues=[_issue("cycle_detected", request_id=current_id)],
            )
        seen.add(current_id)
        ancestor_ids.append(current_id)

        if current_id in conflicts:
            return RecoveryLineageResult(
                status="validation_failed",
                task_id=task_id,
                focus_request_id=request_id,
                issues=[_issue("conflicting_request_metadata", request_id=current_id)],
            )
        shape_issue = _lineage_shape_issue(current)
        if shape_issue is not None:
            return RecoveryLineageResult(
                status="validation_failed",
                task_id=task_id,
                focus_request_id=request_id,
                issues=[shape_issue],
            )

        parent_id = _parent_id(current)
        if parent_id is None:
            root_id = current_id
            break
        parent = records.get(parent_id)
        if parent is None:
            return RecoveryLineageResult(
                status="validation_failed",
                task_id=task_id,
                focus_request_id=request_id,
                issues=[
                    _issue(
                        "missing_parent",
                        request_id=current_id,
                        parent_request_id=parent_id,
                    )
                ],
            )
        if parent.get("task_id") != task_id:
            return RecoveryLineageResult(
                status="validation_failed",
                task_id=task_id,
                focus_request_id=request_id,
                issues=[
                    _issue(
                        "cross_task_parent",
                        request_id=current_id,
                        parent_request_id=parent_id,
                    )
                ],
            )
        current = parent

    task_records = {
        rid: record for rid, record in records.items() if record.get("task_id") == task_id
    }
    children: dict[str, list[str]] = {}
    for rid, record in task_records.items():
        parent = _parent_id(record)
        if parent is not None:
            children.setdefault(parent, []).append(rid)
    for child_ids in children.values():
        child_ids.sort()

    # Traverse only the connected component rooted at the focus root.
    ordered_ids: list[str] = []
    queue = [root_id]
    visited: set[str] = set()
    while queue:
        current_id = queue.pop(0)
        if current_id in visited:
            return RecoveryLineageResult(
                status="validation_failed",
                task_id=task_id,
                focus_request_id=request_id,
                root_request_id=root_id,
                issues=[_issue("cycle_detected", request_id=current_id)],
            )
        visited.add(current_id)
        ordered_ids.append(current_id)
        queue.extend(children.get(current_id, []))

    for rid in ordered_ids:
        if rid in conflicts:
            return RecoveryLineageResult(
                status="validation_failed",
                task_id=task_id,
                focus_request_id=request_id,
                root_request_id=root_id,
                issues=[_issue("conflicting_request_metadata", request_id=rid)],
            )
        shape_issue = _lineage_shape_issue(task_records[rid])
        if shape_issue is not None:
            return RecoveryLineageResult(
                status="validation_failed",
                task_id=task_id,
                focus_request_id=request_id,
                root_request_id=root_id,
                issues=[shape_issue],
            )

    leaves = sorted(rid for rid in ordered_ids if not children.get(rid))
    latest = leaves[0] if len(leaves) == 1 else None
    issues: list[dict[str, Any]] = []
    status = "pass"
    if len(leaves) > 1:
        status = "needs_input"
        issues.append(_issue("ambiguous_leaves"))

    summaries = [
        _safe_request_summary(task_records[rid], is_root=(rid == root_id))
        for rid in ordered_ids
    ]
    effective_hash = task_records[latest].get("plan_hash") if latest is not None else None
    return RecoveryLineageResult(
        status=status,
        task_id=task_id,
        focus_request_id=request_id,
        root_request_id=root_id,
        latest_request_id=latest,
        leaf_request_ids=leaves,
        effective_plan_hash=effective_hash,
        attempt_count=len(ordered_ids),
        requests=summaries,
        issues=issues,
    )
