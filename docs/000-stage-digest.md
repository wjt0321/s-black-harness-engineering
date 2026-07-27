# 000 — 阶段摘要

> 新会话先读本页；历史细节按需进入 `00-index.md` 或 `archive/`。

## 当前基线

- 里程碑：阶段 88 真实执行证据回收与人工审阅闭环已完成
- commit：以当前 Git HEAD 为准；阶段 88 已归档并纳入主分支历史
- 日期：2026-07-27
- 活跃 `docs/` 根目录为 28 份；阶段 88 事实源和实施计划均已归档。

## 当前阶段

- **阶段 88 — 已完成并归档：Pi/OMP 的真实宿主事件、最终结果产物和人工审阅决定均可安全回收、恢复读取与中文展示。**
- 归档事实源：`archive/137-stage88-external-agent-evidence-and-human-review.md`。
- 归档实施计划：`archive/plans/2026-07-27-stage88-external-agent-evidence-human-review.md`。
- 前序执行事实源：`archive/136-stage87-single-work-item-controlled-execution.md`。

## 阶段 88 已完成什么

- Pi/OMP 派发结果升级为固定版本事件协议；成功路径必须形成连续的“请求已领取、轮次已派发、智能体已开始、智能体已结束”事件链。
- 最终 UTF-8 文本或合法 JSON 经过大小限制和敏感信息扫描后，写入 `.runtime/external-agent-evidence/v1/` 的不可变内容寻址产物与执行清单。
- 终态审计与证据归档之间使用可恢复 pending 事务；固定恢复入口不会重新调用 Agent，也不会覆盖既有证据。
- 新增按执行尝试查看证据、恢复待归档证据和提交人工审阅的中文 CLI；控制面板可只读展示事件、产物和审阅状态。
- 人工决定仅允许“通过”或“要求修改”，必须先预览，再使用精确一次性确认摘要和 `--commit`；决定与产物、门禁、清单和意见摘要绑定。
- Pi 真实验收：`attempt-20260727-013`，产物成功归档，人工审阅为“通过”。
- OMP 真实验收：`attempt-20260727-015`，产物成功归档，人工审阅为“要求修改”。
- 两次验收都已通过新的 CLI 进程重新读取；当前没有未闭合执行尝试。

## 当前真实执行能力

1. Windows 固定 Git 状态：固定 `git status --short --branch`。
2. Windows 固定 Pi 打印：固定 `pi --print --no-session --no-tools <prompt>`。
3. 单工作项外部智能体派发：只向用户已打开且工具为空、会话空闲的 `pi-local` 或 `omp-local` 派发一次确认后的固定工作项。

三项都要求显式提交，并保持租约、固定输入、审计、输出约束和失败关闭。单工作项执行成功后可形成不可变证据包并进入人工审阅，但不会自动触发后续 Agent。

## 仍未开放

- 通用 shell、任意适配器执行、POSIX fallback；
- 网络适配器、服务、数据库、自动后台执行；
- 由 Harness 启动、关闭或重启外部 Agent；
- Pi/OMP 的 read/write/edit/bash 或 MCP 工具权限；
- 自动重试、并行派发、跨 Agent 转发和自治循环；
- 自动规划者、自动执行者、自动审阅者闭环；
- 任意项目文件产物回收、自动修改后重试或自动批准；
- QwenPaw 2.0.1 接入。

## 下次恢复顺序

1. `docs/000-stage-digest.md`
2. `docs/00-index.md`
3. `docs/02-roadmap.md`
4. `docs/130-gui-first-external-agent-control-plane-target.md`
5. `docs/archive/137-stage88-external-agent-evidence-and-human-review.md`
6. `docs/archive/136-stage87-single-work-item-controlled-execution.md`
7. `docs/10-cli-poc-usage.md`
8. `tasks/handoff-2026-07-27.md`

然后运行：

```bash
python -m agent_runtime.cli docs context --json
python -m agent_runtime.cli doctor
```

## 下一步做什么

- 阶段 88 到此结束；当前不自动进入下一阶段。
- 下一候选：在现有固定计划、单工作项执行、不可变证据和人工审阅基础上，设计“规划者 -> 执行者 -> 审阅者”的**有限人工确认闭环**。
- 该闭环必须继续保持单工作项、固定 Pi/OMP、无工具、无并行、无自动重试，并为每次角色交接设置明确人工门禁。
- 实时中文图形界面、有限取消/恢复和 QwenPaw 2.0.1 兼容继续排在其后。
