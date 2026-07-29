# 000 — 阶段摘要

> 新会话先读本页；历史细节按需进入 `00-index.md` 或 `archive/`。

## 当前基线

- 里程碑：阶段 94 已于 2026-07-29 完成 Agent Deck P0 与真实 Pi/OMP `Pi → OMP → Pi` 验收；操作者已提交最终“通过”。
- 产品主线：本地优先的聚合式 Agent 平台（Agent Deck）；Harness 作为可信、安全、可追溯的底层。
- 当前状态：P0 已归档，工作区没有待提交改动；阶段 95 尚未设计或授权。
- 活跃 `docs/` 根目录为 28 份；阶段 94 及此前的已验收阶段均在 `docs/archive/` 保留事实源。

## 当前阶段

- **阶段 94 — Agent Deck 工作台 P0（已完成并归档）。** 最近验收事实源：`archive/144-stage94-agent-deck-pilot-acceptance.md`。
- 阶段 95“Agent Deck 协作交互扩展”仅是下一候选，待用户授权；不得据此开始实现、扩大执行权限或将待接入 Agent 伪装为可用。
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
2. `docs/archive/144-stage94-agent-deck-pilot-acceptance.md`
3. `docs/130-gui-first-external-agent-control-plane-target.md`
4. `decisions/0002-deferred-shadcn-frontend-direction.md`
5. 当前获授权阶段的独立设计稿（如有）

然后运行：

```bash
python -m agent_runtime.cli docs context --json
python -m agent_runtime.cli doctor
```

## 下一步推荐入口

- **不要直接实施阶段 95。** 先由用户确认新的产品切片，再创建独立设计和实施计划。
- 不得回到以取消、恢复或单一底层控制能力为主线，也不得让 React 派发任何 Agent。
