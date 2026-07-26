# 000 — Stage Digest

> 新会话先读本页；历史细节按需进入 `00-index.md` 或 `archive/`。

## 当前基线

- 里程碑：`v0.21.0-acp-readiness-evidence-foundation`
- commit：见该里程碑标签指向的提交
- 活跃 `docs/` 只保留当前架构、规范、CLI 和最新事实源；完成阶段已归档。

## 当前阶段

- **Stage 74 — 已完成：ACP runner snapshot collector、readiness evidence 与 dispatch binding；未启动 runner 或执行派发**
- 事实源：`122-acp-readiness-collector-and-dispatch-binding.md`
- 最近完成：**Stage 73 — ACP readiness collection design gate**
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
3. `docs/122-acp-readiness-collector-and-dispatch-binding.md`
4. `docs/121-acp-readiness-collection-design-gate.md`
5. `docs/120-controlled-collaboration-dispatch-foundation.md`
6. `docs/119-socket-readiness-evidence-and-routing-explanations.md`
7. `docs/118-control-panel-collaboration-projection.md`
8. `docs/117-collaboration-plan-read-model.md`
9. `docs/116-multi-agent-collaboration-plan-and-socket-admission.md`
10. `docs/115-agent-socket-registry-v1.md`
11. `docs/49-capability-routing-model.md`
12. `docs/48-adapter-runtime-interface.md`
13. `docs/114-pi-bound-runner-migration-design.md`（deferred security work）
14. `docs/21-controlled-write-boundaries.md`
15. `tasks/handoff-2026-07-26.md`
16. `tasks/progress.md`（只做历史取证，不作为入口）

然后运行：

```bash
python -m agent_runtime.cli docs context --json
python -m agent_runtime.cli doctor
```

## 下一步做什么

- **Stage 75 候选**：冻结更强但仍无 prompt 的 ACP transport/session-openability 证据设计门；未获单独授权前不启动 runner、不打开 session、不调用 Agent；
- Stage 66 Pi bound runner migration 保持 deferred，除非 Pi 成为明确优先执行器且获得单独授权。

## 验证基线

Socket Registry v1 收口需通过：full pytest、public scan、doctor、docs context、Markdown link audit、pre-commit 与 diff check；自动验证不得调用 Agent 或进行进程、网络、会话、额度探测。
