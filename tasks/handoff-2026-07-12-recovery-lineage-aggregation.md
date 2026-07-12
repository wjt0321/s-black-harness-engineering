# Handoff — 2026-07-12 — Recovery Lineage Aggregation Read Model

## 基线

- 上游冻结基线：`v0.12.1-orchestration-read-loop-snapshot`（`0419a04`）。
- 开发起点：`9dbb9ee`。
- 实现 commit：`6ccd8a9`（已 fast-forward 合并到本地 `main`）。
- 本切片：Stage 12 post-freeze recovery lineage aggregation 第一版。

## 已完成

- 新增 `agent_runtime/orchestration_recovery.py`，从现有 run lifecycle event metadata 聚合 recovery chain。
- 新增 `orchestration run inspect --aggregate-lineage`，显式输出 root/latest/leaves、attempt count、effective plan hash、安全 request summaries 与 issues。
- 普通单节点、retry、fallback、多级链使用确定性 parent 关系解析，不依赖 timestamp。
- 多 leaf 返回 `needs_input`，不静默选择 latest。
- missing/cross-task parent、cycle、invalid shape、重复 metadata 冲突返回 `validation_failed`。
- 默认不传 flag 时现有 inspect JSON/human 输出保持兼容。

## 边界

- 只读取 `run_planned` / `run_draft_exported` / `run_blocked` event metadata。
- 不扫描 `drafts/`，不增加 event type 或索引。
- 不写 task/event ledger，不改 envelope，不持久化 recovery snapshot。
- 不执行 adapter，不访问网络，不读取凭据，不输出 target/payload/raw context。

## 关键文件

- `docs/73-recovery-lineage-aggregation-read-model.md`
- `agent_runtime/orchestration_recovery.py`
- `agent_runtime/orchestration_run.py`
- `agent_runtime/cli.py`
- `tests/test_orchestration_recovery.py`
- `tests/test_orchestration_run_inspect.py`

## 验证

- `python -m pytest tests -q`：通过。
- `python -m agent_runtime.cli doctor`：PASS。
- `python tools/public_scan.py`：OK。
- `python -m compileall -q agent_runtime tests`：通过。
- `git diff --check`：通过（仅 Git LF/CRLF 设置提示）。
- `.githooks/pre-commit`：通过（使用 Git for Windows bash）。

## 下一轮恢复顺序

1. `docs/000-stage-digest.md`
2. `docs/74-recovery-lineage-report-reuse.md`
3. `docs/73-recovery-lineage-aggregation-read-model.md`
4. `python -m agent_runtime.cli docs context --json`
5. 本 handoff

## 本轮验收结果

- 阶段验收已通过：duplicate merge、branch / missing parent / cross-task / cycle 语义、JSON/human 安全输出、默认兼容和只读边界均已复核。
- fresh verification：全量 pytest、doctor、public scan、compileall、`git diff --check` 与 docs maintenance hook 均通过。

## Report 复用切片

- 决策：优先接入 `orchestration report generate --aggregate-lineage`；`run list` 保持 envelope-scoped。
- 设计：`docs/74-recovery-lineage-report-reuse.md`。
- 实现：`ReportGenerateResult` 可选输出 `recovery_lineage`，并按 inspect 相同严重度合并整体状态；human 输出仅增加紧凑 root/latest/attempts/leaves 摘要。
- 默认兼容：未传 flag 时 report JSON/human 不增加 aggregation 字段或输出。

## Consolidation 验收结果

- 新增 `tests/test_orchestration_recovery_contract.py`，锁定 inspect/report 的 recovery payload、异常 issue、脱敏和 no-write 一致性。
- 新增共享 `merge_recovery_status()`，统一两个入口的状态严重度矩阵，移除重复 precedence。
- targeted 与全量回归均通过。

## 下一步建议

- 先确认是否存在明确的集合级 lineage 消费者。
- 若有，先设计独立 lineage index/read model，再考虑 `run list`；不要对每行做隐式 ledger 聚合。
- 若没有明确消费者，应保持当前 inspect/report 双入口，不继续堆叠视图。
- 不进入真实 adapter execution、UI、service 或 DB。
