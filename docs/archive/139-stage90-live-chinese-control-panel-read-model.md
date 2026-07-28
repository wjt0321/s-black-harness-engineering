<!-- parents: 130-gui-first-external-agent-control-plane-target.md, archive/138-stage89-bounded-planner-executor-review-design.md -->

# 139 — 阶段 90：实时中文控制面读取模型与只读图形面板

> 状态：已完成并归档；2026-07-28 已完成真实 Pi/OMP 图形界面验收；不授权任何新的外部 Agent 执行能力。
> 日期：2026-07-28

## 1. 目标

在阶段 89 的真实有限自动串行闭环之上，交付一个操作者前台启动的中文只读图形面板。它让操作者在同一窗口内读取 Pi/OMP 的真实安全状态和有限链路的安全摘要，而不是继续增加新的终端执行流程。

本阶段复用既有 `control-plane/control-panel-snapshot/v1`：新增可选 `external_agent_chains` 只读 section，并保持既有 snapshot、证据、审阅和链路记录的权威边界。

## 2. 冻结边界

- 图形面板是前台进程，不监听端口、不启动服务；关闭窗口即停止轮询。
- 每次刷新只重新构建本地安全快照；默认 5 秒，接受 2–60 秒的有界间隔。
- 链路列表最多读取 20 条，并按稳定链路 ID 顺序投影；仅展示链路 ID、状态、任务 ID、固定角色宿主和创建时间。
- 不展示链路目标、规划/执行指令、未扫描原文、原始产物、凭据或任意项目文件内容。
- GUI 只有“立即刷新（只读）”控件；没有派发、确认、最终决定、重试、取消、恢复、宿主启停或任意命令入口。
- `--json` 仅输出单次确定性快照；不打开窗口，也不改变任何运行态。

因此，本阶段不新增 real operation，不改变阶段 87 的单工作项派发、阶段 88 的人工审阅，或阶段 89 的一次启动确认与最终人工决定语义。

## 3. 实现

- `agent_runtime.external_agent_chain_store.list_external_agent_chains()` 从既有不可变 intent 记录中安全地枚举有限链路；目录、符号链接、文件上限和每条链路记录仍受既有 containment / fail-closed 校验保护。
- `build_control_panel_snapshot()` 可按显式上限聚合 `external_agent_chains`；读取失败投影为固定 blocked section，绝不改写链路记录或调用 Agent。
- `agent_runtime.control_panel_live_gui` 使用标准库 Tk 前台窗口展示两个中文表格：Pi/OMP 真实状态与有限自动串行链路安全摘要。
- 新 CLI：

  ```powershell
  python -m agent_runtime.cli orchestration control-panel live
  python -m agent_runtime.cli orchestration control-panel live --refresh-seconds 5 --chain-limit 20
  python -m agent_runtime.cli orchestration control-panel live --chain-limit 20 --json
  ```

## 4. 验收标准

自动化：

1. 链路列表稳定、有界，只释放安全摘要；
2. 非法刷新或链路上限失败关闭；
3. JSON 模式只构建一次快照，不打开 GUI；
4. 既有控制面 HTML 也能显示新的链路摘要，且不泄露目标、指令或原始产物。

真实图形验收（必须由操作者完成，不能用 fixture 代替）：

1. 打开无工具、空闲的 Pi 和 OMP；
2. 启动 `orchestration control-panel live`；
3. 确认同一窗口显示两个真实宿主状态、刷新时间与不可派发原因；
4. 确认同一窗口显示既有正向“通过”和反向“要求修改”链路的安全摘要；
5. 关闭一个宿主或等待状态过期，确认窗口在有限刷新周期内给出稳定、中文的只读失败投影；
6. 确认窗口没有任何执行、审批、重试或宿主控制能力。

## 5. 真实验收记录

2026-07-28 的实际操作者验收（不是 fixture）：

1. 操作者打开无工具、空闲的 Pi 与 OMP；前台窗口以 2 秒刷新、20 条链路上限启动。
2. Harness 在 `2026-07-28T06:33:48Z` 读取到两端真实 `open` 观察；窗口展示 Pi/OMP 中文状态、不可派发原因，以及 `chain-20260728-forward-006` 的“审阅已通过”和 `chain-20260728-reverse-003` 的“要求修改”。
3. 操作者确认窗口只有“立即刷新（只读）”，没有派发、审批、重试、取消、恢复或宿主控制入口。
4. 操作者关闭 OMP；在 `2026-07-28T06:35:09Z`，窗口的同一安全读取模型将 OMP 投影为“状态已过期”/`readiness_expired`，同时继续显示 Pi 的新鲜观察。
5. 操作者最终确认 GUI 验收通过；测试窗口随后关闭。

## 6. 停止线与后续

阶段 90 完成后再单独评估 GUI 审批收件箱、有限取消/恢复和第三宿主兼容。它们都不能通过本阶段的只读 GUI 旁路获得执行权限。
