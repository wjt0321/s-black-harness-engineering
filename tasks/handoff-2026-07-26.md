# Handoff — Stage 78 人工确认与受控导出

> 日期：2026-07-26
> 状态：实现与本地验证完成；待创建本地提交

## 当前基线

Stage 78 在 Stage 77 浏览器内存编辑器上增加了候选计划校验、显式人工确认、复制和下载。当前页面仍是本地静态 Control Panel，不调用 Agent、不启动 ACP session、不访问网络、不写项目文件或 ledger。

当前事实源：

- `docs/126-stage78-manual-confirmation-and-controlled-export.md`
- `docs/000-stage-digest.md`
- `docs/02-roadmap.md`

## 实现摘要

- 合法草稿转换为现有 `control-plane/collaboration-plan/v1` 候选 JSON；
- 自动生成唯一 socket bindings、依赖 handoffs 和 review gates；
- 展示结构、依赖、Agent 插座绑定和审阅要求四组校验；
- 状态为 `editing -> validated -> operator_confirmed`；
- 任意输入修改会撤销校验和确认；
- 只有人工确认后才能复制或下载；
- 下载文件名和 JSON 内容在操作前可见；
- UI 固定展示 `dispatch_eligible=false`、`execution=not_executed`；
- 这些边界字段不进入 collaboration plan v1 JSON。

## 关键文件

- `agent_runtime/orchestration_control_panel.py`
- `tests/test_orchestration_control_panel.py`
- `docs/126-stage78-manual-confirmation-and-controlled-export.md`

Stage 75-77 事实源已归档到 `docs/archive/123-*.md` 至 `docs/archive/125-*.md`。Stage 71 旧 handoff 保留为 `tasks/handoff-2026-07-26-stage71.md`。

## 浏览器验证

使用本机 Microsoft Edge 打开 CLI 生成的静态 HTML，已覆盖：

- 合法 fixture 校验通过；
- 人工确认后下载启用；
- 下载内容等于预览内容；
- 候选只包含 collaboration plan v1 六个顶层字段；
- 编辑后确认被撤销；
- 未知依赖阻止确认；
- 除本地 `file://` 页面外没有请求。

相关截图与下载样例仅保存在 `.runtime/`，不会提交。

## 收口验证

以下检查已实际通过：

- Control Panel 专项 pytest；
- 全量 pytest（保留环境相关预期 skip）；
- doctor；
- public scan；
- docs context；
- 活跃 Markdown 相对链接审计与文档计数；
- pre-commit；
- diff check；
- Microsoft Edge 静态交互验证；
- 下载候选的 collaboration plan v1 inspect。

## 下一候选

Stage 79：协作运行状态模型设计。先定义开始、取消、重试、审阅、交接、阻塞恢复和 artifact 回收，不调用 Agent，不新增真实 operation。
