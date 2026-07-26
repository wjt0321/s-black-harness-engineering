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

## 当前执行事实源

- `111-pi-controlled-dry-run-print-implementation.md` — fixed Pi print 当前实现、边界和真实 smoke。
- `115-agent-socket-registry-v1.md` — 多 Agent 插座式中枢的当前事实源；只读 socket 投影。
- `114-pi-bound-runner-migration-design.md` — deferred security work：bound Node + sealed CLI entry 迁移设计门；未改 runner。
- `113-pi-runtime-binding-implementation.md` — Pi Node/package binding-only 当前实现；未迁移 runner。
- `archive/release-notes/112-release-notes-stage65-pi-bound-runner-migration-design.md` — Stage 65 design-only 收口记录。
- `archive/release-notes/111-release-notes-stage63-stage64-pi-runtime-binding.md` — Stage 63–64 commit-level 收口记录。
- `112-pi-node-runtime-identity-binding-design.md` — Pi Node runtime、CLI entry 与 module closure 的设计契约。
- `110-pi-controlled-dry-run-adapter-contract.md` — Pi print 当前设计契约。
- `archive/100-fixed-execution-operational-recovery-implementation.md` — shared lease、trust/recovery 与 audit v2。
- `archive/98-fixed-git-status-executor-implementation-and-limited-enablement.md` — fixed Git status 实现。
- `archive/97-execution-lifecycle-audit-writer-design-and-implementation.md` — execution audit writer。

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
