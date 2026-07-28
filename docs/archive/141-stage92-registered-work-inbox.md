# 141 — 阶段 92：已登记工作收件箱（已验收）

> 状态：已完成真实 Pi/OMP GUI 验收并归档。自动化测试、受控写入回归、`doctor`、公开扫描和文档检查均通过；不能以 fixture、mock 或自动化测试替代的真实验收已由操作者完成。

## 目标

将阶段 91 的单一固定验收预设升级为只读、已登记的工作收件箱。操作者在 GUI 中只看中文工作卡并选择一项，再做一次启动确认；不填写链路 ID、任务 ID、协作计划路径或目标文本。Harness 自动生成链路 ID，并继续执行既有的有限自动串行与最终人工决定。

## 冻结边界

- 工作卡只从固定项目路径 `adapters/control-panel-registered-work-inbox.json` 读取；不接受 CLI、GUI 或 API 指定的路径、argv、cwd、env、网络地址或自由提示词。
- 收件箱严格限制为 1–20 张卡；每张卡字段精确匹配、长度有界，固定绑定既有任务、`adapters/` 下的协作计划、受扫描的有界目标和两种 Pi/OMP 交替拓扑之一。
- GUI 只显示卡片 ID、中文标题、中文安全摘要、任务 ID、角色拓扑和目标摘要；不展示原始目标、计划、执行文本、产物或凭据。
- 选择工作卡是启动前的业务范围选择；启动和最终决定仍各有一次性绑定确认。启动前和确认提交前都会只读预检该卡涉及的全部 Pi/OMP 宿主；任一宿主未处于已打开、空闲且证据有效状态时，不启动链路。中间三轮保持自动串行，任何失败、漂移或“要求修改”都停止。
- 不新增真实 operation、CLI 执行参数、审计 writer、账本 writer、服务、数据库、并行、自动重试、自动批准、取消、恢复或新宿主。

## 已登记配置

当前仅登记两张阶段 92 验收卡：

1. `acceptance-forward`：`Pi → OMP → Pi`；
2. `acceptance-reverse`：`OMP → Pi → OMP`。

两张卡都绑定既有 `task-20260703-001`，并引用项目内受校验的协作计划。它们是受控验收配置，不构成通用任务创建入口。

## 实现入口

- `agent_runtime/orchestration_control_panel_registered_work.py` — 固定路径只读收件箱、严格结构校验与安全投影。
- `agent_runtime/control_panel_live_gui.py` — 已登记工作表格、只允许启动选中工作、自动链路 ID、全角色只读预检、前台可刷新执行进度和既有最终决定自动路由。
- `adapters/control-panel-registered-work-inbox.json` — 两张受控工作卡。
- `adapters/collaboration-plan.stage92-forward.json` 与 `adapters/collaboration-plan.stage92-reverse.json` — 两种固定拓扑协作计划。
- `tests/test_orchestration_control_panel_registered_work.py` — 固定路径、严格字段、路径逃逸失败关闭及项目卡片—计划绑定。

## 自动验收

- 固定收件箱仅释放安全字段，原始 `goal` 不出现在安全投影。
- 额外字段、路径逃逸、错误拓扑、重复 card ID 或无效文本都会返回稳定 `control-panel-registered-work-invalid`，并且 GUI 不显示或启动工作。
- 项目内两张卡都能通过既有协作计划校验，且任务引用精确匹配。
- 由 GUI 构造的启动信封仅来自选中、已校验的卡片；操作者不提供内部标识符。
- 确认提交在单一后台任务中等待既有受控操作，GUI 主线程继续刷新；执行期间禁用重复启动与最终决定，并阻止关闭主窗口，既不并行、不重试，也不改变既有链路的审计语义。
- 启动卡在预览前和确认提交后都读取卡片拓扑中的全部唯一宿主；任何一个状态证据不满足既有可派发条件，都会在未写入链路或未执行下一轮前失败关闭。

## 真实 Pi/OMP GUI 验收

操作者实际打开无工具、空闲 Pi 与 OMP，在 GUI 中没有填写链路 ID、任务 ID、计划路径或目标文本。

- **正向**：选择 `acceptance-forward` 后，`Pi → OMP → Pi` 三轮真实 attempt 都成功，GUI 自动弹出最终决定；操作者选择“通过”，链路终态为 `approved`，无 lease。
- **反向**：选择 `acceptance-reverse` 后，`OMP → Pi → OMP` 三轮真实 attempt 都成功，GUI 自动弹出最终决定；操作者选择“通过”，链路终态为 `approved`，无 lease。
- 反向验收中曾观察到两种 fail-closed 行为：Pi 状态证据未就绪时在执行前停止；OMP 返回邮箱不符合固定协议时在审阅前停止。两者均没有继续派发或遗留 lease。随后 GUI 在预览与提交前补齐全角色只读预检，邮箱读取将结构/稳定性错误与请求/宿主身份漂移分为不泄露原文的安全 failure code；最终反向真实链路通过。
- 提交确认页在单一后台任务中等待既有受控 operation，主窗口继续刷新并显示进度；执行期间禁止第二次操作和关闭窗口。真实观察确认不会冻结。

新 CLI 进程已只读确认两条通过链路均具备规划候选、执行产物、审阅建议、最终决定和可恢复的终态；反向最终三轮对应 audit 为 `attempt-20260728-053`、`attempt-20260728-055`、`attempt-20260728-057`，每轮均有唯一 started 与 succeeded 事件。

本阶段完成后，后续能力必须另行授权。
