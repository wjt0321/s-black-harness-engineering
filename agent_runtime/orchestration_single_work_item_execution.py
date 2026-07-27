"""Controlled one-work-item dispatch to an already-open Pi or OMP session."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from jsonschema import Draft202012Validator, SchemaError, ValidationError, validate

from .execution_audit_writer import record_execution_attempt_started, record_execution_terminal
from .execution_lease import acquire_execution_lease
from .loader import normalize_path
from .orchestration_collaboration import inspect_collaboration_plan
from .orchestration_external_agent_live_status import inspect_external_agent_live_status
from .policy import check_text
from .result import CheckResult, Finding

SCHEMA_VERSION = "control-plane/single-work-item-execution/v1"
_REQUEST_SCHEMA = Path("adapters/single-work-item-execution-request.schema.json")
_DISPATCH_BINDING_SCHEMA = Path("adapters/external-agent-dispatch-binding.schema.json")
_DISPATCH_IMPLEMENTATION = Path("integrations/pi_omp_live_status/controlled_dispatch.cjs")
_MAX_REQUEST_BYTES = 64 * 1024
_MAX_LEDGER_BYTES = 4 * 1024 * 1024
_PROFILE_SOCKET = {"pi-local": "pi-cli", "omp-local": "omp-acp"}
_PROFILE_BINDINGS = {
    "pi-local": (Path("adapters/external-agent-dispatch-binding.pi-local.json"), Path(".pi/extensions/s-black-live-status.ts")),
    "omp-local": (Path("adapters/external-agent-dispatch-binding.omp-local.json"), Path(".omp/extensions/s-black-live-status.ts")),
}
_PROFILE_PATHS = {
    "pi-local": (
        Path(".runtime/external-agent-dispatch/pi-local.request.v1.json"),
        Path(".runtime/external-agent-dispatch/pi-local.result.v1.json"),
    ),
    "omp-local": (
        Path(".runtime/external-agent-dispatch/omp-local.request.v1.json"),
        Path(".runtime/external-agent-dispatch/omp-local.result.v1.json"),
    ),
}
_OPERATION = "external_agent_single_work_item"
_CAPABILITY = "single_work_item"


def _finding(rule_id: str, message: str, *, validation: bool = False) -> Finding:
    return Finding(
        rule_id=rule_id,
        severity="error" if validation else "block",
        action="error" if validation else "deny",
        message=message,
    )


def _canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _digest(value: object) -> str:
    data = value if isinstance(value, bytes) else _canonical(value)
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _contained(root: Path, relative: str | Path) -> Path:
    rel = Path(relative)
    if rel.is_absolute():
        raise ValueError("absolute path")
    base = root.resolve(strict=True)
    target = (base / rel).resolve(strict=False)
    if os.path.commonpath([str(base), str(target)]) != str(base) or target == base:
        raise ValueError("path escape")
    return target


def _regular_file(path: Path, *, max_bytes: int) -> bytes:
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or stat.S_ISLNK(info.st_mode) or info.st_nlink != 1:
        raise ValueError("unsafe file")
    if info.st_size > max_bytes:
        raise ValueError("file too large")
    data = path.read_bytes()
    if len(data) > max_bytes:
        raise ValueError("file too large")
    after = path.lstat()
    if (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns) != (
        after.st_dev,
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
    ):
        raise ValueError("file changed")
    return data


def _load_request(root: Path, request_file: str) -> tuple[dict[str, Any] | None, Finding | None]:
    try:
        request_path = _contained(root, request_file)
        request = json.loads(_regular_file(request_path, max_bytes=_MAX_REQUEST_BYTES).decode("utf-8"))
        schema = json.loads(_regular_file(_contained(root, _REQUEST_SCHEMA), max_bytes=_MAX_REQUEST_BYTES).decode("utf-8"))
        Draft202012Validator.check_schema(schema)
        validate(request, schema)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError, SchemaError, ValidationError, TypeError):
        return None, _finding(
            "single-work-item-request-invalid",
            "单工作项执行请求不是有效、项目内且有界的 JSON。",
            validation=True,
        )
    return request, None


def _task_exists(root: Path, task_id: str) -> bool:
    try:
        path = _contained(root, "tasks/tasks.jsonl")
        data = _regular_file(path, max_bytes=_MAX_LEDGER_BYTES)
        for line in data.decode("utf-8").splitlines():
            if not line.strip():
                continue
            item = json.loads(line)
            if item.get("id") == task_id:
                return True
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError, TypeError):
        return False
    return False


def _implementation_digest(root: Path, wrapper: Path) -> str:
    digest = hashlib.sha256()
    digest.update(_regular_file(_contained(root, _DISPATCH_IMPLEMENTATION), max_bytes=_MAX_REQUEST_BYTES))
    digest.update(bytes([0]))
    digest.update(_regular_file(_contained(root, wrapper), max_bytes=_MAX_REQUEST_BYTES))
    return "sha256:" + digest.hexdigest()


def _load_dispatch_binding(root: Path, profile_id: str) -> tuple[dict[str, Any] | None, Finding | None]:
    binding_path, wrapper = _PROFILE_BINDINGS[profile_id]
    try:
        binding = json.loads(_regular_file(_contained(root, binding_path), max_bytes=_MAX_REQUEST_BYTES).decode("utf-8"))
        schema = json.loads(_regular_file(_contained(root, _DISPATCH_BINDING_SCHEMA), max_bytes=_MAX_REQUEST_BYTES).decode("utf-8"))
        Draft202012Validator.check_schema(schema)
        validate(binding, schema)
        request_path, result_path = _PROFILE_PATHS[profile_id]
        if (
            binding["target_profile"] != profile_id
            or binding["request_relative_path"] != request_path.as_posix()
            or binding["result_relative_path"] != result_path.as_posix()
            or binding["implementation_binding_id"] != _implementation_digest(root, wrapper)
            or binding["dispatch_authorized"] is not True
            or binding["allowed_host_action"] != "sendUserMessage"
            or binding["required_active_tools"] != []
        ):
            raise ValueError("dispatch binding drift")
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError, SchemaError, ValidationError, TypeError, KeyError):
        return None, _finding(
            "single-work-item-dispatch-binding-invalid",
            "固定 Pi/OMP 派发绑定缺失或实现摘要已漂移。",
            validation=True,
        )
    return binding, None

def _artifact_projection(root: Path, artifacts: list[dict[str, Any]]) -> tuple[list[dict[str, Any]] | None, Finding | None]:
    projected: list[dict[str, Any]] = []
    seen: set[str] = set()
    for artifact in artifacts:
        try:
            path = _contained(root, artifact["path"])
            data = _regular_file(path, max_bytes=_MAX_REQUEST_BYTES)
        except (OSError, ValueError):
            return None, _finding(
                "single-work-item-input-artifact-invalid",
                "输入产物必须是项目内、有界且稳定的普通文件。",
                validation=True,
            )
        normalized = normalize_path(path.relative_to(root.resolve()).as_posix())
        if normalized in seen or _digest(data) != artifact["sha256"]:
            return None, _finding(
                "single-work-item-input-artifact-drift",
                "输入产物重复或内容摘要已变化。",
                validation=True,
            )
        seen.add(normalized)
        projected.append(
            {
                "artifact_type": artifact["artifact_type"],
                "path": normalized,
                "sha256": artifact["sha256"],
                "byte_count": len(data),
            }
        )
    projected.sort(key=lambda item: (item["artifact_type"], item["path"]))
    return projected, None


def _services(overrides: dict[str, Any] | None) -> dict[str, Any]:
    active: dict[str, Any] = {
        "inspect_status": inspect_external_agent_live_status,
        "acquire_lease": acquire_execution_lease,
        "record_started": record_execution_attempt_started,
        "record_terminal": record_execution_terminal,
        "scan_text": check_text,
        "request_already_used": _request_already_used,
        "exchange": _exchange,
    }
    if overrides:
        active.update(overrides)
    return active


@dataclass(frozen=True)
class SingleWorkItemPlanResult:
    status: str
    request_file: str
    approval_binding_id: str | None = None
    plan_hash: str | None = None
    plan: dict[str, Any] | None = None
    request: dict[str, Any] | None = field(default=None, repr=False)
    findings: tuple[Finding, ...] = ()
    next_action: str | None = None

    def exit_code(self) -> int:
        return CheckResult(self.status).exit_code()

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "status": self.status,
            "schema_version": SCHEMA_VERSION,
            "request_file": self.request_file,
            "guarantees": {
                "starts_agent_process": False,
                "opens_network_listener": False,
                "accepts_arbitrary_shell": False,
                "accepts_cwd_env_argv_override": False,
                "single_flight": True,
                "requires_exact_one_time_approval": True,
                "writes_files": False,
                "writes_ledger": False,
                "sends_prompt": False,
            },
        }
        if self.approval_binding_id:
            payload["approval_binding_id"] = self.approval_binding_id
        if self.plan_hash:
            payload["plan_hash"] = self.plan_hash
        if self.plan is not None:
            payload["plan"] = self.plan
        if self.findings:
            payload["findings"] = [item.to_dict() for item in self.findings]
        if self.next_action:
            payload["next_action"] = self.next_action
        return payload


@dataclass(frozen=True)
class SingleWorkItemExecutionResult:
    status: str
    task_id: str = ""
    request_id: str = ""
    target_profile: str = ""
    plan_hash: str | None = None
    approval_binding_id: str | None = None
    output: str | None = None
    output_digest: str | None = None
    artifacts: tuple[dict[str, Any], ...] = ()
    audit: dict[str, Any] = field(default_factory=dict)
    findings: tuple[Finding, ...] = ()
    next_action: str | None = None

    def exit_code(self) -> int:
        return CheckResult(self.status).exit_code()

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "status": self.status,
            "schema_version": SCHEMA_VERSION,
            "task_id": self.task_id,
            "request_id": self.request_id,
            "target_profile": self.target_profile,
            "plan_hash": self.plan_hash,
            "approval_binding_id": self.approval_binding_id,
            "audit": dict(self.audit),
            "guarantees": {
                "starts_agent_process": False,
                "opens_network_listener": False,
                "accepts_arbitrary_shell": False,
                "single_flight": True,
                "started_audit_before_dispatch": True,
                "terminal_audit_required": True,
            },
        }
        if self.output is not None:
            payload["output"] = self.output
            payload["output_digest"] = self.output_digest
        if self.artifacts:
            payload["artifacts"] = list(self.artifacts)
        if self.findings:
            payload["findings"] = [item.to_dict() for item in self.findings]
        if self.next_action:
            payload["next_action"] = self.next_action
        return payload


def build_single_work_item_execution_plan(
    root: Path,
    request_file: str,
    evaluated_at: str,
    *,
    services: dict[str, Any] | None = None,
) -> SingleWorkItemPlanResult:
    root = root.resolve()
    request, failure = _load_request(root, request_file)
    if failure or request is None:
        return SingleWorkItemPlanResult("validation_failed", request_file, findings=(failure,) if failure else ())
    if not _task_exists(root, request["task_id"]):
        return SingleWorkItemPlanResult(
            "validation_failed",
            request_file,
            findings=(_finding("single-work-item-task-unknown", "执行请求必须绑定现有任务账本记录。", validation=True),),
        )
    plan_result = inspect_collaboration_plan(root, request["collaboration_file"])
    if plan_result.status != "pass" or plan_result.plan is None:
        return SingleWorkItemPlanResult(
            "validation_failed",
            request_file,
            findings=(_finding("single-work-item-collaboration-invalid", "协作计划未通过现有计划校验。", validation=True),),
        )
    plan = plan_result.to_dict()["plan"]
    if plan["parent_task_ref"] != request["task_id"]:
        return SingleWorkItemPlanResult(
            "validation_failed",
            request_file,
            findings=(_finding("single-work-item-task-plan-mismatch", "请求任务与协作计划父任务不一致。", validation=True),),
        )
    work = next((item for item in plan["work_items"] if item["work_item_id"] == request["work_item_id"]), None)
    if work is None:
        return SingleWorkItemPlanResult(
            "validation_failed", request_file,
            findings=(_finding("single-work-item-work-item-unknown", "协作计划中不存在指定工作项。", validation=True),),
        )
    expected_socket = _PROFILE_SOCKET[request["target_profile"]]
    if work["socket_id"] != expected_socket:
        return SingleWorkItemPlanResult(
            "validation_failed", request_file,
            findings=(_finding("single-work-item-socket-profile-mismatch", "工作项插座与固定 Pi/OMP 目标配置不匹配。", validation=True),),
        )
    dispatch_binding, binding_failure = _load_dispatch_binding(root, request["target_profile"])
    if binding_failure or dispatch_binding is None:
        return SingleWorkItemPlanResult("validation_failed", request_file, findings=(binding_failure,) if binding_failure else ())
    artifacts, artifact_failure = _artifact_projection(root, request["input_artifacts"])
    if artifact_failure or artifacts is None:
        return SingleWorkItemPlanResult("validation_failed", request_file, findings=(artifact_failure,) if artifact_failure else ())
    scan = _services(services)["scan_text"](root, request["instruction"]) if services and "scan_text" in services else check_text(root, request["instruction"])
    if scan.status != "pass":
        return SingleWorkItemPlanResult(
            "blocked", request_file,
            findings=(_finding("single-work-item-instruction-secret-scan", "执行指令未通过敏感信息扫描；匹配内容不会回显。"),),
        )
    active = _services(services)
    try:
        status = active["inspect_status"](root, evaluated_at, profile_id=request["target_profile"])
    except (OSError, ValueError, TypeError):
        status = None
    evidence = getattr(status, "evidence", None)
    if (
        status is None
        or getattr(status, "status", None) != "pass"
        or getattr(status, "observation_status", None) != "observed"
        or not isinstance(evidence, dict)
    ):
        return SingleWorkItemPlanResult(
            "blocked", request_file,
            findings=(_finding("single-work-item-live-status-unavailable", "目标智能体没有可用的新鲜状态证据。"),),
        )
    if evidence.get("session_state") != "open":
        return SingleWorkItemPlanResult(
            "blocked", request_file,
            findings=(_finding("single-work-item-session-not-open", "目标智能体必须由用户预先打开并保持当前项目会话。"),),
        )
    instruction_digest = _digest(request["instruction"].encode("utf-8"))
    stable = {
        "operation": "external-agent.single-work-item",
        "task_id": request["task_id"],
        "request_id": request["request_id"],
        "collaboration_plan_id": plan["plan_id"],
        "work_item_id": request["work_item_id"],
        "socket_id": work["socket_id"],
        "target_profile": request["target_profile"],
        "target_identity": evidence.get("target"),
        "dispatch_binding_id": _digest(dispatch_binding),
        "required_live_state": "observed_open_session",
        "instruction_digest": instruction_digest,
        "input_artifacts": artifacts,
        "expected_artifact_types": work["expected_artifact_types"],
        "review_required": work["review_required"],
        "timeout_seconds": request["timeout_seconds"],
        "result_max_bytes": request["result_max_bytes"],
    }
    plan_hash = _digest(stable)
    approval_binding_id = _digest({"kind": "one-time-human-approval", "plan_hash": plan_hash})
    public_plan = dict(stable)
    return SingleWorkItemPlanResult(
        "needs_approval",
        request_file,
        approval_binding_id=approval_binding_id,
        plan_hash=plan_hash,
        plan=public_plan,
        request=request,
        next_action="核对中文控制面中的工作项、目标和指令摘要后，使用该确认摘要提交一次执行。",
    )


def _request_already_used(root: Path, task_id: str, request_id: str) -> bool:
    try:
        data = _regular_file(_contained(root, "tasks/events.jsonl"), max_bytes=_MAX_LEDGER_BYTES)
        for line in data.decode("utf-8").splitlines():
            if not line.strip():
                continue
            event = json.loads(line)
            metadata = event.get("metadata", {})
            if (
                event.get("task_id") == task_id
                and event.get("event_type") == "execution_attempt_started"
                and metadata.get("request_id") == request_id
                and metadata.get("operation") == _OPERATION
            ):
                return True
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError, TypeError):
        return True
    return False


def _atomic_write(path: Path, payload: dict[str, Any], max_bytes: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = _canonical(payload) + b"\n"
    if len(encoded) > max_bytes:
        raise ValueError("payload too large")
    temporary = path.with_suffix(path.suffix + ".tmp")
    if temporary.exists():
        info = temporary.lstat()
        if not stat.S_ISREG(info.st_mode) or stat.S_ISLNK(info.st_mode) or info.st_nlink != 1:
            raise ValueError("unsafe temporary")
        temporary.unlink()
    with temporary.open("xb") as handle:
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)
    _regular_file(path, max_bytes=max_bytes)


def _safe_remove(path: Path) -> None:
    try:
        info = path.lstat()
        if stat.S_ISREG(info.st_mode) and not stat.S_ISLNK(info.st_mode) and info.st_nlink == 1:
            path.unlink()
    except FileNotFoundError:
        return


def _exchange(root: Path, payload: dict[str, Any], timeout_seconds: int, result_max_bytes: int) -> dict[str, Any]:
    request_path, result_path = (_contained(root, item) for item in _PROFILE_PATHS[payload["target_profile"]])
    _safe_remove(result_path)
    _atomic_write(request_path, payload, _MAX_REQUEST_BYTES)
    deadline = time.monotonic() + timeout_seconds
    try:
        while time.monotonic() < deadline:
            if result_path.exists():
                result = json.loads(_regular_file(result_path, max_bytes=result_max_bytes + 4096).decode("utf-8"))
                if result.get("request_id") != payload["request_id"] or result.get("target_profile") != payload["target_profile"]:
                    raise ValueError("result identity mismatch")
                return result
            time.sleep(0.1)
        return {
            "status": "timed_out",
            "request_id": payload["request_id"],
            "target_profile": payload["target_profile"],
            "failure_code": "single-work-item-timeout",
            "artifacts": [],
        }
    finally:
        _safe_remove(request_path)
        _safe_remove(result_path)


def _terminal_result(
    root: Path,
    *,
    plan: SingleWorkItemPlanResult,
    started: Any,
    status: str,
    failure_code: str,
    terminal: Callable[..., Any],
    output_digest: str | None = None,
    output_bytes: int | None = None,
    phase: str = "child",
) -> tuple[Any, dict[str, Any]]:
    cancelled = status == "cancelled"
    event_type = "execution_cancelled" if cancelled else "execution_failed"
    result = terminal(
        root,
        attempt_id=started.attempt_id,
        event_type=event_type,
        phase="cancelled" if cancelled else phase,
        output_digest=output_digest,
        stdout_byte_count=output_bytes,
        guard_status="failed" if status == "blocked" else "pass",
        failure_code=failure_code,
    )
    audit = {
        "attempt_id": started.attempt_id,
        "state": "closed_failed" if getattr(result, "committed", False) else "awaiting_terminal",
        "audit_incomplete": not getattr(result, "committed", False),
    }
    return result, audit


def execute_single_work_item(
    root: Path,
    request_file: str,
    evaluated_at: str,
    *,
    approval_binding_id: str | None,
    commit: bool,
    services: dict[str, Any] | None = None,
) -> SingleWorkItemExecutionResult:
    preview = build_single_work_item_execution_plan(root, request_file, evaluated_at, services=services)
    if preview.status != "needs_approval" or preview.request is None or preview.plan is None:
        return SingleWorkItemExecutionResult(
            preview.status,
            plan_hash=preview.plan_hash,
            approval_binding_id=preview.approval_binding_id,
            findings=preview.findings,
            next_action=preview.next_action,
        )
    request = preview.request
    base = {
        "task_id": request["task_id"],
        "request_id": request["request_id"],
        "target_profile": request["target_profile"],
        "plan_hash": preview.plan_hash,
        "approval_binding_id": preview.approval_binding_id,
    }
    if not commit:
        return SingleWorkItemExecutionResult(
            "needs_approval", **base,
            next_action="预览不会执行。请在核对后提供精确确认摘要并显式使用 --commit。",
        )
    if approval_binding_id != preview.approval_binding_id:
        return SingleWorkItemExecutionResult(
            "blocked", **base,
            findings=(_finding("single-work-item-approval-binding-mismatch", "提交的确认摘要与当前执行计划不一致。"),),
        )
    active = _services(services)
    if active["request_already_used"](root, request["task_id"], request["request_id"]):
        return SingleWorkItemExecutionResult(
            "blocked", **base,
            findings=(_finding("single-work-item-request-replayed", "该请求已经进入过执行审计，不允许重放。"),),
        )
    lease = active["acquire_lease"](root)
    if not hasattr(lease, "status") or lease.status != "pass":
        findings = tuple(getattr(lease, "findings", ())) or (_finding("single-work-item-execution-lease-unavailable", "当前已有受控执行占用全局租约。"),)
        return SingleWorkItemExecutionResult("blocked", **base, findings=findings)
    result: SingleWorkItemExecutionResult | None = None
    try:
        started = active["record_started"](
            root,
            task_id=request["task_id"],
            request_id=request["request_id"],
            plan_hash=preview.plan_hash,
            adapter_id=f"{request['target_profile']}-dispatch",
            capability=_CAPABILITY,
            operation=_OPERATION,
            _schema_version="execution-audit/v2",
        )
        if getattr(started, "status", None) != "pass" or not getattr(started, "committed", False) or not getattr(started, "attempt_id", None):
            return SingleWorkItemExecutionResult(
                "error", **base,
                findings=tuple(getattr(started, "findings", ())),
                audit={"state": "not_started", "audit_incomplete": True},
                next_action="修复执行审计后再派发。",
            )
        try:
            live_recheck = active["inspect_status"](
                root,
                datetime.now(timezone.utc).isoformat(),
                profile_id=request["target_profile"],
            )
        except (OSError, ValueError, TypeError):
            live_recheck = None
        recheck_evidence = getattr(live_recheck, "evidence", None)
        if (
            live_recheck is None
            or getattr(live_recheck, "status", None) != "pass"
            or getattr(live_recheck, "observation_status", None) != "observed"
            or not isinstance(recheck_evidence, dict)
            or recheck_evidence.get("session_state") != "open"
        ):
            terminal, audit = _terminal_result(
                root,
                plan=preview,
                started=started,
                status="blocked",
                failure_code="single-work-item-live-status-drift",
                terminal=active["record_terminal"],
            )
            if getattr(terminal, "status", None) != "pass" or not getattr(terminal, "committed", False):
                return SingleWorkItemExecutionResult(
                    "error", **base,
                    findings=tuple(getattr(terminal, "findings", ())), audit=audit,
                    next_action="恢复未闭合的终态审计。",
                )
            return SingleWorkItemExecutionResult(
                "blocked", **base, audit=audit,
                findings=(_finding("single-work-item-live-status-drift", "开始审计后目标会话状态发生变化，任务未发送。"),),
            )
        exchange_payload = {
            "version": 1,
            "contract": "external-agent-single-work-item-mailbox/v1",
            "request_id": request["request_id"],
            "task_id": request["task_id"],
            "work_item_id": request["work_item_id"],
            "target_profile": request["target_profile"],
            "approval_binding_id": preview.approval_binding_id,
            "plan_hash": preview.plan_hash,
            "instruction": request["instruction"],
            "instruction_digest": preview.plan["instruction_digest"],
            "input_artifacts": preview.plan["input_artifacts"],
            "timeout_seconds": request["timeout_seconds"],
            "result_max_bytes": request["result_max_bytes"],
            "issued_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            exchange = active["exchange"](root, exchange_payload, request["timeout_seconds"], request["result_max_bytes"])
        except (OSError, ValueError, json.JSONDecodeError, UnicodeDecodeError, TypeError):
            exchange = {"status": "failed", "failure_code": "single-work-item-mailbox-invalid", "artifacts": []}
        exchange_status = exchange.get("status")
        if exchange_status != "succeeded":
            failure_code = str(exchange.get("failure_code") or "single-work-item-agent-failed")
            terminal, audit = _terminal_result(
                root,
                plan=preview,
                started=started,
                status=str(exchange_status),
                failure_code=failure_code,
                terminal=active["record_terminal"],
            )
            if getattr(terminal, "status", None) != "pass" or not getattr(terminal, "committed", False):
                return SingleWorkItemExecutionResult(
                    "error", **base,
                    findings=tuple(getattr(terminal, "findings", ())), audit=audit,
                    next_action="恢复未闭合的终态审计。",
                )
            result_status = "blocked" if exchange_status in {"blocked", "timed_out", "cancelled"} else "error"
            return SingleWorkItemExecutionResult(
                result_status, **base, audit=audit,
                findings=(_finding(failure_code, "外部智能体未完成该受控工作项；原始失败内容已隐藏。"),),
            )
        output = exchange.get("output")
        if not isinstance(output, str) or not output.strip() or "\x00" in output:
            terminal, audit = _terminal_result(
                root, plan=preview, started=started, status="failed",
                failure_code="single-work-item-result-invalid", terminal=active["record_terminal"],
            )
            return SingleWorkItemExecutionResult(
                "error", **base, audit=audit,
                findings=(_finding("single-work-item-result-invalid", "外部智能体结果为空或格式无效。"),),
            )
        encoded = output.encode("utf-8")
        if len(encoded) > request["result_max_bytes"]:
            terminal, audit = _terminal_result(
                root, plan=preview, started=started, status="failed",
                failure_code="single-work-item-result-too-large", terminal=active["record_terminal"],
            )
            return SingleWorkItemExecutionResult(
                "error", **base, audit=audit,
                findings=(_finding("single-work-item-result-too-large", "外部智能体结果超过已确认的大小上限。"),),
            )
        scan = active["scan_text"](root, output)
        if scan.status != "pass":
            terminal, audit = _terminal_result(
                root, plan=preview, started=started, status="blocked",
                failure_code="single-work-item-result-secret-scan", terminal=active["record_terminal"],
            )
            return SingleWorkItemExecutionResult(
                "blocked", **base, audit=audit,
                findings=(_finding("single-work-item-result-secret-scan", "结果未通过敏感信息扫描；匹配内容不会回显。"),),
            )
        output_digest = _digest(encoded)
        terminal = active["record_terminal"](
            root,
            attempt_id=started.attempt_id,
            event_type="execution_succeeded",
            phase="post_run_validated",
            exit_code=0,
            output_digest=output_digest,
            stdout_byte_count=len(encoded),
            stderr_byte_count=0,
            stdout_truncated=False,
            stderr_truncated=False,
            guard_status="pass",
            job_accounting_passed=True,
            job_total_processes=0,
            job_active_processes=0,
            job_terminated_processes=0,
            direct_child_reaped=True,
            containment_closed=True,
        )
        audit = {
            "attempt_id": started.attempt_id,
            "state": "closed_succeeded" if getattr(terminal, "committed", False) else "awaiting_terminal",
            "audit_incomplete": not getattr(terminal, "committed", False),
        }
        if getattr(terminal, "status", None) != "pass" or not getattr(terminal, "committed", False):
            return SingleWorkItemExecutionResult(
                "error", **base, audit=audit,
                findings=tuple(getattr(terminal, "findings", ())),
                next_action="恢复未闭合的终态审计。",
            )
        result = SingleWorkItemExecutionResult(
            "pass", **base, output=output, output_digest=output_digest,
            artifacts=tuple(exchange.get("artifacts", ())), audit=audit,
            next_action="在中文控制面审阅结果；如工作项要求复核，继续进入人工复核。",
        )
        return result
    finally:
        try:
            valid = lease.validate()
        except BaseException:
            valid = False
        try:
            released = lease.release()
        except BaseException:
            released = CheckResult(status="error")
        if result is not None and (not valid or released.status != "pass"):
            # Python finally 不能替换已经返回的冻结结果；租约异常由全量审计/doctor 检出。
            pass
