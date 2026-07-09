# s-black harness engineering

<p align="center">
  <img src="assets/logo-256.png" alt="s-black harness engineering logo" width="160">
</p>

<p align="center">
  <strong>中文</strong> · <a href="README.en.md">English</a>
</p>

> 一套轻量的 Agent Runtime / Harness Orchestrator，用来沉淀规则门禁、任务账本、Agent 注册表、工具适配器边界和完成验证流程，并逐步演进成多 Agent、多工具、多渠道的中枢运行台。

## 这个项目是什么

`s-black harness engineering` 是一个 Agent 工程基础设施项目。

它的目标不是替代聊天宿主，也不是先做 UI，而是先把 Agent 做事时最容易失控、最需要统一控制的部分单独抽出来：

- 规则检查
- 任务账本
- Agent 注册表
- 工具适配器边界
- 完成验证
- 受控写入流程
- 能力路由与中枢编排基础

最终希望形成一层**小型、可审计、可迁移、可插拔扩展**的 Runtime / Control Plane，让 QwenPaw 只是未来可接入的宿主/适配器之一，而不是唯一边界。

## 全景图

```text
用户 / CLI / 飞书 / 未来 UI
  -> Orchestration Hub / Control Plane
  -> Capability Routing
  -> Policy Guardrails / Approval / Completion Checks
  -> Agent & Tool Adapters
       -> QwenPaw
       -> Kimi Code / WebBridge
       -> Claude Code
       -> OMP / pi
       -> Shell
       -> GitHub
       -> Lark
       -> Obsidian
       -> 其他外部系统
  -> Task / Event / Run / Approval / Artifact State
  -> Report / Audit / Observability
```

一句话理解：

- **门禁 / 账本 / 受控写入** 是这个项目的安全内核
- **统一接入 / 能力路由 / 状态控制 / 未来 UI** 才是这个项目最终要长成的中枢台主体

## 当前项目到了哪里

当前仓库已经从“只读检查 CLI”推进到了“最小受控写入 Runtime”，并开始补“中枢台后端”的总蓝图。

## 当前进度条

> 这是一个长期项目，下面的百分比不是“代码量”，而是按**阶段闭环完成度**估算，用来帮助快速判断：现在做到哪、接下来该往哪走。

### 总体进度（主观工程估算）

```text
[███████████████░░░░░░░░░] 约 60%
```

当前判断：

- **安全与审计内核**：约 **80%**
- **中枢台后端抽象**：约 **55%**
- **未来 UI / Control Panel 准备度**：约 **30%**

### 版本号说明

当前仓库最新里程碑基线已经是 `v0.12.0-orchestration-foundation`（commit `38b4b69`，已 push）。

在 `v0.11.0-runtime-event-import` 之后，项目进入 orchestration 主线，实际改用“**阶段编号 + release notes 文档**”做阶段收口，例如 `55`、`57`、`59`、`61`、`65`、`67`。这代表：

- 阶段收口一直在继续；
- semver / tag 不再按每个阶段同步增长；
- 版本治理改为“阶段推进 + release notes 收口 + 里程碑打 tag”。

当前已通过 `docs/64-versioning-governance.md` 正式定义该策略，并已在 `v0.12.0-orchestration-foundation` 完成一次实际冻结：

- 阶段编号继续用于推进顺序；
- release notes 用于单阶段收口；
- semver / Git tag 只用于里程碑级冻结点，不再逐阶段补 tag。

### 阶段闭环进度

- ✅ Stage 0 — 项目骨架
- ✅ Stage 1 — 通用规则模型
- ✅ Stage 2 — 任务账本
- ✅ Stage 3 — Agent 注册表
- ✅ Stage 4 — 工具适配器层（第一轮设计）
- ✅ Stage 5 — 最小 Runtime CLI
- ✅ Stage 6 — Runtime 只读检查链路
- ✅ Stage 7 — 受控写入基础
- ✅ Stage 8 — Runtime Event Import 能力包（v0.11）
- ✅ Stage 9 — 中枢台定位校正与总蓝图
- 🟡 Stage 10 — Adapter Runtime Interface（文档已起，后续待继续细化）
- 🟡 Stage 11 — Capability Routing Model（文档已起，后续待继续细化）
- 🟡 Stage 12 — Control Plane State Model（文档已起，后续待继续细化）
- 🟡 Stage 13 — Backend-first API Boundary（设计文档已落地，协议选择仍暂缓）
- 🟡 Stage 14 — 中枢台最小编排闭环（设计文档、命令草案与 run 侧 A+B commit 已落地）
- 🟡 Stage 15 — UI / 看板前的后端准备（read-model CLI 第一版已落地，前端实现仍暂缓）
- 🟡 Stage 15.5 — Orchestration 受控写入边界（第一批 controlled handoff / approval resolve 已落地）
- ✅ Stage 15.7 — Orchestration Run Dry-run 落地
- ✅ Stage 15.8 — Orchestration Run Commit（A-only）落地
- ✅ Stage 15.9 — Orchestration Run Lifecycle Events 落地
- ✅ Stage 15.95 — Orchestration Task Submit Created Event 落地
- ✅ Stage 15.96 — Orchestration Run Retry / Fallback Dry-run 落地
- ✅ Stage 15.97 — Orchestration Foundation Freeze 完成（基线：`38b4b69` / `v0.12.0-orchestration-foundation`）
- ⚪ Stage 16 — UI / Control Panel（远期）

### 现在最明确的位置

可以把当前状态理解成：

- **门禁 / ledger / controlled write 这一层，已经不是草稿，而是一个成型的安全内核**
- **中枢台后端主线，已经完成了方向校正和第一批核心文档**
- **真正的统一接入、路由、控制面操作边界，还没进入实现闭环**

### 接下来的方向

下一步最自然的方向不是继续盲目加功能，而是：

1. 继续把 **Stage 10-12** 这三层后端抽象打细
2. 保留 **Stage 13** 上下文，但暂不急着展开
3. 在 freeze 之后先整理 post-freeze 文档口径与下一拍入口
4. 再决定是否进入 retry / fallback commit 设计等新的 orchestration backend 阶段
5. guardrail 若在新阶段中暴露缺口，再边做边回补

已落地的主线能力包括：

- 结构校验、密钥扫描、路径检查、action preflight
- registry / policy / ledger 查询与校验
- adapter execution envelope 的 plan / validate / inspect / gate check
- `runtime draft export --dry-run / --commit`
- `runtime event append --dry-run / --commit`
- `runtime task create --dry-run / --commit`
- `runtime event import --dry-run / --commit`
- `runtime event import --expected-plan-hash` 一致性冻结
- `runtime event import --require-dry-run` strict freeze mode
- controlled write regression 覆盖
- 中枢台总蓝图、adapter 接口、capability routing、control plane state 文档主线
- Stage 15 read-model CLI：`orchestration overview`、`orchestration task list/get`、`orchestration run list/inspect`、`orchestration approval list/get`、`orchestration artifact list/get`、`orchestration report generate`
- Stage 15.5 controlled handoff：`orchestration route preview`、`orchestration preflight`、受控写入 `orchestration approval resolve`（只记录 decision，不执行原请求）
- Stage 15.7/15.8/15.9 run controlled execution：`orchestration run --dry-run`（只读 plan preview + plan_hash）、受控写入 `orchestration run --commit`（A+B envelope draft export + `run_planned` / `run_draft_exported` lifecycle events，不执行真实 adapter）

## 当前边界

当前 Runtime 仍保持保守边界：

- 不执行真实 adapter
- 不访问网络
- 不发送消息
- 不读取 `.env` / credential / token / keyring
- 不做 UI 或后台服务
- 不静默扩张写权限

已实现的写入也都属于**受控写入**：只允许项目内安全路径、显式命令触发、写前校验、写后校验、失败回滚。

## 快速开始

```bash
python -m agent_runtime.cli doctor
python -m agent_runtime.cli check text --text hello
python -m agent_runtime.cli check path ./docs/06-adapter-layer.md --read
python -m agent_runtime.cli agents list
python -m agent_runtime.cli adapters list
python -m agent_runtime.cli policies list
```

更多 CLI 用法见 `docs/10-cli-poc-usage.md`。

## 推荐阅读

如果你第一次进入这个仓库，建议按这个顺序看：

1. `docs/00-index.md`
2. `docs/01-vision-and-boundaries.md`
3. `docs/02-roadmap.md`
4. `docs/47-orchestration-hub-vision.md`
5. `docs/48-adapter-runtime-interface.md`
6. `docs/49-capability-routing-model.md`
7. `docs/50-control-plane-state-model.md`
8. `docs/51-backend-first-api-boundary.md`
9. `docs/52-minimal-orchestration-loop.md`
10. `docs/53-minimal-orchestration-loop-cli-draft.md`
11. `docs/54-backend-preparation-before-ui.md`
12. `docs/55-release-notes-orchestration-read-models.md`
13. `docs/56-orchestration-controlled-write-boundary.md`
14. `docs/57-release-notes-orchestration-controlled-handoff.md`
15. `docs/58-orchestration-run-controlled-execution-design.md`
16. `docs/59-release-notes-orchestration-run-controlled-execution.md`
17. `docs/60-orchestration-run-lifecycle-events-design.md`
18. `docs/61-release-notes-orchestration-run-lifecycle-events.md`
19. `docs/62-orchestration-task-submit-controlled-write-design.md`
20. `docs/63-orchestration-task-submit-created-event-design.md`
21. `docs/64-versioning-governance.md`
22. `docs/65-release-notes-orchestration-task-submit-created-event.md`
23. `docs/66-orchestration-run-retry-fallback-design.md`
24. `docs/67-release-notes-orchestration-run-retry-fallback.md`
25. `docs/68-orchestration-foundation-milestone-freeze-checklist.md`
26. `docs/69-orchestration-foundation-freeze-execution-plan.md`
27. `docs/10-cli-poc-usage.md`
28. `docs/21-controlled-write-boundaries.md`

其中 `docs/47-orchestration-hub-vision.md` 到 `docs/54-backend-preparation-before-ui.md` 是中枢台后端主线，建议按编号顺序阅读。

如果你只想看完整进度账本：

- `tasks/progress.md`

## 仓库结构

| 路径 | 用途 |
|:---|:---|
| `docs/` | 架构、路线图、协议说明、阶段文档 |
| `policies/` | Policy schema 和样例 policy |
| `agents/` | Agent 注册表 schema 和样例注册表 |
| `adapters/` | 工具适配器设计与相关 schema |
| `tasks/` | 任务账本 schema、样例、进度和交接记录 |
| `logs/` | 后续 Runtime 运行日志 |
| `decisions/` | 架构决策记录 |
| `notes/` | 每日推进笔记 |
| `assets/` | 项目视觉资产 |

## 持续集成

push 和 pull_request 到 `main` 分支时，GitHub Actions 会在 Python 3.11 和 3.12 上运行：

- `pytest`
- `doctor`
- ledger CLI smoke checks
- `public_scan`

详见 `.github/workflows/ci.yml`。

## 推进原则

保持小步、可审查、可回滚。

先把规则、状态模型、Agent 注册表、适配器边界和受控写入内核打稳，再逐步补齐统一接入、能力路由、控制面状态和未来 UI 可操作边界。
