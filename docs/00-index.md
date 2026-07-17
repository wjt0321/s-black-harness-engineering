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
- `15-runtime-ledger-audit.md`
- `64-versioning-governance.md`

### 4. 想看 Runtime 主线

- `16-runtime-plan.md`
- `17-runtime-planning-bridge.md`
- `19-runtime-report.md`
- `41-runtime-event-import-consistency-freeze.md`
- `45-runtime-event-import-strict-freeze-mode.md`

### 5. 想看中枢台主线（Stage 49 fixed Git status executor 已收口）

- `47-orchestration-hub-vision.md` — 中枢台愿景
- `48-adapter-runtime-interface.md` — 适配器运行时接口
- `49-capability-routing-model.md` — 能力路由模型
- `50-control-plane-state-model.md` — 控制平面状态模型
- `51-backend-first-api-boundary.md` — 后端优先 API 边界
- `52-minimal-orchestration-loop.md` — 最小编排循环设计（Stage 14 已收口）
- `archive/53-minimal-orchestration-loop-cli-draft.md` — CLI 草稿
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
- `78-control-panel-host-integration-boundary.md` — Stage 17 本地只读 stdio handoff contract 设计与实现边界
- `79-read-only-host-consumer-validation-boundary.md` — Stage 18 本地 reference consumer validation 设计与实现边界（已收口）
- `83-codex-desktop-snapshot-json-reader-implementation.md` — Stage 22 Codex Desktop 显式 snapshot JSON reader（已收口）
- `84-envelope-scoped-snapshot-read-design-gate.md` — Stage 23 设计门与 Stage 24 envelope-scoped snapshot JSON reader 实现事实源（已收口）
- `archive/85-envelope-scoped-consumer-filter-design-gate.md` — Stage 25 consumer/filter 设计门；无 filter 单-envelope v2 与宿主展示边界（已收口）
- `86-filtered-envelope-snapshot-read-design-gate.md` — Stage 26 task/request filter、关系闭包与 v3 identity 设计门（已收口）
- `87-filtered-envelope-snapshot-json-reader-implementation.md` — Stage 27 task/request filtered v3 reader 实现与验收事实源（已收口）
- `archive/88-filtered-snapshot-host-consumer-validation-gate.md` — Stage 28 Codex Desktop filtered v3 独立 consumer contract 与 Stage 29 实现边界（已收口）
- `89-codex-desktop-filtered-snapshot-consumer-implementation.md` — Stage 29 独立标准库-only stdin consumer 实现与验收事实源（已收口）
- `93-codex-desktop-filtered-snapshot-display-host-integration-and-milestone-freeze.md` — Stage 39–41 display host design、实现、验收与 `v0.17.0` 冻结事实源（已收口）
- `archive/94-filtered-snapshot-validated-markdown-presentation-handoff-gate.md` — Stage 42 ready host result → presentation boundary design-only gate（历史事实源，未实现 presenter）
- `archive/95-single-user-real-execution-readiness-gate-and-milestone.md` — Stage 43–45 单用户真实执行 readiness 历史事实源
- `96-fixed-git-status-executor-design-gate.md` — Stage 46 trusted executable/image binding、sanitized PATH、process-tree containment、finite porcelain parser、no-write evidence 与 dedicated audit release gate（design-only 已收口）
- `97-execution-lifecycle-audit-writer-design-and-implementation.md` — Stage 47–48 reserved schema、internal writer、通用入口隔离、rollback 与 recovery inspection 事实源（已收口）
- `98-fixed-git-status-executor-implementation-and-limited-enablement.md` — Stage 49 Windows trust binding、repository guard、Job Object runner、finite parser、audit release 与真实 smoke 事实源（已收口）
- `archive/92-filtered-snapshot-markdown-display-consumer-validation-gate.md` — Stage 36–38 display v1 consumer 与 `v0.16.0` 历史事实源
- `archive/91-codex-desktop-filtered-snapshot-markdown-display-integration-and-milestone-freeze.md` — Stage 33–35 Markdown display 与 `v0.15.0` 历史事实源
- `archive/90-codex-desktop-filtered-snapshot-host-integration-and-milestone-freeze.md` — Stage 30–32 host design、实现、验收与 `v0.14.0` 历史冻结事实源

### 6. 想看里程碑与冻结记录

- 当前提交级里程碑：`98-fixed-git-status-executor-implementation-and-limited-enablement.md` 与 release notes 108
- 上一提交级里程碑：`97-execution-lifecycle-audit-writer-design-and-implementation.md` 与 release notes 107
- 上一设计 gate：`96-fixed-git-status-executor-design-gate.md` 与 release notes 106
- 历史 readiness 里程碑：`archive/95-single-user-real-execution-readiness-gate-and-milestone.md` 与 release notes 104/105
- 历史 presentation gate：`archive/94-filtered-snapshot-validated-markdown-presentation-handoff-gate.md` 与 release notes 103
- 当前稳定里程碑事实源：`93-codex-desktop-filtered-snapshot-display-host-integration-and-milestone-freeze.md` 与 `archive/release-notes/102-release-notes-v0.17.0-filtered-snapshot-display-host-integration.md`
- 上一稳定里程碑事实源：`archive/92-filtered-snapshot-markdown-display-consumer-validation-gate.md` 与 `archive/release-notes/99-release-notes-v0.16.0-filtered-snapshot-display-consumer.md`
- 再上一稳定里程碑事实源：`archive/91-codex-desktop-filtered-snapshot-markdown-display-integration-and-milestone-freeze.md`
- 上一冻结事实源：`archive/77-read-only-control-plane-milestone-freeze.md`
- 历史 `v0.12.0` freeze checklist：`archive/68-orchestration-foundation-milestone-freeze-checklist.md`
- 历史 `v0.12.0` freeze execution plan：`archive/69-orchestration-foundation-freeze-execution-plan.md`

### 7. 想看历史阶段交付物

归档在 `docs/archive/`，按类别存放：

| 目录 | 内容 |
|:---|:---|
| `archive/` | 历史设计门 / freeze checklist / execution plan（含 v0.13 freeze `77`、Stage 19–21 `80`–`82`、v0.14 freeze `90`） |
| `archive/release-notes/` | 各阶段 release notes（最新为 `108-release-notes-stage49-fixed-git-status-executor.md`） |
| `archive/dry-runs/` | dry-run / commit 操作记录（8 个） |
| `archive/smoke-regression/` | smoke test / regression 报告（4 个） |

## 当前最重要 5 份文档

1. `000-stage-digest.md`
2. `98-fixed-git-status-executor-implementation-and-limited-enablement.md`
3. 最新 handoff：`tasks/handoff-2026-07-17.md`
4. `97-execution-lifecycle-audit-writer-design-and-implementation.md`
5. `96-fixed-git-status-executor-design-gate.md`

## 其他入口

- `tasks/progress.md` — 完整推进账本
- `tasks/handoff-*.md` — 阶段性交接上下文
- `README.md` — 仓库入口页
