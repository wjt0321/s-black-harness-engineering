# 000 — Stage Digest

> 新会话先读本页；历史细节按需进入 `00-index.md` 或 `archive/`。

## 当前基线

- 里程碑：Stage 80 操作者操作资格与审批绑定
- commit：当前工作区实现尚未提交
- 日期：2026-07-26
- 活跃 `docs/` 只保留当前架构、规范、CLI 和最新事实源；完成阶段已归档。

## 当前阶段

- **Stage 80 — 已完成：checkpoint 操作资格、fixture 审批精确绑定与不可执行幂等命令候选。**
- 当前唯一产品主线事实源：`128-stage80-operator-action-eligibility-and-approval-binding.md`。
- 已冻结批准开始、取消、重试、要求修改和批准交接的 action/target/state 矩阵。
- 每个操作绑定 Stage 79 事件 sequence、目标实体、期望状态、run projection 和 fixture approval。
- 业务合格候选使用内容寻址 candidate id 与 idempotency key；已记录键稳定阻止重复候选。
- Control Panel 展示 checkpoint、审批绑定、阻止原因和幂等候选；所有控件仍 disabled。
- 即使 `action_eligible=true`，仍固定 `execution_authorized=false`、`dispatch_eligible=false`、`execution=not_executed`。
- 下一断点 Stage 81：当前态操作者待办与审批集合投影；只聚合最新状态，不读取真实 approval ledger。
- Stage 66 Pi bound runner migration 与无 prompt ACP 探针实现继续 deferred，不是当前产品主线。

## 当前真实执行能力

1. Windows fixed Git status：固定 `git status --short --branch`。
2. Windows fixed Pi print：固定 `pi --print --no-session --no-tools <prompt>`。

共同边界：显式 `--commit`、machine-local lease、固定 argv、bounded I/O、started/terminal audit、Windows Job Object containment。Pi smoke 已真实通过 `deepseek-compat/deepseek-v4-flash`；prompt、模型原文和凭据不进入公开结果。

## 仍未开放

- 通用 shell、任意 adapter execution、POSIX fallback；
- 网络 adapter、服务、数据库、自动后台执行；
- Pi read/write/edit/bash 工具；
- 未经独立 design gate 和授权的第三个真实 operation；
- live Agent readiness、Agent-to-Agent invocation 或自动派发；
- 真实 approval ledger 与 fixture 操作资格的执行绑定；
- npm/node executable chain 的完整可信绑定。

## 下次恢复顺序

1. `README.md`
2. `docs/00-index.md`
3. `docs/128-stage80-operator-action-eligibility-and-approval-binding.md`
4. `docs/47-orchestration-hub-vision.md`
5. `docs/48-adapter-runtime-interface.md`
6. `docs/49-capability-routing-model.md`
7. `docs/111-pi-controlled-dry-run-print-implementation.md`（仅在核对真实执行边界时读取）
8. `docs/21-controlled-write-boundaries.md`
9. `tasks/handoff-2026-07-26.md`（仅需恢复本次实现细节时）
10. `tasks/progress.md`（只做历史取证，不作为入口）

然后运行：

```bash
python -m agent_runtime.cli docs context --json
python -m agent_runtime.cli doctor
```

## 下一步做什么

- **下一产品里程碑：Stage 81 当前态操作者待办与审批集合投影。**
- 只针对运行最新状态聚合待处理审批、当前可选操作和稳定阻止原因，形成操作者当前待办 read model。
- 无 prompt ACP 探针、真实 approval ledger 绑定、session 启动和单 work-item 真实派发继续 deferred，必须另行设计和授权。

## 收口验证

Stage 80 收口需通过：新增专项 pytest、协作/Control Panel 回归、full pytest、public scan、doctor、docs context、Markdown link audit、pre-commit 与 diff check；自动验证不得调用 Agent 或进行会话、额度、凭据探测。
