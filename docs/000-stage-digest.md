# 000 — 阶段摘要

> 新会话先读本页；历史细节按需进入 `00-index.md` 或 `archive/`。

## 当前基线

- 里程碑：阶段 86 Pi/OMP 真实只读状态接入已完成
- commit：以当前 Git HEAD 为准
- 日期：2026-07-27
- 活跃 `docs/` 根目录为 28 份；阶段 86 事实源和实施计划均已归档。

## 当前阶段

- **阶段 86 — 已完成并归档：Pi 与 OMP 的项目级状态扩展、固定原子快照、安全读取器、中文控制面板和真实连接/关闭验收全部通过。**
- 归档事实源：`archive/135-stage86-pi-omp-live-status-integration.md`。
- 归档实施计划：`archive/plans/2026-07-27-stage86-pi-omp-live-status-integration.md`。
- 本机核验版本：Pi `@earendil-works/pi-coding-agent` 0.82.0；OMP 启动器 1.3.14，当前内置 `@oh-my-pi/pi-coding-agent` 15.12.3。
- 用户确认本机 QwenPaw 为 2.0.1；旧虚拟环境中的 1.1.12.post3 不再作为依据，QwenPaw 尚未接入。

## 阶段 86 已完成什么

- Pi/OMP 在用户已启动的宿主进程内每 5 秒发布固定、有界、原子状态快照。
- 读取器只允许 `omp-acp`、`pi-local`、`omp-local` 三个审阅配置，不接受任意路径。
- 中文控制面板展示“未连接”“已连接，存在未绑定会话”或“状态已过期”。
- Pi、OMP 真实连接态均通过，证据有效但始终不可派发。
- 宿主关闭后均报告 `session_state=closed`，租约释放；超过 15 秒后安全显示“状态已过期”。
- OMP 缺少 Pi 项目信任接口的兼容问题已修复；Pi 仍必须明确通过项目信任。
- `.runtime/external-agent-status/` 本机权限已收紧为当前用户、SYSTEM 和 Administrators。

## 当前真实执行能力

1. Windows 固定 Git 状态：固定 `git status --short --branch`。
2. Windows 固定 Pi 打印：固定 `pi --print --no-session --no-tools <prompt>`。

阶段 86 没有新增第三个 Harness 真实执行操作。状态扩展不读取提示词、模型、工具输入、原始输出或凭据，也不访问网络。

## 仍未开放

- 通用 shell、任意适配器执行、POSIX fallback；
- 网络适配器、服务、数据库、自动后台执行；
- 由 Harness 启动 Pi、OMP 或 QwenPaw；
- 创建真实会话、调用模型、派发工作项；
- 真实审批账本、事件/产物/审阅回收和自动多智能体闭环。

## 下次恢复顺序

1. `docs/000-stage-digest.md`
2. `docs/00-index.md`
3. `docs/02-roadmap.md`
4. `docs/130-gui-first-external-agent-control-plane-target.md`
5. `docs/archive/135-stage86-pi-omp-live-status-integration.md`
6. `docs/10-cli-poc-usage.md`
7. `tasks/handoff-2026-07-27.md`

然后运行：

```bash
python -m agent_runtime.cli docs context --json
python -m agent_runtime.cli doctor
```

## 下一步做什么

- 阶段 86 到此结束；当前不自动进入下一阶段。
- 下一候选由用户选择：真实审批与单工作项受控派发、真实事件/产物/审阅回收、实时中文图形界面，或 QwenPaw 2.0.1 只读状态兼容。
- 任一候选均需独立边界设计和明确实施授权。
