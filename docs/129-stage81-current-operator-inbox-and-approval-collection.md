<!-- parents: 47-orchestration-hub-vision.md, archive/128-stage80-operator-action-eligibility-and-approval-binding.md -->

# 129 - Stage 81 当前态操作者待办与审批集合

> 状态：已完成并通过完整验证
> 日期：2026-07-26

## 产品结果

Stage 81 新增了 current-state、fixture-backed、确定性、只读的操作者待办投影。它只根据一个当前 Run projection 的最新状态，聚合当前操作资格、待处理审批、历史目标失效原因和不可执行幂等命令候选。

本阶段明确区分：

- 历史 checkpoint 曾经合格的操作；
- 当前最新状态仍然合格的操作；
- 已进入待处理审批集合但尚未批准的操作；
- 目标已经不是 current attempt/review/handoff 的 stale 操作。

本阶段不读取真实 approval ledger，不调用 Agent、不启动 ACP session、不探测 readiness、不访问网络、不写项目文件或 ledger，也不新增真实 operation。

## 当前态规则

固定沿用五种 action/state 矩阵，但只允许最新目标：

| 操作 | current 目标 | 允许状态 |
|:---|:---|:---|
| `approve_start` | current Run | `awaiting_approval` |
| `cancel` | current Run | `ready`、`running`、`blocked` |
| `retry` | latest attempt | `changes_requested`、`failed` |
| `request_changes` | current review | `in_review` |
| `approve_handoff` | current handoff | `ready` |

历史 attempt、属于旧 attempt 的 review、已被接受的旧 handoff 不会因为仍存在于 run history 中，就重新成为当前待办。它们返回 `target_not_current` 或稳定的状态阻止原因。

演示 fixture 的最新 Run 为 `blocked`：

- `cancel` 当前业务资格成立，并生成 1 个不可执行 command candidate；
- `request_changes` 有 1 个 `pending` fixture approval，但目标 review 属于历史 attempt；
- `approve_start`、`retry` 和 `approve_handoff` 因当前状态或历史目标被阻止。

## 审批集合

inbox fixture 的 approval binding 精确绑定：

- run id；
- run projection id；
- action；
- target type 和 target id；
- expected state。

`pending` 审批会进入 `pending_approvals` 集合，但不会生成候选或执行权限。审批状态不是 ledger 事实，只是当前阶段的 fixture evidence。

## 幂等候选与边界

当前合格操作的 candidate id 和 idempotency key 由 canonical JSON 内容寻址，并绑定 run projection、action、target、expected state 和 approval id。

以下情况稳定阻止：

- `action_target_mismatch`；
- `target_not_current`；
- `target_state_mismatch`；
- `approval_missing`；
- `approval_not_approved`；
- `approval_binding_mismatch`；
- `command_already_recorded`；
- `command_duplicate_in_projection`。

即使 `action_eligible=true`，输出仍固定：

- `execution_authorized=false`；
- `dispatch_eligible=false`；
- `execution=not_executed`；
- candidate 不包含 argv、cwd 或 env。

## 实现位置

- `adapters/collaboration-run-state-current.example.json`：Stage 79 run-state 的当前 blocked 前缀 fixture；
- `adapters/collaboration-operator-inbox.schema.json`：当前待办与审批集合严格 schema；
- `adapters/collaboration-operator-inbox.example.json`：1 个当前合格取消候选、1 个待处理审批和 4 个阻止示例；
- `agent_runtime/orchestration_collaboration_operator_inbox.py`：当前实体索引、stale target 检查、审批集合和幂等候选；
- `agent_runtime/cli.py`：`orchestration collaboration inbox inspect` 和 Control Panel 参数；
- `agent_runtime/orchestration_control_panel.py`：中文“协作 / 当前待办”投影；
- `tests/test_orchestration_collaboration_operator_inbox.py`：current-state 与 fail-closed 回归；
- `tests/test_orchestration_control_panel_operator_inbox.py`：中文界面、handoff、禁用控件和 CLI 回归。

## CLI

检查当前待办：

```bash
python -m agent_runtime.cli orchestration collaboration inbox inspect \
  --file adapters/collaboration-operator-inbox.example.json --json
```

生成 Control Panel 快照：

```bash
python -m agent_runtime.cli orchestration control-panel snapshot \
  --collaboration-inbox-file adapters/collaboration-operator-inbox.example.json --json
```

渲染自包含中文 HTML：

```bash
python -m agent_runtime.cli orchestration control-panel render \
  --collaboration-inbox-file adapters/collaboration-operator-inbox.example.json
```

## Control Panel 边界

新增“协作 / 当前待办”区段，展示：

- 当前 Run 状态和 current attempt/review/handoff 集合；
- 待处理审批；
- 当前操作资格；
- stale target 和状态阻止原因；
- 当前幂等命令候选。

五个控件全部 disabled，并标记“当前待办不是执行授权”。页面仍无 `fetch`、`XMLHttpRequest` 或执行入口。

## 收口验证

2026-07-26 已完成：

- Stage 81 新增测试：15/15 通过；
- 协作与 Control Panel 相关回归：103/103 通过；
- 完整 `tests/`：收集 1559 项，pytest exit 0；
- `doctor`：PASS；
- `public_scan.py`：OK；
- `docs context --json`：正确识别 Stage 81 completed、31 份活跃文档和 Stage 82 下一入口；
- 活跃 Markdown 相对链接审计：35 个入口/文档文件、31 份活跃 `docs/`，无断链；
- Stage 81 CLI inspect/snapshot/render smoke：summary 为 5 个操作、1 个 eligible、4 个 blocked、1 个 pending approval；
- Edge 静态渲染 smoke、`.githooks/pre-commit` 和 `git diff --check`：通过。

验证过程未调用 Agent、未启动 session、未探测 readiness、未读取凭据或真实 approval ledger。

## 下一阶段断点：Stage 82

下一产品里程碑是“External Agent Adapter Contract 与 MVP Boundary”。长期产品目标以 `130-gui-first-external-agent-control-plane-target.md` 为准：统一 GUI 管理 Claude、Kimi、OMP/Pi、QwenPaw 和未来外部 Agent，并通过结构化 plan、work item、handoff、artifact 和 review 完成真实多 Agent 协同。

Stage 82 需要冻结 transport-neutral 的 identity、capability、readiness、session、dispatch、event、cancel、artifact、recovery contract；approval evidence 安全审查是 dispatch authority 的组成部分，不再作为孤立产品方向。

Stage 82 仍必须：

- NEVER 调用 Agent、启动 session 或探测 live readiness；
- NEVER 读取或修改真实 approval ledger；
- NEVER 将 current inbox、fixture approval 或业务资格解释为执行授权；
- NEVER 新增真实 operation、网络 adapter、服务或数据库；
- 只输出 schema、failure matrix、测试计划和 GUI 最小 live read model；真实接入继续等待独立设计、测试和用户授权。
