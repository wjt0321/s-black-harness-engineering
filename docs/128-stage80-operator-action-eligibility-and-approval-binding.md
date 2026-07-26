<!-- parents: 47-orchestration-hub-vision.md, archive/127-stage79-collaboration-run-state-model.md -->

# 128 - Stage 80 操作者操作资格与审批绑定

> 状态：已实现并通过本地验证
> 日期：2026-07-26

## 产品结果

Stage 80 在 Stage 79 已验证的协作运行事件流之上新增了 fixture-backed、确定性、只读的操作者操作资格投影。它能在指定历史事件 checkpoint 检查目标实体状态、审批证据精确绑定和已记录幂等键，并为业务合格的操作生成不可执行 command candidate。

本阶段没有新增执行权限。即使 `action_eligible=true`，仍固定：

- `execution_authorized=false`；
- `dispatch_eligible=false`；
- `execution=not_executed`；
- 不生成 argv、cwd 或 env；
- 不调用 Agent；
- 不启动 ACP session；
- 不探测 readiness；
- 不访问网络；
- 不写项目文件或 ledger；
- 不新增真实 operation。

## 方案选择

采用“独立 action-eligibility fixture + Stage 79 历史 checkpoint”方案，而不是把策略字段写入 run-state schema，也不直接读取真实 approval ledger。

这样可以在同一个已完成的演示运行中审阅五种操作的合法时点，同时保持三条边界：

1. 运行事实、审批证据和操作策略分层；
2. fixture 审批不能被解释为真实 ledger 授权；
3. 业务资格和执行授权是两个不同概念。

## 固定操作矩阵

| 操作 | 目标类型 | 允许的 checkpoint 状态 |
|:---|:---|:---|
| `approve_start` | run | `awaiting_approval` |
| `cancel` | run | `ready`、`running`、`blocked` |
| `retry` | work item attempt | `changes_requested`、`failed` |
| `request_changes` | review | `in_review` |
| `approve_handoff` | handoff | `ready` |

fixture 使用 Stage 79 的连续事件流分别选择 sequence 2、4、26、23 和 13，因此五种操作都能在其历史合法时点形成业务合格候选。Control Panel 中对应按钮仍全部 disabled。

## 审批绑定

每份 fixture approval 必须精确绑定：

- run id；
- run projection id；
- action；
- target type 和 target id；
- as-of sequence；
- expected state。

只有 approval 状态为 `approved` 且全部字段精确一致时，审批前置条件才满足。`pending`、`rejected`、`cancelled`、`expired`、缺失审批或任一绑定漂移都会生成稳定 blocked reason，而不是回退到宽松模式。

## 幂等命令候选

业务合格操作生成 `control-plane/collaboration-action-command-candidate/v1`：

- `candidate_id` 和 `idempotency_key` 都由 canonical JSON 内容寻址；
- 幂等键绑定 run projection、action、target、checkpoint、expected state 和 approval id；
- 已存在于 `recorded_idempotency_keys` 的键返回 `command_already_recorded`；
- candidate 不包含可执行参数，并固定不可执行 guarantees。

稳定阻止原因包括：checkpoint 越界、action/target 不匹配、目标尚未出现、目标状态不匹配、审批缺失、审批未批准、审批绑定不一致、命令已记录和同一投影内重复命令。

## 实现位置

- `adapters/collaboration-action-eligibility.schema.json`：严格 Stage 80 schema；
- `adapters/collaboration-action-eligibility.example.json`：五种操作和 fixture approval 演示；
- `agent_runtime/orchestration_collaboration_action_eligibility.py`：128 KiB 项目内读取、checkpoint 状态重建、审批绑定和幂等候选；
- `agent_runtime/cli.py`：`orchestration collaboration action-eligibility inspect` 和 Control Panel 参数；
- `agent_runtime/orchestration_control_panel.py`：中文操作资格、审批绑定和命令候选投影；
- `tests/test_orchestration_collaboration_action_eligibility.py`：核心资格与 fail-closed 回归；
- `tests/test_orchestration_control_panel_action_eligibility.py`：Control Panel、handoff 和 CLI 回归。

## CLI

检查操作资格 fixture：

```bash
python -m agent_runtime.cli orchestration collaboration action-eligibility inspect \
  --file adapters/collaboration-action-eligibility.example.json --json
```

生成包含操作资格的 Control Panel 快照：

```bash
python -m agent_runtime.cli orchestration control-panel snapshot \
  --collaboration-action-file adapters/collaboration-action-eligibility.example.json --json
```

渲染中文自包含 HTML：

```bash
python -m agent_runtime.cli orchestration control-panel render \
  --collaboration-action-file adapters/collaboration-action-eligibility.example.json
```

## Control Panel 边界

新增“协作 / 操作资格”区段，显示：

- 操作资格检查点；
- 当前状态与期望状态；
- fixture 审批状态和绑定；
- 稳定阻止原因；
- candidate id 与幂等键；
- `execution_authorized=false`、`dispatch_eligible=false`、`execution=not_executed`。

五个操作控件全部 disabled，并紧邻“资格不等于执行授权”提示。页面仍无网络请求和执行入口。

## 验证结果

最终实际通过：

- Stage 80 action eligibility 和 Control Panel 新增测试：19 passed；
- collaboration、run-state、Control Panel 与命令面相关回归：88 passed；
- `python -m pytest tests -q`（保留 8 个环境相关预期 skip）；
- `python -m agent_runtime.cli doctor`；
- `python tools/public_scan.py`（项目根 `PYTHONPATH`）；
- `python -m agent_runtime.cli docs context --json`；
- 35 个活跃 Markdown 文件相对链接审计，`docs/` 活跃文档数保持 31；
- `bash .githooks/pre-commit`；
- `git diff --check`；
- CLI 连续两次输出字节一致；
- Microsoft Edge 独立临时 profile 的自包含 HTML 静态渲染检查。

验证过程没有调用 Agent、启动 session、探测额度或读取凭据。

## 下一阶段断点：Stage 81

下一产品里程碑是“当前态操作者待办与审批集合投影”。Stage 80 证明历史 checkpoint 上的操作资格可以确定性计算；Stage 81 将只针对运行最新状态聚合待处理审批、当前可选操作和稳定阻止原因，形成操作者当前待办 read model。

Stage 81 仍必须：

- NEVER 调用 Agent、启动 session 或探测 readiness；
- NEVER 读取或修改真实 approval ledger；
- NEVER 把 fixture approval、业务资格或 disabled UI 解释为执行授权；
- NEVER 新增真实 operation；
- 真实 readiness 和单 work-item 派发继续等待独立设计及用户授权。
