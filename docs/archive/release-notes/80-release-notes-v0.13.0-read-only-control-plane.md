# 80 — Release Notes：v0.13.0 Read-only Control Plane

## 里程碑定位

`v0.13.0-read-only-control-plane` 冻结 Stage 13–16 形成的本地 Control Plane 能力包。它提供后端边界、可回放编排、CLI 自动化契约和静态只读控制面，但不表示真实执行、服务化或持久化平台已经开放。

## 相对 v0.12.1 的新增能力

- 真实 CLI/read models 的 stable、stable_limited、preview、unavailable 边界；
- 最小 orchestration replay 与结构化 `next_action`；
- recovery lineage aggregation 与 inspect/report 复用；
- machine-readable orchestration contract 与 Requirement Gate；
- source-backed Automation Profile；
- deterministic Workflow Plan 与 content-hash drift validation；
- `control-plane/control-panel-snapshot/v1`；
- 自包含、无网络、无写入的静态 Control Panel HTML。

## 兼容与安全

- 既有 CLI 默认输出保持兼容；
- preview 能力继续显式，不升级为真实持久资源；
- controlled write 继续要求 `--commit`，并保持写前校验、写后校验、失败回滚；
- 不执行真实 adapter 或外部 command；
- 不启动 service、不访问网络、不读取 credential；
- 不引入 DB、auth、实时订阅或 UI 写操作。

## 验证

<!-- freeze-verification -->
以下冻结验证均通过：

```bash
python -m pytest tests -q
python -m agent_runtime.cli doctor
python tools/public_scan.py
python -m pytest tests/test_controlled_write_regression.py -q
python -m compileall -q agent_runtime tests
python -m agent_runtime.cli docs context --json
git diff --check
bash .githooks/pre-commit
```

验证结论：

- 全量 pytest 通过；
- doctor PASS；
- public scan OK；
- controlled-write regression 通过；
- compileall、docs context、diff check 与 docs maintenance hook 通过；
- Stage 16 Chromium 验收继续有效：8 个 section、过滤交互、键盘聚焦、移动端 overflow containment、无 console/page error；
- freeze commit 推送后，GitHub Actions `CI` 的 Python 3.11 / 3.12 matrix 均通过，随后才创建并推送 annotated tag。
<!-- /freeze-verification -->

## 冻结入口

- Freeze checklist：`docs/77-read-only-control-plane-milestone-freeze.md`；
- Version governance：`docs/64-versioning-governance.md`；
- Stage digest：`docs/000-stage-digest.md`；
- Handoff：`tasks/handoff-2026-07-14.md`。

## 后续边界

下一个 semver tag 继续以里程碑能力包为单位，不为单个文档、单个 preview 命令或单个 UI 增量自动创建 tag。
