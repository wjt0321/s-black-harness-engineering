"""Immutable machine-local evidence store for controlled external-agent results."""

from __future__ import annotations

import hashlib
import json
import os
import stat
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, SchemaError, ValidationError

_EVIDENCE_ROOT = Path(".runtime/external-agent-evidence/v1")
_MANIFEST_SCHEMA = Path("adapters/external-agent-evidence-manifest.schema.json")
_REVIEW_SCHEMA = Path("adapters/external-agent-review-record.schema.json")
_RESULT_SCHEMA = Path("adapters/external-agent-single-work-item-result.schema.json")
_MAX_RECORD_BYTES = 128 * 1024
_MAX_OUTPUT_BYTES = 32 * 1024


@dataclass(frozen=True)
class EvidenceStoreError(ValueError):
    code: str
    message: str

    def __str__(self) -> str:
        return self.message


def _canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _digest(value: object) -> str:
    data = value if isinstance(value, bytes) else _canonical(value)
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _key(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _base(root: Path) -> Path:
    return root.resolve(strict=True)


def _contained(root: Path, relative: Path | str) -> Path:
    base = _base(root)
    rel = Path(relative)
    if rel.is_absolute():
        raise EvidenceStoreError("external-agent-evidence-path-invalid", "证据路径必须位于项目内部。")
    target = (base / rel).resolve(strict=False)
    if os.path.commonpath([str(base), str(target)]) != str(base) or target == base:
        raise EvidenceStoreError("external-agent-evidence-path-invalid", "证据路径必须位于项目内部。")
    return target


def _ensure_directory(root: Path, relative: Path) -> Path:
    current = _base(root)
    try:
        for part in relative.parts:
            current = current / part
            if current.exists():
                info = current.lstat()
                if not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode):
                    raise EvidenceStoreError("external-agent-evidence-path-unsafe", "证据目录不是安全的普通目录。")
            else:
                current.mkdir()
    except EvidenceStoreError:
        raise
    except OSError as exc:
        raise EvidenceStoreError("external-agent-evidence-write-io-failed", "证据目录创建或校验失败。") from exc
    return current


def _read_regular(path: Path, max_bytes: int = _MAX_RECORD_BYTES) -> bytes:
    try:
        before = path.lstat()
        if not stat.S_ISREG(before.st_mode) or stat.S_ISLNK(before.st_mode) or before.st_nlink != 1:
            raise EvidenceStoreError("external-agent-evidence-file-unsafe", "证据文件不是安全的普通文件。")
        if before.st_size > max_bytes:
            raise EvidenceStoreError("external-agent-evidence-file-too-large", "证据文件超过固定大小上限。")
        data = path.read_bytes()
        after = path.lstat()
        if len(data) > max_bytes or (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
        ):
            raise EvidenceStoreError("external-agent-evidence-file-drift", "证据文件读取期间发生变化。")
        return data
    except FileNotFoundError as exc:
        raise EvidenceStoreError("external-agent-evidence-not-found", "没有找到指定执行证据。") from exc
    except EvidenceStoreError:
        raise
    except OSError as exc:
        raise EvidenceStoreError("external-agent-evidence-read-io-failed", "证据文件读取失败。") from exc


def _immutable_write(root: Path, relative: Path, data: bytes, *, max_bytes: int) -> Path:
    if not data or len(data) > max_bytes:
        raise EvidenceStoreError("external-agent-evidence-write-size", "证据写入内容为空或超过固定上限。")
    parent = _ensure_directory(root, relative.parent)
    target = _contained(root, relative)
    if target.parent != parent.resolve(strict=True):
        raise EvidenceStoreError("external-agent-evidence-path-invalid", "证据目标目录发生漂移。")
    if target.exists():
        existing = _read_regular(target, max_bytes=max_bytes)
        if existing == data:
            return target
        raise EvidenceStoreError("external-agent-evidence-conflict", "已存在同名但内容不同的不可变证据。")
    temporary = parent / (target.name + f".tmp-{os.getpid()}")
    if temporary.exists():
        raise EvidenceStoreError("external-agent-evidence-temporary-conflict", "证据临时文件已存在。")
    try:
        with temporary.open("xb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, target)
    except FileExistsError as exc:
        raise EvidenceStoreError("external-agent-evidence-conflict", "不可变证据已由其他写入创建。") from exc
    except OSError as exc:
        raise EvidenceStoreError("external-agent-evidence-write-io-failed", "不可变证据写入失败。") from exc
    finally:
        try:
            if temporary.exists() and not temporary.is_symlink():
                temporary.unlink()
        except OSError:
            pass
    if _read_regular(target, max_bytes=max_bytes) != data:
        raise EvidenceStoreError("external-agent-evidence-post-write-invalid", "证据写后校验失败。")
    return target


def _schema_source(root: Path, relative: Path) -> Path:
    candidate = root.resolve() / relative
    if candidate.is_file():
        return candidate
    return Path(__file__).resolve().parents[1] / relative


def _validate_schema(root: Path, value: dict[str, Any], relative: Path) -> None:
    try:
        schema_path = _schema_source(root, relative)
        schema = json.loads(_read_regular(schema_path).decode("utf-8"))
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(value)
    except (UnicodeDecodeError, json.JSONDecodeError, SchemaError, ValidationError, OSError, EvidenceStoreError) as exc:
        if isinstance(exc, EvidenceStoreError):
            raise
        raise EvidenceStoreError("external-agent-evidence-schema-invalid", "证据记录未通过固定结构校验。") from exc


def _pending_path(attempt_id: str) -> Path:
    return _EVIDENCE_ROOT / "pending" / f"{_key(attempt_id)}.json"


def _manifest_path(attempt_id: str) -> Path:
    return _EVIDENCE_ROOT / "attempts" / _key(attempt_id) / "manifest.json"


def _review_path(attempt_id: str) -> Path:
    return _EVIDENCE_ROOT / "reviews" / f"{_key(attempt_id)}.json"


def validate_host_result(root: Path, result: dict[str, Any], *, result_max_bytes: int) -> dict[str, Any]:
    _validate_schema(root, result, _RESULT_SCHEMA)
    events = result["events"]
    if [event["sequence"] for event in events] != list(range(1, len(events) + 1)):
        raise EvidenceStoreError("external-agent-result-event-sequence-invalid", "宿主事件序号不连续。")
    try:
        timestamps = [datetime.fromisoformat(event["occurred_at"].replace("Z", "+00:00")) for event in events]
        completed_at = datetime.fromisoformat(result["completed_at"].replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise EvidenceStoreError("external-agent-result-event-time-invalid", "宿主事件时间格式无效。") from exc
    if any(item.tzinfo is None for item in timestamps) or completed_at.tzinfo is None:
        raise EvidenceStoreError("external-agent-result-event-time-invalid", "宿主事件时间必须带时区。")
    if timestamps != sorted(timestamps) or completed_at < timestamps[-1]:
        raise EvidenceStoreError("external-agent-result-event-time-invalid", "宿主事件时间顺序发生倒退。")
    event_types = [event["event_type"] for event in events]
    status = result["status"]
    allowed = False
    if status == "succeeded":
        allowed = event_types == ["request_claimed", "host_turn_dispatched", "host_turn_started", "host_turn_completed"]
    elif status == "blocked":
        allowed = event_types == ["request_claimed", "host_turn_blocked"]
    elif status == "timed_out":
        allowed = event_types in (
            ["request_claimed", "host_turn_dispatched", "host_turn_timed_out"],
            ["request_claimed", "host_turn_dispatched", "host_turn_started", "host_turn_timed_out"],
        )
    elif status in {"failed", "cancelled"}:
        allowed = bool(event_types and event_types[0] == "request_claimed" and event_types[-1] == "host_session_closed")
    if not allowed:
        raise EvidenceStoreError("external-agent-result-event-chain-invalid", "宿主事件链与执行状态不一致。")
    if status != "succeeded":
        terminal_code = events[-1].get("failure_code")
        if terminal_code != result.get("failure_code"):
            raise EvidenceStoreError("external-agent-result-failure-code-mismatch", "宿主终止事件与结果失败码不一致。")
    else:
        output = result["output"]
        encoded = output.encode("utf-8")
        if len(encoded) > result_max_bytes or result["output_bytes"] != len(encoded) or result["output_digest"] != _digest(encoded):
            raise EvidenceStoreError("external-agent-result-output-binding-invalid", "宿主结果的大小或内容摘要不一致。")
    return result


def _public(manifest: dict[str, Any], *, status: str, review_record: dict[str, Any] | None = None) -> dict[str, Any]:
    result = dict(manifest)
    result["status"] = status
    result["manifest_digest"] = _digest(manifest)
    review = dict(manifest["review"])
    if review_record is not None:
        review["status"] = "approved" if review_record["decision"] == "approve" else "changes_requested"
        review["record"] = review_record
    result["review"] = review
    return result


def _load_pending(root: Path, pending_path: Path, attempt_id: str) -> tuple[dict[str, Any], str]:
    try:
        pending = json.loads(_read_regular(pending_path).decode("utf-8"))
        manifest = pending["manifest"]
        output = pending["output"]
    except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise EvidenceStoreError("external-agent-evidence-pending-invalid", "待恢复证据格式无效。") from exc
    if pending.get("version") != 1 or pending.get("contract") != "external-agent-evidence-pending/v1":
        raise EvidenceStoreError("external-agent-evidence-pending-invalid", "待恢复证据版本或契约无效。")
    if not isinstance(manifest, dict) or not isinstance(output, str):
        raise EvidenceStoreError("external-agent-evidence-pending-invalid", "待恢复证据格式无效。")
    _validate_schema(root, manifest, _MANIFEST_SCHEMA)
    encoded = output.encode("utf-8")
    if (
        manifest["attempt_id"] != attempt_id
        or pending.get("manifest_digest") != _digest(manifest)
        or not encoded
        or len(encoded) > _MAX_OUTPUT_BYTES
        or b"\x00" in encoded
        or pending.get("output_digest") != _digest(encoded)
        or manifest["artifact"]["content_hash"] != _digest(encoded)
        or manifest["artifact"]["byte_count"] != len(encoded)
    ):
        raise EvidenceStoreError("external-agent-evidence-pending-binding-invalid", "待恢复证据与执行尝试或产物绑定不一致。")
    return manifest, output


def prepare_evidence(
    root: Path,
    *,
    attempt_id: str,
    task_id: str,
    request_id: str,
    collaboration_file: str,
    collaboration_plan_id: str,
    work_item_id: str,
    target_profile: str,
    plan_hash: str,
    approval_binding_id: str,
    completed_at: str,
    host_events: list[dict[str, Any]],
    output: str,
    expected_artifact_types: list[str],
    review_required: bool,
    review_gate_id: str | None,
) -> dict[str, Any]:
    root = root.resolve()
    manifest_path = _contained(root, _manifest_path(attempt_id))
    if manifest_path.exists():
        raise EvidenceStoreError("external-agent-evidence-already-finalized", "该执行尝试已经存在不可变证据。")
    encoded = output.encode("utf-8")
    if not encoded or len(encoded) > _MAX_OUTPUT_BYTES or b"\x00" in encoded:
        raise EvidenceStoreError("external-agent-evidence-output-invalid", "输出产物为空、包含空字符或超过固定上限。")
    media_type = "text/plain"
    suffix = "txt"
    try:
        json.loads(output)
    except (json.JSONDecodeError, TypeError):
        pass
    else:
        media_type = "application/json"
        suffix = "json"
    content_hash = _digest(encoded)
    hex_digest = content_hash.split(":", 1)[1]
    artifact_type = expected_artifact_types[0] if len(expected_artifact_types) == 1 else "execution_result"
    manifest = {
        "version": 1,
        "contract": "external-agent-evidence-manifest/v1",
        "attempt_id": attempt_id,
        "task_id": task_id,
        "request_id": request_id,
        "collaboration_file": collaboration_file,
        "collaboration_plan_id": collaboration_plan_id,
        "work_item_id": work_item_id,
        "target_profile": target_profile,
        "plan_hash": plan_hash,
        "approval_binding_id": approval_binding_id,
        "execution_status": "succeeded",
        "completed_at": completed_at,
        "host_events": host_events,
        "artifact": {
            "artifact_id": "artifact-" + hex_digest,
            "artifact_type": artifact_type,
            "media_type": media_type,
            "content_hash": content_hash,
            "byte_count": len(encoded),
            "relative_path": (_EVIDENCE_ROOT / "artifacts" / f"{hex_digest}.{suffix}").as_posix(),
        },
        "expected_artifact_types": list(expected_artifact_types),
        "review": {
            "required": review_required,
            "gate_id": review_gate_id,
            "status": "pending" if review_required else "not_required",
        },
    }
    _validate_schema(root, manifest, _MANIFEST_SCHEMA)
    pending = {
        "version": 1,
        "contract": "external-agent-evidence-pending/v1",
        "manifest": manifest,
        "output": output,
        "manifest_digest": _digest(manifest),
        "output_digest": content_hash,
    }
    pending_data = _canonical(pending) + b"\n"
    path = _contained(root, _pending_path(attempt_id))
    if path.exists():
        try:
            existing = json.loads(_read_regular(path).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError, TypeError) as exc:
            raise EvidenceStoreError("external-agent-evidence-pending-invalid", "待恢复证据格式无效。") from exc
        if existing == pending:
            return _public(manifest, status="prepared")
        raise EvidenceStoreError("external-agent-evidence-pending-conflict", "该执行尝试已有不同的待恢复证据。")
    _immutable_write(root, _pending_path(attempt_id), pending_data, max_bytes=_MAX_RECORD_BYTES)
    return _public(manifest, status="prepared")


def finalize_evidence(root: Path, attempt_id: str) -> dict[str, Any]:
    root = root.resolve()
    pending_path = _contained(root, _pending_path(attempt_id))
    if not pending_path.exists():
        if _contained(root, _manifest_path(attempt_id)).exists():
            return inspect_evidence(root, attempt_id)
        raise EvidenceStoreError("external-agent-evidence-pending-not-found", "没有找到可归档的待恢复证据。")
    manifest, output = _load_pending(root, pending_path, attempt_id)
    encoded = output.encode("utf-8")
    _immutable_write(root, Path(manifest["artifact"]["relative_path"]), encoded, max_bytes=_MAX_OUTPUT_BYTES)
    _immutable_write(root, _manifest_path(attempt_id), _canonical(manifest) + b"\n", max_bytes=_MAX_RECORD_BYTES)
    try:
        info = pending_path.lstat()
        if not stat.S_ISREG(info.st_mode) or stat.S_ISLNK(info.st_mode) or info.st_nlink != 1:
            raise EvidenceStoreError("external-agent-evidence-file-unsafe", "待恢复证据不是安全的普通文件。")
        pending_path.unlink()
    except FileNotFoundError:
        pass
    except OSError as exc:
        raise EvidenceStoreError("external-agent-evidence-write-io-failed", "待恢复证据清理失败。") from exc
    return inspect_evidence(root, attempt_id)


def inspect_evidence(root: Path, attempt_id: str) -> dict[str, Any]:
    root = root.resolve()
    manifest_path = _contained(root, _manifest_path(attempt_id))
    if not manifest_path.exists():
        pending_path = _contained(root, _pending_path(attempt_id))
        if not pending_path.exists():
            raise EvidenceStoreError("external-agent-evidence-not-found", "没有找到指定执行证据。")
        manifest, _output = _load_pending(root, pending_path, attempt_id)
        return _public(manifest, status="recovery_pending")
    try:
        manifest = json.loads(_read_regular(manifest_path).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError) as exc:
        raise EvidenceStoreError("external-agent-evidence-manifest-invalid", "执行证据清单格式无效。") from exc
    _validate_schema(root, manifest, _MANIFEST_SCHEMA)
    if manifest.get("attempt_id") != attempt_id:
        raise EvidenceStoreError("external-agent-evidence-attempt-mismatch", "执行证据清单与尝试编号不一致。")
    artifact_path = _contained(root, Path(manifest["artifact"]["relative_path"]))
    artifact_data = _read_regular(artifact_path, max_bytes=_MAX_OUTPUT_BYTES)
    if _digest(artifact_data) != manifest["artifact"]["content_hash"] or len(artifact_data) != manifest["artifact"]["byte_count"]:
        raise EvidenceStoreError("external-agent-evidence-artifact-drift", "执行结果产物已发生变化。")
    review_record = None
    review_path = _contained(root, _review_path(attempt_id))
    if review_path.exists():
        try:
            review_record = json.loads(_read_regular(review_path).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError, TypeError) as exc:
            raise EvidenceStoreError("external-agent-review-record-invalid", "人工审阅记录格式无效。") from exc
        _validate_schema(root, review_record, _REVIEW_SCHEMA)
        if (
            review_record["attempt_id"] != attempt_id
            or review_record["manifest_digest"] != _digest(manifest)
            or review_record["artifact_id"] != manifest["artifact"]["artifact_id"]
            or review_record["artifact_digest"] != manifest["artifact"]["content_hash"]
        ):
            raise EvidenceStoreError("external-agent-review-binding-invalid", "人工审阅记录与执行证据绑定不一致。")
    return _public(manifest, status="pass", review_record=review_record)


def read_artifact_content(root: Path, attempt_id: str) -> str:
    evidence = inspect_evidence(root, attempt_id)
    if evidence["status"] != "pass":
        raise EvidenceStoreError("external-agent-evidence-not-finalized", "执行证据尚未完成归档。")
    path = _contained(root.resolve(), Path(evidence["artifact"]["relative_path"]))
    data = _read_regular(path, max_bytes=_MAX_OUTPUT_BYTES)
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise EvidenceStoreError("external-agent-evidence-artifact-encoding-invalid", "执行结果产物不是有效 UTF-8。") from exc


def write_review_record(root: Path, record: dict[str, Any]) -> dict[str, Any]:
    root = root.resolve()
    attempt_id = record.get("attempt_id")
    if not isinstance(attempt_id, str):
        raise EvidenceStoreError("external-agent-review-record-invalid", "人工审阅记录缺少执行尝试编号。")
    review_path = _contained(root, _review_path(attempt_id))
    if review_path.exists():
        raise EvidenceStoreError("external-agent-review-already-recorded", "该执行尝试已经存在人工审阅决定。")
    evidence = inspect_evidence(root, attempt_id)
    if evidence["status"] != "pass" or evidence["review"]["status"] != "pending":
        raise EvidenceStoreError("external-agent-review-not-pending", "该执行尝试当前不等待人工审阅。")
    normalized = dict(record)
    normalized["comment_digest"] = _digest(normalized.get("comment", "").encode("utf-8"))
    if (
        normalized.get("gate_id") != evidence["review"]["gate_id"]
        or normalized.get("artifact_id") != evidence["artifact"]["artifact_id"]
        or normalized.get("artifact_digest") != evidence["artifact"]["content_hash"]
        or normalized.get("manifest_digest") != evidence["manifest_digest"]
        or normalized.get("collaboration_plan_id") != evidence["collaboration_plan_id"]
    ):
        raise EvidenceStoreError("external-agent-review-binding-invalid", "人工审阅记录与执行证据绑定不一致。")
    _validate_schema(root, normalized, _REVIEW_SCHEMA)
    _immutable_write(root, _review_path(attempt_id), _canonical(normalized) + b"\n", max_bytes=_MAX_RECORD_BYTES)
    stored = inspect_evidence(root, attempt_id)["review"]["record"]
    return stored
