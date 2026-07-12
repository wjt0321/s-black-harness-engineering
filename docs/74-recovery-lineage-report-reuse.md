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

## 验收

至少覆盖 JSON、human、默认兼容、aggregation validation failure 状态提升、只读/no-write 和全量回归。
