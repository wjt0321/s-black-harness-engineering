# 000 — Stage Digest

> 新会话先读本页；历史细节按需进入 `00-index.md` 或 `archive/`。

## 当前基线

- 里程碑：`v0.18.0-pi-runtime-binding`
- commit：`pending-amend`
- 活跃 `docs/` 只保留当前架构、规范、CLI 和最新事实源；完成阶段已归档。

## 当前阶段

- **Stage 64 — 已完成 binding-only implementation：Node/Pi module closure inspect/create/rotate；未迁移 Pi runner、未扩大执行权限**
- 收口记录：`archive/release-notes/111-release-notes-stage63-stage64-pi-runtime-binding.md`
- 最近完成：**Stage 63 — Pi npm shim、Node runtime 与 CLI module closure 的 review-bound identity design gate**

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
3. `docs/113-pi-runtime-binding-implementation.md`
4. `docs/112-pi-node-runtime-identity-binding-design.md`
5. `docs/111-pi-controlled-dry-run-print-implementation.md`
6. `docs/21-controlled-write-boundaries.md`
7. `tasks/handoff-2026-07-26-stage64-pi-runtime-binding.md`
8. `tasks/handoff-2026-07-25.md`（需要 Stage 52–62 细节时）
9. `tasks/progress.md`（只做历史取证，不作为入口）

然后运行：

```bash
python -m agent_runtime.cli docs context --json
python -m agent_runtime.cli doctor
```

## 下一步做什么

- **Stage 65 bound runner migration design gate**：定义 direct Node + sealed CLI entry 的接线、post-run identity recheck 与真实 smoke 许可，不直接改 runner；
- read roundtrip 与 canonical approval binding 继续维持独立 design gate；
- 若进入新能力阶段，先更新本页和 `02-roadmap.md`，不要继续堆叠已完成 Stage 叙事。

## 验证基线

Stage 64 收口证据：full pytest、public scan、doctor、docs context、Markdown link audit、pre-commit 与 diff check 均通过；自动验证未创建真实 binding、未执行 Node/Pi/npm。
