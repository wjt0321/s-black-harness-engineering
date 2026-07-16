# 77 — v0.13.0 Read-only Control Plane Milestone Freeze

> 归档状态：2026-07-16 被 `docs/90-codex-desktop-filtered-snapshot-host-integration-and-milestone-freeze.md` 取代后完整移入 archive；本文仍是 v0.13.0 历史事实源。

<!-- parents: 64-versioning-governance.md, 76-read-only-control-panel-mvp.md -->
<!-- relates: 51-backend-first-api-boundary.md, 52-minimal-orchestration-loop.md, 75-cli-automation-contract-discovery.md -->

## 1. 冻结结论

Stage 13–16 已形成一个可独立描述、可审计、可重复验证的能力包，满足里程碑 tag 条件。本轮冻结名为：

```text
v0.13.0-read-only-control-plane
```

该 tag 表示 **本地、确定性、可回放、只读优先的 Control Plane 基线**，不是 live service、生产执行平台或可写 UI。

## 2. 相对 v0.12.1 的语义变化

上一冻结点 `v0.12.1-orchestration-read-loop-snapshot` 覆盖 Stage 10–12 的 registry、routing、decision trace 与 routing/read-loop snapshot。

本次新增能力包包括：

- Stage 13 Backend-first API Boundary：stable / stable_limited / preview / unavailable 边界与 argparse 契约；
- Stage 14 Minimal Orchestration Loop：Evidence candidate projection、replay 与结构化 `next_action`；
- CLI automation consumer：contract discovery、Requirement Gate、Automation Profile、Workflow Plan 与 drift check；
- Stage 16 Read-only Control Panel：确定性 snapshot 与自包含静态 HTML；
- retry/fallback lineage 的写入、读取与 recovery aggregation；
- 受控 run/task/approval 写入边界继续保持显式 `--commit`、校验与回滚。

## 3. 对外可引用能力

### Read-only / preview

- `orchestration overview`
- task/run/approval/artifact/report read models
- route/preflight 与 routing/read-loop snapshot
- recovery lineage aggregation 与 replay
- `orchestration contract inspect/check`
- `orchestration profile list/inspect/check`
- `orchestration workflow plan/check`
- `orchestration control-panel snapshot/render`

### Controlled write

- task submit A+B；
- run commit envelope draft + lifecycle events；
- approval resolve 仅记录 decision；
- retry/fallback commit lineage；
- 所有写操作仍不执行真实 adapter。

## 4. 明确不属于本里程碑

- 真实 adapter / 外部命令执行；
- live HTTP/API/service/background process；
- auth/session、多租户、计费；
- DB 与独立 Run/Report/Artifact collection；
- 实时刷新、WebSocket、在线 availability probe；
- UI controlled write；
- 模型代理或生产调度平台。

## 5. 冻结证据

- Stage 13：`docs/archive/release-notes/76-release-notes-stage13-backend-first-api-boundary.md`；
- Stage 14：`docs/archive/release-notes/77-release-notes-stage14-minimal-orchestration-loop.md`；
- CLI automation：`docs/archive/release-notes/78-release-notes-cli-automation-consumer.md`；
- Stage 16：`docs/archive/release-notes/79-release-notes-stage16-read-only-control-panel.md`；
- 里程碑 release notes：`docs/archive/release-notes/80-release-notes-v0.13.0-read-only-control-plane.md`。

## 6. 冻结验证

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

## 7. Git 冻结动作

1. 提交本里程碑文档与入口同步；
2. 确认 `main` 与 `origin/main` 一致；
3. 确认 GitHub CI 的 Python 3.11 / 3.12 检查通过；
4. 在 freeze commit 创建 annotated tag；
5. 推送 tag；
6. 不创建额外 stage tag。

Annotated tag message 保持紧凑：

```text
Freeze the Stage 13-16 read-only control plane milestone

Includes:
- backend-first orchestration boundaries
- replay and recovery lineage read models
- CLI automation contracts and workflow projections
- deterministic static read-only Control Panel
```

## 8. 后续策略

`v0.13.0-read-only-control-plane` 冻结后，下一 tag 不按单个 Stage 自动增长。只有出现新的稳定能力包，例如 live service boundary、宿主集成或受控 UI operation，并完成独立设计 gate 与验收时，才考虑后续 semver milestone。


## 9. 实际冻结结果

- freeze commit：`f401b98`；
- annotated tag：`v0.13.0-read-only-control-plane`；
- tag 指向：`f401b9807eaa778de2cc0953f220ef27a06a5429`；
- GitHub Actions run `29325425721`：Python 3.11 / 3.12 jobs 均通过；
- tag 与 `main` 均已推送到 `origin`。
