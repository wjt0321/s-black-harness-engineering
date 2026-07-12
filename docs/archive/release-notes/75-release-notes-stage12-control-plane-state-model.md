<!-- parents: ../../../50-control-plane-state-model.md -->
<!-- relates: ../../../73-recovery-lineage-aggregation-read-model.md, ../../../74-recovery-lineage-report-reuse.md -->

# 75 — Release Notes — Stage 12 Control Plane State Model

## 收口结论

Stage 12 — Control Plane State Model 已完成。冻结范围是**确定性、只读、可审计的 control-plane read model**，而不是持久化服务或真实执行系统。

Stage 12 已把以下对象及关系讲清并形成可消费投影：

- Task、Event、Run、Approval、Artifact、Evidence、Report 的关系与职责；
- routing/preflight decision snapshot；
- routing snapshot 到 run preview 的安全内容寻址引用；
- Run Preview → candidate Event → Report Preview 的 ephemeral read-loop snapshot；
- retry/fallback recovery lineage 的 ledger-backed inspect/report 聚合；
- 跨入口一致的状态严重度、异常 issue、脱敏和 no-write 契约。

## 验收矩阵

| Stage 12 目标 | 权威证据 | 结果 |
|:---|:---|:---|
| 定义状态对象关系 | `docs/50-control-plane-state-model.md` 的核心对象与状态关系 | 通过 |
| 区分顶层与附属对象 | `docs/51-backend-first-api-boundary.md` 的资源模型 | 通过 |
| 支撑审计、回放、观察和 future UI | Event/Evidence/Report 关系、read-loop snapshot、API boundary 映射 | 通过 |
| 路由/preflight 状态可消费 | routing snapshot 与 deterministic snapshot id | 通过 |
| Run/Event/Report 只读闭环 | `OrchestrationReadLoopSnapshot` 与相关测试 | 通过 |
| Recovery lineage 可审计 | inspect/report aggregation 与 contract tests | 通过 |
| 默认兼容、确定性、脱敏、no-write | 全量测试、doctor、public scan、docs hook | 通过 |

## 正式延期

以下事项不属于本次 Stage 12 冻结范围，已明确延期：

- snapshot 与持久化 Run/Event storage 的真实衔接；
- 独立 Report storage、report id 与长期索引；
- 完整持久化生命周期的数据库/service 实现；
- HTTP/RPC 协议、鉴权、UI 和真实 adapter execution。

对象字段和生命周期的**设计边界**已在 50/51 中冻结；其持久化实现不能为了 Stage 12 收口突破现有安全边界。

## Collection-level Lineage 决策

当前没有明确集合级消费者，因此不新增 lineage index，也不改造 `run list`：

- 单 request 使用 `run inspect --aggregate-lineage`；
- report 消费使用 `report generate --aggregate-lineage`；
- `run list` 继续保持 envelope-scoped；
- 若后续出现跨 envelope 查询需求，必须先设计一次扫描的独立只读 projection，禁止逐行重复扫描 ledger。

## 安全边界

- 不执行真实 adapter；
- 不访问网络、凭据或外部系统；
- 不新增 UI、service 或 DB；
- snapshot 与 aggregation 均保持 ephemeral/read-only；
- 所有写操作继续遵循显式 `--commit`、写前校验、写后校验和失败回滚。

## 下一阶段

进入 **Stage 13 — Backend-first API Boundary**。

Stage 13 首要工作不是选择 HTTP/RPC，而是把当前真实 CLI/read model 与 `docs/51-backend-first-api-boundary.md` 中的资源/操作模型对齐，区分：

- 已稳定可映射的资源与操作；
- 仍是 preview/ephemeral 的对象；
- 尚未实现、不得伪装存在的持久资源。
