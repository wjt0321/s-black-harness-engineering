<!-- parents: ../../../docs/archive/91-codex-desktop-filtered-snapshot-markdown-display-integration-and-milestone-freeze.md -->

# Release Notes 95 — Stage 34 Codex Desktop Filtered Snapshot Markdown Display

> 日期：2026-07-16
> 状态：实现与验收已收口

Stage 34 按 TDD 新增 `tools/codex_desktop_filtered_snapshot_display.py`：

- fixed Stage 31 host child，stdin 为 null；
- strict UTF-8 JSON、duplicate-key、exact shape/status/lifecycle/guarantees/identity/safe sections gate；
- deterministic escaped Markdown 与 SHA-256 content id；
- request-only、task-only、AND、合法空视图；
- host 非 ready、协议漂移、identity/count/type drift 与 output overflow 均 fail closed；
- no direct reader/consumer、no arbitrary input、no file/network/service/write/execution。

11 项专用测试、78 项相关回归与 868 项全量测试通过；doctor、public scan、py_compile 与真实 one-shot smoke 均通过。
