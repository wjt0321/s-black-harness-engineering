// Stage 52 Pi host preflight bridge client (Node stdlib only, no npm deps).
//
// Spawns the fixed Harness CLI `python -m agent_runtime.cli pi-bridge preflight`
// as a one-shot stdio subprocess: one bounded JSON request on stdin, one
// deterministic JSON response on stdout. shell=false, bounded timeout, bounded
// stdout/stderr, minimal environment allowlist, no retries, no secret reads.
//
// This file uses erasable TypeScript syntax only, so Node >= 22.18 can run it
// directly (type stripping) without a build step.

import { spawn } from "node:child_process";

export type BridgeDecision = "pass" | "needs_approval" | "blocked" | "invalid";

export const REQUEST_SCHEMA_VERSION = "pi-bridge/preflight-request/v1";
export const RESPONSE_SCHEMA_VERSION = "pi-bridge/preflight-response/v1";

// Tool-specific minimal input fields, mirroring the bridge request schema.
export interface ReadInput {
  path: string;
}

export interface WriteInput {
  path: string;
  content: string;
}

export interface EditEntry {
  old_string: string;
  new_string: string;
}

export interface EditInput {
  path: string;
  edits: EditEntry[];
}

export interface BashInput {
  command: string;
}

export type BridgeRequestInput = ReadInput | WriteInput | EditInput | BashInput;

interface BridgeRequestBase {
  schema_version: typeof REQUEST_SCHEMA_VERSION;
  request_id?: string;
}

// Discriminated request union: the input shape is fixed by `tool`.
export type BridgeRequest =
  | (BridgeRequestBase & { tool: "read"; input: ReadInput })
  | (BridgeRequestBase & { tool: "write"; input: WriteInput })
  | (BridgeRequestBase & { tool: "edit"; input: EditInput })
  | (BridgeRequestBase & { tool: "bash"; input: BashInput });

export interface BridgeFinding {
  rule_id: string;
  severity: string;
  action: string;
  message: string;
}

export interface BridgeResponse {
  schema_version: string;
  bridge: string;
  decision: BridgeDecision;
  request_id: string | null;
  request_hash: string | null;
  tool: string | null;
  target_hash: string | null;
  checks: Array<{ id: string; status: string }>;
  findings: BridgeFinding[];
  next_action: { code: string; message: string };
  guarantees: Record<string, boolean>;
}

export interface BridgeClientOptions {
  // Project root that the Harness CLI uses as --root (its cwd). Required.
  cwd: string;
  // Python launcher. The argv after it is fixed; shell is never used.
  pythonCommand?: string;
  // Bounded one-shot timeout. Clamped to [1000, 30000] ms. Default 10000.
  timeoutMs?: number;
}

const BRIDGE_ARGV: readonly string[] = ["-m", "agent_runtime.cli", "pi-bridge", "preflight"];
const DEFAULT_TIMEOUT_MS = 10_000;
const MIN_TIMEOUT_MS = 1_000;
const MAX_TIMEOUT_MS = 30_000;
const MAX_STDOUT_BYTES = 64 * 1024;
const MAX_STDERR_BYTES = 16 * 1024;
const DECISIONS: readonly string[] = ["pass", "needs_approval", "blocked", "invalid"];
const SAFE_GUARANTEES: Record<string, boolean> = {
  executes_tools: false,
  writes_files: false,
  writes_ledgers: false,
  accesses_network: false,
  reads_target_files: false,
  echoes_input_values: false,
};

// Minimal environment for the child process. Secret-bearing variables are
// never forwarded; the Python bridge itself never reads credentials.
// APPDATA/USERPROFILE/HOME are required so the Python launcher can locate
// per-user site-packages (where runtime deps such as jsonschema may live).
const CHILD_ENV_KEYS: readonly string[] = [
  "PATH",
  "Path",
  "SYSTEMROOT",
  "SystemRoot",
  "WINDIR",
  "PATHEXT",
  "TEMP",
  "TMP",
  "APPDATA",
  "LOCALAPPDATA",
  "USERPROFILE",
  "HOMEDRIVE",
  "HOMEPATH",
  "HOME",
];

function clampTimeout(timeoutMs: number | undefined): number {
  if (timeoutMs === undefined || Number.isNaN(timeoutMs)) return DEFAULT_TIMEOUT_MS;
  return Math.min(Math.max(Math.trunc(timeoutMs), MIN_TIMEOUT_MS), MAX_TIMEOUT_MS);
}

function childEnv(): Record<string, string> {
  const env: Record<string, string> = {};
  for (const key of CHILD_ENV_KEYS) {
    const value = process.env[key];
    if (typeof value === "string") env[key] = value;
  }
  return env;
}

// Synthetic fail-closed response for local transport failures (spawn error,
// timeout, overflow, malformed output). Marked with a local fallback identity
// so it can never be confused with a real bridge response.
function localBlockedResponse(reason: string): BridgeResponse {
  return {
    schema_version: RESPONSE_SCHEMA_VERSION,
    bridge: "pi-extension-local-fallback/v1",
    decision: "blocked",
    request_id: null,
    request_hash: null,
    tool: null,
    target_hash: null,
    checks: [{ id: "bridge_transport", status: "error" }],
    findings: [
      {
        rule_id: "pi-extension-bridge-unavailable",
        severity: "error",
        action: "error",
        message: reason,
      },
    ],
    next_action: {
      code: "do_not_execute",
      message: "The preflight bridge did not return a usable decision; failing closed.",
    },
    guarantees: { ...SAFE_GUARANTEES },
  };
}

function parseBridgeResponse(text: string): BridgeResponse | null {
  let value: unknown;
  try {
    value = JSON.parse(text);
  } catch {
    return null;
  }
  if (typeof value !== "object" || value === null) return null;
  const candidate = value as Record<string, unknown>;
  if (typeof candidate.decision !== "string" || !DECISIONS.includes(candidate.decision)) {
    return null;
  }
  if (candidate.schema_version !== RESPONSE_SCHEMA_VERSION) return null;
  return value as BridgeResponse;
}

// Run exactly one preflight round trip. Never throws; any transport failure
// resolves to a fail-closed local blocked response. Never retries.
export function runPreflightBridge(
  request: BridgeRequest,
  options: BridgeClientOptions,
): Promise<BridgeResponse> {
  return new Promise((resolve) => {
    let settled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const finish = (response: BridgeResponse): void => {
      if (settled) return;
      settled = true;
      if (timer !== undefined) clearTimeout(timer);
      resolve(response);
    };

    let child;
    try {
      child = spawn(options.pythonCommand ?? "python", [...BRIDGE_ARGV], {
        cwd: options.cwd,
        env: childEnv(),
        shell: false,
        stdio: ["pipe", "pipe", "pipe"],
        windowsHide: true,
      });
    } catch {
      finish(localBlockedResponse("The bridge process could not be started."));
      return;
    }

    timer = setTimeout(() => {
      try {
        child.kill("SIGKILL");
      } catch {
        // best effort only
      }
      finish(localBlockedResponse("The bridge did not answer within the bounded timeout."));
    }, clampTimeout(options.timeoutMs));

    let stdoutBytes = 0;
    let stderrBytes = 0;
    const stdoutChunks: Buffer[] = [];

    child.stdout.on("data", (chunk: Buffer) => {
      stdoutBytes += chunk.length;
      if (stdoutBytes > MAX_STDOUT_BYTES) {
        try {
          child.kill("SIGKILL");
        } catch {
          // best effort only
        }
        finish(localBlockedResponse("The bridge stdout exceeded the 64 KiB bound."));
        return;
      }
      stdoutChunks.push(chunk);
    });

    child.stderr.on("data", (chunk: Buffer) => {
      stderrBytes += chunk.length;
      if (stderrBytes > MAX_STDERR_BYTES) {
        try {
          child.kill("SIGKILL");
        } catch {
          // best effort only
        }
        finish(localBlockedResponse("The bridge stderr exceeded the 16 KiB bound."));
      }
    });

    child.on("error", () => {
      finish(localBlockedResponse("The bridge process failed to spawn."));
    });

    child.on("close", () => {
      if (settled) return;
      const parsed = parseBridgeResponse(Buffer.concat(stdoutChunks).toString("utf-8"));
      if (parsed === null) {
        finish(localBlockedResponse("The bridge returned an unreadable decision."));
        return;
      }
      finish(parsed);
    });

    child.stdin.on("error", () => {
      // EPIPE when the child exits early; the close/error handlers decide.
    });
    child.stdin.end(JSON.stringify(request), "utf-8");
  });
}
