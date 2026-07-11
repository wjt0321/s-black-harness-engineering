# 000 — Stage Digest

> **新会话先读这份，不要先翻整仓文档。**

## 文档池规模

- docs/ 活跃文档：~35 个
- 归档文档：`docs/archive/`（release-notes / dry-runs / smoke-regression）
- 全仓 .md 文件：~140 个
- **文档维护规则：`docs/MAINTENANCE.md`**

## 当前基线

- 稳定基线：`v0.12.0-orchestration-foundation`
- 冻结 commit：`38b4b69`
- 当前 HEAD：以 `git rev-parse --short HEAD` 为准

## 当前阶段

- **Stage 15.99 — Run Lineage / Recovery Read Model 第一版**
- 当前成果：retry / fallback lineage 已经形成 **可写 + 可读** 的最小闭环
- **新进落地：Stage 10 — Adapter Runtime Interface Registry 投影第一版**
  - `agent_runtime/adapter_registry.py`：从现有 `adapters/adapters.sample.json` 投影出 Stage 10 元数据，单一事实源
  - `agent_runtime/orchestration_adapter.py`：只读 read model
  - CLI：`orchestration adapter list` / `orchestration adapter inspect <adapter_id>`
  - 投影字段清楚标识 derived/defaulted；schema ref 为指向该 entry 内嵌 schema 的真实 JSON Pointer
  - 不过滤 disabled entries，与 `loader.load_adapters` 同批条目语义一致
  - 测试覆盖：source 变更反射、schema pointer 解析、disabled entry 保留、loader 一致性、模型校验、列表稳定排序、inspect、JSON、人类可读输出、未知 ID、缺文件/非法 JSON/schema 错误

## 现在已经能做什么

- retry / fallback commit 第一版已落地
- `orchestration run inspect` 可见 lineage
- `orchestration run list` 可见紧凑 lineage 标识
- `orchestration report generate` 可见 lineage 安全摘要
- `python -m agent_runtime.cli docs context` 可输出恢复入口
- `orchestration adapter list` / `inspect` 可查询内置 adapter capability registry

## 下次恢复顺序

1. 先读：`docs/000-stage-digest.md`（本文件）
2. 再跑：`python -m agent_runtime.cli docs context`
3. 再读：`docs/02-roadmap.md`
4. 如需接续上轮会话：读最新 `tasks/handoff-*.md`

## 下一步做什么

- **优先方向：Stage 10 — Adapter Runtime Interface（已落地第一版，继续巩固）**
- 入口文档：`docs/48-adapter-runtime-interface.md`
- 目标：把中枢台后端主线继续往前推，不急着跳真实执行；后续可把 registry 与 `orchestration route preview` / `orchestration preflight` 进一步打通

## 重要约束

- 仍然**不做真实 adapter execution**
- 仍然**不做 UI / service / DB**
- 编码默认继续交给 Kimi；主控负责审核、文档、提交、push

## 一句话理解当前项目

这项目现在的重点不是继续堆零散功能，而是：

> 在保持受控写入边界的前提下，把 orchestration control-plane 的恢复链路、read model 和后端主线继续做扎实。
