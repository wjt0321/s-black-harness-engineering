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

当前仓库已经形成可内部试用的**离线、可审计 CLI / Runtime 安全内核**，并完成 Stage 12 control-plane read model 验收：

- 已可用于规则校验、任务/事件账本、能力路由、dry-run、受控写入和 recovery lineage 审计；
- Stage 13–45 的 backend/read-model/controlled-write/host/display/readiness 主线均已收口；Stage 46 又冻结了 fixed Git status executor 的可信 executable/image binding、sanitized child PATH、process-tree containment、有限 porcelain parser、safe output、no-write evidence 与专用 audit release contract；
- 当前可生成本地、自包含、确定性的静态只读 Control Panel，通过版本化 descriptor 声明 snapshot/HTML representation；filtered v3 还可通过独立标准库-only、stdin-only consumer 验证 schema、lifecycle、identity、safe sections 与 filter semantics，并由 one-shot host 在 validation pass 后返回安全内存投影。真实 adapter execution、持久化 service/DB、鉴权和 UI 写操作仍未开放，因此当前不是自动执行型生产中枢台。

## 当前进度条

> 这是一个长期项目，下面的百分比不是“代码量”，而是按**阶段闭环完成度**估算，用来帮助快速判断：现在做到哪、接下来该往哪走。

### 总体进度（主观工程估算）

```text
[███████████████░░░░░░░░░] 约 60%
```

当前判断：

- **安全与审计内核**：约 **80%**
- **中枢台后端抽象**：约 **55%**
- **UI / Control Panel 准备度**：约 **45%**

### 版本号说明

当前仓库最新里程碑基线为 `v0.17.0-filtered-snapshot-display-host-integration`（已推送至 `origin`），覆盖 Stage 39–40 的 validation-before-release one-shot Markdown display host。上一基线 `v0.16.0-filtered-snapshot-display-consumer` 也已推送至 `origin`。

在 `v0.11.0-runtime-event-import` 之后，项目进入 orchestration 主线，实际改用“**阶段编号 + release notes 文档**”做阶段收口，例如 `55`、`57`、`59`、`61`、`65`、`67`、`72`。这代表：

- 阶段收口一直在继续；
- semver / tag 不再按每个阶段同步增长；
- 版本治理改为“阶段推进 + release notes 收口 + 里程碑打 tag”。

当前已通过 `docs/64-versioning-governance.md` 正式定义该策略，并已在 `v0.12.0-orchestration-foundation`、`v0.12.1-orchestration-read-loop-snapshot`、`v0.13.0-read-only-control-plane`、`v0.14.0-filtered-snapshot-host-integration`、`v0.15.0-filtered-snapshot-display-integration`、`v0.16.0-filtered-snapshot-display-consumer` 与 `v0.17.0-filtered-snapshot-display-host-integration` 七次实际冻结：

- 阶段编号继续用于推进顺序；
- release notes 用于单阶段收口；
- semver / Git tag 只用于里程碑级冻结点，不再逐阶段补 tag；
- 当前最新冻结里程碑为本地 `v0.17.0-filtered-snapshot-display-host-integration`，在 `v0.16.0` consumer 上补齐 validation-before-release 与 five-id cross-check host。

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
- 🟡 Stage 10 — Adapter Runtime Interface（source-backed registry 投影第一版已落地，持续巩固）
- 🟡 Stage 11 — Capability Routing Model（约束路由 + decision trace 第一版已落地，持续巩固）
- ✅ Stage 12 — Control Plane State Model（read-only loop、recovery lineage aggregation 与 inspect/report consolidation 已完成验收）
- ✅ Stage 13 — Backend-first API Boundary（资源/操作边界对账与 CLI 契约测试已完成）
- ✅ Stage 14 — 中枢台最小编排闭环（七步闭环、replay 与结构化 next_action 已收口）
- 🟡 Stage 15 — UI / 看板前的后端准备（read-model CLI 第一版已落地，交互式前端仍暂缓）
- 🟡 Stage 15.5 — Orchestration 受控写入边界（第一批 controlled handoff / approval resolve 已落地）
- ✅ Stage 15.7 — Orchestration Run Dry-run 落地
- ✅ Stage 15.8 — Orchestration Run Commit（A-only）落地
- ✅ Stage 15.9 — Orchestration Run Lifecycle Events 落地
- ✅ Stage 15.95 — Orchestration Task Submit Created Event 落地
- ✅ Stage 15.96 — Orchestration Run Retry / Fallback Dry-run 落地
- ✅ Stage 15.97 — Orchestration Foundation Freeze 完成（基线：`38b4b69` / `v0.12.0-orchestration-foundation`）
- ✅ Stage 15.98 — Orchestration Run Retry / Fallback Commit 落地
- ✅ Stage 15.99 — Run Lineage / Recovery 单条只读模型落地
- ✅ Stage 16 — Read-only Control Panel MVP（静态只读 snapshot/render 已收口；live UI 延期）
- ✅ Stage 17 — Control Panel Host Integration Boundary（stdio-first handoff descriptor 已收口）
- ✅ Stage 18 — Read-only Host Consumer Validation（独立 reference consumer 已按 TDD 收口）
- ✅ Stage 19 — Host-specific Read-only Adapter Design Gate（Codex Desktop 本地任务进程边界已冻结）
- ✅ Stage 20 — Host-specific Read-only Adapter Implementation（固定 producer/consumer 的 one-shot read-only adapter 已收口）
- ✅ Stage 21 — Read-only Representation Read Design Gate（validation-only 已冻结）
- ✅ Stage 22 — Codex Desktop Snapshot JSON Reader（显式 one-shot snapshot read 已收口）
- ✅ Stage 23 — Envelope-scoped Snapshot Read Design Gate（已通过）
- ✅ Stage 24 — Codex Desktop Envelope-scoped Snapshot JSON Reader（显式 allowlist-only v2 已收口）
- ✅ Stage 25 — Envelope-scoped Consumer Integration / Filter Design Gate（无 filter consumer contract 已冻结）
- ✅ Stage 26 — Filtered Envelope Snapshot Read Design Gate（task/request exact filter 与 v3 identity 已冻结）
- ✅ Stage 27 — Filtered Envelope Snapshot JSON Reader Implementation（task/request exact filter v3 已收口）
- ✅ Stage 28 — Filtered Snapshot Host Consumer Validation Gate（独立 v3 consumer contract 已冻结，未实现 consumer）
- ✅ Stage 29 — Codex Desktop Filtered Snapshot Consumer Implementation（独立 stdin-only v3 consumer 已收口）
- ✅ Stage 30 — Codex Desktop Filtered Snapshot Host Integration Gate（已收口）
- ✅ Stage 31 — Codex Desktop Filtered Snapshot Host Integration Implementation（one-shot host 已收口）
- ✅ Stage 32 — Filtered Snapshot Host Integration Milestone Freeze（`v0.14.0` 已 push）
- ✅ Stage 33 — Codex Desktop Filtered Snapshot Display Integration Gate
- ✅ Stage 34 — Codex Desktop Filtered Snapshot Markdown Display Implementation
- ✅ Stage 35 — Filtered Snapshot Display Integration Milestone Freeze（`v0.15.0` 已推送）
- ✅ Stage 36 — Filtered Snapshot Markdown Display Consumer Validation Gate
- ✅ Stage 37 — Filtered Snapshot Markdown Display Consumer Implementation
- ✅ Stage 38 — Filtered Snapshot Display Consumer Milestone Freeze（`v0.16.0` 已推送）
- ✅ Stage 39 — Filtered Snapshot Markdown Display Consumer Host Integration Gate
- ✅ Stage 40 — Filtered Snapshot Markdown Display Consumer Host Integration Implementation
- ✅ Stage 41 — Filtered Snapshot Display Host Integration Milestone Freeze（`v0.17.0` 已推送）
- ✅ Stage 42 — Filtered Snapshot Validated Markdown Presentation Handoff Gate（design-only 已收口）
- ✅ Stage 43–45 — Single-user Real Execution Readiness（提交级里程碑已收口；真实执行仍 blocked）
- ✅ Stage 46 — Fixed Git Status Executor Design Gate（design-only 已收口；未执行 Git）

### 现在最明确的位置

可以把当前状态理解成：

- **门禁 / ledger / controlled write 这一层，已经不是草稿，而是一个成型的安全内核**
- **中枢台后端主线已经具备 source-backed registry、约束路由、read-loop snapshot、recovery lineage aggregation，以及 CLI automation contract/profile/workflow plan/drift validation projection**
- **真实 adapter execution 仍 blocked；fixed `git_status` 的 trust/image binding、sanitized PATH、process-tree runner、output/no-write/audit release 设计已冻结，但 audit writer 和 executor 尚未实现**

### 接下来的方向

Stage 23–35 scoped/filtered reader、consumer、host 与 Markdown display，以及 Stage 36–38 display consumer milestone 已完成：

1. 用户必须同时显式选择 `snapshot-json` 并提供 allowlist 内的 project-relative `--envelope`
2. allowlist 为 `adapters/*.json` 与 `drafts/runtime/**/*.envelope.json`，绝对路径、`..`、越界和 arbitrary JSON 均拒绝
3. 复用 Stage 17 handoff、Stage 18 validation 与 Stage 22 snapshot identity/hash 校验，不创建平行管线
4. scoped v2 输出 envelope content/scope identity，并在 one-shot 结束前复查内容未漂移
5. 仍不读取 HTML、不打开浏览器、不写文件或 artifact；事实源为 `docs/84-envelope-scoped-snapshot-read-design-gate.md`
6. Stage 25 保持单-envelope、无 filter v2；宿主只能一次性读取并内存展示已验证 JSON，不新增 query/persistence/export；事实源为 `docs/archive/85-envelope-scoped-consumer-filter-design-gate.md`
7. Stage 26 冻结 v3 的 task/request exact filter、AND/空视图、关系闭包与 filter/view identity；事实源为 `docs/86-filtered-envelope-snapshot-read-design-gate.md`
8. Stage 27 在既有 reader 上实现 filtered v3；filter 仅作用于已验证安全 summaries，fixed child argv 不携带 filter，v1/v2 保持兼容；事实源为 `docs/87-filtered-envelope-snapshot-json-reader-implementation.md`
9. Stage 28 选择 Codex Desktop 一次性本地任务进程作为具体宿主，冻结未来专用 stdin-only consumer 的完整 v3 输入、scope/filter/view identity、safe sections、最小输出与 no-side-effect contract；本阶段不实现 consumer，事实源为 `docs/archive/88-filtered-snapshot-host-consumer-validation-gate.md`，下一阶段为 Stage 29 条件实现。
10. Stage 29 已实现 `tools/codex_desktop_filtered_snapshot_consumer.py`：只消费完整 v3 stdin，固定 11 项验证、1 MiB 输入、64 KiB 最小输出与状态/退出码；不自动执行 reader、不读写文件、不访问网络。
11. Stage 31 已实现 `tools/codex_desktop_filtered_snapshot_host.py`：固定 reader → consumer 管道，consumer pass 与 identity cross-check 前不释放 payload；事实源为 `docs/archive/90-codex-desktop-filtered-snapshot-host-integration-and-milestone-freeze.md`。
12. Stage 33–35 已完成 fixed Stage 31 host → strict validation → deterministic escaped Markdown，并冻结、推送 `v0.15.0`；事实源为 `docs/archive/91-codex-desktop-filtered-snapshot-markdown-display-integration-and-milestone-freeze.md`。
13. Stage 39–41 已完成 validation-before-release display host design、实现与本地 `v0.17.0` 里程碑冻结；Stage 42 已按 design-only 收口，冻结 ready/pass/identity/content hash 重确认与 future presentation 启动条件，不新增 presenter、专有 UI/HTML/browser/service/persistence/write。
14. Stage 43–45 已完成单用户真实执行 readiness：固定 `shell-local/git_status`、exact argv、bounded process、approval binding 与 audit contract，并以 10 pass/3 blocked 明确下一实现缺口；不执行命令。
15. Stage 46 已完成 fixed Git status executor design-only gate：拒绝通用 shell，明确 PATH 只做候选发现，冻结 operator-reviewed trust/image binding、sanitized child PATH、POSIX process group / Windows Job Object、有限 porcelain grammar、安全摘要、no-write 证据分层与 reserved audit event 来源隔离；下一步先做 execution lifecycle audit writer。

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
- Stage 12 post-freeze recovery read model：`orchestration run inspect --aggregate-lineage` / `orchestration report generate --aggregate-lineage`（基于现有 lifecycle events 聚合 root/latest/leaves、attempt count 与 effective plan hash，只读、不扫描 drafts）
- post-Stage 14 CLI automation：`orchestration contract inspect/check`、`orchestration profile list/inspect/check`、`orchestration workflow plan/check`（确定性发现、协商、命名化、未执行步骤投影与 hash drift validation）
- Stage 16/17 Read-only Control Panel：`orchestration control-panel snapshot/render/handoff`（确定性 snapshot、自包含 HTML、stdio host descriptor、可选 envelope-scoped run/approval/artifact、无 service/network/write/execute）
- Stage 20 Codex Desktop Read-only Adapter：`python tools/codex_desktop_read_only_adapter.py --project-root . --timeout-seconds 30 --json`（固定 producer → reference consumer validation，一次性、无写入、无网络、不读取 representation）
- Stage 22/24 Codex Desktop Snapshot JSON Reader：无 envelope 时保持 v1；显式追加 `--envelope adapters/execution-envelope.examples.json` 时返回 allowlist-only scoped v2（固定三段 argv、scope/content identity、无写入/网络/执行）

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
python -m agent_runtime.cli orchestration run inspect --task-id <task-id> --request-id <request-id> --envelope <envelope.json> --events-file tasks/events.jsonl --aggregate-lineage --json
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
10. `docs/archive/53-minimal-orchestration-loop-cli-draft.md`
11. `docs/54-backend-preparation-before-ui.md`
12. `docs/archive/release-notes/55-release-notes-orchestration-read-models.md`
13. `docs/56-orchestration-controlled-write-boundary.md`
14. `docs/archive/release-notes/57-release-notes-orchestration-controlled-handoff.md`
15. `docs/58-orchestration-run-controlled-execution-design.md`
16. `docs/archive/release-notes/59-release-notes-orchestration-run-controlled-execution.md`
17. `docs/60-orchestration-run-lifecycle-events-design.md`
18. `docs/archive/release-notes/61-release-notes-orchestration-run-lifecycle-events.md`
19. `docs/62-orchestration-task-submit-controlled-write-design.md`
20. `docs/63-orchestration-task-submit-created-event-design.md`
21. `docs/64-versioning-governance.md`
22. `docs/archive/release-notes/65-release-notes-orchestration-task-submit-created-event.md`
23. `docs/66-orchestration-run-retry-fallback-design.md`
24. `docs/archive/release-notes/67-release-notes-orchestration-run-retry-fallback.md`
25. `docs/archive/68-orchestration-foundation-milestone-freeze-checklist.md`
26. `docs/archive/69-orchestration-foundation-freeze-execution-plan.md`
27. `docs/70-orchestration-run-retry-fallback-commit-design.md`
28. `docs/archive/release-notes/71-release-notes-run-lineage-read-models.md`
29. `docs/10-cli-poc-usage.md`
30. `docs/21-controlled-write-boundaries.md`

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
