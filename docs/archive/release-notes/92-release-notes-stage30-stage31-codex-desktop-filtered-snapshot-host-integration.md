<!-- parents: ../../../docs/90-codex-desktop-filtered-snapshot-host-integration-and-milestone-freeze.md -->

# Release Notes 92 — Stage 30/31 Codex Desktop Filtered Snapshot Host Integration

> 日期：2026-07-16
> 状态：已收口

## 交付

- Stage 30 冻结 `codex-desktop-filtered-snapshot-host/v1` design gate；
- Stage 31 新增 `tools/codex_desktop_filtered_snapshot_host.py`；
- 新增 `tests/test_codex_desktop_filtered_snapshot_host.py`；
- 固定 filtered v3 reader → Stage 29 consumer 本地 stdin pipeline；
- consumer pass 与 base/scope/filter/view identity cross-check 前不释放 payload；
- ready 后只返回已验证 safe summaries 的 one-shot 内存投影；
- 状态/退出码：`ready/0`、`error/1`、`blocked/2`、`validation_failed/5`。

## 安全边界

- fixed argv、`shell=False`、最小环境、30 秒默认/60 秒上限；
- reader stdout 与 host stdout 1 MiB；consumer stdout 和 child stderr 64 KiB；
- no retry、no write、no network、no service、no DB/auth；
- no descriptor argv、candidate command、adapter execution；
- no HTML/browser、persistence/cache/export、arbitrary query；
- failure 不回显 absolute root、relative envelope、stderr 或未验证 payload。

## 验收

- RED：host 文件不存在时专用测试按预期失败；
- GREEN：15 项专用测试通过；
- Stage 18/20 与 Stage 22–29 相关 99 项测试通过；
- 全量 857 项测试通过；
- doctor、public scan、py_compile 通过；
- 真实 request-only 与 task+request AND pipeline 返回 ready。

## Compatibility

Stage 18 consumer、Stage 20 adapter、Stage 22 v1、Stage 24 v2、Stage 27 v3 reader 与 Stage 29 consumer 均保持兼容；未修改受控写入模块或真实 ledger。
