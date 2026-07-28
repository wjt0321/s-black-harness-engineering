# 140 — 阶段 91：GUI 结构化审批收件箱（已完成并归档）

> 状态：实现、自动验证与真实 Pi/OMP GUI 验收均已完成；fixture、mock 或自动化测试没有替代该验收。
>
> 基线：`ee991ed`（阶段 90 已推送；阶段 91 变更待提交）
>
> 日期：2026-07-28

## 目标

在既有阶段 89 的有限链路之上，让中文前台窗口承载两次且仅两次操作者决定：

1. 对唯一已登记、固定且有界的链路提交一次启动确认；
2. 在三个既有串行角色轮次结束后，对同一链路提交最终“通过”或“要求修改”。

中间的规划者 → 执行者 → 审阅者仍由既有受控链路自动串行完成。该阶段不把“预览”解释成执行权，也不把 GUI 变成通用命令终端。

## 冻结边界

- GUI 只能构造 `control-panel-approval/v1` 的两种精确 JSON 信封：`start_chain` 与 `final_decision`；字段集合、版本和 operation 均精确匹配，未知、缺失、类型错误或额外字段一律失败关闭。
- 启动按钮不向操作者索取链路 ID、任务 ID、协作计划文件或目标；它只装配唯一已登记的阶段 91 验收计划（固定任务、固定 `Pi → OMP → Pi` 拓扑和固定有界目标），并自动生成安全链路 ID。最终决定页也只让操作者选择“通过 / 要求修改”，意见使用固定安全文本。
- 两种信封仅转发给既有 `preview_chain_start` / `execute_chain_start` 和 `preview_chain_final_decision` / `commit_chain_final_decision`。不新增真实 operation、CLI 执行入口、ledger writer、审计 writer 或宿主协议。
- 每次 GUI 操作均先取得既有一次性确认摘要，再由操作者点击第二次确认。提交时继续依赖既有 binding 重预览、漂移检测、lease、started/terminal audit、不可变证据和最终审阅记录。
- 窗口确认页只展示 operation、链路 ID、计划摘要、一次性绑定摘要及既有安全摘要；不复制原始目标、原始计划、未扫描输出、凭据或任意项目文件内容。
- 启动后的三个角色轮次保持前台同步、最多三次、严格串行。没有后台服务、监听端口、并行、自动重试、自动批准、取消、恢复、宿主启动/关闭或任意 argv/cwd/env。
- `control-panel live --json` 继续是只读确定性快照；GUI 操作没有新增 CLI 参数或 JSON 执行通道。

## 设计问题与取舍

### 为什么不在 GUI 重写执行链

Stage 89 已有完整的确认绑定、实时状态门、受控写入、事件审计、失败 `stop` 与证据恢复语义。GUI 新建执行路径会产生第二个 writer，容易破坏这些不变量。因此窗口只是一个严格的已登记请求适配层；实际写入仍只通过已验收的固定编排。链路 ID、任务、协作计划和验收目标都不是操作者输入。

### 为什么最终决定仍必须单独确认

三个角色的完成回执只携带审阅建议，不是业务批准。最终决定继续精确绑定阶段 88 审阅记录；若状态、证据或绑定发生漂移，既有 commit 失败关闭，而不会重新调用 Pi/OMP。

### 为什么不添加“自动继续”或“重试”按钮

“要求修改”、任何角色失败、状态过期、证据待恢复和确认漂移都会停止当前链路。新一次执行仍需要新的启动确认；恢复也只能使用既有只读恢复路径，不能从窗口重新派发。

## 实现入口

- `agent_runtime/control_panel_live_gui.py` — 前台中文窗口、无标识符输入的已登记启动按钮、最终结论选择、双重确认与安全摘要渲染。
- `agent_runtime/orchestration_control_panel_approval.py` — 严格信封校验及向既有阶段 89 operation 的唯一转发。
- `tests/test_orchestration_control_panel_approval.py` — 精确字段、错误类型、未知字段、一次性 binding 与无调用失败关闭。
- `adapters/collaboration-plan.stage91-gui-acceptance.json` — 唯一已登记的阶段 91 验收协作计划。
- `tests/test_control_panel_live_gui.py` — 固定信封构造、自动链路标识和不泄露原始目标的确认摘要。

## 自动验收

- start 和 final 两种 GUI 信封分别到达既有 preview / commit operation，且 `commit=True` 与一次性 binding 原样受控传递。
- 额外字段、不完整字段、错误类型及不可哈希 decision 都返回稳定 `control-panel-approval-command-invalid`，不调用底层链路。
- 确认摘要包含绑定哈希和安全摘要，但不包含 `intent_template.goal` 的原文。
- 回归继续覆盖 `control-panel live --json`、控制面边界和既有链路契约。

## 真实 Pi/OMP GUI 验收

2026-07-28，操作者实际打开无工具、空闲的 Pi 与 OMP，并在前台 GUI 完成了唯一已登记的正向链路：

1. 只点击“启动已登记链路”，在一次性摘要页确认；没有填写链路 ID、任务 ID、协作计划路径或目标。GUI 自动生成 `chain-20260728-gui-forward-075109735`，并装配固定 `Pi → OMP → Pi` 验收计划。
2. 三次真实单工作项派发自动串行完成：Pi 规划 `attempt-20260728-033`、OMP 执行 `attempt-20260728-035`、Pi 审阅 `attempt-20260728-037`；每次均有 started/terminal audit，终态均为成功且进程树活动数为零。
3. 链路自动进入 `awaiting_final_human_decision` 后，GUI 自动弹出最终决定页；操作者只选择“通过”，再确认一次性摘要。最终链路状态为 `approved`，完成记录绑定 `review-c668af0656f407cfa265909789ca8b86c9bfc142c571a579f94cdc2f7aad61b2`。
4. 新 CLI 进程重新读取到 `approved`，不可变规划候选、执行收据、审阅建议和完成记录均存在；`.runtime/` 下没有 lease 文件。

验收期间曾发现秒级截断的评估时间会将带毫秒的宿主快照误判为未来观察，导致一个未派发角色的链路停止。修正为毫秒级评估时间后，以新的自动生成链路完成上述真实验收；该失败链路没有被重试或复用。

本文件现为已验收事实源，应移动到 `docs/archive/`。
