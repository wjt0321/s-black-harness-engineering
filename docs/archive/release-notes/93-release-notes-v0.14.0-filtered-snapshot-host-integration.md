<!-- parents: ../../../docs/archive/90-codex-desktop-filtered-snapshot-host-integration-and-milestone-freeze.md -->
<!-- relates: 80-release-notes-v0.13.0-read-only-control-plane.md -->

# Release Notes 93 — v0.14.0 Filtered Snapshot Host Integration

> 日期：2026-07-16
> 状态：本地里程碑冻结

## 里程碑

```text
v0.14.0-filtered-snapshot-host-integration
```

本里程碑在 `v0.13.0-read-only-control-plane` 上增加 Stage 17–31 的完整只读宿主消费链：

1. stdio handoff；
2. 独立 handoff consumer；
3. Codex Desktop one-shot adapter boundary；
4. project/envelope scoped snapshot JSON reader；
5. task/request exact filtered v3；
6. 独立 filtered snapshot consumer；
7. validation-before-display one-shot host。

## 冻结能力

- explicit project root、allowlisted envelope 与 exact filter；
- deterministic base/scope/filter/view identity；
- bounded fixed subprocess/stdin pipeline；
- consumer pass 之前不展示 payload；
- 只展示 filtered safe summaries；
- stable status/exit mapping 与 value-safe failure。

## 未开放

- Codex Desktop 专有插件/UI；
- HTML/browser/live refresh；
- service/network/DB/auth；
- cache/persistence/export；
- arbitrary query/sort/page/lineage expansion；
- UI controlled write 或真实 adapter execution。

## 验证

- 857 项全量 pytest 通过；
- doctor、public scan、py_compile、真实 one-shot smoke 通过；
- 文档 hook 与 `git diff --check` 在冻结提交前通过。

本次 annotated tag 按用户要求只创建在本地，不 push。下一阶段为 Stage 33 Codex Desktop Filtered Snapshot Display Integration Gate（条件启动）。
