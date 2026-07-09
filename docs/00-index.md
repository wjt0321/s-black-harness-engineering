# 00 — 文档索引

## 这份文档是干什么的

本索引用来帮助新读者快速定位 `s-black harness engineering` 的阅读入口。

如果你第一次看这个仓库，**不要从头顺序读完整个 `docs/`**。先按主题挑关键文档看。

## 推荐阅读路径

### 1. 先理解项目是什么

- `01-vision-and-boundaries.md`：项目愿景、边界、为什么要做
- `02-roadmap.md`：阶段路线图

适合：第一次进入项目、想知道“这到底是什么”的读者。

### 2. 想直接上手 CLI

- `10-cli-poc-usage.md`：CLI 用法总入口
- `21-controlled-write-boundaries.md`：受控写入总边界

适合：想直接试命令、想知道当前能做什么和不能做什么的读者。

### 3. 想理解 Runtime 主线能力

- `16-runtime-plan.md`：runtime plan
- `19-runtime-report.md`：runtime report
- `22-runtime-draft-export-dry-run.md` / `24-runtime-draft-export-commit.md`
- `26-runtime-event-append-dry-run.md` / `28-runtime-event-append-commit.md`
- `31-runtime-task-create-dry-run.md` / `33-runtime-task-create-commit.md`
- `37-runtime-event-import-dry-run.md`
- `39-runtime-event-import-commit-design.md`
- `41-runtime-event-import-consistency-freeze.md`
- `45-runtime-event-import-strict-freeze-mode.md`
- `46-release-notes-runtime-event-import-strict-freeze.md`

适合：想理解这个 Runtime 现在已经推进到哪里、受控写入链路怎么演化的读者。

### 4. 想看模型和协议层

- `03-policy-schema.md`
- `04-task-state-model.md`
- `05-agent-registry.md`
- `06-adapter-layer.md`
- `07-policy-task-bridge.md`
- `12-adapter-execution-envelope.md`
- `14-task-runtime-bridge.md`

适合：想理解底层 schema、registry、adapter envelope 和 task bridge 的读者。

### 5. 想看中枢台后端主线

- `47-orchestration-hub-vision.md`
- `48-adapter-runtime-interface.md`
- `49-capability-routing-model.md`
- `50-control-plane-state-model.md`
- `51-backend-first-api-boundary.md`
- `52-minimal-orchestration-loop.md`
- `53-minimal-orchestration-loop-cli-draft.md`
- `54-backend-preparation-before-ui.md`
- `55-release-notes-orchestration-read-models.md`
- `56-orchestration-controlled-write-boundary.md`
- `57-release-notes-orchestration-controlled-handoff.md`
- `58-orchestration-run-controlled-execution-design.md`
- `59-release-notes-orchestration-run-controlled-execution.md`
- `60-orchestration-run-lifecycle-events-design.md`
- `61-release-notes-orchestration-run-lifecycle-events.md`

适合：想理解项目如何从 guardrail 内核演进成中枢运行台、以及最小执行闭环如何串起 adapter / routing / state 的读者。

> 注意：旧 `14-task-runtime-bridge.md` 属于早期 Runtime gate 设计，与高位编号的中枢台后端主线不是同一组文档。

### 6. 想看发布与阶段收口

- `11-release-notes-v0.1.md`
- `13-release-notes-adapter-envelope.md`
- `18-release-notes-runtime-planning-bridge.md`
- `20-release-notes-runtime-report.md`
- `23` ~ `46` 各阶段 release notes
- `55-release-notes-orchestration-read-models.md`
- `57-release-notes-orchestration-controlled-handoff.md`
- `58-orchestration-run-controlled-execution-design.md`
- `59-release-notes-orchestration-run-controlled-execution.md`
- `60-orchestration-run-lifecycle-events-design.md`
- `61-release-notes-orchestration-run-lifecycle-events.md`

适合：想知道每一阶段交付了什么、能力如何封版的读者。

## 当前最重要的几份文档

如果只看 5 份，建议先看：

1. `01-vision-and-boundaries.md`
2. `10-cli-poc-usage.md`
3. `21-controlled-write-boundaries.md`
4. `47-orchestration-hub-vision.md`
5. `55-release-notes-orchestration-read-models.md`

## 其他入口

- `tasks/progress.md`：完整推进账本，适合追历史，但内容较长
- `tasks/handoff-*.md`：阶段性交接上下文
- `README.md` / `README.en.md`：仓库入口页，适合快速建立总体模型
