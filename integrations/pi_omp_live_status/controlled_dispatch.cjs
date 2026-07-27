"use strict";

const crypto = require("node:crypto");
const fs = require("node:fs");
const path = require("node:path");

const MAX_REQUEST_BYTES = 65536;
const MAX_RESULT_BYTES = 32768;
const PROFILE_PATHS = Object.freeze({
  "pi-local": {
    request: ".runtime/external-agent-dispatch/pi-local.request.v1.json",
    result: ".runtime/external-agent-dispatch/pi-local.result.v1.json",
  },
  "omp-local": {
    request: ".runtime/external-agent-dispatch/omp-local.request.v1.json",
    result: ".runtime/external-agent-dispatch/omp-local.result.v1.json",
  },
});

function canonicalJson(value) {
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(",")}]`;
  if (value && typeof value === "object") {
    return `{${Object.keys(value).sort().map(key => `${JSON.stringify(key)}:${canonicalJson(value[key])}`).join(",")}}`;
  }
  return JSON.stringify(value);
}

function sha256Bytes(value) {
  return "sha256:" + crypto.createHash("sha256").update(value).digest("hex");
}

function implementationDigest(extensionFile) {
  const hash = crypto.createHash("sha256");
  hash.update(fs.readFileSync(__filename));
  hash.update(Buffer.from([0]));
  hash.update(fs.readFileSync(extensionFile));
  return "sha256:" + hash.digest("hex");
}

function containedPath(root, relativePath) {
  const base = path.resolve(root);
  const target = path.resolve(base, relativePath);
  const prefix = base.endsWith(path.sep) ? base : base + path.sep;
  if (!target.startsWith(prefix)) throw new Error("path containment failed");
  return target;
}

function assertRealParentContainment(root, filePath) {
  const realRoot = fs.realpathSync(path.resolve(root));
  const realParent = fs.realpathSync(path.dirname(filePath));
  const prefix = realRoot.endsWith(path.sep) ? realRoot : realRoot + path.sep;
  if (realParent !== realRoot && !realParent.startsWith(prefix)) throw new Error("real parent containment failed");
}

function assertRegular(filePath, maxBytes) {
  const info = fs.lstatSync(filePath);
  if (!info.isFile() || info.isSymbolicLink() || info.nlink !== 1 || info.size > maxBytes) {
    throw new Error("unsafe bounded file");
  }
  return info;
}

function parseJsonFile(filePath, maxBytes) {
  const before = assertRegular(filePath, maxBytes);
  const data = fs.readFileSync(filePath);
  if (data.length > maxBytes) throw new Error("file too large");
  const after = assertRegular(filePath, maxBytes);
  if (before.dev !== after.dev || before.ino !== after.ino || before.size !== after.size || before.mtimeMs !== after.mtimeMs) {
    throw new Error("file identity drift");
  }
  const value = JSON.parse(data.toString("utf8"));
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("invalid object");
  return value;
}

function validateBinding(binding, profileId, expectedDigest) {
  const fixed = PROFILE_PATHS[profileId];
  if (!fixed) throw new Error("unsupported profile");
  if (binding.version !== 1 || binding.contract !== "external-agent-dispatch-binding/v1") throw new Error("binding version drift");
  if (binding.review_status !== "reviewed_for_single_work_item_dispatch") throw new Error("binding review drift");
  if (binding.target_profile !== profileId) throw new Error("binding profile drift");
  if (binding.request_relative_path !== fixed.request || binding.result_relative_path !== fixed.result) throw new Error("binding path drift");
  if (binding.implementation_binding_id !== expectedDigest) throw new Error("binding implementation drift");
  if (binding.protocol !== "external-agent-single-work-item-mailbox/v1") throw new Error("binding protocol drift");
  if (binding.max_request_bytes !== MAX_REQUEST_BYTES || binding.max_result_bytes !== MAX_RESULT_BYTES) throw new Error("binding bounds drift");
  if (!Number.isInteger(binding.request_ttl_seconds) || binding.request_ttl_seconds < 5 || binding.request_ttl_seconds > 120) throw new Error("binding ttl drift");
  if (!Number.isInteger(binding.poll_interval_ms) || binding.poll_interval_ms < 20 || binding.poll_interval_ms > 1000) throw new Error("binding poll drift");
  if (!Array.isArray(binding.required_active_tools) || binding.required_active_tools.length !== 0) throw new Error("binding tools drift");
  if (binding.allowed_host_action !== "sendUserMessage" || binding.dispatch_authorized !== true) throw new Error("binding authority drift");
  const forbidden = new Set(binding.forbidden_capabilities || []);
  for (const name of ["exec", "setActiveTools", "startProcess", "network", "automaticRetry", "parallelDispatch"]) {
    if (!forbidden.has(name)) throw new Error("binding forbidden capability drift");
  }
}

function loadBinding(root, relativePath, profileId, extensionFile) {
  const bindingPath = containedPath(root, relativePath);
  assertRealParentContainment(root, bindingPath);
  const binding = parseJsonFile(bindingPath, MAX_REQUEST_BYTES);
  validateBinding(binding, profileId, implementationDigest(extensionFile));
  return binding;
}

function safeRemove(filePath) {
  try {
    const info = assertRegular(filePath, MAX_REQUEST_BYTES);
    if (info) fs.unlinkSync(filePath);
  } catch (error) {
    if (error && error.code === "ENOENT") return;
  }
}

function atomicWrite(filePath, value, maxBytes) {
  const encoded = Buffer.from(canonicalJson(value) + "\n", "utf8");
  if (encoded.length > maxBytes) throw new Error("result too large");
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  const temporary = filePath + ".tmp";
  safeRemove(temporary);
  const descriptor = fs.openSync(temporary, "wx", 0o600);
  try {
    fs.writeFileSync(descriptor, encoded);
    fs.fsyncSync(descriptor);
  } finally {
    fs.closeSync(descriptor);
  }
  assertRegular(temporary, maxBytes);
  fs.renameSync(temporary, filePath);
  assertRegular(filePath, maxBytes);
}

function safeToken(value) {
  return typeof value === "string" && /^[A-Za-z0-9][A-Za-z0-9._:-]{0,95}$/.test(value);
}

function safeHash(value) {
  return typeof value === "string" && /^sha256:[a-f0-9]{64}$/.test(value);
}

function validateRequest(request, binding, profileId) {
  if (request.version !== 1 || request.contract !== binding.protocol) return "request-contract-invalid";
  if (!safeToken(request.request_id) || !safeToken(request.task_id) || !safeToken(request.work_item_id)) return "request-identity-invalid";
  if (request.target_profile !== profileId) return "request-profile-mismatch";
  if (!safeHash(request.approval_binding_id) || !safeHash(request.plan_hash) || !safeHash(request.instruction_digest)) return "request-binding-invalid";
  if (typeof request.instruction !== "string" || request.instruction.length < 1 || Buffer.byteLength(request.instruction, "utf8") > 4096 || request.instruction.includes("\0")) return "instruction-invalid";
  if (sha256Bytes(Buffer.from(request.instruction, "utf8")) !== request.instruction_digest) return "instruction-digest-mismatch";
  if (!Array.isArray(request.input_artifacts) || request.input_artifacts.length > 8) return "input-artifacts-invalid";
  if (!Number.isInteger(request.timeout_seconds) || request.timeout_seconds < 5 || request.timeout_seconds > 900) return "timeout-invalid";
  if (!Number.isInteger(request.result_max_bytes) || request.result_max_bytes < 256 || request.result_max_bytes > binding.max_result_bytes) return "result-bound-invalid";
  const issued = Date.parse(request.issued_at);
  const now = Date.now();
  if (!Number.isFinite(issued) || issued > now + 5000 || now - issued > binding.request_ttl_seconds * 1000) return "request-expired";
  return null;
}

function textFromMessage(message) {
  if (!message || message.role !== "assistant") return "";
  if (typeof message.content === "string") return message.content;
  if (!Array.isArray(message.content)) return "";
  return message.content
    .filter(item => item && item.type === "text" && typeof item.text === "string")
    .map(item => item.text)
    .join("\n");
}

function assistantOutput(messages) {
  if (!Array.isArray(messages)) return "";
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const text = textFromMessage(messages[index]);
    if (text.trim()) return text;
  }
  return "";
}

function createControlledDispatchExtension(pi, options) {
  const profileId = options.profileId;
  if (!PROFILE_PATHS[profileId]) throw new Error("unsupported profile");
  let state = null;

  function appendEvent(active, eventType, failureCode = null) {
    if (!active || !Array.isArray(active.events) || active.events.length >= 8) return;
    const event = {
      sequence: active.events.length + 1,
      event_type: eventType,
      occurred_at: new Date().toISOString(),
    };
    if (failureCode) event.failure_code = failureCode;
    active.events.push(event);
  }

  function appendTerminalEvent(active, status, failureCode) {
    const last = active?.events?.[active.events.length - 1]?.event_type;
    if (status === "blocked" && last !== "host_turn_blocked") appendEvent(active, "host_turn_blocked", failureCode);
    if (status === "timed_out" && last !== "host_turn_timed_out") appendEvent(active, "host_turn_timed_out", failureCode);
    if ((status === "failed" || status === "cancelled") && last !== "host_session_closed") {
      appendEvent(active, "host_session_closed", failureCode);
    }
  }

  function stop() {
    if (!state) return;
    if (state.pollTimer) clearInterval(state.pollTimer);
    if (state.timeoutTimer) clearTimeout(state.timeoutTimer);
    state.pollTimer = null;
    state.timeoutTimer = null;
  }

  function finish(status, failureCode, output) {
    if (!state || !state.active) return;
    const active = state.active;
    if (active.finished) return;
    active.finished = true;
    appendTerminalEvent(active, status, failureCode);
    if (state.timeoutTimer) clearTimeout(state.timeoutTimer);
    state.timeoutTimer = null;
    const result = {
      version: 2,
      contract: "external-agent-single-work-item-result/v2",
      request_id: active.request.request_id,
      target_profile: profileId,
      status,
      completed_at: new Date().toISOString(),
      events: Array.isArray(active.events) ? active.events.slice() : [],
      artifacts: [],
    };
    if (failureCode) result.failure_code = failureCode;
    if (status === "succeeded") {
      const bytes = Buffer.byteLength(output, "utf8");
      if (!output.trim()) {
        result.status = "failed";
        result.failure_code = "result-empty";
      } else if (bytes > active.request.result_max_bytes) {
        result.status = "failed";
        result.failure_code = "result-too-large";
      } else {
        result.output = output;
        result.output_bytes = bytes;
        result.output_digest = sha256Bytes(Buffer.from(output, "utf8"));
      }
    }
    try {
      atomicWrite(state.resultPath, result, state.binding.max_result_bytes + 4096);
    } finally {
      safeRemove(active.processingPath);
      state.active = null;
    }
  }

  function rejectRequest(request, processingPath, failureCode) {
    state.active = { request, processingPath, finished: false, events: [] };
    appendEvent(state.active, "request_claimed");
    finish("blocked", failureCode, "");
  }

  function poll() {
    if (!state || state.active || !fs.existsSync(state.requestPath)) return;
    const processingPath = state.requestPath + ".processing";
    try {
      safeRemove(processingPath);
      fs.renameSync(state.requestPath, processingPath);
      assertRealParentContainment(state.root, processingPath);
      const request = parseJsonFile(processingPath, state.binding.max_request_bytes);
      const failure = validateRequest(request, state.binding, profileId);
      if (failure) {
        rejectRequest(request, processingPath, failure);
        return;
      }
      const activeTools = typeof pi.getActiveTools === "function" ? pi.getActiveTools() : null;
      if (!Array.isArray(activeTools) || activeTools.length !== 0) {
        rejectRequest(request, processingPath, "host-tools-active");
        return;
      }
      let hostIdle = false;
      try {
        hostIdle = typeof state.isIdle === "function" && state.isIdle() === true;
      } catch {
        hostIdle = false;
      }
      if (!hostIdle) {
        rejectRequest(request, processingPath, "host-session-busy");
        return;
      }
      state.active = { request, processingPath, correlated: false, running: false, finished: false, events: [] };
      appendEvent(state.active, "request_claimed");
      appendEvent(state.active, "host_turn_dispatched");
      state.timeoutTimer = setTimeout(() => finish("timed_out", "host-turn-timeout", ""), request.timeout_seconds * 1000);
      if (typeof state.timeoutTimer.unref === "function") state.timeoutTimer.unref();
      pi.sendUserMessage(request.instruction);
    } catch {
      const fallback = {
        request_id: "unknown-request",
        target_profile: profileId,
        result_max_bytes: 256,
      };
      state.active = { request: fallback, processingPath, finished: false, events: [] };
      appendEvent(state.active, "request_claimed");
      finish("blocked", "mailbox-request-invalid", "");
    }
  }

  pi.on("session_start", async (_event, ctx) => {
    if (!ctx || typeof ctx.cwd !== "string" || state) return;
    const trustCheck = ctx.isProjectTrusted;
    if (typeof trustCheck === "function") {
      if (trustCheck.call(ctx) !== true) return;
    } else if (profileId !== "omp-local") {
      return;
    }
    let binding;
    try {
      binding = loadBinding(ctx.cwd, options.bindingRelativePath, profileId, options.extensionFile);
      const fixed = PROFILE_PATHS[profileId];
      const requestPath = containedPath(ctx.cwd, fixed.request);
      const resultPath = containedPath(ctx.cwd, fixed.result);
      fs.mkdirSync(path.dirname(requestPath), { recursive: true });
      assertRealParentContainment(ctx.cwd, requestPath);
      assertRealParentContainment(ctx.cwd, resultPath);
      state = {
        root: path.resolve(ctx.cwd),
        binding,
        requestPath,
        resultPath,
        active: null,
        pollTimer: null,
        timeoutTimer: null,
        isIdle: typeof ctx.isIdle === "function" ? () => ctx.isIdle() : null,
      };
      const pollMs = options.pollMs || binding.poll_interval_ms;
      state.pollTimer = setInterval(poll, pollMs);
      if (typeof state.pollTimer.unref === "function") state.pollTimer.unref();
      poll();
    } catch {
      stop();
      state = null;
    }
  });

  pi.on("before_agent_start", async event => {
    if (!state?.active || typeof event?.prompt !== "string") return;
    if (sha256Bytes(Buffer.from(event.prompt, "utf8")) === state.active.request.instruction_digest) {
      state.active.correlated = true;
    }
  });

  pi.on("agent_start", async () => {
    if (state?.active?.correlated) {
      state.active.running = true;
      appendEvent(state.active, "host_turn_started");
    }
  });

  pi.on("agent_end", async event => {
    if (!state?.active?.correlated || !state.active.running) return;
    appendEvent(state.active, "host_turn_completed");
    finish("succeeded", null, assistantOutput(event?.messages));
  });

  pi.on("session_shutdown", async () => {
    if (state?.active) finish("failed", "host-session-closed", "");
    stop();
    state = null;
  });
}

module.exports = {
  PROFILE_PATHS,
  createControlledDispatchExtension,
  implementationDigest,
  validateRequest,
};
