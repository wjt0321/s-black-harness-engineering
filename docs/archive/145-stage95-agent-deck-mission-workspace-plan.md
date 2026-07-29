# 阶段 95 Agent Deck 任务工作区实施计划

> 用户已授权自主实施、测试、提交和推送；本计划只实施已批准的安全任务工作区切片。

## 1. 后端安全投影（测试先行）

- 在 `tests/test_agent_deck_projection.py` 增加失败测试：真实任务被投影为有界 `task_queue`；安全标题可显示；secret 命中或超长标题被隐藏；摘要、证据和路径不进入 snapshot。
- 在 `agent_runtime/agent_deck_projection.py` 使用既有 `load_tasks` 和 `check_text` 实现有界、安全的 `task_queue`，保持 schema 版本与 read-only guarantees。
- 扩展 fixture 和 TypeScript 类型以接受可选 `task_queue`。

## 2. 前台任务工作区（测试先行）

- 在 `frontend/src/components/task-composer.test.tsx` 先断言：生成草案显示 Pi→OMP→Pi 的待派发建议，session draft 仍不触发 dispatch。
- 新增 `frontend/src/components/task-workspace.tsx` 及测试：展示当前草案和 snapshot 任务队列；任务状态按后端标签展示；不渲染执行或批准入口。
- 修改 `TaskComposer`、`App.tsx`、fixture 和类型定义连接任务工作区。

## 3. 运行时与构建验收

- 导出真实 Agent Deck snapshot；断言其中 `task_queue` 有界、`ui_dispatch=false`，并通过 Vite 生产构建验证 runtime handoff 被复制。
- 执行 Python 全量/受控写入回归、doctor、public scan、diff/pre-commit；执行前端测试、typecheck、build。

## 4. 文档与交付

- 新建阶段 95 事实源，更新 digest/index/roadmap/README，明确这是“草案 + 真实任务投影”，不是自由执行或自治主 Agent。
- 记录实际验证结果；提交并推送 `main`。
