# Release Notes 89 — Stage 27 Filtered Envelope Snapshot JSON Reader

## 阶段结论

Stage 27 已按 TDD 实现并收口。在既有 snapshot reader 上新增 task/request filtered v3，无 filter v2 与无 envelope v1 保持兼容。

## 交付内容

- `run_snapshot_json_reader()` 新增 `task_id_filter` / `request_id_filter`；
- CLI 新增 `--task-id` / `--request-id`，禁止 duplicate last-value-wins；
- filter 必须绑定显式 envelope，使用 canonical ASCII exact id；
- 支持 task-only、request-only、task+request AND；
- task filter 通过 request→task 关系闭包包含 response artifacts；
- 合法无匹配返回 ready empty view；
- 新增 v3 result、filtered payload schema、filter id 与 view id；
- 新增 filtered payload 自校验与 tamper rejection；
- fixed child argv 不携带 filter；
- 新增 real stdio、identity、安全摘要与兼容测试。

## 版本

- `control-plane/codex-desktop-snapshot-read/v3`
- `codex-desktop-filtered-envelope-snapshot-json-reader/v3`
- `control-plane/filtered-envelope-snapshot/v1`
- `control-plane/envelope-snapshot-filter/v1`

## 安全边界

- 只过滤完整验证后的 runs/approvals/artifacts summaries；
- 不输出 project/registry sections 或 raw envelope values；
- 不提供 query、wildcard、regex、sort/page、lineage expansion；
- 不保存/cache/export，不读取 HTML/browser，不访问网络，不启动 service，不执行 adapter 或 descriptor argv。

## 文档维护

- 新增 `docs/87-filtered-envelope-snapshot-json-reader-implementation.md`；
- Stage 20 host adapter 实现文档已被 Stage 22–27 reader 事实源取代，完整归档至 `docs/archive/81-codex-desktop-read-only-adapter-implementation.md`；
- 活跃文档继续保持 50 个，历史内容未删除；
- 同步 digest、index、roadmap、README、AGENTS、CLI usage、Stage 26 设计门、handoff 与 progress。

## 下一阶段

Stage 28 — Filtered Snapshot Host Consumer Validation Gate（条件启动）。只有具体宿主需要独立验证 v3 schema/filter/view identity 时启动。

本阶段不创建 tag；`v0.13.0-read-only-control-plane` / `f401b98` 继续作为稳定 milestone。
