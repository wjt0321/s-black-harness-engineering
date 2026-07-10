# 37 — Runtime Event Import Dry-run 预备设计

## 阶段定位

本文为后续 `runtime event import --dry-run` 预留设计上下文。本阶段只写设计，不实现 CLI，不新增写权限，不修改 Runtime 行为。

已有能力：

- `runtime task create --dry-run` / `--commit`
- `runtime event append --dry-run` / `--commit`
- `runtime report`
- controlled write regression test

下一步如果要支持批量 event 导入，必须先定义批量语义、失败语义、排序语义和输出脱敏规则，避免把单条 append 的安全边界扩散成不可审计的批量写入。

## 非目标

本阶段不应做：

- 不实现 `runtime event import` CLI。
- 不写 event ledger。
- 不写 task ledger。
- 不写 adapter envelope。
- 不执行 adapter。
- 不访问网络。
- 不发送消息。
- 不删除文件。
- 不读取 `.env`、credential、token 或 keyring。
- 不做自动 ledger 修复。
- 不做批量 commit。
- 不允许部分成功。

## 目标能力（下一实现阶段）

未来 `runtime event import --dry-run` 只做只读预检：

```bash
python -m agent_runtime.cli runtime event import \
  --file candidate-events.jsonl \
  --dry-run
```

可选：

```bash
--tasks-file tasks/tasks.jsonl
--events-file tasks/events.jsonl
--json
```

第一版建议只支持 JSONL 输入，每行一个 event object。暂不支持 JSON array，避免一次性读取和错误定位语义混乱。

## 输入格式

候选文件：

```text
candidate-events.jsonl
```

规则：

- 每个非空行必须是一个 JSON object。
- 每个 object 必须符合 `tasks/event.schema.json`。
- 空行可忽略，但输出应统计 ignored blank line count。
- 输入文件必须位于项目根目录内。
- 输入文件后缀必须为 `.jsonl`。
- 输入文件必须通过 safe read guard，禁止 `.env` / credential / key / pem 等。
- 禁止读取 `.git` / credential / secret 路径下的文件。

## 批量语义

第一版 dry-run 建议采用 **all-or-nothing preflight**：

- 只要任意一条 event 不合法，整体 `status=validation_failed` 或 `blocked`。
- 不做“部分可导入”结果。
- 不生成可被误解为部分成功的 commit plan。
- 输出可以列出安全摘要级别的问题定位：line number、event_id、task_id、event_type、rule_id。

原因：未来如果进入 commit 阶段，批量写入必须能事务化回滚；在语义稳定前，dry-run 就不应鼓励部分成功。

## 排序语义

第一版建议采用 **输入顺序即导入顺序**：

- 不按 timestamp 自动排序。
- 不重排输入事件。
- 不自动修复 timestamp 顺序。
- 如果输入顺序导致非法状态迁移或 ledger consistency 失败，dry-run 返回失败。

原因：自动排序会隐藏调用方真实意图，也会让审计变难。

## 重复检测

`runtime event import --dry-run` 必须检测：

1. candidate events 内部重复 `event_id`。
2. candidate `event_id` 与现有 event ledger 重复。
3. candidate 中同一 task 的状态迁移是否按输入顺序一致。
4. candidate 引用的 `task_id` 是否存在于 task ledger，或是否在同一阶段另有明确 task create plan（第一版不支持跨命令 plan，因此默认必须已存在）。

重复检测输出不能回显完整 message / metadata / payload。

## Secret / Public Scan

每条 candidate event 序列化后必须执行：

- secret scan
- public scan

命中时：

- 返回 `blocked`。
- 输出 line number、event_id（如可安全解析）、rule_id。
- 不输出完整匹配值。
- 不输出完整 message、metadata values、artifact payload、evidence description。

## 模拟 append 与 ledger consistency

Dry-run 必须在临时文件中模拟：

```text
existing events ledger + candidate events in input order
```

然后运行等价检查：

```bash
python -m agent_runtime.cli task validate --record-file <tmp-events> --schema event
python -m agent_runtime.cli task check-ledger --tasks-file <tasks-file> --events-file <tmp-events>
```

临时文件要求：

- 必须位于临时目录或项目根内可控临时文件。
- 检查完成后删除。
- 不修改真实 `tasks/events.jsonl`。
- 不创建真实 ledger 父目录。

## 输出摘要

Human 输出示例：

```text
PASS
Source: candidate-events.jsonl
event_count=3
blank_line_count=0
task_count=2
event_type_counts=created:1,status_changed:2
would_import=True
ledger_check=pass
Next: Dry-run passed. Review the event batch before any future commit command.
```

JSON 输出建议字段：

- `status`
- `source`
- `event_count`
- `blank_line_count`
- `task_count`
- `event_type_counts`
- `candidate_event_ids_present`
- `would_import`
- `ledger_check`
- `findings`
- `next_action`

不得输出完整：

- `message`
- metadata values
- artifacts payload
- evidence description
- target / input
- raw_ref / decision_ref
- secret match

## 错误定位

Findings 应优先包含：

- `line`
- `rule_id`
- `event_id`（如已解析且安全）
- `task_id`（如已解析且安全）
- `event_type`（如已解析且安全）

示例：

```text
- duplicate-candidate-event-id at line 4: event id duplicates an earlier candidate event.
- event-schema-validation-failed at line 7: required field missing: task_id
- ledger-consistency-failed at line 9: illegal status transition for task task-...
```

错误消息不得包含 candidate 原始 JSON 行全文。

## Commit 阶段预留但不实现

未来如果实现 `runtime event import --commit`，必须重新写设计文档，不应直接从 dry-run 推导。

Commit 设计至少需要定义：

- 是否允许创建新 event ledger 文件。
- 是否要求目标文件非空时必须以换行结尾。
- 写入前 byte size 记录。
- 失败按 byte size truncate 回滚。
- 批量写入中途 IO 失败的恢复策略。
- post-check 顺序。
- 是否要求 dry-run plan hash。
- 是否允许 candidate 文件在 dry-run 与 commit 之间变化。

第一版建议：**不实现 commit**。

## 测试清单（未来实现阶段）

必须覆盖：

- dry-run pass：多个 event 按输入顺序模拟 append 后通过。
- 输入文件不存在。
- 输入文件在项目根外。
- 输入文件后缀非 `.jsonl`。
- 输入文件位于 `.git` / credential / secret 路径下。
- 某行 invalid JSON。
- 某行不是 JSON object。
- 某行 schema invalid。
- candidate 内部重复 `event_id`。
- candidate 与现有 ledger 重复 `event_id`。
- 引用不存在 task。
- 非法状态迁移。
- secret scan blocked 且不泄露匹配值。
- public scan blocked 且不泄露匹配值。
- dry-run 不修改真实 events ledger。
- dry-run 不修改真实 tasks ledger。
- JSON 输出脱敏。
- 空行计数与忽略行为。

## 与现有能力的关系

`runtime event import --dry-run` 不替代：

- `runtime event append --dry-run`：单条 event 预检仍是最小安全入口。
- `runtime event append --commit`：当前唯一 event ledger 写入命令仍是单条 append。
- controlled write regression：继续保护当前已实现的受控写入点。

本设计只为后续批量预检提供边界，不改变当前 v0.10 行为。
