# 000 — Stage Digest

> 新会话先读本页；历史细节按需进入 `00-index.md` 或 `archive/`。

## 当前基线

- 里程碑：`v0.18.0-pi-runtime-binding`
- commit：`pending-amend`
- 活跃 `docs/` 只保留当前架构、规范、CLI 和最新事实源；完成阶段已归档。

## 当前阶段

- **Stage 68 — 已完成 design gate：多 Agent collaboration plan 与可扩展 socket admission；未实现 plan、未调用 Agent**
- 事实源：`116-multi-agent-collaboration-plan-and-socket-admission.md`
- 最近完成：**Stage 67 — Socket Registry v1：Pi、Kimi Code、Claude Code、OMP 与 QwenPaw API 统一 Agent socket 只读投影**
- Stage 66 Pi bound runner migration 已冻结为 deferred security work，不是当前产品主线。

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
3. `docs/116-multi-agent-collaboration-plan-and-socket-admission.md`
4. `docs/115-agent-socket-registry-v1.md`
5. `docs/49-capability-routing-model.md`
6. `docs/48-adapter-runtime-interface.md`
7. `docs/114-pi-bound-runner-migration-design.md`（deferred security work）
8. `docs/21-controlled-write-boundaries.md`
9. `tasks/handoff-2026-07-26.md`
10. `tasks/progress.md`（只做历史取证，不作为入口）

然后运行：

```bash
python -m agent_runtime.cli docs context --json
python -m agent_runtime.cli doctor
```

## 下一步做什么

- **Stage 69 collaboration plan read model**：以 declared sockets 实现 deterministic `plan/validate/inspect`，不探测 readiness、不持久化、不调用 Agent；
- socket-specific readiness 和 capability routing explanation 随后独立推进；
- Stage 66 Pi bound runner migration 保持 deferred，除非 Pi 成为明确优先执行器且获得单独授权。

## 验证基线

Socket Registry v1 收口需通过：full pytest、public scan、doctor、docs context、Markdown link audit、pre-commit 与 diff check；自动验证不得调用 Agent 或进行进程、网络、会话、额度探测。
