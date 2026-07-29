# Agent Deck P0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first usable Agent Deck workbench: a Chinese React desktop-style UI that renders a safe, versioned projection of real Pi/OMP status and existing registered collaboration work, while preserving the Python Harness as the only execution authority.

**Architecture:** Add a Python `agent_deck_projection` read model that narrows the existing `control-panel-snapshot/v1` and registered-work inbox into a stable `agent-deck/read-model/v1` document. A fixed, atomic `.runtime/agent-deck/v1/agent-deck.snapshot.json` export is the only P0 frontend data handoff; it is generated only by an explicit `--commit` CLI action. A Vite/React/Tailwind/shadcn frontend reads that safe static document in foreground development mode and contains no process, credential, filesystem, or command authority.

**Tech Stack:** Python 3.11+ and pytest; React 19.2.8; React DOM 19.2.8; TypeScript 7.0.2; Vite 8.1.5; `@vitejs/plugin-react` 6.0.4; Tailwind CSS 4.3.3; `@tailwindcss/vite` 4.3.3; shadcn CLI 4.16.0; lucide-react 1.27.0; Vitest 4.1.10; Testing Library React 16.3.2; Testing Library user-event 14.6.1; jsdom 30.0.1.

## Global Constraints

- UI 默认简体中文；Pi、OMP、Codex CLI、Claude Code 等名称可保留并紧邻中文角色说明。
- Python Harness 是唯一 command authority。React 只读取 `agent-deck/read-model/v1`，不得执行 Agent、写 ledger、读取凭据、传入 argv/cwd/env 或构造通用命令。
- 固定 exporter 只可写入 `.runtime/agent-deck/v1/agent-deck.snapshot.json`；不接受输出路径、不启动服务、不开放 socket、数据库、网络 adapter 或后台调度。
- 快照仅包含已经安全投影的标题、状态、角色、摘要、digest 和已登记工作卡。不得含原始 prompt、stdout/stderr、session reference、绝对路径、secrets、keys、tokens 或原始事件文本。
- P0 只有 Pi/OMP 是 live 成员。Codex CLI、Claude Code、Kimi Code 是固定 `not_integrated` 展示卡，绝不伪造 readiness 或执行能力。
- P0 不新增 React UI dispatch。Pi/OMP 启动、最终决定和有限放弃继续走既有 Tk GUI 的严格结构化信封，直到另行设计桌面 command bridge。
- Vite 仅为开发阶段的前台工具，不是产品服务；Tauri/IPC/常驻服务不在 P0。
- 新 Python 和 TypeScript 行为一律先写失败测试；既有 Control Panel、approval、lease、audit、evidence 与 Stage 93 测试不得弱化。
- 每项提交都需要用户在实施会话中明确授权。

---

### Task 1: Freeze documentation, supply-chain, and the fixed frontend handoff

**Files:**
- Modify: `docs/143-agent-deck-platform-mvp.md`
- Modify: `docs/superpowers/specs/2026-07-29-agent-deck-platform-mvp-design.md`
- Modify: `decisions/0002-deferred-shadcn-frontend-direction.md`
- Modify: `.gitignore`
- Create: `tests/test_agent_deck_docs.py`

**Interfaces:**
- Consumes: approved Agent Deck P0 design.
- Produces: explicit `agent-deck/read-model/v1`, fixed snapshot path and frontend dependency policy.

- [ ] **Step 1: Write the failing documentation contract test**

```python
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_agent_deck_documents_declare_a_fixed_safe_snapshot_handoff() -> None:
    stage = (ROOT / "docs/143-agent-deck-platform-mvp.md").read_text(encoding="utf-8")
    spec = (ROOT / "docs/superpowers/specs/2026-07-29-agent-deck-platform-mvp-design.md").read_text(encoding="utf-8")
    assert "agent-deck/read-model/v1" in spec
    assert ".runtime/agent-deck/v1/agent-deck.snapshot.json" in spec
    assert "P0 不新增 UI dispatch" in stage
```

- [ ] **Step 2: Verify it fails, then add the exact contract**

Run `python -m pytest tests/test_agent_deck_docs.py -q`; it must fail before the wording is added. Add this exact design block:

```markdown
### P0 前端数据交接

Python 只通过 `agent-deck/read-model/v1` 生成安全只读投影。显式 `--commit` 仅原子写入固定文件 `.runtime/agent-deck/v1/agent-deck.snapshot.json`；不接受输出路径，不启动服务，不开放 UI dispatch。React 开发工作台只读取该固定安全快照；当前真实 Pi/OMP 启动和最终决定继续由既有 Tk GUI 严格结构化信封完成。
```

Pin the package versions in the shadcn decision, require `frontend/package-lock.json`, and add only these ignores:

```gitignore
.runtime/agent-deck/
frontend/dist/
frontend/coverage/
```

- [ ] **Step 3: Verify and commit when authorized**

Run `python -m pytest tests/test_agent_deck_docs.py -q`, `python -m agent_runtime.cli docs context --json`, `python tools/public_scan.py`, and `git diff --check`. On explicit authorization, commit only these docs, ignore rules and the documentation test with message `docs: plan agent deck workbench foundation`.

---

### Task 2: Add the bounded Python Agent Deck read model

**Files:**
- Create: `agent_runtime/agent_deck_projection.py`
- Create: `tests/test_agent_deck_projection.py`

**Interfaces:**
- Consumes: `control_panel_live_gui.build_live_control_panel_snapshot` and `orchestration_control_panel_registered_work.load_registered_work_inbox`.
- Produces: `AGENT_DECK_SCHEMA_VERSION`, `AgentDeckSnapshot`, and `build_agent_deck_snapshot(root: Path, *, evaluated_at: str, chain_limit: int = 20) -> AgentDeckSnapshot`.

- [ ] **Step 1: Write failing projection tests**

Use monkeypatches for the two existing read models; do not create host processes. Require an ordered Agent list `pi-local`, `omp-local`, `codex-cli`, `claude-code`, `kimi-code`. Require Pi/OMP `integration_status="live"` only when their safe source projection exists. Require the exact pending record:

```python
{
    "id": "codex-cli",
    "name_zh": "Codex CLI",
    "role_zh": "待接入成员",
    "integration_status": "not_integrated",
    "status": "unknown",
    "status_label_zh": "待接入",
    "safe_summary_zh": "尚未接入真实状态或执行能力。",
}
```

Add tests for invalid `chain_limit`, missing Pi/OMP data, deterministic output for the same evaluated time, safe registered cards only, and a chain timeline that contains no raw prompt/output field.

- [ ] **Step 2: Run and confirm the red state**

Run `python -m pytest tests/test_agent_deck_projection.py -q`. Expected: `ModuleNotFoundError` for `agent_runtime.agent_deck_projection`.

- [ ] **Step 3: Implement the narrowed read model**

```python
AGENT_DECK_SCHEMA_VERSION = "agent-deck/read-model/v1"
MAX_CHAIN_LIMIT = 20
PENDING_AGENTS = (("codex-cli", "Codex CLI"), ("claude-code", "Claude Code"), ("kimi-code", "Kimi Code"))

@dataclass(frozen=True)
class AgentDeckSnapshot:
    status: str
    payload: dict[str, Any]
    def to_dict(self) -> dict[str, Any]: return self.payload
    def exit_code(self) -> int: return EXIT_PASS if self.status == "pass" else EXIT_ERROR

def build_agent_deck_snapshot(root: Path, *, evaluated_at: str, chain_limit: int = MAX_CHAIN_LIMIT) -> AgentDeckSnapshot:
    panel = build_live_control_panel_snapshot(root.resolve(), evaluated_at=evaluated_at, chain_limit=chain_limit)
    return _project_panel(panel.to_dict(), load_registered_work_inbox(root).to_safe_dict(), evaluated_at)
```

Call `build_live_control_panel_snapshot(root.resolve(), evaluated_at=evaluated_at, chain_limit=chain_limit)` once. Read only its `external_agents` and `external_agent_chains` sections plus `load_registered_work_inbox(root).to_safe_dict()`. Emit safe `project`, `agents`, `registered_work`, `tasks`, `timeline`, `delivery`, `guarantees`, `findings`, `snapshot_id`, and source fields. Sort every collection by stable IDs.

- [ ] **Step 4: Verify and commit when authorized**

Run `python -m pytest tests/test_agent_deck_projection.py tests/test_control_panel_live_gui.py tests/test_orchestration_control_panel.py -q`. Then commit `agent_runtime/agent_deck_projection.py` and its test with message `feat: add agent deck read model`.
---

### Task 3: Add the fixed snapshot exporter and deterministic CLI boundary

**Files:**
- Modify: `agent_runtime/agent_deck_projection.py`
- Modify: `agent_runtime/cli.py`
- Create: `tests/test_agent_deck_cli.py`
- Modify: `tests/test_orchestration_boundary_contract.py`

**Interfaces:**
- Consumes: `build_agent_deck_snapshot` from Task 2.
- Produces: `export_agent_deck_snapshot(root: Path, *, evaluated_at: str, commit: bool) -> AgentDeckSnapshot`; CLI `python -m agent_runtime.cli agent-deck snapshot --evaluated-at <RFC3339> --json [--commit]`; fixed path `.runtime/agent-deck/v1/agent-deck.snapshot.json`.

- [ ] **Step 1: Write failing exporter and CLI tests**

Require preview to produce `export.would_write=true` and never create a file. Require explicit commit to write only the exact fixed relative path and return:

```python
{
    "path": ".runtime/agent-deck/v1/agent-deck.snapshot.json",
    "written": True,
    "atomic": True,
}
```

Test invalid RFC3339 values, `chain_limit` outside `1..20`, output larger than 131072 bytes, JSON serialization failure and replace failure. Each failure must preserve a prior output file and remove only its explicit sibling temporary file. Test that parser rejects `--output`, `--argv`, `--cwd`, `--env`, dispatch and host-control flags. Add a boundary contract assertion that this is a fixed safe projection writer, never an adapter executor or generic command entry.

- [ ] **Step 2: Run and confirm the red state**

Run `python -m pytest tests/test_agent_deck_cli.py tests/test_orchestration_boundary_contract.py -q`. Expected: fail because the exporter and `agent-deck` CLI parser do not exist.

- [ ] **Step 3: Implement atomic fixed-path export**

```python
SNAPSHOT_RELATIVE_PATH = Path(".runtime/agent-deck/v1/agent-deck.snapshot.json")
MAX_SNAPSHOT_BYTES = 131_072

def export_agent_deck_snapshot(root: Path, *, evaluated_at: str, commit: bool) -> AgentDeckSnapshot:
    """Preview or atomically export one fixed safe Agent Deck snapshot."""
    snapshot = build_agent_deck_snapshot(root, evaluated_at=evaluated_at)
    return _preview_or_write_fixed_snapshot(root, snapshot, commit=commit)
```

Implement private helper `_preview_or_write_fixed_snapshot(root: Path, snapshot: AgentDeckSnapshot, *, commit: bool) -> AgentDeckSnapshot` and private helper `_fixed_snapshot_path(root: Path) -> Path`. Serialize with `json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"`; UTF-8 encode; cap at `MAX_SNAPSHOT_BYTES`; resolve the fixed path and verify it remains under `root`. For commit, create the exact parent directory, write a sibling `.tmp`, close it, then call `Path.replace`. Add `export.would_write` only in preview, and `export.path/written/atomic` only after a successful commit.

Add a top-level `agent-deck` CLI group with only `snapshot`. Its only new flags are `--evaluated-at`, `--commit`, and `--json` plus the standard repository-root option. It prints stable JSON with `--json`; otherwise it prints compact Chinese status. It accepts no caller-controlled file path.

- [ ] **Step 4: Verify and commit when authorized**

Run:

```powershell
python -m pytest tests/test_agent_deck_projection.py tests/test_agent_deck_cli.py tests/test_orchestration_boundary_contract.py -q
python -m agent_runtime.cli agent-deck snapshot --evaluated-at 2026-07-29T09:00:00Z --json
python -m agent_runtime.cli agent-deck snapshot --evaluated-at 2026-07-29T09:00:00Z --json --commit
python -m agent_runtime.cli doctor
```

Expected: preview does not write; explicit commit writes the sole fixed safe file; all tests and doctor pass. Commit with `feat: export agent deck snapshot` after explicit authorization.

---

### Task 4: Bootstrap the reproducible Agent Deck React application

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/package-lock.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/tsconfig.json`
- Create: `frontend/tsconfig.app.json`
- Create: `frontend/tsconfig.node.json`
- Create: `frontend/components.json`
- Create: `frontend/index.html`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/index.css`
- Create: `frontend/src/lib/utils.ts`
- Create: `frontend/src/test/setup.ts`
- Create: `frontend/vitest.config.ts`
- Create: `frontend/src/App.tsx`
- Create: `frontend/src/App.test.tsx`

**Interfaces:**
- Consumes: the fixed runtime public directory from Task 3.
- Produces: a buildable local React app that fetches only `/agent-deck.snapshot.json` from `.runtime/agent-deck/v1` during foreground Vite development.

- [ ] **Step 1: Write the failing shell test**

```tsx
import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import App from "./App"

describe("Agent Deck application shell", () => {
  it("renders the Chinese primary navigation", () => {
    render(<App />)
    expect(screen.getByRole("navigation", { name: "主导航" })).toBeInTheDocument()
    expect(screen.getByText("新建任务")).toBeInTheDocument()
    expect(screen.getByText("Agent 团队")).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Confirm the red state**

From `frontend`, run `npm ci` and `npm run test`. Expected: fail because the Vite project and `App.tsx` do not exist.

- [ ] **Step 3: Create pinned Vite/Tailwind/shadcn configuration**

Use this exact package policy: React/React DOM `19.2.8`, TypeScript `7.0.2`, Vite `8.1.5`, `@vitejs/plugin-react` `6.0.4`, Tailwind and `@tailwindcss/vite` `4.3.3`, lucide-react `1.27.0`, Vitest `4.1.10`, Testing Library React `16.3.2`, jest-dom `7.0.0`, jsdom `30.0.1`, plus shadcn-required `@radix-ui/react-slot` `1.3.3`, class-variance-authority `0.7.1`, clsx `2.1.1`, tailwind-merge `3.6.0`, and sonner `2.0.7`. Use exact versions with no `^` or `~`, Node `>=24.11.1 <25`, and npm `>=11.12.1 <12`.

Use the official alias and Tailwind plugin setup:

```ts
import path from "node:path"
import tailwindcss from "@tailwindcss/vite"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vite"

export default defineConfig({
  plugins: [react(), tailwindcss()],
  publicDir: path.resolve(__dirname, "../.runtime/agent-deck/v1"),
  resolve: { alias: { "@": path.resolve(__dirname, "./src") } },
})
```

Use `@import "tailwindcss";` first in `src/index.css`, then define neutral dark/light variables, gold action accent, visible focus ring, Chinese-readable typography and reduced-motion behavior. Configure `components.json` as `new-york`, non-RSC, TSX, neutral base, CSS variables and `@/*` aliases. Run:

```powershell
npm install --ignore-scripts
npx shadcn@4.16.0 add avatar badge button card dialog scroll-area select sheet sonner switch tabs tooltip
npm install --package-lock-only --ignore-scripts
```

Commit every generated `frontend/src/components/ui/*` source file and `package-lock.json`.

- [ ] **Step 4: Implement and verify the minimal shell**

Create `main.tsx` with `StrictMode`, `App`, `index.css` and `<Toaster richColors position="top-right" />`; configure Vitest with jsdom and `@testing-library/jest-dom/vitest`. Implement only a labelled sidebar and a main region in `App.tsx`; it must not fetch data in this task. Run `npm ci`, `npm run test`, `npm run typecheck`, and `npm run build`. Commit with `feat: add agent deck frontend foundation` when explicitly authorized.

---

### Task 5: Implement the product workbench views against safe fixtures and live snapshots

**Files:**
- Create: `frontend/src/lib/agent-deck-types.ts`
- Create: `frontend/src/lib/load-agent-deck-snapshot.ts`
- Create: `frontend/src/lib/load-agent-deck-snapshot.test.ts`
- Create: `frontend/src/fixtures/agent-deck.fixture.json`
- Create: `frontend/src/components/app-sidebar.tsx`
- Create: `frontend/src/components/task-composer.tsx`
- Create: `frontend/src/components/agent-team.tsx`
- Create: `frontend/src/components/collaboration-timeline.tsx`
- Create: `frontend/src/components/delivery-panel.tsx`
- Create: `frontend/src/components/runtime-state.tsx`
- Create: `frontend/src/components/agent-team.test.tsx`
- Create: `frontend/src/components/task-composer.test.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/App.test.tsx`

**Interfaces:**
- Consumes: `agent-deck/read-model/v1` from Task 2/3, or a fixture marked `source_mode: "fixture"`.
- Produces: a responsive Chinese workbench that distinguishes fixture, live, unavailable and invalid state; it has no execution button or command bridge.

- [ ] **Step 1: Write failing core-path tests**

```tsx
it("shows Pi and OMP as live pilot members and pending adapters as pending", () => {
  render(<AgentTeam agents={fixture.agents} />)
  expect(screen.getByText("Pi")).toBeInTheDocument()
  expect(screen.getByText("OMP")).toBeInTheDocument()
  expect(screen.getAllByText("待接入")).toHaveLength(3)
  expect(screen.queryByText("立即执行")).not.toBeInTheDocument()
})

it("keeps natural-language task input as a non-executing draft in P0", async () => {
  const user = userEvent.setup()
  render(<TaskComposer />)
  await user.type(screen.getByLabelText("任务目标"), "审查当前项目的测试失败原因")
  await user.click(screen.getByRole("button", { name: "保存任务草稿" }))
  expect(screen.getByText("任务草稿已保存在当前浏览器会话中，尚未派发给 Agent。"))
    .toBeInTheDocument()
})
```

Loader tests must require `fetch("/agent-deck.snapshot.json", { cache: "no-store" })`; schema mismatch returns `invalid` with Chinese safe message; 404/network errors return `unavailable`; a committed fixture is never silently displayed as live data.

- [ ] **Step 2: Confirm the red state**

Run `npm run test`. Expected: fail because the model, loader and components do not exist.

- [ ] **Step 3: Implement types and honest runtime state**

```ts
export type RuntimeState =
  | { kind: "loading" }
  | { kind: "live"; snapshot: AgentDeckSnapshot }
  | { kind: "unavailable"; message: string }
  | { kind: "invalid"; message: string }

export async function loadAgentDeckSnapshot(): Promise<RuntimeState> {
  const response = await fetch("/agent-deck.snapshot.json", { cache: "no-store" })
  if (!response.ok) return { kind: "unavailable", message: "尚未生成 Agent Deck 安全快照。" }
  const value: unknown = await response.json()
  if (!isAgentDeckSnapshot(value)) return { kind: "invalid", message: "Agent Deck 快照格式无效，已拒绝展示。" }
  return { kind: "live", snapshot: value }
}
```

The fixture must contain only safe data and a visible `source_mode: "fixture"`/`演示数据` badge. A runtime snapshot must be called `实时快照` only when it carries `source_mode: "runtime"`, schema version and safe guarantees.

- [ ] **Step 4: Implement the workbench**

Implement:

- `AppSidebar`: project, task, team, collaboration, delivery, automation, plugin and setting navigation;
- `TaskComposer`: `任务目标` textarea, project chip, `协同模式（P0 仅试运行）`, Pi/OMP member chips, four quick-start cards and browser-session-only draft save;
- `AgentTeam`: cards showing role, real status/readiness summary, pending labels, and no affordance to execute a pending Agent;
- `CollaborationTimeline`: planning/execution/review safe event cards and a `过程与证据` disclosure;
- `DeliveryPanel`: safe artifact/review summaries and the explicit note that Pi/OMP final approval remains in the existing controlled GUI during P0;
- `RuntimeState`: loading, fixture, unavailable and invalid callouts.

Use shadcn `Card`, `Badge`, `Avatar`, `ScrollArea`, `Tabs`, `Tooltip`, `Sheet` and `Sonner`, plus lucide icons. Each color-coded status also needs text and an icon; all controls require visible focus.

- [ ] **Step 5: Verify and commit when authorized**

Run `npm run test`, `npm run typecheck`, and `npm run build`. Open the fixture build manually and confirm project navigation, task input, Pi/OMP cards, three pending Agent cards, timeline, delivery panel and the fixture label. Commit with `feat: render agent deck workbench` after explicit authorization.

---

### Task 6: Bind the foreground workbench to real Pi/OMP safe snapshots and validate the pilot

**Files:**
- Modify: `agent_runtime/agent_deck_projection.py`
- Modify: `tests/test_agent_deck_projection.py`
- Modify: `tests/test_agent_deck_cli.py`
- Modify: `frontend/src/lib/agent-deck-types.ts`
- Modify: `frontend/src/components/runtime-state.tsx`
- Modify: `frontend/src/components/agent-team.tsx`
- Modify: `frontend/src/components/collaboration-timeline.tsx`
- Modify: `docs/143-agent-deck-platform-mvp.md`
- Modify: `docs/000-stage-digest.md`
- Create: `docs/archive/144-stage94-agent-deck-pilot-acceptance.md` only after complete real acceptance.

**Interfaces:**
- Consumes: the Task 3 fixed exporter and Task 4 `publicDir`.
- Produces: a foreground-only Vite workbench that renders actual Pi/OMP safe state, safe registered cards and safe chain timeline records.

- [ ] **Step 1: Add failing live-binding tests**

Add a Python test that exports a valid monkeypatched runtime snapshot, re-reads the exact fixed file and verifies it contains only documented safe keys. Add React tests for `实时快照`, `状态已过期`, and `未连接`. A stale/unavailable Pi/OMP member must never be relabelled idle, ready or runnable.

- [ ] **Step 2: Confirm the red state**

Run `python -m pytest tests/test_agent_deck_projection.py tests/test_agent_deck_cli.py -q` and `npm run test`. Expected: only the new source-mode/stale-state expectations fail.

- [ ] **Step 3: Implement source-mode and direct status mapping**

The backend runtime document must contain:

```json
{
  "source_mode": "runtime",
  "source": {
    "control_panel_snapshot_id": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "evaluated_at": "2026-07-29T09:00:00Z"
  }
}
```

`source_mode: "fixture"` is permitted only in the committed frontend fixture. TypeScript must render Pi/OMP status labels exactly as supplied by the Python safe projection and must never recalculate readiness.

- [ ] **Step 4: Perform the real Pi/OMP pilot**

With Pi and OMP opened by the user and tools empty, run only:

```powershell
python -m agent_runtime.cli agent-deck snapshot --evaluated-at <current-RFC3339-UTC> --json --commit
Set-Location frontend
npm run dev -- --host 127.0.0.1
```

Verify the foreground browser shows real Pi/OMP state and registered work cards. Execute one already-registered Pi/OMP chain only through the existing GUI, not React. Re-export after observable transitions and verify the workbench projects the safe status, handoff, result and final state. Do not use React to dispatch, approve, cancel, restart or recover a host.

- [ ] **Step 5: Run complete verification**

```powershell
Set-Location ..
python -m pytest tests -q
python -m pytest tests/test_controlled_write_regression.py -q
python -m agent_runtime.cli doctor
python tools/public_scan.py
git diff --check
bash .githooks/pre-commit
Set-Location frontend
npm ci
npm run test
npm run typecheck
npm run build
```

Expected: all commands pass. If the foreground verification or any external publish action did not succeed, record it as pending and do not claim P0 acceptance.

- [ ] **Step 6: Record acceptance and commit when authorized**

Only after the real pilot passes, update stage/digest/index/roadmap and create `docs/archive/144-stage94-agent-deck-pilot-acceptance.md` with the actual tested chain ID, safe terminal result and validation summary. Commit with `feat: add agent deck Pi OMP pilot`. If the pilot is pending, commit only passing implementation and leave the stage document active with the exact pending condition.
