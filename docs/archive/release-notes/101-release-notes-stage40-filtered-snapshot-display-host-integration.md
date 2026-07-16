<!-- parents: ../../../docs/93-codex-desktop-filtered-snapshot-display-host-integration-and-milestone-freeze.md -->

# Release Notes 101 — Stage 40 Filtered Snapshot Display Host Integration

> 日期：2026-07-16
> 状态：implementation 已收口

Stage 40 按 TDD 实现 fixed Stage 34 display → exact stdout → fixed Stage 37 consumer → validation-before-release one-shot host：

- 新增 `tools/codex_desktop_filtered_snapshot_display_host.py` 与 40 项专用测试；
- strict display/consumer wrapper、status/exit、lifecycle、guarantees、checks 与 next-action validation；
- display ready/0、consumer pass/0 与五项 identity cross-check 前 content withheld；
- task-only、request-only、AND、empty view 与 valid non-ready mapping；
- 64 KiB child I/O、64 KiB stderr、128 KiB final output、timeout/cancel/no-retry；
- minimal safe output，不复制 child message、stderr、argv、path、envelope 或未验证 content；
- no Markdown reparse、file/URL/network/service/persistence/write/execution。

验收证据：40 项专用测试、164 项跨阶段回归与 924 项全量测试通过；doctor、public scan、py_compile 与四条真实 CLI 管道通过。
