<!-- parents: ../../../docs/93-codex-desktop-filtered-snapshot-display-host-integration-and-milestone-freeze.md -->

# Release Notes 100 — Stage 39 Filtered Snapshot Display Host Integration Gate

> 日期：2026-07-16
> 状态：design gate 已收口

Stage 39 冻结 fixed Stage 34 display → exact stdout → fixed Stage 37 consumer → validation-before-release one-shot host contract：

- explicit project/envelope/exact filter/markdown action；
- fixed argv ownership、minimal environment、sequential no-retry lifecycle；
- 64 KiB child I/O、64 KiB stderr 与 128 KiB final output bounds；
- strict display/consumer protocol、status/exit、guarantees/checks validation；
- consumer pass/0 与五项 identity cross-check 前 content withheld；
- minimal result，不复制 child finding message、stderr、argv、path 或 envelope；
- no UI/HTML/browser/file/URL/network/service/persistence/write/execution。

本阶段不实现工具；Stage 40 必须先写 RED tests，再实现 `tools/codex_desktop_filtered_snapshot_display_host.py`。
