<!-- parents: 47-orchestration-hub-vision.md, archive/126-stage78-manual-confirmation-and-controlled-export.md -->

# 127 - Stage 79 协作运行状态模型

> 状态：已实现并通过本地验证
> 日期：2026-07-26

## 产品结果

Stage 79 新增了 fixture-backed、事件驱动、只读的协作运行状态模型。它把 Stage 78 已确认但仍不可派发的 collaboration plan 投影为一条完整模拟运行，覆盖工作项尝试、重试、审阅、交接、阻塞恢复和产物回收，并在中文 Control Panel 中展示。

本阶段没有新增执行权限。所有投影固定保持：

- `dispatch_eligible=false`；
- `execution=not_executed`；
- 不调用 Agent；
- 不启动 ACP session；
- 不探测 readiness；
- 不访问网络；
- 不写项目文件或 ledger；
- 不新增第三个真实 operation。

## 运行状态契约

新增 `control-plane/collaboration-run-state/v1` schema，包含五类实体和一条有序事件流：

| 实体 | 状态 |
|:---|:---|
| Run | `draft`、`awaiting_approval`、`ready`、`running`、`blocked`、`cancelling`、`cancelled`、`completed`、`failed` |
| Work item attempt | `planned`、`ready`、`running`、`blocked`、`review_pending`、`changes_requested`、`completed`、`failed`、`cancelled` |
| Review | `pending`、`in_review`、`approved`、`changes_requested`、`cancelled` |
| Handoff | `pending`、`ready`、`accepted`、`rejected`、`superseded` |
| Artifact | `expected`、`reported`、`validated`、`rejected`、`superseded` |

事件必须使用从 1 开始的连续 sequence，并显式记录 `entity_type`、`entity_id`、`from_state` 和 `to_state`。校验器从事件流重放最终状态，拒绝非法迁移、断号、未知实体和最终投影不一致。

## 重试、审阅与完成条件

- 同一 work item 的 attempt number 必须从 1 连续递增；同一时刻最多一个未关闭尝试。
- 只有前一尝试进入关闭状态后才能创建重试。
- `changes_requested` 审阅必须绑定同一 work item、attempt 和已有 artifact；重试产物可将旧产物标为 `superseded`。
- handoff 必须符合 collaboration plan 中的来源、目标和 artifact 类型约束。
- completed run 必须满足：每个 work item 的最新尝试 completed、所有预期 artifact 类型均有 validated 产物、所有计划 handoff 均 accepted。
- fixture 演示包含一次 `running -> blocked -> running` 恢复，以及实现工作项的第二次尝试。

## 实现位置

- `adapters/collaboration-run-state.schema.json`：严格 JSON Schema；
- `adapters/collaboration-run-state.example.json`：56 个连续事件的确定性演示；
- `agent_runtime/orchestration_collaboration_run_state.py`：128 KiB 项目内读取、schema/语义/事件重放校验和只读投影；
- `agent_runtime/cli.py`：`orchestration collaboration run-state inspect` 以及 Control Panel `--collaboration-run-file` 参数；
- `agent_runtime/orchestration_control_panel.py`：运行摘要、当前尝试、尝试历史、审阅、交接、产物、事件时间线和禁用操作按钮；
- `tests/test_orchestration_collaboration_run_state.py`：状态契约与 fail-closed 回归；
- `tests/test_orchestration_control_panel_run_state.py`：中文界面、转义、handoff 和 CLI 回归。

## CLI

检查 fixture：

```bash
python -m agent_runtime.cli orchestration collaboration run-state inspect \
  --file adapters/collaboration-run-state.example.json --json
```

生成包含运行状态的确定性快照：

```bash
python -m agent_runtime.cli orchestration control-panel snapshot \
  --collaboration-run-file adapters/collaboration-run-state.example.json --json
```

渲染自包含中文 HTML：

```bash
python -m agent_runtime.cli orchestration control-panel render \
  --collaboration-run-file adapters/collaboration-run-state.example.json
```

缺失、越界、超限、schema 不符或语义不一致的输入统一 fail closed，并返回稳定 finding rule；不会回退到执行或宽松投影。

## Control Panel 边界

页面显示五个未来操作语义：批准开始、取消、重试、要求修改、批准交接。它们全部使用 disabled 按钮，并紧邻“仅模拟 · 无执行权限”提示。页面无 `fetch`、无 `XMLHttpRequest`，事件标签经过 HTML 转义。

## 验证结果

最终实际通过：

- `python -m pytest tests/test_orchestration_control_panel.py tests/test_orchestration_control_panel_collaboration.py tests/test_orchestration_manual_board.py tests/test_orchestration_control_panel_run_state.py tests/test_orchestration_collaboration_run_state.py -q`；
- `python -m pytest tests -q`（保留 8 个环境相关预期 skip）；
- `python -m agent_runtime.cli doctor`；
- `python tools/public_scan.py`（项目根 `PYTHONPATH`）；
- `python -m agent_runtime.cli docs context --json`；
- 35 个活跃 Markdown 文件相对链接审计，`docs/` 活跃文档数保持 31；
- `bash .githooks/pre-commit`；
- `git diff --check`；
- Microsoft Edge 无头模式自包含 HTML 静态渲染截图检查。

验证过程没有调用 Agent、启动 session、探测额度或读取凭据。

## 下一阶段断点：Stage 80

下一产品里程碑是“操作者操作资格与审批绑定设计”。在不执行 Agent 的前提下，为批准开始、取消、重试、要求修改和批准交接定义确定性资格、阻止原因、审批绑定和幂等命令候选。

Stage 80 仍必须：

- NEVER 调用 Agent、启动 ACP session 或 readiness probe；
- NEVER 新增真实 operation；
- NEVER 把 disabled UI、人工确认或 read model 解释为权限；
- 先完成操作资格和审批/取消语义，再考虑无 prompt 探针或单 work-item 真实派发。
