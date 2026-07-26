# 000 — Stage Digest

> 新会话先读本页；历史细节按需进入 `00-index.md` 或 `archive/`。

## 当前基线

- 里程碑：Stage 78 人工确认与受控导出
- commit：见包含本文件的里程碑提交
- 日期：2026-07-26
- 活跃 `docs/` 只保留当前架构、规范、CLI 和最新事实源；完成阶段已归档。

## 当前阶段

- **Stage 78 — 已完成：人工计划候选校验、显式人工确认、用户触发复制与下载。**
- 当前唯一产品主线事实源：`126-stage78-manual-confirmation-and-controlled-export.md`。
- 候选 JSON 严格保持现有 collaboration plan v1 字段；确认状态和派发/执行边界不污染计划 schema。
- 状态固定为“编辑中 -> 校验通过 -> 已人工确认”；任意编辑都会撤销确认。
- 导出前后始终 `dispatch_eligible=false`、`execution=not_executed`。
- 页面不调用 Agent、不启动 ACP session、不探测 readiness、不访问网络、不写项目文件或 ledger、不消耗模型额度。
- 下一断点 Stage 79：协作运行状态模型设计；先冻结开始、取消、重试、审阅、交接、阻塞恢复和 artifact 回收，不调用 Agent。
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
- npm/node executable chain 的完整可信绑定。

## 下次恢复顺序

1. `README.md`
2. `docs/00-index.md`
3. `docs/126-stage78-manual-confirmation-and-controlled-export.md`
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

- **下一产品里程碑：Stage 79 协作运行状态模型设计。**
- 先定义开始、取消、重试、审阅、交接、blocked/ready/approval 和 artifact 回收的确定性状态与事件，不接入真实 Agent。
- 无 prompt ACP 探针、单 work-item 真实派发与 Stage 66 Pi bound runner migration 均保持 deferred；必须在状态、审批、取消和产物回收契约齐备后另行设计和授权。

## 验证基线

Stage 78 收口需通过：Control Panel 专项 pytest、full pytest、public scan、doctor、docs context、Markdown link audit、pre-commit 与 diff check；自动验证不得调用 Agent 或进行会话、额度、凭据探测。
