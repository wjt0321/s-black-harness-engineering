<!-- parents: ../../../docs/archive/92-filtered-snapshot-markdown-display-consumer-validation-gate.md -->

# Release Notes 97 — Stage 36 Filtered Snapshot Markdown Display Consumer Validation Gate

> 日期：2026-07-16
> 状态：design gate 已收口

Stage 36 冻结独立标准库-only、stdin-only display v1 consumer contract：

- 64 KiB strict UTF-8 JSON、duplicate-key 与 exact wrapper gate；
- display status/lifecycle/guarantees/withheld validation；
- ready content hash、identity links、固定 Markdown grammar 与 safe ASCII JSON literal validation；
- counts/matched/filter/empty-view/report coherence；
- minimal value-safe output，不复制 content；
- no display/host/reader process、file/URL/network/service/persistence/write/execution。

本阶段不实现工具；Stage 37 必须先写 RED tests，再实现 `tools/codex_desktop_filtered_snapshot_display_consumer.py`。
