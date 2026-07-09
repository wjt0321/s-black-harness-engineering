# 2026-07-07 新会话恢复入口 — Orchestration Hub 后端主线

> 本文件供明天新开会话时直接恢复 `s-black harness engineering` 项目使用。当前项目根目录：仓库 checkout 根目录。GitHub 仓库：`https://github.com/wjt0321/s-black-harness-engineering`。

## 这一轮已经完成什么

本轮没有继续深挖新功能，而是把项目主线从“门禁 / 受控写入 Runtime”正式校正为“中枢运行台（Orchestration Hub / Control Plane）后端”。

已经落地：

- `README.md` / `README.en.md`
  - 已补项目全景图
  - 已补总体进度条与阶段进度
  - 已明确项目不只是 guardrail，而是中枢台后端
- `docs/02-roadmap.md`
  - 已细化为更长线、更细颗粒度的路线图
  - 已拆成安全内核与中枢台后端双主线
  - 已明确 Stage 13 暂缓，不急着展开
- `docs/47-orchestration-hub-vision.md`
  - 明确项目定位：中枢运行台，而不只是门禁
  - 明确五层结构
  - 新增“积木式可插拔原则”
- `docs/48-adapter-runtime-interface.md`
  - 明确工具接入必须优先走积木式 adapter
- `docs/49-capability-routing-model.md`
  - 明确 capability 优先于工具名
- `docs/50-control-plane-state-model.md`
  - 明确 task / event / run / approval / artifact / evidence / report
- `tasks/handoff-2026-07-07-orchestration-hub-docs.md`
  - 已写本轮衔接逻辑

## 当前最重要结论

这个项目当前最准确的理解是：

> guardrail / ledger / controlled write 已经形成了一个相对成型的安全内核；接下来主线要补的是“中枢台本身”的后端抽象，而不是继续把项目叙事压缩成门禁工具。

## 明天开新会话时，不要丢的三个意图

### 1. 积木式可插拔

用户明确要求：未来扩展必须能像“插积木”一样接进来，而不是每来一个工具就重写主流程。

这意味着：

- adapter 要保持可插拔
- capability 要尽量稳定
- 上层 workflow 不能写死某个 runner / 脚本 / 平台
- 未来 UI 也应消费同一套 control plane 抽象

### 2. guardrail 仍可继续做，但不阻塞主线

用户明确接受：

- guardrail 还没做完没关系
- 可以边做边发现边回补
- 也可以在某个阶段结束后再统一补一轮

因此：

> guardrail 是长期内核，允许继续增强，但不是“全部做完才能继续下一步”的前置阻塞项。

### 3. 51 先留上下文，不着急展开

当前已经明确：

- `51 — Backend-first API Boundary` 是后续节点
- 但下一会话不必急着从 51 开始深挖
- 应该优先看当前 47-50 这组文档是否还需要再收紧、排序或补前后关系

## 明天建议从哪里恢复

建议恢复顺序：

1. `README.md`
2. `docs/02-roadmap.md`
3. `docs/47-orchestration-hub-vision.md`
4. `docs/48-adapter-runtime-interface.md`
5. `docs/49-capability-routing-model.md`
6. `docs/50-control-plane-state-model.md`
7. `tasks/handoff-2026-07-07-orchestration-hub-docs.md`

如果只读一份恢复全局语境，优先读：

- `tasks/handoff-2026-07-07-orchestration-hub-docs.md`

## 明天最自然的下一步

明天不建议立刻开新功能实现。

更自然的方向是二选一：

### 方向 A：继续把 47-50 这组文档打磨到更顺手执行

例如：

- 补文档之间的编号衔接
- 明确 48 / 49 / 50 的输入输出关系
- 增加更清晰的“从 task intent 到 adapter run”的样例链路
- 再把 README / docs 索引做轻微校正

### 方向 B：在不急着做 51 的前提下，先规划 Stage 14 的最小编排闭环长什么样

也就是：

- 不立刻写 API 边界
- 先定义一个最小 orchestration 闭环，用来承接前面 47-50 的抽象

## 不建议明天直接做什么

- 不建议马上做 UI
- 不建议马上服务化
- 不建议一头扎回单点 guardrail 细节
- 不建议直接跳到大量 adapter 实现
- 不建议现在就大整理 `tasks/progress.md`（已约定留到后面统一整理）

## 当前远端状态（供新会话心里有数）

最近关键提交链：

- `289b071 Add project progress bar to README`
- `dc21219 Refine pluggable orchestration hub docs`
- `dc4b8f1 Document orchestration hub backend vision`
- `521ef26 Simplify README and add docs index`
- `3cdbf33 Add runtime event import strict freeze mode`

README 当前已经是最适合“快速定位项目位置”的入口页。

## 明天可直接对我说的话

你明天新会话可以直接这样开：

> 继续当前仓库，从 `tasks/handoff-2026-07-07-next-session-entry.md` 恢复。先沿着 47-50 这组中枢台后端文档继续，不着急做 51，也不要先跳 UI。优先保持积木式可插拔和 guardrail 不阻塞主线这两个原则。
