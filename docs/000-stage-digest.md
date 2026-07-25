# 000 — Stage Digest

> 新会话先读本页；历史细节按需进入 `00-index.md` 或 `archive/`。

## 当前基线

- 里程碑：`v0.17.0-filtered-snapshot-display-host-integration`
- commit：`ee7f7d5`
- 活跃 `docs/` 只保留当前架构、规范、CLI 和最新事实源；完成阶段已归档。

## 当前阶段

- **Stage 62 — 已完成并收口：fixed Pi print 真实 smoke、lease、audit 与 Windows Job containment 全部闭合**

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
3. `docs/111-pi-controlled-dry-run-print-implementation.md`
4. `docs/21-controlled-write-boundaries.md`
5. `tasks/handoff-2026-07-25.md`（需要 Stage 52–62 细节时）
6. `tasks/progress.md`（只做历史取证，不作为入口）

然后运行：

```bash
python -m agent_runtime.cli docs context --json
python -m agent_runtime.cli doctor
```

## 下一步做什么

- operator 在真实终端完成 Pi TUI 人工验收；
- read roundtrip、npm identity binding、canonical approval binding 分别建立独立 design gate；
- 若进入新能力阶段，先更新本页和 `02-roadmap.md`，不要继续堆叠已完成 Stage 叙事。

## 验证基线

Stage 62 收口证据：1426 passed、8 skipped；public scan、doctor、docs context、diff check 与真实 Pi smoke 均通过。
