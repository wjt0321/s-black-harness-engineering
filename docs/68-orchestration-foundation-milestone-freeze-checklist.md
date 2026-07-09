# 68 — Orchestration Foundation Milestone Freeze Checklist

## 目标

本文档用于判断当前仓库是否已经具备冻结为 `v0.12.0-orchestration-foundation` 候选里程碑的条件。

它**不直接创建 tag**，也不自动触发 commit / push；它只回答：

- 当前这一批能力是否已经形成了可命名的 orchestration foundation；
- 还缺不缺关键收口项；
- 如果要打 `v0.12.0-orchestration-foundation`，应以什么证据支撑。

## 候选里程碑名

- `v0.12.0-orchestration-foundation`

命名依据见：`docs/64-versioning-governance.md`。

## 相对上一冻结点的语义变化

上一条 semver 冻结点仍是：

- `v0.11.0-runtime-event-import`

相对它，当前仓库已经从 Runtime controlled-write 积木继续扩展到一条更完整的 orchestration control-plane 基础面，包括：

- read-model CLI
- controlled handoff
- run A+B commit
- task submit A+B
- retry / fallback dry-run preview

因此当前候选里程碑并不是单功能增量，而是一组围绕 orchestration backend surface 的连续能力包。

## 里程碑能力包检查

### A. Read models

- [x] `55-release-notes-orchestration-read-models.md`
- [x] `orchestration overview`
- [x] `orchestration task list`
- [x] `orchestration task get`
- [x] `orchestration run list`
- [x] `orchestration run inspect`
- [x] `orchestration approval list/get`
- [x] `orchestration artifact list/get`
- [x] `orchestration report generate`

结论：已具备最小 read-model surface。

### B. Controlled handoff

- [x] `57-release-notes-orchestration-controlled-handoff.md`
- [x] `orchestration route preview`
- [x] `orchestration preflight`
- [x] `orchestration approval resolve`

结论：已具备 route / guardrail / approval 的最小 handoff surface。

### C. Run controlled execution

- [x] `59-release-notes-orchestration-run-controlled-execution.md`
- [x] `61-release-notes-orchestration-run-lifecycle-events.md`
- [x] `orchestration run --dry-run`
- [x] `orchestration run --commit` A+B

结论：run 侧已具备 dry-run preview + A+B controlled write。

### D. Task submit entry

- [x] `62-orchestration-task-submit-controlled-write-design.md`
- [x] `63-orchestration-task-submit-created-event-design.md`
- [x] `65-release-notes-orchestration-task-submit-created-event.md`
- [x] `orchestration task submit --commit` A+B

结论：task 入口已对齐 `TaskCollection.create` 的“Task + 初始 Event”语义。

### E. Recovery preview

- [x] `66-orchestration-run-retry-fallback-design.md`
- [x] `67-release-notes-orchestration-run-retry-fallback.md`
- [x] `orchestration run --retry-of ... --dry-run`
- [x] `orchestration run --fallback-from ... --fallback-to ... --dry-run`

结论：恢复性能力已进入第一版 dry-run preview。

## 文档收口检查

- [x] `README.md` 已接入 63 / 64 / 65 / 66 / 67
- [x] `README.en.md` 已接入 63 / 64 / 65 / 66 / 67
- [x] `docs/00-index.md` 已接入 63 / 64 / 65 / 66 / 67
- [x] `docs/02-roadmap.md` 已包含 15.95 / 15.96 的实现收口状态
- [x] `docs/10-cli-poc-usage.md` 已更新 task submit A+B 与 retry/fallback dry-run preview
- [x] `tasks/progress.md` 已记录 63 / 65 / 66 / 67 推进与验证结果

## 验证证据检查

当前已复核通过：

- [x] `python -m pytest tests/test_orchestration_task_submit.py tests/test_controlled_write_regression.py -q`
- [x] `python -m pytest tests/test_orchestration_run_dry_run.py tests/test_orchestration_task_submit.py tests/test_controlled_write_regression.py -q`
- [x] `python -m pytest tests -q`
- [x] `python -m agent_runtime.cli doctor`
- [x] `python tools/public_scan.py`
- [x] `git diff --check`

说明：

- `git diff --check` 当前仅提示两个既有 Python 文件未来会按 Git 设置从 LF 转 CRLF，不属于空白错误。
- 当前没有发现 retry/fallback preview 对 commit 语义造成回归。

## 工作区状态检查

当前仍处于**未提交冻结前**状态：

- 有实现代码改动
- 有 README / roadmap / progress / release notes 改动
- 新增 63 / 64 / 65 / 66 / 67 / 68 文档尚未提交
- 尚未创建 `v0.12.0-orchestration-foundation` tag
- 尚未 push

这意味着：

- 从“能力与证据”角度，已经达到候选冻结点；
- 从“Git 冻结动作”角度，还差一次整理后的 commit/tag/push 决策。

## 当前判定

### 能力判定

**通过。**

当前仓库已经具备 `v0.12.0-orchestration-foundation` 的候选能力包：

- orchestration read models 已齐
- controlled handoff 已齐
- run A+B 已齐
- task submit A+B 已齐
- retry / fallback dry-run preview 已齐

### 冻结动作判定

**尚未执行。**

当前还没有做：

- 统一 commit
- 创建 tag
- push

因此现在的正确状态不是“已经冻结完成”，而是：

> **已具备 milestone freeze 候选条件，等待最终整理与冻结动作。**

## 建议的下一步

推荐顺序：

1. 维持当前工作区不再扩功能。
2. 由维护者审一下这批未提交变更的最终口径。
3. 若确认无新增功能，再统一 commit。
4. commit 后创建：`v0.12.0-orchestration-foundation`
5. 如需要，再执行 push。

## 本阶段结束判定

如果用户当前要求“推进到这阶段结束”，那么本阶段的正确结束条件应为：

- freeze checklist 已落盘
- milestone 候选判定已明确
- 文档入口已接好
- 验证已通过
- 不擅自执行 tag / push

以上条件当前均已满足。
