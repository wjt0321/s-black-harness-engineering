"""Foreground-only Chinese live Control Panel without a local service."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from .orchestration_control_panel import ControlPanelSnapshot, build_control_panel_snapshot

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
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


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
            from tkinter import ttk
        except ImportError as exc:  # pragma: no cover - depends on local Python build
            raise LiveControlPanelError("control-panel-live-gui-unavailable", "当前 Python 环境不提供本地图形界面组件。") from exc
        self._tk = tk
        self._ttk = ttk
        self._root_path = root.resolve()
        self._refresh_seconds = refresh_seconds
        self._chain_limit = chain_limit
        self._snapshot_builder = snapshot_builder
        self._closed = False

        self.window = tk.Tk()
        self.window.title("Agent Runtime — 实时控制面（只读）")
        self.window.minsize(1040, 680)
        self.window.protocol("WM_DELETE_WINDOW", self._close)

        container = ttk.Frame(self.window, padding=16)
        container.pack(fill="both", expand=True)
        ttk.Label(container, text="实时中文控制面", font=("Microsoft YaHei UI", 18, "bold")).pack(anchor="w")
        ttk.Label(
            container,
            text="只读：不派发、不批准、不重试、不控制宿主；关闭窗口即停止轮询。",
        ).pack(anchor="w", pady=(2, 10))

        self._status = tk.StringVar(value="正在读取本地安全快照…")
        ttk.Label(container, textvariable=self._status).pack(anchor="w", pady=(0, 10))

        self._agent_table = self._table(
            container,
            title="Pi / OMP 真实状态",
            columns=(("agent", "智能体", 160), ("status", "当前状态", 180), ("observed", "最后观察", 220), ("reason", "阻止原因", 340)),
        )
        self._chain_table = self._table(
            container,
            title="有限自动串行链路（安全摘要）",
            columns=(("chain", "链路 ID", 250), ("status", "状态", 180), ("task", "任务 ID", 180), ("topology", "角色拓扑", 320)),
        )

        controls = ttk.Frame(container)
        controls.pack(fill="x", pady=(12, 0))
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
        for item in table.get_children():
            table.delete(item)
        for row in rows:
            table.insert("", "end", values=row)

    def _refresh(self) -> None:
        if self._closed:
            return
        try:
            snapshot = self._snapshot_builder(
                self._root_path,
                chain_limit=self._chain_limit,
            )
            payload = snapshot.to_dict()
            self._replace_rows(self._agent_table, _agent_rows(payload))
            self._replace_rows(self._chain_table, _chain_rows(payload))
            observed = payload.get("source", {}).get("external_agent_evaluated_at", "未知")
            self._status.set(
                f"最新读取：{observed}；总体状态：{payload.get('status', '未知')}；仅展示安全摘要。"
            )
        except Exception:  # pragma: no cover - defensive boundary for a foreground display
            self._status.set("本地安全快照读取失败；未执行、未写入、未控制外部智能体。")
        if not self._closed:
            self.window.after(self._refresh_seconds * 1000, self._refresh)

    def _close(self) -> None:
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
