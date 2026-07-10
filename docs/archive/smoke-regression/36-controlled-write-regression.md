# 36 — Controlled Write Regression

## 阶段定位

本阶段把当前受控写入链路固化成回归保护，不新增任何写权限，也不进入 adapter 真实执行。通过文档梳理、聚焦测试和 CI 步骤，确保已落地的三个 commit 命令在后续变更中不被破坏。

## 当前受控写入点

### 1. `runtime draft export --commit`

- **唯一写入目标**：项目根内 `drafts/runtime/.../*.json` 新文件。
- **Path guard**：必须在项目根目录内、后缀 `.json`、必须位于 `drafts/runtime/` 下、禁止路径逃逸、禁止 `.git`/credential/secret 路径、禁止覆盖已存在文件。
- **Post-check**：写后再次执行 `runtime draft validate` 与 `runtime draft inspect`。
- **Rollback**：post-check 失败时删除本命令创建的文件。
- **输出脱敏**：不回显完整 `target` / `input` / `evidence` / `raw_ref` / `decision_ref` / secret match。

### 2. `runtime event append --commit`

- **唯一写入目标**：项目根内 event ledger JSONL 文件（默认 `tasks/events.jsonl`）。
- **Path guard**：必须在项目根目录内、后缀 `.jsonl`、禁止 sample ledger（`tasks/examples.jsonl`、`tasks/events.examples.jsonl`）、禁止 `.git`/credential/secret 路径。
- **Post-check**：写后执行 `task validate --schema event`、`task check-ledger`；如有 `--envelope` 再执行 `runtime check-ledger`。
- **Rollback**：post-check 失败时按写入前 byte size 截断；若本命令新建文件则删除。
- **输出脱敏**：不回显完整 `message` / metadata values / artifacts payload / evidence description / `target` / `input` / `raw_ref` / `decision_ref` / secret match。

### 3. `runtime task create --commit`

- **唯一写入目标**：项目根内 task ledger JSONL 文件（默认 `tasks/tasks.jsonl`）。
- **Path guard**：必须在项目根目录内、后缀 `.jsonl`、禁止 sample ledger（`tasks/examples.jsonl`、`*.examples.jsonl`）、禁止 `.git`/credential/secret 路径。
- **Post-check**：写后执行 `task validate --schema task`、`task check-ledger`。
- **Rollback**：post-check 失败时按写入前 byte size 截断；若本命令新建文件则删除。
- **输出脱敏**：不回显完整 `title` / `summary` / `current_step` / `blocked_message` / `failure_reason` / evidence description / artifacts payload / secret match。

### 4. `runtime event import --commit`

- **唯一写入目标**：项目根内已存在的 event ledger JSONL 文件（默认 `tasks/events.jsonl`）。
- **Path guard**：必须在项目根目录内、后缀 `.jsonl`、禁止 sample ledger（`tasks/examples.jsonl`、`tasks/events.examples.jsonl`）、禁止 `.git`/credential/secret 路径。
- **Preflight**：重跑完整 preflight（JSON 语法、schema、secret/public scan、candidate 内部去重、与现有 ledger 去重、unknown task、状态迁移合法性、模拟 check-ledger）。
- **Consistency freeze**：可选 `--expected-plan-hash`；提供时会在 preflight 前比对当前 plan hash，不一致直接 `blocked`。
- **Post-check**：写后执行 `task validate --schema event`、`task check-ledger`。
- **Rollback**：post-check 失败或写入异常时按写入前 byte size 截断；不允许部分成功。
- **输出脱敏**：不回显完整 `message` / metadata values / artifacts payload / evidence description / `target` / `input` / `raw_ref` / `decision_ref` / secret match；freeze 字段只暴露 hash、size、line count。

## 必须保持只读的命令

以下命令只读，不写入、不执行 adapter、不访问网络、不发送消息、不读取 `.env`/credential：

- `runtime plan` / `runtime plan --draft-json`
- `runtime draft validate` / `runtime draft inspect`
- `runtime draft export --dry-run`
- `runtime gate check`
- `runtime check-ledger`
- `runtime report`
- `task validate`
- `task check-ledger`
- `task status`
- `task events`
- `adapter plan`
- `adapter validate`
- `adapter inspect`
- `adapter approval check`
- `adapter response check`
- `adapter gate check`
- `check text` / `check path` / `check action`
- `agents list` / `adapters list` / `policies list`
- `doctor`

## 回归测试

`tests/test_controlled_write_regression.py` 在临时项目根中运行完整链路：

1. `runtime task create --dry-run`
2. `runtime task create --commit`
3. `runtime event append --dry-run`
4. `runtime event append --commit`
5. `runtime event import --dry-run`（验证输出包含 `plan_hash`）
6. `runtime event import --commit --expected-plan-hash <hash>`（验证批量追加）
7. `runtime event import --commit --expected-plan-hash <stale-hash>`（验证 freeze mismatch 被 blocked）
8. `task validate` + `task check-ledger`
9. `runtime report`

断言：

- 每一步返回预期状态码。
- task/event ledger 只追加预期行数。
- `--expected-plan-hash` mismatch 时 events ledger 不被修改。
- `runtime report` 不泄露 `title` / event `message`。
- 仓库真实 `tasks/tasks.jsonl` 与 `tasks/events.jsonl` 不被修改。
- 新加入的 `runtime event import --commit` 与 consistency freeze 链路不会污染现有受控写入点。

## 建议本地 / CI 命令

本地回归：

```bash
python -m pytest tests/test_controlled_write_regression.py -q
```

完整验证：

```bash
python -m pytest -q
python -m agent_runtime.cli doctor
python -m agent_runtime.cli task validate --record-file tasks/tasks.jsonl --schema task
python -m agent_runtime.cli task validate --record-file tasks/events.jsonl --schema event
python -m agent_runtime.cli task check-ledger --tasks-file tasks/tasks.jsonl --events-file tasks/events.jsonl
python tools/public_scan.py
```

## 实现文件

- `docs/36-controlled-write-regression.md`：本文档。
- `docs/43-controlled-write-regression-event-import.md`：event import 纳入回归保护的扩展说明。
- `tests/test_controlled_write_regression.py`：受控写入回归测试。
- `.github/workflows/ci.yml`：新增 controlled write smoke test 步骤。

## 验证结果

```text
python -m pytest tests/test_controlled_write_regression.py -q -> passed
python -m pytest -q -> passed
python -m agent_runtime.cli doctor -> PASS
python tools/public_scan.py -> OK public scan
git diff --check -> PASS
```
