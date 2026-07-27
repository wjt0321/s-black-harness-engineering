"use strict";

const crypto = require("node:crypto");
const fs = require("node:fs");
const path = require("node:path");

const MAX_BYTES = 65536;
const LEASE_STALE_MS = 30000;
const PROFILE_PATHS = Object.freeze({
  "pi-local": ".runtime/external-agent-status/pi-local.v1.json",
  "omp-local": ".runtime/external-agent-status/omp-local.v1.json",
});

function sortedValue(value) {
  if (Array.isArray(value)) return value.map(sortedValue);
  if (value && typeof value === "object") {
    const out = {};
    for (const key of Object.keys(value).sort()) out[key] = sortedValue(value[key]);
    return out;
  }
  return value;
}

function canonicalJson(value) {
  return JSON.stringify(sortedValue(value));
}

function canonicalDigest(value, idField) {
  const body = {};
  for (const [key, item] of Object.entries(value)) {
    if (key !== idField) body[key] = item;
  }
  return "sha256:" + crypto.createHash("sha256").update(canonicalJson(body), "utf8").digest("hex");
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

function assertRealContainment(root, filePath) {
  const realRoot = fs.realpathSync(path.resolve(root));
  const realParent = fs.realpathSync(path.dirname(filePath));
  const prefix = realRoot.endsWith(path.sep) ? realRoot : realRoot + path.sep;
  if (realParent !== realRoot && !realParent.startsWith(prefix)) {
    throw new Error("real path containment failed");
  }
}

function assertRegularPath(filePath) {
  const info = fs.lstatSync(filePath);
  if (!info.isFile() || info.isSymbolicLink() || info.nlink !== 1) {
    throw new Error("unsafe file type");
  }
  return info;
}

function parseJsonFile(filePath, maxBytes = MAX_BYTES) {
  const info = assertRegularPath(filePath);
  if (info.size > maxBytes) throw new Error("file too large");
  const data = fs.readFileSync(filePath);
  if (data.length > maxBytes) throw new Error("file too large");
  const value = JSON.parse(data.toString("utf8"));
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("invalid json object");
  return value;
}

function validateBinding(binding, profileId, expectedDigest) {
  const expectedPath = PROFILE_PATHS[profileId];
  if (!expectedPath || binding.source_relative_path !== expectedPath) throw new Error("binding path drift");
  if (binding.max_bytes !== MAX_BYTES || binding.ttl_seconds !== 15) throw new Error("binding bounds drift");
  if (binding.producer_or_probe_authorized !== true || binding.dispatch_authorized !== false) throw new Error("binding authority drift");
  if (binding.expected_producer?.producer_binding_id !== expectedDigest) throw new Error("producer content drift");
  const previousDigest = binding.previous_producer_binding_id;
  if (previousDigest !== undefined) {
    if (typeof previousDigest !== "string" || !/^sha256:[a-f0-9]{64}$/.test(previousDigest) || previousDigest === expectedDigest) {
      throw new Error("previous producer binding invalid");
    }
  }
  if (binding.expected_producer?.source_kind !== "adapter_owned_atomic_snapshot") throw new Error("producer source drift");
  if (binding.expected_target?.transport?.kind !== "local_process") throw new Error("transport drift");
}

function loadBinding(root, bindingRelativePath, profileId, extensionFile) {
  const bindingPath = containedPath(root, bindingRelativePath);
  assertRealContainment(root, bindingPath);
  const binding = parseJsonFile(bindingPath);
  validateBinding(binding, profileId, implementationDigest(extensionFile));
  return binding;
}

function snapshotPaths(root, profileId) {
  const target = containedPath(root, PROFILE_PATHS[profileId]);
  return {
    root: path.resolve(root),
    target,
    directory: path.dirname(target),
    temporary: target + ".tmp",
    lease: target + ".lock",
  };
}

function safeRemoveRegular(filePath) {
  try {
    const info = assertRegularPath(filePath);
    if (info.size > MAX_BYTES) throw new Error("unsafe cleanup target");
    fs.unlinkSync(filePath);
  } catch (error) {
    if (error && error.code === "ENOENT") return;
    throw error;
  }
}

function acquireLease(paths, profileId, staleMs = LEASE_STALE_MS) {
  fs.mkdirSync(paths.directory, { recursive: true, mode: 0o700 });
  assertRealContainment(paths.root, paths.target);
  try {
    const previous = assertRegularPath(paths.lease);
    if (Date.now() - previous.mtimeMs <= staleMs) return null;
    safeRemoveRegular(paths.lease);
  } catch (error) {
    if (!error || error.code !== "ENOENT") throw error;
  }
  let descriptor;
  try {
    descriptor = fs.openSync(paths.lease, "wx", 0o600);
  } catch (error) {
    if (error && error.code === "EEXIST") return null;
    throw error;
  }
  const lease = canonicalJson({ profile_id: profileId, acquired_at: new Date().toISOString() }) + "\n";
  fs.writeFileSync(descriptor, lease, { encoding: "utf8" });
  fs.fsyncSync(descriptor);
  return descriptor;
}

function refreshLease(paths, descriptor, profileId) {
  const lease = canonicalJson({ profile_id: profileId, refreshed_at: new Date().toISOString() }) + "\n";
  fs.ftruncateSync(descriptor, 0);
  fs.writeSync(descriptor, lease, 0, "utf8");
  fs.fsyncSync(descriptor);
  const now = new Date();
  fs.futimesSync(descriptor, now, now);
}

function releaseLease(paths, descriptor) {
  if (descriptor !== null) fs.closeSync(descriptor);
  safeRemoveRegular(paths.lease);
}

function validateSnapshot(snapshot, binding) {
  if (snapshot.version !== 1 || snapshot.contract !== "external-agent-status-snapshot/v1" || snapshot.complete !== true) {
    throw new Error("snapshot contract invalid");
  }
  if (!Number.isSafeInteger(snapshot.generation) || snapshot.generation < 1) throw new Error("generation invalid");
  if (snapshot.snapshot_id !== canonicalDigest(snapshot, "snapshot_id")) throw new Error("snapshot digest invalid");
  if (canonicalJson(snapshot.producer) !== canonicalJson(binding.expected_producer)) throw new Error("producer mismatch");
  if (canonicalJson(snapshot.target) !== canonicalJson(binding.expected_target)) throw new Error("target mismatch");
  const observation = snapshot.observation || {};
  if (!["listed", "missing", "unknown"].includes(observation.transport_presence)) throw new Error("presence invalid");
  if (!["open", "closed", "unknown"].includes(observation.session_state)) throw new Error("session invalid");
  if (observation.event_cursor !== null) throw new Error("event cursor forbidden");
  const attestation = snapshot.producer_attestation || {};
  for (const key of ["started_process", "connected_transport", "started_runner", "opened_session", "sent_prompt", "invoked_model", "read_credentials", "accessed_network"]) {
    if (attestation[key] !== false) throw new Error("attestation invalid");
  }
}

function nextGeneration(paths, binding) {
  try {
    const previous = parseJsonFile(paths.target, binding.max_bytes);
    try {
      validateSnapshot(previous, binding);
    } catch (currentError) {
      if (binding.previous_producer_binding_id === undefined) throw currentError;
      const previousBinding = {
        ...binding,
        expected_producer: {
          ...binding.expected_producer,
          producer_binding_id: binding.previous_producer_binding_id,
        },
      };
      validateSnapshot(previous, previousBinding);
    }
    return previous.generation + 1;
  } catch (error) {
    if (error && error.code === "ENOENT") return 1;
    throw error;
  }
}

function buildSnapshot(binding, generation, presence, sessionState, safeSummaryZh) {
  const snapshot = {
    version: 1,
    contract: "external-agent-status-snapshot/v1",
    complete: true,
    snapshot_id: "sha256:" + "0".repeat(64),
    generation,
    observed_at: new Date().toISOString(),
    producer: binding.expected_producer,
    target: binding.expected_target,
    observation: {
      transport_presence: presence,
      runner_alias: binding.expected_target.agent_id,
      session_state: sessionState,
      event_cursor: null,
      safe_summary_zh: safeSummaryZh,
    },
    producer_attestation: {
      started_process: false,
      connected_transport: false,
      started_runner: false,
      opened_session: false,
      sent_prompt: false,
      invoked_model: false,
      read_credentials: false,
      accessed_network: false,
    },
  };
  snapshot.snapshot_id = canonicalDigest(snapshot, "snapshot_id");
  return snapshot;
}

function publish(paths, binding, descriptor, profileId, presence, sessionState, safeSummaryZh) {
  refreshLease(paths, descriptor, profileId);
  safeRemoveRegular(paths.temporary);
  const snapshot = buildSnapshot(binding, nextGeneration(paths, binding), presence, sessionState, safeSummaryZh);
  validateSnapshot(snapshot, binding);
  const encoded = Buffer.from(canonicalJson(snapshot) + "\n", "utf8");
  if (encoded.length > binding.max_bytes) throw new Error("snapshot too large");
  const temporaryDescriptor = fs.openSync(paths.temporary, "wx", 0o600);
  try {
    fs.writeFileSync(temporaryDescriptor, encoded);
    fs.fsyncSync(temporaryDescriptor);
  } finally {
    fs.closeSync(temporaryDescriptor);
  }
  validateSnapshot(parseJsonFile(paths.temporary, binding.max_bytes), binding);
  fs.renameSync(paths.temporary, paths.target);
  validateSnapshot(parseJsonFile(paths.target, binding.max_bytes), binding);
  return snapshot;
}

function createLiveStatusExtension(pi, options) {
  const profileId = options.profileId;
  if (!PROFILE_PATHS[profileId]) throw new Error("unsupported profile");
  const heartbeatMs = options.heartbeatMs || 5000;
  const leaseStaleMs = options.leaseStaleMs || LEASE_STALE_MS;
  const leaseRetryMs = options.leaseRetryMs || 5000;
  if (!Number.isSafeInteger(leaseStaleMs) || leaseStaleMs < 10 || leaseStaleMs > LEASE_STALE_MS) {
    throw new Error("lease stale bound invalid");
  }
  if (!Number.isSafeInteger(leaseRetryMs) || leaseRetryMs < 10 || leaseRetryMs > leaseStaleMs) {
    throw new Error("lease retry bound invalid");
  }
  let state = null;
  let retryTimer = null;
  let shuttingDown = false;

  function stopHeartbeat() {
    if (state?.timer) clearInterval(state.timer);
    if (state) state.timer = null;
  }

  function stopLeaseRetry() {
    if (retryTimer) clearTimeout(retryTimer);
    retryTimer = null;
  }

  function publishState(presence, sessionState, summary) {
    if (!state) return null;
    return publish(state.paths, state.binding, state.descriptor, profileId, presence, sessionState, summary);
  }

  function disablePublisher() {
    stopLeaseRetry();
    if (!state) return;
    stopHeartbeat();
    const current = state;
    state = null;
    try {
      releaseLease(current.paths, current.descriptor);
    } catch {
      // 状态扩展清理失败不得影响 Pi/OMP 宿主。
    }
  }

  function publishWithoutHostFailure(presence, sessionState, summary) {
    try {
      return publishState(presence, sessionState, summary);
    } catch {
      disablePublisher();
      return null;
    }
  }

  function scheduleLeaseRetry(ctx) {
    if (retryTimer || shuttingDown || state) return;
    retryTimer = setTimeout(() => {
      retryTimer = null;
      startPublisher(ctx);
    }, leaseRetryMs);
    if (typeof retryTimer.unref === "function") retryTimer.unref();
  }

  function startPublisher(ctx) {
    if (state || shuttingDown) return;
    let paths = null;
    let descriptor = null;
    try {
      paths = snapshotPaths(ctx.cwd, profileId);
      const binding = loadBinding(ctx.cwd, options.bindingRelativePath, profileId, options.extensionFile);
      descriptor = acquireLease(paths, profileId, leaseStaleMs);
      if (descriptor === null) {
        scheduleLeaseRetry(ctx);
        return;
      }
      state = { paths, binding, descriptor, timer: null };
      publishState("listed", "open", "宿主进程内扩展已观察到会话；该证据不授权派发。" );
      state.timer = setInterval(() => {
        try {
          publishState("listed", "open", "宿主进程内扩展正在持续发布只读状态。" );
        } catch {
          disablePublisher();
        }
      }, heartbeatMs);
      if (typeof state.timer.unref === "function") state.timer.unref();
    } catch {
      stopHeartbeat();
      state = null;
      if (paths && descriptor !== null) {
        try {
          releaseLease(paths, descriptor);
        } catch {
          // 状态扩展失败不得影响 Pi/OMP 宿主。
        }
      }
    }
  }

  pi.on("session_start", async (_event, ctx) => {
    if (!ctx || typeof ctx.cwd !== "string") return;
    const trustCheck = ctx.isProjectTrusted;
    if (typeof trustCheck === "function") {
      if (trustCheck.call(ctx) !== true) return;
    } else if (profileId !== "omp-local") {
      // Pi 必须提供并通过项目信任；OMP 当前没有暴露该方法，只允许固定 OMP 配置。
      return;
    }
    shuttingDown = false;
    startPublisher(ctx);
  });

  pi.on("agent_start", async () => {
    publishWithoutHostFailure("listed", "open", "宿主已观察到智能体活动；未读取提示词、模型或原始输出。" );
  });

  pi.on("agent_end", async () => {
    publishWithoutHostFailure("listed", "open", "宿主会话仍然存在；当前未观察到持续处理。" );
  });

  pi.on("session_shutdown", async () => {
    shuttingDown = true;
    stopLeaseRetry();
    if (!state) return;
    stopHeartbeat();
    publishWithoutHostFailure("missing", "closed", "宿主会话已关闭；等待下一次被动观察。" );
    disablePublisher();
  });
}

function readPublishedSnapshot(root, profileId) {
  const paths = snapshotPaths(root, profileId);
  return parseJsonFile(paths.target);
}

module.exports = {
  PROFILE_PATHS,
  canonicalDigest,
  createLiveStatusExtension,
  implementationDigest,
  readPublishedSnapshot,
};
