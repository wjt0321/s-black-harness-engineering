// Behavior tests for the Stage 52 preflight bridge client and Pi extension.
// Run from the repository root:
//   node --test integrations/pi/test/preflight-bridge.test.ts
// Requires Node >= 22.18 (type stripping) and `python` on PATH.

import { test } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import { runPreflightBridge } from "../preflight-bridge.ts";
import {
  createToolCallHandler,
  decisionToGateResult,
  extractEditEntries,
  resolveBridgeOptions,
  sanitizeRequestId,
  toBridgeRequest,
} from "../extension.ts";

const repoRoot = fileURLToPath(new URL("../../..", import.meta.url));
const options = { cwd: repoRoot, timeoutMs: 20_000 };

function readEvent(target: string) {
  return { toolName: "read", toolCallId: "call-1", input: { path: target } };
}

test("pass decision for a plain read", async () => {
  const response = await runPreflightBridge(
    {
      schema_version: "pi-bridge/preflight-request/v1",
      tool: "read",
      input: { path: "docs/00-index.md" },
    },
    options,
  );
  assert.equal(response.decision, "pass");
  assert.equal(response.tool, "read");
  assert.match(response.request_hash ?? "", /^sha256:[0-9a-f]{64}$/);
  assert.match(response.target_hash ?? "", /^sha256:[0-9a-f]{64}$/);
  assert.equal(response.next_action.code, "proceed");
});

test("blocked decision for a credential target, without echoing it", async () => {
  const response = await runPreflightBridge(
    {
      schema_version: "pi-bridge/preflight-request/v1",
      tool: "read",
      input: { path: ".env" },
    },
    options,
  );
  assert.equal(response.decision, "blocked");
  assert.ok(!JSON.stringify(response).includes(".env"));
});

test("needs_approval decision for git push, without echoing the command", async () => {
  const response = await runPreflightBridge(
    {
      schema_version: "pi-bridge/preflight-request/v1",
      tool: "bash",
      input: { command: "git push origin main" },
    },
    options,
  );
  assert.equal(response.decision, "needs_approval");
  assert.equal(response.next_action.code, "request_user_approval");
  // The full command line is never echoed; policy finding messages are static
  // operator-owned text (they may mention rule names such as "git push").
  assert.ok(!JSON.stringify(response).includes("git push origin main"));
});

test("deterministic responses for identical requests", async () => {
  const make = () =>
    runPreflightBridge(
      {
        schema_version: "pi-bridge/preflight-request/v1",
        tool: "read",
        input: { path: "docs/00-index.md" },
      },
      options,
    );
  assert.deepEqual(await make(), await make());
});

test("unknown python command fails closed", async () => {
  const response = await runPreflightBridge(
    {
      schema_version: "pi-bridge/preflight-request/v1",
      tool: "read",
      input: { path: "docs/00-index.md" },
    },
    { cwd: repoRoot, pythonCommand: "definitely-not-a-real-python-launcher", timeoutMs: 5_000 },
  );
  assert.equal(response.decision, "blocked");
  assert.equal(response.bridge, "pi-extension-local-fallback/v1");
  assert.equal(response.guarantees.executes_tools, false);
  assert.equal(response.guarantees.accesses_network, false);
  assert.equal(response.guarantees.writes_ledgers, false);
});

test("toBridgeRequest maps the four default tools with official field names", () => {
  // read: { path, offset?, limit? } — offset/limit are dropped by design.
  assert.deepEqual(toBridgeRequest({ toolName: "read", toolCallId: "c1", input: { path: "a.md", offset: 10, limit: 5 } })?.input, {
    path: "a.md",
  });
  // write: { path, content }
  assert.deepEqual(
    toBridgeRequest({ toolName: "write", toolCallId: "c2", input: { path: "a.md", content: "x" } })?.input,
    { path: "a.md", content: "x" },
  );
  // bash: { command, timeout? } — timeout is dropped by design.
  assert.deepEqual(
    toBridgeRequest({ toolName: "bash", toolCallId: "c3", input: { command: "ls", timeout: 30 } })?.input,
    { command: "ls" },
  );
  // edit (current pi schema): { path, edits: [{ oldText, newText }] }
  assert.deepEqual(
    toBridgeRequest({
      toolName: "edit",
      toolCallId: "c4",
      input: { path: "a.md", edits: [{ oldText: "x", newText: "y" }] },
    })?.input,
    { path: "a.md", edits: [{ old_string: "x", new_string: "y" }] },
  );
  assert.equal(toBridgeRequest({ toolName: "read", toolCallId: "c5", input: { path: 42 } }), null);
  assert.equal(toBridgeRequest({ toolName: "unknown-tool", toolCallId: "c6", input: {} }), null);
});

test("extractEditEntries handles current and legacy edit shapes", () => {
  assert.deepEqual(extractEditEntries({ path: "a", edits: [{ oldText: "x", newText: "y" }] }), [
    { oldText: "x", newText: "y" },
  ]);
  // Legacy top-level oldText/newText (older models; pi normalizes these too).
  assert.deepEqual(extractEditEntries({ path: "a", oldText: "x", newText: "y" }), [
    { oldText: "x", newText: "y" },
  ]);
  // Multiple entries are preserved in order.
  assert.deepEqual(
    extractEditEntries({ path: "a", edits: [{ oldText: "x", newText: "y" }, { oldText: "p", newText: "q" }] }),
    [
      { oldText: "x", newText: "y" },
      { oldText: "p", newText: "q" },
    ],
  );
  assert.equal(extractEditEntries({ path: "a" }), null);
  assert.equal(extractEditEntries({ path: "a", edits: [] }), null);
  assert.equal(extractEditEntries({ path: "a", edits: [{ oldText: "x" }] }), null);
});

test("sanitizeRequestId keeps toolCallId within the bridge alphabet", () => {
  assert.equal(sanitizeRequestId("call_abc-123:xyz.9"), "call_abc-123:xyz.9");
  assert.equal(sanitizeRequestId("call abc$def"), "call-abc-def");
  assert.equal(sanitizeRequestId("###"), undefined);
  assert.equal(sanitizeRequestId(42), undefined);
  assert.equal(sanitizeRequestId("a".repeat(200))?.length, 128);
});

test("request_id comes from the toolCallId", () => {
  const request = toBridgeRequest(readEvent("docs/00-index.md"));
  assert.equal(request?.request_id, "call-1");
});

test("decisionToGateResult allows pass and blocks everything else", () => {
  const base = { next_action: { code: "proceed", message: "ok" } };
  assert.equal(decisionToGateResult({ ...base, decision: "pass" }), undefined);
  for (const decision of ["needs_approval", "blocked", "invalid"]) {
    const result = decisionToGateResult({ ...base, decision });
    assert.equal(result?.block, true);
    assert.match(result?.reason ?? "", new RegExp(decision));
  }
});

test("tool_call handler allows pass and blocks needs_approval via the real bridge", async () => {
  const handler = createToolCallHandler(options);
  assert.equal(await handler(readEvent("docs/00-index.md")), undefined);
  const pushed = await handler({ toolName: "bash", toolCallId: "c9", input: { command: "git push origin main" } });
  assert.equal(pushed?.block, true);
  const outside = await handler({ toolName: "web_search", toolCallId: "c10", input: { query: "x" } });
  assert.equal(outside?.block, true);
  const malformed = await handler({ toolName: "read", toolCallId: "c11", input: {} });
  assert.equal(malformed?.block, true);
});

test("resolveBridgeOptions requires AGENT_RUNTIME_ROOT", () => {
  assert.equal(resolveBridgeOptions({}), null);
  assert.equal(resolveBridgeOptions({ AGENT_RUNTIME_ROOT: "" }), null);
  assert.deepEqual(resolveBridgeOptions({ AGENT_RUNTIME_ROOT: "/repo" }), { cwd: "/repo" });
  assert.deepEqual(
    resolveBridgeOptions({ AGENT_RUNTIME_ROOT: "/repo", AGENT_RUNTIME_PYTHON: "python3" }),
    { cwd: "/repo", pythonCommand: "python3" },
  );
});
