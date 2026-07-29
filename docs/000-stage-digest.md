# 000 — 阶段摘要

> 新会话先读本页；历史细节按需进入 `00-index.md` 或 `archive/`。

## 当前基线

- 里程碑：阶段 96 已于 2026-07-29 完成受控任务登记与规划收件箱：正式目标可安全进入真实任务账本并在 Deck 显示等待规划；阶段 94 的 Pi/OMP 真实链路保持已通过。
- 产品主线：本地优先的聚合式 Agent 平台（Agent Deck）；Harness 作为可信、安全、可追溯的底层。
- 当前状态：阶段 96 已归档；下一候选为受限主控 Agent 结构化规划提议。
- 活跃 `docs/` 根目录为 28 份；阶段 96 及此前的已验收阶段均在 `docs/archive/` 保留事实源；最新文档收敛记录为 `archive/147-documentation-consolidation-2026-07-29.md`。

## 当前阶段

- **阶段 96 — 受控任务登记与规划收件箱（已完成并归档）。** 最近验收事实源：`archive/146-stage96-controlled-mission-intake.md`。
- 阶段 97“受限主控 Agent 结构化规划提议”是下一候选；必须先独立设计，且不得扩大执行权限或将待接入 Agent 伪装为可用。
- 长期产品目标与边界：`130-gui-first-external-agent-control-plane-target.md`。

## 已冻结边界

- Harness 仍唯一持有真实 command authority、lease、approval、audit、evidence、artifact 与失败关闭；前端只消费安全、版本化 read model 并构造最小结构化命令。
- P0 不读取或管理凭据；认证继续归原 CLI 或系统凭据库。
- 不开放任意 argv/cwd/env、通用 shell、任意文件权限、网络 adapter、长期服务、后台执行、运行中取消、恢复执行、并发、自动重试或完全自治主 Agent。
- 不得把 Agent 的“待接入”“已发现”“可见”伪装成真实 readiness 或可执行能力。
- Pi/OMP 真实试运行只复用既有已登记工作项、固定拓扑、显式确认、租约、审计与人工最终决定；不得因前台产品化扩大权限。

## 当前真实执行能力

1. Windows 固定 Git 状态：固定 `git status --short --branch`；
2. Windows 固定 Pi 打印：固定 `pi --print --no-session --no-tools <prompt>`；
3. Pi/OMP 单工作项派发，以及固定三角色受控串行 wrapper。

所有真实能力仍要求显式 `--commit`、固定输入、租约、审计、输出约束和失败关闭。

## 下次恢复顺序

1. `docs/000-stage-digest.md`
2. `docs/00-index.md`
3. `docs/130-gui-first-external-agent-control-plane-target.md`
4. `docs/archive/146-stage96-controlled-mission-intake.md`
5. `tasks/handoff-2026-07-29-stage97.md`
6. 当前任务直接相关的 1–2 份事实源或独立设计稿

然后运行：

```bash
python -m agent_runtime.cli docs context --json
python -m agent_runtime.cli doctor
```

## 下一步推荐入口

- **不要直接实施阶段 97。** 先读取 `tasks/handoff-2026-07-29-stage97.md` 并完成受限主控 Agent 结构化规划的独立设计；浏览器草案或已登记任务都不是执行授权。
- 不得回到以取消、恢复或单一底层控制能力为主线，也不得让 React 派发任何 Agent。
