# 86 — Release Notes: Stage 24 Codex Desktop Envelope-scoped Snapshot JSON Reader

<!-- parents: ../../84-envelope-scoped-snapshot-read-design-gate.md -->
<!-- relates: ../../83-codex-desktop-snapshot-json-reader-implementation.md -->

## 1. 阶段结论

Stage 23 design gate 已通过，Stage 24 envelope-scoped snapshot JSON reader 已实现并收口。

用户现在可以在继续显式选择 `snapshot-json` 的同时，提供 allowlist 内的 project-relative envelope：

```bash
python tools/codex_desktop_snapshot_json_reader.py \
  --project-root . \
  --representation snapshot-json \
  --envelope adapters/execution-envelope.examples.json \
  --timeout-seconds 30 \
  --json
```

无 `--envelope` 时保持 Stage 22 `v1` 输出和 unavailable 边界；显式 envelope scope 时输出 `control-plane/codex-desktop-snapshot-read/v2`。

## 2. 新增能力

- `--envelope` 只接受 project-relative allowlist：
  - `adapters/*.json`；
  - `drafts/runtime/**/*.envelope.json`。
- 拒绝绝对路径、drive/UNC path、`..`、非 canonical path、allowlist 外路径和 project-root 外 symlink。
- 读取前执行 1 MiB、strict UTF-8、duplicate-key、JSON object、schema、cross-artifact consistency 与 secret scan 门禁。
- scope source 包含 normalized `relative_envelope`、`envelope_content_id` 与 canonical `scope_id`。
- handoff source 必须匹配显式 scope；consumer 的 `source_handoff_id` 必须匹配 handoff；snapshot source/id/canonical hash 必须匹配。
- snapshot 返回后再次读取 envelope content id，拒绝 one-shot 生命周期内的内容漂移。
- scoped snapshot 只复用既有 runs / approvals / artifacts 安全摘要，不输出 request `input`、payload refs 或 raw refs。

## 3. 兼容性

- 未提供 `--envelope`：继续输出 Stage 22 `control-plane/codex-desktop-snapshot-read/v1`。
- 提供合法 `--envelope`：输出 `control-plane/codex-desktop-snapshot-read/v2` 与 `codex-desktop-envelope-snapshot-json-reader/v2`。
- representation 仍只有 `snapshot-json`，且必须显式选择。
- descriptor argv 仍不执行；reader 只构造固定 producer/consumer/snapshot argv。

## 4. 安全边界

以下能力仍未开放：

- HTML/browser representation read；
- URL/socket/任意路径；
- 网络访问或长期 service；
- 文件、ledger、draft、artifact export 写入；
- candidate command 或真实 adapter execution；
- retry/fallback/background refresh；
- request-scoped report collection。

## 5. TDD 与验收

新增测试覆盖：

- scoped v2 成功路径与真实 stdio；
- fixed argv，不消费 descriptor argv；
- absolute/parent/disallowed/missing path；
- duplicate key 与 secret scan；
- handoff scope mismatch；
- envelope content drift；
- v1 默认兼容与 scoped section projection。

收口验证：

```bash
python -m pytest tests -q
python -m agent_runtime.cli doctor
python tools/public_scan.py
python -m pytest tests/test_controlled_write_regression.py -q
python -m compileall -q agent_runtime tests tools
python -m agent_runtime.cli docs context --json
git diff --check
bash .githooks/pre-commit
```

<!-- release-status: stage24-complete -->
