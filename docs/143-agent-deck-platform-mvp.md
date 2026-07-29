# 143 — Agent Deck 聚合式 Agent 平台 MVP

> 状态：**P0 前台真实投影已验收；Pi/OMP 受控链路的继续试运行等待新鲜宿主状态。**
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
- 这不等于 Pi/OMP 受控链路的继续试运行已通过：两宿主观察仍为 `stale`，因此不得启动已登记链路。任何真实链路启动和最终业务决定仍只经既有受控 GUI。

## 下一步

实施计划已保存为 [`superpowers/plans/2026-07-29-agent-deck-p0-implementation-plan.md`](superpowers/plans/2026-07-29-agent-deck-p0-implementation-plan.md)。前台安全投影已完成；当前只剩 Pi/OMP 发布新鲜宿主状态后的既有 GUI 受控链路试运行、重导安全快照及最终人工业务决定。不得为了推进试运行而扩大 Harness 权限。
