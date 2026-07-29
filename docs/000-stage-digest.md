# 000 — 阶段摘要

> 新会话先读本页；历史细节按需进入 `00-index.md` 或 `archive/`。

## 当前基线

- 里程碑：阶段 93 已于 2026-07-29 完成真实 Pi/OMP GUI 有限放弃验收
- 产品主线：2026-07-29 已重置为聚合式 Agent 平台（Agent Deck）；Harness 作为可信底层
- 当前状态：阶段 94 的 P0 前台真实投影、Pi→OMP→Pi 一次真实受控链路均已完成；链路停在必须由操作者作出的最终业务决定，前台对本次链路的浏览器复核仍待补做。
- 活跃 `docs/` 根目录为 29 份；阶段 93 及此前的已验收阶段均已归档

## 当前阶段

- **阶段 94 — Agent Deck 工作台基础（实施中）。** 已建设项目、任务、Agent 团队、协作时间线和交付/验收的产品主路径；Pi/OMP 已完成一次真实 Pi→OMP→Pi 试运行并等待最终人工决定，Codex CLI、Claude Code、Kimi Code 等以统一待接入模型出现。
- 当前事实源：`143-agent-deck-platform-mvp.md`；完整设计稿：`superpowers/specs/2026-07-29-agent-deck-platform-mvp-design.md`。
- 阶段 93 已验收基线：`archive/142-stage93-pending-final-decision-abandonment.md`；Pi/OMP 的固定受控链路、证据与最终决定继续作为 P0 的底层试运行能力。

## 已冻结边界

- Harness 仍唯一持有真实 command authority、lease、approval、audit、evidence、artifact 与失败关闭；前端只消费安全、版本化 read model 并构造最小结构化命令。
- P0 不读取或管理凭据；认证继续归原 CLI 或系统凭据库。
- P0 不开放任意 argv/cwd/env、通用 shell、任意文件权限、网络 adapter、长期服务、后台执行、运行中取消、恢复执行、并发、自动重试或完全自治主 Agent。
- 不得把 Agent 的“待接入”“已发现”“可见”伪装成真实 readiness 或可执行能力。
- Pi/OMP 真实试运行只复用既有已登记工作项、固定拓扑、显式确认、租约、审计与人工最终决定；不得因前台产品化扩大权限。

## 当前真实执行能力

1. Windows 固定 Git 状态：固定 `git status --short --branch`；
2. Windows 固定 Pi 打印：固定 `pi --print --no-session --no-tools <prompt>`；
3. Pi/OMP 单工作项派发，以及固定三角色受控串行 wrapper。

所有真实能力仍要求显式 `--commit`、固定输入、租约、审计、输出约束和失败关闭。

## 下次恢复顺序

1. `docs/000-stage-digest.md`
2. `docs/143-agent-deck-platform-mvp.md`
3. `docs/superpowers/specs/2026-07-29-agent-deck-platform-mvp-design.md`
4. `docs/superpowers/plans/2026-07-29-agent-deck-p0-implementation-plan.md`
5. `docs/130-gui-first-external-agent-control-plane-target.md`
6. `decisions/0002-deferred-shadcn-frontend-direction.md`
7. `docs/archive/142-stage93-pending-final-decision-abandonment.md`

然后运行：

```bash
python -m agent_runtime.cli docs context --json
python -m agent_runtime.cli doctor
```

## 下一步推荐入口

- **阶段 94 — 完成当前真实链路的最终人工决定，并补做该链路的前台投影复核。**
  - 实施计划：`docs/superpowers/plans/2026-07-29-agent-deck-p0-implementation-plan.md`
  - 2026-07-29T11:15:19Z 至 `2026-07-29T11:16:43Z`，已完成 `chain-20260729-acceptance-forward-111423627`：Pi 规划 `attempt-20260729-019`、OMP 执行 `attempt-20260729-021`、Pi 审阅 `attempt-20260729-023` 均有 started/terminal audit、不可变产物和已回收进程树；审阅建议为 `approve`，链路现为 `awaiting_final_human_decision`。
  - 只可由操作者在既有受控 GUI 核对证据后选择“通过 / 要求修改”；不得自动批准、再派发或复用该链路。随后以当前 `agent-deck/read-model/v1` 快照复核前台时间线，再归档阶段事实源。
  - 不得回到以取消、恢复或单一底层控制能力为主线，也不得让 React 派发任何 Agent。
