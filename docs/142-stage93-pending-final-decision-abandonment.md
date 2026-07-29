# 142 — 阶段 93：待决最终决定的有限放弃

> 状态：实现与自动化验证已完成；尚未进行真实 Pi/OMP GUI 验收。

## 目标

为已经完成 `Planner → Executor → Reviewer` 三轮、并停在“等待最终人工决定”的单条链路提供一个**唯一、不可逆、需二次确认的有限放弃**。操作者可明确结束该待决链路，而不把“通过 / 要求修改”写入既有人工审阅记录。

这不是运行中取消：Harness 不终止、暂停、启动或重启外部 Agent，也不杀死进程树。外部三轮必须已经全部结束；本阶段不会恢复失败角色、自动重试、重新派发或重新打开链路。

## 精确边界

- 仅接受 `awaiting_final_human_decision` 状态；规划、执行、审阅进行中、`finalization_pending`、已停止或已完成均失败关闭。
- 先只读预览，再携带一次性 `approval_binding_id` 与显式 `--commit`。确认摘要精确绑定链路 ID、执行尝试与 manifest/artifact 摘要、审阅建议摘要及建议结论。
- 提交只复用既有不可变 `stop` 记录，固定写入 `role=final_human_decision` 与 `failure_code=external-agent-chain-operator-abandoned`；写前和写后均重新检查链路状态。
- 不新增 Agent adapter、宿主权限、任意 argv/cwd/env、网络、数据库、服务、并行、自动批准、自动恢复或自由文本停止原因。
- 放弃后保留既有 intent、规划候选、执行证据和审阅建议以供只读审计；最终决定和完成恢复入口均因链路已停止而失败关闭。

## 入口

- `agent_runtime/orchestration_external_agent_chain.py`：`preview_abandon_chain_final_decision` 与 `abandon_chain_final_decision`。
- `agent_runtime/orchestration_control_panel_approval.py`：第三种严格 GUI 信封 `abandon_final_decision`。
- `agent_runtime/control_panel_live_gui.py`：选中链路后显示“放弃选中待决链路…”，先出现不可逆提示，再复用一次性确认页。
- CLI：`orchestration execution external-agent-chain abandon-final-decision`。

## 自动验收

- 仅等待最终人工决定的链路可生成预览；初始链路、已完成、已停止或任何其他状态不能放弃。
- 错误确认摘要不写入；正确确认摘要只生成一条不可变停止记录。
- 停止后最终人工决定被拒绝；不增加执行尝试、lease、Agent 调用或审阅写入。
- CLI JSON 保持 preview-first、确定性和固定 failure code；GUI 仅能构造严格的四字段放弃信封。

## 已完成的真实运行态验证（2026-07-29）

已观察到由 GUI 启动的真实正向链路 `chain-20260729-acceptance-forward-074416191` 完成三轮并停在 `awaiting_final_human_decision`。在操作者授权下，Harness 以同一固定放弃 operation 完成 preview、一次性确认和 `--commit`：链路收束为 `stopped`，停止码为 `external-agent-chain-operator-abandoned`。

新 CLI 进程确认三轮真实证据 `attempt-20260729-001`、`attempt-20260729-003`、`attempt-20260729-005` 均可读；既有最终决定与完成恢复入口都返回 `blocked`，且 `doctor` 通过。该验证不替代下节所述的 GUI 写入按钮真实点击验收。

## 待进行的真实 GUI 验收

由操作者打开无工具且空闲的 Pi/OMP，会话完成一条已登记三轮链路后，在**不提交最终人工决定**的前提下：

1. 选中“等待最终人工决定”的链路；
2. 选择“放弃选中待决链路…”，核对提示与一次性确认摘要，再确认提交；
3. 在新 CLI 进程只读检查链路为 `stopped`，停止码为 `external-agent-chain-operator-abandoned`；
4. 确认既有候选、执行证据和审阅建议仍可读，最终决定和恢复均失败关闭，且没有新增 attempt、未闭合 audit 或 lease。

真实验收成功前，不得称其为 Pi/OMP 真实验收或将本阶段归档。
