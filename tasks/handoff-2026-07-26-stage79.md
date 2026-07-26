# Handoff — Stage 79 协作运行状态模型

> 日期：2026-07-26
> 状态：已实现并通过本地验证

## 当前结果

Stage 79 已实现 fixture-backed、事件驱动、只读的协作运行状态模型。它基于既有 collaboration plan 演示开始、阻塞恢复、审阅退回、重试、交接、产物 supersede/validated 和最终完成，并投影到中文 Control Panel。

安全边界未扩大：`dispatch_eligible=false`、`execution=not_executed`；不调用 Agent、不启动 session、不探测 readiness、不访问网络、不写 ledger、不新增真实 operation。

## 事实源

- `docs/127-stage79-collaboration-run-state-model.md`
- `adapters/collaboration-run-state.schema.json`
- `adapters/collaboration-run-state.example.json`
- `agent_runtime/orchestration_collaboration_run_state.py`
- `tests/test_orchestration_collaboration_run_state.py`
- `tests/test_orchestration_control_panel_run_state.py`

Stage 78 事实源已归档为 `docs/archive/126-stage78-manual-confirmation-and-controlled-export.md`，实施计划归档为 `docs/archive/plans/2026-07-26-stage79-collaboration-run-state.md`。

## 已实现契约

- Run、attempt、review、handoff、artifact 五类状态机；
- 从 1 开始连续的事件 sequence 和严格 from/to 状态重放；
- attempt 连续编号、单活跃尝试和关闭后重试；
- review gate、attempt、artifact 绑定；
- handoff 与 collaboration plan 来源/目标/产物约束；
- completed run 的最新尝试、validated artifact 和 accepted handoff 收口条件；
- 128 KiB、project containment、确定性 JSON、稳定 failure code 和 fail-closed；
- Control Panel 运行摘要、当前尝试、尝试历史、审阅、交接、产物和 56 条事件时间线；
- 五个 disabled 操作按钮，固定标注“仅模拟 · 无执行权限”。

## 常用命令

```bash
python -m agent_runtime.cli orchestration collaboration run-state inspect --file adapters/collaboration-run-state.example.json --json
python -m agent_runtime.cli orchestration control-panel snapshot --collaboration-run-file adapters/collaboration-run-state.example.json --json
python -m agent_runtime.cli orchestration control-panel render --collaboration-run-file adapters/collaboration-run-state.example.json
```

## 验证结果

最终实际通过：

- 新增 run-state 与 Control Panel 专项测试：20 passed；
- 相关 Control Panel 回归：65 passed；
- `python -m pytest tests -q`，保留 8 个环境相关预期 skip；
- `python -m agent_runtime.cli doctor`；
- `python tools/public_scan.py`（项目根 `PYTHONPATH`）；
- `python -m agent_runtime.cli docs context --json`；
- 35 个活跃 Markdown 文件相对链接审计，`docs/` 活跃文档数 31；
- `bash .githooks/pre-commit`；
- `git diff --check`；
- Microsoft Edge 无头模式自包含 HTML 静态渲染检查。

验证过程没有调用 Agent、启动 session、探测额度或读取凭据。

## 下一候选

Stage 80：操作者操作资格与审批绑定设计。为批准开始、取消、重试、要求修改和批准交接冻结资格条件、阻止原因、审批绑定和幂等命令候选；仍不调用 Agent、不启动 session、不新增真实 operation。

## Git 状态

本次用户授权实现，但未明确授权 commit。最终验证后保留工作区改动，等待用户另行要求提交；不得自动 push。
