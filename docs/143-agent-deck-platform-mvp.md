# 143 — Agent Deck 聚合式 Agent 平台 MVP

> 状态：**P0 前台真实投影和一次 Pi/OMP 真实受控链路已完成；最终人工业务决定与该链路的前台复核待完成。**
> 日期：2026-07-29
> 主线：聚合式 Agent 平台；Harness 为可信、安全、可追溯的底层，而非前台产品主角。

## 产品决策

项目主线调整为本地优先的 **Agent Deck**：将 Pi、OMP、Codex CLI、Claude Code、Kimi Code 等异构 CLI Agent 组织为同一项目中的可见团队。用户默认只需发布目标、观察协作并验收结果；未来主 Agent 负责分解、调度、汇总和验收建议。

首个产品阶段优先建设“工作台骨架 + Pi/OMP 真实试运行”，而不是继续扩展运行中取消、恢复执行或单一 Pi/OMP 控制流。Cindy 截图只作为工作台结构、任务入口、设置层级、成员协作感和产品完整度的参考；不得复制其品牌、素材、代码、文案或信息架构。

## 当前 P0 范围

- 中文项目工作台、任务入口、Agent 团队、协作时间线与交付/验收视图；
- Pi/OMP 作为首批真实试运行成员：规划、执行、审阅角色仍复用既有受控链路；
- Codex CLI、Claude Code、Kimi Code 先使用统一的待接入 Agent 卡片模型；
- React + TypeScript + Vite + Tailwind + shadcn/ui 为正式候选展示层；
- **P0 不新增 UI dispatch**：React 只读取固定的 `agent-deck/read-model/v1` 安全快照；Pi/OMP 的真实启动与最终决定继续复用既有 Tk GUI 严格结构化信封。
- 使用版本化只读 Agent Deck Read Model，Harness 继续唯一持有真实 command authority。

## 硬边界

- 不读取或管理凭据；认证继续归原 CLI 或系统凭据库；
- 不开放任意 argv/cwd/env、通用 shell、任意文件权限、网络 adapter、长期服务或后台执行；
- 不让 UI 绕开 approval、lease、audit、evidence、expected state 或失败关闭；
- 不在 P0 实现运行中取消、恢复、并发、自动重试或完全自治主 Agent；
- 不把“待接入”“已发现”“可见”伪装成真实可执行能力。

## 正式设计稿与恢复顺序

1. [`superpowers/specs/2026-07-29-agent-deck-platform-mvp-design.md`](superpowers/specs/2026-07-29-agent-deck-platform-mvp-design.md) — P0 的完整范围、页面架构、数据模型、Pi/OMP 试运行、验收与风险；
2. [`130-gui-first-external-agent-control-plane-target.md`](130-gui-first-external-agent-control-plane-target.md) — 长期产品目标与 Harness 边界；
3. [`../decisions/0002-deferred-shadcn-frontend-direction.md`](../decisions/0002-deferred-shadcn-frontend-direction.md) — React/Vite/shadcn 的展示层决策；
4. [`archive/142-stage93-pending-final-decision-abandonment.md`](archive/142-stage93-pending-final-decision-abandonment.md) — 可复用的 Pi/OMP 真实试运行底层事实源。

## 当前实现与真实试运行状态

- 已实现 `agent-deck/read-model/v1` 安全 read model、固定快照导出命令、React/Vite/Tailwind/shadcn 工作台、显式演示数据入口、浏览器会话草稿、Pi/OMP 团队卡片、协作时间线和交付/验收视图；React 不包含派发、批准、取消、恢复或命令桥接。
- 2026-07-29T10:24:13Z 已用真实项目运行态写出固定安全快照；它如实投影 Pi 为“已连接，存在未绑定会话”、OMP 为“状态已过期”，两者 readiness 都是 `stale`。前台不得把这类状态改标为空闲、就绪或可执行。
- 2026-07-29T10:51:10Z 已在浏览器前台核验真实快照投影：Pi 的“已连接，存在未绑定会话”、OMP 的“状态已过期”、两张已登记工作项卡及安全时间线均按快照展示；React 没有派发、批准、取消或恢复入口。
- 2026-07-29T11:15:19Z 至 `2026-07-29T11:16:43Z`，用户重新打开 Pi 与 OMP 后，已只通过既有受控链路完成 `chain-20260729-acceptance-forward-111423627`：Pi 规划 `attempt-20260729-019`、OMP 执行 `attempt-20260729-021`、Pi 审阅 `attempt-20260729-023` 均成功。三次均已写入 started/terminal audit、回收不可变证据和确认进程树活动数为零；审阅建议为 `approve`，无 findings。
- 这不等于最终业务验收已通过：该链路当前严格停在 `awaiting_final_human_decision`。最终“通过 / 要求修改”仍只能由操作者在既有受控 GUI 中核对证据后提交；不得由 React、Harness 自动化或本阶段 Agent 代替决定。
- 本次链路已通过 `agent-deck snapshot --commit` 写入固定安全快照并出现在安全时间线中。快照生成时 Pi/OMP 的宿主观察已经超过 TTL，故前台必须如实显示为过期/未绑定状态；这不改变已归档证据和等待中的最终人工决定。当前链路的浏览器前台复核仍待补做。

## 下一步

实施计划已保存为 [`superpowers/plans/2026-07-29-agent-deck-p0-implementation-plan.md`](superpowers/plans/2026-07-29-agent-deck-p0-implementation-plan.md)。当前只剩：操作者对 `chain-20260729-acceptance-forward-111423627` 提交最终业务决定，以及用该链路已导出的安全快照补做前台浏览器复核；两者完成前不得归档阶段 94、再次派发或扩大 Harness 权限。
