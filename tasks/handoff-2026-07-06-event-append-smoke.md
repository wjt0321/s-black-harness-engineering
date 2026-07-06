# 2026-07-06 Runtime Event Append Smoke / Report Loop 接续上下文

> 本文件供压缩后恢复 `s-black harness engineering` 项目使用。当前项目根目录：仓库 checkout 根目录。GitHub 仓库：`https://github.com/wjt0321/s-black-harness-engineering`。

## 当前结论

`s-black harness engineering` 已完成 **Runtime Event Append Smoke / Report Loop** 阶段。

本阶段不是新的 runtime 行为版本，不新增写权限，不打新 tag。它用于验证并文档化 v0.8 的受控 event append 能力可以安全接上只读校验与聚合报告。

当前最新提交：

```text
ce39212 Document runtime event append smoke loop
```

当前最新功能 tag 仍为：

```text
v0.8.0-runtime-event-append-commit
```

## 阶段目标

本阶段补齐 append 后闭环：

```text
candidate event dry-run
  -> commit
  -> task validate
  -> task check-ledger
  -> runtime check-ledger
  -> runtime report
```

所有真实写入都只发生在临时项目副本 / pytest `tmp_path` 中，不修改仓库真实样例 ledger。

## 新增/修改文件

- `docs/30-runtime-event-append-smoke.md` - smoke/report loop 操作文档。
- `tests/test_runtime_event_append_report_loop.py` - focused 自动化 smoke 测试。
- `docs/10-cli-poc-usage.md` - 增加 smoke/report loop 用法入口。
- `README.md` / `README.en.md` - 文档索引补充 `docs/29` 与 `docs/30`。

## 当前完整链路

当前链路为：

```text
task ledger
  -> runtime plan --draft-json
  -> runtime draft validate
  -> runtime draft inspect
  -> runtime draft export --dry-run
  -> runtime draft export --commit
  -> runtime event append --dry-run
  -> runtime event append --commit
  -> task validate / task check-ledger
  -> runtime check-ledger
  -> runtime report
```

## 验证结果

本阶段收口前验证：

```text
python -m pytest tests/test_runtime_event_append_report_loop.py -q -> passed
python -m pytest -q -> passed
python -m agent_runtime.cli doctor -> PASS
python tools/public_scan.py -> OK public scan
git diff --check -> PASS
key pattern scan -> OK key scan
```

额外执行了真实临时目录 smoke 脚本，结果：

```text
runtime event append --dry-run -> PASS
runtime event append --commit -> PASS
task validate --schema event -> PASS
task check-ledger -> PASS
runtime check-ledger -> PASS
runtime report -> PASS
```

## 安全边界

本阶段没有新增 runtime 写权限。当前允许的写入仍只有：

- `runtime draft export --commit` 写入 `drafts/runtime/.../*.json` 的新文件。
- `runtime event append --commit` 追加一个 JSON object 到 event ledger JSONL 最后一行。

本阶段特别强调：

- 不要在仓库真实 `tasks/events.jsonl` 样例 ledger 上直接 `commit`。
- smoke 写入应使用临时项目副本、`tmp_path`、或显式隔离且可丢弃的 `--events-file`。
- Windows PowerShell 5 的 `Set-Content -Encoding UTF8` 会写 BOM，临时 JSON/JSONL 建议用 Python 或 `.NET UTF8Encoding(false)` 写入。

仍禁止：

- 执行真实 adapter。
- 访问网络。
- 发送消息。
- 读取 `.env`、`.env.local` 或 credential 文件。
- 修改 task snapshot ledger。
- 覆盖、删除、重排或重写历史 event。
- 自动修复 ledger。
- 回显完整 secret match、target、input、evidence、raw_ref、decision_ref。

## 当前恢复命令

```bash
git status -sb
git log -3 --oneline
git tag --points-at HEAD
python -m pytest -q
python -m agent_runtime.cli doctor
python tools/public_scan.py
```

预期：

```text
main...origin/main
HEAD: ce39212 Document runtime event append smoke loop
python -m pytest -q -> passed
python -m agent_runtime.cli doctor -> PASS
python tools/public_scan.py -> OK public scan
```

注意：`git tag --points-at HEAD` 预期为空，因为本阶段不打 tag；最新 tag 仍停留在 `v0.8.0-runtime-event-append-commit`。

## 后续建议

下一阶段继续保持低风险，不直接进入 adapter execution。建议优先考虑：

1. `runtime task create --dry-run`：为未来 task snapshot 受控写入做预检门禁。
2. `runtime event import --dry-run`：批量 event 导入预检，但需要谨慎定义排序、重复与部分失败语义。
3. `ledger compaction --dry-run`：只读分析 ledger 压缩候选，不执行重写。

若继续 controlled write，建议从 `runtime task create --dry-run` 开始，而不是直接实现 task create commit。
