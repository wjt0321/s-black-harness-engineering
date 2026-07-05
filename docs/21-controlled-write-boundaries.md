# 21 — Controlled Write Boundaries 受控写入边界

## 阶段定位

本文定义 `s-black harness engineering` 从只读 Runtime 走向最小受控写入前必须满足的边界。它不是写入实现文档，也不引入任何会修改 ledger、draft 或外部系统的代码。

当前已经完成的只读链路为：

```text
task ledger
  -> runtime plan --draft-json
  -> runtime draft validate
  -> runtime draft inspect
  -> adapter validate / adapter inspect
  -> runtime gate check
  -> runtime check-ledger
  -> runtime report
```

下一步若允许 Runtime 产生持久化结果，只能从两个最低风险动作开始：

- `draft export`：把已经通过校验的 envelope draft 写入项目内受控路径。
- `event append`：把已经通过 schema 与一致性预检的 task event 追加到 event ledger。

真实 adapter execution、网络访问、消息发送、删除文件、改配置、push 等外部动作仍不属于本阶段范围。

## 总原则

### MUST

- 写入必须是显式命令触发，不能作为 `plan` / `report` / `gate` 的副作用。
- 写入前必须完成 schema validation。
- 写入前必须完成 public scan / secret pattern scan。
- 写入目标必须限制在项目根目录内的允许路径。
- 写入后必须重新运行相关 consistency validation。
- 写入结果必须有可审计证据：目标路径、校验摘要、写入摘要、下一步。
- 对既有文件的覆盖必须默认禁止，除非命令显式使用 overwrite 选项且通过审批规则。
- ledger 写入必须优先使用 append-only 模型。

### NEVER

- 不读取 `.env`、`.env.local`、credential、token、keyring 或系统密钥文件。
- 不把完整 secret match、完整 raw_ref、完整 decision_ref 输出到终端、JSON 或日志。
- 不允许向项目根目录外写入。
- 不允许通过相对路径逃逸，例如 `..`、绝对路径重定向、符号链接逃逸。
- 不允许默认覆盖已存在的 draft、ledger 或配置文件。
- 不允许在 controlled write 阶段执行真实 adapter、访问网络、发送消息、删除文件或 push。

### SHOULD

- 写入前先生成 dry-run 报告，让调用方看到将写入什么、写到哪里、需要哪些验证。
- 写入文件名使用稳定、可追踪、低碰撞格式，例如 `drafts/runtime/<task-id>/<request-id>.envelope.json`。
- 写入后输出 compact summary，避免回显完整 payload。
- 失败时保留原文件不变，返回可恢复的错误说明。

## 写入类型一：Draft Export

### 目标

把 `runtime plan --draft-json` 生成且已经通过 `runtime draft validate` 的 envelope draft 保存到项目内受控路径，供后续人工审阅、gate 检查或 ledger audit 使用。

### 允许路径

默认允许：

```text
drafts/runtime/<task-id>/<request-id>.envelope.json
```

可选允许：

```text
drafts/runtime/<task-id>/<timestamp>-<request-id>.envelope.json
```

路径规则：

- MUST 位于仓库根目录内。
- MUST 使用 `.json` 后缀。
- MUST 不包含 `..`。
- MUST 不指向 `.env`、credential、config secret 或 git internals。
- SHOULD 使用 task_id 与 request_id 建立可追踪关系。

### 写入前检查

`draft export` 写入前必须检查：

1. 输入 JSON 可解析。
2. 输入为 direct envelope 或 `runtime plan --draft-json` wrapper。
3. 通过 envelope schema validation。
4. 通过 envelope artifact consistency validation。
5. 输出路径通过 path guard。
6. 输出内容通过 public scan / secret pattern scan。
7. 目标文件不存在，或显式 overwrite 通过审批规则。

### 写入后检查

写入后必须立即检查：

1. 重新读取落盘文件。
2. 再次运行 `runtime draft validate --file <path>`。
3. 运行 `runtime draft inspect --file <path>`，只输出摘要。
4. 如有对应 task/event ledger，运行 `runtime check-ledger`。

### 输出

文本输出建议：

```text
PASS
Draft: drafts/runtime/task-.../req-....envelope.json
Validation: pass
Inspect: adapter_request=1, approval_record=0, execution_event=0, adapter_response=0
Next: Review the draft before any adapter execution.
```

JSON 输出不得包含完整 target、input payload、raw_ref、decision_ref 或 evidence description。

## 写入类型二：Event Append

### 目标

把候选 task event 追加到 event ledger，用于记录已发生的状态变化、审批请求、证据添加或完成状态。

### 允许路径

默认允许：

```text
tasks/events.jsonl
```

测试或 dry-run 可允许显式传入项目内安全 `.jsonl` 文件。

路径规则：

- MUST 位于仓库根目录内。
- MUST 使用 `.jsonl` 后缀。
- MUST 不包含 `..`。
- MUST 不指向 `.env`、credential、config secret 或 git internals。

### 写入前检查

`event append` 写入前必须检查：

1. 候选 event 是单个 JSON object。
2. event 通过 `tasks/event.schema.json`。
3. `task_id` 存在于 task ledger。
4. event timestamp 不破坏该 task 的事件顺序。
5. event 状态流转合法。
6. 若 event 引用 `request_id`，对应 request 能在 envelope 或已知 draft 中找到。
7. append 后的临时 ledger 能通过 `task check-ledger`。
8. append 后的临时 runtime ledger audit 不产生新的 error。
9. 候选 event 内容通过 public scan / secret pattern scan。

### Append-only 原则

- MUST 只追加新行，不原地修改既有 event。
- MUST 保持每行一个 JSON object。
- MUST 保留文件末尾换行。
- SHOULD 在写入前记录原文件字节大小，用于失败恢复。
- SHOULD 在写入失败时截断回原字节大小。

### 写入后检查

写入后必须立即检查：

1. `task validate --record-file <events-file> --schema event`。
2. `task check-ledger --tasks-file <tasks-file> --events-file <events-file>`。
3. 如有 envelope，运行 `runtime check-ledger`。
4. 输出 append 摘要与 next_action。

## Dry-run 与 Commit 模式

受控写入命令应该分成两个模式：

```text
--dry-run   只验证和展示将写入的摘要，不落盘。
--commit    显式落盘。
```

规则：

- 默认 SHOULD 是 `--dry-run`。
- 没有 `--commit` 时 NEVER 写入。
- `--commit` 只对当前命令、当前目标、当前输入有效，不形成长期授权。
- 高风险写入仍需额外审批，例如 overwrite、终态 task 后追加事件、跨 request 写入。

## Overwrite 规则

### Draft Export

- 默认禁止覆盖。
- 覆盖必须显式传入 `--overwrite`。
- `--overwrite` 前必须对旧文件做摘要，不回显完整内容。
- SHOULD 先把旧文件复制到受控 backup 路径，例如：

```text
backup/drafts/<timestamp>-<filename>
```

### Event Append

- 不存在 overwrite；只能 append。
- 如需修正错误 event，应追加 correction event，而不是修改历史行。

## 回滚与恢复

### Draft Export 回滚

- 如果写入前目标不存在，失败时删除半写入文件。
- 如果 overwrite 已授权，写入前必须备份旧文件；失败时恢复备份。
- 写入完成后不自动删除，后续清理必须另走审批。

### Event Append 回滚

- 写入前记录原文件 byte size。
- 追加失败或写后校验失败时，优先截断回原 byte size。
- 如果截断失败，必须输出 blocker，提示人工恢复。
- 不允许静默继续。

## 审批语义

受控写入审批必须收窄为：

```text
this command + this task_id + this request_id + this target path + this input hash
```

禁止把一次审批泛化为：

- 永久允许某类写入。
- 永久允许某路径写入。
- 自动允许后续 overwrite。
- 自动允许真实 adapter execution。

## 与现有只读命令的关系

- `runtime plan --draft-json` 仍只输出 stdout，不落盘。
- `runtime draft validate` / `inspect` 仍只读。
- `runtime gate check` 仍只读。
- `runtime check-ledger` 仍只读。
- `runtime report` 仍只读。

未来可以新增命令，但不得改变以上命令的只读语义。

可能命令形态：

```bash
python -m agent_runtime.cli runtime draft export --stdin --output drafts/runtime/... --dry-run
python -m agent_runtime.cli runtime draft export --stdin --output drafts/runtime/... --commit
python -m agent_runtime.cli runtime event append --file candidate-event.json --dry-run
python -m agent_runtime.cli runtime event append --file candidate-event.json --commit
```

## 最小 Controlled Write POC 建议

如果后续进入实现阶段，建议顺序如下：

1. 先实现 `runtime draft export --dry-run`。
2. 再实现 `runtime draft export --commit`，只允许新文件，不允许 overwrite。
3. 再实现 `runtime event append --dry-run`。
4. 最后实现 `runtime event append --commit`，只允许 append 到显式测试 ledger；真实 `tasks/events.jsonl` 需要单独审批。

每一步都必须有测试覆盖：

- 安全路径。
- 路径逃逸拒绝。
- schema invalid 拒绝。
- secret pattern 拒绝。
- dry-run 不写文件。
- commit 写入后可重新 validate。
- 失败时不破坏原文件。

## 本阶段完成条件

本设计阶段完成条件：

- 本文档落盘并纳入 README 文档索引。
- `tasks/progress.md` 记录受控写入边界设计完成。
- 不新增任何真实写入命令。
- `python -m pytest` 通过。
- `python -m agent_runtime.cli doctor` 通过。
- `python tools/public_scan.py` 通过。
- 推送前 key pattern scan 通过。

完成后，下一阶段才能考虑最小 `runtime draft export --dry-run` POC。
