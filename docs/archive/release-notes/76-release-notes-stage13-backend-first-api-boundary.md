<!-- parents: ../../../51-backend-first-api-boundary.md -->
<!-- relates: ../../../52-minimal-orchestration-loop.md, ../../../53-minimal-orchestration-loop-cli-draft.md -->

# 76 — Release Notes — Stage 13 Backend-first API Boundary

## 收口结论

Stage 13 — Backend-first API Boundary 已完成。冻结范围是**资源/操作语义与当前真实 CLI/read model 的边界对账**，不是协议、服务化或真实执行阶段。

本阶段完成了：

- Task、Run、Approval、Artifact、Report 以及 routing/preflight 的资源/操作映射；
- stable、stable（受限）、preview、unavailable 四类当前可用性分类；
- 真实 CLI 命令名、输入边界、request/envelope 关系和受控写入语义校准；
- 持久 Run/Report collection、独立资源 API、真实 adapter execution、service/auth/DB/UI 的明确延期；
- orchestration CLI surface 与关键 preview/commit/retry/fallback/snapshot/aggregate-lineage flag 的契约测试。

## 验收矩阵

| 验收项 | 权威证据 | 结果 |
|:---|:---|:---:|
| 资源与操作模型 | `docs/51-backend-first-api-boundary.md` | 通过 |
| 真实 CLI surface | `tests/test_orchestration_boundary_contract.py` | 通过 |
| 默认输出兼容 | inspect/report/read-loop/snapshot 既有测试 | 通过 |
| preview、determinism、no-write | routing/read-loop/recovery 测试 | 通过 |
| task/event ledger 与受控写入 | 全量测试、ledger checks、controlled-write regression | 通过 |
| doctor、public scan、docs hook | 提交前门禁 | 通过 |

## 稳定边界

当前可以稳定复用的是**受限 CLI + 受限 read model**：

- task list/get/submit；
- route preview/snapshot 与 preflight；
- run dry-run/commit/list/inspect；
- approval list/get/resolve；
- artifact list/get；
- report generate；
- source-backed adapter registry list/inspect。

preview 或受限边界包括：routing/preflight snapshot、run dry-run、read-loop snapshot、recovery aggregation，以及 envelope-scoped 的 run/approval/artifact/report 投影。

## 正式延期

以下事项不属于 Stage 13 未完成项，已正式延期：

- HTTP/RPC/本地 service 协议选型；
- 用户鉴权、权限、多租户；
- 独立持久 Run/Event/Report storage 与 collection；
- orchestration Artifact export API；
- 真实 adapter execution、网络访问和外部系统写入；
- UI、看板、数据库、缓存、索引和后台服务。

## 下一阶段

进入 **Stage 14 — 中枢台最小编排闭环**。

第一拍不是重做 51 的资源模型，而是将已经冻结的契约应用到最小闭环：

```text
Task intent
→ routing
→ guardrail preflight
→ dry-run / controlled commit
→ lifecycle event
→ artifact / evidence / report projection
→ replay / next_action
```

继续保持：不选择 HTTP/RPC、不启动 service、不执行真实 adapter。

## 验证命令

```bash
python -m pytest tests -q
python -m agent_runtime.cli doctor
python tools/public_scan.py
python -m compileall -q agent_runtime tests
python -m pytest tests/test_controlled_write_regression.py -q
python -m agent_runtime.cli task check-ledger --tasks-file tasks/tasks.jsonl --events-file tasks/events.jsonl
bash .githooks/pre-commit
```

最终验收提交：`9625ba2`。
