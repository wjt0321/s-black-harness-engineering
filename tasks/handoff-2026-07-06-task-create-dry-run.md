# 2026-07-06 Runtime Task Create Dry-run 接续上下文

> 本文件供压缩后恢复 `s-black harness engineering` 项目使用。当前项目根目录：仓库 checkout 根目录。GitHub 仓库：`https://github.com/wjt0321/s-black-harness-engineering`。

## 当前结论

`s-black harness engineering` 已完成 **Runtime Task Create Dry-run** 阶段。

功能提交：

```text
1fd9982 Add runtime task create dry-run
```

建议冻结 tag：

```text
v0.9.0-runtime-task-create-dry-run
```

本阶段只实现 dry-run，不新增真实写权限，不实现 task create commit。

## 当前完整链路

当前链路为：

```text
task ledger
  -> runtime task create --dry-run
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

- `agent_runtime/runtime_task_create.py` - task create dry-run 门禁逻辑。
- `agent_runtime/cli.py` - 新增 `runtime task create` 子命令。
- `tests/test_runtime_task_create_dry_run.py` - focused 测试。
- `docs/31-runtime-task-create-dry-run.md` - 使用与设计文档。
- `docs/32-release-notes-runtime-task-create-dry-run.md` - 本阶段 release notes。
- `docs/10-cli-poc-usage.md` - CLI 用法入口。
- `README.md` / `README.en.md` - 当前状态与文档索引更新。
- `tasks/progress.md` - 进度记录。

## 当前 CLI

```bash
python -m agent_runtime.cli runtime task create \
  --file candidate-task.json \
  --dry-run
```

```bash
type candidate-task.json | python -m agent_runtime.cli runtime task create \
  --stdin \
  --dry-run
```

支持：

```bash
--tasks-file tasks/tasks.jsonl
--events-file tasks/events.jsonl
--json
```

`--commit` 未实现；显式传入会返回 `commit-not-implemented`。

## 验证结果

本阶段收口前验证：

```text
python -m pytest tests/test_runtime_task_create_dry_run.py -q -> passed
python -m pytest -q -> passed
python -m agent_runtime.cli doctor -> PASS
python tools/public_scan.py -> OK public scan
git diff --check -> PASS
key pattern scan -> OK key scan
```

## 安全边界

本阶段没有新增真实写权限。

当前允许的真实写入仍只有：

- `runtime draft export --commit` 写入 `drafts/runtime/.../*.json` 的新文件。
- `runtime event append --commit` 追加一个 JSON object 到 event ledger JSONL 最后一行。

`runtime task create --dry-run`：

- 不写 `tasks/tasks.jsonl`。
- 不写 `tasks/events.jsonl`。
- 不执行 adapter。
- 不访问网络。
- 不发送消息。
- 不读取 `.env` / credential。
- 不回显完整 title、summary、evidence description、secret match 或自由文本 payload。
- 允许新 task 暂时没有对应 event；只要求模拟 append 后不破坏现有 ledger consistency。

## 恢复命令

```bash
git status -sb
git log -5 --oneline
git tag --points-at HEAD
python -m pytest -q
python -m agent_runtime.cli doctor
python tools/public_scan.py
```

预期冻结后：

```text
main...origin/main
HEAD tag: v0.9.0-runtime-task-create-dry-run
python -m pytest -q -> passed
python -m agent_runtime.cli doctor -> PASS
python tools/public_scan.py -> OK public scan
```

## 后续建议

下一阶段继续保持低风险，建议优先做：

1. 从 `docs/33-runtime-task-create-commit.md` 出发实现或继续审查 `runtime task create --commit`。先保持唯一写入目标为 task ledger，禁止自动写 event ledger。
2. `runtime event import --dry-run`，但需先定义批量排序、重复、部分失败与事务语义。
3. `ledger compaction --dry-run`，只读分析压缩候选，不执行重写。

不要直接进入真实 adapter execution。
