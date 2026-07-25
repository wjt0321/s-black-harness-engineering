// Stage 52 installable Pi extension: gate Pi's default tool calls
// (read/write/edit/bash) through the Harness preflight bridge before Pi
// executes anything.
//
// Install: copy this directory into `~/.pi/agent/extensions/pi-preflight-bridge/`
// and rename this file to `index.ts` (or reference it from settings.json), then
// set AGENT_RUNTIME_ROOT to the Harness repository root. Verified against the
// official ExtensionAPI (`@earendil-works/pi-coding-agent`):
//   - default export factory `function (pi: ExtensionAPI)`
//   - `pi.on("tool_call", handler)` with `event.toolName` / `event.toolCallId` /
//     `event.input`; returning `{ block: true, reason }` blocks execution
//   - built-in input fields (from pi source): bash {command}; read
//     {path, offset?, limit?}; write {path, content}; edit {path,
//     edits: [{oldText, newText}]} (legacy top-level oldText/newText is
//     normalized into edits by pi, and tolerated here as well)
//
// Decision mapping (fixed contract):
//   pass                                 -> allow (return undefined)
//   needs_approval / blocked / invalid   -> { block: true, reason }
//
// The type import below is erased at runtime; this extension has no runtime
// npm dependencies. Pure functions are exported for tests.

import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { createHash } from "node:crypto";
import { resolve } from "node:path";
import { runPreflightBridge, REQUEST_SCHEMA_VERSION } from "./preflight-bridge.ts";
import type { BridgeClientOptions, BridgeRequest, BridgeResponse } from "./preflight-bridge.ts";

// Structural subset of Pi's tool_call event, so handlers stay testable
// without the pi runtime.
export interface ToolCallEventLike {
  toolName: string;
  toolCallId: string;
  input: Record<string, unknown>;
}

export interface ToolResultEventLike {
  toolName: string;
  toolCallId: string;
  input: Record<string, unknown>;
  content: Array<Record<string, unknown>>;
  isError: boolean;
  details?: unknown;
}

export type ToolResultPatch = { content?: Array<Record<string, unknown>>; details?: unknown; isError?: boolean } | undefined;

export interface PiEditEntry {
  oldText: string;
  newText: string;
}

export type ToolCallGateResult = { block: true; reason: string } | undefined;

export interface ApprovalContextLike {
  hasUI: boolean;
  mode: string;
  cwd: string;
  confirm(title: string, message: string, options?: { timeout?: number }): Promise<boolean>;
}

// Only these explicit environment values enable host-side optional behavior.
export const INTERACTIVE_APPROVAL_MODE = "interactive";
export const POSTFLIGHT_PROJECTION_MODE = "summary";
const APPROVAL_ACTIONS = new Set(["require_user_approval", "require_secret_scan"]);
const POSTFLIGHT_TOOLS: readonly string[] = ["read", "write", "edit", "bash"];
const POSTFLIGHT_MARKER = "[Harness postflight projection]";

// Pi default tools gated by the Stage 52 bridge. Anything else is blocked
// fail-closed in this extension; relax only with an explicit design decision.
const GATED_TOOLS: readonly string[] = ["read", "write", "edit", "bash"];

const REQUEST_ID_MAX_CHARS = 128;

function asString(value: unknown): string | null {
  return typeof value === "string" && value.length > 0 ? value : null;
}

// Sanitize a Pi toolCallId into the bridge request_id alphabet
// ([A-Za-z0-9._:-], <= 128 chars). Returns undefined when nothing usable
// remains; the request_id is then simply omitted.
export function sanitizeRequestId(toolCallId: unknown): string | undefined {
  if (typeof toolCallId !== "string" || toolCallId.length === 0) return undefined;
  const cleaned = toolCallId.replace(/[^A-Za-z0-9._:-]/g, "-").replace(/^[^A-Za-z0-9]+/, "");
  if (cleaned.length === 0) return undefined;
  return cleaned.slice(0, REQUEST_ID_MAX_CHARS);
}

// Extract normalized edit entries from Pi's edit input. Current pi schema is
// { path, edits: [{ oldText, newText }] }; legacy top-level oldText/newText
// (accepted by older models and normalized by pi itself) is also tolerated.
// Returns null when no usable entry exists (fail closed).
export function extractEditEntries(input: Record<string, unknown>): PiEditEntry[] | null {
  const entries: PiEditEntry[] = [];
  if (Array.isArray(input.edits)) {
    for (const item of input.edits) {
      if (typeof item !== "object" || item === null) return null;
      const oldText = asString((item as Record<string, unknown>).oldText);
      const newText = asString((item as Record<string, unknown>).newText);
      if (oldText === null || newText === null) return null;
      entries.push({ oldText, newText });
    }
  }
  // Legacy single-edit shape: top-level oldText/newText.
  const legacyOld = asString(input.oldText);
  const legacyNew = asString(input.newText);
  if (legacyOld !== null && legacyNew !== null) {
    entries.push({ oldText: legacyOld, newText: legacyNew });
  }
  return entries.length > 0 ? entries : null;
}

// Normalize a Pi tool_call event into the bridge request minimal field set.
// Returns null when the tool is not gated or fields are unusable.
export function toBridgeRequest(event: ToolCallEventLike): BridgeRequest | null {
  const input = event.input ?? {};
  let request: BridgeRequest | null = null;

  if (event.toolName === "read") {
    // Pi read input is { path, offset?, limit? }; the bridge gates path only.
    const path = asString(input.path);
    if (path !== null) {
      request = { schema_version: REQUEST_SCHEMA_VERSION, tool: "read", input: { path } };
    }
  } else if (event.toolName === "write") {
    const path = asString(input.path);
    const content = asString(input.content);
    if (path !== null && content !== null) {
      request = { schema_version: REQUEST_SCHEMA_VERSION, tool: "write", input: { path, content } };
    }
  } else if (event.toolName === "edit") {
    const path = asString(input.path);
    const entries = extractEditEntries(input);
    if (path !== null && entries !== null) {
      request = {
        schema_version: REQUEST_SCHEMA_VERSION,
        tool: "edit",
        input: {
          path,
          edits: entries.map((entry) => ({
            old_string: entry.oldText,
            new_string: entry.newText,
          })),
        },
      };
    }
  } else if (event.toolName === "bash") {
    const command = asString(input.command);
    if (command !== null) {
      request = { schema_version: REQUEST_SCHEMA_VERSION, tool: "bash", input: { command } };
    }
  }

  if (request === null) return null;
  const requestId = sanitizeRequestId(event.toolCallId);
  if (requestId !== undefined) request.request_id = requestId;
  return request;
}

// Map a bridge response to a tool_call handler result. pass allows; every
// other decision blocks with a safe, value-free reason.
export function decisionToGateResult(response: BridgeResponse): ToolCallGateResult {
  if (response.decision === "pass") return undefined;
  return {
    block: true,
    reason: `Harness preflight ${response.decision}: ${response.next_action.message}`,
  };
}

function sameResolvedPath(left: string, right: string): boolean {
  const a = resolve(left);
  const b = resolve(right);
  return process.platform === "win32" ? a.toLowerCase() === b.toLowerCase() : a === b;
}

function deepFreeze(value: unknown): void {
  if (typeof value !== "object" || value === null || Object.isFrozen(value)) return;
  for (const child of Object.values(value)) deepFreeze(child);
  Object.freeze(value);
}

// Stage 53 v1 deliberately supports one approval candidate only. This keeps
// user approval bound to an exact, reviewable command while the wider approval
// ledger/roundtrip contract remains unimplemented.
export function isInteractiveApprovalCandidate(
  request: BridgeRequest,
  response: BridgeResponse,
  hostCwd: string,
  options: BridgeClientOptions,
): boolean {
  if (request.tool !== "bash" || request.input.command !== "git push origin main") return false;
  if (!sameResolvedPath(hostCwd, options.cwd)) return false;
  if (response.decision !== "needs_approval") return false;
  if (response.request_hash === null || response.target_hash === null) return false;
  if (response.findings.length === 0) return false;
  return response.findings.every((finding) => APPROVAL_ACTIONS.has(finding.action));
}

function sameApprovalIdentity(first: BridgeResponse, second: BridgeResponse): boolean {
  return (
    second.decision === "needs_approval" &&
    second.request_id === first.request_id &&
    second.request_hash === first.request_hash &&
    second.tool === first.tool &&
    second.target_hash === first.target_hash
  );
}

function sha256Text(value: string): string {
  return `sha256:${createHash("sha256").update(value, "utf8").digest("hex")}`;
}

function summarizeContentBlocks(content: Array<Record<string, unknown>>): Record<string, number> {
  let textBlocks = 0;
  let imageBlocks = 0;
  let otherBlocks = 0;
  let textChars = 0;
  for (const block of content) {
    if (block?.type === "text" && typeof block.text === "string") {
      textBlocks += 1;
      textChars += block.text.length;
    } else if (block?.type === "image") {
      imageBlocks += 1;
    } else {
      otherBlocks += 1;
    }
  }
  return { blocks: content.length, text_blocks: textBlocks, image_blocks: imageBlocks, other_blocks: otherBlocks, text_chars: textChars };
}

function postflightSummaryText(response: BridgeResponse, event: ToolResultEventLike): string {
  const counts = summarizeContentBlocks(event.content ?? []);
  const idHash = sha256Text(String(event.toolCallId || ""));
  return [
    POSTFLIGHT_MARKER,
    `tool=${response.tool ?? event.toolName}`,
    `decision=${response.decision}`,
    `is_error=${event.isError ? "true" : "false"}`,
    `request_id=${response.request_id ?? "none"}`,
    `request_hash=${response.request_hash ?? "none"}`,
    `target_hash=${response.target_hash ?? "none"}`,
    `tool_call_id_hash=${idHash}`,
    `content_blocks=${counts.blocks}`,
    `text_blocks=${counts.text_blocks}`,
    `image_blocks=${counts.image_blocks}`,
    `other_blocks=${counts.other_blocks}`,
    `text_chars=${counts.text_chars}`,
    "writes_ledgers=false",
    "executes_tools=false",
  ].join("\n");
}

export function createPostflightProjectionHandler(
  options: BridgeClientOptions,
  postflightMode: string | undefined,
): (event: ToolResultEventLike) => Promise<ToolResultPatch> {
  return async (event: ToolResultEventLike): Promise<ToolResultPatch> => {
    if (postflightMode !== POSTFLIGHT_PROJECTION_MODE) return undefined;
    if (!POSTFLIGHT_TOOLS.includes(event.toolName)) return undefined;
    const request = toBridgeRequest(event);
    if (request === null) return undefined;
    const response = await runPreflightBridge(request, options);
    const summary = postflightSummaryText(response, event);
    return { content: [...(event.content ?? []), { type: "text", text: summary }] };
  };
}

export function createApprovalToolCallHandler(
  options: BridgeClientOptions,
  approvalMode: string | undefined,
  context: ApprovalContextLike,
): (event: ToolCallEventLike) => Promise<ToolCallGateResult> {
  const baseHandler = createToolCallHandler(options);
  return async (event: ToolCallEventLike): Promise<ToolCallGateResult> => {
    try {
      const request = toBridgeRequest(event);
      if (request === null) return baseHandler(event);

      const first = await runPreflightBridge(request, options);
      if (first.decision === "pass") return undefined;
      if (
        approvalMode !== INTERACTIVE_APPROVAL_MODE ||
        !context.hasUI ||
        (context.mode !== "tui" && context.mode !== "rpc") ||
        !isInteractiveApprovalCandidate(request, first, context.cwd, options)
      ) {
        return decisionToGateResult(first);
      }

      const approved = await context.confirm(
        "Harness approval required",
        "Allow one execution of git push origin main in the current project? This approval cannot be reused.",
      );
      if (!approved) {
        return { block: true, reason: "Harness approval was denied or dismissed." };
      }

      const currentRequest = toBridgeRequest(event);
      if (currentRequest === null) {
        return { block: true, reason: "Harness approval input became invalid during confirmation; failing closed." };
      }
      const second = await runPreflightBridge(currentRequest, options);
      if (!sameApprovalIdentity(first, second)) {
        return { block: true, reason: "Harness approval identity changed during confirmation; failing closed." };
      }
      deepFreeze(event.input);
      return undefined;
    } catch {
      return { block: true, reason: "Harness approval interaction failed; failing closed." };
    }
  };
}

// Create the tool_call handler bound to fixed bridge options. Never throws;
// every failure blocks.
export function createToolCallHandler(
  options: BridgeClientOptions,
): (event: ToolCallEventLike) => Promise<ToolCallGateResult> {
  return async (event: ToolCallEventLike): Promise<ToolCallGateResult> => {
    if (!GATED_TOOLS.includes(event.toolName)) {
      return {
        block: true,
        reason: `tool '${event.toolName}' is outside the Stage 52 gated default set (read/write/edit/bash)`,
      };
    }
    const request = toBridgeRequest(event);
    if (request === null) {
      return {
        block: true,
        reason: "tool call could not be normalized into a preflight request",
      };
    }
    const response = await runPreflightBridge(request, options);
    return decisionToGateResult(response);
  };
}

// Resolve bridge options from the extension environment. AGENT_RUNTIME_ROOT
// must point at the Harness repository root (policies + adapter registry);
// without it the extension fails closed. AGENT_RUNTIME_PYTHON optionally
// overrides the python launcher; the argv after it stays fixed.
export function resolveBridgeOptions(
  env: Record<string, string | undefined>,
): BridgeClientOptions | null {
  const root = env.AGENT_RUNTIME_ROOT;
  if (typeof root !== "string" || root.length === 0) return null;
  const options: BridgeClientOptions = { cwd: root };
  const python = env.AGENT_RUNTIME_PYTHON;
  if (typeof python === "string" && python.length > 0) options.pythonCommand = python;
  return options;
}

export default function (pi: ExtensionAPI) {
  const options = resolveBridgeOptions(process.env);
  const approvalMode = process.env.AGENT_RUNTIME_APPROVAL_MODE;
  const postflightMode = process.env.AGENT_RUNTIME_POSTFLIGHT_MODE;
  pi.on("tool_call", async (event, ctx) => {
    if (options === null) {
      return {
        block: true,
        reason:
          "Harness preflight bridge is not configured (AGENT_RUNTIME_ROOT missing); failing closed",
      };
    }
    return createApprovalToolCallHandler(options, approvalMode, {
      hasUI: ctx.hasUI,
      mode: ctx.mode,
      cwd: ctx.cwd,
      confirm: (title, message, dialogOptions) =>
        ctx.ui.confirm(title, message, { ...dialogOptions, timeout: 60_000 }),
    })(event as ToolCallEventLike);
  });

  pi.on("tool_result", async (event) => {
    if (options === null) return undefined;
    return createPostflightProjectionHandler(options, postflightMode)(event as ToolResultEventLike);
  });
}
