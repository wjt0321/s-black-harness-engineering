# 02 — 路线图

> 本页只保留能力包、当前产品切片和下一候选。完整阶段设计、实施计划与验收记录均在 `docs/archive/`。

## 产品主线

构建本地优先、GUI-first 的 **Agent Deck 聚合式 Agent 平台**：用户发布目标、观察团队协作并验收结果；Harness 作为统一的计划、审批、状态、证据、审计和恢复底座。它不重写外部 Agent 的模型、会话或工具系统。

## 已完成能力包

1. **安全与账本内核**：策略、schema、敏感信息扫描、路径/动作门禁、任务与事件账本、事务写入、写后校验和失败回滚。
2. **编排控制面**：Agent/adapter registry、能力路由、协作计划、work item、handoff、approval、artifact、review 与恢复读取模型。
3. **受控执行基础**：Windows trust binding、lease、started/terminal audit、Job Object 进程树约束和有界安全投影。
4. **Pi/OMP 真实闭环**：只读状态、单工作项派发、不可变证据、人工审阅、有限 `Pi → OMP → Pi` / 反向串行链路，以及 GUI 启动与最终决定验收。
5. **Agent Deck 平台切片**：P0 中文工作台、浏览器协作草案、Harness 安全任务队列，以及受控正式任务登记与“等待主控 Agent 规划”收件箱。

## 当前真实操作

| 操作 | 固定范围 | 不变边界 |
|:---|:---|:---|
| Git status | `git status --short --branch` | 显式 `--commit`、信任绑定、lease 与审计 |
| Pi print | `pi --print --no-session --no-tools <prompt>` | 显式 `--commit`、固定运行时、lease 与审计 |
| Pi/OMP 工作项与三角色链路 | 已登记工作、固定角色拓扑 | 预检、一次性确认、宿主空闲、审计、证据和最终人工决定 |

任务登记不是第四种执行操作：`agent-deck mission submit --commit` 只向固定账本追加一项任务和一条 `created` 事件，不启动 Agent、宿主或链路。

## 最近完成里程碑

### 阶段 94 — Agent Deck 工作台 P0

统一项目、任务、团队、协作和交付的中文展示层已交付；Pi/OMP 完成真实 `Pi → OMP → Pi` 试运行并由人工最终通过。事实源：`archive/144-stage94-agent-deck-pilot-acceptance.md`。

### 阶段 95 — Agent Deck 任务工作区

浏览器草案与真实安全任务队列分开展示；草案不会派发 Agent。事实源：`archive/145-stage95-agent-deck-mission-workspace.md`。

### 阶段 96 — 受控任务登记与规划收件箱

有界目标可安全、显式地进入既有任务账本，并在 Deck 显示“等待主控 Agent 规划”；没有网页写入或 Agent 启动。事实源：`archive/146-stage96-controlled-mission-intake.md`。

## 下一候选：阶段 97 受限主控 Agent 结构化规划提议

阶段 97 必须先完成独立设计。目标是让**已登记、等待规划**的任务获得一份可验证、可审阅的结构化协作提议；它不是任务自动执行。

设计必须冻结：

- 只从登记任务读取哪些安全字段；
- Planner 的固定输入、无工具运行方式、输出 schema、字节上限与敏感信息扫描；
- 计划提议的不可变存储、审计、恢复和 read model；
- 用户如何确认计划后，才允许复用已有 Pi/OMP 受控链路；
- 失败、漂移、无效 JSON、证据未闭合和“要求修改”如何停止且不自动重试。

## 持续停止线

- 不开放通用 shell、任意 argv/cwd/env、网络 adapter、长期服务或数据库；
- 不由 Harness 启动、关闭或重启外部 Agent；
- 不开放 Agent 工具、并发派发、运行中取消、自动重试、自动批准或自治循环；
- 不将浏览器草案、read model、预览、readiness 或已登记任务解释为执行授权；
- 不把 Codex CLI、Claude Code、Kimi Code 等待接入卡片伪装为已具备真实状态或执行能力。
