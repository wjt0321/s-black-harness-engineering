# Release Notes — Stage 14 — Minimal Orchestration Loop

日期：2026-07-13

## 结论

Stage 14「中枢台最小编排闭环」完成收口。本阶段把 Stage 13 已冻结的 CLI/read-model 边界应用到一个本地、受控、可回放、可审计的最小闭环；不引入 service/API/UI/DB，不执行真实 adapter。

## 已交付

- 对账并冻结七步闭环：Task Submit → Routing → Preflight → Dry-run/Controlled Commit → Lifecycle/Event/Artifact/Evidence Projection → Approval → Report。
- read-loop snapshot 的 Report Preview 新增 `evidence_candidate_count` 与 `evidence_candidate_type_counts`，直接投影 dry-run 结果，不伪造 Evidence。
- 新增显式 `--replay`：
  - `orchestration run inspect --replay`
  - `orchestration report generate --replay`
- 两个入口复用同一份 runtime report，输出 `control-plane/orchestration-replay/v1`，不新增第二套状态计算。
- 冻结结构化 `next_action.code`：
  - `proceed_to_commit`
  - `blocked_wait_for_approval`
  - `needs_input`
  - `needs_human_review`
  - `task_finished`
- replay state 仅保留 task/request、事件计数、最新事件安全字段、gate 状态、artifact/response/evidence 计数和 ledger 状态；不回显 target、payload、凭据、raw ref、decision ref 或 Evidence 正文。
- docs context 能识别 digest 中的「已完成」阶段，便于新会话恢复。

## 验收覆盖

- 跨 `run inspect` / `report generate` replay projection 一致；
- 默认输出不传 `--replay` 时保持兼容；
- read-loop preview 的 pass / approval / input / blocked next-action 映射；
- replay 的确定性、脱敏和 no-write；
- 既有 controlled write rollback、retry/fallback lineage、approval 和全量回归继续通过。

## 明确不交付

- 独立 Run/Event/Report 持久集合；
- HTTP/RPC/API service、鉴权、UI、数据库；
- 真实 adapter 或外部命令执行；
- 自动化多系统放权和长期后台服务。

## 基线与下一步

- 稳定 semver 基线保持 `v0.12.1-orchestration-read-loop-snapshot` / `0419a04`；本阶段不创建新 tag。
- Stage 14 收口提交为本地 commit，等待用户明确指令后再 push。
- 后续不自动启动新阶段；长期候选 Stage 16 UI / Control Panel 仍保持远期。
