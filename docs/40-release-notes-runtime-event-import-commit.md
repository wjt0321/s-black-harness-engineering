# 40 — Release Notes: Runtime Event Import Commit

## 阶段定位

本文档标记 `runtime event import --commit` 第一版实现完成。它在上一个阶段（`docs/39-runtime-event-import-commit-design.md`）确定的事务边界基础上，正式把批量 event 导入从只读预检推进到受控写入。

## 已实现能力

- `python -m agent_runtime.cli runtime event import --file <jsonl> --commit`：将候选 JSONL 中的 event 批量追加到现有 event ledger 尾部。
- `--dry-run` 与 `--commit` 互斥；两者都不提供时报错。
- commit 内部会重跑完整 preflight，不依赖之前任何 dry-run 结果。
- 只支持 `--file` JSONL 输入；不支持 JSON array。
- 第一版要求目标 events ledger 必须已存在；不允许创建新 ledger 文件。
- 非空 events ledger 末尾必须已有换行符，否则 blocked。
- 批量 event 作为一个连续 JSONL block 追加到 ledger 尾部，不允许覆盖、插入或重排旧记录。
- 追加后立即跑 `task validate --schema event` 与 `task check-ledger` 等价 post-check。
- 任一失败按写入前 `original_size_bytes` 做 byte-size truncate 回滚；不允许部分成功。
- 不自动排序；输入顺序即写入顺序。
- 不写入 task ledger，不写入 envelope。
- 不访问网络、不执行 adapter、不发送消息、不读取 `.env`/credential、不删除文件。

## 核心实现点

- 修改 `agent_runtime/runtime_event_import.py`：
  - 新增 `EventImportCommitResult` 数据类，承载 commit 阶段的安全摘要。
  - 抽公共 preflight 为 `_run_preflight`，dry-run 与 commit 共用。
  - commit 调用 preflight 时要求目标 events ledger 必须已存在；否则返回 `events-file-not-found` blocked。
  - `import_events_commit` 按 `preflight -> target guard -> write preparation -> append block -> post-check -> rollback` 顺序执行。
  - 写入前记录 `original_size_bytes`；写入失败或 post-check 失败时 truncate 回滚。
  - rollback 失败时返回 `rollback_error`。
- 修改 `agent_runtime/cli.py`：
  - `runtime event import` 新增 `--commit` 参数。
  - `--dry-run` / `--commit` 互斥；都不传时报错 `missing-import-mode`。
  - 渲染函数同时处理 dry-run 与 commit 结果，输出保持脱敏。

## 输出摘要

人类输出示例（commit 成功）：

```text
PASS
Source: candidate-events.jsonl
event_count=3
blank_line_count=0
task_count=2
event_type_counts=created:1,status_changed:2
target_events_file=tasks/events.jsonl
committed=True
appended_line_count=3
post_validate=pass
post_ledger_check=pass
rolled_back=False
Next: Event batch committed successfully.
```

失败回滚时：

```text
VALIDATION_FAILED
Source: candidate-events.jsonl
event_count=3
blank_line_count=0
task_count=2
target_events_file=tasks/events.jsonl
committed=False
appended_line_count=0
rolled_back=True
- terminal-status-reverted at line 7: illegal status transition for task task-...
Next: Post-import checks failed and rollback succeeded. Fix the candidate batch and rerun dry-run before commit.
```

JSON 输出字段：

- `status`
- `source`
- `event_count`
- `blank_line_count`
- `task_count`
- `event_type_counts`
- `candidate_event_ids_present`
- `target_events_file`
- `committed`
- `appended_line_count`
- `post_validate`
- `post_ledger_check`
- `rolled_back`
- `rollback_error`
- `findings`
- `next_action`

## 安全边界

- 输出不回显 `message`、metadata values、artifacts payload、evidence description、`target`、`input`、`raw_ref`、`decision_ref` 或 secret match。
- 只在显式 `--commit` 下写入；默认行为仍是 dry-run。
- 写入目标严格限定为项目根目录内已存在的安全 `.jsonl` 文件；不允许 `.git`/credential/secret 路径，不允许 sample ledger。
- 回滚只 truncate 本命令追加的字节，不删除用户既有文件。

## 测试覆盖

新增 `tests/test_runtime_event_import_commit.py`，覆盖：

- commit pass：多个 event 作为连续 block 成功追加。
- `--dry-run` / `--commit` 互斥。
- 两者都不传时报错。
- candidate 文件不存在 / 根外 / 后缀错误 / 位于 `.git` 路径下。
- invalid JSON / 非 object / schema invalid。
- candidate 内部重复 `event_id`。
- 与现有 ledger 重复 `event_id`。
- unknown task。
- 非法状态迁移。
- secret scan / public scan blocked 且输出脱敏。
- events ledger 不存在 -> blocked。
- events ledger 非空但末尾无换行 -> blocked。
- post-check `task validate` 失败触发回滚。
- post-check `task check-ledger` 失败触发回滚。
- 写入中途 OSError 触发回滚。
- rollback 失败时正确报告 `rollback_error`。
- commit 不修改 task ledger。
- JSON 输出脱敏。

## 验证结果

- `python -m pytest tests/test_runtime_event_import_commit.py -q`：通过。
- `python -m pytest tests/test_runtime_event_import_dry_run.py -q`：通过。
- `python -m pytest -q`：通过。
- `python -m agent_runtime.cli doctor`：PASS。
- `python tools/public_scan.py`：OK public scan。

## 已知限制与后续建议

- 第一版不支持 `--expected-plan-hash` 与 ledger fingerprint；后续若需要 dry-run / commit 一致性冻结，可在此基础上扩展。
- 第一版不允许创建新 events ledger；后续可考虑开放“父目录已存在即可创建新 ledger”，并引入新建文件回滚时的受控删除语义。
- 暂不支持 JSON array 输入。
- 暂不支持部分成功或自动排序。
