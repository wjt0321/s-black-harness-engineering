# Stage 78 人工确认与受控导出 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将浏览器内存人工计划转换为符合现有 collaboration plan v1 契约的候选 JSON，经过本地校验和显式人工确认后允许用户复制或下载，同时继续固定为不可派发、未执行。

**Architecture:** 保持 Control Panel 为单文件静态 HTML，不增加服务、网络调用或磁盘写 API。在 `_manual_board_section_body` 中嵌入当前计划的 Agent 插座/角色元数据，在 `_JS` 中实现浏览器内状态机与契约校验；导出的 JSON 只包含现有 collaboration plan v1 字段，`dispatch_eligible=false` 与 `execution=not_executed` 作为不可变 UI 边界展示，不污染既有计划 schema。

**Tech Stack:** Python 3.11、标准库 HTML/JSON 渲染、原生浏览器 JavaScript、pytest。

---

## 方案选择

1. **选择：纯浏览器状态机与用户触发导出。** 满足静态、无网络、无服务、无项目写入边界，改动集中在现有 Control Panel。
2. **拒绝：增加本地 API 或临时计划文件。** 会引入服务或受控写入语义，超出 Stage 78。
3. **拒绝：修改 collaboration plan v1 增加确认/派发字段。** 会污染既有机器契约并错误耦合计划校验与派发权限。

### Task 1: 冻结 Stage 78 HTML/JS 合同

**Files:**
- Modify: `tests/test_orchestration_control_panel.py`
- Modify: `tests/test_orchestration_control_panel_collaboration.py`

1. 增加失败测试，要求存在编辑中、校验通过、已人工确认三种中文状态。
2. 要求确认、复制、下载按钮及文件名/内容预览。
3. 要求候选 JSON 使用 collaboration plan v1 顶层字段，并生成 socket bindings、handoffs、review gates。
4. 要求编辑后撤销确认，复制/下载仅在人工确认后启用。
5. 要求无 `fetch`、`XMLHttpRequest`、Agent 调用或项目写入 API。
6. 运行专项测试确认先失败。

### Task 2: 实现候选生成、校验和状态机

**Files:**
- Modify: `agent_runtime/orchestration_control_panel.py`

1. 在选择项中绑定 socket role 元数据。
2. 生成严格 collaboration plan v1 候选：`parent_task_ref`、`revision`、`socket_bindings`、`work_items`、`handoffs`、`review_gates`。
3. 校验标题/父任务、ID 唯一性、socket 绑定、依赖引用与循环、artifact 白名单、review gate 覆盖。
4. 实现 `editing -> validated -> operator_confirmed` 状态；任何编辑回退到 `editing`。
5. 人工确认后启用复制与下载；复制使用 Clipboard API 并提供本地 fallback，下载使用用户触发的 Blob URL。
6. 始终展示 `dispatch_eligible=false`、`execution=not_executed`，不把它们加入 collaboration plan v1 JSON。
7. 运行专项测试确认通过。

### Task 3: 更新当前事实源和入口

**Files:**
- Create: `docs/126-stage78-manual-confirmation-and-controlled-export.md`
- Modify: `docs/000-stage-digest.md`
- Modify: `docs/00-index.md`
- Modify: `docs/02-roadmap.md`
- Modify: `README.md`
- Modify: `README.en.md`
- Modify: `AGENTS.md`
- Archive: `docs/plans/2026-07-26-stage78-controlled-export.md`

1. 记录 Stage 78 已实现范围、验证和硬边界。
2. 将当前基线统一到 Stage 78，清理 Stage 62/75/旧下一步描述。
3. 下一里程碑改为协作运行状态模型设计，仍不调用 Agent。
4. 按文档治理将本实施计划归档。

### Task 4: 完整验证与本地提交

1. 运行 Control Panel 专项测试。
2. 运行 `python -m pytest tests -q`。
3. 运行 `python -m agent_runtime.cli doctor`。
4. 运行 `python tools/public_scan.py`。
5. 运行 docs context、Markdown 相对链接审计、活跃文档计数和 `git diff --check`。
6. 如环境允许运行 `bash .githooks/pre-commit`。
7. 审查 diff 和 Git 状态，确认无 `.runtime` 或凭据内容进入提交。
8. 创建一个本地 Stage 78 提交，不推送。
