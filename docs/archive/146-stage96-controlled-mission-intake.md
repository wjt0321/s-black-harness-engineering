# 146 — 阶段 96 Agent Deck 受控任务登记与规划收件箱

> 状态：已完成并归档
> 日期：2026-07-29
> 前序：`145-stage95-agent-deck-mission-workspace.md`
> 长期目标：`../130-gui-first-external-agent-control-plane-target.md`

## 1. 本阶段解决的问题

阶段 95 的浏览器草案和真实任务账本仍然断开：用户可以描述目标，但草案不能安全、可审计地成为 Harness 的正式任务。本阶段交付固定的 **受控任务登记入口**：只接受一段有界自然语言目标，自动分配内部任务编号，并复用既有任务账本 A+B 事务写入一项任务及一条 `created` 事件。

登记后的任务会以“等待主控 Agent 规划”状态进入 Agent Deck 安全快照和任务工作区。它是主控规划的明确收件箱，而不是已经启动的主控 Agent。

## 2. 已交付能力

- 新增 `agent-deck mission submit`：
  - `--goal` 仅为单段、最多 500 字符 / 1 KiB 的任务目标；先经 secret scan；
  - `--dry-run` 只预览，`--commit` 才会写入；二者互斥且必选；
  - 用户不能提供 task ID、event ID、账本路径、Agent 参数、cwd、env 或宿主控制参数；
  - 内部编号按当天现有账本安全递增，写入复用 `orchestration_task_submit.submit_task` 的 A+B 事务、后验和回滚；
  - 结果 JSON 只返回状态、生成的身份和安全计数，不回显任务目标。
- 正式任务固定标记为 `source=agent-deck`、`created_by=agent-deck-user`、`status=planned`、`current_step=等待主控 Agent 规划`。
- `agent-deck/read-model/v1` 现能安全展示 `planned` 状态，并只为上述严格来源的任务投影 `planning_state_zh`；不投影摘要、证据、产物、路径、模型输出或内部 Agent 名称。
- React 任务卡显示“等待主控 Agent 规划”，且仍然没有“启动主控 Agent”、执行、批准、取消或命令桥接入口。

## 3. 明确没有做什么

- 没有把网页草案直接变成账本写入；网页仍是只读工作台和浏览器会话草案。桌面 IPC/服务桥接需要独立设计。
- 没有启动 Pi、OMP 或任何其他 Agent；没有将固定 Pi print 伪装成结构化主控规划。
- 没有创建协作计划、work item、链路、证据、批准或最终决定，也没有改变既有 Pi/OMP 执行权限。
- 没有新增通用 shell、任意 argv/cwd/env、网络 adapter、长期服务、数据库、重试、并发或自治循环。

这避免了把“目标进入收件箱”错误扩大为“目标已获执行授权”。

## 4. 验收结果

- 新增 Python 单元与 CLI 回归覆盖：预览不写入、正式 A+B 写入、自动编号、安全扫描失败关闭、CLI JSON 不回显自由文本；
- 新增 read model / React 回归覆盖：已登记任务显示等待规划状态，且无启动入口；
- `python -m pytest tests -q` 通过；受控写入回归、doctor、public scan、文档检查、前端测试/typecheck/build 均通过；
- 对真实仓库执行了 `agent-deck mission submit --dry-run`：只验证固定收件箱预览，不写入任务、事件或执行审计，也不启动 Pi/OMP。

## 5. 下一候选

阶段 97 应独立设计 **受限主控 Agent 规划提议**：从已登记且等待规划的任务读取固定安全字段，调用一个受审计、结构化、无工具的规划 adapter，写入可验证的 plan proposal，并在进入现有 Pi→OMP→Pi 链路前保留明确的人类确认。该阶段不得从浏览器直接执行，也不得复用自由文本输出作为未校验控制面事实。
