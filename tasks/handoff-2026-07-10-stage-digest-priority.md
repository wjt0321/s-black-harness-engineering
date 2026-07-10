# 2026-07-10 Stage Digest Priority Handoff

## 当前结论

今天的最后一拍目标，是把 `docs/000-stage-digest.md` 固定成**最高优先级恢复入口**，让后续新会话或新窗口里的智能体，不需要先阅读大量上下文，就能在最短路径上恢复项目状态、当前目标与下一步方向。

## 已完成

- `docs/72-stage-digest.md` 已提升并重命名为 `docs/000-stage-digest.md`
- `docs context` 已改为优先读取 `docs/000-stage-digest.md`
- `tests/test_docs_context.py` 已同步适配 digest 新路径
- `docs/10-cli-poc-usage.md` 已同步更新为 `docs/000-stage-digest.md`
- 当前 `docs/000-stage-digest.md` 已被压缩为更短、更偏执行导向的恢复摘要

## 这份 digest 的定位

它不是 roadmap，也不是 progress，也不是 handoff 替代品。

它的唯一目标是：

> **让新会话先读这一页，就知道现在在哪、下一步做什么、哪些东西不要做。**

因此它应该长期保持：

- 短
- 明确
- 目标导向
- 尽量少历史废话
- 尽量少细节堆积

## 当前 digest 应维持的内容边界

应该保留：

- 当前稳定基线
- 当前阶段
- 现在已经能做什么
- 下次恢复顺序
- 下一步做什么
- 重要约束
- 一句话理解当前项目

不应继续膨胀成：

- 长 release notes
- 完整 roadmap 复刻
- 详细变更流水
- 冗长 handoff

## 当前推荐下一步

如果继续推进项目主线，当前最自然的方向仍然是：

- **Stage 10 — Adapter Runtime Interface**
- 入口文档：`docs/48-adapter-runtime-interface.md`

原因：

- retry/fallback commit 已落地
- lineage read model 已补齐
- docs context + stage digest 恢复层已补上
- 现在更适合回到 orchestration backend 主线，而不是继续横向扩很多恢复类细节

## 若今天结束前要做的最后动作

1. 跑一次最小校验：
   - `python -m pytest tests/test_docs_context.py -q`
   - `python -m agent_runtime.cli doctor`
   - `python tools/public_scan.py`
   - `git diff --check`
2. 提交 digest 精简与 handoff
3. push 到远端
4. 若 GitHub 网络不通：
   - 先尝试直连 push
   - 失败时按既有规则使用代理/V2Ray
   - push 成功后关闭 V2Ray，归还网络

## 给下次新会话的最短提示

如果下次要最快恢复，只要这么做：

1. 读 `docs/000-stage-digest.md`
2. 跑 `python -m agent_runtime.cli docs context`
3. 若要继续主线，读 `docs/48-adapter-runtime-interface.md`
4. 若要接续今天会话，再读这份 handoff