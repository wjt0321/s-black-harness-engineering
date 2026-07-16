# Release Notes 90 — Stage 28 Filtered Snapshot Host Consumer Validation Gate

## 阶段结论

Stage 28 已完成设计审计并收口。用户明确要求继续推进后，本阶段选择 Codex Desktop 本地任务进程作为具体宿主，冻结 filtered v3 独立 consumer contract，但未实现 consumer。

## 关键决策

- consumer 输入为完整 `control-plane/codex-desktop-snapshot-read/v3` result，不接受 payload-only；
- 未来使用专用标准库-only stdin consumer，不扩展 Stage 18 handoff consumer；
- 只接受 ready、closed lifecycle、pass handoff/representation 与严格 guarantees；
- 独立重算 scope id、filter id 与 view id；
- base snapshot id 因无 base payload 只做 cross-field/shape 校验，不伪称重算；
- 严格验证 safe sections、summary counts 与 task/request relation semantics；
- validation result 不回显 payload/filter/path，stdout 上限 64 KiB；
- 不读文件、不访问网络、不写入、不执行 subprocess/argv/adapter。

## Contract evidence

新增 `tests/test_filtered_snapshot_host_consumer_contract.py`，通过真实 Stage 27 reader stdout 冻结 v3 wrapper、identity links、guarantees、安全 sections、determinism、1 MiB 与 no-raw-value 前置契约。

## 文档维护

- 当时新增 `docs/88-filtered-snapshot-host-consumer-validation-gate.md`，现已完整归档至 `docs/archive/88-filtered-snapshot-host-consumer-validation-gate.md`；
- 旧 `docs/09-policy-checker-poc-plan.md` 已完整归档至 `docs/archive/09-policy-checker-poc-plan.md`；
- 活跃文档继续保持 50 个，历史内容未删除；
- 同步 digest、index、roadmap、README、AGENTS、Stage 27 fact source、handoff 与 progress。

## 下一阶段

Stage 29 — Codex Desktop Filtered Snapshot Consumer Implementation（条件启动）。必须按 Stage 28 TDD 矩阵先确认 RED，再实现独立 stdin-only consumer。

本阶段不创建 tag；`v0.13.0-read-only-control-plane` / `f401b98` 继续作为稳定 milestone。
