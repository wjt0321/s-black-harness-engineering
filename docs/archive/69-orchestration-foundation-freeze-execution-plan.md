# 69 — Orchestration Foundation Freeze Execution Plan

> 归档状态：2026-07-15 按 `docs/MAINTENANCE.md` 移入 `docs/archive/`；正文与历史命令示例完整保留，不应再作为当前执行计划。当前冻结事实源为 `docs/77-read-only-control-plane-milestone-freeze.md`。


## 目标

本文档用于把当前已通过验证的 orchestration foundation 候选变更，整理成一次可执行的冻结动作方案。

它回答三个问题：

1. 这次冻结建议包含哪些内容？
2. commit message / tag message 应该怎么写？
3. 实际执行顺序应当是什么？

本文档本身**不执行** commit、tag 或 push。

## 冻结范围

建议纳入本次冻结的范围：

### 代码

- `agent_runtime/orchestration_task_submit.py`
- `agent_runtime/orchestration_run_dry_run.py`
- `agent_runtime/cli.py`

### 测试

- `tests/test_orchestration_task_submit.py`
- `tests/test_orchestration_run_dry_run.py`

### 文档与索引

- `README.md`
- `README.en.md`
- `docs/00-index.md`
- `docs/02-roadmap.md`
- `docs/10-cli-poc-usage.md`
- `tasks/progress.md`

### 新增阶段文档

- `docs/63-orchestration-task-submit-created-event-design.md`
- `docs/64-versioning-governance.md`
- `docs/archive/release-notes/65-release-notes-orchestration-task-submit-created-event.md`
- `docs/66-orchestration-run-retry-fallback-design.md`
- `docs/archive/release-notes/67-release-notes-orchestration-run-retry-fallback.md`
- `docs/68-orchestration-foundation-milestone-freeze-checklist.md`
- `docs/69-orchestration-foundation-freeze-execution-plan.md`

## 建议 commit message

建议使用单个、里程碑导向的 commit，而不是按文件碎切。

推荐：

```text
Freeze orchestration foundation milestone
```

如果想更具体一点，也可以用：

```text
Freeze v0.12 orchestration foundation candidate
```

当前更推荐第一种，因为它更适合作为最终 tag 所在提交。

## 建议 tag

推荐 tag：

```text
v0.12.0-orchestration-foundation
```

## 建议 annotated tag message

推荐简版：

```text
v0.12.0-orchestration-foundation

Includes:
- orchestration read models
- controlled handoff
- run A+B controlled write
- task submit A+B controlled write
- retry/fallback dry-run preview
```

如果使用多行详细版，也建议控制在这个范围，不要把所有细节都塞进 tag message。

## 冻结前最后检查

在真正执行冻结动作前，建议重新确认：

- `python -m pytest tests -q`
- `python -m agent_runtime.cli doctor`
- `python tools/public_scan.py`
- `git diff --check`
- `git status --short`

判定标准：

- 测试全绿
- doctor PASS
- public scan OK
- diff check 无空白错误
- 工作区只包含本次预期改动

## 建议执行顺序

### Step 1 — 再跑一次冻结前验证

```bash
python -m pytest tests -q
python -m agent_runtime.cli doctor
python tools/public_scan.py
git diff --check
```

### Step 2 — 统一 add

```bash
git add README.md README.en.md \
  agent_runtime/cli.py \
  agent_runtime/orchestration_task_submit.py \
  agent_runtime/orchestration_run_dry_run.py \
  docs/00-index.md docs/02-roadmap.md docs/10-cli-poc-usage.md \
  docs/63-orchestration-task-submit-created-event-design.md \
  docs/64-versioning-governance.md \
  docs/archive/release-notes/65-release-notes-orchestration-task-submit-created-event.md \
  docs/66-orchestration-run-retry-fallback-design.md \
  docs/archive/release-notes/67-release-notes-orchestration-run-retry-fallback.md \
  docs/68-orchestration-foundation-milestone-freeze-checklist.md \
  docs/69-orchestration-foundation-freeze-execution-plan.md \
  tasks/progress.md \
  tests/test_orchestration_task_submit.py \
  tests/test_orchestration_run_dry_run.py
```

Windows 下也可以分多次 `git add`，不要求一条命令完成。

### Step 3 — commit

```bash
git commit -m "Freeze orchestration foundation milestone"
```

### Step 4 — 创建 annotated tag

```bash
git tag -a v0.12.0-orchestration-foundation -m "v0.12.0-orchestration-foundation

Includes:
- orchestration read models
- controlled handoff
- run A+B controlled write
- task submit A+B controlled write
- retry/fallback dry-run preview"
```

### Step 5 — 再看一眼状态

```bash
git status --short
git tag --sort=creatordate
```

### Step 6 — 如需再 push

push 不属于本文档默认动作，应在用户明确确认后再执行。

## 当前结论

当前仓库已经达到了执行上述冻结动作的条件。

也就是说，若用户下一步批准真正执行 Git 动作，那么：

- 先 commit
- 再打 `v0.12.0-orchestration-foundation`
- 是否 push 另行确认

这是当前最短、最稳、最不拐弯的收口路径。
