<!-- parents: ../../../docs/92-filtered-snapshot-markdown-display-consumer-validation-gate.md -->

# Release Notes 98 — Stage 37 Filtered Snapshot Markdown Display Consumer

> 日期：2026-07-16
> 状态：implementation 已收口

Stage 37 按 TDD 实现独立标准库-only、stdin-only display v1 consumer：

- 新增 `tools/codex_desktop_filtered_snapshot_display_consumer.py` 与 16 项专用测试；
- 最大 64 KiB strict UTF-8 JSON、duplicate-key、exact wrapper/status/lifecycle/guarantees gate；
- ready 时独立重算 content SHA-256，验证固定 Markdown grammar、安全 ASCII JSON inline literal 与 identity/count/filter/empty-view/report coherence；
- non-ready 只接受 withheld contract；输出不复制 Markdown content 或上游 finding message；
- 不启动 display/host/reader/consumer/command/adapter，不接受 CLI 参数、file/URL/payload-only/raw Markdown；
- 不访问网络、不启动 service、不持久化、不写入、不执行真实 adapter。

验收证据：16 项专用测试、124 项跨阶段回归与 884 项全量测试通过；doctor、public scan、py_compile、ready/blocked 真实 stdio pipe 均通过。
