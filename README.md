# s-black harness engineering

<p align="center">
  <img src="assets/logo.png" alt="s-black harness engineering logo" width="180">
</p>

<p align="center">
  <a href="#中文">中文</a> · <a href="#english">English</a>
</p>

---

## 中文

> 一套轻量的 Agent Runtime / Harness Orchestrator，用来沉淀规则门禁、任务账本、Agent 注册表、工具适配器边界和完成验证流程。

## 这个项目是什么

`s-black harness engineering` 是一个长期工程项目，目标是把 Agent 调度、规则检查、任务记录、工具适配和交付验证，从单一宿主框架中逐步抽象出来，形成一套小型、可审计、可迁移的运行层。

它不是要立刻替代 QwenPaw。第一阶段只做文档、协议、schema、样例和边界设计，在设计稳定前不接入真实执行链路。

## 当前状态

- 阶段：规划与协议骨架
- 创建日期：2026-07-02
- 当前本地项目目录：`D:\agent-runtime`
- 运行时代码：尚未实现

## 初始范围

这套 Runtime 未来预计覆盖：

1. **Agent 注册表**：记录 Agent 的能力、边界、工作区和委派关系。
2. **任务路由**：判断一个任务应该交给哪个 Agent 或工具处理。
3. **规则门禁**：在外发、删除、改配置、push 等高风险动作前做检查。
4. **工具适配器**：把 QwenPaw、Kimi、Claude、OMP、Shell、飞书、GitHub、WebBridge 等封装成统一接口。
5. **任务状态账本**：记录任务从计划、执行、阻塞、失败到完成的过程。
6. **完成验证**：任务完成前必须有证据，避免只靠口头结果宣称完成。
7. **记忆与文档交接**：把关键上下文落到合适的位置，而不是只留在聊天里。

## 第一阶段暂不做什么

第一阶段不做：

- 不替代 QwenPaw
- 不做 UI 或桌面壳
- 不启动长期后台服务
- 不接管现有定时任务
- 不做模型代理或计费系统
- 不在设计稳定前静默执行真实外部操作

## 仓库结构

| 路径 | 用途 |
|:---|:---|
| `docs/` | 架构、路线图、协议说明 |
| `policies/` | Policy schema 和样例 policy |
| `agents/` | Agent 注册表 schema 和样例注册表 |
| `adapters/` | 后续工具适配器设计或代码 |
| `tasks/` | 任务账本 schema、样例、进度和交接记录 |
| `logs/` | 后续 Runtime 运行日志 |
| `decisions/` | 架构决策记录 |
| `notes/` | 每日推进笔记 |
| `assets/` | 项目视觉资产 |

## 当前文档

- `docs/01-vision-and-boundaries.md`
- `docs/02-roadmap.md`
- `docs/03-policy-schema.md`
- `docs/04-task-state-model.md`
- `docs/05-agent-registry.md`

## 推进原则

保持小步、可审查、可回滚。先把规则、任务模型、Agent 注册表、适配器边界和完成验证想清楚，再开始写真正可执行的 Runtime 代码。

---

## English

> A lightweight Agent Runtime / Harness Orchestrator for policy guardrails, task ledgers, agent registries, adapter boundaries, and completion verification.

## What This Project Is

`s-black harness engineering` is a long-term project for extracting agent orchestration, policy checks, task tracking, tool adapters, and delivery verification out of a single host framework and into a small, auditable runtime layer.

It is not intended to replace QwenPaw immediately. The first phase focuses on documents, schemas, examples, and clear boundaries before any real runtime execution code is introduced.

## Current Status

- Stage: planning and protocol skeleton
- Created: 2026-07-02
- Current local project directory: `D:\agent-runtime`
- Runtime code: not implemented yet

## Initial Scope

The runtime is expected to cover these areas over time:

1. **Agent registry**: track agents, capabilities, boundaries, workspaces, and handoff rules.
2. **Task routing**: decide which agent or tool should handle a task.
3. **Policy guardrails**: check risky actions before external publishing, deletion, configuration changes, or pushes.
4. **Tool adapters**: wrap QwenPaw, Kimi, Claude, OMP, Shell, Lark, GitHub, and WebBridge behind consistent interfaces.
5. **Task ledger**: record task state from planning through execution, blocking, failure, or completion.
6. **Completion verification**: require evidence before a task is marked finished.
7. **Memory and documentation handoff**: preserve important context in the right place instead of only in chat.

## Non-Goals For The First Phase

The first phase does not:

- Replace QwenPaw
- Provide a UI or desktop shell
- Start a long-running background service
- Take over existing scheduled jobs
- Implement a model proxy or billing system
- Silently execute real external operations before the design is stable

## Repository Layout

| Path | Purpose |
|:---|:---|
| `docs/` | Architecture, roadmap, protocol notes |
| `policies/` | Policy schema and sample policies |
| `agents/` | Agent registry schema and sample registry |
| `adapters/` | Future adapter designs or code |
| `tasks/` | Task ledger schemas, examples, progress, handoff notes |
| `logs/` | Future runtime logs |
| `decisions/` | Architecture decision records |
| `notes/` | Daily project notes |
| `assets/` | Project visual assets |

## Current Documents

- `docs/01-vision-and-boundaries.md`
- `docs/02-roadmap.md`
- `docs/03-policy-schema.md`
- `docs/04-task-state-model.md`
- `docs/05-agent-registry.md`

## Development Principle

Move in small, reviewable steps. Define the rules, task model, agent registry, adapter boundaries, and completion checks before implementing executable runtime code.
