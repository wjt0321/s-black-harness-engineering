# Release Notes 91 — Stage 29 Codex Desktop Filtered Snapshot Consumer

## 阶段结论

Stage 29 已按 Stage 28 contract 完成独立 filtered v3 stdin consumer 实现与收口。

## 新增实现

- `tools/codex_desktop_filtered_snapshot_consumer.py`
- 输入完整 `control-plane/codex-desktop-snapshot-read/v3`；
- 输出 `control-plane/filtered-snapshot-host-consumer-validation/v1`；
- 标准库-only、stdin-only、1 MiB 输入、64 KiB 输出；
- 固定 11 项检查、确定性状态/退出码与 value-safe finding。

## 安全与 identity

- 独立重算 scope/filter/view identity；
- base snapshot、envelope content、handoff identity 只做 shape/link 检查；
- 严格验证 ready lifecycle、guarantees、safe sections、counts 与 filter semantics；
- 不回显 filter/path/rows/raw input；
- 不读文件、不访问网络、不写入、不启动 service、不执行 reader/command/adapter。

## TDD 与兼容

- 新增 `tests/test_codex_desktop_filtered_snapshot_consumer.py`；
- 首个 valid v3 用例先确认因工具不存在而 RED；
- nested payload/filter schema allowlist 修正也先确认 RED；
- 真实 reader stdout → consumer stdin smoke 返回 pass；
- Stage 18 consumer 与 Stage 27 reader contract 保持兼容。

## 文档维护

- 新增 `docs/89-codex-desktop-filtered-snapshot-consumer-implementation.md`；
- 早期 `docs/archive/14-task-runtime-bridge.md` 完整归档至 `docs/archive/14-task-runtime-bridge.md`；
- 活跃文档保持 50 个，历史内容未删除；
- 同步 digest、index、roadmap、README、AGENTS、CLI usage、Stage 28 gate、handoff 与 progress。

## 下一阶段

Stage 30 — Codex Desktop Filtered Snapshot Host Integration Gate（条件启动）。第一拍只允许冻结固定 reader → consumer 管道的宿主调用、状态映射和一次性展示边界，不默认引入 UI、service 或持久化。

本阶段不创建 tag；稳定 milestone 仍为 `v0.13.0-read-only-control-plane` / `f401b98`。
