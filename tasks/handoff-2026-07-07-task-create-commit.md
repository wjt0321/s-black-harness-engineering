# 2026-07-07 Runtime Task Create Commit 接续上下文

> 本文件供压缩后恢复 `s-black harness engineering` 项目使用。当前项目根目录：仓库 checkout 根目录。GitHub 仓库：`https://github.com/wjt0321/s-black-harness-engineering`。

## 当前结论

`s-black harness engineering` 已完成 **Runtime Task Create Commit** 功能提交。

功能提交：

```text
2dfb8d3 Add runtime task create commit
```

建议冻结 tag：

```text
v0.10.0-runtime-task-create-commit
```

本阶段把上一阶段 `runtime task create --dry-run` 的只读门禁扩展为受控写入：允许 Runtime 在严格边界内向 task ledger 追加一个 task snapshot。

## 当前完整链路

当前链路为：

```text
task ledger
  -> runtime task create --dry-run
  -> runtime task create --commit
  -> runtime plan --draft-json
  -> runtime draft validate
  -> runtime draft inspect
  -> runtime draft export --dry-run
  -> runtime draft export --commit
  -> runtime event append --dry-run
  -> runtime event append --commit
  -> task validate / task check-ledger
  -> runtime check-ledger
  -> runtime report
```

## 新增/修改文件

- `agent_runtime/runtime_task_create.py` - task create dry-run 与 commit 受控写入逻辑。
- `agent_runtime/cli.py` - `runtime task create` 支持 `--dry-run` / `--commit` 显式互斥二选一。
- `tests/test_runtime_task_create_commit.py` - commit focused 测试。
- `tests/test_runtime_task_create_dry_run.py` - dry-run 兼容性测试更新。
- `docs/34-release-notes-runtime-task-create-commit.md` - 本阶段 release notes。
- `docs/10-cli-poc-usage.md` - CLI 用法入口更新。
- `docs/31-runtime-task-create-dry-run.md` / `docs/32-release-notes-runtime-task-create-dry-run.md` - 历史阶段文档补充指针。
- `README.md` / `README.en.md` / `AGENTS.md` - 当前状态、文档索引和项目 Agent 指引更新。
- `tasks/progress.md` - 进度记录。
- `tasks/handoff-2026-07-06-task-create-dry-run.md` - 后续补充指针。

## 当前 CLI

Dry-run：

```bash
python -m agent_runtime.cli runtime task create \
  --file candidate-task.json \
  --dry-run
```

Commit：

```bash
python -m agent_runtime.cli runtime task create \
  --file candidate-task.json \
  --commit
```

从 stdin commit：

```bash
type candidate-task.json | python -m agent_runtime.cli runtime task create \
  --stdin \
  --commit
```

支持：

```bash
--tasks-file tasks/tasks.jsonl
--events-file tasks/events.jsonl
--json
```

模式规则：

- `--dry-run` 与 `--commit` 互斥。
- 必须显式提供其中一个。
- `--dry-run` 完全只读。
- `--commit` 写入前复用 dry-run 全部门禁。

## 写入边界

`runtime task create --commit` 的唯一真实写入动作：

```text
append exactly one JSON object as the last line of a task ledger JSONL file
```

它不会：

- 写 event ledger。
- 自动创建对应 event。
- 写 adapter envelope。
- 执行 adapter。
- 访问网络。
- 发送消息。
- 覆盖、删除、重排或重写历史 task。
- 读取 `.env`、credential 或 keyring。

## 门禁与回滚

写入前检查：

- 候选 task JSON 解析。
- 候选 task 必须是单个 JSON object。
- `tasks/task.schema.json` schema validation。
- `task.id` 在目标 task ledger 中不得重复。
- candidate task 内容 secret scan。
- candidate task 内容 public scan。
- 目标 task ledger 必须位于项目根目录内、后缀 `.jsonl`、安全可读。
- commit target 禁止 sample ledger：`tasks/examples.jsonl` 与 `*.examples.jsonl`，大小写不敏感。
- commit target 禁止 `.git` / `credential` / `credentials` / `secret` / `secrets` 路径段。
- 路径逃逸通过 `resolve()` + root 包含检查拦截。
- 在临时 task ledger 中模拟 append 后运行 ledger consistency。
- 现有非空 task ledger 必须以换行结尾。
- 目标父目录必须已存在。

写入后检查：

- 等价 `task validate --schema task`。
- 等价 `task check-ledger`。

失败回滚：

- 写入前记录原 byte size 与文件是否已存在。
- 写后检查失败时按原 byte size truncate 回滚。
- 若本命令新建文件且 post-check 失败，则删除新文件。
- 回滚成功返回 `validation_failed` 并标记 `rolled_back=True`；回滚失败返回 `error` 并带 `rollback_error`。

## 输出脱敏

Human / JSON 输出只包含安全摘要：

- `source`
- `task_id`
- `task_status`
- `title_present`
- `assignee_present`
- `tag_count`
- `artifact_count`
- `evidence_count`
- `would_create`
- `ledger_check`
- `committed`
- `post_validate`
- `post_ledger_check`
- `rolled_back`
- `rollback_error`
- `findings`
- `next_action`

不会回显完整：

- title
- summary
- current_step
- blocked_message
- failure_reason
- evidence description
- artifact payload
- secret match

## 验证结果

功能提交后验证：

```text
python -m pytest tests/test_runtime_task_create_dry_run.py tests/test_runtime_task_create_commit.py -q -> 38 passed
python -m pytest -q -> passed
python -m agent_runtime.cli doctor -> PASS
python tools/public_scan.py -> OK public scan
git diff --check -> PASS
key pattern scan -> OK key scan
```

## 恢复命令

```bash
git status -sb
git log -6 --oneline --decorate
git tag --points-at HEAD
python -m pytest -q
python -m agent_runtime.cli doctor
python tools/public_scan.py
```

预期冻结后：

```text
HEAD tag: v0.10.0-runtime-task-create-commit
python -m pytest -q -> passed
python -m agent_runtime.cli doctor -> PASS
python tools/public_scan.py -> OK public scan
```

## 后续建议

下一阶段继续保持低风险，不直接进入真实 adapter execution。建议优先做：

1. `runtime task create` smoke/report loop：在临时项目副本中执行 task create dry-run -> commit -> event append dry-run/commit -> task validate/check-ledger -> runtime report。
2. `runtime event import --dry-run`：批量 event 导入预检，但需先定义排序、重复、部分失败与事务语义。
3. `ledger compaction --dry-run`：只读分析 ledger 压缩候选，不执行重写。

不要直接进入真实 adapter execution。
