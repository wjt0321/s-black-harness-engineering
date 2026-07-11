<!-- parents: 50-control-plane-state-model.md -->
<!-- relates: 70-orchestration-run-retry-fallback-commit-design.md -->

# 73 — Recovery Lineage Aggregation Read Model

## 阶段定位

本设计承接 `v0.12.1-orchestration-read-loop-snapshot` 冻结基线，在不引入真实执行、独立 Run storage、数据库或服务的前提下，把已经写入 run lifecycle event metadata 的 retry / fallback lineage 聚合为确定性的只读恢复视图。

第一版只扩展现有命令：

```bash
orchestration run inspect --aggregate-lineage
```

默认未传 flag 时，现有 `run inspect` 输出保持不变。

## 数据源

第一版以 task event ledger 为 lineage 索引，复用已有字段：

- `task_id`
- `event_type`
- `metadata.request_id`
- `metadata.plan_hash`
- `metadata.lineage_type`
- `metadata.retry_of`
- `metadata.fallback_from`
- `metadata.fallback_to`
- `metadata.adapter_id`
- `metadata.envelope_path`

只消费 `run_planned`、`run_draft_exported`、`run_blocked`。同一 request 的多条 lifecycle event 按 request_id 合并；关键 metadata 必须一致。现有 `--envelope` 仍负责当前 run 的详情与 gate/report 聚合，lineage aggregation 不扫描 `drafts/`，也不引入新索引文件。

## 输出契约

`RunInspectResult` 在显式聚合时新增 `recovery_lineage`：

```json
{
  "schema_version": "control-plane/recovery-lineage/v1",
  "status": "pass",
  "task_id": "task-...",
  "focus_request_id": "req-...",
  "root_request_id": "req-...",
  "latest_request_id": "req-...",
  "leaf_request_ids": ["req-..."],
  "effective_plan_hash": "sha256:...",
  "attempt_count": 2,
  "requests": [],
  "issues": []
}
```

每个 request 摘要只包含安全标识、relationship、parent、adapter、plan hash、状态和可选 fallback target adapter id，不回显 target、payload、raw context 或 finding message。

## 确定性规则

- 普通 run 是单节点链，自身同时为 root、leaf、latest。
- retry 的 parent 为 `retry_of`；fallback 的 parent 为 `fallback_from`。
- 从 focus request 向上解析 root，再返回该 root 下同 task 的全部 descendants。
- request 顺序按 root-first、parent-before-child、request_id 稳定排序。
- 唯一 leaf 时，该 leaf 是 `latest_request_id`，其 plan hash 是 `effective_plan_hash`。
- 多 leaf 表示分支歧义：`latest_request_id` 与 `effective_plan_hash` 为 `null`，聚合状态为 `needs_input`。
- 重复 lifecycle events 只有在关键字段一致时才合并。

## 校验与失败语义

以下情况返回 `validation_failed`，且 issues 只包含安全 id：

- focus request 不存在
- parent request 不存在
- parent 属于其他 task
- lineage cycle
- 同一 request 的 lifecycle metadata 冲突
- lineage_type 与 parent 字段组合不合法

多 leaf 不是数据损坏，返回 `needs_input`。没有 lineage 的普通 run 返回 `pass` 单节点视图。

## 安全边界

- 只读，不写 task/event ledger 或 envelope。
- 不执行 adapter，不访问网络，不读取凭据。
- 不增加 event type，不修改 schema enum。
- 不扫描任意目录，不构造持久化 recovery snapshot。
- 不自动选择或执行 retry / fallback。

## 测试门禁

至少覆盖普通 run、retry、fallback、多级链、分支、缺失 parent、跨 task parent、cycle、重复一致事件、重复冲突事件、CLI JSON/human、默认兼容、不写文件与脱敏输出。
