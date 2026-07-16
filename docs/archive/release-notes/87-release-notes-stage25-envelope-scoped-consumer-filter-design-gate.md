# Release Notes 87 — Stage 25 Envelope-scoped Consumer / Filter Design Gate

## 阶段结论

Stage 25 已完成设计审计并收口。当前没有具体 task/request filter 消费者，也没有足够事实冻结 filter 组合语义、canonical identity、排序/分页或持久化边界，因此不修改 Stage 24 reader，不新增 filter/query 命令面。

## 冻结内容

- 单个显式 envelope 的 `control-plane/codex-desktop-snapshot-read/v2` 继续是唯一 scoped representation；
- 无 filter、无多 envelope 聚合、无 reader-local 二次筛选；
- reader 不暴露 `--task-id`、`--request-id`、`--filter`、`--query`、`--sort`、`--page` 或 `--export`；
- 宿主只能一次性读取 bounded stdout JSON，在 `status=ready` 且 schema/reader id 匹配后内存展示；
- 不执行任何 argv，不保存/export/cache，不打开 HTML/browser，不自动刷新，不访问网络/DB/auth，不执行真实 adapter；
- Stage 24 v1/v2 schema、reader id、scope id 与 snapshot identity 保持兼容。

## 契约测试

新增 `test_reader_cli_keeps_stage25_no_filter_boundary`，直接检查 parser 命令面，防止后续无设计门地引入 filter、query、pagination 或 export。

## 文档维护

- 新增活跃事实源 `docs/archive/85-envelope-scoped-consumer-filter-design-gate.md`；
- Stage 19 旧设计门已被 Stage 20 implementation 事实源取代，完整移动到 `docs/archive/80-codex-desktop-read-only-adapter-design-gate.md`；
- 活跃文档仍保持 50 个，没有删除历史内容；
- 同步 digest、index、roadmap、README、AGENTS、handoff 与 progress。

## 下一阶段

Stage 26 — Filtered Envelope Snapshot Read Design Gate（条件启动）。只有具体消费者给出结构化 task/request filter、canonical identity、结果上限与 no-persistence/no-query 安全边界后才启动。

本阶段不创建 tag；`v0.13.0-read-only-control-plane` / `f401b98` 继续作为稳定 milestone。
