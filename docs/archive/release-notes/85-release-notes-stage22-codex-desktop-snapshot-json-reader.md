# 85 — Stage 22 Codex Desktop Snapshot JSON Reader

> 日期：2026-07-15
> 状态：验收完成
> 设计与实现事实源：`docs/83-codex-desktop-snapshot-json-reader-implementation.md`

## 1. 交付

- 新增 `tools/codex_desktop_snapshot_json_reader.py`；
- 新增 `tests/test_codex_desktop_snapshot_json_reader.py`；
- 用户必须显式传入 `--representation snapshot-json`；
- 固定执行 handoff producer → Stage 18 consumer → snapshot producer；
- 输出 `control-plane/codex-desktop-snapshot-read/v1`；
- 将已验证 snapshot JSON 作为有界内存/stdout representation 返回。

## 2. Identity 与协议门禁

`ready` 前验证：

- handoff consumer `pass`；
- snapshot strict UTF-8 JSON object，无 duplicate key；
- snapshot schema/status/source/guarantees；
- snapshot id 与 handoff 声明一致；
- snapshot canonical content hash 与 id 一致；
- 子进程 exit code、timeout 与 1 MiB 输出上限。

## 3. 安全边界

- 不执行 descriptor argv；
- 不读取 HTML，不打开浏览器；
- 不接受 envelope、URL、socket、任意文件路径或 shell 字符串；
- 不写文件、ledger、draft、artifact 或 Python bytecode cache；
- 不访问网络，不启动 service/background process；
- 不执行 candidate command 或真实 adapter；
- 不自动重试。

## 4. 验收

目标测试、真实 Windows 三段 stdio smoke、全量 pytest、doctor、public scan、controlled-write regression、compileall、pre-commit 与 `git diff --check` 均通过。

下一阶段为条件启动的 Stage 23 Envelope-scoped Snapshot Read Design Gate；Stage 22 完成不自动开放 envelope、HTML、浏览器或 export。

## 5. Post-close 文档沉淀

- 将已被当前冻结事实源取代的 `68` / `69` 两份 `v0.12.0` freeze 历史文档完整移入 `docs/archive/`；
- 更新全部当前路径引用与维护规则；
- 活跃 `docs/` 根目录 Markdown 数从 51 降至 49；
- 无内容删除，无生产代码行为变化，Stage 23 条件启动边界不变。
