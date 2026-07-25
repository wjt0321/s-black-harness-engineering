# 41 — Runtime Event Import Consistency Freeze 设计

## 阶段定位

本文定义 `runtime event import --dry-run` 与 `runtime event import --commit` 之间的一致性冻结策略，目标是避免出现“dry-run 检查的是 A，commit 提交的是 B”的情况。

前置条件：

- `runtime event import --dry-run` 已实现。
- `runtime event import --commit` 已实现。
- commit 当前已能在写前重跑完整 preflight，并在写后失败时 rollback。

本阶段只写设计，不实现 CLI，不新增写权限，不修改现有 Runtime 行为。

## 要解决的问题

当前 `runtime event import --commit` 已经足够安全，但仍存在两类“时间差”风险：

### 风险 1：candidate 文件变化

场景：

1. 用户对 `candidate-events.jsonl` 跑了 dry-run，结果通过。
2. 之后该文件被手动编辑、重新生成、覆盖，甚至只改了一行。
3. 调用方仍然拿着旧 dry-run 的理解去执行 commit。

结果：

- commit 虽然会重跑 preflight，但调用方可能误以为“这是刚才看过那一批”。
- 人类审阅链与实际写入内容脱节。

### 风险 2：目标 ledger 变化

场景：

1. 用户对当前 `tasks/events.jsonl` 跑了 dry-run，结果通过。
2. 之后另一个命令、另一个分支、或人工编辑改变了目标 ledger。
3. 调用方继续用原来的 dry-run 理解执行 commit。

结果：

- commit 仍可能通过，因为当前状态也许仍然合法。
- 但它已经不是“基于当时那份 ledger 的计划”。
- 审计上会出现“review 时看到的上下文”和“真正写入时的上下文”不一致。

## 目标能力

未来建议给 `runtime event import --dry-run` 与 `runtime event import --commit` 增加 **一致性冻结（consistency freeze）** 支持。

### dry-run 新增输出

dry-run 除现有安全摘要外，额外输出：

- `plan_hash`
- `candidate_fingerprint`
- `events_ledger_fingerprint`
- `events_ledger_size_bytes`
- `events_ledger_line_count`
- `tasks_ledger_fingerprint`（可选）
- `freeze_mode`

### commit 新增输入

commit 可选新增：

```bash
--expected-plan-hash <hash>
--expected-events-ledger-fingerprint <hash>
--expected-events-ledger-size-bytes <n>
--require-dry-run
```

其中第一版推荐最低实现：

- `--expected-plan-hash`
- `--expected-events-ledger-fingerprint`

## 设计原则

### 原则 1：冻结只约束“人类审阅过的上下文”

一致性冻结不是为了替代 commit 内部 preflight。

commit 内部 preflight 解决的是：

- 现在写进去会不会破坏 ledger
- 现在输入是否合法

一致性冻结解决的是：

- 这次 commit 是否仍然对应“那次 dry-run 审阅过的同一批输入、同一份上下文”

两者必须并存，不能互相替代。

### 原则 2：默认不强制，但一旦提供 freeze 参数就必须严格校验

第一版建议：

- dry-run 默认总是输出 freeze 信息。
- commit 默认不强制要求 dry-run。
- 但如果调用方显式提供了 freeze 参数，则 commit 必须严格校验，不允许“差不多就算了”。

### 原则 3：freeze 失败应返回 blocked，而不是 validation_failed

因为这不是输入 schema 错误，也不是 ledger 逻辑错误，而是：

- 审阅上下文与提交上下文不一致
- 应提示重新 dry-run

因此状态建议为：

- `blocked`

## Candidate Fingerprint

### 定义

`candidate_fingerprint` 表示当前 candidate 文件内容的稳定摘要。

建议基于以下内容计算：

- 候选文件中每个非空行的原始 UTF-8 文本（保留输入顺序）
- 使用 `\n` 统一拼接
- 对拼接后的字节串做 `sha256`

原因：

- 候选文件是按“输入顺序即导入顺序”语义解释的。
- 不应在 fingerprint 阶段重排、规范化排序或重新 pretty-print JSON。
- 否则会掩盖真正的输入变化。

### 输出字段

```json
{
  "candidate_fingerprint": "sha256:..."
}
```

## Events Ledger Fingerprint

### 定义

`events_ledger_fingerprint` 表示 dry-run 时目标 events ledger 的稳定摘要。

建议基于以下内容计算：

- 目标 `events_file` 当前的完整 UTF-8 文本字节
- 做 `sha256`

同时附带：

- `events_ledger_size_bytes`
- `events_ledger_line_count`

理由：

- fingerprint 用于严格比对全文是否变化。
- size / line count 用于更易读的差异提示与快速 sanity check。

### 不存在文件时

当前 commit 第一版不允许目标 `events_file` 不存在，因此 freeze 阶段可简单处理为：

- 若文件不存在，则 dry-run 仍可输出：
  - `events_ledger_exists=false`
  - `events_ledger_fingerprint=null`
  - `events_ledger_size_bytes=0`
  - `events_ledger_line_count=0`

但如果未来调用方把这一状态带入 commit，commit 仍应 blocked。

## Tasks Ledger Fingerprint

### 是否需要

严格来说，candidate 的合法性也依赖 `tasks/tasks.jsonl`，因为需要：

- task 是否存在
- snapshot status 与 event 流是否一致

所以从纯一致性角度看，也应该冻结 `tasks_file`。

### 第一版建议

建议先分两层：

#### 最小冻结（推荐首发）

只冻结：

- candidate 内容
- events ledger

#### 扩展冻结（后续可加）

再冻结：

- tasks ledger

原因：

- events ledger 是 event import 的直接写入目标，也是最关键的上下文。
- tasks ledger 虽然重要，但如果 commit 内部仍会重跑 preflight，那么 tasks ledger 的变化已经会被重新校验，不会造成越权写入。
- 第一版先冻结最关键的“审阅-提交一致性”对象即可。

因此：

- `tasks_ledger_fingerprint` 可先作为可选预留字段，不作为首发强约束。

## Plan Hash

### 目标

`plan_hash` 不只是 candidate 或 ledger 的 hash，它表示一次 dry-run 的“完整上下文计划”。

### 建议输入

建议基于一个稳定的 JSON object 计算：

```json
{
  "schema_version": 1,
  "mode": "runtime-event-import",
  "candidate_fingerprint": "sha256:...",
  "tasks_file": "tasks/tasks.jsonl",
  "events_file": "tasks/events.jsonl",
  "events_ledger_fingerprint": "sha256:...",
  "events_ledger_size_bytes": 1234,
  "events_ledger_line_count": 12,
  "input_order_preserved": true,
  "all_or_nothing": true
}
```

然后：

- `json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))`
- 对结果做 `sha256`

### 为什么要有 plan hash

因为单独传多个 fingerprint 参数太散：

- 容易漏传
- 容易传错组合
- 人类不容易识别“这是不是同一份计划”

`plan_hash` 可以作为一次 dry-run 的统一摘要锚点。

## Freeze Mode

建议定义两种模式：

### 1. advisory

- dry-run 输出 freeze 信息
- commit 不强制检查
- 仅供人工比对或上层系统保存

### 2. strict

- commit 接收 `--expected-plan-hash`
- 若当前环境算出的 hash 不一致，则 blocked

第一版推荐：

- 先实现 advisory 输出 + strict commit 校验
- 不强制全局 always-on strict

## CLI 形态建议

### Dry-run

现有：

```bash
python -m agent_runtime.cli runtime event import \
  --file candidate-events.jsonl \
  --dry-run
```

建议无需新增参数，直接在结果里附带：

- `plan_hash`
- `candidate_fingerprint`
- `events_ledger_fingerprint`
- `events_ledger_size_bytes`
- `events_ledger_line_count`
- `freeze_mode=advisory`

### Commit

建议新增：

```bash
python -m agent_runtime.cli runtime event import \
  --file candidate-events.jsonl \
  --commit \
  --expected-plan-hash sha256:...
```

可选扩展：

```bash
--expected-events-ledger-fingerprint sha256:...
--expected-events-ledger-size-bytes 1234
```

### `--require-dry-run`

这个参数也可作为更强工作流约束：

- 未提供 `--expected-plan-hash` 时，如果传了 `--require-dry-run`，则直接报错。
- 表示“这次 commit 必须绑定某次 dry-run 计划”。

但第一版不一定要和 freeze 一起首发。

## Commit 校验顺序

未来若实现 consistency freeze，建议 commit 顺序变为：

```text
1. resolve candidate/events/tasks paths
2. recompute current candidate_fingerprint
3. recompute current events_ledger_fingerprint
4. if expected freeze params present -> compare freeze first
5. if freeze mismatch -> blocked immediately
6. rerun full preflight
7. append block
8. post-check
9. rollback on failure
```

### 为什么先比 freeze 再跑 preflight

因为 freeze 的目标是告诉用户：

- “你现在提交的不是刚才审过的那份上下文”

这件事不需要等 preflight 跑完才知道。

更早失败更符合用户心智，也更省资源。

## Freeze 失败时的输出

### Human 输出示例

```text
BLOCKED
Source: candidate-events.jsonl
event_count=3
would_import=False
freeze_check=failed
- plan-hash-mismatch: current candidate or ledger context no longer matches the reviewed dry-run plan.
Next: Rerun runtime event import --dry-run and review the updated batch before commit.
```

### JSON 输出建议字段

- `freeze_check`
- `expected_plan_hash`
- `current_plan_hash`
- `expected_events_ledger_fingerprint`（如有）
- `current_events_ledger_fingerprint`
- `findings`
- `next_action`

### 脱敏要求

freeze 失败输出仍不得回显：

- candidate 原始 JSON 行全文
- message
- metadata values
- artifacts payload
- evidence description
- secret match

最多只输出：

- hash 值
- 文件相对路径
- line count / size bytes

## 风险决策

### 是否把 freeze 做成 commit 默认强制

推荐：**第一版不强制**。

原因：

- 现有 commit 已有完整 preflight + post-check，功能上已经安全。
- freeze 是“审阅上下文一致性增强”，不是写入安全的最低门槛。
- 直接强制会改变现有使用方式，阻力更大。

### 是否同时冻结 tasks ledger

推荐：**第一版先不强制**。

### 是否允许只传 size 不传 fingerprint

推荐：**不建议**。

size 相同但内容不同并不罕见，因此：

- `events_ledger_size_bytes` 只能作为辅助信息
- 不能替代 `events_ledger_fingerprint`

### 是否允许只传 candidate hash 不传 ledger hash

可以，但推荐 `plan_hash` 一次打包更稳妥。

## 与现有能力的关系

一致性冻结不会替代：

- dry-run
- commit 内部 preflight
- post-check rollback

它只是在两者之间增加一层：

- **审阅上下文一致性校验**

理想路径将变成：

```text
runtime event import --dry-run
  -> review summary + plan_hash
  -> runtime event import --commit --expected-plan-hash <hash>
  -> write + post-check + rollback if needed
```

## 建议测试清单（未来实现阶段）

必须覆盖：

- dry-run 输出 `plan_hash` / `candidate_fingerprint` / `events_ledger_fingerprint`。
- 同一输入两次 dry-run 产生相同 `plan_hash`。
- candidate 文件改一行后 `plan_hash` 改变。
- target events ledger 变化后 `events_ledger_fingerprint` 改变。
- commit 提供正确 `--expected-plan-hash` 时通过。
- commit 提供错误 `--expected-plan-hash` 时 blocked。
- commit 在 dry-run 后 candidate 文件被改动时 blocked。
- commit 在 dry-run 后 target events ledger 变化时 blocked。
- freeze mismatch 输出脱敏，不回显原始 JSON 行。
- 不提供 freeze 参数时，现有 commit 行为不变。
- 若后续支持 `tasks_ledger_fingerprint`，则 tasks ledger 改变也能触发 blocked。

## 建议实现文件（未来）

```text
agent_runtime/runtime_event_import.py
agent_runtime/cli.py
tests/test_runtime_event_import_freeze.py
docs/42-release-notes-runtime-event-import-consistency-freeze.md
```

## 第一版实现建议结论

若进入下一实现阶段，建议采用以下最小边界：

- dry-run 默认输出 `plan_hash`、`candidate_fingerprint`、`events_ledger_fingerprint`、`events_ledger_size_bytes`、`events_ledger_line_count`。
- commit 可选接收 `--expected-plan-hash`。
- 若提供 `--expected-plan-hash`，则在 preflight 前先重算当前 plan hash 并严格比对。
- mismatch 一律 `blocked`。
- 不强制全局 always-on freeze。
- 第一版先不强制冻结 tasks ledger。
