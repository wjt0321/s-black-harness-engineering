# Handoff: runtime event append --dry-run

## 会话上下文

本会话完成 `s-black harness engineering` 最小 Controlled Write POC 的第三步：
`runtime event append --dry-run`。该命令在把单个候选 event 真正追加到
`tasks/events.jsonl` 之前跑通所有入门禁，但保持只读、不落盘。

## 新增命令

```bash
# 从文件模拟追加
python -m agent_runtime.cli runtime event append \
  --file candidate-event.json \
  --dry-run

# 从 stdin 模拟追加
echo '{"event_id":"evt-20260705-001",...}' | \
  python -m agent_runtime.cli runtime event append --stdin --dry-run

# 带 ledger 与 envelope audit
python -m agent_runtime.cli runtime event append \
  --file candidate-event.json \
  --dry-run \
  --tasks-file tasks/tasks.jsonl \
  --events-file tasks/events.jsonl \
  --envelope adapters/execution-envelope.examples.json \
  --json
```

## 新增/修改文件

- `agent_runtime/runtime_event_append.py`：核心 dry-run 逻辑。
- `agent_runtime/cli.py`：新增 `runtime event append` 子命令。
- `tests/test_runtime_event_append_dry_run.py`：10 个新测试。
- `docs/26-runtime-event-append-dry-run.md`：功能文档。
- `docs/10-cli-poc-usage.md`：新增用法示例。
- `README.md` / `README.en.md`：文档索引与当前状态更新。
- `tasks/progress.md`：进度记录。
- `tasks/handoff-2026-07-05-event-append-dry-run.md`：本文件。

## 验证结果

- `python -m pytest tests -q`：通过（具体数量见 `tasks/progress.md`）。
- `python -m agent_runtime.cli doctor`：PASS。
- `python tools/public_scan.py`：OK public scan。

## 安全边界

- 只实现 `--dry-run`，不实现 `--commit`。
- 不写 `tasks/events.jsonl`、不写 task ledger、不写 envelope。
- 不执行 adapter、不访问网络、不发送消息、不删除文件、不读取 `.env`/credential。
- 输出不回显完整 target / input payload / evidence description / raw_ref / decision_ref / secret match。
- 未修改 `AGENTS.md`。

## 下一步建议

1. 如需继续 Controlled Write，可实现 `runtime event append --commit`：
   - 复用 dry-run 所有预检。
   - 只允许追加到 `tasks/events.jsonl`（或显式 `--events-file`）。
   - 写入前检查 event_id 不重复、状态流转合法。
   - 写入后重新跑 ledger consistency。
   - 失败时回滚（删除本命令写入的最后一行）。
2. 或进入其他 Runtime 增强：task 创建 dry-run、批量 event import dry-run、ledger compaction dry-run 等。
3. 完善 `runtime event append` 的 JSON 输出摘要，增加 `artifact_count`、`metadata_keys` 等结构化字段。
