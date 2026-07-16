# 000 — Stage Digest

> **新会话先读这份，不要先翻整仓文档。**

## 文档池规模

- docs/ 活跃文档：50 个
- 归档文档：68 个，位于 `docs/archive/`（historical design gates / freeze records / release-notes / dry-runs / smoke-regression）
- 全仓 .md 文件：约 194 个
- **文档维护规则：`docs/MAINTENANCE.md`**

## 当前基线

- 稳定基线：`v0.15.0-filtered-snapshot-display-integration` / `b1fa0b3`（annotated tag 与 `main` 已推送至 `origin`）
- 上一冻结基线（v0.14）：`v0.14.0-filtered-snapshot-host-integration` / `dfae346`（annotated tag 与 `main` 已推送至 `origin`）
- 上一冻结基线：`v0.13.0-read-only-control-plane` / `f401b98`（已 push）
- 再上一冻结基线：`v0.12.1-orchestration-read-loop-snapshot` / `0419a04`
- Stage 13 最终收口提交：`9625ba2`
- Stage 14 Evidence projection 提交：`4a64ace`
- Stage 14 最终收口提交：`03b64dd`（已推送至 `origin/main`）
- 上一 foundation 基线：`v0.12.0-orchestration-foundation`（commit `38b4b69`）
- Stage 17–31 filtered snapshot host 能力包已冻结并推送 annotated milestone tag：`v0.14.0-filtered-snapshot-host-integration`

## 当前阶段

- **Stage 36 — Filtered Snapshot Markdown Display Consumer Validation Gate（收口完成）**
- Stage 35 — Filtered Snapshot Display Integration Milestone Freeze（已收口）
- Stage 34 — Codex Desktop Filtered Snapshot Markdown Display Implementation（已收口）
- 下一阶段：Stage 37 — Filtered Snapshot Markdown Display Consumer Implementation（条件启动）
- Stage 13 已完成：资源/操作模型与真实 CLI/read models 的 stable、stable（受限）、preview、unavailable 矩阵已冻结。
- Stage 14 最小编排闭环与 post-Stage 14 CLI 自动化消费者均已收口。
- 2026-07-14 Stage 16 第一版已落地：确定性 `control-panel snapshot` 与自包含静态 HTML `render`，复用既有 read models，不启动 service、不访问网络、不写 ledger、不执行 adapter。
- Stage 16 收口提交：`b46c013`（`Complete Stage 16 read-only control panel`）；已按用户授权推送到 `origin/main`。
- 2026-07-14 Stage 17 第一拍已落地：`control-panel handoff` 输出版本化 stdio descriptor，复用 snapshot identity 并声明 JSON/HTML representation、renderer identity 与只读安全边界。
- project-local 绝对 envelope 路径会归一化为 root-relative 表示；descriptor 不内嵌 HTML、不执行 argv、不启动 service、不访问网络、不写文件或 ledger。
- Stage 17 当时以 release notes 收口且未追补 tag；其后已由 `v0.14.0-filtered-snapshot-host-integration` 汇总冻结。
- Stage 18 第一拍已按 TDD 完成：标准库-only、stdin-only reference consumer 独立校验 handoff schema、identity、representation metadata、argv shape 与 boundary，绝不执行 argv。
- 输入门禁覆盖 1 MiB 上限、空输入、非 UTF-8、非法 JSON、duplicate key；输出为确定性的 `control-plane/control-panel-host-consumer-validation/v1`。
- Stage 18 事实源：`docs/79-read-only-host-consumer-validation-boundary.md` 与 `docs/archive/release-notes/82-release-notes-stage18-read-only-host-consumer-validation.md`。
- Stage 19 已冻结 Codex Desktop 本地任务进程边界的只读 adapter design gate：一次性 bootstrap → reference consumer validation → 宿主状态映射；v1 不读取 representation、不执行 descriptor argv、不写文件。
- Stage 19 事实源：`docs/archive/80-codex-desktop-read-only-adapter-design-gate.md`。
- Stage 20 已实现 `tools/codex_desktop_read_only_adapter.py`：固定 producer/consumer argv、一次性生命周期、30 秒默认/60 秒上限、1 MiB stdout 上限、最小环境白名单、确定性 adapter result 与状态/退出码映射。
- Stage 20 历史事实源：`docs/archive/81-codex-desktop-read-only-adapter-implementation.md` 与 `docs/archive/release-notes/83-release-notes-stage20-codex-desktop-read-only-adapter.md`。
- Stage 21 已审计 representation 消费边界并冻结 validation-only：当前不执行 descriptor argv、不读取 HTML/JSON、不新增 consume 命令、reader schema 或 service。
- Stage 21 事实源：`docs/archive/82-read-only-representation-read-design-gate.md` 与 `docs/archive/release-notes/84-release-notes-stage21-read-only-representation-read-design-gate.md`。
- Stage 22 已按 TDD 实现 `tools/codex_desktop_snapshot_json_reader.py`：用户显式选择 `snapshot-json`，固定 handoff → consumer → snapshot 三段 argv，独立校验 schema/source/guarantees/identity/canonical hash 后返回有界 JSON representation。
- Stage 22 v1 不执行 descriptor argv、不读取 HTML、不接受 envelope/URL/任意路径、不写文件、不访问网络、不启动 service、不执行 candidate command 或真实 adapter。
- Stage 22 事实源：`docs/83-codex-desktop-snapshot-json-reader-implementation.md` 与 `docs/archive/release-notes/85-release-notes-stage22-codex-desktop-snapshot-json-reader.md`。
- Stage 22 post-close 文档沉淀已完成：旧 `v0.12.0` freeze checklist / execution plan（68/69）完整移入 `docs/archive/`，活跃根目录文档从 51 降至 49，所有外部引用已更新，内容未删除。
- envelope 未提供时，run/approval/artifact 区段诚实显示 unavailable；report 保持 request-scoped boundary，不伪造持久 collection。
- Stage 23 design gate 已通过，Stage 24 已在同一 reader 上新增显式 `--envelope` scoped v2；无 envelope 的 Stage 22 v1 保持兼容。
- scoped input 只接受 `adapters/*.json` 与 `drafts/runtime/**/*.envelope.json`，并校验 path、1 MiB、UTF-8、duplicate key、schema/consistency、secret scan、scope/content identity 与 one-shot content drift。
- Stage 23/24 事实源：`docs/84-envelope-scoped-snapshot-read-design-gate.md` 与 `docs/archive/release-notes/86-release-notes-stage24-envelope-scoped-snapshot-json-reader.md`。
- Stage 25 已审计 consumer/filter 需求并冻结无 filter 方案：单个显式 envelope 的 v2 仍是唯一 scoped contract，reader 不新增 task/request/query/sort/page/export。
- 宿主只可一次性读取 `status=ready` 的 bounded stdout JSON 并在内存展示；不得保存、cache、export、打开 HTML/browser、自动刷新、访问网络或执行 adapter。
- Stage 25 事实源：`docs/85-envelope-scoped-consumer-filter-design-gate.md` 与 `docs/archive/release-notes/87-release-notes-stage25-envelope-scoped-consumer-filter-design-gate.md`。
- Stage 19 历史设计门已被 Stage 20 implementation 事实源取代，完整归档至 `docs/archive/80-codex-desktop-read-only-adapter-design-gate.md`；活跃文档保持 50 个。
- 用户明确要求进入下一阶段后，Stage 26 已冻结未来 v3 的 task/request exact filter、双参数 AND、合法空视图和 request→task 关系闭包。
- filter 仅作用于完整验证后的 runs/approvals/artifacts 安全 summaries；不传入 child argv，不触碰 raw envelope，不自动扩展 lineage。
- v3 使用独立 filtered payload schema、canonical `filter_id` 与 `view_id`，关联 Stage 24 base snapshot id / scope id，不静默改变 v1/v2。
- Stage 26 事实源：`docs/86-filtered-envelope-snapshot-read-design-gate.md` 与 `docs/archive/release-notes/88-release-notes-stage26-filtered-envelope-snapshot-read-design-gate.md`。
- Stage 27 已在既有 reader 上实现 `--task-id` / `--request-id` filtered v3：支持 task-only、request-only、双参数 AND、合法空视图与 request→task 关系闭包。
- v3 使用独立 filtered payload、canonical `filter_id` 与 `view_id`；过滤只发生在 Stage 24 base snapshot 全链验证及 content-drift recheck 之后，filter 不进入 child argv。
- 无 filter 继续输出 Stage 24 v2；无 envelope 继续输出 Stage 22 v1；通用 query、lineage expansion、persistence/export、HTML/browser/network/write/execute 均未开放。
- Stage 27 事实源：`docs/87-filtered-envelope-snapshot-json-reader-implementation.md` 与 `docs/archive/release-notes/89-release-notes-stage27-filtered-envelope-snapshot-json-reader.md`。
- 2026-07-16 Stage 28 design gate 已收口：具体宿主冻结为 Codex Desktop 本地一次性任务进程，输入为完整 filtered v3 reader result，不接受 payload-only，也不扩展 Stage 18 handoff consumer。
- 未来候选 consumer 冻结为标准库-only、stdin-only、1 MiB 输入上限；独立重算 scope/filter/view identity，base snapshot id 只做关联与形状检查。
- 新增 `tests/test_filtered_snapshot_host_consumer_contract.py`，以真实 Stage 27 stdout 冻结 wrapper/lifecycle/guarantees/identity/safe sections 前置契约；本阶段没有实现 consumer。
- Stage 28 事实源：`docs/88-filtered-snapshot-host-consumer-validation-gate.md` 与 `docs/archive/release-notes/90-release-notes-stage28-filtered-snapshot-host-consumer-validation-gate.md`。
- 旧 `docs/09-policy-checker-poc-plan.md` 已完整移入 `docs/archive/09-policy-checker-poc-plan.md`；活跃文档保持 50 个。
- 2026-07-16 Stage 29 已按 TDD 实现 `tools/codex_desktop_filtered_snapshot_consumer.py`：标准库-only、stdin-only、1 MiB 输入、64 KiB 输出，不自动启动 reader。
- consumer 固定 11 项检查，独立重算 scope/filter/view identity，严格验证 safe sections、counts、matched/status 与 task/request filter semantics；base/envelope/handoff identity 只关联检查。
- 新增 `tests/test_codex_desktop_filtered_snapshot_consumer.py`，覆盖 valid/blocked/validation_failed/error、输入门禁、value-safe determinism、禁止依赖与真实 reader → consumer stdio smoke。
- Stage 29 事实源：`docs/89-codex-desktop-filtered-snapshot-consumer-implementation.md` 与 `docs/archive/release-notes/91-release-notes-stage29-codex-desktop-filtered-snapshot-consumer.md`。
- 早期 `docs/14-task-runtime-bridge.md` 已完整移入 `docs/archive/14-task-runtime-bridge.md`；活跃文档保持 50 个。
- Stage 20 实现文档已完整归档至 `docs/archive/81-codex-desktop-read-only-adapter-implementation.md`；活跃文档保持 50 个。
- Stage 21 历史 validation-only 设计门已被 Stage 22 及后续事实源取代，完整归档至 `docs/archive/82-read-only-representation-read-design-gate.md`；活跃文档仍为 50 个。

### Stage 10 基线（保留）

- `adapters/adapters.sample.json` 是 adapter/capability/risk 的单一事实源。
- `agent_runtime.adapter_registry` 提供 source-backed 投影，供 `orchestration adapter list/inspect`、route preview、preflight 共同消费。
- 投影字段包括 adapter_id、display_name、kind、capabilities、risk_level、enabled、功能开关（background/artifacts/approval_roundtrip 等）、timeout_profile、指向该 entry 真实 input/output schema 的 JSON Pointer。
- route preview 与 preflight 基于此投影生成路由决策，避免查询 registry 与路由 registry 漂移。

### 新进落地：Stage 11 — Capability Routing Model 约束路由第一版

- `RouteConstraints` 已接入 `orchestration route preview` / `orchestration preflight`。
- 支持约束：`--preferred-adapter`、`--max-risk`、`--require-background`、`--require-artifacts`。
- 路由流程：capability match → constraint filter → preference rank。
- 默认未传约束参数时，route/preflight 保持原有输出字段不变；仅在显式使用约束 flag 时才输出 `routing_constraints` / `rejected_candidates` 等新增字段。
- 新增 `--explain` 决策解释 trace：暴露 capability-matched / constraint-rejected / eligible / selected / fallback 候选及 deterministic reason，trace 由 `preview_route` 内部中间结果直接构造，preflight 复用不复算，为 Stage 12 状态模型做准备。

### 新进落地：Stage 12 — Control Plane State Model 第一拍

- 新增 `RoutingDecisionSnapshot`：把 Stage 11 route/preflight 决策投影为稳定、compact、只读的控制面状态对象。
- `snapshot_id` 由 canonical safe payload 的 SHA-256 内容哈希确定性生成，无时间戳/随机数/进程状态。
- CLI：`orchestration route snapshot` 与 `orchestration preflight --snapshot`。
- snapshot 包含分层的 routing 状态与 guardrail 状态（preflight snapshot），不写 ledger、不生成持久 Run、不执行真实 adapter。

### 新进落地：Routing Snapshot → Run Preview 安全引用第一拍

- `orchestration run --dry-run` 新增可选 `--routing-snapshot-id sha256:<64hex>`。
- 引用只接受 `sha256:<64 lowercase hex>` 格式；非法值返回 `needs_input`，绝不读取任意路径或把 JSON 当参数。
- 引用进入 `RunDryRunResult`、candidate artifact refs、`run_planned` candidate event metadata keys 与 `plan_hash` canonical payload。
- 默认不传时旧输出与 `plan_hash` 完全兼容；传入时相同输入重复运行产生 byte-equivalent JSON，`plan_hash` 随 snapshot id 变化。
- retry / fallback dry-run 同样支持引用，lineage 与 routing snapshot 各自独立。
- 不校验 snapshot 是否存在于磁盘，明确其为 content-addressed reference contract，不是持久化产物假装已落地。
- 文档已更新：`docs/50-control-plane-state-model.md`、`docs/52-minimal-orchestration-loop.md`、`docs/02-roadmap.md`、`docs/10-cli-poc-usage.md`。

- preflight 将 routing decision passthrough 到 guardrail，不越界替 guardrail 做阻断判断。
- cost / latency / availability / 在线状态仍未实现，保留给后续阶段。

### 新进落地：Run Preview → Event / Report 只读投影闭环

- `orchestration run --dry-run --snapshot` 基于真实 `RunDryRunResult` 一次性构造 `OrchestrationReadLoopSnapshot` 只读闭环 snapshot。
- snapshot 包含 Run Preview（`status=planned/preview`）、candidate Event summaries（`status=planned`，不伪造 event_id/timestamp）、Report Preview（`status=preview`，无持久 report_id）。
- `snapshot_id` 由最终安全 payload（去掉 `snapshot_id`）的 canonical SHA-256 哈希确定性生成，无时间戳/随机数/进程状态。
- 默认不传 `--snapshot` 时，`orchestration run --dry-run` 旧输出与 `plan_hash` 严格兼容；传入时仅新增 snapshot 字段。
- `--commit` 模式下传入 `--snapshot` 会被明确拒绝（`blocked`），本拍仅 `--dry-run` preview 支持。
- 不写入 ledger、不生成持久 Run/Event/Report、不执行真实 adapter；明确为 ephemeral read model。
- Routing Snapshot → Run Preview → Event/Report read-only loop 已闭合，但仍明确非持久/非执行。


### 新进落地：Recovery Lineage Aggregation Read Model

- 新增 `agent_runtime/orchestration_recovery.py`，以现有 `run_planned` / `run_draft_exported` / `run_blocked` event metadata 为索引，确定性聚合同一 recovery chain。
- `orchestration run inspect --aggregate-lineage` 与 `orchestration report generate --aggregate-lineage` 输出 root request、leaf/latest request、attempt count、effective plan hash 与安全 request summaries。
- 多 leaf 不静默猜测 latest，返回 `needs_input`；missing/cross-task parent、cycle、重复 metadata 冲突返回 `validation_failed`。
- 默认未传 flag 时现有 inspect 输出保持兼容；不扫描 drafts、不增加事件类型、不写 ledger、不执行 adapter。
- 设计入口：`docs/73-recovery-lineage-aggregation-read-model.md`。

## 现在已经能做什么

- 已冻结里程碑 `v0.12.1-orchestration-read-loop-snapshot`（commit `0419a04`），包含 Stage 10–12 的 registry/routing/state read model 闭环。
- `orchestration run --dry-run` 可安全引用 `orchestration route snapshot` / `orchestration preflight --snapshot` 的内容寻址 snapshot id
- retry / fallback commit 第一版已落地
- `orchestration run inspect` 可见 lineage
- `orchestration run list` 可见紧凑 lineage 标识
- `orchestration report generate` 可见 lineage 安全摘要
- `python -m agent_runtime.cli docs context` 可输出恢复入口
- `orchestration contract inspect --json` 可供脚本确定性发现当前 CLI 能力、关键 flag 与不可用边界
- `orchestration contract check --require ...` 可供脚本在执行前做 requirement negotiation，不执行被声明的 command
- `orchestration profile list/inspect/check` 可复用版本化的 CI read-only、local dry-run 与 controlled-write preparation profiles
- `orchestration control-panel snapshot/render/handoff` 可输出确定性 snapshot、自包含只读 HTML 与版本化 stdio descriptor；可选 envelope 只用于投影 scoped run/approval/artifact
- `orchestration adapter list` / `inspect` 可查询 source-backed adapter capability registry；`orchestration route preview` / `orchestration preflight` 已基于同一投影生成路由与 preflight 决策

## 下次恢复顺序

1. 先读：`docs/000-stage-digest.md`（本文件）
2. 再读：`docs/92-filtered-snapshot-markdown-display-consumer-validation-gate.md`
3. 再读：`docs/archive/91-codex-desktop-filtered-snapshot-markdown-display-integration-and-milestone-freeze.md`
4. 再读：`docs/archive/90-codex-desktop-filtered-snapshot-host-integration-and-milestone-freeze.md`
5. 再读：`docs/89-codex-desktop-filtered-snapshot-consumer-implementation.md`
6. 再读：`docs/87-filtered-envelope-snapshot-json-reader-implementation.md`
7. 再读：`tasks/handoff-2026-07-16.md`
8. 再读：`docs/88-filtered-snapshot-host-consumer-validation-gate.md`
9. 再读：`docs/86-filtered-envelope-snapshot-read-design-gate.md`
10. 再读：`docs/84-envelope-scoped-snapshot-read-design-gate.md`
11. 再读：`docs/83-codex-desktop-snapshot-json-reader-implementation.md`
12. 需要 Stage 36 验收事实时读：`docs/archive/release-notes/97-release-notes-stage36-filtered-snapshot-markdown-display-consumer-validation-gate.md`
13. 需要 v0.15 验收事实时读：`docs/archive/release-notes/96-release-notes-v0.15.0-filtered-snapshot-display-integration.md`
14. 需要 Stage 34/33 验收事实时读 release notes 95/94。
15. 需要 v0.14/Stage 30–31 验收事实时读 release notes 93/92。
16. 再跑：`python -m agent_runtime.cli docs context --json`

## 下一步做什么

- **Stage 37 — Filtered Snapshot Markdown Display Consumer Implementation（条件启动）**
- 必须先写 RED tests，再实现标准库-only、stdin-only validator。
- ready 时独立重算 content hash，并验证固定 Markdown grammar、安全 ASCII JSON literal、identity/count/filter/empty-view coherence。
- non-ready 只验证 withheld contract；不启动 display/host/reader，不复制 content。
- Stage 37 验收后进入 Stage 38 milestone freeze，候选 tag 为 `v0.16.0-filtered-snapshot-display-consumer`。
- 专有 UI、HTML/browser、file/URL、network/service、persistence/export、写操作与真实 execution 继续 unavailable。

## 重要约束

- 仍然**不做真实 adapter execution**
- Stage 16–36 只允许**本地静态只读表示、stdio descriptor、stdin-only validation、one-shot host adapter、显式 project/envelope-scoped snapshot JSON read、结构化 filtered v3、内存展示契约与独立 filtered consumer 、validation-before-display one-shot host 与 escaped deterministic Markdown display**；仍然不做 live service、DB、auth、网络访问、UI 写操作、HTML/browser 自动读取、通用 query、持久化/export 或真实 adapter execution
- 后续实现可由任意受控编码 Agent 承担，但必须先消费本 digest、91、archive/release-notes/96、95、94、archive/90、89/88/87/86/85/84/83/79/78/76 与 archive/77 事实源与最新 handoff；Stage 20/21/19 历史实现与设计按需读取 archive/81、archive/82 与 archive/80，并保持验证/提交边界

## 一句话理解当前项目

这项目现在的重点不是继续堆零散功能，而是：

> 在不服务化的前提下，把现有 CLI/read models 收敛为稳定、可由未来入口复用的后端资源与操作契约。
