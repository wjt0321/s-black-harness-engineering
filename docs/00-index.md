# 00 — 文档索引

> 先读 `000-stage-digest.md`。这里只按主题导航；已完成阶段在 `archive/`，不逐 Stage 展开。

## 当前入口

- `../README.md` — 项目定位、当前能力、快速开始。
- `000-stage-digest.md` — 当前断点和恢复顺序。
- `02-roadmap.md` — 能力包与下一候选。
- `130-gui-first-external-agent-control-plane-target.md` — GUI-first 外部 Agent 控制面长期目标、MVP 边界和反偏航检查。
- `10-cli-poc-usage.md` — 完整 CLI 参数和示例。
- `111-pi-controlled-dry-run-print-implementation.md` — 最新真实执行事实源。
- `113-pi-runtime-binding-implementation.md` — 当前 binding-only 实现与本地 review evidence 事实源。
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

- `130-gui-first-external-agent-control-plane-target.md` — 长期产品主线：统一 GUI、外部 Agent adapter/socket、多 Agent 协同与事实权威边界。
- `129-stage81-current-operator-inbox-and-approval-collection.md` — 当前多 Agent 产品主线：最新状态操作者待办、pending approval 集合、stale target 阻止，以及待办不等于执行授权的边界。
- `111-pi-controlled-dry-run-print-implementation.md` — 当前唯一 Agent 类真实执行能力及其安全边界。

Stage 61、63、65 和 67-80 的已完成/冻结设计、实现与阶段记录已归档到 `archive/110-*.md`、`archive/112-*.md`、`archive/114-*.md` 与 `archive/115-*.md` 至 `archive/128-*.md`，仅在追溯设计依据时读取。

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
