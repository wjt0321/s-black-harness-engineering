"""Immutable records for the bounded planner-executor-review chain."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, SchemaError, ValidationError, validate

_MAX_RECORD_BYTES = 32768
_MAX_ROLE_OUTPUT_BYTES = 8192
_BASE = Path(".runtime/external-agent-chain/v1")
_INTENT_SCHEMA = "adapters/external-agent-chain-intent.schema.json"
_CANDIDATE_SCHEMA = "adapters/external-agent-chain-planner-candidate.schema.json"
_ADVICE_SCHEMA = "adapters/external-agent-chain-review-advice.schema.json"
_KEY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")


@dataclass
class ChainStoreError(ValueError):
    code: str
    message: str


def _canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _digest(value: object) -> str:
    data = value if isinstance(value, bytes) else _canonical(value)
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _key(value: str) -> str:
    if not isinstance(value, str) or not _KEY_RE.fullmatch(value):
        raise ChainStoreError("external-agent-chain-identifier-invalid", "链路标识不符合固定格式。")
    return value


def _contained(root: Path, relative: Path | str) -> Path:
    target = (root / relative).resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise ChainStoreError("external-agent-chain-path-escape", "链路记录路径超出项目范围。") from exc
    return target


def _ensure_directory(root: Path, relative: Path) -> Path:
    path = _contained(root, relative)
    try:
        path.mkdir(parents=True, exist_ok=True)
        info = path.lstat()
    except OSError as exc:
        raise ChainStoreError("external-agent-chain-write-io-failed", "链路记录目录不可用。") from exc
    if not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode):
        raise ChainStoreError("external-agent-chain-directory-unsafe", "链路记录目录不安全。")
    return path


def _read_regular(path: Path, *, max_bytes: int = _MAX_RECORD_BYTES) -> bytes:
    try:
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or stat.S_ISLNK(info.st_mode) or info.st_nlink != 1 or info.st_size > max_bytes:
            raise ChainStoreError("external-agent-chain-file-unsafe", "链路记录不是安全的有界普通文件。")
        with path.open("rb") as handle:
            data = handle.read(max_bytes + 1)
    except ChainStoreError:
        raise
    except OSError as exc:
        raise ChainStoreError("external-agent-chain-read-io-failed", "链路记录读取失败。") from exc
    if len(data) > max_bytes:
        raise ChainStoreError("external-agent-chain-record-too-large", "链路记录超过大小上限。")
    return data


def _immutable_write(root: Path, relative: Path, data: bytes, *, max_bytes: int = _MAX_RECORD_BYTES) -> Path:
    if len(data) > max_bytes:
        raise ChainStoreError("external-agent-chain-record-too-large", "链路记录超过大小上限。")
    path = _contained(root, relative)
    _ensure_directory(root, relative.parent)
    if path.exists():
        raise ChainStoreError("external-agent-chain-already-recorded", "同一链路记录已经存在，不允许覆盖。")
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("xb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        written = _read_regular(path, max_bytes=max_bytes)
    except ChainStoreError:
        raise
    except OSError as exc:
        raise ChainStoreError("external-agent-chain-write-io-failed", "链路记录写入失败。") from exc
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
        except OSError:
            pass
    if written != data:
        raise ChainStoreError("external-agent-chain-write-verify-failed", "链路记录写后校验失败。")
    return path


def _schema_source(root: Path, relative: str) -> Path:
    path = _contained(root, relative)
    if not path.exists():
        raise ChainStoreError("external-agent-chain-schema-missing", "链路记录 schema 不存在。")
    return path


def _validate_schema(root: Path, value: dict[str, Any], relative: str) -> None:
    try:
        schema = json.loads(_read_regular(_schema_source(root, relative)).decode("utf-8"))
        Draft202012Validator.check_schema(schema)
        validate(value, schema)
    except (UnicodeDecodeError, json.JSONDecodeError, SchemaError, ValidationError, TypeError, ValueError) as exc:
        raise ChainStoreError("external-agent-chain-schema-invalid", "链路记录未通过固定 schema 校验。") from exc


def _intent_path(chain_id: str) -> Path:
    return _BASE / "intents" / f"{_key(chain_id)}.json"


def _candidate_path(chain_id: str) -> Path:
    return _BASE / "planner-candidates" / f"{_key(chain_id)}.json"


def _advice_path(chain_id: str) -> Path:
    return _BASE / "review-advice" / f"{_key(chain_id)}.json"


def _execution_path(chain_id: str) -> Path:
    return _BASE / "execution-receipts" / f"{_key(chain_id)}.json"


def _completion_path(chain_id: str) -> Path:
    return _BASE / "completion-receipts" / f"{_key(chain_id)}.json"


def _pending_completion_path(chain_id: str) -> Path:
    return _BASE / "finalization-pending" / f"{_key(chain_id)}.json"


def _stop_path(chain_id: str) -> Path:
    return _BASE / "stops" / f"{_key(chain_id)}.json"


def _valid_hash(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch(r"sha256:[a-f0-9]{64}", value) is not None


def _load_json(root: Path, relative: Path, *, missing_code: str, missing_message: str) -> dict[str, Any]:
    path = _contained(root, relative)
    if not path.exists():
        raise ChainStoreError(missing_code, missing_message)
    try:
        value = json.loads(_read_regular(path).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError) as exc:
        raise ChainStoreError("external-agent-chain-record-invalid", "链路记录格式无效。") from exc
    if not isinstance(value, dict):
        raise ChainStoreError("external-agent-chain-record-invalid", "链路记录必须是对象。")
    return value


def _load_intent(root: Path, chain_id: str) -> dict[str, Any]:
    intent = _load_json(
        root, _intent_path(chain_id),
        missing_code="external-agent-chain-not-found", missing_message="没有找到指定链路。",
    )
    _validate_schema(root, intent, _INTENT_SCHEMA)
    if intent.get("chain_id") != chain_id or intent.get("goal_digest") != _digest(intent["goal"].encode("utf-8")):
        raise ChainStoreError("external-agent-chain-intent-drift", "链路意图摘要不一致。")
    return intent


def _topology_valid(intent: dict[str, Any]) -> bool:
    roles = intent["roles"]
    planner = roles["planner"]["profile"]
    executor = roles["executor"]["profile"]
    reviewer = roles["reviewer"]["profile"]
    return planner == reviewer and planner != executor and {planner, executor} == {"pi-local", "omp-local"}


def create_chain_intent(root: Path, intent: dict[str, Any]) -> dict[str, Any]:
    root = root.resolve()
    _validate_schema(root, intent, _INTENT_SCHEMA)
    if intent["goal_digest"] != _digest(intent["goal"].encode("utf-8")):
        raise ChainStoreError("external-agent-chain-goal-digest-mismatch", "链路目标摘要不一致。")
    if not _topology_valid(intent):
        raise ChainStoreError("external-agent-chain-role-topology-invalid", "链路角色必须使用固定 Pi/OMP 交替拓扑。")
    data = _canonical(intent) + b"\n"
    path = _intent_path(intent["chain_id"])
    try:
        _immutable_write(root, path, data)
    except ChainStoreError as exc:
        if exc.code == "external-agent-chain-already-recorded":
            raise ChainStoreError("external-agent-chain-intent-already-recorded", "该链路意图已经存在，不允许覆盖。") from exc
        raise
    stored = _load_intent(root, intent["chain_id"])
    if stored != intent:
        raise ChainStoreError("external-agent-chain-write-verify-failed", "链路意图写后校验失败。")
    return stored


def _load_stop(root: Path, chain_id: str) -> dict[str, Any] | None:
    path = _contained(root, _stop_path(chain_id))
    if not path.exists():
        return None
    record = _load_json(root, _stop_path(chain_id), missing_code="external-agent-chain-record-invalid", missing_message="链路停止记录缺失。")
    required = {"chain_id", "role", "failure_code"}
    if (
        set(record) != required
        or record.get("chain_id") != chain_id
        or record.get("role") not in {"planner", "executor", "reviewer", "final_human_decision"}
        or not isinstance(record.get("failure_code"), str)
        or not re.fullmatch(r"[a-z0-9][a-z0-9-]{2,127}", record["failure_code"])
    ):
        raise ChainStoreError("external-agent-chain-stop-invalid", "链路停止记录无效。")
    return record


def _ensure_not_stopped(root: Path, chain_id: str) -> None:
    if _load_stop(root, chain_id) is not None:
        raise ChainStoreError("external-agent-chain-stopped", "当前链路已停止，不能继续交接、派发或完成。")


def write_chain_stop(root: Path, chain_id: str, *, role: str, failure_code: str) -> dict[str, Any]:
    root = root.resolve()
    _load_intent(root, chain_id)
    if _load_completion(root, chain_id) is not None:
        raise ChainStoreError("external-agent-chain-already-completed", "当前链路已经完成，不能再写入停止记录。")
    if _load_stop(root, chain_id) is not None:
        raise ChainStoreError("external-agent-chain-stop-already-recorded", "当前链路已经停止，不能覆盖停止记录。")
    record = {"chain_id": chain_id, "role": role, "failure_code": failure_code}
    if role not in {"planner", "executor", "reviewer", "final_human_decision"} or not re.fullmatch(r"[a-z0-9][a-z0-9-]{2,127}", failure_code):
        raise ChainStoreError("external-agent-chain-stop-invalid", "链路停止原因不符合固定格式。")
    _immutable_write(root, _stop_path(chain_id), _canonical(record) + b"\n")
    stored = _load_stop(root, chain_id)
    if stored != record:
        raise ChainStoreError("external-agent-chain-write-verify-failed", "链路停止记录写后校验失败。")
    return stored


def write_planner_candidate(
    root: Path,
    chain_id: str,
    candidate: dict[str, Any],
    *,
    source_attempt_id: str,
    source_manifest_digest: str,
    source_artifact_digest: str,
) -> dict[str, Any]:
    root = root.resolve()
    _ensure_not_stopped(root, chain_id)
    intent = _load_intent(root, chain_id)
    path = _contained(root, _candidate_path(chain_id))
    if path.exists():
        raise ChainStoreError("external-agent-chain-planner-candidate-already-recorded", "规划候选已经存在，不允许覆盖。")
    encoded = _canonical(candidate)
    if len(encoded) > _MAX_ROLE_OUTPUT_BYTES:
        raise ChainStoreError("external-agent-chain-planner-candidate-too-large", "规划候选超过固定大小上限。")
    _validate_schema(root, candidate, _CANDIDATE_SCHEMA)
    if candidate["chain_id"] != chain_id or candidate["goal_digest"] != intent["goal_digest"]:
        raise ChainStoreError("external-agent-chain-planner-candidate-binding-invalid", "规划候选未绑定当前链路目标。")
    source = {
        "attempt_id": _key(source_attempt_id),
        "manifest_digest": source_manifest_digest,
        "artifact_digest": source_artifact_digest,
    }
    if not all(isinstance(value, str) and re.fullmatch(r"sha256:[a-f0-9]{64}", value) for value in source.values() if value != source["attempt_id"]):
        raise ChainStoreError("external-agent-chain-planner-source-invalid", "规划候选来源证据摘要无效。")
    record = {
        "candidate": candidate,
        "candidate_digest": _digest(candidate),
        "source": source,
    }
    _immutable_write(root, _candidate_path(chain_id), _canonical(record) + b"\n")
    stored = _load_json(root, _candidate_path(chain_id), missing_code="external-agent-chain-record-invalid", missing_message="规划候选缺失。")
    if stored != record:
        raise ChainStoreError("external-agent-chain-write-verify-failed", "规划候选写后校验失败。")
    return stored


def _load_candidate(root: Path, chain_id: str) -> dict[str, Any] | None:
    path = _contained(root, _candidate_path(chain_id))
    if not path.exists():
        return None
    record = _load_json(root, _candidate_path(chain_id), missing_code="external-agent-chain-record-invalid", missing_message="规划候选缺失。")
    candidate = record.get("candidate")
    if not isinstance(candidate, dict):
        raise ChainStoreError("external-agent-chain-record-invalid", "规划候选记录无效。")
    _validate_schema(root, candidate, _CANDIDATE_SCHEMA)
    if record.get("candidate_digest") != _digest(candidate):
        raise ChainStoreError("external-agent-chain-planner-candidate-drift", "规划候选摘要不一致。")
    return record


def write_execution_receipt(
    root: Path,
    chain_id: str,
    *,
    attempt_id: str,
    manifest_digest: str,
    artifact_digest: str,
) -> dict[str, Any]:
    root = root.resolve()
    _ensure_not_stopped(root, chain_id)
    _load_intent(root, chain_id)
    if _load_candidate(root, chain_id) is None:
        raise ChainStoreError("external-agent-chain-planner-candidate-missing", "尚未归档规划候选。")
    path = _contained(root, _execution_path(chain_id))
    if path.exists():
        raise ChainStoreError("external-agent-chain-execution-receipt-already-recorded", "执行证据已经绑定到当前链路。")
    record = {
        "attempt_id": _key(attempt_id),
        "manifest_digest": manifest_digest,
        "artifact_digest": artifact_digest,
    }
    if not _valid_hash(record["manifest_digest"]) or not _valid_hash(record["artifact_digest"]):
        raise ChainStoreError("external-agent-chain-execution-receipt-invalid", "执行证据摘要无效。")
    _immutable_write(root, _execution_path(chain_id), _canonical(record) + b"\n")
    stored = _load_json(root, _execution_path(chain_id), missing_code="external-agent-chain-record-invalid", missing_message="执行证据缺失。")
    if stored != record:
        raise ChainStoreError("external-agent-chain-write-verify-failed", "执行证据写后校验失败。")
    return stored


def _load_execution_receipt(root: Path, chain_id: str) -> dict[str, Any] | None:
    path = _contained(root, _execution_path(chain_id))
    if not path.exists():
        return None
    record = _load_json(root, _execution_path(chain_id), missing_code="external-agent-chain-record-invalid", missing_message="执行证据缺失。")
    if set(record) != {"attempt_id", "manifest_digest", "artifact_digest"} or not isinstance(record.get("attempt_id"), str) or not _valid_hash(record.get("manifest_digest")) or not _valid_hash(record.get("artifact_digest")):
        raise ChainStoreError("external-agent-chain-execution-receipt-invalid", "执行证据记录无效。")
    return record


def write_review_advice(root: Path, chain_id: str, advice: dict[str, Any]) -> dict[str, Any]:
    root = root.resolve()
    _ensure_not_stopped(root, chain_id)
    _load_intent(root, chain_id)
    candidate = _load_candidate(root, chain_id)
    if candidate is None:
        raise ChainStoreError("external-agent-chain-planner-candidate-missing", "尚未归档规划候选。")
    execution = _load_execution_receipt(root, chain_id)
    if execution is None:
        raise ChainStoreError("external-agent-chain-execution-receipt-missing", "尚未绑定执行证据。")
    path = _contained(root, _advice_path(chain_id))
    if path.exists():
        raise ChainStoreError("external-agent-chain-review-advice-already-recorded", "审阅建议已经存在，不允许覆盖。")
    encoded = _canonical(advice)
    if len(encoded) > _MAX_ROLE_OUTPUT_BYTES:
        raise ChainStoreError("external-agent-chain-review-advice-too-large", "审阅建议超过固定大小上限。")
    _validate_schema(root, advice, _ADVICE_SCHEMA)
    if (
        advice["chain_id"] != chain_id
        or advice["planner_candidate_digest"] != candidate["candidate_digest"]
        or advice["execution_attempt_id"] != execution["attempt_id"]
        or advice["execution_manifest_digest"] != execution["manifest_digest"]
        or advice["execution_artifact_digest"] != execution["artifact_digest"]
    ):
        raise ChainStoreError("external-agent-chain-review-advice-binding-invalid", "审阅建议未绑定当前规划候选和执行证据。")
    finding_ids = [item.get("finding_id") for item in advice["findings"]]
    if len(finding_ids) != len(set(finding_ids)):
        raise ChainStoreError("external-agent-chain-review-advice-findings-duplicate", "审阅建议包含重复问题编号。")
    record = {"advice": advice, "advice_digest": _digest(advice)}
    _immutable_write(root, _advice_path(chain_id), _canonical(record) + b"\n")
    stored = _load_json(root, _advice_path(chain_id), missing_code="external-agent-chain-record-invalid", missing_message="审阅建议缺失。")
    if stored != record:
        raise ChainStoreError("external-agent-chain-write-verify-failed", "审阅建议写后校验失败。")
    return stored


def _load_advice(root: Path, chain_id: str) -> dict[str, Any] | None:
    path = _contained(root, _advice_path(chain_id))
    if not path.exists():
        return None
    record = _load_json(root, _advice_path(chain_id), missing_code="external-agent-chain-record-invalid", missing_message="审阅建议缺失。")
    advice = record.get("advice")
    if not isinstance(advice, dict):
        raise ChainStoreError("external-agent-chain-record-invalid", "审阅建议记录无效。")
    _validate_schema(root, advice, _ADVICE_SCHEMA)
    if record.get("advice_digest") != _digest(advice):
        raise ChainStoreError("external-agent-chain-review-advice-drift", "审阅建议摘要不一致。")
    return record


def _load_pending_completion(root: Path, chain_id: str) -> dict[str, Any] | None:
    path = _contained(root, _pending_completion_path(chain_id))
    if not path.exists():
        return None
    record = _load_json(root, _pending_completion_path(chain_id), missing_code="external-agent-chain-record-invalid", missing_message="链路完成待恢复记录缺失。")
    required = {"chain_id", "attempt_id", "decision", "comment_digest", "advice_digest", "committed_at"}
    if (
        set(record) != required
        or record.get("chain_id") != chain_id
        or not isinstance(record.get("attempt_id"), str)
        or record.get("decision") not in {"approve", "request_changes"}
        or not all(_valid_hash(record.get(name)) for name in ("comment_digest", "advice_digest"))
        or not isinstance(record.get("committed_at"), str)
        or len(record["committed_at"]) < 20
        or len(record["committed_at"]) > 40
    ):
        raise ChainStoreError("external-agent-chain-finalization-pending-invalid", "链路完成待恢复记录无效。")
    return record


def prepare_chain_completion(
    root: Path,
    chain_id: str,
    *,
    decision: str,
    comment_digest: str,
    advice_digest: str,
    committed_at: str,
) -> dict[str, Any]:
    """Persist the fixed recovery binding before the one-time human review write."""
    root = root.resolve()
    _ensure_not_stopped(root, chain_id)
    _load_intent(root, chain_id)
    execution = _load_execution_receipt(root, chain_id)
    advice = _load_advice(root, chain_id)
    if execution is None or advice is None:
        raise ChainStoreError("external-agent-chain-completion-prerequisite-missing", "链路尚未具备完成条件。")
    if _contained(root, _completion_path(chain_id)).exists():
        raise ChainStoreError("external-agent-chain-completion-already-recorded", "链路完成回执已经存在。")
    if _load_pending_completion(root, chain_id) is not None:
        raise ChainStoreError("external-agent-chain-finalization-pending-already-recorded", "该链路已有待恢复的最终人工决定。")
    if (
        decision not in {"approve", "request_changes"}
        or not _valid_hash(comment_digest)
        or advice_digest != advice["advice_digest"]
        or not isinstance(committed_at, str)
        or len(committed_at) < 20
        or len(committed_at) > 40
    ):
        raise ChainStoreError("external-agent-chain-finalization-pending-invalid", "待恢复的最终人工决定未绑定当前审阅建议。")
    record = {
        "chain_id": chain_id,
        "attempt_id": execution["attempt_id"],
        "decision": decision,
        "comment_digest": comment_digest,
        "advice_digest": advice_digest,
        "committed_at": committed_at,
    }
    _immutable_write(root, _pending_completion_path(chain_id), _canonical(record) + b"\n")
    stored = _load_pending_completion(root, chain_id)
    if stored != record:
        raise ChainStoreError("external-agent-chain-write-verify-failed", "链路完成待恢复记录写后校验失败。")
    return stored


def _delete_pending_completion(root: Path, chain_id: str) -> None:
    path = _contained(root, _pending_completion_path(chain_id))
    try:
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or stat.S_ISLNK(info.st_mode) or info.st_nlink != 1:
            raise ChainStoreError("external-agent-chain-file-unsafe", "链路完成待恢复记录不是安全的普通文件。")
        path.unlink()
    except ChainStoreError:
        raise
    except OSError as exc:
        raise ChainStoreError("external-agent-chain-write-io-failed", "链路完成待恢复记录清理失败。") from exc
    if path.exists():
        raise ChainStoreError("external-agent-chain-write-verify-failed", "链路完成待恢复记录清理校验失败。")


def finalize_chain_completion(
    root: Path,
    chain_id: str,
    *,
    human_review: dict[str, Any],
) -> dict[str, Any]:
    """Finalize exactly the decision pinned by ``prepare_chain_completion``."""
    root = root.resolve()
    pending = _load_pending_completion(root, chain_id)
    if pending is None:
        raise ChainStoreError("external-agent-chain-finalization-pending-missing", "没有找到可恢复的链路完成记录。")
    required = {"review_id", "decision", "comment_digest", "manifest_digest", "artifact_digest"}
    if (
        set(human_review) != required
        or human_review.get("decision") != pending["decision"]
        or human_review.get("comment_digest") != pending["comment_digest"]
    ):
        raise ChainStoreError("external-agent-chain-finalization-binding-invalid", "人工审阅与待恢复的最终决定不一致。")
    completion = write_chain_completion(
        root, chain_id, human_review=human_review,
        advice_digest=pending["advice_digest"], committed_at=pending["committed_at"],
    )
    _delete_pending_completion(root, chain_id)
    return completion


def recover_chain_completion(root: Path, chain_id: str) -> dict[str, Any]:
    """Fixed recovery: read an existing stage-88 review; never call an Agent."""
    from .external_agent_evidence_store import EvidenceStoreError, inspect_evidence

    root = root.resolve()
    pending = _load_pending_completion(root, chain_id)
    if pending is None:
        completion = _load_completion(root, chain_id)
        if completion is not None:
            return completion
        raise ChainStoreError("external-agent-chain-finalization-pending-missing", "没有找到可恢复的链路完成记录。")
    try:
        evidence = inspect_evidence(root, pending["attempt_id"])
    except EvidenceStoreError as exc:
        raise ChainStoreError("external-agent-chain-finalization-evidence-unavailable", "无法读取既有执行证据以恢复链路完成回执。") from exc
    review = evidence.get("review") if isinstance(evidence, dict) else None
    record = review.get("record") if isinstance(review, dict) else None
    if evidence.get("status") != "pass" or not isinstance(record, dict):
        raise ChainStoreError("external-agent-chain-finalization-review-missing", "既有人工审阅记录尚不可用于恢复链路完成回执。")
    return finalize_chain_completion(
        root, chain_id,
        human_review={
            "review_id": record.get("review_id"),
            "decision": record.get("decision"),
            "comment_digest": record.get("comment_digest"),
            "manifest_digest": evidence.get("manifest_digest"),
            "artifact_digest": evidence.get("artifact", {}).get("content_hash") if isinstance(evidence.get("artifact"), dict) else None,
        },
    )


def write_chain_completion(
    root: Path,
    chain_id: str,
    *,
    human_review: dict[str, Any],
    advice_digest: str,
    committed_at: str,
) -> dict[str, Any]:
    root = root.resolve()
    _ensure_not_stopped(root, chain_id)
    _load_intent(root, chain_id)
    execution = _load_execution_receipt(root, chain_id)
    advice = _load_advice(root, chain_id)
    if execution is None or advice is None:
        raise ChainStoreError("external-agent-chain-completion-prerequisite-missing", "链路尚未具备完成条件。")
    path = _contained(root, _completion_path(chain_id))
    if path.exists():
        raise ChainStoreError("external-agent-chain-completion-already-recorded", "链路完成回执已经存在。")
    required = {"review_id", "decision", "comment_digest", "manifest_digest", "artifact_digest"}
    if set(human_review) != required or human_review.get("decision") not in {"approve", "request_changes"} or not isinstance(human_review.get("review_id"), str) or not all(_valid_hash(human_review.get(name)) for name in ("comment_digest", "manifest_digest", "artifact_digest")):
        raise ChainStoreError("external-agent-chain-completion-invalid", "人工审阅完成信息无效。")
    if (
        advice_digest != advice["advice_digest"]
        or human_review["manifest_digest"] != execution["manifest_digest"]
        or human_review["artifact_digest"] != execution["artifact_digest"]
        or not isinstance(committed_at, str)
        or len(committed_at) < 20
        or len(committed_at) > 40
    ):
        raise ChainStoreError("external-agent-chain-completion-binding-invalid", "人工审阅未绑定当前链路证据和审阅建议。")
    record = {
        "review_id": human_review["review_id"],
        "decision": human_review["decision"],
        "comment_digest": human_review["comment_digest"],
        "manifest_digest": human_review["manifest_digest"],
        "artifact_digest": human_review["artifact_digest"],
        "advice_digest": advice_digest,
        "committed_at": committed_at,
    }
    _immutable_write(root, _completion_path(chain_id), _canonical(record) + b"\n")
    stored = _load_json(root, _completion_path(chain_id), missing_code="external-agent-chain-record-invalid", missing_message="链路完成回执缺失。")
    if stored != record:
        raise ChainStoreError("external-agent-chain-write-verify-failed", "链路完成回执写后校验失败。")
    return stored


def _load_completion(root: Path, chain_id: str) -> dict[str, Any] | None:
    path = _contained(root, _completion_path(chain_id))
    if not path.exists():
        return None
    record = _load_json(root, _completion_path(chain_id), missing_code="external-agent-chain-record-invalid", missing_message="链路完成回执缺失。")
    required = {"review_id", "decision", "comment_digest", "manifest_digest", "artifact_digest", "advice_digest", "committed_at"}
    if set(record) != required or record.get("decision") not in {"approve", "request_changes"} or not isinstance(record.get("review_id"), str) or not all(_valid_hash(record.get(name)) for name in ("comment_digest", "manifest_digest", "artifact_digest", "advice_digest")):
        raise ChainStoreError("external-agent-chain-completion-invalid", "链路完成回执无效。")
    return record


def inspect_external_agent_chain(root: Path, chain_id: str) -> dict[str, Any]:
    root = root.resolve()
    intent = _load_intent(root, chain_id)
    candidate = _load_candidate(root, chain_id)
    execution = _load_execution_receipt(root, chain_id)
    advice = _load_advice(root, chain_id)
    completion = _load_completion(root, chain_id)
    pending_completion = _load_pending_completion(root, chain_id)
    stop = _load_stop(root, chain_id)
    status = "awaiting_planner_confirmation"
    if candidate is not None:
        status = "awaiting_executor_confirmation"
    if execution is not None:
        status = "awaiting_reviewer_confirmation"
    if advice is not None:
        status = "awaiting_final_human_decision"
    if pending_completion is not None:
        status = "finalization_pending"
    if stop is not None:
        status = "stopped"
    if completion is not None:
        status = "approved" if completion["decision"] == "approve" else "changes_requested"
    return {
        "chain_id": chain_id,
        "status": status,
        "intent": intent,
        **({"planner_candidate": candidate} if candidate is not None else {}),
        **({"execution": execution} if execution is not None else {}),
        **({"review_advice": advice} if advice is not None else {}),
        **({"finalization_pending": pending_completion} if pending_completion is not None else {}),
        **({"stop": stop} if stop is not None else {}),
        **({"completion": completion} if completion is not None else {}),
    }
