<!-- parents: 47-orchestration-hub-vision.md, 124-stage76-manual-collaboration-board.md -->

# 125 - Stage 77 中文优先界面与人工计划编辑器

> 状态：已实现并通过本地验证
> 日期：2026-07-26

## 产品原则

用户实际看见、点击或操作的 UI/UX MUST 默认使用简体中文。

- 常规标题、按钮、状态、提示、表头、空状态、错误说明和辅助文字必须使用中文。
- Agent 名称、Socket ID、schema、API、ACP、CLI、read model 等专业术语可以保留原文。
- 保留专业术语时，必须紧邻中文名称或中文解释；不得把整段裸英文界面交给用户自行理解。
- 后台服务、代码、协议、日志、JSON 字段、CLI machine output 和其他不可见机器接口可默认使用英文，不要求强制中文化。
- 底层机器契约和内容哈希不因界面翻译而改变。
- `lang=zh-CN` 只是文档语言声明，不能代替真实中文化。

## Stage 77 范围

### 中文默认展示

Control Panel 的用户可见 HTML 默认使用中文，包括：

- 页面标题、导航、概要指标和区段标题；
- 表格标题、列名、空状态和布尔值；
- 状态、角色、事件、操作和审阅结果；
- 边界提示、错误区域、搜索计数和页脚；
- 人工协作看板的泳道、时间线和操作区。

技术 ID 保持原样，并通过中文标签说明其用途。

### 人工计划编辑器

页面提供浏览器内存中的人工计划草稿编辑器：

- 修改父任务引用；
- 添加、删除和编辑工作项；
- 从当前投影中选择 Agent 插座（Agent Socket）；
- 填写依赖、预期产物和是否需要审阅；
- 生成中文草稿预览和 JSON 草稿；
- 明确标记为“待人工确认、不可派发”。

编辑器 NEVER 写入磁盘、访问网络、调用 Agent、修改 ledger 或授予执行权限。刷新页面后草稿消失。

## 验收标准

- HTML 保持 `lang=zh-CN`。
- 核心用户路径不再以裸英文标题或按钮为主文案。
- `planner`、`reviewer`、状态码、事件码和操作码都有中文显示或中文解释。
- `Agent`、`Socket ID` 等保留术语旁有中文注释。
- 人工编辑器生成的内容明确为浏览器内存草稿和待确认状态。
- 自动测试覆盖中文核心文案、术语注释、编辑器非执行边界和既有确定性。

## 不在本阶段

- 保存计划到项目文件；
- 系统自动拆分任务；
- 调用真实 Agent；
- 开始、取消、重试或审阅真实协作运行；
- ACP session probe 或 dispatch authority；
- 持久化消息、产物或协作时间线。

## 下一阶段断点：Stage 78

下一产品里程碑是“人工计划草稿确认与受控导出”。

### 目标

1. 把浏览器内存草稿转换为符合现有 collaboration plan 契约的候选 JSON；
2. 在界面内显示结构校验、依赖校验、Agent 插座绑定和审阅要求结果；
3. 增加明确的人工确认步骤，区分“编辑中”“校验通过”“已人工确认”；
4. 支持用户主动复制或下载候选 JSON，文件名和内容均可预览；
5. 导出后仍固定 `dispatch_eligible=false`、`execution=not_executed`。

### 硬边界

- NEVER 自动写入项目计划文件或 ledger；
- NEVER 调用 Agent、启动 ACP session、探测 readiness 或消耗模型额度；
- NEVER 把“校验通过”解释为“允许派发”；
- 导出和复制必须由用户在中文 UI 中明确触发；
- 后台校验器、schema 和机器字段可以保持英文。

### 恢复顺序

先读本文件，再检查：

```text
python -m agent_runtime.cli doctor
python -m pytest tests/test_orchestration_control_panel.py tests/test_orchestration_control_panel_collaboration.py -q
```

然后从 `_manual_board_section_body`、`_JS` 与现有 `inspect_collaboration_plan` 契约继续，不修改 execution、readiness 或 dispatch authority 模块。
