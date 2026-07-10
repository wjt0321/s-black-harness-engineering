# 13 — Adapter Execution Envelope 阶段说明

## Summary

本阶段完成了 `s-black harness engineering` 的 Adapter execution envelope 只读检查链路。

它把一次 adapter 动作拆成可描述、可校验、可检查的结构化 artifact，并提供一组只读 CLI 命令，用来判断某个 request 当前是否具备继续推进的条件。

本阶段仍不接真实外部系统，不执行 adapter，不写 task ledger。

## Scope

本阶段覆盖：

- adapter request / response / approval / event artifact 设计
- execution envelope schema 与样例
- envelope schema validation
- envelope cross-artifact consistency check
- request 级 approval 状态检查
- request 级 response / evidence 状态检查
- request 级 gate 聚合判断
- 面向人类的紧凑摘要输出
- JSON 输出，供后续 Runtime 编排层消费

## New Documents And Data

新增或扩展的主要文件：

- `docs/12-adapter-execution-envelope.md`
- `adapters/execution-envelope.schema.json`
- `adapters/execution-envelope.examples.json`
- `agent_runtime/adapter_plan.py`
- `agent_runtime/adapter_validation.py`
- `agent_runtime/adapter_approval.py`
- `agent_runtime/adapter_response.py`
- `agent_runtime/adapter_gate.py`
- `tests/test_adapter_plan.py`
- `tests/test_adapter_validate.py`
- `tests/test_adapter_inspect.py`
- `tests/test_adapter_approval.py`
- `tests/test_adapter_response.py`
- `tests/test_adapter_gate.py`

## CLI Commands

### Plan

```bash
python -m agent_runtime.cli adapter plan \
  --adapter github-cli \
  --operation git_push \
  --target origin/main
```

`adapter plan` 把 `check action` 的 preflight 结果包装成 execution envelope 草案。

它只生成草案，不执行 adapter。

### Validate

```bash
python -m agent_runtime.cli adapter validate \
  --file adapters/execution-envelope.examples.json
```

`adapter validate` 做两层检查：

- JSON Schema：结构是否符合 `adapters/execution-envelope.schema.json`
- Consistency：artifact 之间的引用和 scope 是否一致

主要 consistency 规则：

- `adapter_request.request_id` 必须唯一。
- `approval_record.request_id` 必须引用存在的 request。
- `adapter_response.request_id` 必须引用存在的 request。
- `execution_event.request_id` 必须引用存在的 request。
- `approval_record.scope` 必须与对应 request 的 task / adapter / operation / target 一致。
- 需要 approval 的 request 必须存在 approval record。
- `approval_requested` event 的 `approval_id` 必须引用存在的 approval record。

### Inspect

```bash
python -m agent_runtime.cli adapter inspect \
  --file adapters/execution-envelope.examples.json
```

`adapter inspect` 在 validate 通过后输出紧凑摘要：

- envelope version / description
- artifact counts
- request 摘要
- approval 摘要
- response 摘要
- event type counts
- overall flags

它不打印完整 envelope，也不打印 input payload。

### Approval Check

```bash
python -m agent_runtime.cli adapter approval check \
  --file adapters/execution-envelope.examples.json \
  --request-id req-20260703-001
```

`adapter approval check` 判断某个 request 的 approval 状态。

状态映射：

| 条件 | 状态 |
|:---|:---|
| request 不存在 | `needs_input` |
| request 不需要 approval | `pass` |
| approval `granted` | `pass` |
| approval `pending` | `needs_approval` |
| approval `denied` / `expired` | `blocked` |

### Response Check

```bash
python -m agent_runtime.cli adapter response check \
  --file adapters/execution-envelope.examples.json \
  --request-id req-20260703-002
```

`adapter response check` 判断某个 request 的 response 和 evidence 状态。

状态映射：

| 条件 | 状态 |
|:---|:---|
| request 不存在 | `needs_input` |
| response 缺失 | `needs_input` |
| `succeeded` 且 evidence 存在 | `pass` |
| `succeeded` 但无 evidence | `blocked` |
| `blocked` / `failed` / `skipped` | `blocked` |
| `needs_approval` | `needs_approval` |
| `needs_input` | `needs_input` |

### Gate Check

```bash
python -m agent_runtime.cli adapter gate check \
  --file adapters/execution-envelope.examples.json \
  --request-id req-20260703-002
```

`adapter gate check` 聚合 approval check 与 response check，给出单一 `can_proceed` 判断。

聚合规则：

- 先跑 approval check。
- approval 非 `pass` 时停在 `approval` 阶段。
- approval `pass` 后跑 response check。
- response check 的状态成为最终 gate 状态。
- 只有最终 `pass` 时 `can_proceed=true`。

示例结果：

```text
req-20260703-002 -> PASS, stage=response, can_proceed=True
req-20260703-001 -> NEEDS_APPROVAL, stage=approval, can_proceed=False
```

## Safety Boundary

本阶段仍保持只读：

- 不执行真实 adapter。
- 不访问网络。
- 不发送消息。
- 不删除文件。
- 不写 `tasks/tasks.jsonl` 或 `tasks/events.jsonl`。
- 不读取 `.env`、`.env.local` 或 credential 文件。
- 不回显完整 secret match。
- 不输出 input payload、evidence description 或 raw_ref 值。
- 不把 approval 泛化成长期授权。

## Validation

本阶段收口时通过：

```text
python -m pytest
152 passed

python -m agent_runtime.cli doctor
PASS

python tools/public_scan.py
OK public scan
```

已抽查：

```text
python -m agent_runtime.cli adapter gate check --file adapters/execution-envelope.examples.json --request-id req-20260703-002
PASS

python -m agent_runtime.cli adapter gate check --file adapters/execution-envelope.examples.json --request-id req-20260703-001
NEEDS_APPROVAL
```

## Known Limits

- 仍没有真实 adapter 执行器。
- 仍不会写入 task ledger。
- gate 判断只消费 envelope 文件中的既有 artifact。
- approval record 仍是结构化样例，不连接真实用户授权系统。
- response / evidence 仍来自 envelope artifact，不连接真实工具输出。
- 当前命令以 request 为中心，尚未和 task 状态自动联动。

## Recommended Next Steps

推荐下一阶段进入 **task-runtime bridge** 设计：

1. 设计 `task preflight`：把 policy check、adapter gate、completion rules 合并成 task 级只读判断。
2. 设计 task event draft：只生成将要写入的 event 草案，但不写 ledger。
3. 设计 approval artifact 的生命周期：pending -> granted / denied / expired 的只读校验与转换草案。
4. 继续保持 plan-only / dry-run，不接真实外部执行。
