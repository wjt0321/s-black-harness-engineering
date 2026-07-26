# 000 — Stage Digest

> 新会话先读本页；历史细节按需进入 `00-index.md` 或 `archive/`。

## 当前基线

- 里程碑：Stage 76 manual collaboration board
- commit：见包含本文件的里程碑提交
- 活跃 `docs/` 只保留当前架构、规范、CLI 和最新事实源；完成阶段已归档。

## 当前阶段

- **Stage 76 — 已完成：manual-first 协作看板、人工拆分 fixture、Agent 泳道、交接/产物时间线与模拟操作面。**
- 当前唯一主线事实源：`124-stage76-manual-collaboration-board.md`
- 规划模式结论：用户可人工拆分；未来系统建议必须经人工确认；automatic 尚未启用。
- 当前 walkthrough 全部为 fixture/simulated，不调用 Agent、不消耗模型额度、不授予执行权。
- Stage 66 Pi bound runner migration 与 Stage 75 探针实现均为 deferred，不是当前产品主线。

## 当前真实执行能力

1. Windows fixed Git status：固定 `git status --short --branch`。
2. Windows fixed Pi print：固定 `pi --print --no-session --no-tools <prompt>`。

共同边界：显式 `--commit`、machine-local lease、固定 argv、bounded I/O、started/terminal audit、Windows Job Object containment。Pi smoke 已真实通过 `deepseek-compat/deepseek-v4-flash`；prompt、模型原文和凭据不进入公开结果。

## 仍未开放

- 通用 shell、任意 adapter execution、POSIX fallback；
- 网络 adapter、服务、数据库、自动后台执行；
- Pi read/write/edit/bash 工具；
- 未经独立 design gate 和授权的第三个真实 operation；
- npm/node executable chain 的完整可信绑定。

## 下次恢复顺序

1. `README.md`
2. `docs/00-index.md`
3. `docs/124-stage76-manual-collaboration-board.md`
4. `docs/123-multi-agent-control-hub-current-state-and-stage75-gate.md`
5. `docs/47-orchestration-hub-vision.md`
6. `docs/48-adapter-runtime-interface.md`
7. `docs/49-capability-routing-model.md`
8. `docs/111-pi-controlled-dry-run-print-implementation.md`（仅在核对真实执行边界时读取）
9. `docs/21-controlled-write-boundaries.md`
9. `tasks/progress.md`（只做历史取证，不作为入口）

然后运行：

```bash
python -m agent_runtime.cli docs context --json
python -m agent_runtime.cli doctor
```

## 下一步做什么

- **下一产品里程碑**：可用协作看板与 fixture-backed 端到端演示，覆盖任务录入、计划审阅、Agent work-item 泳道、handoff/artifact 时间线、blocked/ready/approval 状态和单一 operator action surface。
- Stage 75 的无 prompt ACP 探针实现与 Stage 66 Pi bound runner migration 均保持 deferred；只有看板暴露真实操作需求后再恢复。

## 验证基线

Socket Registry v1 收口需通过：full pytest、public scan、doctor、docs context、Markdown link audit、pre-commit 与 diff check；自动验证不得调用 Agent 或进行进程、网络、会话、额度探测。
