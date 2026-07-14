# 00 — 文档索引

> **智能体先读 `000-stage-digest.md`，再按需读这里的具体文档。别从头顺序遍历。**

## 推荐阅读路径

### 1. 先理解项目是什么

- `01-vision-and-boundaries.md` — 项目愿景、边界、为什么要做
- `02-roadmap.md` — 阶段路线图与版本治理

### 2. 想直接上手 CLI

- `10-cli-poc-usage.md` — CLI 用法总入口 **（70KB，按需读）**
- `21-controlled-write-boundaries.md` — 受控写入总边界

### 3. 想看模型与协议层

- `03-policy-schema.md`
- `04-task-state-model.md`
- `05-agent-registry.md`
- `06-adapter-layer.md`
- `07-policy-task-bridge.md`
- `08-minimal-cli-design.md`
- `12-adapter-execution-envelope.md`
- `14-task-runtime-bridge.md`（早期 Runtime gate 设计）
- `15-runtime-ledger-audit.md`
- `64-versioning-governance.md`

### 4. 想看 Runtime 主线

- `16-runtime-plan.md`
- `17-runtime-planning-bridge.md`
- `19-runtime-report.md`
- `41-runtime-event-import-consistency-freeze.md`
- `45-runtime-event-import-strict-freeze-mode.md`

### 5. 想看中枢台主线（Stage 16 MVP 已收口）

- `47-orchestration-hub-vision.md` — 中枢台愿景
- `48-adapter-runtime-interface.md` — 适配器运行时接口
- `49-capability-routing-model.md` — 能力路由模型
- `50-control-plane-state-model.md` — 控制平面状态模型
- `51-backend-first-api-boundary.md` — 后端优先 API 边界
- `52-minimal-orchestration-loop.md` — 最小编排循环设计（Stage 14 已收口）
- `53-minimal-orchestration-loop-cli-draft.md` — CLI 草稿
- `54-backend-preparation-before-ui.md` — 后端准备（UI 之前）
- `56-orchestration-controlled-write-boundary.md` — 受控写入边界
- `58-orchestration-run-controlled-execution-design.md` — Run 受控执行设计
- `60-orchestration-run-lifecycle-events-design.md` — Run 生命周期事件
- `62-orchestration-task-submit-controlled-write-design.md` — Task 提交受控写入
- `63-orchestration-task-submit-created-event-design.md` — Task 提交事件设计
- `66-orchestration-run-retry-fallback-design.md` — Retry/Fallback 设计
- `70-orchestration-run-retry-fallback-commit-design.md` — Retry/Fallback Commit 设计
- `73-recovery-lineage-aggregation-read-model.md` — Recovery lineage 聚合只读模型（Stage 12 post-freeze）
- `74-recovery-lineage-report-reuse.md` — Recovery lineage 在 report generate 的显式复用契约
- `75-cli-automation-contract-discovery.md` — CLI 自动化 discovery、gate、profile、workflow plan 与 drift validation（已收口）
- `76-read-only-control-panel-mvp.md` — Stage 16 本地静态只读 Control Panel 设计与验收边界（已收口）

### 6. 想看里程碑与冻结记录

- `68-orchestration-foundation-milestone-freeze-checklist.md`
- `69-orchestration-foundation-freeze-execution-plan.md`

### 7. 想看历史阶段交付物

归档在 `docs/archive/`，按类别存放：

| 目录 | 内容 |
|:---|:---|
| `archive/release-notes/` | 各阶段 release notes（最新为 `79-release-notes-stage16-read-only-control-panel.md`） |
| `archive/dry-runs/` | dry-run / commit 操作记录（8 个） |
| `archive/smoke-regression/` | smoke test / regression 报告（4 个） |

## 当前最重要 5 份文档

1. `000-stage-digest.md`
2. `76-read-only-control-panel-mvp.md`
3. 最新 handoff：`tasks/handoff-2026-07-14.md`
4. `75-cli-automation-contract-discovery.md`
5. `52-minimal-orchestration-loop.md`

## 其他入口

- `tasks/progress.md` — 完整推进账本
- `tasks/handoff-*.md` — 阶段性交接上下文
- `README.md` — 仓库入口页
