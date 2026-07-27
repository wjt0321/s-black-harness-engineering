# 000 — 阶段摘要

> 新会话先读本页；历史细节按需进入 `00-index.md` 或 `archive/`。

## 当前基线

- 里程碑：阶段 87 单工作项受控执行闭环已完成
- commit：以当前 Git HEAD 为准；阶段 87 工作区尚未提交
- 日期：2026-07-27
- 活跃 `docs/` 根目录为 28 份；阶段 87 事实源和实施计划均已归档。

## 当前阶段

- **阶段 87 — 已完成并归档：用户一次性确认后，可向已经打开的 Pi 或 OMP 会话派发一个固定工作项，并回收有界结果与完整审计。**
- 归档事实源：`archive/136-stage87-single-work-item-controlled-execution.md`。
- 归档实施计划：`archive/plans/2026-07-27-stage87-single-work-item-controlled-execution.md`。
- 前序只读状态事实源：`archive/135-stage86-pi-omp-live-status-integration.md`。

## 阶段 87 已完成什么

- 新增 `orchestration execution single-work-item`：预览不执行，提交必须带精确确认摘要和 `--commit`。
- 只允许 `pi-local`、`omp-local` 两个固定目标、一个工作项、固定项目级信箱和独立派发绑定。
- 派发前检查状态绑定、活动工具为空和宿主空闲；不满足时失败关闭。
- started audit 先于派发，每次尝试只有一个 terminal audit；请求不可重放。
- 结果有界、经过敏感信息扫描；原始信箱内容只存在于 gitignored `.runtime/`。
- Pi 真实验收：`stage87-pi-smoke-003`，`attempt-20260727-005`，成功闭合。
- OMP 真实验收：`stage87-omp-smoke-003`，`attempt-20260727-011`，成功闭合。
- OMP 17.0.8 的跨工具 MCP 自动发现已通过项目本地配置隔离，没有修改 Claude、OpenCode 等全局配置。

## 当前真实执行能力

1. Windows 固定 Git 状态：固定 `git status --short --branch`。
2. Windows 固定 Pi 打印：固定 `pi --print --no-session --no-tools <prompt>`。
3. 单工作项外部智能体派发：只向用户已打开且工具为空、会话空闲的 `pi-local` 或 `omp-local` 派发一次确认后的固定工作项。

三者都要求显式提交，并保持租约、固定输入、审计、输出约束和失败关闭。第三项不启动宿主、不接受任意命令或工具权限。

## 仍未开放

- 通用 shell、任意适配器执行、POSIX fallback；
- 网络适配器、服务、数据库、自动后台执行；
- 由 Harness 启动、关闭或重启外部 Agent；
- Pi/OMP 的 read/write/edit/bash 或 MCP 工具权限；
- 自动重试、并行派发、跨 Agent 转发和自治循环；
- 真实事件流、产物、审阅结果和多智能体闭环；
- QwenPaw 2.0.1 接入。

## 下次恢复顺序

1. `docs/000-stage-digest.md`
2. `docs/00-index.md`
3. `docs/02-roadmap.md`
4. `docs/130-gui-first-external-agent-control-plane-target.md`
5. `docs/archive/136-stage87-single-work-item-controlled-execution.md`
6. `docs/10-cli-poc-usage.md`
7. `tasks/handoff-2026-07-27.md`

然后运行：

```bash
python -m agent_runtime.cli docs context --json
python -m agent_runtime.cli doctor
```

## 下一步做什么

- 阶段 87 到此结束；当前不自动进入下一阶段。
- 首选下一候选：真实事件、产物与人工审阅结果回收。
- 之后再评估规划者 -> 执行者 -> 审阅者闭环、实时中文图形界面和 QwenPaw 2.0.1 兼容。
- 任一候选仍需独立边界设计和用户授权。
