# 02 — 路线图

## 路线图说明

`s-black harness engineering` 是一个长期项目。

它的最终目标不是单做“规则门禁”，而是建设一个面向多 Agent、多工具、多渠道的**中枢运行台（Orchestration Hub / Control Plane）**。当前已经做出来的 policy、ledger、controlled write、freeze、verification 等能力，属于这个中枢台的**安全与审计内核**。

因此后续路线图分为两条并行主线：

- **主线 A：安全与审计内核**
- **主线 B：中枢台接入与编排**

## 版本治理说明

当前仓库最新里程碑基线为 `v0.14.0-filtered-snapshot-host-integration`（commit `dfae346`，annotated tag 与 `main` 已推送）。上一基线为 `v0.13.0-read-only-control-plane`（commit `f401b98`，已 push）。

从 orchestration 阶段开始，项目持续使用 `docs/55`、`docs/57`、`docs/59`、`docs/61`、`docs/65`、`docs/67`、`docs/72` 这类**阶段编号 + release notes**来完成阶段收口，而 semver/tag 改为只在里程碑节点冻结。

这表示版本治理已经从“过渡态”进入“已执行态”：

- release notes 与阶段文档持续更新；
- semver/tag 不再逐阶段增长；
- `docs/64-versioning-governance.md` 定义的“阶段推进 + release notes 收口 + 里程碑打 tag”策略，已经在 `v0.12.0-orchestration-foundation`、`v0.12.1-orchestration-read-loop-snapshot`、`v0.13.0-read-only-control-plane` 与 `v0.14.0-filtered-snapshot-host-integration` 四次得到实际执行。

两条主线并行推进，但优先级上仍遵循：先把底层边界和状态模型打稳，再逐步放开接入、编排和未来 UI 可操作性。

---

## Stage 0 — 项目骨架（已完成）

目标：建立稳定的项目根目录、基础说明文件和长期推进账本。

已交付：

- `README.md`
- `README.en.md`
- `docs/01-vision-and-boundaries.md`
- `docs/02-roadmap.md`
- `tasks/progress.md`
- `decisions/0001-project-location.md`

结果：仓库骨架、文档入口和长期推进方式建立完成。

---

## Stage 1 — 通用规则模型（已完成）

目标：把 Orchestrator、Media Agent、Memory Agent 的 harness 经验，抽象成可复用的规则格式。

已完成内容：

- `policy schema`
- 路径归属、secret scan、危险命令、只读区、外发前检查等规则类型
- Orchestrator / Media Agent / Memory Agent 样例 policy
- 硬门禁与提醒项分层

结果：中枢台的规则表达层已形成第一版基础。

---

## Stage 2 — 任务账本（已完成）

目标：定义任务如何被提交、执行、阻塞、恢复和完成。

已完成内容：

- 任务状态模型：`planned`、`running`、`blocked`、`finished`、`failed`
- `task schema` / `event schema`
- JSONL 样例 ledger
- ledger 校验与一致性检查基础

结果：中枢台的最小 task / event 状态沉淀模型已具备。

---

## Stage 3 — Agent 注册表（已完成）

目标：在 Runtime 外部清楚记录有哪些 Agent、各自能力和边界。

已完成内容：

- agent registry schema
- sample registry
- capability / workspace / boundary / policy profile 等字段
- Agent 间委派与验收关系基础表达

结果：中枢台具备了最小 Agent 元数据层。

---

## Stage 4 — 工具适配器层（已完成第一轮设计）

目标：不再把工具能力绑死在某一个宿主框架里，而是抽象成 adapter。

已完成内容：

- adapter schema
- adapter sample registry
- adapter execution envelope 设计
- runtime gate / report / inspect / validate 等围绕 adapter 的只读链路

当前结论：

- 这一阶段已经有足够多的设计积木
- 但“统一接入中枢台”的总叙事还需要继续补强

---

## Stage 5 — 最小 Runtime CLI（已完成）

目标：做出第一个能跑的命令行入口。

已完成内容：

- `doctor`
- `check text`
- `check path`
- `check action`
- `agents list`
- `adapters list`
- `policies list`
- `task status`
- `task events`
- `task validate`
- `task check-ledger`

结果：仓库已经从纯文档阶段进入可运行的最小 Runtime CLI 阶段。

---

## Stage 6 — Runtime 只读检查链路（已完成）

目标：把 runtime 相关检查链路串起来，但仍保持只读。

已完成内容：

- `runtime plan`
- `runtime draft validate`
- `runtime draft inspect`
- `runtime gate check`
- `runtime report`
- adapter envelope plan / validate / inspect / approval / response / gate check

结果：中枢台的只读 runtime 主线已经跑通。

---

## Stage 7 — 受控写入基础（已完成）

目标：允许最小、可审计、可回滚的项目内写入，而不是一步到位放开执行能力。

已完成内容：

- `runtime draft export --dry-run / --commit`
- `runtime event append --dry-run / --commit`
- `runtime task create --dry-run / --commit`
- controlled write boundaries
- controlled write regression

结果：中枢台已经具备最小受控写入能力，但仍未接入真实外部执行。

---

## Stage 8 — Runtime Event Import 能力包（已完成 v0.11）

目标：把批量候选 event 安全导入现有 event ledger。

已完成内容：

- `runtime event import --dry-run`
- `runtime event import --commit`
- `--expected-plan-hash` consistency freeze
- `--require-dry-run` strict freeze mode
- event import controlled write regression coverage
- `v0.11.0-runtime-event-import`

结果：受控写入链路已经从单条 append 扩展到批量 import，并补上审阅上下文一致性约束。

---

# 下一阶段：从“门禁内核”走向“中枢台后端”

到当前为止，项目最大的风险不是底层能力不足，而是项目叙事容易被误解成“只是在做门禁”。

因此下一阶段不应继续盲目深挖局部门禁细节，而应开始补齐**中枢运行台后端主线**。

---

## Stage 9 — 中枢台定位校正与总蓝图（已完成）

目标：明确项目不是单纯 guardrail 工具，而是一个中枢运行台；guardrail 只是其安全与审计内核。

本阶段要做的事：

- 补一份中枢台总蓝图文档
- 明确“接入层 / 编排层 / 状态层 / 门禁内核 / 观察层”五层结构
- 在 README 中加入全景图和新定位说明
- 调整路线图，把后续工作拆成“安全内核”和“中枢台后端”双主线

主要交付物：

- `docs/47-orchestration-hub-vision.md`
- `README.md` / `README.en.md` 定位修正
- `docs/02-roadmap.md` 细化

---

## Stage 10 — Adapter Runtime Interface（第一版已落地，持续巩固）

目标：定义中枢台如何以“积木式可插拔”方式统一接入 Agent、工具和外部系统，而不是每个工具各写一套调用方式。

要做的事：

- 定义 adapter 分类：agent / tool / service
- 定义统一 adapter metadata
- 定义统一 request / response / artifact / evidence / error 模型
- 定义 approval roundtrip、timeout、cancel、background 等语义
- 对现有 QwenPaw / Kimi / Claude / OMP / Shell / GitHub / Lark / WebBridge 做能力映射草案

主要交付物：

- `docs/48-adapter-runtime-interface.md`（已更新 registry 投影落地说明）
- `agent_runtime/adapter_registry.py`：从现有 `adapters/adapters.sample.json` 投影 Stage 10 元数据
- `agent_runtime/orchestration_adapter.py`：只读 read model
- CLI：`orchestration adapter list` / `orchestration adapter inspect <adapter_id>`
- 测试：`tests/test_adapter_registry.py`、`tests/test_orchestration_adapter.py`

已落地能力：

- **单一事实源**：`orchestration adapter list/inspect` 与 `orchestration route preview` / `orchestration preflight` / `runtime plan` / `adapters list` 共用同一 `adapters/adapters.sample.json`。
- **投影已被路由消费**：`orchestration route preview` 与 `orchestration preflight` 现在直接消费该 source-backed registry 投影，routing 候选集与 registry 查询同源。
- 从 legacy registry 确定性投影 Stage 10 字段，并清楚标识 derived/defaulted 来源。
- `input_schema_ref` / `output_schema_ref` 为指向该 entry 内嵌 schema 的真实 JSON Pointer（`adapters/adapters.sample.json#/adapters/<index>/input_schema|output_schema`）。
- 不过滤 disabled entries，与 `loader.load_adapters` 同批条目语义一致。
- 列表稳定排序、支持按 `type` / `risk` / `capability` 过滤。
- inspect 输出完整元数据（含 derived 映射与 source_index），未知 ID 返回 `needs_input`。
- 缺文件、非法 JSON、schema 不匹配、结构损坏均以安全 findings 返回，不 traceback。
- 保持只读、确定性、无真实 adapter execution、无网络/凭据/UI/DB。

仍后续：

- 若未来为每个 adapter 补齐独立 input/output schema 文件，再更新 schema ref 指向这些真实文件。

---

## Stage 11 — Capability Routing Model（约束路由与 decision trace 第一版已落地）

目标：在 Stage 10 source-backed registry 投影基础上，继续把 capability-level routing 抽象做扎实，让上层任务调度优先面向 capability，而不是硬编码具体工具名。

要做的事：

- 设计 capability 命名方式
- 设计 routing 输入 / 输出模型
- 设计 capability match / constraint filter / preference rank 三层路由过程
- 明确 fallback 机制
- 明确 routing 与 guardrail 的边界

主要交付物：

- `docs/49-capability-routing-model.md`

已落地能力：

- constraint filter + preference rank 第一版。
- CLI flags：`--preferred-adapter`、`--require-background`、`--require-artifacts`、`--max-risk`。
- `orchestration route preview` 与 `orchestration preflight` 已消费 `RouteConstraints` 并返回带约束的 routing decision。
- 新增 `--explain` 决策解释 trace：暴露 capability-matched / rejected / eligible / selected / fallback 候选与 deterministic reason，trace 由 routing 内部中间结果直接构造，preflight 复用不复算，为 Stage 12 状态模型提供可消费输入。
- preflight 把 routing 决策 passthrough 到下游 guardrail / runtime plan，保持 routing 与 guardrail 边界清晰。

仍后续：

- cost / latency / availability 在线打分。
- 真实 runner 在线状态感知。
- 自动化 fallback / retry 执行（当前仅输出 fallback 链，不自动切换）。

---

## Stage 12 — Control Plane State Model（已完成）

目标：把未来 CLI、UI、自动化共同依赖的状态对象讲清楚，并把路由/preflight 决策沉淀为可消费的控制面状态。

完成范围：

- Task / Event / Run / Approval / Artifact / Evidence / Report 的关系、职责和顶层/附属分类已在 50/51 中冻结。
- `RoutingDecisionSnapshot`、routing snapshot 引用和 `OrchestrationReadLoopSnapshot` 已形成确定性、内容寻址、只读投影。
- recovery lineage 已通过 inspect/report 双入口聚合，并由跨入口 contract tests 锁定状态、异常、脱敏和 no-write。
- collection-level lineage 经评估无明确消费者，本阶段不实现 index，不改造 envelope-scoped `run list`。

正式延期：

- 持久化 Run/Event/Report storage 与数据库/service 实现；
- HTTP/RPC、鉴权、UI 与真实 adapter execution。

冻结状态：

- 第一拍冻结：`v0.12.1-orchestration-read-loop-snapshot`（`0419a04`，已 push）。
- Stage 12 最终验收已通过；最终 release notes：`docs/archive/release-notes/75-release-notes-stage12-control-plane-state-model.md`。
- 本次按阶段 release notes 收口，不创建新的 semver tag。

主要交付物：

- `docs/50-control-plane-state-model.md`
- `docs/73-recovery-lineage-aggregation-read-model.md`
- `docs/74-recovery-lineage-report-reuse.md`
- `docs/archive/release-notes/75-release-notes-stage12-control-plane-state-model.md`

---

## Stage 13 — Backend-first API Boundary（已完成）

目标：虽然现在不急着做 UI，但后端必须先按未来可被 UI 调用的方式设计。

要做的事：

- 定义未来 UI / CLI / automation 共同依赖的 API 边界
- 先做资源模型，不急着选 HTTP / RPC / 本地进程协议
- 明确任务列表、任务详情、run 详情、approval 操作、dry-run / commit、report 的统一接口草案

主要交付物：

- `docs/51-backend-first-api-boundary.md`

完成状态：

- 真实 CLI/read models 已映射为 stable、stable（受限）、preview、unavailable 契约。
- `tests/test_orchestration_boundary_contract.py` 已冻结命令集合与关键 flag 边界。
- 默认输出兼容、preview/no-write、determinism 和 recovery lineage 跨入口测试已通过。
- 最终 release notes：`docs/archive/release-notes/76-release-notes-stage13-backend-first-api-boundary.md`。
- 本阶段不选择协议、不引入鉴权/service/DB/UI、不执行真实 adapter；本次不创建新 semver tag。

---

## Stage 14 — 中枢台最小编排闭环（已完成；2026-07-13 收口）

目标：在后端抽象稳定后，跑通第一个真正体现“中枢台”特征的最小闭环。

主要交付物：

- `docs/52-minimal-orchestration-loop.md`
- `docs/53-minimal-orchestration-loop-cli-draft.md`（命令面草案参考，非正式 API 边界）

实施入口（已完成）：将 Stage 13 已冻结的 stable/preview/unavailable 契约应用到最小闭环的 use-case 与回放验证；全过程保持不选 HTTP/RPC、不启动 service、不执行真实 adapter。

已完成收口：七步闭环入口、read-loop Evidence projection、显式 replay projection、结构化 next_action、跨入口一致性、默认兼容、确定性、脱敏、no-write 和 rollback 均已冻结；release notes 见 `docs/archive/release-notes/77-release-notes-stage14-minimal-orchestration-loop.md`。

Post-Stage 14 CLI 自动化消费者增量（2026-07-14）：

- 新增 `orchestration contract inspect` 机器可读契约发现入口；
- 使用 `control-plane/orchestration-contract/v1` 投影 stable/stable_limited/preview/unavailable 矩阵；
- command argv 与关键 flag 由契约测试反向校验真实 argparse surface；
- 只读、确定性、no-write、no-network、no-adapter-execution，不启动新的产品 Stage；
- 设计事实源：`docs/75-cli-automation-contract-discovery.md`。
- 第二拍新增 `orchestration contract check` requirement gate：支持 requirement 去重排序、preview 显式 opt-in、access ceiling、结构化 next action 与退出码；继续保持纯只读。
- 第三拍新增 `orchestration profile list/inspect/check`：source-backed 命名化 requirements，复用同一 gate，doctor 校验 schema/sample，仍不执行 workflow。
- 第四拍新增 `orchestration workflow plan --profile-id ...`：gate 通过后按固定 phase 投影 manifest-backed command/flag 候选，生成内容寻址 `plan_id`；步骤全部为 `not_executed`，不写文件或 ledger。
- 第五拍新增 `orchestration workflow check --expected-plan-id ...`：重投影并比较 content hash，match 为 pass，drift 为 blocked；不读取旧 plan 文件、不执行步骤。
- CLI 自动化消费者已完成五拍收口；验收见 `docs/archive/release-notes/78-release-notes-cli-automation-consumer.md`，不自动启动新的产品阶段。

候选闭环：

- 提交 task intent
- 中枢台做 capability routing（49）
- 执行 guardrail preflight（不阻塞闭环设计，只决定执行模式）
- 按 dry-run / commit 模式执行 adapter（48）
- 沉淀 task / event / run / artifact / evidence（50）
- 如需审批，创建 approval request 并暂停等待决议
- 生成 report，给出 next_action

要求：

- 不破坏现有工作流
- 有 capability-level fallback
- 有 report
- 有 evidence
- 可回放
- 不进入真实多系统放权、UI、服务化、数据库选型

---

## Stage 15 — UI / 看板前的后端准备（read-model CLI 第一版已落地，前端实现仍暂缓）

目标：在不急着做前端的前提下，先把未来看板所需后端对象和操作面准备齐。

主要交付物：

- `docs/54-backend-preparation-before-ui.md`
- `docs/archive/release-notes/55-release-notes-orchestration-read-models.md`
- 十只读 `orchestration *` CLI 命令（见 55）

要做的事：

- 梳理“总览页、任务页、执行页、审批页、产物页、报告页”分别需要哪些状态对象
- 确认 CLI 输出与状态模型的映射关系
- 为每一类页面提供最小只读 CLI read model

已落地能力：

- 总览页：`orchestration overview`
- 任务页：`orchestration task list` / `orchestration task get`
- 执行页：`orchestration run list` / `orchestration run inspect`
- 审批页：`orchestration approval list` / `orchestration approval get`
- 产物页：`orchestration artifact list` / `orchestration artifact get`
- 报告页：`orchestration report generate`

说明：

- 这一阶段仍以“后端先行”为原则
- 不是现在马上做 Web UI，也不是做服务/数据库
- 所有 read model 都是只读 CLI，不写 ledger、不执行 adapter、不访问网络
- Run / Approval / Artifact 当前为 envelope-scoped；Report 为 runtime-report-backed，均未引入独立持久集合

---

## Stage 15.5 — Orchestration 受控写入边界（第一批 controlled handoff / approval resolve 已落地）

目标：在进入第一批 orchestration 写入命令前，先把 dry-run / commit 语义、capability routing handoff、approval resolve 安全边界定清楚，并实际落地第一批 handoff / controlled-write 命令。

主要交付物：

- `docs/56-orchestration-controlled-write-boundary.md`（design gate）
- `docs/archive/release-notes/57-release-notes-orchestration-controlled-handoff.md`
- `orchestration route preview`（只读 capability routing preview）
- `orchestration preflight`（只读 routing + guardrail 聚合）
- `orchestration approval resolve`（event-ledger append 方案受控写入）

已落地能力：

- `route preview` 输出安全 routing decision，为 `preflight` / `runtime plan` 提供输入。
- `preflight` 聚合 routing + guardrail，明确 `effective_mode`、`requires_approval`、`requires_dry_run`。
- `approval resolve` 只记录 decision，不执行原请求；`--dry-run` 预览 event，`--commit` 追加 `approval_resolved` event 到 ledger；granted 后仍需重新发起 preflight/run。
- `tasks/event.schema.json` 新增 `approval_resolved` event_type。

要做的事（仍保留）：

- 明确 `orchestration run --dry-run/--commit` 的 draft/export 产物形态和 freeze guard。
- 明确 `orchestration task submit --commit` 与现有 `runtime task create --commit` 的关系。
- 在 retry / fallback 自动化进入实现前，先确认 run 侧状态沉淀规则。

说明：

- 本阶段先实现只读 handoff 命令，再实现第一条受控写入命令；`orchestration run --commit` 已在 Stage 15.8/15.9 升级到 A+B，retry / fallback、真实 adapter execution 仍未开放。
- 不标记 Stage 16 开始；Stage 16 仍保持远期。
- 完成本阶段后，下一步建议先明确 run draft/export 产物形态，再进入 Stage 14/15.7/15.8 run 侧实现。

---

## Stage 15.6 — Orchestration Run 受控执行设计（design gate，进入 run 实现前）

目标：在实现 `orchestration run --dry-run / --commit` 之前，先定义 run 的产物形态、freeze guard、event/artifact/evidence 沉淀规则和 rollback 策略，避免匆忙开放 run 写入。

主要交付物：

- `docs/58-orchestration-run-controlled-execution-design.md`

要做的事：

- 定义 `orchestration run --dry-run` 输出：routing summary、preflight summary、candidate envelope/events summary、artifact/evidence refs、稳定 `plan_hash`。
- 定义 `orchestration run --commit` 产物策略：优先 envelope draft export（A），配合 run lifecycle events append（B），all-or-nothing 回滚。
- 定义 freeze guard：`--expected-plan-hash` 覆盖 task_id、request_id、capability、adapter_id、operation、target 摘要、mode、routing、preflight、candidate envelope/events 指纹；mismatch 返回 `blocked`。
- 定义 approval handoff：preflight `needs_approval` 时 commit 不写产物；已有 `approval_resolved` event 仍需重新 preflight。
- 明确 state model mapping：Run 暂不独立持久，由 `(task_id, request_id, envelope_path)` + run lifecycle events 代理；Artifact/Evidence 仍 envelope-scoped；Report 仍 runtime-report-backed。
- 明确 rollback / post-check：draft export 失败删除新文件，event append 失败按 byte size 回滚，post-check 包括 schema / ledger consistency / runtime audit / public scan。

说明：

- 本阶段是 design gate，不新增代码实现。
- 若进入实现，先在 `tasks/event.schema.json` 新增候选 event types（如 `run_planned`、`run_draft_exported`、`run_blocked`）并补测试。
- 不实现 `orchestration task submit --commit`、retry / fallback、真实 adapter execution。
- 不标记 Stage 16 开始；Stage 16 仍保持远期。

---

## Stage 15.7 — Orchestration Run Dry-run 落地

目标：实现只读的 `orchestration run --dry-run`，输出 run plan preview 与稳定 `plan_hash`。

主要交付物：

- `agent_runtime/orchestration_run_dry_run.py`
- `tests/test_orchestration_run_dry_run.py`
- `docs/10-cli-poc-usage.md` / `docs/53-minimal-orchestration-loop-cli-draft.md` 更新

已落地能力：

- `orchestration run --dry-run` 聚合 routing + guardrail preflight + runtime plan 安全摘要。
- 输出 candidate envelope/events/artifact/evidence refs 与 `plan_hash`。
- 不写 ledger、不写 envelope/draft、不执行 adapter、不访问网络。

说明：

- `--commit` 仍标记为未实现；传入返回 `needs_input`。
- 不标记 Stage 16 开始。

---

## Stage 15.8 — Orchestration Run Commit（A-only 第一版）落地

目标：实现 `orchestration run --commit` 第一版 A-only controlled write，把已审阅 run plan 沉淀为 envelope draft 文件。

主要交付物：

- `agent_runtime/orchestration_run_commit.py`
- `tests/test_orchestration_run_commit.py`
- `docs/archive/release-notes/59-release-notes-orchestration-run-controlled-execution.md`
- `docs/10-cli-poc-usage.md` / `docs/53-minimal-orchestration-loop-cli-draft.md` / `docs/58-orchestration-run-controlled-execution-design.md` 更新

已落地能力：

- `orchestration run --commit` 必须提供 `--output` 与 `--expected-plan-hash`。
- commit 前重新 dry-run/preflight；非 `pass` 状态不写，hash mismatch 不写。
- 复用 `runtime_draft_export` 受控写入机制：路径校验、scan、写入、post-check、失败回滚。
- 产物为 `drafts/runtime/.../*.json` envelope draft；不覆盖已存在文件。

仍后续：

- retry / fallback 自动化。
- `orchestration task submit --commit`。
- 真实 adapter execution、网络访问、消息发送、UI/服务/数据库。

说明：

- 不标记 Stage 16 开始；Stage 16 仍保持远期。

---

## Stage 15.9 — Orchestration Run Lifecycle Events 落地

目标：把 `orchestration run --commit` 从 A-only envelope draft export 升级为 A+B controlled write，在不放开真实 adapter execution 的前提下，为 run 沉淀最小 lifecycle event trail。

主要交付物：

- `docs/60-orchestration-run-lifecycle-events-design.md`
- `docs/archive/release-notes/61-release-notes-orchestration-run-lifecycle-events.md`
- `tasks/event.schema.json` enum 扩展
- `agent_runtime/orchestration_run_commit.py`
- `tests/test_orchestration_run_commit.py`
- `tests/test_task_validation.py`

已落地能力：

- `orchestration run --commit` 必须显式提供 `--events-file`；缺失返回 `needs_input`，不写 A/B。
- 成功路径执行 A+B：写入 envelope draft/export 文件，并追加 `run_planned` + `run_draft_exported` lifecycle events。
- B 写入后检查实际落盘的 events ledger：event schema validation、task/event ledger consistency、runtime ledger audit。
- B 失败时回滚 A（删除 draft）和 B（truncate events ledger 或删除本次新建 ledger 文件），保持 all-or-nothing。
- `tasks/event.schema.json` 新增 `run_planned`、`run_draft_exported`、`run_blocked` enum；第一版成功路径只写入前两者。
- CLI 输出新增 `events_file`、`appended_event_count` 与 `event_refs` 安全摘要。

仍后续：

- `run_blocked` 暂不写入 blocked/needs_approval/hash mismatch 路径。
- retry / fallback 自动化。
- `orchestration task submit --commit`（进入新的独立 design gate：`docs/62-orchestration-task-submit-controlled-write-design.md`）。
- 真实 adapter execution、网络访问、消息发送、UI/服务/数据库。

说明：

- 本阶段已经从 design gate 进入实现收口。
- `orchestration run --dry-run` / `--commit` 的 freeze guard 语义保持不变。
- 不标记 Stage 16 开始；Stage 16 仍保持远期。

---

## Stage 15.95 — Orchestration Task Submit Created Event 落地

目标：把 `orchestration task submit --commit` 从只写 task ledger 的 A-only 入口，升级为 A+B controlled write，使其真正对齐 `TaskCollection.create` 的“Task + 初始 Event”语义。

已完成范围：

- A：向 task ledger 追加新 task snapshot。
- B：向 event ledger 追加一条 `created` event。
- A+B：all-or-nothing rollback，不接受“task 已存在但没有 created event”或“created event 已存在但 task 不存在”的残留状态。
- 输出与 read model 一致性：补齐 task list/get 与 event timeline 的入口一致性，但仍不自动触发 route / preflight / run。
- 阶段收口文档：`docs/archive/release-notes/65-release-notes-orchestration-task-submit-created-event.md`。

说明：

- 本阶段已从 design gate 进入实现收口。
- `orchestration task submit --commit` 现在要求显式 `--events-file`，缺失则不写 A/B。
- retry / fallback、真实 adapter execution 仍未开放。
- 不标记 Stage 16 开始；Stage 16 仍保持远期。

---

## Stage 15.96 — Orchestration Run Retry / Fallback Dry-run 落地

目标：在 task submit 入口 A+B 与 run commit A+B 均已落地后，补齐恢复性执行分支的第一版只读 preview：`orchestration run --retry-of` 与 `orchestration run --fallback-from / --fallback-to`。

已完成范围：

- Retry：同一 task 下基于旧 request 重新生成新 run plan，新 request_id 必须不同于原 request_id，并通过 `retry_of` 关联。
- Fallback：同一 task 下切换到显式 fallback adapter，新 request_id 必须不同于原 request_id，并通过 `fallback_from` / `fallback_to` 关联。
- 每次 retry / fallback 都重新 route、preflight、dry-run，不信任旧 plan_hash 或旧 approval。
- `plan_hash` 纳入 lineage 字段，避免普通 dry-run、retry dry-run、fallback dry-run 共用同一 hash。
- 第一版仅实现 dry-run preview，不实现 retry/fallback commit。
- 不扩展 event schema enum，不引入独立 Run storage，不自动执行真实 adapter。
- 阶段收口文档：`docs/archive/release-notes/67-release-notes-orchestration-run-retry-fallback.md`。

说明：

- 本阶段已从 design gate 进入 dry-run preview 实现收口。
- retry/fallback commit 语义仍需另开设计。
- 不标记 Stage 16 开始；Stage 16 仍保持远期。

---

## Stage 15.97 — Orchestration Foundation Freeze 完成

目标：把 `v0.12.0-orchestration-foundation` 作为 orchestration foundation 的首个正式里程碑基线完成冻结，并为后续 post-freeze 文档整理与下一拍设计建立稳定起点。

已完成范围：

- 已新增 `docs/archive/68-orchestration-foundation-milestone-freeze-checklist.md`，明确候选能力包、验证证据与冻结前判定。
- 已新增 `docs/archive/69-orchestration-foundation-freeze-execution-plan.md`，记录冻结范围、建议 commit message、建议 tag、annotated tag message 与执行顺序。
- 已完成冻结前验证：全量 `pytest tests -q`、`doctor`、`public_scan`、`git diff --check`。
- 已完成实际冻结：commit `38b4b69`、tag `v0.12.0-orchestration-foundation`、push 完成。

说明：

- `68` / `69` 已完整归档到 `docs/archive/`，继续保留冻结前判断与执行方案的历史证据。
- 当前阶段已经不再是“等待 Git 动作”，而是进入 freeze 之后的文档收口与下一拍承接。
- 不标记 Stage 16 开始；Stage 16 仍保持远期。

---

## Stage 15.98 — Retry / Fallback Commit 落地

目标：在 retry / fallback dry-run preview 已落地、且 `v0.12.0-orchestration-foundation` 已冻结完成后，把恢复性分支的 commit 语义正式落成 lineage-aware 的受控写入能力。

已完成范围：

- retry commit 与 fallback commit 继续复用现有 `orchestration run --commit` 的 A+B 事务模型
- envelope metadata 与 lifecycle event metadata 已支持 `lineage_type`、`retry_of`、`fallback_from`、`fallback_to`
- retry/fallback commit 对 `--expected-plan-hash`、`--output`、`--events-file` 采用更严格要求
- 已补 source request 存在性校验、同 task 归属校验、重复 commit 防护与 rollback 边界
- 第一版复用现有 `run_planned` / `run_draft_exported` event_type，仅在 metadata 中表达 lineage
- 阶段设计与收口文档：`docs/70-orchestration-run-retry-fallback-commit-design.md`

说明：

- 本阶段实现的仍是受控写入，不是真实 adapter execution。
- lineage 已能被写入 envelope / lifecycle event metadata。
- 下一步自然转向 read model 对 lineage 的可见性与 recovery 聚合，而不是立刻进入真实执行。

---

## Stage 15.99 — Run Lineage / Recovery Read Model（历史编号，能力并入 Stage 12 post-freeze）

目标：让 retry / fallback lineage 不只是被写进去，还能被现有 orchestration read models 以安全、紧凑的方式读出来。

已完成范围：

- `orchestration run inspect` 已能输出 `lineage_type`、`retry_of`、`fallback_from`、`fallback_to`
- `orchestration run list` 已能在每条 run 摘要中显示紧凑 lineage 标识
- `orchestration report generate` 已补 lineage 安全摘要
- lineage 提取优先复用 envelope `adapter_request.context`，不引入新存储
- 阶段收口文档：`docs/archive/release-notes/71-release-notes-run-lineage-read-models.md`

说明：

- 本阶段仍不放开真实 adapter execution、独立 Run storage、DB、service 或 UI。
- recovery lineage 已形成“可写 + 单条可读”的最小闭环。
- 后续聚合能力已并入 Stage 12 post-freeze，并由 `docs/73-recovery-lineage-aggregation-read-model.md` 与 `orchestration run inspect --aggregate-lineage` 落地；该历史编号不再代表当前阶段。

---

## Stage 16 — Read-only Control Panel MVP（已完成）

目标：在不引入 service、DB、auth 或真实执行的前提下，把既有后端 read models 收敛成一个可观察、可审计的本地控制面。

第一拍已完成：

- `orchestration control-panel snapshot [--envelope ...]` 输出 `control-plane/control-panel-snapshot/v1`；
- `orchestration control-panel render [--envelope ...]` 向 stdout 输出自包含静态 HTML；
- 固定聚合 overview、tasks、adapters、automation、runs、approvals、artifacts、reports 八个区段；
- envelope 未提供时，scoped 区段诚实标为 unavailable，不伪造 collection；
- snapshot 内容寻址、确定性、只读、无网络、无写入、无命令/adapter 执行；
- industrial audit console 视觉、全局本地过滤、CSP、escaping、语义结构和窄屏适配均已验证。

设计与验收事实源：

- `docs/76-read-only-control-panel-mvp.md`
- `docs/archive/release-notes/79-release-notes-stage16-read-only-control-panel.md`

继续延期：

- live HTTP/API、auth/session、DB 与持久 collection；
- 实时刷新、WebSocket、在线 availability probe；
- UI 内 dry-run/commit/approval resolve 等写操作；
- 真实 adapter execution。

---

## Stage 17 — Control Panel Host Integration Boundary（已完成）

目标：为 Stage 16 的 snapshot / static HTML 定义一个宿主可消费、版本化、stdio-first 的只读 handoff contract，而不是直接进入 live service 或可写 UI。

第一拍实现：

- 新增 `orchestration control-panel handoff [--envelope ...] --json`；
- 复用现有 snapshot builder，输出 `control-plane/control-panel-handoff/v1`；
- 声明 snapshot/render representation、media type、encoding、renderer version、identity 与安全边界；
- descriptor 不内嵌 HTML、不写文件、不启动 server、不执行命令或 adapter；
- 将新命令并入现有 `control_panel_read` contract entry，并冻结跨入口一致性、确定性和 no-write。

设计事实源：

- `docs/78-control-panel-host-integration-boundary.md`
- `docs/archive/release-notes/81-release-notes-stage17-control-panel-host-handoff.md`

继续延期：

- controlled artifact export 与任意路径写入；
- 自动打开浏览器；
- live HTTP/API、auth/session、DB、实时刷新与在线 probe；
- UI controlled write 与真实 adapter execution；
- 特定宿主专有耦合。

Tag 策略：design gate 与单个 additive descriptor 不自动创建 tag；待形成稳定 host contract 与可验收消费者能力包后再评估里程碑冻结。

---

## Stage 18 — Read-only Host Consumer Validation（已完成）

目标：用一个与 producer 解耦的本地 reference consumer，验证 Stage 17 handoff descriptor 能被外部宿主安全校验，而不是直接进入专有宿主集成。

第一拍：

- 新增标准库-only `tools/control_panel_handoff_consumer.py`；
- stdin-only 读取单个 handoff JSON，最大 1 MiB；
- 严格校验 schema、handoff/render identity、representation metadata、argv shape 与安全 boundary；
- producer 非 pass、unsafe boundary 或 unsupported schema 不得伪装为可信 representation；
- consumer 不导入 producer builder、不读取项目资源、不执行 argv、不访问网络、不写文件。

设计与验收事实源：

- `docs/79-read-only-host-consumer-validation-boundary.md`
- `docs/archive/release-notes/82-release-notes-stage18-read-only-host-consumer-validation.md`

验收结果：标准库-only、stdin-only consumer 已独立验证 handoff schema、identity、representation metadata、argv shape 与安全 boundary；真实 producer 管道、确定性、脱敏和 no-side-effect 均已通过。

继续延期：Codex Desktop/QwenPaw 专有 bridge、representation 自动读取、live refresh/server、文件输入/export、UI 写操作与真实 adapter execution。

Stage 19 design gate 已冻结；Stage 20 已按设计落地 one-shot read-only adapter；下一拍进入 Stage 21 representation read design gate。


---

## Stage 19 — Host-specific Read-only Adapter Design Gate（已冻结）

目标：在不直接实现专有 bridge 的前提下，选择一个真实宿主候选并冻结 descriptor、validation result、生命周期、错误映射、授权和 representation 读取边界。

本阶段选择 **Codex Desktop 的本地任务进程边界**作为首个宿主候选，但不依赖未公开插件 API，也不在 `agent_runtime` 中新增 Codex Desktop 专有模块。冻结的 adapter contract 为：

```text
codex-desktop-read-only-adapter/v1
```

已冻结范围：

- 宿主只调用固定的 handoff bootstrap，接收 Stage 17 `control-plane/control-panel-handoff/v1`；
- descriptor 原样交给 Stage 18 stdin-only reference consumer，复用其 identity、shape、boundary 与脱敏校验；
- 生命周期为一次性 `created → producing → validating → ready/blocked/validation_failed/error → closed`；
- `pass` / `blocked` / `validation_failed` / `error` 的宿主状态映射、有限超时、取消和不自动重试语义；
- v1 不读取 snapshot/HTML representation，不执行 descriptor argv，不刷新、不写文件、不访问网络、不启动服务；
- 用户授权只覆盖指定 project root 内的一次只读 handoff validation，不扩展为 run、approval、artifact 或 adapter execution 授权。

设计事实源：

- `docs/archive/80-codex-desktop-read-only-adapter-design-gate.md`
- `docs/79-read-only-host-consumer-validation-boundary.md`
- `docs/78-control-panel-host-integration-boundary.md`

验收结论：Stage 19 design gate 已冻结，生产代码不变；Stage 20 才评估宿主侧实现与显式 representation read。

继续延期：Codex Desktop/QwenPaw 专有 bridge、descriptor argv 自动执行、representation 自动读取、live refresh/server、文件输入/export、UI 写操作与真实 adapter execution。

---

## Stage 20 — Host-specific Read-only Adapter Implementation（已完成）

目标：将 Stage 19 冻结的 Codex Desktop 本地任务进程边界落地为一次性、只读、可审计的宿主 adapter。

第一拍已完成：

- 新增 `tools/codex_desktop_read_only_adapter.py`；
- 只执行固定 handoff producer 与 Stage 18 reference consumer；
- 不执行 descriptor 中的 `snapshot.argv` / `render.argv`，不读取 representation；
- 固定一次性生命周期、超时/取消/不自动重试、1 MiB stdout 上限与最小子进程环境；
- 输出 `control-plane/codex-desktop-read-only-adapter/v1`，结果确定性、脱敏并映射 `ready` / `blocked` / `validation_failed` / `error`；
- 新增单元测试与真实本地 stdio smoke test。

设计与验收事实源：

- `docs/archive/81-codex-desktop-read-only-adapter-implementation.md`
- `docs/archive/release-notes/83-release-notes-stage20-codex-desktop-read-only-adapter.md`

继续延期：representation 自动读取、live refresh/server、文件输入/export、UI 写操作与真实 adapter execution。

---

## Stage 21 — Read-only Representation Read Design Gate（已完成）

目标：确认 Stage 20 validation-only adapter 是否已经具备安全、明确的 representation read 需求，并在实现前冻结授权与读取边界。

审计与决策已完成：

- Stage 17 descriptor 只声明 snapshot / HTML representation；
- Stage 18 reference consumer 与 Stage 20 host adapter 都只做 validation，不读取 representation；
- 当前没有已冻结的真实消费者、用户动作、representation 类型选择或授权需求；
- 自动读取与新增 `control-panel consume` 均被拒绝；
- 当前唯一允许的宿主行为冻结为 validation-only，不执行 descriptor argv，不读取 HTML/JSON，不打开浏览器、不写文件、不启动 service。

设计与验收事实源：

- `docs/archive/82-read-only-representation-read-design-gate.md`
- `docs/archive/release-notes/84-release-notes-stage21-read-only-representation-read-design-gate.md`

---

## Stage 22 — Codex Desktop Snapshot JSON Reader（已完成）

目标：为 Codex Desktop 本地任务进程提供第一个用户显式触发、一次性、有界的 snapshot JSON representation reader。

第一拍已完成：

- 新增 `tools/codex_desktop_snapshot_json_reader.py`；
- 用户必须显式选择 `--representation snapshot-json`；
- 固定执行 handoff producer → Stage 18 consumer → snapshot producer；
- 不执行 descriptor argv；
- 校验 snapshot strict JSON、schema、source、guarantees、handoff identity 与 canonical content hash；
- 输出 `control-plane/codex-desktop-snapshot-read/v1`，包含已验证的 snapshot payload；
- 一次性、确定性、1 MiB 有界、no-retry、no-write、no-network、no-service、no-adapter-execution；
- 新增目标测试与真实 Windows 三段 stdio smoke。

事实源：

- `docs/83-codex-desktop-snapshot-json-reader-implementation.md`
- `docs/archive/release-notes/85-release-notes-stage22-codex-desktop-snapshot-json-reader.md`

Stage 22 收口时继续延期 envelope 参数；该项已在 Stage 23/24 通过独立设计门与版本化 v2 实现。HTML、浏览器、文件 export、refresh/server、UI write 与真实 adapter execution 继续延期。

---

## Stage 23 — Envelope-scoped Snapshot Read Design Gate（已完成）

已冻结显式授权、project-relative envelope path allowlist、越界拒绝、输入大小/UTF-8/duplicate-key/schema/secret scan、scope identity、输出脱敏与 no-write/no-network/no-service 证据。事实源：`docs/84-envelope-scoped-snapshot-read-design-gate.md`。

---

## Stage 24 — Codex Desktop Envelope-scoped Snapshot JSON Reader（已完成）

已在既有 reader 上新增显式 `--envelope` scoped v2：

- 无 envelope 保持 Stage 22 v1；
- allowlist 仅为 `adapters/*.json` 与 `drafts/runtime/**/*.envelope.json`；
- 固定 handoff → consumer → snapshot 三段 argv；
- 输出 envelope content id / scope id，并校验 handoff/source/snapshot identity 与 one-shot content drift；
- 只返回 runs / approvals / artifacts 安全摘要；reports 继续 request-scoped unavailable；
- 不执行 descriptor argv、HTML、网络、service、写入或真实 adapter。

验收记录：`docs/archive/release-notes/86-release-notes-stage24-envelope-scoped-snapshot-json-reader.md`。

---

## Stage 25 — Envelope-scoped Consumer Integration / Filter Design Gate（已完成）

审计结论：当前没有具体 task/request filter 消费者，也没有足够事实冻结 filter 组合语义、canonical identity、排序/分页或持久化边界。因此 Stage 25 选择并冻结方案 C：

- 保持单个显式 envelope、无 filter 的 scoped v2；
- 不新增 `--task-id`、`--request-id`、`--filter`、`--query`、排序、分页或 export；
- 宿主只能一次性读取 `status=ready` 的 bounded stdout JSON，并在进程内展示既有安全摘要；
- 不执行 argv、不保存/cache/export、不打开 HTML/browser、不刷新/轮询、不访问网络或真实 adapter；
- Stage 24 v1/v2 schema、reader id、scope id 与 snapshot identity 保持兼容。

事实源：

- `docs/85-envelope-scoped-consumer-filter-design-gate.md`
- `docs/archive/release-notes/87-release-notes-stage25-envelope-scoped-consumer-filter-design-gate.md`

---

## Stage 26 — Filtered Envelope Snapshot Read Design Gate（已完成）

用户明确要求进入下一阶段后，已冻结未来 filtered v3：

- 只允许 canonical `--task-id` / `--request-id` exact filter，至少一个，双参数为 AND；
- filter 必须与显式 envelope 同时使用，非法/重复输入在 spawn 前失败；
- 只过滤已验证 snapshot 的 runs/approvals/artifacts 安全 summaries；
- task filter 使用 request→task 关系闭包，确保 response summaries 不因缺少直接 task_id 丢失；
- 合法无匹配返回 ready 空视图，不猜测或降级；
- 使用独立 v3 result、filtered payload schema、filter id 与 view id，不改变 v1/v2；
- child argv 不传 filter，继续 no query/persistence/export/HTML/browser/network/write/execute。

事实源：

- `docs/86-filtered-envelope-snapshot-read-design-gate.md`
- `docs/archive/release-notes/88-release-notes-stage26-filtered-envelope-snapshot-read-design-gate.md`

---

## Stage 27 — Filtered Envelope Snapshot JSON Reader Implementation（已完成）

已按 Stage 26 contract 在既有 reader 上实现：

- `--task-id` / `--request-id` canonical exact filter，双参数使用 AND；
- task filter 使用 request→task 关系闭包，合法无匹配返回 ready 空视图；
- v3 独立 filtered payload、filter id 与 view id，并在输出前重算验证；
- filter 只作用于完整验证后的安全 summaries，不进入 fixed child argv；
- 无 filter 保持 Stage 24 v2，未提供 envelope 保持 Stage 22 v1；
- no query/persistence/export/HTML/browser/network/write/execute 边界保持不变。

事实源：

- `docs/87-filtered-envelope-snapshot-json-reader-implementation.md`
- `docs/archive/release-notes/89-release-notes-stage27-filtered-envelope-snapshot-json-reader.md`

---

## Stage 28 — Filtered Snapshot Host Consumer Validation Gate（已完成）

用户于 2026-07-16 明确要求继续推进到下一阶段收口，条件启动成立。已冻结：

- 具体宿主为 Codex Desktop 本地一次性任务进程；
- consumer 输入为完整 filtered v3 reader result，不接受 payload-only；
- 未来采用专用标准库-only、stdin-only consumer，不扩展 Stage 18 handoff consumer；
- 输入上限 1 MiB，strict UTF-8，拒绝 duplicate key、非 object 与 schema drift；
- 只接受 ready、closed lifecycle、pass handoff/representation 与精确 guarantees；
- 独立重算 scope/filter/view id；base snapshot payload 未提供时只做关联与形状验证；
- 严格验证 safe sections、counts、matched/status 与 task/request exact filter semantics；
- 输出为最小、确定性、value-safe validation result，不回显 payload/filter/path/rows；
- 不读文件、不访问网络、不写入、不执行 reader、descriptor argv、candidate command 或 adapter。

新增 prerequisite contract test，以真实 Stage 27 stdout 冻结 Stage 29 所需的 wrapper/lifecycle/guarantees/identity/safe section 前置契约；本阶段不实现 consumer。

事实源：

- `docs/88-filtered-snapshot-host-consumer-validation-gate.md`
- `docs/archive/release-notes/90-release-notes-stage28-filtered-snapshot-host-consumer-validation-gate.md`
- `tests/test_filtered_snapshot_host_consumer_contract.py`

---

## Stage 29 — Codex Desktop Filtered Snapshot Consumer Implementation（已完成）

用户明确要求继续推进后，已按 Stage 28 contract 完成：

- 新增独立 `tools/codex_desktop_filtered_snapshot_consumer.py`；
- 标准库-only、stdin-only，最大输入 1 MiB，最大输出 64 KiB；
- 只接受完整 filtered v3 reader result，不接受 payload-only、v1/v2、文件或 URL；
- 固定 11 项检查和 `pass/error/blocked/validation_failed` 状态/退出码；
- 独立重算 scope/filter/view identity，base/envelope/handoff identity 只做 shape/link 检查；
- 严格验证 lifecycle、guarantees、safe sections、counts、matched/status 与 task/request filter semantics；
- 输出只包含四个 content ids、checks、value-safe findings、guarantees 与 next action；
- 不自动启动 reader，不读写文件，不访问网络，不执行 command/adapter，不修改 Stage 18 consumer。

事实源：

- `docs/89-codex-desktop-filtered-snapshot-consumer-implementation.md`
- `docs/archive/release-notes/91-release-notes-stage29-codex-desktop-filtered-snapshot-consumer.md`
- `tests/test_codex_desktop_filtered_snapshot_consumer.py`

---

## Stage 30 — Codex Desktop Filtered Snapshot Host Integration Gate（已完成）

已冻结固定 reader/consumer argv、本地 stdin pipe、timeout/stdout/stderr bounds、consumer 状态映射、validation-before-display 与一次性内存展示边界。事实源为 `docs/archive/90-codex-desktop-filtered-snapshot-host-integration-and-milestone-freeze.md`。

---

## Stage 31 — Codex Desktop Filtered Snapshot Host Integration Implementation（已完成）

- 新增 `tools/codex_desktop_filtered_snapshot_host.py`；
- 至少一个 exact task/request filter，两个同时提供时为 AND；
- 固定运行 Stage 27 filtered v3 reader，再通过 stdin 运行 Stage 29 consumer；
- consumer pass 和 base/scope/filter/view identity cross-check 前不释放 payload；
- ready 后只返回 validated safe summaries；failure payload 为 null；
- no retry、no write、no network、no service、no descriptor argv/adapter execution；
- 15 项专用测试、99 项相关回归和 857 项全量测试通过。

---

## Stage 32 — Filtered Snapshot Host Integration Milestone Freeze（已完成）

冻结并已推送 annotated tag：

```text
v0.14.0-filtered-snapshot-host-integration
```

本能力包覆盖 Stage 17–31 的 stdio handoff、独立 consumer、project/envelope/filtered reader、filtered consumer 与 validation-before-display host。commit/tag 后续已按用户授权推送至 `origin`。

事实源：

- `docs/archive/90-codex-desktop-filtered-snapshot-host-integration-and-milestone-freeze.md`
- `docs/archive/release-notes/92-release-notes-stage30-stage31-codex-desktop-filtered-snapshot-host-integration.md`
- `docs/archive/release-notes/93-release-notes-v0.14.0-filtered-snapshot-host-integration.md`

---

## Stage 33 — Codex Desktop Filtered Snapshot Display Integration Gate（已完成）

已选择 Codex Desktop 可消费的 deterministic escaped Markdown 作为首个具体展示面，冻结 fixed Stage 31 host、strict result gate、安全字段投影、空视图 UX、64 KiB 输出与 one-shot/no-side-effect 边界。事实源为 `docs/91-codex-desktop-filtered-snapshot-markdown-display-integration-and-milestone-freeze.md`。

---

## Stage 34 — Codex Desktop Filtered Snapshot Markdown Display Implementation（条件启动）

按 TDD 实现 `tools/codex_desktop_filtered_snapshot_display.py`。只能固定启动 Stage 31 host；不得接受 arbitrary stdin/file/URL，不得绕过 consumer，不得输出 raw Markdown/HTML 或新增持久化。

---

## Stage 35 — Filtered Snapshot Display Integration Milestone Freeze（条件启动）

Stage 34 全量验收后冻结候选 annotated tag `v0.15.0-filtered-snapshot-display-integration`，同步 release notes、digest、handoff 与版本治理。

---

## Guardrail 主线策略

guardrail / ledger / controlled write 这条主线仍然是必需能力，不应被放弃。

但从当前阶段开始，它的推进策略调整为：

1. **允许继续补完**：如果后续在接入、编排或控制面设计中发现 guardrail 缺口，可以继续回补。
2. **不阻塞主线**：只要不影响中枢台后端主线推进，就不要求在当前阶段把所有门禁一次性做完。
3. **阶段性回补**：可以在每完成一个中枢台阶段后，回头整理本阶段暴露出的 guardrail 缺口。
4. **边做边发现**：允许在 capability routing、adapter 接入、state model、future UI 准备过程中，再反推哪些 guardrail 还需要增强。

这意味着：

> guardrail 不是“做完了才准继续”，而是“作为长期内核，伴随中枢台成长持续补完”。

## 当前策略总结

当前最合理的策略是：

1. 不返工已完成的 guardrail / ledger / controlled write 内核
2. 不把 guardrail 当成必须一次性收尾的前置阻塞项
3. 先把“中枢台后端”这条主线的文档和抽象立起来
4. 在后续阶段中持续记录和回补 guardrail 缺口
5. 给后续实现留下清晰的顺序和 handoff
6. 对已冻结里程碑，在进入下一拍前先完成 post-freeze 文档口径校正

换句话说：

> 现在项目已经把“中枢台的安全内核”打牢，接下来要补的是“中枢台本身”；而安全内核会在后续阶段继续跟着主线一起长。
