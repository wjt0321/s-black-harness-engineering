<!-- parents: 73-recovery-lineage-aggregation-read-model.md -->
<!-- relates: 50-control-plane-state-model.md -->

# 74 — Recovery Lineage Report Reuse

## 决策

第一版 aggregation 先复用到 `orchestration report generate`，暂不接入 `orchestration run list`。

原因：

- `report generate` 已显式接收 `task_id`、`request_id`、`events_file`，与 `run inspect --aggregate-lineage` 的聚合输入完全一致。
- report 本身就是单 request 的实时只读聚合，新增显式视图不会改变集合范围。
- `run list` 目前是单 envelope、保持请求顺序的 read model；接入 ledger-backed lineage 会引入逐行聚合、跨 envelope descendants 和列表状态汇总等尚未冻结的语义。

## 最小契约

新增显式 flag：

```bash
orchestration report generate ... --aggregate-lineage
```

- 默认不传 flag 时，现有 JSON/human 输出不变。
- 显式传入时，结果新增 `recovery_lineage`，结构直接复用 `control-plane/recovery-lineage/v1`。
- report status 与 aggregation status 使用与 `run inspect` 相同的严重度合并规则；aggregation 的 `needs_input` / `validation_failed` 不得被 report 的 `pass` 覆盖。
- human 输出新增紧凑的 root/latest/attempts/leaves 摘要，不打印 target、payload、raw context 或 envelope 内容。
- 数据源仍只读取 lifecycle event ledger；不写文件、不执行 adapter、不持久化 Report 或 recovery snapshot。

## 暂缓项

- 不把 recovery 字段塞入 `status_summary` 或每个 finding。
- 不为 `run list` 增加隐式 ledger 查询。
- 不增加 report storage、report id、UI、service、DB 或真实 adapter execution。

## 验收结果（2026-07-12）

本切片已完成 consolidation 验收：

- 新增 inspect/report 跨入口契约测试，同一 lifecycle events 下 `recovery_lineage` byte-equivalent。
- branch、missing focus/parent、cross-task parent、cycle、duplicate conflict 的 aggregation status 与 issue code 在两个入口一致。
- 状态严重度矩阵由 `merge_recovery_status()` 统一维护，inspect/report 不再各自复制 precedence。
- 契约测试同时锁定 no-write 与 recovery 输出不包含 envelope target/input。
- JSON、human、默认兼容和原有 aggregation 单元测试继续通过。

下一步不直接改造 `run list`。只有出现明确的集合级消费者后，才设计独立 lineage index/read model，避免逐行重复扫描 ledger。


## Stage 12 最终决策

Collection-level lineage 在 Stage 12 不实现：当前没有明确消费者，inspect/report 双入口已经覆盖单 request 和 report 场景。`run list` 保持 envelope-scoped；未来若出现跨 envelope 查询需求，必须先设计独立、一次扫描、只读的 lineage index projection。
