# 000 — Stage Digest

> 新会话先读本页；历史细节按需进入 `00-index.md` 或 `archive/`。

## 当前基线

- 里程碑：Stage 81 当前态操作者待办与审批集合
- commit：以当前 Git HEAD 为准
- 日期：2026-07-26
- 活跃 `docs/` 只保留当前架构、规范、CLI 和最新事实源；本次整理后活跃文档为 28 份，完成阶段已归档。

## 当前阶段

- **Stage 81 — 已完成：current-state、fixture-backed、只读的操作者待办与审批集合投影。**
- 当前唯一产品主线事实源：`129-stage81-current-operator-inbox-and-approval-collection.md`。
- 当前待办只接受最新 attempt，以及与最新 attempt 对齐的 review/handoff；历史实体稳定返回 `target_not_current` 或状态阻止原因。
- 示例 blocked Run 聚合 5 个操作：1 个当前合格 cancel、1 个 pending approval、4 个 blocked/stale action。
- 合格候选继续使用内容寻址 candidate id 与 idempotency key，并精确绑定 run projection、action、target、expected state 和 fixture approval。
- Control Panel 新增中文“协作 / 当前待办”区段；所有操作控件仍 disabled。
- 即使 `action_eligible=true`，仍固定 `execution_authorized=false`、`dispatch_eligible=false`、`execution=not_executed`。
- 下一断点 Stage 82：真实 approval ledger 接入前的安全审查与只读契约收口；不得读取真实 ledger。
- Stage 65 Pi bound runner migration 设计已归档为 `archive/114-pi-bound-runner-migration-design.md`；无 prompt ACP 探针继续 deferred，不是当前产品主线。

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
- 真实 approval ledger、真实审批绑定或 current inbox 执行绑定；
- npm/node executable chain 的完整可信绑定。

## 下次恢复顺序

1. `README.md`
2. `docs/00-index.md`
3. `docs/129-stage81-current-operator-inbox-and-approval-collection.md`
4. `docs/47-orchestration-hub-vision.md`
5. `docs/48-adapter-runtime-interface.md`
6. `docs/49-capability-routing-model.md`
7. `docs/111-pi-controlled-dry-run-print-implementation.md`（仅在核对真实执行边界时读取）
8. `docs/113-pi-runtime-binding-implementation.md`（仅在核对 binding-only review evidence 时读取）
9. `docs/21-controlled-write-boundaries.md`
10. `tasks/handoff-2026-07-26.md`（仅需恢复本次实现细节和 Stage82 入口时）
11. `tasks/progress.md`（只做历史取证，不作为入口）

然后运行：

```bash
python -m agent_runtime.cli docs context --json
python -m agent_runtime.cli doctor
```

## 下一步做什么

- **下一产品里程碑：Stage 82 真实 approval ledger 接入前的安全审查与只读契约收口。**
- 审查 fixture approval、current inbox、受控写入审计和未来 readiness probe 的字段与授权边界，但不读取或修改真实 ledger。
- 首个设计输出应是 approval evidence 的身份绑定、状态矩阵、失效/撤销语义和审计字段清单；先做只读 schema 与 deterministic failure matrix，不实现 ledger adapter。
- 收口标准：不新增真实 operation，不启动 Agent/session，不探测 readiness，不把 `action_eligible` 或 `pending_approval` 解释为执行授权。
- 无 prompt ACP 探针、session 启动、真实审批绑定和单 work-item 真实派发继续 deferred，必须另行设计、测试和授权。

## 收口验证

Stage 81 收口需通过：新增专项 pytest、协作/Control Panel 回归、full pytest、public scan、doctor、docs context、Markdown link audit、pre-commit 与 diff check；自动验证不得调用 Agent 或进行会话、额度、凭据探测。
