from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DISPATCHER = ROOT / "integrations/pi_omp_live_status/controlled_dispatch.cjs"


def _run_node(tmp_path: Path, mode: str, profile: str = "pi-local") -> dict:
    script = r'''
const fs = require("node:fs");
const path = require("node:path");
const crypto = require("node:crypto");
const dispatcher = require(process.argv[1]);
const root = process.argv[2];
const repo = process.argv[3];
const mode = process.argv[4];
const profile = process.argv[5];
const handlers = {};
const sent = [];
const execCalls = [];
const pi = {
  on(name, handler) { handlers[name] = handler; },
  sendUserMessage(text, options) { sent.push({ text, options }); },
  getActiveTools() { return mode === "tools" ? ["bash"] : []; },
  exec(...args) { execCalls.push(args); throw new Error("exec forbidden"); },
};
const extensionFile = path.join(repo, profile === "pi-local" ? ".pi/extensions/s-black-live-status.ts" : ".omp/extensions/s-black-live-status.ts");
dispatcher.createControlledDispatchExtension(pi, {
  profileId: profile,
  bindingRelativePath: `adapters/external-agent-dispatch-binding.${profile}.json`,
  extensionFile,
  pollMs: 20,
});
(async () => {
  await handlers.session_start({}, {
    cwd: root,
    isProjectTrusted: () => true,
    isIdle: () => mode !== "busy",
  });
  const instruction = "只回复：阶段87受控执行验收通过。不要使用工具。";
  const digest = "sha256:" + crypto.createHash("sha256").update(Buffer.from(instruction, "utf8")).digest("hex");
  const request = {
    version: 1,
    contract: "external-agent-single-work-item-mailbox/v1",
    request_id: "request-stage87-node-001",
    task_id: "task-stage87",
    work_item_id: "implement",
    target_profile: profile,
    approval_binding_id: "sha256:" + "a".repeat(64),
    plan_hash: "sha256:" + "b".repeat(64),
    instruction,
    instruction_digest: mode === "digest" ? "sha256:" + "0".repeat(64) : digest,
    input_artifacts: [],
    timeout_seconds: 30,
    result_max_bytes: 8192,
    issued_at: new Date().toISOString(),
  };
  const requestPath = path.join(root, ".runtime/external-agent-dispatch", `${profile}.request.v1.json`);
  fs.mkdirSync(path.dirname(requestPath), { recursive: true });
  fs.writeFileSync(requestPath, JSON.stringify(request));
  await new Promise(resolve => setTimeout(resolve, 100));
  if (sent.length) {
    await handlers.before_agent_start({ type: "before_agent_start", prompt: instruction }, {});
    await handlers.agent_start({ type: "agent_start" }, {});
    await handlers.agent_end({
      type: "agent_end",
      messages: [{ role: "assistant", content: [{ type: "text", text: "阶段87受控执行验收通过。" }] }],
    }, {});
  }
  await new Promise(resolve => setTimeout(resolve, 40));
  const resultPath = path.join(root, ".runtime/external-agent-dispatch", `${profile}.result.v1.json`);
  const result = fs.existsSync(resultPath) ? JSON.parse(fs.readFileSync(resultPath, "utf8")) : null;
  await handlers.session_shutdown({ type: "session_shutdown" }, {});
  process.stdout.write(JSON.stringify({ sent, execCalls, result }));
})().catch(error => { console.error(error); process.exit(1); });
'''
    completed = subprocess.run(
        ["node", "-e", script, str(DISPATCHER), str(tmp_path), str(ROOT), mode, profile],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=15,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    return json.loads(completed.stdout)


def _copy_bindings(tmp_path: Path) -> None:
    adapters = tmp_path / "adapters"
    adapters.mkdir(parents=True, exist_ok=True)
    for profile in ("pi-local", "omp-local"):
        source = ROOT / f"adapters/external-agent-dispatch-binding.{profile}.json"
        (adapters / source.name).write_bytes(source.read_bytes())


def test_valid_fixed_request_sends_exactly_one_user_message_and_collects_result(tmp_path: Path) -> None:
    _copy_bindings(tmp_path)
    result = _run_node(tmp_path, "success")
    assert result["execCalls"] == []
    assert result["sent"] == [{
        "text": "只回复：阶段87受控执行验收通过。不要使用工具。",
    }]
    assert result["result"]["version"] == 2
    assert result["result"]["contract"] == "external-agent-single-work-item-result/v2"
    assert result["result"]["status"] == "succeeded"
    assert result["result"]["output"] == "阶段87受控执行验收通过。"
    assert result["result"]["artifacts"] == []
    assert [event["event_type"] for event in result["result"]["events"]] == [
        "request_claimed",
        "host_turn_dispatched",
        "host_turn_started",
        "host_turn_completed",
    ]
    assert [event["sequence"] for event in result["result"]["events"]] == [1, 2, 3, 4]


def test_dispatch_is_blocked_when_host_tools_are_active(tmp_path: Path) -> None:
    _copy_bindings(tmp_path)
    result = _run_node(tmp_path, "tools")
    assert result["sent"] == []
    assert result["execCalls"] == []
    assert result["result"]["status"] == "blocked"
    assert result["result"]["failure_code"] == "host-tools-active"
    assert [event["event_type"] for event in result["result"]["events"]] == [
        "request_claimed",
        "host_turn_blocked",
    ]
    assert result["result"]["events"][-1]["failure_code"] == "host-tools-active"
    assert "output" not in result["result"]


def test_dispatch_is_blocked_when_host_session_is_busy(tmp_path: Path) -> None:
    _copy_bindings(tmp_path)
    result = _run_node(tmp_path, "busy", profile="omp-local")
    assert result["sent"] == []
    assert result["execCalls"] == []
    assert result["result"]["status"] == "blocked"
    assert result["result"]["failure_code"] == "host-session-busy"
    assert [event["event_type"] for event in result["result"]["events"]] == [
        "request_claimed",
        "host_turn_blocked",
    ]
    assert result["result"]["events"][-1]["failure_code"] == "host-session-busy"
    assert "output" not in result["result"]


def test_instruction_digest_drift_never_reaches_agent(tmp_path: Path) -> None:
    _copy_bindings(tmp_path)
    result = _run_node(tmp_path, "digest", profile="omp-local")
    assert result["sent"] == []
    assert result["execCalls"] == []
    assert result["result"]["status"] == "blocked"
    assert result["result"]["failure_code"] == "instruction-digest-mismatch"
