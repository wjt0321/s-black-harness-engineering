# Release Notes 88 — Stage 26 Filtered Envelope Snapshot Read Design Gate

## 阶段结论

Stage 26 已完成设计审计并收口。用户明确要求直接进入下一阶段后，本阶段冻结了结构化 task/request filter 的输入、匹配、identity、输出版本与安全边界；生产 reader 尚未修改。

## 冻结内容

- filter 只接受 `--task-id` / `--request-id`，至少一个，允许二者 AND；
- filter 必须与显式 envelope 同时使用；非法、重复或非 canonical 输入在 spawn 前失败；
- 仅过滤已验证 snapshot 的 runs/approvals/artifacts 安全 summaries；
- task filter 通过 run request→task 映射包含缺少直接 task_id 的 response artifacts；
- request filter exact match，不自动扩展 retry/fallback lineage；
- 无匹配返回 `ready`、空列表与 `matched=false`，不猜测；
- v3 使用新的 reader result、filtered payload 与 filter schema，不静默改变 v1/v2；
- `filter_id` 绑定 canonical filter，`view_id` 绑定 filtered payload，source 关联 base snapshot id 与 scope id；
- child argv 保持 Stage 24 固定三段链路，不传 filter、不执行 descriptor argv；
- no query、no sort/page、no persistence/export、no HTML/browser/network/write/execute。

## 验收前置证据

新增 Stage 26 prerequisite contract test，确认现有安全 summaries 具备 request/task join keys，并明确 adapter response 可能需要 request→task 关系闭包。

## 文档维护

- 新增 `docs/86-filtered-envelope-snapshot-read-design-gate.md`；
- Stage 21 validation-only 设计门已被 Stage 22 reader 及后续事实源取代，完整归档至 `docs/archive/82-read-only-representation-read-design-gate.md`；
- 活跃文档继续保持 50 个，历史内容未删除；
- 同步 digest、index、roadmap、README、AGENTS、CLI usage、handoff 与 progress。

## 下一阶段

Stage 27 — Filtered Envelope Snapshot JSON Reader Implementation（条件启动），按 Stage 26 的 v3、identity 与 TDD 矩阵实现。

本阶段不创建 tag；`v0.13.0-read-only-control-plane` / `f401b98` 继续作为稳定 milestone。
