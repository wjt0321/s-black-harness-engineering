# 00 — 文档索引

> 先读 `000-stage-digest.md`。这里只按主题导航；已完成阶段在 `archive/`，不逐 Stage 展开。

## 当前入口

- `../README.md` — 项目定位、当前能力、快速开始。
- `000-stage-digest.md` — 当前断点和恢复顺序。
- `02-roadmap.md` — 能力包与下一候选。
- `10-cli-poc-usage.md` — 完整 CLI 参数和示例。
- `111-pi-controlled-dry-run-print-implementation.md` — 最新真实执行事实源。
- `112-pi-node-runtime-identity-binding-design.md` — Node/Pi trusted-chain design gate。
- `113-pi-runtime-binding-implementation.md` — 当前 binding-only 实现事实源。
- `MAINTENANCE.md` — 文档治理规则。

## 核心模型

- `01-vision-and-boundaries.md` — 愿景与边界。
- `03-policy-schema.md` — Policy schema。
- `04-task-state-model.md` — Task/Event 状态模型。
- `05-agent-registry.md` — Agent registry。
- `06-adapter-layer.md` — Adapter 层。
- `07-policy-task-bridge.md` — Policy 与任务桥接。
- `08-minimal-cli-design.md` — CLI 基础设计。
- `12-adapter-execution-envelope.md` — Execution envelope。
- `15-runtime-ledger-audit.md` — Ledger 与 audit。

## Runtime 与受控写入

- `16-runtime-plan.md` — Runtime plan。
- `17-runtime-planning-bridge.md` — Planning bridge。
- `19-runtime-report.md` — Runtime report。
- `21-controlled-write-boundaries.md` — 当前写入与回滚边界。

## Orchestration 控制面

- `47-orchestration-hub-vision.md` — 中枢台愿景。
- `48-adapter-runtime-interface.md` — Adapter runtime interface。
- `49-capability-routing-model.md` — Capability routing。
- `50-control-plane-state-model.md` — Control-plane state。
- `51-backend-first-api-boundary.md` — Backend-first API boundary。
- `52-minimal-orchestration-loop.md` — 最小编排闭环。
- `64-versioning-governance.md` — 版本与阶段治理。

## 当前事实源

- `125-stage77-chinese-first-interface-and-manual-editor.md` — 当前多 Agent 产品主线：中文默认界面契约、术语中文注释与浏览器内存人工计划编辑器。
- `124-stage76-manual-collaboration-board.md` — Stage 76 历史基线：manual-first 决策、人工协作 fixture、泳道与时间线。
- `123-multi-agent-control-hub-current-state-and-stage75-gate.md` — Stage 75 历史基线：产品目标、安全边界与方向回正结论。
- `111-pi-controlled-dry-run-print-implementation.md` — 当前唯一 Agent 类真实执行能力及其安全边界。
- `114-pi-bound-runner-migration-design.md` — deferred 安全工作；不是当前产品主线。

Stage 67-74 的 socket、协作计划、看板、dispatch 与 readiness 详细记录已归档到 `archive/115-*.md` 至 `archive/122-*.md`，仅在追溯设计依据时读取。

## 历史归档

| 目录 | 内容 |
|:---|:---|
| `archive/` | 已完成的设计、实现与里程碑事实源 |
| `archive/plans/` | 已执行的实施计划 |
| `archive/release-notes/` | 阶段与版本发布记录 |
| `archive/dry-runs/` | 历史 dry-run/commit 记录 |
| `archive/smoke-regression/` | 历史 smoke 与 regression |
| `archive/snapshots/2026-07-26/` | 本次治理前的长版 README、AGENTS、index、digest、roadmap 快照 |

完整推进账本位于 `../tasks/progress.md`，仅在追溯历史决策时读取。
