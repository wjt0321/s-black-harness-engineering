# 43 — Controlled Write Regression: Event Import

## 阶段定位

本文档标记 `runtime event import --commit` 与 consistency freeze 已被纳入 controlled write regression 保护。它是在 `docs/36-controlled-write-regression.md` 已有受控写入回归基础上，对新增写入点的扩展覆盖，不引入新的写入能力，只补测试与文档。

## 背景

前序阶段已完成：

- `runtime event import --dry-run`
- `runtime event import --commit`
- `runtime event import` consistency freeze（dry-run 输出 `plan_hash`，commit 支持 `--expected-plan-hash`）

这些功能引入了新的真实写入点（向 event ledger 批量追加连续 JSONL block），因此需要纳入 controlled write regression，确保：

- 批量写入不会破坏 task/event ledger 一致性。
- `--expected-plan-hash` freeze 机制在回归场景下按预期工作。
- 失败回滚不会污染 ledger。
- 输出脱敏边界不被突破。

## 纳入回归的写入点

### `runtime event import --commit`

- **唯一写入目标**：项目根内已存在的 event ledger JSONL 文件（默认 `tasks/events.jsonl`）。
- **Path guard**：必须在项目根目录内、后缀 `.jsonl`、禁止 sample ledger、禁止 `.git`/credential/secret 路径。
- **Preflight**：重跑完整 preflight（JSON 语法、schema、secret/public scan、candidate 内部 event_id 去重、与现有 ledger event_id 去重、unknown task、状态迁移合法性、模拟 check-ledger）。
- **Consistency freeze**：可选 `--expected-plan-hash`；提供时会在 preflight 前比对当前 plan hash，不一致直接 `blocked`。
- **Post-check**：写后执行 `task validate --schema event` 与 `task check-ledger`。
- **Rollback**：post-check 失败或写入异常时按写入前 byte size 截断；不允许部分成功。
- **输出脱敏**：不回显 `message` / metadata values / artifacts payload / evidence description / `target` / `input` / `raw_ref` / `decision_ref` / secret match；freeze 字段只暴露 hash、size、line count。

## 回归测试扩展

`tests/test_controlled_write_regression.py` 新增独立测试函数 `test_controlled_write_regression_event_import_does_not_touch_real_ledgers`，在临时项目根中运行：

1. 创建 task 并追加 seed event。
2. 更新 task snapshot 到 `running`，为后续 `status_changed` 事件提供一致上下文。
3. `runtime event import --dry-run`：验证通过并输出 `plan_hash`。
4. `runtime event import --commit --expected-plan-hash <hash>`：验证批量追加成功。
5. 构造第二个 candidate 并 capture 其 `plan_hash`，然后主动 mutate events ledger 使其失效。
6. `runtime event import --commit --expected-plan-hash <stale-hash>`：验证被 `blocked`，events ledger 不被修改。
7. `task validate --schema event` + `task check-ledger`：验证 ledger 仍一致。
8. `runtime report`：验证通过且输出不脱敏泄露。
9. 断言 task ledger 未被 event import 修改。
10. 断言仓库真实 `tasks/tasks.jsonl` 与 `tasks/events.jsonl` 未被修改。

## 关键断言

- `--dry-run` 不修改 events ledger。
- `--commit` 成功时 events ledger 行数增加预期数量。
- `--expected-plan-hash` mismatch 时：
  - 返回码为 `2`（blocked）。
  - 输出包含 `plan-hash-mismatch` 与 `freeze_check=failed`。
  - events ledger 字节与 mismatch 前完全一致。
- `task check-ledger` 在批量 import 后仍通过。
- `runtime report` 中不出现 `title` 或 event `message` 原文。
- 真实仓库 ledger 在测试前后字节一致。

## 与现有 CI 的关系

`.github/workflows/ci.yml` 已包含：

```bash
python -m pytest tests/test_controlled_write_regression.py -q
```

新增测试随该步骤自动运行，无需额外 CI 改动。

## 安全边界

- 所有破坏性/写入操作在 `tmp_path` 临时项目根中完成。
- 不修改真实 `tasks/tasks.jsonl` 或 `tasks/events.jsonl`。
- 不访问网络、不读取 `.env`/credential、不删除文件。
- 不新增 envelope 写入。

## 验证结果

- `python -m pytest tests/test_controlled_write_regression.py -q`：通过。
- `python -m pytest tests/test_runtime_event_import_dry_run.py tests/test_runtime_event_import_commit.py tests/test_runtime_event_import_freeze.py -q`：通过。
- `python -m pytest -q`：通过。
- `python -m agent_runtime.cli doctor`：PASS。
- `python tools/public_scan.py`：OK public scan。
