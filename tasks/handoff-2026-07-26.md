# Handoff — Stage 80 操作者操作资格与审批绑定

> 日期：2026-07-26
> 状态：已实现并通过本地验证

## 当前结果

Stage 80 已实现 fixture-backed、checkpoint 驱动的操作者操作资格和审批绑定。五种操作可以在 Stage 79 事件流的合法历史时点完成状态、审批和幂等检查，并生成不可执行 command candidate。

业务资格不等于执行授权。所有结果固定 `execution_authorized=false`、`dispatch_eligible=false`、`execution=not_executed`；不生成 argv/cwd/env，不调用 Agent，不启动 session，不探测 readiness，不访问网络，不写 ledger。

## 事实源

- `docs/128-stage80-operator-action-eligibility-and-approval-binding.md`
- `adapters/collaboration-action-eligibility.schema.json`
- `adapters/collaboration-action-eligibility.example.json`
- `agent_runtime/orchestration_collaboration_action_eligibility.py`
- `tests/test_orchestration_collaboration_action_eligibility.py`
- `tests/test_orchestration_control_panel_action_eligibility.py`

Stage 79 事实源已归档为 `docs/archive/127-stage79-collaboration-run-state-model.md`，实施计划归档为 `docs/archive/plans/2026-07-26-stage80-operator-action-eligibility.md`。

## 固定操作资格

- `approve_start`：run / `awaiting_approval`；
- `cancel`：run / `ready|running|blocked`；
- `retry`：work item attempt / `changes_requested|failed`；
- `request_changes`：review / `in_review`；
- `approve_handoff`：handoff / `ready`。

审批必须精确绑定 run id、run projection id、action、target、checkpoint 和 expected state。幂等键已记录时返回 `command_already_recorded`。

## 常用命令

```bash
python -m agent_runtime.cli orchestration collaboration action-eligibility inspect --file adapters/collaboration-action-eligibility.example.json --json
python -m agent_runtime.cli orchestration control-panel snapshot --collaboration-action-file adapters/collaboration-action-eligibility.example.json --json
python -m agent_runtime.cli orchestration control-panel render --collaboration-action-file adapters/collaboration-action-eligibility.example.json
```

## 验证结果

最终实际通过：

- Stage 80 action eligibility 和 Control Panel 新增测试：19 passed；
- collaboration、run-state、Control Panel 与命令面相关回归：88 passed；
- `python -m pytest tests -q`，保留 8 个环境相关预期 skip；
- `python -m agent_runtime.cli doctor`；
- `python tools/public_scan.py`（项目根 `PYTHONPATH`）；
- `python -m agent_runtime.cli docs context --json`；
- 35 个活跃 Markdown 文件相对链接审计，`docs/` 活跃文档数 31；
- `bash .githooks/pre-commit`；
- `git diff --check`；
- CLI 连续两次输出字节一致；
- Microsoft Edge 独立临时 profile 的自包含 HTML 静态渲染检查。

验证过程没有调用 Agent、启动 session、探测额度或读取凭据。

## 下一候选

Stage 81：当前态操作者待办与审批集合投影。只针对最新运行状态聚合待处理审批、当前可选操作和稳定阻止原因；仍不读取真实 approval ledger、不调用 Agent、不启动 session、不新增真实 operation。

## Git 状态

Stage 79 和 Stage 80 当前仍在同一未提交工作区中。本次用户授权继续推进，但未明确授权 commit；最终验证后继续保留改动，等待用户另行要求提交或推送。
