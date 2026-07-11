# 02 — 路线图

## 路线图说明

`s-black harness engineering` 是一个长期项目。

它的最终目标不是单做“规则门禁”，而是建设一个面向多 Agent、多工具、多渠道的**中枢运行台（Orchestration Hub / Control Plane）**。当前已经做出来的 policy、ledger、controlled write、freeze、verification 等能力，属于这个中枢台的**安全与审计内核**。

因此后续路线图分为两条并行主线：

- **主线 A：安全与审计内核**
- **主线 B：中枢台接入与编排**

## 版本治理说明

当前仓库最新里程碑基线已更新为 `v0.12.0-orchestration-foundation`（commit `38b4b69`，已 push）。

从 orchestration 阶段开始，项目持续使用 `docs/55`、`docs/57`、`docs/59`、`docs/61`、`docs/62`、`docs/65`、`docs/67` 这类**阶段编号 + release notes**来完成阶段收口，而 semver/tag 改为只在里程碑节点冻结。

这表示版本治理已经从“过渡态”进入“已执行态”：

- release notes 与阶段文档持续更新；
- semver/tag 不再逐阶段增长；
- `docs/64-versioning-governance.md` 定义的“阶段推进 + release notes 收口 + 里程碑打 tag”策略，已经在 `v0.12.0-orchestration-foundation` 得到实际执行。

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

## Stage 9 — 中枢台定位校正与总蓝图（当前阶段）

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

## Stage 11 — Capability Routing Model（下一步高优先级）

目标：在 Stage 10 source-backed registry 投影基础上，继续把 capability-level routing 抽象做扎实，让上层任务调度优先面向 capability，而不是硬编码具体工具名。

要做的事：

- 设计 capability 命名方式
- 设计 routing 输入 / 输出模型
- 设计 capability match / constraint filter / preference rank 三层路由过程
- 明确 fallback 机制
- 明确 routing 与 guardrail 的边界

主要交付物：

- `docs/49-capability-routing-model.md`

---

## Stage 12 — Control Plane State Model（下一步高优先级）

目标：把未来 CLI、UI、自动化共同依赖的状态对象讲清楚。

要做的事：

- 定义 task / event / run / approval / artifact / evidence / report 等对象关系
- 明确哪些是顶层对象，哪些是附属对象
- 明确这些对象如何支撑审计、回放、观察和 future UI

主要交付物：

- `docs/50-control-plane-state-model.md`

---

## Stage 13 — Backend-first API Boundary（设计文档已落地，协议选择仍暂缓）

目标：虽然现在不急着做 UI，但后端必须先按未来可被 UI 调用的方式设计。

要做的事：

- 定义未来 UI / CLI / automation 共同依赖的 API 边界
- 先做资源模型，不急着选 HTTP / RPC / 本地进程协议
- 明确任务列表、任务详情、run 详情、approval 操作、dry-run / commit、report 的统一接口草案

主要交付物：

- `docs/51-backend-first-api-boundary.md`

说明：

- 资源模型与操作模型已在 51 中定义。
- 协议（REST / RPC / 本地进程调用）和鉴权细节仍不在本阶段展开。
- 本阶段仍保持“文档先行”，不进入协议实现。

---

## Stage 14 — 中枢台最小编排闭环（设计文档、命令草案与 run 侧 A+B commit 已落地）

目标：在后端抽象稳定后，跑通第一个真正体现“中枢台”特征的最小闭环。

主要交付物：

- `docs/52-minimal-orchestration-loop.md`
- `docs/53-minimal-orchestration-loop-cli-draft.md`（命令面草案参考，非正式 API 边界）

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
- `docs/55-release-notes-orchestration-read-models.md`
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
- `docs/57-release-notes-orchestration-controlled-handoff.md`
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
- `docs/59-release-notes-orchestration-run-controlled-execution.md`
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
- `docs/61-release-notes-orchestration-run-lifecycle-events.md`
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
- 阶段收口文档：`docs/65-release-notes-orchestration-task-submit-created-event.md`。

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
- 阶段收口文档：`docs/67-release-notes-orchestration-run-retry-fallback.md`。

说明：

- 本阶段已从 design gate 进入 dry-run preview 实现收口。
- retry/fallback commit 语义仍需另开设计。
- 不标记 Stage 16 开始；Stage 16 仍保持远期。

---

## Stage 15.97 — Orchestration Foundation Freeze 完成

目标：把 `v0.12.0-orchestration-foundation` 作为 orchestration foundation 的首个正式里程碑基线完成冻结，并为后续 post-freeze 文档整理与下一拍设计建立稳定起点。

已完成范围：

- 已新增 `docs/68-orchestration-foundation-milestone-freeze-checklist.md`，明确候选能力包、验证证据与冻结前判定。
- 已新增 `docs/69-orchestration-foundation-freeze-execution-plan.md`，记录冻结范围、建议 commit message、建议 tag、annotated tag message 与执行顺序。
- 已完成冻结前验证：全量 `pytest tests -q`、`doctor`、`public_scan`、`git diff --check`。
- 已完成实际冻结：commit `38b4b69`、tag `v0.12.0-orchestration-foundation`、push 完成。

说明：

- `68` / `69` 仍保留为冻结前判断与执行方案的历史文档。
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

## Stage 15.99 — Run Lineage / Recovery Read Model（当前阶段）

目标：让 retry / fallback lineage 不只是被写进去，还能被现有 orchestration read models 以安全、紧凑的方式读出来。

已完成范围：

- `orchestration run inspect` 已能输出 `lineage_type`、`retry_of`、`fallback_from`、`fallback_to`
- `orchestration run list` 已能在每条 run 摘要中显示紧凑 lineage 标识
- `orchestration report generate` 已补 lineage 安全摘要
- lineage 提取优先复用 envelope `adapter_request.context`，不引入新存储
- 阶段收口文档：`docs/71-release-notes-run-lineage-read-models.md`

说明：

- 本阶段仍不放开真实 adapter execution、独立 Run storage、DB、service 或 UI。
- recovery lineage 现在已形成“可写 + 可读”的最小闭环。
- 下一步更适合进入 recovery lineage 聚合视图设计，而不是跳去真实执行。

---

## Stage 16 — UI / Control Panel（远期）

目标：在后端抽象稳定后，为中枢台提供一个真正可操作、可观察、可审计的前端或看板。

候选能力：

- adapter / agent availability 总览
- task / event / run 浏览
- blocked / approval pending 列表
- dry-run / commit 操作面
- artifacts / evidence / reports 查看
- diagnostics / health / regression 状态总览

前提：

- 必须以后端抽象成熟为前提
- 不应倒逼后端临时补洞

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
