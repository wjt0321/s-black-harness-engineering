"""Bounded fixed-path reader for external-Agent live status snapshots."""

from __future__ import annotations

import hashlib
import json
import math
import os
import stat
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, BinaryIO

from jsonschema import Draft202012Validator, FormatChecker, SchemaError, ValidationError, validate

from .result import EXIT_BLOCKED, EXIT_ERROR, EXIT_PASS, Finding

SCHEMA_VERSION = "control-plane/external-agent-live-status-inspection/v1"
FIXED_SNAPSHOT_PATH = Path(".runtime/external-agent-status/omp-acp.v1.json")
_BINDING_PATH = Path("adapters/external-agent-live-status-binding.json")
_BINDING_SCHEMA_PATH = Path("adapters/external-agent-live-status-binding.schema.json")
_SNAPSHOT_SCHEMA_PATH = Path("adapters/external-agent-status-snapshot.schema.json")
_EVIDENCE_SCHEMA_PATH = Path("adapters/external-agent-live-status-evidence.schema.json")
_GUI_SCHEMA_PATH = Path("adapters/external-agent-live-read-model.schema.json")
_FILE_ATTRIBUTE_REPARSE_POINT = 0x400
_REVIEWED_CONTRACT_DIGESTS = {
    _BINDING_SCHEMA_PATH: "sha256:d68fd38cf63aeee074460059e30ea3e6755ad1ef484c9caf8938759d3ace68fd",
    _BINDING_PATH: "sha256:d2a930dcc452bfcf6624ef115ca8153b12fc0f8a5f0dfbc36a59f34460e2abb7",
    _SNAPSHOT_SCHEMA_PATH: "sha256:f260aed697f67e4e6f4536c44309affa75d589103a9a7053208cbf53669abf23",
    _EVIDENCE_SCHEMA_PATH: "sha256:423ab29887b225c00441d0b0e64500c5b7e0d6c16b3651c25fc818c221297b95",
    _GUI_SCHEMA_PATH: "sha256:9a5e0fa168b752e2cf4b1436189d397783a046b9dd8408b368bc0029f603c5fa",
}

_SAFE_MESSAGES = {
    "status_source_missing": "固定状态快照不存在。",
    "status_source_not_regular": "状态源不是普通文件。",
    "status_source_indirection_blocked": "状态源使用了不允许的文件间接层。",
    "status_source_too_large": "状态源超过 64 KiB。",
    "status_source_unreadable": "状态源无法按 UTF-8 单次读取。",
    "status_source_schema_invalid": "状态源不符合严格 schema。",
    "status_snapshot_incomplete": "状态快照未完成原子发布。",
    "status_snapshot_replayed": "generation 未前进或 snapshot 已重放。",
    "status_observation_from_future": "观察时间晚于评估时间。",
    "status_observation_expired": "观察已超过 TTL。",
    "status_identity_binding_mismatch": "Agent、adapter 或 transport identity 漂移。",
    "status_producer_binding_missing": "缺少已审阅 producer binding。",
    "status_producer_binding_drift": "Producer version 或 binding 已漂移。",
    "status_target_not_observed": "目标 runner 未出现在快照中。",
    "status_unbound_session_observed": "观察到 open session，但不存在 Harness run/attempt mapping。",
    "status_projection_invalid": "生成的 GUI 投影不符合 Stage 82 contract。",
}


class _ReadFailure(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class _DuplicateKeyError(ValueError):
    pass


def _finding(code: str) -> Finding:
    return Finding(
        rule_id=code,
        severity="block" if code != "status_snapshot_replayed" and code != "status_observation_expired" and code != "status_target_not_observed" else "warn",
        action="deny" if code not in {"status_snapshot_replayed", "status_observation_expired", "status_target_not_observed"} else "retry",
        message=_SAFE_MESSAGES[code],
    )


def _document_digest(value: dict[str, Any]) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _canonical_digest(value: dict[str, Any], id_field: str) -> str:
    body = {key: item for key, item in value.items() if key != id_field}
    encoded = json.dumps(
        body,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateKeyError
        result[key] = value
    return result


def _reject_constant(_value: str) -> None:
    raise ValueError("non-finite JSON constant")


def _parse_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError("non-finite JSON number")
    return parsed


def _strict_json(data: bytes) -> dict[str, Any]:
    text = data.decode("utf-8")
    value = json.loads(
        text,
        object_pairs_hook=_reject_duplicate_keys,
        parse_constant=_reject_constant,
        parse_float=_parse_float,
    )
    if not isinstance(value, dict):
        raise ValueError("top-level object required")
    return value


def _parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timezone required")
    return parsed.astimezone(timezone.utc)


def _format_time(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _identity(info: os.stat_result) -> tuple[int, int]:
    return info.st_dev, info.st_ino


def _version(info: os.stat_result) -> tuple[int, int]:
    return info.st_size, info.st_mtime_ns


def _is_reparse(info: os.stat_result) -> bool:
    return bool(getattr(info, "st_file_attributes", 0) & _FILE_ATTRIBUTE_REPARSE_POINT)


def _check_parent_components(root: Path, path: Path) -> None:
    current = root
    for part in path.relative_to(root).parts[:-1]:
        current = current / part
        try:
            info = current.lstat()
        except FileNotFoundError as exc:
            raise _ReadFailure("status_source_missing") from exc
        except OSError as exc:
            raise _ReadFailure("status_source_unreadable") from exc
        if stat.S_ISLNK(info.st_mode) or _is_reparse(info):
            raise _ReadFailure("status_source_indirection_blocked")
        if not stat.S_ISDIR(info.st_mode):
            raise _ReadFailure("status_source_not_regular")


def _verify_path_identity(path: Path, expected: os.stat_result) -> os.stat_result:
    try:
        current = path.lstat()
    except FileNotFoundError as exc:
        raise _ReadFailure("status_source_unreadable") from exc
    except OSError as exc:
        raise _ReadFailure("status_source_unreadable") from exc
    if stat.S_ISLNK(current.st_mode) or _is_reparse(current) or current.st_nlink != 1:
        raise _ReadFailure("status_source_indirection_blocked")
    if not stat.S_ISREG(current.st_mode):
        raise _ReadFailure("status_source_not_regular")
    if _identity(current) != _identity(expected):
        raise _ReadFailure("status_source_unreadable")
    return current


def _open_snapshot(path: Path) -> BinaryIO:
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags)
    except FileNotFoundError as exc:
        raise _ReadFailure("status_source_missing") from exc
    except OSError as exc:
        raise _ReadFailure("status_source_unreadable") from exc
    return os.fdopen(descriptor, "rb", closefd=True)


def _read_fixed_snapshot(root: Path, max_bytes: int) -> bytes:
    base = root.resolve()
    path = base / FIXED_SNAPSHOT_PATH
    if base not in path.parents:
        raise _ReadFailure("status_source_indirection_blocked")
    _check_parent_components(base, path)
    try:
        before = path.lstat()
    except FileNotFoundError as exc:
        raise _ReadFailure("status_source_missing") from exc
    except OSError as exc:
        raise _ReadFailure("status_source_unreadable") from exc
    if stat.S_ISLNK(before.st_mode) or _is_reparse(before) or before.st_nlink != 1:
        raise _ReadFailure("status_source_indirection_blocked")
    if not stat.S_ISREG(before.st_mode):
        raise _ReadFailure("status_source_not_regular")
    if before.st_size > max_bytes:
        raise _ReadFailure("status_source_too_large")

    try:
        with _open_snapshot(path) as handle:
            opened = os.fstat(handle.fileno())
            if not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1 or _is_reparse(opened):
                raise _ReadFailure("status_source_indirection_blocked")
            if _identity(opened) != _identity(before):
                raise _ReadFailure("status_source_unreadable")
            _verify_path_identity(path, opened)
            data = handle.read(max_bytes + 1)
            after_handle = os.fstat(handle.fileno())
        after_path = _verify_path_identity(path, opened)
    except _ReadFailure:
        raise
    except OSError as exc:
        raise _ReadFailure("status_source_unreadable") from exc

    if len(data) > max_bytes:
        raise _ReadFailure("status_source_too_large")
    if _version(opened) != _version(after_handle) or _version(opened) != _version(after_path):
        raise _ReadFailure("status_source_unreadable")
    return data


def _load_contract(root: Path, path: Path) -> dict[str, Any]:
    data = (root / path).read_bytes()
    if len(data) > 65536:
        raise ValueError("contract too large")
    return _strict_json(data)


def _load_binding(root: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    documents = {
        path: _load_contract(root, path)
        for path in _REVIEWED_CONTRACT_DIGESTS
    }
    for path, expected_digest in _REVIEWED_CONTRACT_DIGESTS.items():
        if _document_digest(documents[path]) != expected_digest:
            raise ValueError("reviewed contract drift")
    binding = documents[_BINDING_PATH]
    binding_schema = documents[_BINDING_SCHEMA_PATH]
    snapshot_schema = documents[_SNAPSHOT_SCHEMA_PATH]
    evidence_schema = documents[_EVIDENCE_SCHEMA_PATH]
    gui_schema = documents[_GUI_SCHEMA_PATH]
    for schema in (binding_schema, snapshot_schema, evidence_schema, gui_schema):
        Draft202012Validator.check_schema(schema)
    validate(binding, binding_schema, format_checker=FormatChecker())
    return binding, snapshot_schema, evidence_schema, gui_schema


def _blocked_projection(binding: dict[str, Any] | None) -> dict[str, Any]:
    target = (binding or {}).get("expected_target", {})
    transport = target.get(
        "transport",
        {"transport_id": "qwenpaw-acp-runner-omp", "kind": "acp", "protocol_version": "acp/v1"},
    )
    return {
        "agent_id": target.get("agent_id", "omp-pi-acp"),
        "adapter_id": target.get("adapter_id", "omp-acp"),
        "display_name_zh": "OMP/Pi 外部 Agent",
        "status": "blocked",
        "status_label_zh": "状态证据绑定无效",
        "transport": transport,
        "capabilities": [{"capability_id": "live_status.observe", "roles": ["executor"], "label_zh": "只读状态观察"}],
        "readiness": {
            "status": "blocked",
            "status_label_zh": "状态证据绑定无效",
            "evidence_id": None,
            "expires_at": None,
            "binding_valid": False,
            "safe_summary_zh": "固定状态快照未通过只读安全校验。",
        },
        "session": None,
        "current_work_item_id": None,
        "blocked_reason_code": "readiness_binding_drift",
        "safe_summary_zh": "外部 Agent 状态不可安全投影。",
    }


def _projection(evidence: dict[str, Any]) -> dict[str, Any]:
    mapping = {
        "observed": ("unknown", "unknown", None, "Runner 已列出，未证明就绪"),
        "unavailable": ("disconnected", "unknown", "transport_unavailable", "目标 Runner 未观察到"),
        "stale": ("stale", "stale", "readiness_expired", "状态观察已过期"),
        "blocked": ("blocked", "blocked", "readiness_binding_drift", "状态证据绑定无效"),
    }
    agent_status, readiness_status, blocked_reason, label = mapping[evidence["observation_status"]]
    target = evidence["target"]
    return {
        "agent_id": target["agent_id"],
        "adapter_id": target["adapter_id"],
        "display_name_zh": "OMP/Pi 外部 Agent",
        "status": agent_status,
        "status_label_zh": label,
        "transport": target["transport"],
        "capabilities": [{"capability_id": "live_status.observe", "roles": ["executor"], "label_zh": "只读状态观察"}],
        "readiness": {
            "status": readiness_status,
            "status_label_zh": label,
            "evidence_id": evidence["evidence_id"],
            "expires_at": evidence["expires_at"],
            "binding_valid": evidence["source_integrity"]["producer_binding_valid"],
            "safe_summary_zh": evidence["safe_summary_zh"],
        },
        "session": None,
        "current_work_item_id": None,
        "blocked_reason_code": blocked_reason,
        "safe_summary_zh": evidence["safe_summary_zh"],
    }


@dataclass(frozen=True)
class ExternalAgentLiveStatusResult:
    status: str
    observation_status: str
    evidence: dict[str, Any] | None = None
    gui_projection: dict[str, Any] | None = None
    findings: tuple[Finding, ...] = ()

    def exit_code(self) -> int:
        if self.status == "pass":
            return EXIT_PASS
        if self.status == "blocked":
            return EXIT_BLOCKED
        return EXIT_ERROR

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "status": self.status,
            "schema_version": SCHEMA_VERSION,
            "observation_status": self.observation_status,
            "source": {"snapshot_file": FIXED_SNAPSHOT_PATH.as_posix()},
            "guarantees": {
                "deterministic": True,
                "read_only": True,
                "fixed_path_only": True,
                "starts_process": False,
                "connects_acp": False,
                "opens_session": False,
                "sends_prompt": False,
                "invokes_model": False,
                "reads_credentials": False,
                "accesses_network": False,
                "writes_files": False,
                "writes_ledger": False,
                "grants_execution_authority": False,
                "enables_dispatch": False,
            },
        }
        if self.evidence is not None:
            payload["evidence"] = self.evidence
        if self.gui_projection is not None:
            payload["gui_projection"] = self.gui_projection
        if self.findings:
            payload["findings"] = [item.to_dict() for item in self.findings]
        payload["next_action"] = {
            "code": "inspect_only" if self.status == "pass" else "wait_for_valid_snapshot",
            "message": "该结果仅供只读展示，不授权启动 Agent、创建 session 或派发任务。",
        }
        return payload


def _failure(code: str, binding: dict[str, Any] | None = None) -> ExternalAgentLiveStatusResult:
    return ExternalAgentLiveStatusResult(
        status="blocked",
        observation_status="blocked",
        gui_projection=_blocked_projection(binding),
        findings=(_finding(code),),
    )


def inspect_external_agent_live_status(
    root: Path,
    evaluated_at: str,
    *,
    expected_after_generation: int | None = None,
) -> ExternalAgentLiveStatusResult:
    """Inspect the fixed snapshot without starting or contacting an external Agent."""
    try:
        binding, snapshot_schema, evidence_schema, gui_schema = _load_binding(root)
    except (OSError, ValueError, json.JSONDecodeError, SchemaError, ValidationError):
        return _failure("status_producer_binding_missing")

    try:
        raw = _read_fixed_snapshot(root, binding["max_bytes"])
    except _ReadFailure as exc:
        return _failure(exc.code, binding)

    try:
        snapshot = _strict_json(raw)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError, TypeError):
        return _failure("status_source_unreadable", binding)
    if snapshot.get("complete") is not True:
        return _failure("status_snapshot_incomplete", binding)
    try:
        validate(snapshot, snapshot_schema, format_checker=FormatChecker())
    except (SchemaError, ValidationError):
        return _failure("status_source_schema_invalid", binding)
    if snapshot["snapshot_id"] != _canonical_digest(snapshot, "snapshot_id"):
        return _failure("status_source_schema_invalid", binding)

    if snapshot.get("producer") != binding["expected_producer"]:
        if not snapshot.get("producer") or not snapshot.get("producer", {}).get("producer_binding_id"):
            return _failure("status_producer_binding_missing", binding)
        return _failure("status_producer_binding_drift", binding)
    if snapshot.get("target") != binding["expected_target"]:
        return _failure("status_identity_binding_mismatch", binding)

    try:
        observed = _parse_time(snapshot["observed_at"])
        evaluated = _parse_time(evaluated_at)
    except (TypeError, ValueError):
        return _failure("status_source_schema_invalid", binding)
    if observed > evaluated:
        return _failure("status_observation_from_future", binding)
    expires = observed + timedelta(seconds=binding["ttl_seconds"])

    code: str | None = None
    observation_status = "observed"
    readiness_status = "unknown"
    presence = snapshot["observation"]["transport_presence"]
    level = "runner_listed"
    summary = "Runner 已列出，但该 evidence 不证明 readiness、session openability、模型可用或 dispatch authority。"
    if expected_after_generation is not None and snapshot["generation"] <= expected_after_generation:
        code = "status_snapshot_replayed"
        observation_status = "stale"
        readiness_status = "stale"
        summary = _SAFE_MESSAGES[code]
    elif evaluated > expires:
        code = "status_observation_expired"
        observation_status = "stale"
        readiness_status = "stale"
        summary = _SAFE_MESSAGES[code]
    elif snapshot["observation"]["session_state"] == "open":
        code = "status_unbound_session_observed"
        observation_status = "blocked"
        readiness_status = "blocked"
        summary = _SAFE_MESSAGES[code]
    elif presence != "listed":
        code = "status_target_not_observed"
        observation_status = "unavailable"
        level = "runner_missing" if presence == "missing" else "runner_presence_unknown"
        summary = _SAFE_MESSAGES[code]

    evidence: dict[str, Any] = {
        "version": 1,
        "contract": "external-agent-live-status-evidence/v1",
        "fixture_only": False,
        "evidence_id": "sha256:" + "0" * 64,
        "source_snapshot_id": snapshot["snapshot_id"],
        "observed_at": _format_time(observed),
        "evaluated_at": _format_time(evaluated),
        "expires_at": _format_time(expires),
        "target": snapshot["target"],
        "observation_status": observation_status,
        "readiness_status": readiness_status,
        "readiness_level": level,
        "session_state": snapshot["observation"]["session_state"],
        "session_binding": None,
        "event_cursor": None,
        "source_integrity": {
            "complete": True,
            "generation": snapshot["generation"],
            "producer_binding_valid": True,
            "stable_read": True,
        },
        "sufficient_for_dispatch": False,
        "execution_authorized": False,
        "safe_summary_zh": summary,
    }
    evidence["evidence_id"] = _canonical_digest(evidence, "evidence_id")
    try:
        validate(evidence, evidence_schema, format_checker=FormatChecker())
        projection = _projection(evidence)
        validate(projection, gui_schema["properties"]["agents"]["items"], format_checker=FormatChecker())
    except (SchemaError, ValidationError, KeyError, TypeError):
        return _failure("status_projection_invalid", binding)

    findings = (_finding(code),) if code else ()
    if observation_status == "blocked":
        return ExternalAgentLiveStatusResult(
            status="blocked",
            observation_status=observation_status,
            evidence=evidence,
            gui_projection=projection,
            findings=findings,
        )
    return ExternalAgentLiveStatusResult(
        status="pass",
        observation_status=observation_status,
        evidence=evidence,
        gui_projection=projection,
        findings=findings,
    )
