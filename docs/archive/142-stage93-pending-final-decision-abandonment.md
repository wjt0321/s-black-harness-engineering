# 142 — 阶段 93：待决最终决定的有限放弃

> 状态：已验收并归档（2026-07-29）。

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

## 真实 Pi/OMP GUI 验收（2026-07-29）

操作者保持无工具、空闲的 Pi 与 OMP 打开。Harness 自动建立正向 `Pi → OMP → Pi` 链路 `chain-20260729-stage93-gui-abandon-084220441`；三轮真实角色完成后，链路进入 `awaiting_final_human_decision`。

操作者在 GUI 中关闭自动弹出的最终人工决定窗口，选中该链路，实际点击“放弃选中待决链路…”，确认不可逆提示并提交一次性确认摘要。新 CLI 进程随后确认：

- 链路为 `stopped`，停止码为 `external-agent-chain-operator-abandoned`；
- 规划、执行与审阅证据仍可读；规划与执行尝试为 `attempt-20260729-013`、`attempt-20260729-015`；
- 最终人工决定与完成恢复均返回 `blocked`；
- `doctor` 通过，未观察到未闭合 lease 或自动重试。

此前 `chain-20260729-acceptance-forward-074416191` 的真实运行态放弃也已验证证据保留与失败关闭；该次 CLI 复用固定 operation 的验证不替代本节的 GUI 点击验收。

本阶段验收完成后，后续能力必须另行授权。
