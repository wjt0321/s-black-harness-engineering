# 72 — Stage Digest / Recovery Summary

> 这是一份紧凑恢复摘要，不是 roadmap 复刻。新会话建议先跑 `python -m agent_runtime.cli docs context`，再读本篇，再按需深入 roadmap / index / handoff。

## 当前稳定基线

- 里程碑：`v0.12.0-orchestration-foundation`
- 冻结 commit：`38b4b69`
- 治理模式：阶段编号 + release notes 收口，semver / Git tag 只在里程碑节点冻结

## 当前阶段

- **Stage 15.99 — Run Lineage / Recovery Read Model 第一版**
- 刚完成：让 retry/fallback lineage 在 `orchestration run inspect / list / report generate` 与 `docs context` 中稳定、脱敏地可见。

## 最近完成的 5 个阶段/里程碑

1. **Stage 15.97** — Orchestration Foundation Freeze 完成（基线 `38b4b69` / `v0.12.0-orchestration-foundation`）
2. **Stage 15.96** — Orchestration Run Retry / Fallback Dry-run 落地
3. **Stage 15.95** — Orchestration Task Submit Created Event 落地
4. **Stage 15.9** — Orchestration Run Lifecycle Events 落地
5. **Stage 15.8** — Orchestration Run Commit（A-only）落地

## 推荐恢复顺序

1. `docs/000-stage-digest.md` — 快速确认当前基线与阶段
2. `docs/02-roadmap.md` — 看双主线大图与下一阶段
3. `docs/00-index.md` — 按主题选读
4. `tasks/handoff-latest.md` — 接续上回会话上下文（实际文件名为 `tasks/handoff-YYYY-MM-DD-*.md` 最新一份）

## 下一步推荐入口

- **Stage 10 — Adapter Runtime Interface**（中枢台后端主线下一高优先级）
- 入口文档：`docs/48-adapter-runtime-interface.md`
- 重点：adapter 分类（agent / tool / service）、统一 metadata、request/response/artifact/evidence/error 模型

## 文档增长后的使用建议

- 不要从头顺序读 `docs/`。
- 先用 `docs context` 拿到 10 项以内的恢复清单。
- 想确认“现在做到哪” → 读本篇 digest。
- 想规划下一步 → 读 roadmap 与 `docs/48-adapter-runtime-interface.md`。
- 想回接上回会话 → 读最新 `tasks/handoff-*.md`。
