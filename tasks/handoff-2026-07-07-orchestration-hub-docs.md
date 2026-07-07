# 2026-07-07 中枢台文档主线接续上下文

> 本文件供新会话恢复 `s-black harness engineering` 项目使用。当前项目根目录：仓库 checkout 根目录。GitHub 仓库：`https://github.com/wjt0321/s-black-harness-engineering`。

## 本轮目标

本轮目标不是继续深挖局部功能，而是把项目从“门禁 / 受控写入 Runtime”重新校正为“中枢运行台（Orchestration Hub / Control Plane）”叙事，并把这一层落盘到正式文档。

## 本轮已完成

### README 与入口层

- README 已补全项目全景图（中文 / 英文）。
- README 已明确：
  - 门禁 / ledger / controlled write 是安全内核
  - 统一接入 / capability routing / control-plane state / future UI 才是更大的中枢台主体
- 推荐阅读路径已更新，加入：
  - `docs/02-roadmap.md`
  - `docs/47-orchestration-hub-vision.md`
  - `docs/48-adapter-runtime-interface.md`
  - `docs/49-capability-routing-model.md`
  - `docs/50-control-plane-state-model.md`

### Roadmap 细化

- `docs/02-roadmap.md` 已从早期粗粒度阶段说明，升级成更细的双主线路线图：
  - 安全与审计内核
  - 中枢台接入与编排
- 已明确 Stage 0 ~ Stage 8 的历史阶段定位。
- 已新增 Stage 9 ~ Stage 16 的中枢台后端主线规划。

### 新增文档

- `docs/47-orchestration-hub-vision.md`
  - 定义项目不是单纯 guardrail，而是中枢运行台
  - 明确五层结构：接入层 / 编排层 / 状态层 / 安全与审计内核 / 观察层
- `docs/48-adapter-runtime-interface.md`
  - 定义 adapter 分类、统一 metadata、request / response / artifact / evidence / error / approval 语义
- `docs/49-capability-routing-model.md`
  - 定义 capability 优先于工具名的路由模型
  - 定义 capability match / constraint filter / preference rank 三层路由过程
- `docs/50-control-plane-state-model.md`
  - 定义 task / event / run / approval / artifact / evidence / report 七类控制面状态对象

## 本轮未做

- 未继续深挖新的 CLI 功能
- 未继续扩大受控写入面
- 未做 UI 页面
- 未做 HTTP / 服务化 API
- 未整理 `tasks/progress.md`（用户明确要求留到最后统一整理）

## 当前判断

当前项目最重要的阶段性变化是：

> 仓库已经把“中枢台的安全内核”打牢，现在开始补“中枢台本身”的后端抽象。

也就是说，后续实现优先级不应再只是新增局部门禁能力，而应转向：

1. 工具如何被统一接进来
2. capability 如何路由到 agent / tool adapter
3. 控制面到底记录哪些状态对象
4. 即使现在没有 UI，后端如何按未来 UI 可操作的方式组织

## 建议下一步

当前**不急着进入实现或深挖**：

```text
51 — Backend-first API Boundary
```

但需要把它作为明确的后续节点保留下来。

建议目标（暂存上下文，不立刻展开）：

- 定义未来 UI / CLI / automation 共同依赖的后端接口边界
- 不急着选 HTTP / RPC / 本地进程协议
- 先定义资源模型和操作模型

后续至少应覆盖：

- task list / task detail
- run list / run detail
- approval list / resolve
- artifact list / inspect
- report list / inspect
- dry-run / commit action boundary
- routing preview / adapter selection preview

## Guardrail / 门禁主线说明

门禁内核仍然重要，而且允许继续补完；但它不再作为当前阶段的唯一主线，也不作为“做完才能继续”的阻塞项。

后续策略：

- 可以在每一阶段结束后回看一次：本阶段暴露了哪些新的 guardrail 缺口。
- 也可以在中途边做边发现，再把缺口回写到 roadmap / handoff / docs。
- 如果某个新 adapter / capability / state model 需要额外 guardrail 支撑，可以立即补一个局部节点，而不是等全盘门禁一次性完工。

换句话说：

> guardrail 是长期内核，跟着中枢台一起长；不是现在必须一次性收尾的前置阻塞项。

## 与前文衔接

当前这组文档的关系是：

```text
47 -> 为什么这项目是中枢台
48 -> 工具如何统一接进来
49 -> 能力如何路由
50 -> 控制面记录哪些状态
51 -> 未来 UI / CLI / automation 如何操作后端
```

所以 51 应该顺着 47-50 往下接，不应重新回到单点功能开发。

## 收尾检查

本轮收尾前应确认：

- `python tools/public_scan.py`
- `python -m pytest tests/test_public_scan.py -q`
- `git diff --check`
- 提交中不混入无关文件
- push 成功后回看 CI

## 提示

- 用户明确认可：当前方向就是他想要的“中枢台后端”主线。
- 用户明确要求：README 里应有全景图，roadmap 要更细。
- 用户明确要求：先把当前讨论内容落地到文档，并留下下一步上下文和前后衔接，再 push。
