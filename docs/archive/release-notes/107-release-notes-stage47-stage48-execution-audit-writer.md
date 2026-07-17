<!-- parents: ../../../docs/97-execution-lifecycle-audit-writer-design-and-implementation.md -->
<!-- relates: ../../../docs/96-fixed-git-status-executor-design-gate.md -->

# Release Notes 107 — Stage 47–48 Execution Lifecycle Audit Writer

> 日期：2026-07-17
> 类型：提交级里程碑；不创建 tag，不 push
> 稳定版本：`v0.17.0-filtered-snapshot-display-host-integration`

## 阶段结论

Stage 47 已冻结 execution lifecycle audit writer contract，Stage 48 已按 TDD 实现并收口。该能力只提供 future executor 可调用的内部 Python API，不新增 operator/automation CLI，也不启动 subprocess。

## 已交付

- shared event schema 增加 `execution_attempt_started`、`execution_succeeded`、`execution_failed`、`execution_cancelled`；
- 新增 strict `tasks/execution-audit-event.schema.json`，固定 actor、writer origin/version、writer-only append token、phase 与 safe evidence allowlist；
- 通用 `runtime event append/import` 对四类 reserved type 固定返回 `blocked/reserved-execution-event-type`，dry-run/commit 均不写 ledger；
- 新增 `agent_runtime/execution_audit_writer.py`：
  - `record_execution_attempt_started(...)`
  - `record_execution_terminal(...)`
  - `inspect_execution_attempt(...)`
  - `validate_execution_audit_ledger(...)`
- started 与 terminal 在同一个打开的 ledger file descriptor 上持有 dedicated writer lock 并各自追加一行；
- preflight identity/size 被绑定到打开的写 fd；成功提交要求 exact final size，不接受 post-check 后额外 bytes；
- write helper 显式报告当前调用的 `owned_bytes`；失败回滚仅接受精确 `expected_line[:owned_bytes]`，未知异常按 0 字节所有权处理，不从公共 JSON prefix 猜测；
- inspection 在同一 loaded records 集合上完成 persisted scan、chain validation 与 projection；
- 检测到并发 ledger 漂移时拒绝破坏性 rollback，返回 `concurrent-ledger-change` 并保留全部记录；
- terminal 失败只回滚 terminal，保留 started 并返回 `audit_incomplete=true`；
- read-only recovery state 覆盖 awaiting、三类 closed、missing 与 invalid；
- task/event ledger 启用 RFC 3339 `date-time` 校验，persisted audit record 在 projection 前执行 secret/public scan；
- `task validate --schema event` 对 reserved event 叠加 dedicated schema；
- Stage 44 readiness v1 保持历史 10 pass / 3 blocked，不把本阶段实现反写为旧 gate 权限。

## 安全边界

- 不接受 caller-supplied event dict、actor、message、writer provenance 或 arbitrary metadata；
- 不保存 raw stdout/stderr、path、branch、cwd、environment、config value 或异常正文；
- 不新增 execution CLI、service、DB、UI、network、credential read 或 background worker；
- 不实现 fixed Git status executor，不执行 Git；
- Stage 49 仍需用户再次明确授权真实 subprocess，并满足 Stage 46 的 trust/image binding、sanitized child PATH、process-tree containment 与 finite parser。

## 验证

收口验证入口：

```bash
python -m pytest tests -q
python -m agent_runtime.cli doctor
python tools/public_scan.py
python -m pytest tests/test_controlled_write_regression.py -q
python -m compileall -q agent_runtime tests tools
python -m agent_runtime.cli docs context --json
git diff --check
bash .githooks/pre-commit
```

专用测试覆盖 fixed provenance、成功/失败/取消 terminal、known/unknown partial write ownership、byte-identical append、post-check exception/extra bytes、rollback/stat failure、同 payload 不同 append provenance、并发 append 漂移、preflight/append file identity replacement、orphan/duplicate/order/reference/mismatch chain、timestamp、same-snapshot persisted secret、invalid input type、safe projection、historical readiness 与真实仓库 ledger no-write isolation。

## 后续

下一阶段为 **Stage 49 — Fixed Git Status Executor Implementation and Limited Enablement（条件启动）**。audit writer 完成只是必要前置，不构成 subprocess permission。
