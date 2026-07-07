# 39 — Runtime Event Import Commit 设计

## 阶段定位

本文定义未来 `runtime event import --commit` 的事务边界、回滚语义、输入冻结策略和 post-check 顺序。

前置条件：

- `runtime event import --dry-run` 已实现。
- 单条 `runtime event append --commit` 已实现。
- `runtime task create --commit` 已实现。
- 当前受控写入点仍然很少，必须继续维持“可审计、可回滚、可验证”的边界。

本阶段只写设计，不实现 CLI，不新增写权限，不修改现有 Runtime 行为。

## 为什么不能直接从 dry-run 推导 commit

`runtime event import --dry-run` 只解决“这一批 event 看起来是否合法”。

它没有解决：

- 批量写入过程中途失败怎么办。
- dry-run 通过后，candidate 文件被改了怎么办。
- dry-run 与 commit 之间，目标 ledger 被别的命令改了怎么办。
- 目标 ledger 不存在、为空、末尾无换行时如何处理。
- post-check 失败时如何精确回滚到写入前状态。
- 是否允许部分成功。

因此 `--commit` 必须独立设计，不能“把 dry-run 末尾加一段 append”就上线。

## 非目标

本阶段不应做：

- 不实现 `runtime event import --commit` CLI。
- 不新增真实批量写入代码。
- 不执行 adapter。
- 不访问网络。
- 不发送消息。
- 不读取 `.env` / credential / keyring。
- 不自动修复 ledger。
- 不支持“部分成功写入后保留成功部分”。
- 不支持自动重排 event 顺序。
- 不支持同时创建 task snapshot。

## 目标能力（未来实现阶段）

未来命令形态建议为：

```bash
python -m agent_runtime.cli runtime event import \
  --file candidate-events.jsonl \
  --commit
```

可选：

```bash
--tasks-file tasks/tasks.jsonl
--events-file tasks/events.jsonl
--json
--require-dry-run
--expected-plan-hash <hash>
```

其中：

- `--commit` 必须显式提供。
- 第一版建议 `--dry-run` 与 `--commit` 互斥。
- 第一版建议额外支持 `--require-dry-run`，用于强制要求调用方先跑 dry-run。
- 第一版建议支持 `--expected-plan-hash`，用于冻结 dry-run 结果与 commit 输入的一致性。

## 事务语义

第一版 `runtime event import --commit` 必须采用 **all-or-nothing append transaction**：

- 要么整批 candidate event 全部作为一个连续块写入成功。
- 要么一条都不留下。
- 不允许部分成功。
- 不允许“前 7 条成功、后 2 条失败”。
- 不允许遇错跳过继续写。

原因：

- event ledger 是时序账本，部分成功会让审计边界变得模糊。
- 当前仓库只支持本地文件级回滚，没有数据库事务；因此语义必须尽量简单而强。

## 输入与目标文件约束

### Candidate 文件

必须满足：

- 位于项目根目录内。
- 后缀为 `.jsonl`。
- 通过 safe read guard。
- 不位于 `.git` / credential / secret 路径下。
- 与 dry-run 使用的输入完全一致（若启用 `--expected-plan-hash` 则通过 hash 强校验）。

### Tasks ledger

- 默认 `tasks/tasks.jsonl`。
- 必须位于项目根目录内。
- 后缀 `.jsonl`。
- 不允许 sample ledger。
- 不允许 git internals / credential 路径。
- commit 阶段只读 task ledger，不写入 task ledger。

### Events ledger

- 默认 `tasks/events.jsonl`。
- 必须位于项目根目录内。
- 后缀 `.jsonl`。
- 不允许 sample ledger。
- 不允许 git internals / credential 路径。

第一版建议：

- **允许目标 event ledger 不存在，但父目录必须已存在。**
- 若文件不存在，可由 commit 显式创建新文件。
- 若文件已存在且非空，则必须以换行结尾。
- 若文件存在但不是 UTF-8 文本 JSONL，则直接 blocked。

原因：

- 批量导入可能用于初始化一个隔离测试账本。
- 但不应隐式创建深层目录，以免误写错路径。

## Dry-run 与 Commit 一致性

未来 commit 阶段最大的风险是：

1. dry-run 时检查的是 A 文件内容。
2. commit 时写的是 B 文件内容。
3. 或者目标 ledger 在两次调用之间被改变。

第一版建议引入 **plan hash + ledger fingerprint**：

### Plan hash

dry-run 输出建议新增：

- `plan_hash`

计算输入：

- candidate 文件规范化后的逐行内容
- 目标 `tasks_file` 相对路径
- 目标 `events_file` 相对路径
- 当前实现版本号（可选）

作用：

- commit 时传入 `--expected-plan-hash <hash>`。
- 若当前 candidate 内容与 dry-run 不一致，则 blocked。

### Ledger fingerprint

dry-run 输出建议新增：

- `events_ledger_fingerprint`
- `events_ledger_line_count`
- `events_ledger_size_bytes`

commit 前再次读取真实 ledger：

- 若 fingerprint 或 byte size 与 dry-run 时不同，则 blocked。
- 提示调用方重新 dry-run。

第一版最低要求：

- 至少校验 `events_ledger_size_bytes`。

更稳妥建议：

- 校验 `sha256(existing_events_text)`。

## Commit 流程

未来实现建议严格按以下顺序：

### Phase 1: preflight reload

在 commit 命令内重新做一遍最关键的写前校验：

- 解析 candidate JSONL。
- schema 校验。
- secret/public scan。
- candidate 内部重复 `event_id`。
- 与现有 ledger 重复 `event_id`。
- unknown task。
- 输入顺序下的状态迁移合法性。
- simulated validate/check-ledger。
- 若提供 `--expected-plan-hash`，校验 plan hash。
- 若记录了 ledger fingerprint，校验目标 ledger 未变化。

原则：

- commit 不能信任“之前某次 dry-run 通过过”；必须在写前重新确认当前状态。

### Phase 2: write preparation

写入前记录：

- `original_exists`
- `original_size_bytes`
- `original_line_count`
- `target_path`

同时检查：

- 父目录已存在。
- 现有非空文件以换行结尾。
- 目标文件当前仍是安全 project-local `.jsonl`。

### Phase 3: append block

只允许：

- 将 candidate events 作为 **一个连续 JSONL block** 追加到文件尾部。

不允许：

- 覆盖历史内容。
- 插入到中间。
- 重写整个 ledger 的排序。
- 自动格式化旧记录。

实现建议：

- 打开文件为 append 模式。
- 按输入顺序逐行写入 `json.dumps(candidate, ensure_ascii=False)`。
- 每行结尾补 `\n`。
- 记录本次新增 byte count。

### Phase 4: post-check

写入完成后，必须立即对真实 ledger 跑：

```bash
python -m agent_runtime.cli task validate --record-file <events-file> --schema event
python -m agent_runtime.cli task check-ledger --tasks-file <tasks-file> --events-file <events-file>
```

第一版建议：

- 不要求 `runtime check-ledger`，因为 event import 不涉及 envelope。

如果任一 post-check 失败：

- 立即回滚。
- 返回 `validation_failed` 或 `blocked`。
- 不保留本次半写入结果。

### Phase 5: success summary

通过后输出：

- `committed=True`
- `event_count`
- `target_events_file`
- `appended_line_count`
- `post_validate=pass`
- `post_ledger_check=pass`
- `rolled_back=False`

仍然不得回显：

- `message`
- metadata values
- artifacts payload
- evidence description
- target/input
- raw_ref/decision_ref
- secret match

## 回滚策略

第一版建议采用 **byte-size truncate rollback**，与当前单条 append / task create commit 保持一致。

写入前记录：

- `original_size_bytes`

若写后检查失败或写入过程中抛异常：

- 重新打开目标文件。
- `truncate(original_size_bytes)`。
- 若原来文件不存在且本次创建了新文件：
  - truncate 后若大小为 0，建议直接删除该新文件。
  - 但如果删除动作被定义为“危险操作”，则需在实现阶段明确其许可边界。

这里需要先定规则：

### 新文件回滚规则（建议）

若 commit 创建了一个原本不存在的 event ledger，后续失败时：

- **允许删除本次新建的空/半写入文件**，因为它属于本命令的临时副产物回滚。
- 该删除只针对“本命令新创建的目标 ledger 文件”，不适用于其他文件。

这是第一版唯一建议允许的受控删除场景。

## 删除边界

虽然全局规则倾向避免删除，但 commit 回滚阶段必须允许一类受控删除：

- 删除本命令刚创建、且因 post-check 失败需要回滚的 event ledger 文件。

必须满足：

- 文件路径就是目标 `events_file`。
- 文件在本命令开始时不存在。
- 文件由本命令创建。
- 删除发生在本命令异常/失败回滚分支。
- 不允许删除目录。
- 不允许删除其他既有文件。

如果不想引入删除语义，保守替代方案是：

- 第一版不允许创建新 ledger 文件；要求目标文件必须预先存在。

二选一建议中，我更偏向：

- **第一版先不允许创建新 ledger 文件。**

原因：

- 这样可以避免把“受控删除回滚”一起带进第一版复杂度。
- 等 commit 跑稳后，再开放新文件创建。

因此，本设计的最终推荐改为：

### 第一版最终推荐

- `events_file` **必须已存在**。
- 父目录必须已存在。
- 非空文件必须以换行结尾。
- 第一版 commit **不允许创建新 ledger 文件**。

这样 rollback 就统一为：

- 只需 `truncate(original_size_bytes)`。
- 不需要删除文件。

## 输出摘要

Human 输出建议：

```text
PASS
Source: candidate-events.jsonl
event_count=3
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
target_events_file=tasks/events.jsonl
committed=False
rolled_back=True
rollback=pass
- ledger-consistency-failed at line 7: illegal status transition for task task-...
Next: Fix the candidate batch and rerun dry-run before commit.
```

JSON 输出建议字段：

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

## 风险决策

### 是否允许目标文件不存在

推荐：**第一版不允许**。

理由：

- 避免引入“失败时删除新文件”的额外回滚边界。
- 与单条 append 的保守策略一致。
- 先保证事务语义最小可控。

### 是否要求 dry-run 先执行

推荐：**软要求 + 可选强校验**。

- 默认允许直接 `--commit`，但 commit 内仍会重跑 preflight。
- 若调用方提供 `--expected-plan-hash`，则额外要求 dry-run 与 commit 输入一致。

理由：

- 从工程角度，commit 本身重跑 preflight 已足够保证安全。
- 强制外部先调 dry-run 会增加流程耦合。

### 是否允许部分成功

推荐：**永不允许**。

### 是否自动排序

推荐：**永不允许**。

### 是否支持 JSON array 输入

推荐：**第一版不支持**。

## 与现有能力的关系

未来 `runtime event import --commit` 不替代：

- `runtime event append --commit`：单条 event 仍是最小写入入口。
- `runtime event import --dry-run`：批量写入前的只读预检。
- `runtime task create --commit`：task snapshot 仍独立写入，不与 event import 混做一个命令。

未来更合理的使用路径应是：

```text
runtime event import --dry-run
  -> review summary
  -> runtime event import --commit
  -> task validate / task check-ledger
```

但 commit 内部仍必须自带 post-check，不能把验证责任外抛给调用方。

## 建议测试清单（未来实现阶段）

必须覆盖：

- commit pass：多个 event 作为连续 block 成功追加。
- `--dry-run` 与 `--commit` 互斥。
- 未提供任一模式时报错。
- candidate 文件不存在。
- candidate 文件在项目根外。
- candidate 文件后缀非 `.jsonl`。
- candidate 文件位于 `.git` / credential / secret 路径下。
- invalid JSON / 非 object / schema invalid。
- candidate 内部重复 `event_id`。
- 与现有 ledger 重复 `event_id`。
- unknown task。
- 非法状态迁移。
- secret scan blocked 且不泄露匹配值。
- public scan blocked 且不泄露匹配值。
- events ledger 不存在（若第一版不允许则应 blocked）。
- events ledger 非空但末尾无换行。
- append 后 `task validate` 失败触发回滚。
- append 后 `task check-ledger` 失败触发回滚。
- 写入中途 OSError 触发回滚。
- rollback 本身失败时正确报告 `rollback_error`。
- commit 不修改 task ledger。
- commit 不写 envelope。
- JSON 输出脱敏。
- 若支持 `--expected-plan-hash`，则 hash 不一致时报错。
- 若记录 ledger fingerprint，则 dry-run 与 commit 之间 ledger 被外部修改时报错。

## 建议实现文件（未来）

```text
agent_runtime/runtime_event_import.py
agent_runtime/cli.py
tests/test_runtime_event_import_commit.py
docs/40-release-notes-runtime-event-import-commit.md
```

## 第一版实现建议结论

若进入下一实现阶段，建议采用以下最小边界：

- 只支持 `--file` JSONL 输入。
- `--dry-run` / `--commit` 互斥。
- commit 内部重跑完整 preflight。
- 不允许目标 events ledger 不存在。
- 只允许向现有 ledger 文件尾部追加连续 block。
- 写入后必须跑 `task validate --schema event` + `task check-ledger`。
- 任一失败按原始 byte size 回滚。
- 不允许部分成功。
- 不自动排序。
- 不支持 JSON array。
- 输出保持与 dry-run 同级别脱敏。
