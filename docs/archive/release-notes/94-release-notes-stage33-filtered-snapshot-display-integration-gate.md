<!-- parents: ../../../docs/91-codex-desktop-filtered-snapshot-markdown-display-integration-and-milestone-freeze.md -->

# Release Notes 94 — Stage 33 Filtered Snapshot Display Integration Gate

> 日期：2026-07-16
> 状态：design gate 已收口

Stage 33 冻结 Codex Desktop 可消费的 one-shot Markdown display contract：

- fixed Stage 31 host child，禁止 direct reader/consumer；
- strict host schema/status/lifecycle/guarantees/identity/section gate；
- dynamic values 只以 escaped JSON inline literal 进入静态 Markdown 模板；
- output 为 versioned JSON wrapper + `text/markdown` content；
- content id 确定性，最终 stdout 64 KiB；
- host 非 ready 时 content withheld；
- no plugin/UI、HTML/browser、network/service、cache/export、write 或真实 execution。

本阶段不实现工具；Stage 34 必须先写 RED tests，再实现 `tools/codex_desktop_filtered_snapshot_display.py`。
