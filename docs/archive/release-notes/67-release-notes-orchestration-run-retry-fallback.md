# 67 — Release Notes：Orchestration Run Retry / Fallback Dry-run

## 阶段定位

本阶段是 `docs/66-orchestration-run-retry-fallback-design.md` 的第一版实现收口。

在 `orchestration task submit --commit` 完成入口级 A+B、`orchestration run --commit` 完成 run 侧 A+B 之后，本阶段补上恢复性执行分支的只读 preview：

- `orchestration run --retry-of <request_id> --dry-run`
- `orchestration run --fallback-from <request_id> --fallback-to <adapter_id> --dry-run`

本阶段仍然只做 dry-run preview，不实现 retry/fallback commit，不执行真实 adapter，不访问网络，不写 ledger/envelope，不扩展 event schema enum。

## 已实现能力

### 1. Retry dry-run preview

`orchestration run --retry-of <source_request_id> --dry-run` 现在会生成带 lineage 的 run plan preview：

- `lineage_type = retry`
- `retry_of = <source_request_id>`
- 新 `request_id` 必须不同于 source request id
- 重新执行 route / preflight / dry-run
- 不复用旧 `plan_hash`
- 不自动复用旧 approval

Retry 仍只是一次新的 read-only run plan preview。

### 2. Fallback dry-run preview

`orchestration run --fallback-from <source_request_id> --fallback-to <adapter_id> --dry-run` 现在会生成 fallback run plan preview：

- `lineage_type = fallback`
- `fallback_from = <source_request_id>`
- `fallback_to = <adapter_id>`
- 新 `request_id` 必须不同于 source request id
- `fallback_to` 会作为 effective adapter id 参与 routing / preflight
- 重新执行 route / preflight / dry-run

直接调用 `dry_run_run(..., fallback_from=..., fallback_to=...)` 与 CLI 路径保持一致：`fallback_to` 会强制绑定为 effective adapter。

### 3. 参数校验

新增校验规则：

- `--retry-of` 与 `--fallback-from` 互斥。
- `--fallback-to` 必须与 `--fallback-from` 一起使用。
- retry/fallback 的新 `request_id` 不得等于 source request id。

违规时返回 `validation_failed`，不继续 route / preflight / planning，也不写任何文件。

### 4. Plan hash 纳入 lineage

`plan_hash` 现在会把以下 lineage 字段纳入 hash 输入：

- `lineage_type`
- `retry_of`
- `fallback_from`
- `fallback_to`

这样普通 dry-run、retry dry-run、fallback dry-run 不会误用同一个 hash。

### 5. 输出安全边界

JSON 与 human 输出现在包含安全 lineage 字段，但仍不回显：

- 完整 target 原文
- raw payload
- secret match
- raw_ref / decision_ref / payload_refs
- evidence descriptions

## 修改范围

核心代码：

- `agent_runtime/orchestration_run_dry_run.py`
- `agent_runtime/cli.py`

测试：

- `tests/test_orchestration_run_dry_run.py`

文档：

- `docs/10-cli-poc-usage.md`
- `docs/66-orchestration-run-retry-fallback-design.md`
- `docs/67-release-notes-orchestration-run-retry-fallback.md`

## 保持不变的边界

本阶段不开放：

- retry/fallback commit
- 真实 adapter execution
- 网络访问
- 消息发送
- ledger 写入
- envelope/draft 写入
- 独立 Run storage
- event schema enum 扩展
- approval 自动复用

## 验证

本阶段已完成并复核以下验证：

```bash
python -m pytest tests/test_orchestration_run_dry_run.py -q
python -m pytest tests/test_orchestration_run_dry_run.py tests/test_orchestration_task_submit.py tests/test_controlled_write_regression.py -q
python -m pytest tests -q
python -m agent_runtime.cli doctor
python tools/public_scan.py
git diff --check
```

验证结果：

- `tests/test_orchestration_run_dry_run.py`：25 passed。
- retry/fallback + task submit + controlled write regression 组合测试：通过。
- 全量 `pytest tests -q`：通过。
- `doctor`：PASS。
- `public_scan`：OK public scan。
- `git diff --check`：无空白错误，仅提示两个既有 Python 文件后续会按 Git 设置从 LF 转 CRLF。

## 下一步建议

本阶段完成后，后续实际已发生的路径是：

1. 已完成 `v0.12.0-orchestration-foundation` milestone freeze。
2. 当前基线为 `38b4b69` / `v0.12.0-orchestration-foundation`。

因此如果从现在继续往后接，下一步建议应改为：

1. 进入 retry/fallback commit 设计。
2. 或先做 post-freeze 文档整理与下一拍入口统一。

默认建议先完成 post-freeze 文档收口，再进入 retry/fallback commit 设计。
