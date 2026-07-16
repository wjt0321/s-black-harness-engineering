<!-- parents: ../../../docs/archive/92-filtered-snapshot-markdown-display-consumer-validation-gate.md -->

# Release Notes 99 — v0.16.0 Filtered Snapshot Display Consumer

> 日期：2026-07-16
> 状态：本地 annotated milestone freeze

`v0.16.0-filtered-snapshot-display-consumer` 冻结 Stage 36–37 的 display-result consumer design 与实现能力包：

- `control-plane/filtered-snapshot-markdown-display-consumer-validation/v1`；
- `codex-desktop-filtered-snapshot-markdown-display-consumer/v1`；
- independent stdin-only validation、bounded strict parsing 与 deterministic minimal output；
- content hash、fixed Markdown grammar、escaping invariants、identity/count/filter/empty-view/report coherence；
- ready/pass、blocked、validation_failed、error 状态/退出码映射；
- full regression、doctor、public scan、docs maintenance 与 Git diff verification。

继续 unavailable：自动启动上游、专有 Codex Desktop 插件/UI、HTML/browser、file/URL、raw arbitrary Markdown、service/network/DB/auth、cache/export、query/sort/page、UI write 与真实 adapter execution。该 tag 冻结时保持本地，后于 2026-07-16 按用户授权推送至 `origin`。
