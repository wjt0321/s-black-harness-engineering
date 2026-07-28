"""Foreground-only Chinese live Control Panel without a local service."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from queue import Empty, Queue
from threading import Thread
from typing import Any, Callable

from .orchestration_control_panel import ControlPanelSnapshot, build_control_panel_snapshot
from .orchestration_external_agent_chain import ExternalAgentChainResult
from .orchestration_external_agent_live_status import inspect_external_agent_live_status
from .result import Finding
from .orchestration_control_panel_approval import (
    commit_control_panel_approval,
    preview_control_panel_approval,
)
from .orchestration_control_panel_registered_work import (
    RegisteredWorkCard,
    load_registered_work_inbox,
)

_MIN_REFRESH_SECONDS = 2
_MAX_REFRESH_SECONDS = 60
_MIN_CHAIN_LIMIT = 1
_MAX_CHAIN_LIMIT = 20

@dataclass(frozen=True)
class LiveControlPanelError(ValueError):
    code: str
    message: str


def validate_live_control_panel_options(*, refresh_seconds: int, chain_limit: int) -> tuple[int, int]:
    """Validate bounded foreground polling options before any runtime read."""
    if isinstance(refresh_seconds, bool) or not isinstance(refresh_seconds, int):
        raise LiveControlPanelError("control-panel-live-refresh-invalid", "刷新间隔必须是整数秒。")
    if not _MIN_REFRESH_SECONDS <= refresh_seconds <= _MAX_REFRESH_SECONDS:
        raise LiveControlPanelError(
            "control-panel-live-refresh-invalid",
            f"刷新间隔必须在 {_MIN_REFRESH_SECONDS} 到 {_MAX_REFRESH_SECONDS} 秒之间。",
        )
    if isinstance(chain_limit, bool) or not isinstance(chain_limit, int):
        raise LiveControlPanelError("control-panel-live-chain-limit-invalid", "链路展示上限必须是整数。")
    if not _MIN_CHAIN_LIMIT <= chain_limit <= _MAX_CHAIN_LIMIT:
        raise LiveControlPanelError(
            "control-panel-live-chain-limit-invalid",
            f"链路展示上限必须在 {_MIN_CHAIN_LIMIT} 到 {_MAX_CHAIN_LIMIT} 条之间。",
        )
    return refresh_seconds, chain_limit


def _current_utc_evaluated_at() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def build_live_control_panel_snapshot(
    root: Path,
    *,
    evaluated_at: str | None = None,
    chain_limit: int = _MAX_CHAIN_LIMIT,
) -> ControlPanelSnapshot:
    """Build one fresh, read-only snapshot for the foreground UI."""
    validate_live_control_panel_options(
        refresh_seconds=_MIN_REFRESH_SECONDS,
        chain_limit=chain_limit,
    )
    return build_control_panel_snapshot(
        root.resolve(),
        external_agent_evaluated_at=evaluated_at or _current_utc_evaluated_at(),
        external_agent_chain_limit=chain_limit,
    )


def build_start_chain_approval_command(
    *,
    chain_id: str,
    task_id: str,
    collaboration_file: str,
    goal: str,
) -> dict[str, object]:
    """Build the sole fixed GUI envelope for the existing chain start operation."""
    return {
        "version": 1,
        "contract": "control-panel-approval/v1",
        "operation": "start_chain",
        "chain_id": chain_id,
        "task_id": task_id,
        "collaboration_file": collaboration_file,
        "goal": goal,
    }


def build_registered_start_chain_approval_command(card: RegisteredWorkCard) -> dict[str, object]:
    """Build one selected registered card; the operator supplies no internal identifiers."""
    issued_at = datetime.now(UTC)
    chain_id = "chain-{}-{}-{}".format(
        issued_at.strftime("%Y%m%d"),
        card.card_id,
        issued_at.strftime("%H%M%S%f")[:9],
    )
    return build_start_chain_approval_command(
        chain_id=chain_id,
        task_id=card.task_id,
        collaboration_file=card.collaboration_file,
        goal=card.goal,
    )


def build_final_decision_approval_command(
    *,
    chain_id: str,
    decision: str,
    comment: str,
) -> dict[str, object]:
    """Build the sole fixed GUI envelope for the existing final decision operation."""
    return {
        "version": 1,
        "contract": "control-panel-approval/v1",
        "operation": "final_decision",
        "chain_id": chain_id,
        "decision": decision,
        "comment": comment,
    }


def format_approval_confirmation(result: Any) -> str:
    """Return a safe confirmation summary without copying untrusted command text."""
    plan = result.plan if isinstance(getattr(result, "plan", None), dict) else {}
    lines = [
        f"操作：{plan.get('operation', '未知')}",
        f"链路：{getattr(result, 'chain_id', '-')}",
        f"计划摘要：{getattr(result, 'plan_hash', '-')}",
        f"一次性确认摘要：{getattr(result, 'approval_binding_id', '-')}",
    ]
    for key, label in (
        ("goal_digest", "目标摘要"),
        ("review_advice_digest", "审阅建议摘要"),
        ("human_decision", "最终决定"),
        ("human_comment_digest", "意见摘要"),
        ("review_recommendation", "审阅建议"),
    ):
        if key in plan:
            lines.append(f"{label}：{plan[key]}")
    return "\n".join(lines)

def registered_card_preflight_failure(
    root: Path,
    card: RegisteredWorkCard,
    *,
    evaluated_at: str,
) -> str | None:
    """Check each host required by a selected card before it may start a serial chain."""
    labels = {"pi-local": "Pi", "omp-local": "OMP"}
    for profile_id in dict.fromkeys(card.topology):
        try:
            status = inspect_external_agent_live_status(
                root.resolve(),
                evaluated_at,
                profile_id=profile_id,
            )
        except Exception:
            status = None
        evidence = getattr(status, "evidence", None) if status is not None else None
        if (
            getattr(status, "status", None) == "pass"
            and getattr(status, "observation_status", None) == "observed"
            and isinstance(evidence, dict)
            and evidence.get("session_state") == "open"
        ):
            continue
        label = labels.get(profile_id, "目标")
        return f"{label} 宿主未处于可受控派发的已打开、空闲且证据有效状态；未启动链路。"
    return None


def _preflight_blocked_result(command: dict[str, object], message: str) -> ExternalAgentChainResult:
    return ExternalAgentChainResult(
        "blocked",
        str(command.get("chain_id", "")),
        findings=(Finding("control-panel-registered-work-host-not-ready", "warn", "deny", message),),
    )


def _start_approval_commit_worker(commit: Callable[[], Any]) -> Queue[tuple[str, Any | None]]:
    """Run one already-confirmed operation off the Tk event loop and return a single safe outcome."""
    outcomes: Queue[tuple[str, Any | None]] = Queue(maxsize=1)

    def run() -> None:
        try:
            outcomes.put(("result", commit()))
        except Exception:
            outcomes.put(("error", None))

    Thread(target=run, name="agent-runtime-control-panel-approval", daemon=False).start()
    return outcomes


def _agent_rows(payload: dict[str, Any]) -> list[tuple[str, str, str, str]]:
    section = payload.get("sections", {}).get("external_agents", {})
    observations = {
        item.get("profile_id"): item
        for item in section.get("observations", [])
        if isinstance(item, dict)
    }
    rows: list[tuple[str, str, str, str]] = []
    for item in section.get("agents", []):
        if not isinstance(item, dict):
            continue
        readiness = item.get("readiness") if isinstance(item.get("readiness"), dict) else {}
        profile_id = item.get("agent_id", "-")
        observation = observations.get(profile_id, {})
        rows.append(
            (
                str(item.get("display_name_zh", profile_id)),
                str(item.get("status_label_zh", item.get("status", "未知"))),
                str(observation.get("observed_at") or "尚未观察"),
                str(item.get("blocked_reason_code") or readiness.get("blocked_reason_code") or "无"),
            )
        )
    return rows


def _chain_rows(payload: dict[str, Any]) -> list[tuple[str, str, str, str]]:
    section = payload.get("sections", {}).get("external_agent_chains", {})
    labels = {
        "awaiting_planner_confirmation": "等待确认规划",
        "awaiting_executor_confirmation": "等待确认执行",
        "awaiting_reviewer_confirmation": "等待确认审阅",
        "awaiting_final_human_decision": "等待最终人工决定",
        "finalization_pending": "等待恢复最终决定",
        "stopped": "已停止",
        "approved": "审阅已通过",
        "changes_requested": "要求修改",
    }
    rows: list[tuple[str, str, str, str]] = []
    for item in section.get("chains", []):
        if not isinstance(item, dict):
            continue
        roles = item.get("roles") if isinstance(item.get("roles"), dict) else {}
        rows.append(
            (
                str(item.get("chain_id", "-")),
                labels.get(str(item.get("status", "")), str(item.get("status", "未知"))),
                str(item.get("task_id", "-")),
                " → ".join(str(roles.get(role, "-")) for role in ("planner", "executor", "reviewer")),
            )
        )
    return rows


def pending_final_decision_chain_id(payload: dict[str, Any]) -> str | None:
    """Return the sole pending final decision that the GUI can route automatically."""
    section = payload.get("sections", {}).get("external_agent_chains", {})
    candidates = [
        item.get("chain_id")
        for item in section.get("chains", [])
        if isinstance(item, dict)
        and item.get("status") == "awaiting_final_human_decision"
        and isinstance(item.get("chain_id"), str)
        and item["chain_id"]
    ]
    return candidates[0] if len(candidates) == 1 else None


def _registered_work_rows(cards: tuple[RegisteredWorkCard, ...]) -> list[tuple[str, str, str, str]]:
    return [
        (
            card.card_id,
            card.title_zh,
            card.summary_zh,
            " → ".join(card.topology),
        )
        for card in cards
    ]


class _LiveControlPanelWindow:
    """A small, foreground-only Tk window that owns no operation authority."""

    def __init__(
        self,
        root: Path,
        *,
        refresh_seconds: int,
        chain_limit: int,
        snapshot_builder: Callable[..., ControlPanelSnapshot] = build_live_control_panel_snapshot,
    ) -> None:
        try:
            import tkinter as tk
            from tkinter import messagebox, ttk
        except ImportError as exc:  # pragma: no cover - depends on local Python build
            raise LiveControlPanelError("control-panel-live-gui-unavailable", "当前 Python 环境不提供本地图形界面组件。") from exc
        self._tk = tk
        self._ttk = ttk
        self._messagebox = messagebox
        self._root_path = root.resolve()
        self._refresh_seconds = refresh_seconds
        self._chain_limit = chain_limit
        self._snapshot_builder = snapshot_builder
        self._closed = False
        self._registered_cards: dict[str, RegisteredWorkCard] = {}
        self._auto_prompted_final_chain_ids: set[str] = set()
        self._approval_commit_in_flight = False

        self.window = tk.Tk()
        self.window.title("Agent Runtime — 实时控制面（只读）")
        self.window.minsize(1040, 680)
        self.window.protocol("WM_DELETE_WINDOW", self._close)

        container = ttk.Frame(self.window, padding=16)
        container.pack(fill="both", expand=True)
        ttk.Label(container, text="实时中文控制面", font=("Microsoft YaHei UI", 18, "bold")).pack(anchor="w")
        ttk.Label(
            container,
            text="操作者选择已登记工作后只作启动授权与最终决定；内部标识符、计划和中间串行均自动处理。",
        ).pack(anchor="w", pady=(2, 10))

        self._status = tk.StringVar(value="正在读取本地安全快照…")
        ttk.Label(container, textvariable=self._status).pack(anchor="w", pady=(0, 10))

        self._agent_table = self._table(
            container,
            title="Pi / OMP 真实状态",
            columns=(("agent", "智能体", 160), ("status", "当前状态", 180), ("observed", "最后观察", 220), ("reason", "阻止原因", 340)),
        )
        self._work_table = self._table(
            container,
            title="已登记待启动工作（安全摘要）",
            columns=(("card", "工作卡", 180), ("title", "工作", 180), ("summary", "摘要", 360), ("topology", "角色拓扑", 260)),
        )
        self._chain_table = self._table(
            container,
            title="有限自动串行链路（安全摘要）",
            columns=(("chain", "链路 ID", 250), ("status", "状态", 180), ("task", "任务 ID", 180), ("topology", "角色拓扑", 320)),
        )

        approvals = ttk.LabelFrame(container, text="操作者确认 / 既有受控执行", padding=8)
        approvals.pack(fill="x", pady=(0, 12))
        ttk.Label(
            approvals,
            text="选中工作后生成一次性确认摘要；中间自动串行，只有最终业务结论仍由操作者决定。",
        ).pack(side="left")
        self._start_work_button = ttk.Button(
            approvals,
            text="启动选中工作…",
            command=self._start_selected_registered_work,
        )
        self._start_work_button.pack(side="right", padx=(8, 0))
        self._final_decision_button = ttk.Button(
            approvals,
            text="为选中链路提交最终决定…",
            command=self._open_final_decision_dialog,
        )
        self._final_decision_button.pack(side="right")

        controls = ttk.Frame(container)
        controls.pack(fill="x", pady=(0, 0))
        ttk.Button(controls, text="立即刷新（只读）", command=self._refresh).pack(side="left")
        ttk.Label(
            controls,
            text=f"自动刷新：{refresh_seconds} 秒；最多展示 {chain_limit} 条链路",
        ).pack(side="right")

    def _table(
        self,
        parent: Any,
        *,
        title: str,
        columns: tuple[tuple[str, str, int], ...],
    ) -> Any:
        frame = self._ttk.LabelFrame(parent, text=title, padding=8)
        frame.pack(fill="both", expand=True, pady=(0, 12))
        table = self._ttk.Treeview(frame, columns=tuple(item[0] for item in columns), show="headings", height=7)
        for identifier, label, width in columns:
            table.heading(identifier, text=label)
            table.column(identifier, width=width, anchor="w", stretch=True)
        scrollbar = self._ttk.Scrollbar(frame, orient="vertical", command=table.yview)
        table.configure(yscrollcommand=scrollbar.set)
        table.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        return table

    @staticmethod
    def _replace_rows(table: Any, rows: list[tuple[str, ...]]) -> None:
        selected_keys = {
            str(values[0])
            for item in table.selection()
            if (values := table.item(item, "values"))
        }
        for item in table.get_children():
            table.delete(item)
        restored_items: list[Any] = []
        for row in rows:
            item = table.insert("", "end", values=row)
            if row and str(row[0]) in selected_keys:
                restored_items.append(item)
        if restored_items:
            table.selection_set(*restored_items)

    def _set_approval_controls_enabled(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        self._start_work_button.configure(state=state)
        self._final_decision_button.configure(state=state)

    def _selected_registered_card_id(self) -> str | None:
        selected = self._work_table.selection()
        if not selected:
            return None
        values = self._work_table.item(selected[0], "values")
        return str(values[0]) if values else None

    def _selected_chain_id(self) -> str | None:
        selected = self._chain_table.selection()
        if not selected:
            return None
        values = self._chain_table.item(selected[0], "values")
        return str(values[0]) if values else None

    def _start_selected_registered_work(self) -> None:
        if self._approval_commit_in_flight:
            self._messagebox.showwarning("正在执行", "已有一条受控操作正在串行执行，请等待它完成。")
            return
        card_id = self._selected_registered_card_id()
        card = self._registered_cards.get(card_id or "")
        if card is None:
            self._messagebox.showwarning("需要选择工作", "请先在“已登记待启动工作”中选择一张工作卡。")
            return

        def preflight() -> str | None:
            return registered_card_preflight_failure(
                self._root_path,
                card,
                evaluated_at=_current_utc_evaluated_at(),
            )

        failure = preflight()
        if failure is not None:
            self._messagebox.showwarning("宿主状态未就绪", failure)
            return
        self._preview_approval(
            None,
            build_registered_start_chain_approval_command(card),
            preflight=preflight,
        )

    def _open_final_decision_dialog(self, chain_id: str | None = None) -> None:
        if self._approval_commit_in_flight:
            self._messagebox.showwarning("正在执行", "已有一条受控操作正在串行执行，请等待它完成。")
            return
        chain_id = chain_id or self._selected_chain_id()
        if chain_id is None:
            self._messagebox.showwarning("需要选择链路", "请先在有限自动串行链路表格中选择一条等待最终人工决定的链路。")
            return
        dialog = self._tk.Toplevel(self.window)
        dialog.title("提交最终人工决定")
        dialog.transient(self.window)
        dialog.grab_set()
        body = self._ttk.Frame(dialog, padding=14)
        body.pack(fill="both", expand=True)
        self._ttk.Label(body, text=f"链路：{chain_id}").grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))
        self._ttk.Label(body, text="最终决定").grid(row=1, column=0, sticky="w", pady=3)
        decision = self._tk.StringVar(value="approve")
        self._ttk.Combobox(
            body,
            textvariable=decision,
            state="readonly",
            values=("approve", "request_changes"),
            width=30,
        ).grid(row=1, column=1, sticky="w", pady=3)
        self._ttk.Label(
            body,
            text="操作者仅选择最终结论；意见会自动以固定安全文本记录，并在下一页作一次性确认。",
            wraplength=500,
        ).grid(row=2, column=0, columnspan=2, sticky="w", pady=(6, 3))

        def preview() -> None:
            selected = decision.get()
            comment = (
                "操作者通过 GUI 确认该链路的最终结论。"
                if selected == "approve"
                else "操作者通过 GUI 要求该链路修改后重新提交。"
            )
            command = build_final_decision_approval_command(
                chain_id=chain_id,
                decision=selected,
                comment=comment,
            )
            self._preview_approval(dialog, command)

        self._ttk.Button(body, text="生成一次性确认摘要", command=preview).grid(row=3, column=1, sticky="e", pady=(10, 0))

    def _preview_approval(
        self,
        source_dialog: Any | None,
        command: dict[str, object],
        *,
        preflight: Callable[[], str | None] | None = None,
    ) -> None:
        try:
            result = preview_control_panel_approval(
                self._root_path,
                command=command,
                evaluated_at=_current_utc_evaluated_at(),
            )
        except Exception:
            self._messagebox.showerror("确认预览失败", "无法构建固定确认预览；未执行或写入任何链路记录。")
            return
        if result.status != "needs_approval" or not result.approval_binding_id:
            self._show_approval_result(result, title="确认预览未通过")
            return
        if source_dialog is not None:
            source_dialog.destroy()
        self._open_confirmation_dialog(command, result, preflight=preflight)

    def _open_confirmation_dialog(
        self,
        command: dict[str, object],
        preview: Any,
        *,
        preflight: Callable[[], str | None] | None = None,
    ) -> None:
        dialog = self._tk.Toplevel(self.window)
        dialog.title("确认既有受控操作")
        dialog.transient(self.window)
        dialog.grab_set()
        body = self._ttk.Frame(dialog, padding=14)
        body.pack(fill="both", expand=True)
        self._ttk.Label(
            body,
            text="请核对以下不可变摘要。确认后仅调用既有固定 operation；状态漂移或摘要不匹配将失败关闭。",
            wraplength=620,
        ).pack(anchor="w", pady=(0, 8))
        summary = self._tk.Text(body, width=82, height=10, wrap="word")
        summary.insert("1.0", format_approval_confirmation(preview))
        summary.configure(state="disabled")
        summary.pack(fill="both", expand=True)
        actions = self._ttk.Frame(body)
        actions.pack(fill="x", pady=(10, 0))
        confirm = self._ttk.Button(actions, text="确认并提交既有受控操作")
        confirm.pack(side="right")
        cancel = self._ttk.Button(actions, text="取消", command=dialog.destroy)
        cancel.pack(side="right", padx=(0, 8))

        waiting = self._ttk.Label(
            body,
            text="",
            foreground="#1f5f8b",
            wraplength=620,
        )
        waiting.pack(anchor="w", pady=(8, 0))
        progress = self._ttk.Progressbar(body, mode="indeterminate")

        def finish(outcomes: Queue[tuple[str, Any | None]]) -> None:
            try:
                outcome, result = outcomes.get_nowait()
            except Empty:
                if not self._closed:
                    self.window.after(120, lambda: finish(outcomes))
                return
            progress.stop()
            progress.pack_forget()
            self._approval_commit_in_flight = False
            self._set_approval_controls_enabled(True)
            if outcome != "result":
                waiting.configure(text="固定操作提交失败；未自动重试或继续派发。")
                self._messagebox.showerror("提交失败", "固定操作无法确认完成；不会自动重试或继续派发。")
                confirm.configure(state="normal")
                cancel.configure(state="normal")
                return
            self._show_approval_result(result, title="既有受控操作结果")
            if result.status == "pass":
                dialog.destroy()
                self._refresh()
            else:
                confirm.configure(state="normal")
                cancel.configure(state="normal")

        def commit() -> None:
            confirm.configure(state="disabled")
            cancel.configure(state="disabled")
            self._approval_commit_in_flight = True
            self._set_approval_controls_enabled(False)
            waiting.configure(text="正在受控串行执行：窗口会继续刷新状态；不会自动重试、并行或扩大权限。")
            progress.pack(fill="x", pady=(4, 0))
            progress.start(80)
            def execute_confirmed_operation() -> ExternalAgentChainResult:
                failure = preflight() if preflight is not None else None
                if failure is not None:
                    return _preflight_blocked_result(command, failure)
                return commit_control_panel_approval(
                    self._root_path,
                    command=command,
                    approval_binding_id=preview.approval_binding_id,
                    evaluated_at=_current_utc_evaluated_at(),
                )

            outcomes = _start_approval_commit_worker(execute_confirmed_operation)
            self.window.after(120, lambda: finish(outcomes))

        confirm.configure(command=commit)

    def _show_approval_result(self, result: Any, *, title: str) -> None:
        findings = getattr(result, "findings", ())
        detail = "\n".join(str(item.message) for item in findings if getattr(item, "message", None))
        message = f"链路：{getattr(result, 'chain_id', '-')}\n状态：{getattr(result, 'status', '未知')}"
        if detail:
            message += f"\n{detail}"
        if getattr(result, "next_action", None):
            message += f"\n下一步：{result.next_action}"
        if getattr(result, "status", None) == "pass":
            self._messagebox.showinfo(title, message)
        else:
            self._messagebox.showwarning(title, message)
        self._status.set(f"最近确认操作：{getattr(result, 'status', '未知')}；窗口不会自动重试或继续执行。")

    def _refresh(self) -> None:
        if self._closed:
            return
        try:
            snapshot = self._snapshot_builder(
                self._root_path,
                chain_limit=self._chain_limit,
            )
            payload = snapshot.to_dict()
            inbox = load_registered_work_inbox(self._root_path)
            self._registered_cards = {card.card_id: card for card in inbox.cards} if inbox.status == "pass" else {}
            self._replace_rows(self._agent_table, _agent_rows(payload))
            self._replace_rows(self._work_table, _registered_work_rows(inbox.cards))
            self._replace_rows(self._chain_table, _chain_rows(payload))
            observed = payload.get("source", {}).get("external_agent_evaluated_at", "未知")
            self._status.set(
                f"最新读取：{observed}；总体状态：{payload.get('status', '未知')}；已登记工作：{inbox.status}。"
            )
            pending_chain_id = pending_final_decision_chain_id(payload)
            if pending_chain_id is not None and pending_chain_id not in self._auto_prompted_final_chain_ids:
                self._auto_prompted_final_chain_ids.add(pending_chain_id)
                self.window.after_idle(lambda chain_id=pending_chain_id: self._open_final_decision_dialog(chain_id))
        except Exception:  # pragma: no cover - defensive boundary for a foreground display
            self._status.set("本地安全快照读取失败；未执行、未写入、未控制外部智能体。")
        if not self._closed:
            self.window.after(self._refresh_seconds * 1000, self._refresh)

    def _close(self) -> None:
        if self._approval_commit_in_flight:
            self._messagebox.showwarning("正在执行", "受控操作仍在串行执行。为保证审计终态完整，请等待完成后再关闭窗口。")
            return
        self._closed = True
        self.window.destroy()

    def run(self) -> None:
        self._refresh()
        self.window.mainloop()


def launch_live_control_panel(
    root: Path,
    *,
    refresh_seconds: int = 5,
    chain_limit: int = _MAX_CHAIN_LIMIT,
) -> None:
    """Open the foreground-only read panel; it never starts a service or Agent."""
    refresh_seconds, chain_limit = validate_live_control_panel_options(
        refresh_seconds=refresh_seconds,
        chain_limit=chain_limit,
    )
    _LiveControlPanelWindow(
        root,
        refresh_seconds=refresh_seconds,
        chain_limit=chain_limit,
    ).run()
