# Handoff — 2026-07-12 — Recovery Lineage Aggregation Read Model

## 基线

- 上游冻结基线：`v0.12.1-orchestration-read-loop-snapshot`（`0419a04`）。
- 开发起点：`9dbb9ee`。
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
- `.githooks/pre-commit`：当前 PowerShell 环境无 bash，未直接执行；等价文档规则已人工核对，73 文档已加入 `docs/00-index.md`，根目录文档数低于阈值。

## 下一步建议

- 先做本切片阶段验收，重点检查：
  - lifecycle duplicate merge 是否足够严格；
  - branch / missing parent / cross-task / cycle 的状态语义；
  - human/JSON 输出是否保持安全和紧凑；
  - 默认 inspect 是否 byte-compatible。
- 验收通过后再决定是否把同一 aggregation 复用到 `orchestration run list` / `orchestration report generate`。
- 不进入真实 adapter execution、UI、service 或 DB。
