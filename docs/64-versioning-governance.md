# 63 — 版本治理与 Tag 策略

## 背景

仓库当前可见的 Git tag / semver 冻结在 `v0.11.0-runtime-event-import`。

但从 orchestration 主线开始，项目并没有停止推进，而是改用以下形态持续收口：

- 设计文档：如 `56`、`58`、`60`、`62`
- 阶段 release notes：如 `55`、`57`、`59`、`61`
- 代码提交：围绕 `orchestration *` 命令持续实现

因此问题不是“55/57/59/61/62 漏打 tag”，而是**版本治理从 Runtime 线切到 Orchestration 线之后，没有把新规则正式写下来**。

本文档的目标，就是把这个规则补齐。

## 结论

从 `v0.11.0-runtime-event-import` 之后，仓库采用以下三层版本治理：

1. **Semver tag 负责里程碑冻结**
2. **阶段编号负责文档与实现推进顺序**
3. **Release notes 负责单阶段收口说明**

这三者不再要求一一对应。

也就是说：

- 不是每个阶段编号都要对应一个 Git tag；
- 不是每篇 release notes 都要升级一次 semver；
- 只有形成明确的、可对外描述的里程碑能力包时，才打新的 tag。

## 三层对象的职责

### 1. Semver / Git tag

Semver tag 只用于**里程碑级冻结点**。

它应该满足以下条件：

- 能代表一段稳定、可回看、可引用的能力集合；
- 相比上一个 tag，已经形成清晰的新阶段能力包，而不只是单个局部命令；
- 对外描述时，用一个版本名比用多个阶段号更清楚；
- 该冻结点最好同时包含：代码、文档、release notes、验证记录。

因此，tag 的节奏应当比 release notes 更稀疏。

### 2. 阶段编号

阶段编号用于表示 orchestration 主线内部的**推进顺序**。

它的作用是：

- 保持设计文档、实现收口、路线图引用之间的可追踪顺序；
- 让读者知道当前能力是如何一阶段一阶段长出来的；
- 为后续设计 gate 与实现 gate 留出稳定编号。

阶段编号不是版本号，也不要求对外暴露为 semver。

### 3. Release notes

Release notes 用于记录单阶段的：

- 阶段定位
- 已实现能力
- 安全边界
- 已知限制
- 验证方式
- 后续入口

Release notes 是阶段收口文档，不自动等于 tag 候选。

## 从 Runtime 线到 Orchestration 线的策略变化

`v0.1.0` 到 `v0.11.0` 期间，仓库主要沿着 Runtime / controlled-write 积木推进，tag 粒度相对密。

从 orchestration 主线开始，推进模式发生了变化：

- 文档与实现交替推进；
- 有些阶段是 design gate，不是 release gate；
- 多个连续阶段一起看，才构成一个更完整的 control-plane 能力面。

因此继续沿用“每个阶段一个 semver tag”的方式，会带来两个问题：

1. tag 变得过密，信息噪声高；
2. design gate 与 implementation gate 会被误当成同等级发布节点。

所以从 orchestration 主线开始，默认规则改为：

- **阶段照常推进；**
- **release notes 照常收口；**
- **tag 只在里程碑阶段补打。**

## 对 55 / 57 / 59 / 61 / 62 的具体判定

### 55

`55-release-notes-orchestration-read-models.md` 是明确的阶段 release notes。

它属于 orchestration read-model CLI 第一版收口，适合作为里程碑候选的一部分，但**不单独补 semver tag**。

### 57

`57-release-notes-orchestration-controlled-handoff.md` 是明确的阶段 release notes。

它把 route preview / preflight / approval resolve 这一段受控 handoff 跑通，属于里程碑候选的一部分，但**不单独补 semver tag**。

### 59

`59-release-notes-orchestration-run-controlled-execution.md` 是明确的阶段 release notes。

它把 run dry-run / commit 的第一版边界建立起来，属于里程碑候选的一部分，但**不单独补 semver tag**。

### 61

`61-release-notes-orchestration-run-lifecycle-events.md` 是明确的阶段 release notes。

它把 run commit 从 A-only 提升到 A+B controlled write，是 orchestration 主线里的重要实现收口，但**仍建议并入统一里程碑 tag，而不是单独补 tag**。

### 62

`62-orchestration-task-submit-controlled-write-design.md` 目前是 design gate，不是 release notes。

因此：

- 当前**不应**为 62 单独打 release tag；
- 只有当 62 对应实现完成，并产生独立 release notes 后，才进入里程碑候选集合。

## 当前默认决策

当前默认决策如下：

- **不追补** 55 / 57 / 59 / 61 的逐阶段 semver tag；
- **不为** 62 设计文档打 tag；
- 继续保留阶段编号 + release notes 的推进方式；
- 等 `orchestration task submit` 实现收口之后，再判断是否把 55 / 57 / 59 / 61 / 62x 合并冻结为一个新的 orchestration milestone tag。

这里的 `62x` 指：62 对应设计完成后，后续若产生实现文档与 release notes，应以实现收口文档为准，而不是以设计文档本身为准。

## 新 tag 的触发条件

从现在开始，只有满足以下条件之一，才建议新建 tag：

### 条件 A：形成新的 orchestration 里程碑能力包

例如同时满足：

- read models 已齐；
- controlled handoff 已齐；
- run controlled execution 已齐；
- run lifecycle events 已齐；
- task submit 入口也已齐。

这时可以把多个连续阶段合并为一个新的里程碑版本。

### 条件 B：出现需要稳定对外引用的冻结点

例如：

- 需要给其他仓库/文档/演示明确引用一个版本；
- 需要为某个集成方提供稳定基线；
- 需要把一个阶段能力包作为“当前推荐基线”固定下来。

### 条件 C：代码与文档已经明显跨过上一 tag 的语义边界

如果相对 `v0.11.0-runtime-event-import`，能力叙事已经从 Runtime 工具链明显扩展到 Orchestration control plane，则应考虑新 tag，而不是无限期停留在旧 tag 之后。

## 新 tag 的命名建议

后续若决定给 orchestration 里程碑补统一 tag，建议遵循原有模式继续扩展：

- `v0.12.0-orchestration-foundation`
- 或 `v0.12.0-orchestration-control-plane-foundation`

命名原则：

- 保留 `v0.x.y-*` 形态，避免仓库出现第二套完全不同的 tag 命名体系；
- 后缀描述里程碑能力包，而不是单个命令；
- 不把阶段号直接塞进 tag 名里，避免把内部推进编号误当成公开版本名。

当前更推荐的候选名是：`v0.12.0-orchestration-foundation`。

原因：55 / 57 / 59 / 61 / 62 共同描述的是 orchestration 基础面的建立，而不是某一个孤立功能点。

## 补 tag 前的最小检查清单

在真正创建下一个 tag 之前，至少应完成以下检查：

- 对应阶段 release notes 已完整存在；
- README / roadmap / index 已能解释该里程碑是什么；
- 关键命令已有测试或可重复验证路径；
- `tasks/progress.md` 与 handoff 文档已能追溯该阶段；
- tag 指向的提交足够稳定，不是只包含单个 design gate。

## 对仓库文档的影响

从本文档生效后，仓库里的“版本治理说明”应统一表述为：

- `v0.11.0-runtime-event-import` 是上一条 semver 冻结点；
- 55 / 57 / 59 / 61 / 62 是 orchestration 主线的连续阶段文档；
- 当前采用“阶段推进 + release notes 收口 + 里程碑打 tag”的版本治理策略。

## 实施结果

本文档落地后，当前问题的处理结论就是：

- 先不补 55 / 57 / 59 / 61 的统一版本号或 tag；
- 先不为 62 打 tag；
- 继续推进 task submit；
- 等 orchestration 入口与 run 主线形成更完整里程碑后，再统一决定下一个 semver tag。

## 后续状态补充（post-freeze）

- 已实际冻结 `v0.12.0-orchestration-foundation`（commit `38b4b69`，annotated tag 已 push）。
- 已实际冻结 `v0.12.1-orchestration-read-loop-snapshot`（commit `0419a04`，annotated tag 已 push），覆盖 Stage 10–12 的 source-backed registry、约束路由、decision trace、routing snapshot 与 read-loop snapshot 只读 read model。
- 后续 semver tag 仍只在里程碑级冻结点创建，不逐阶段补 tag。

## Stage 12 最终收口（2026-07-12）

- Stage 12 — Control Plane State Model 已按只读、确定性、可审计的 read-model 范围完成最终验收。
- 本次收口使用 release notes + Git commit 记录，验收入口为 `docs/archive/release-notes/75-release-notes-stage12-control-plane-state-model.md`。
- 当前稳定 semver 基线继续保持 `v0.12.1-orchestration-read-loop-snapshot` / `0419a04`；本次不创建新 tag。
- 原因：本次工作完成的是阶段契约验收、延期项划界和下一阶段交接，没有形成需要新增 semver 对外引用的独立执行能力包。
- Stage 12 最终验收 commit：`5e8df01`。
- 后续进入 Stage 13 — Backend-first API Boundary，第一拍为 Boundary Contract Reconciliation。

## Stage 13 最终收口（2026-07-13）

- Stage 13 — Backend-first API Boundary 已完成真实 CLI/read model 的资源/操作边界对账与命令 surface 契约测试。
- 验收入口：`docs/archive/release-notes/76-release-notes-stage13-backend-first-api-boundary.md`。
- 当前稳定 semver 基线继续保持 `v0.12.1-orchestration-read-loop-snapshot` / `0419a04`；本次不创建新 tag。
- 原因：本次冻结的是后端契约语义与兼容边界，没有新增真实执行、service 或持久化能力包。
- Stage 13 最终验收 commit：`9625ba2`。
- 后续进入 Stage 14 — 中枢台最小编排闭环。


## v0.13.0 Read-only Control Plane 里程碑冻结（2026-07-14）

Stage 13–16 已跨过 `v0.12.1-orchestration-read-loop-snapshot` 的语义边界，形成新的可引用能力包：

- Backend-first API Boundary；
- Minimal Orchestration Loop replay / next_action；
- recovery lineage aggregation；
- CLI automation contract/profile/workflow；
- deterministic static Read-only Control Panel。

因此本轮按条件 A、B、C 同时满足处理，冻结 annotated tag：

```text
v0.13.0-read-only-control-plane
```

冻结事实源为 `docs/archive/77-read-only-control-plane-milestone-freeze.md` 与 `docs/archive/release-notes/80-release-notes-v0.13.0-read-only-control-plane.md`。该 tag 不改变项目边界：真实 adapter execution、live service、auth、DB、实时订阅和 UI controlled write 继续 unavailable。


实际冻结结果：

- freeze commit：`f401b98`；
- annotated tag：`v0.13.0-read-only-control-plane`；
- GitHub Actions CI：Python 3.11 / 3.12 matrix 均通过；
- `main` 与 tag 均已推送到 `origin`。

## v0.14.0 Filtered Snapshot Host Integration 里程碑冻结（2026-07-16）

Stage 17–31 已在 `v0.13.0-read-only-control-plane` 上形成新的可引用能力包：

- versioned stdio handoff 与独立 consumer validation；
- Codex Desktop one-shot process boundary；
- project/envelope scoped snapshot JSON reader；
- task/request exact filtered v3 与 identity；
- 独立 filtered snapshot consumer；
- validation-before-display one-shot host integration。

因此条件 A、B、C 再次满足，冻结 annotated tag：

```text
v0.14.0-filtered-snapshot-host-integration
```

冻结事实源为 `docs/archive/90-codex-desktop-filtered-snapshot-host-integration-and-milestone-freeze.md` 与 `docs/archive/release-notes/93-release-notes-v0.14.0-filtered-snapshot-host-integration.md`。

冻结后已按用户授权将 commit/tag 推送至 `origin`，target 为 `dfae346`。该 tag 不开放专有 Codex Desktop 插件/UI、HTML/browser、live service、network/DB/auth、cache/export、arbitrary query、UI controlled write 或真实 adapter execution。


## v0.15.0 Filtered Snapshot Display Integration 里程碑冻结（2026-07-16）

Stage 33–34 在 v0.14.0 fixed host 上形成新的 one-shot safe display 能力包：

- strict host result validation；
- safe allowlist projection；
- deterministic escaped Markdown；
- content hash、empty-view UX 与 bounded output；
- non-ready withheld 与 no-side-effect contract。

冻结本地 annotated tag：

```text
v0.15.0-filtered-snapshot-display-integration
```

冻结事实源为 `docs/archive/91-codex-desktop-filtered-snapshot-markdown-display-integration-and-milestone-freeze.md` 与 `docs/archive/release-notes/96-release-notes-v0.15.0-filtered-snapshot-display-integration.md`。commit/tag 随后已按用户授权推送至 `origin`；专有 UI、HTML/browser、network/service、persistence/export、write 与真实 execution 继续 unavailable。


## v0.16.0 Filtered Snapshot Display Consumer 里程碑冻结（2026-07-16）

Stage 36–37 在 v0.15.0 deterministic Markdown display 上形成独立、可引用的 consumer validation 能力包：

- 完整 display v1 wrapper/status/lifecycle/guarantees validation；
- bounded strict stdin parsing 与 duplicate-key rejection；
- independent content hash、fixed Markdown grammar 与 escaping invariant validation；
- identity/count/filter/empty-view/report coherence；
- minimal value-safe output 与 non-ready withheld contract。

因此再次满足里程碑冻结条件，创建本地 annotated tag：

```text
v0.16.0-filtered-snapshot-display-consumer
```

冻结事实源为 `docs/archive/92-filtered-snapshot-markdown-display-consumer-validation-gate.md` 与 `docs/archive/release-notes/99-release-notes-v0.16.0-filtered-snapshot-display-consumer.md`。该 tag 后于 2026-07-16 按用户授权推送至 `origin`；自动启动上游、专有 UI、HTML/browser、file/URL、network/service、persistence/export、write 与真实 execution 继续 unavailable。


## v0.17.0 Filtered Snapshot Display Host Integration 里程碑冻结（2026-07-16）

Stage 39–40 在 v0.16.0 display consumer 上形成 validation-before-release one-shot host 能力包：

- fixed Stage 34 display 与 Stage 37 consumer argv ownership；
- exact stdout-to-stdin handoff；
- strict wrapper/status/exit/lifecycle/guarantees/check validation；
- five-id cross-check 与 content withheld until pass；
- bounded minimal environment、timeout/cancel/no-retry 与 no-side-effect。

冻结本地 annotated tag：

```text
v0.17.0-filtered-snapshot-display-host-integration
```

事实源为 `docs/93-codex-desktop-filtered-snapshot-display-host-integration-and-milestone-freeze.md` 与 `docs/archive/release-notes/102-release-notes-v0.17.0-filtered-snapshot-display-host-integration.md`。该 tag 后于 2026-07-16 按用户授权推送至 `origin`；专有 UI、render、file/URL、network/service、persistence/export、write 与真实 execution 继续 unavailable。

## Stage 42 Presentation Handoff Design-only Gate（2026-07-16）

Stage 42 仅冻结 Stage 40 ready result → future read-only presentation boundary 的 design-only contract 与启动条件，没有新增 production presenter、CLI、schema 或用户可见能力包，因此不满足新的 semver milestone tag 条件。

- 稳定 tag 继续为 `v0.17.0-filtered-snapshot-display-host-integration`，并已推送至 `origin`；
- Stage 42 以阶段文档、release notes 103 与 prerequisite contract test 收口；
- 不创建 `v0.18.0` 候选 tag；
- 只有后续明确 consumer/action 并完成实现与全量验收后，才重新评估里程碑版本。

## Stage 43–45 Single-user Execution Readiness 提交级里程碑（2026-07-16）

Stage 43–44 已形成真实执行前的可引用 readiness 能力，但 executor、approval plan binding 与 audit writer 仍明确 blocked，尚未形成可执行能力包。因此 Stage 45 采用提交级里程碑收口：

- 不创建 `v0.18.0` tag；
- 稳定 semver 继续为已推送的 `v0.17.0-filtered-snapshot-display-host-integration`；
- readiness CLI 作为 preview/read-only contract；
- future fixed executor、binding、audit writer 全部实现并验收后，再评估 v0.18 milestone；
- 未经用户明确要求不创建 tag、不 push。

## Stage 46 Fixed Git Status Executor Design-only Gate（2026-07-16）

Stage 46 只冻结 executable/image trust binding、sanitized child PATH、repository/config/submodule preflight、process-tree containment、有限 porcelain parser、safe output、no-write evidence 分层与 dedicated audit release ordering，没有新增 production executor、CLI、schema、event type 或可执行能力包，因此继续不满足新的 semver tag 条件。

- 稳定 tag 继续为已推送的 `v0.17.0-filtered-snapshot-display-host-integration`；
- Stage 46 以 `docs/archive/96-fixed-git-status-executor-design-gate.md` 与 release notes 106 收口；
- 不创建 `v0.18.0` tag，不 push；
- Stage 47–48 先完成 reserved execution lifecycle schema、专用 provenance 与不可由通用 append/import 伪造的 audit writer；
- Stage 49 只有 trust/image binding、sanitized child PATH、process-tree containment、有限 porcelain parser 全部闭合，用户再次明确授权真实 subprocess 且全量验收通过后，才重新评估 v0.18 milestone。

## Stage 47–48 Execution Lifecycle Audit Writer 提交级里程碑（2026-07-17）

Stage 47–48 已形成可复用的内部 controlled-write 能力包：

- 四类 reserved execution lifecycle event 的 shared + dedicated schema；
- 固定 provenance、safe evidence allowlist 与通用 append/import 来源隔离；
- started/terminal 使用同一 locked file descriptor、writer-only append token 与 path/file identity byte-size rollback；检测到并发 ledger 漂移或 file replacement 时拒绝 committed/truncate；
- audit chain validator 与 open/closed/missing/invalid recovery inspection；
- Stage 44 readiness v1 历史兼容和 controlled-write isolation regression。

但本能力没有 CLI，也不启动 subprocess、执行 Git、访问网络或开放 adapter execution，因此仍不满足新的 semver tag 条件：

- 稳定 tag 继续为已推送的 `v0.17.0-filtered-snapshot-display-host-integration`；
- Stage 47–48 以 `docs/97-execution-lifecycle-audit-writer-design-and-implementation.md` 与 release notes 107 收口；
- 本轮只创建本地提交，不创建 `v0.18.0` tag，不 push；
- Stage 49 必须在用户再次明确授权真实 subprocess，并闭合 Stage 46 trust/image binding、sanitized child PATH、process-tree containment 与有限 parser 后，才允许实现；
- audit writer 完成不得被解释为 execution permission。

## Stage 49 Fixed Git Status Executor 提交级里程碑（2026-07-17）

Stage 49 已形成第一个真实但严格有限的 Windows execution 能力包：

- machine-local operator-reviewed executable trust binding；
- non-shareable handle、SHA-256/file-id/AuthentiCode signer 与 suspended process image recheck；
- sanitized PATH、repository/config containment 与 pre/post no-write guard evidence；
- Windows Job Object bounded one-shot runner；
- finite porcelain parser、安全摘要与 dedicated execution audit release gate；
- 一次显式授权真实 temporary repository smoke。

本轮仍不创建 `v0.18.0` tag：

- enablement 仅限 Windows 和一个 fixed operation；
- POSIX 等价实现不存在；
- `filesystem_write_proof=false`，尚无 OS-enforced read-only filesystem；
- machine-local trust binding 需要 operator provisioning，不是跨机器即开即用能力；
- 用户要求只提交到本地，不 push。

稳定 semver 继续为已推送的 `v0.17.0-filtered-snapshot-display-host-integration`。Stage 49 以 `docs/98-fixed-git-status-executor-implementation-and-limited-enablement.md` 与 release notes 108 收口；后续是否形成 v0.18 必须在 operational recovery、平台覆盖和 stronger isolation 重新评估后决定。

## Stage 50 Fixed Execution Operational Recovery Design-only Gate（2026-07-17）

Stage 50 冻结 Stage 49 之后的 operational recovery contract：

- machine-local single-flight execution lease；
- trust binding inspection、reviewed rotation 与 invalid-binding fail-closed；
- reviewed rotation 绑定 expected old binding id 与完整 new executable/PATH identity，lease 拒绝 pathname replacement/split-brain；
- open attempt bounded discovery、inspection 与 outcome-unknown fixed closure；
- Windows Job accounting active-zero、direct-child reap 与 containment-close evidence；
- `execution-audit/v1` 历史兼容与 future v2 Job evidence。

本阶段没有新增 production CLI、schema、writer、subprocess 或真实 operation，因此不形成新的 semver capability pack：

- 稳定 tag 继续为已推送的 `v0.17.0-filtered-snapshot-display-host-integration`；
- Stage 50 以 `docs/99-fixed-execution-operational-recovery-design-gate.md` 与 release notes 109 收口；
- 不创建 `v0.18.0`，不 push；
- Stage 51 只能按 Stage 50 contract 实现 recovery，不得增加第二个 command、POSIX、network adapter 或 stronger filesystem claim。
