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

SCHEMA_VERSION = "control-plane/external-agent-live-status-inspection/v2"


@dataclass(frozen=True)
class FixedStatusProfile:
    profile_id: str
    snapshot_path: Path
    binding_path: Path
    binding_schema_path: Path
    display_name_zh: str


_BINDING_SCHEMA_V1_PATH = Path("adapters/external-agent-live-status-binding.schema.json")
_BINDING_SCHEMA_V2_PATH = Path("adapters/external-agent-live-status-binding.v2.schema.json")
_SNAPSHOT_SCHEMA_PATH = Path("adapters/external-agent-status-snapshot.schema.json")
_EVIDENCE_SCHEMA_PATH = Path("adapters/external-agent-live-status-evidence.schema.json")
_GUI_SCHEMA_PATH = Path("adapters/external-agent-live-read-model.schema.json")
FIXED_STATUS_PROFILES = {
    "omp-acp": FixedStatusProfile(
        profile_id="omp-acp",
        snapshot_path=Path(".runtime/external-agent-status/omp-acp.v1.json"),
        binding_path=Path("adapters/external-agent-live-status-binding.json"),
        binding_schema_path=_BINDING_SCHEMA_V1_PATH,
        display_name_zh="OMP/Pi ACP 外部智能体",
    ),
    "pi-local": FixedStatusProfile(
        profile_id="pi-local",
        snapshot_path=Path(".runtime/external-agent-status/pi-local.v1.json"),
        binding_path=Path("adapters/external-agent-live-status-binding.pi-local.json"),
        binding_schema_path=_BINDING_SCHEMA_V2_PATH,
        display_name_zh="Pi 编码智能体",
    ),
    "omp-local": FixedStatusProfile(
        profile_id="omp-local",
        snapshot_path=Path(".runtime/external-agent-status/omp-local.v1.json"),
        binding_path=Path("adapters/external-agent-live-status-binding.omp-local.json"),
        binding_schema_path=_BINDING_SCHEMA_V2_PATH,
        display_name_zh="OMP 编码智能体",
    ),
}
FIXED_SNAPSHOT_PATH = FIXED_STATUS_PROFILES["omp-acp"].snapshot_path
_FILE_ATTRIBUTE_REPARSE_POINT = 0x400
_REVIEWED_CONTRACT_DIGESTS = {
    _BINDING_SCHEMA_V1_PATH: "sha256:d68fd38cf63aeee074460059e30ea3e6755ad1ef484c9caf8938759d3ace68fd",
    _BINDING_SCHEMA_V2_PATH: "sha256:884a1284c4fdfef1256bef6cbd11655e29f1facfc2c292a93de7247052b073a0",
    Path("adapters/external-agent-live-status-binding.json"): "sha256:d2a930dcc452bfcf6624ef115ca8153b12fc0f8a5f0dfbc36a59f34460e2abb7",
    Path("adapters/external-agent-live-status-binding.pi-local.json"): "sha256:5d03fb65a0fccd82b0b8d938800157b589b84258ab873bec16c7b5db706495c8",
    Path("adapters/external-agent-live-status-binding.omp-local.json"): "sha256:9c20378a451b38a7fe1a3e74f538168693541b9b992ad904b99e47cfed839cb9",
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
    warning_codes = {
        "status_source_missing",
        "status_snapshot_replayed",
        "status_observation_expired",
        "status_target_not_observed",
        "status_unbound_session_observed",
    }
    retry_codes = {
        "status_source_missing",
        "status_snapshot_replayed",
        "status_observation_expired",
        "status_target_not_observed",
    }
    return Finding(
        rule_id=code,
        severity="warn" if code in warning_codes else "block",
        action="retry" if code in retry_codes else "deny",
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


def _read_fixed_snapshot(
    root: Path,
    snapshot_path: Path,
    max_bytes: int,
    *,
    snapshot_root: Path | None = None,
) -> bytes:
    base = (snapshot_root or root).resolve()
    path = base / snapshot_path
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


def _load_binding(
    root: Path,
    profile: FixedStatusProfile,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    paths = {
        profile.binding_path,
        profile.binding_schema_path,
        _SNAPSHOT_SCHEMA_PATH,
        _EVIDENCE_SCHEMA_PATH,
        _GUI_SCHEMA_PATH,
    }
    documents = {path: _load_contract(root, path) for path in paths}
    for path in paths:
        expected_digest = _REVIEWED_CONTRACT_DIGESTS[path]
        if _document_digest(documents[path]) != expected_digest:
            raise ValueError("reviewed contract drift")
    binding = documents[profile.binding_path]
    binding_schema = documents[profile.binding_schema_path]
    snapshot_schema = documents[_SNAPSHOT_SCHEMA_PATH]
    evidence_schema = documents[_EVIDENCE_SCHEMA_PATH]
    gui_schema = documents[_GUI_SCHEMA_PATH]
    for schema in (binding_schema, snapshot_schema, evidence_schema, gui_schema):
        Draft202012Validator.check_schema(schema)
    validate(binding, binding_schema, format_checker=FormatChecker())
    if binding["source_relative_path"] != profile.snapshot_path.as_posix():
        raise ValueError("profile path drift")
    return binding, snapshot_schema, evidence_schema, gui_schema


def _blocked_projection(
    binding: dict[str, Any] | None,
    profile: FixedStatusProfile,
) -> dict[str, Any]:
    target = (binding or {}).get("expected_target", {})
    transport = target.get(
        "transport",
        {"transport_id": "unknown", "kind": "local_process", "protocol_version": "unknown"},
    )
    return {
        "agent_id": target.get("agent_id", profile.profile_id),
        "adapter_id": target.get("adapter_id", f"{profile.profile_id}-status"),
        "display_name_zh": profile.display_name_zh,
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
        "safe_summary_zh": "外部智能体状态不可安全投影。",
    }


def _missing_projection(binding: dict[str, Any], profile: FixedStatusProfile) -> dict[str, Any]:
    target = binding["expected_target"]
    return {
        "agent_id": target["agent_id"],
        "adapter_id": target["adapter_id"],
        "display_name_zh": profile.display_name_zh,
        "status": "disconnected",
        "status_label_zh": "未连接",
        "transport": target["transport"],
        "capabilities": [{"capability_id": "live_status.observe", "roles": ["executor"], "label_zh": "只读状态观察"}],
        "readiness": {
            "status": "unknown",
            "status_label_zh": "未连接",
            "evidence_id": None,
            "expires_at": None,
            "binding_valid": True,
            "safe_summary_zh": "尚未收到宿主进程内扩展发布的状态快照。",
        },
        "session": None,
        "current_work_item_id": None,
        "blocked_reason_code": "transport_unavailable",
        "safe_summary_zh": "宿主未运行，或尚未在本项目中加载状态扩展。",
    }


def _projection(
    evidence: dict[str, Any],
    profile: FixedStatusProfile,
) -> dict[str, Any]:
    mapping = {
        "observed": ("unknown", "unknown", None, "已连接，尚未证明就绪"),
        "unavailable": ("disconnected", "unknown", "transport_unavailable", "未连接"),
        "stale": ("stale", "stale", "readiness_expired", "状态已过期"),
        "blocked": ("blocked", "blocked", "readiness_binding_drift", "状态证据绑定无效"),
    }
    agent_status, readiness_status, blocked_reason, label = mapping[evidence["observation_status"]]
    target = evidence["target"]
    session = None
    if evidence["session_state"] == "open" and profile.profile_id != "omp-acp":
        agent_status = "busy"
        blocked_reason = "session_mapping_conflict"
        label = "已连接，存在未绑定会话"
        session = {
            "mapping_id": f"{profile.profile_id}.unbound",
            "state": "open",
            "state_label_zh": "存在未绑定会话",
            "external_session_ref": None,
            "safe_summary_zh": "只观察到宿主会话存在；未读取或保存外部会话标识。",
        }
    elif evidence["session_state"] == "closed" and profile.profile_id != "omp-acp":
        session = {
            "mapping_id": f"{profile.profile_id}.closed",
            "state": "closed",
            "state_label_zh": "会话已关闭",
            "external_session_ref": None,
            "safe_summary_zh": "宿主报告会话已关闭。",
        }
    return {
        "agent_id": target["agent_id"],
        "adapter_id": target["adapter_id"],
        "display_name_zh": profile.display_name_zh,
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
        "session": session,
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
    profile_id: str = "omp-acp"
    snapshot_path: Path = FIXED_SNAPSHOT_PATH

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
            "source": {
                "profile_id": self.profile_id,
                "snapshot_file": self.snapshot_path.as_posix(),
            },
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


def _failure(
    code: str,
    profile: FixedStatusProfile,
    binding: dict[str, Any] | None = None,
) -> ExternalAgentLiveStatusResult:
    if code == "status_source_missing" and binding is not None and profile.profile_id != "omp-acp":
        return ExternalAgentLiveStatusResult(
            status="pass",
            observation_status="unavailable",
            gui_projection=_missing_projection(binding, profile),
            findings=(_finding(code),),
            profile_id=profile.profile_id,
            snapshot_path=profile.snapshot_path,
        )
    finding = _finding(code)
    if code == "status_source_missing" and profile.profile_id == "omp-acp":
        finding = Finding(
            rule_id=code,
            severity="block",
            action="deny",
            message=_SAFE_MESSAGES[code],
        )
    return ExternalAgentLiveStatusResult(
        status="blocked",
        observation_status="blocked",
        gui_projection=_blocked_projection(binding, profile),
        findings=(finding,),
        profile_id=profile.profile_id,
        snapshot_path=profile.snapshot_path,
    )


def inspect_external_agent_live_status(
    root: Path,
    evaluated_at: str,
    *,
    expected_after_generation: int | None = None,
    profile_id: str = "omp-acp",
    snapshot_root: Path | None = None,
) -> ExternalAgentLiveStatusResult:
    """Inspect one reviewed fixed snapshot without starting or contacting an Agent.

    ``snapshot_root`` exists only for in-process tests. CLI callers cannot set it.
    """
    profile = FIXED_STATUS_PROFILES.get(profile_id)
    if profile is None:
        raise ValueError(f"unsupported fixed status profile: {profile_id}")
    try:
        binding, snapshot_schema, evidence_schema, gui_schema = _load_binding(root, profile)
    except (OSError, ValueError, json.JSONDecodeError, SchemaError, ValidationError):
        return _failure("status_producer_binding_missing", profile)

    try:
        raw = _read_fixed_snapshot(
            root,
            profile.snapshot_path,
            binding["max_bytes"],
            snapshot_root=snapshot_root,
        )
    except _ReadFailure as exc:
        return _failure(exc.code, profile, binding)

    try:
        snapshot = _strict_json(raw)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError, TypeError):
        return _failure("status_source_unreadable", profile, binding)
    if snapshot.get("complete") is not True:
        return _failure("status_snapshot_incomplete", profile, binding)
    try:
        validate(snapshot, snapshot_schema, format_checker=FormatChecker())
    except (SchemaError, ValidationError):
        return _failure("status_source_schema_invalid", profile, binding)
    if snapshot["snapshot_id"] != _canonical_digest(snapshot, "snapshot_id"):
        return _failure("status_source_schema_invalid", profile, binding)

    if snapshot.get("producer") != binding["expected_producer"]:
        if not snapshot.get("producer") or not snapshot.get("producer", {}).get("producer_binding_id"):
            return _failure("status_producer_binding_missing", profile, binding)
        return _failure("status_producer_binding_drift", profile, binding)
    if snapshot.get("target") != binding["expected_target"]:
        return _failure("status_identity_binding_mismatch", profile, binding)

    try:
        observed = _parse_time(snapshot["observed_at"])
        evaluated = _parse_time(evaluated_at)
    except (TypeError, ValueError):
        return _failure("status_source_schema_invalid", profile, binding)
    if observed > evaluated:
        return _failure("status_observation_from_future", profile, binding)
    expires = observed + timedelta(seconds=binding["ttl_seconds"])

    code: str | None = None
    observation_status = "observed"
    readiness_status = "unknown"
    presence = snapshot["observation"]["transport_presence"]
    level = "runner_listed"
    summary = "宿主已被动发布运行状态，但该证据不证明模型可用、会话可派发或执行授权。"
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
    elif presence != "listed":
        code = "status_target_not_observed"
        observation_status = "unavailable"
        level = "runner_missing" if presence == "missing" else "runner_presence_unknown"
        summary = snapshot["observation"]["safe_summary_zh"]
    elif snapshot["observation"]["session_state"] == "open":
        code = "status_unbound_session_observed"
        summary = _SAFE_MESSAGES[code]
        if profile.profile_id == "omp-acp":
            observation_status = "blocked"
            readiness_status = "blocked"

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
        projection = _projection(evidence, profile)
        validate(projection, gui_schema["properties"]["agents"]["items"], format_checker=FormatChecker())
    except (SchemaError, ValidationError, KeyError, TypeError):
        return _failure("status_projection_invalid", profile, binding)

    findings = (_finding(code),) if code else ()
    return ExternalAgentLiveStatusResult(
        status="blocked" if observation_status == "blocked" else "pass",
        observation_status=observation_status,
        evidence=evidence,
        gui_projection=projection,
        findings=findings,
        profile_id=profile.profile_id,
        snapshot_path=profile.snapshot_path,
    )
