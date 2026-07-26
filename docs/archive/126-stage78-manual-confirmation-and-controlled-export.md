<!-- parents: 47-orchestration-hub-vision.md, archive/125-stage77-chinese-first-interface-and-manual-editor.md -->

# 126 - Stage 78 人工确认与受控导出

> 状态：已实现并通过本地验证
> 日期：2026-07-26

## 产品结果

Control Panel 的人工计划编辑器现在可以把浏览器内存草稿转换为符合现有 `control-plane/collaboration-plan/v1` 契约的候选 JSON，并在用户主动导出前完成本地校验和明确的人工确认。

Stage 78 没有新增执行权限。校验通过、人工确认、复制和下载均固定：

- `dispatch_eligible=false`；
- `execution=not_executed`；
- 不调用 Agent；
- 不启动 ACP session 或 readiness probe；
- 不访问网络；
- 不写项目文件或 ledger；
- 不消耗模型额度。

浏览器下载是用户在中文界面中明确触发的客户端操作，不是项目受控写入链。

## 候选计划契约

导出的 JSON 只包含既有 collaboration plan v1 顶层字段：

- `parent_task_ref`；
- `revision`；
- `socket_bindings`；
- `work_items`；
- `handoffs`；
- `review_gates`。

`task_title` 只用于界面说明和安全文件名生成，不进入既有机器契约。确认状态、派发资格和执行状态也不写入候选 JSON，避免污染既有 schema 或把 UI 确认误解释为派发授权。

## 校验范围

界面内固定展示四组结果：

1. 结构校验：标题、父任务、工作项 ID、预期产物和支持的产物类型；
2. 依赖校验：已知依赖、自依赖和循环依赖；
3. Agent 插座绑定校验：选中插座必须携带当前投影中的角色绑定，同一插座不能出现冲突角色；
4. 审阅要求校验：所有 `review_required=true` 工作项必须生成审阅门。

候选自动从依赖关系生成 handoff，并从审阅要求生成 review gate。任何编辑都会撤销之前的校验和人工确认。

## 状态机

浏览器内状态固定为：

```text
editing -> validated -> operator_confirmed
   ^             |               |
   +-------------+---------------+
        任意内容修改后回退
```

对应中文状态：

- 编辑中 · 不可派发；
- 校验通过 · 等待人工确认；
- 已人工确认 · 仅可导出。

复制和下载按钮只有在 `operator_confirmed` 状态启用。下载前显示确定性安全文件名和完整候选内容。

## 实现位置

- `agent_runtime/orchestration_control_panel.py`：中文 UI、候选生成、校验、确认、复制和下载；
- `tests/test_orchestration_control_panel.py`：Stage 78 HTML/JS 边界和空依赖输入回归；
- `tests/test_orchestration_control_panel_collaboration.py`：既有 collaboration plan 投影兼容性。

没有修改 execution、readiness、dispatch authority、ledger 或 controlled-write 模块。

## 浏览器验证路径

本地静态页面验证覆盖：

1. 初始状态不可确认、不可复制、不可下载；
2. 合法 fixture 校验后进入 `validated`；
3. 人工确认后允许下载；
4. 下载 JSON 与预览完全一致，且只有 collaboration plan v1 字段；
5. 修改任意输入后撤销确认并重新禁用导出；
6. 未知依赖校验失败并阻止确认；
7. 页面只产生本地 `file://` 请求。

## 验证结果

提交前实际通过：

- `python -m pytest tests/test_orchestration_control_panel.py tests/test_orchestration_control_panel_collaboration.py -q`；
- `python -m pytest tests -q`（保留环境相关预期 skip）；
- `python -m agent_runtime.cli doctor`；
- `python tools/public_scan.py` 的同等项目根 `PYTHONPATH` 调用；
- `python -m agent_runtime.cli docs context --json`；
- 活跃 Markdown 相对链接审计和 `docs/` 活跃文档计数；
- `bash .githooks/pre-commit`；
- `git diff --check`；
- 本机 Microsoft Edge 静态页面交互验证；
- 下载候选再次通过 `orchestration collaboration inspect`。

## 下一阶段断点：Stage 79

下一产品里程碑是“协作运行状态模型设计”。先冻结真实协作未来需要的状态与事件：开始、取消、重试、审阅、交接、阻塞恢复和 artifact 回收。

Stage 79 仍是设计/只读模型阶段：

- NEVER 调用 Agent；
- NEVER 启动 ACP session 或 readiness probe；
- NEVER 新增真实 operation；
- NEVER 把已人工确认的计划解释为派发授权；
- 只有状态、审批、取消和产物回收契约完整后，才考虑恢复探针或单 work-item 真实派发设计。
