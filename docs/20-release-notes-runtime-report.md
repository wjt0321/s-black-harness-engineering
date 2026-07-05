# 20 — Runtime Report 阶段收口说明

## 阶段定位

本阶段冻结只读 `runtime report` 聚合报告能力。它把 task ledger、task event stream、adapter envelope inspection、runtime gate 与 runtime ledger audit 聚合成一份面向人和机器的状态报告，用于快速判断当前任务是否可继续推进、有哪些 blocker，以及下一步应该做什么。

这一阶段仍然是只读 POC：不执行真实 adapter，不访问网络，不发送消息，不删除文件，不写真实 task ledger / event ledger / adapter envelope，也不读取 `.env` / credential 文件。

## 新增能力

### `runtime report`

新增命令：

```bash
python -m agent_runtime.cli runtime report \
  --task-id task-20260703-001 \
  --request-id req-20260703-002 \
  --envelope adapters/execution-envelope.examples.json
```

可选参数：

```bash
--tasks-file <path>
--events-file <path>
--json
```

报告聚合以下内容：

- task snapshot 当前状态。
- task event stream 摘要。
- adapter envelope / draft inspection 摘要。
- runtime gate 状态。
- runtime ledger audit 状态。
- blocker 列表。
- next_action 建议。

### 文本输出

文本输出保持 compact，适合人工快速阅读。示例 task 已经处于 `finished` 终态，因此报告返回 `BLOCKED` 是预期行为：

```text
BLOCKED
Task: task-20260703-001 (finished): Wire read-only task ledger queries
Events: 4 events, latest=finished at 2026-07-03T10:35:00+08:00
Envelope: adapter_request=2, approval_record=1, execution_event=2, adapter_response=1
Gate: stage=response, can_proceed=True
Ledger: warn (tasks=2, events=8, requests=2, execution_events=2)
Blockers:
- Task is in terminal state (finished).
- Ledger audit has warnings.
Next: Task is terminal (finished); no new actions can be planned.
```

### JSON 输出

`--json` 输出结构化聚合报告，适合后续 orchestrator 或上层工具读取。JSON 输出仍然遵守最小披露原则，不回显完整 target、input payload、evidence description、raw_ref 或 decision_ref。

## 安全边界

- 不执行 adapter。
- 不访问网络。
- 不发送消息。
- 不删除文件。
- 不写 `tasks/tasks.jsonl`、`tasks/events.jsonl` 或 adapter envelope 文件。
- 不读取 `.env`、`.env.local` 或 credential 文件。
- 不回显完整 secret match。
- 不回显完整 `target`、`input` payload、`evidence` description、`raw_ref` 或 `decision_ref`。

## 实现文件

- `agent_runtime/runtime_report.py` — 只读聚合报告实现。
- `agent_runtime/cli.py` — 注册 `runtime report` 子命令与输出渲染。
- `tests/test_runtime_report.py` — 覆盖文本输出、JSON 脱敏、终态阻塞与只读不变性。
- `docs/19-runtime-report.md` — Runtime Report 设计说明。

## 验证结果

本阶段收口前验证：

```text
python -m pytest -> 211 passed
python -m agent_runtime.cli doctor -> PASS
python tools/public_scan.py -> OK public scan
```

推送前额外执行：

```text
tools/public_scan.py -> OK public scan
commit diff key pattern scan -> OK key scan
```

## 当前限制

- `runtime report` 当前要求调用方显式传入 `--request-id`。
- 报告只聚合已有 ledger / envelope 信息，不生成或写入新的 draft / event。
- ledger audit 的 warning 仅用于提示，不自动修复。
- 真实 draft export、真实 event append、真实 adapter execution 仍需要后续显式授权与单独设计。

## 后续建议

下一阶段建议不要直接进入写入实现，而是先定义受控写入边界：

```text
docs/21-controlled-write-boundaries.md
```

重点明确：

- draft export 的授权、路径与回滚规则。
- event append 的授权、schema validation 与 consistency validation。
- 写前 / 写后 public scan 与安全检查。
- append-only ledger 与恢复策略。

在边界文档冻结前，继续保持 runtime 链路只读。
