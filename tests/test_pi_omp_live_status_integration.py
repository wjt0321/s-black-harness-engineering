from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest

from agent_runtime import orchestration_control_panel as control_panel
from agent_runtime import orchestration_external_agent_live_status as live_status

ROOT = Path(__file__).resolve().parents[1]
PROFILES = ("pi-local", "omp-local")
FORBIDDEN_EXTENSION_TOKENS = (
    "process.env",
    "process.argv",
    "fetch(",
    "http://",
    "https://",
    "child_process",
    "spawn(",
    "exec(",
    "event.prompt",
    "event.message",
    "tool_input",
    "sessionManager",
    "modelRegistry",
)


def _canonical_digest(value: dict, id_field: str) -> str:
    body = {key: item for key, item in value.items() if key != id_field}
    encoded = json.dumps(
        body,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _binding(profile_id: str) -> dict:
    path = live_status.FIXED_STATUS_PROFILES[profile_id].binding_path
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def _snapshot(binding: dict, *, observed_at: str, generation: int = 1, session_state: str = "closed") -> dict:
    payload = {
        "version": 1,
        "contract": "external-agent-status-snapshot/v1",
        "complete": True,
        "snapshot_id": "sha256:" + "0" * 64,
        "generation": generation,
        "observed_at": observed_at,
        "producer": binding["expected_producer"],
        "target": binding["expected_target"],
        "observation": {
            "transport_presence": "listed",
            "runner_alias": binding["expected_target"]["agent_id"],
            "session_state": session_state,
            "event_cursor": None,
            "safe_summary_zh": "宿主进程内扩展已观察到运行状态。",
        },
        "producer_attestation": {
            "started_process": False,
            "connected_transport": False,
            "started_runner": False,
            "opened_session": False,
            "sent_prompt": False,
            "invoked_model": False,
            "read_credentials": False,
            "accessed_network": False,
        },
    }
    payload["snapshot_id"] = _canonical_digest(payload, "snapshot_id")
    return payload


def _write_snapshot(root: Path, profile_id: str, payload: dict) -> None:
    relative = live_status.FIXED_STATUS_PROFILES[profile_id].snapshot_path
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_pi_and_omp_project_extensions_are_minimal_and_do_not_collect_sensitive_runtime_data() -> None:
    paths = (
        ROOT / ".pi/extensions/s-black-live-status.ts",
        ROOT / ".omp/extensions/s-black-live-status.ts",
        ROOT / "integrations/pi_omp_live_status/publisher.cjs",
    )
    for path in paths:
        text = path.read_text(encoding="utf-8")
        for token in FORBIDDEN_EXTENSION_TOKENS:
            assert token not in text, f"{path} contains forbidden token {token!r}"


def test_fixed_profiles_bind_pi_and_omp_to_separate_reviewed_paths() -> None:
    attributes = (ROOT / ".gitattributes").read_text(encoding="utf-8").splitlines()
    assert ".pi/extensions/s-black-live-status.ts text eol=lf" in attributes
    assert ".omp/extensions/s-black-live-status.ts text eol=lf" in attributes
    assert "integrations/pi_omp_live_status/publisher.cjs text eol=lf" in attributes
    assert set(live_status.FIXED_STATUS_PROFILES) >= set(PROFILES)
    assert live_status.FIXED_STATUS_PROFILES["pi-local"].snapshot_path.as_posix() == ".runtime/external-agent-status/pi-local.v1.json"
    assert live_status.FIXED_STATUS_PROFILES["omp-local"].snapshot_path.as_posix() == ".runtime/external-agent-status/omp-local.v1.json"

    for profile_id in PROFILES:
        binding = _binding(profile_id)
        assert binding["source_relative_path"] == live_status.FIXED_STATUS_PROFILES[profile_id].snapshot_path.as_posix()
        assert binding["producer_or_probe_authorized"] is True
        assert binding["dispatch_authorized"] is False
        assert binding["expected_target"]["transport"]["kind"] == "local_process"
        assert binding["expected_producer"]["producer_version"] == "1.0.0"
        wrapper = ROOT / (
            ".pi/extensions/s-black-live-status.ts"
            if profile_id == "pi-local"
            else ".omp/extensions/s-black-live-status.ts"
        )
        digest = hashlib.sha256()
        digest.update((ROOT / "integrations/pi_omp_live_status/publisher.cjs").read_bytes())
        digest.update(b"\0")
        digest.update(wrapper.read_bytes())
        assert binding["expected_producer"]["producer_binding_id"] == "sha256:" + digest.hexdigest()


def test_pi_omp_publisher_handles_start_heartbeat_and_shutdown_without_agent_execution(tmp_path: Path) -> None:
    for profile_id in PROFILES:
        binding_path = live_status.FIXED_STATUS_PROFILES[profile_id].binding_path
        destination = tmp_path / binding_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((ROOT / binding_path).read_bytes())

    node_script = r'''
const path = require("node:path");
const publisher = require(process.argv[1]);
const root = process.argv[2];
const repo = process.argv[3];
const profile = process.argv[4];
const handlers = new Map();
const pi = { on(name, handler) { handlers.set(name, handler); } };
const wrapper = path.join(repo, profile === "pi-local" ? ".pi/extensions/s-black-live-status.ts" : ".omp/extensions/s-black-live-status.ts");
publisher.createLiveStatusExtension(pi, {
  profileId: profile,
  bindingRelativePath: `adapters/external-agent-live-status-binding.${profile}.json`,
  extensionFile: wrapper,
  heartbeatMs: 20,
});
const ctx = { cwd: root, isProjectTrusted() { return true; } };
(async () => {
  await handlers.get("session_start")({ type: "session_start", reason: "startup" }, ctx);
  const first = publisher.readPublishedSnapshot(root, profile);
  await new Promise((resolve) => setTimeout(resolve, 45));
  const heartbeat = publisher.readPublishedSnapshot(root, profile);
  await handlers.get("session_shutdown")({ type: "session_shutdown" }, ctx);
  const shutdown = publisher.readPublishedSnapshot(root, profile);
  process.stdout.write(JSON.stringify({ first, heartbeat, shutdown }));
})().catch((error) => { console.error(error); process.exit(1); });
'''

    for profile_id in PROFILES:
        completed = subprocess.run(
            [
                "node",
                "-e",
                node_script,
                str(ROOT / "integrations/pi_omp_live_status/publisher.cjs"),
                str(tmp_path),
                str(ROOT),
                profile_id,
            ],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=15,
        )
        assert completed.returncode == 0, completed.stderr
        result = json.loads(completed.stdout)
        assert result["first"]["observation"]["transport_presence"] == "listed"
        assert result["first"]["observation"]["session_state"] == "open"
        assert result["heartbeat"]["generation"] > result["first"]["generation"]
        assert result["shutdown"]["generation"] > result["heartbeat"]["generation"]
        assert result["shutdown"]["observation"]["transport_presence"] == "missing"
        assert result["shutdown"]["observation"]["session_state"] == "closed"
        assert result["shutdown"]["producer_attestation"] == {
            "started_process": False,
            "connected_transport": False,
            "started_runner": False,
            "opened_session": False,
            "sent_prompt": False,
            "invoked_model": False,
            "read_credentials": False,
            "accessed_network": False,
        }
        inspected = live_status.inspect_external_agent_live_status(
            ROOT,
            result["shutdown"]["observed_at"],
            profile_id=profile_id,
            snapshot_root=tmp_path,
        )
        assert inspected.status == "pass"
        assert inspected.observation_status == "unavailable"
        assert inspected.evidence is not None
        assert inspected.evidence["source_integrity"]["producer_binding_valid"] is True




def test_publisher_recovers_after_abrupt_restart_lease_becomes_stale(tmp_path: Path) -> None:
    profile_id = "pi-local"
    binding_path = live_status.FIXED_STATUS_PROFILES[profile_id].binding_path
    destination = tmp_path / binding_path
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes((ROOT / binding_path).read_bytes())
    status_dir = tmp_path / ".runtime/external-agent-status"
    status_dir.mkdir(parents=True, exist_ok=True)
    (status_dir / "pi-local.v1.json.lock").write_text('{"profile_id":"pi-local"}\n', encoding="utf-8")

    node_script = r'''
const path = require("node:path");
const publisher = require(process.argv[1]);
const root = process.argv[2];
const repo = process.argv[3];
const handlers = new Map();
const pi = { on(name, handler) { handlers.set(name, handler); } };
publisher.createLiveStatusExtension(pi, {
  profileId: "pi-local",
  bindingRelativePath: "adapters/external-agent-live-status-binding.pi-local.json",
  extensionFile: path.join(repo, ".pi/extensions/s-black-live-status.ts"),
  heartbeatMs: 10000,
  leaseStaleMs: 40,
  leaseRetryMs: 20,
});
const ctx = { cwd: root, isProjectTrusted() { return true; } };
(async () => {
  await handlers.get("session_start")({}, ctx);
  await new Promise((resolve) => setTimeout(resolve, 120));
  const recovered = publisher.readPublishedSnapshot(root, "pi-local");
  await handlers.get("session_shutdown")({}, ctx);
  process.stdout.write(JSON.stringify(recovered));
})().catch((error) => { console.error(error); process.exit(1); });
'''
    completed = subprocess.run(
        [
            "node",
            "-e",
            node_script,
            str(ROOT / "integrations/pi_omp_live_status/publisher.cjs"),
            str(tmp_path),
            str(ROOT),
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=15,
    )
    assert completed.returncode == 0, completed.stderr
    recovered = json.loads(completed.stdout)
    assert recovered["observation"]["session_state"] == "open"
    assert recovered["producer"] == _binding(profile_id)["expected_producer"]



def test_publisher_accepts_only_explicit_previous_binding_during_reviewed_upgrade(tmp_path: Path) -> None:
    profile_id = "pi-local"
    binding_path = live_status.FIXED_STATUS_PROFILES[profile_id].binding_path
    current_binding = _binding(profile_id)
    previous_binding_id = "sha256:" + "1" * 64
    current_binding["previous_producer_binding_id"] = previous_binding_id
    destination = tmp_path / binding_path
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(current_binding, ensure_ascii=False), encoding="utf-8")

    previous_binding = json.loads(json.dumps(current_binding))
    previous_binding["expected_producer"]["producer_binding_id"] = previous_binding_id
    previous = _snapshot(previous_binding, observed_at="2026-07-27T12:00:00Z", generation=7)
    _write_snapshot(tmp_path, profile_id, previous)

    node_script = r'''
const path = require("node:path");
const publisher = require(process.argv[1]);
const root = process.argv[2];
const repo = process.argv[3];
const handlers = new Map();
const pi = { on(name, handler) { handlers.set(name, handler); } };
publisher.createLiveStatusExtension(pi, {
  profileId: "pi-local",
  bindingRelativePath: "adapters/external-agent-live-status-binding.pi-local.json",
  extensionFile: path.join(repo, ".pi/extensions/s-black-live-status.ts"),
  heartbeatMs: 10000,
});
const ctx = { cwd: root, isProjectTrusted() { return true; } };
(async () => {
  await handlers.get("session_start")({}, ctx);
  const upgraded = publisher.readPublishedSnapshot(root, "pi-local");
  await handlers.get("session_shutdown")({}, ctx);
  process.stdout.write(JSON.stringify(upgraded));
})().catch((error) => { console.error(error); process.exit(1); });
'''
    completed = subprocess.run(
        [
            "node",
            "-e",
            node_script,
            str(ROOT / "integrations/pi_omp_live_status/publisher.cjs"),
            str(tmp_path),
            str(ROOT),
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=15,
    )
    assert completed.returncode == 0, completed.stderr
    upgraded = json.loads(completed.stdout)
    assert upgraded["generation"] == 8
    assert upgraded["producer"] == current_binding["expected_producer"]
    assert upgraded["observation"]["session_state"] == "open"



def test_single_writer_lease_prevents_second_pi_publisher_from_overwriting(tmp_path: Path) -> None:
    binding_path = live_status.FIXED_STATUS_PROFILES["pi-local"].binding_path
    destination = tmp_path / binding_path
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes((ROOT / binding_path).read_bytes())
    node_script = r'''
const path = require("node:path");
const publisher = require(process.argv[1]);
const root = process.argv[2];
const repo = process.argv[3];
function host() { const handlers = new Map(); return { handlers, api: { on(name, handler) { handlers.set(name, handler); } } }; }
const first = host(); const second = host();
const options = {
  profileId: "pi-local",
  bindingRelativePath: "adapters/external-agent-live-status-binding.pi-local.json",
  extensionFile: path.join(repo, ".pi/extensions/s-black-live-status.ts"),
  heartbeatMs: 10000,
};
publisher.createLiveStatusExtension(first.api, options);
publisher.createLiveStatusExtension(second.api, options);
const ctx = { cwd: root, isProjectTrusted() { return true; } };
(async () => {
  await first.handlers.get("session_start")({}, ctx);
  const afterFirst = publisher.readPublishedSnapshot(root, "pi-local");
  await second.handlers.get("session_start")({}, ctx);
  await second.handlers.get("agent_start")({}, ctx);
  const afterSecond = publisher.readPublishedSnapshot(root, "pi-local");
  await second.handlers.get("session_shutdown")({}, ctx);
  await first.handlers.get("session_shutdown")({}, ctx);
  const final = publisher.readPublishedSnapshot(root, "pi-local");
  process.stdout.write(JSON.stringify({ afterFirst, afterSecond, final }));
})().catch((error) => { console.error(error); process.exit(1); });
'''
    completed = subprocess.run(
        ["node", "-e", node_script, str(ROOT / "integrations/pi_omp_live_status/publisher.cjs"), str(tmp_path), str(ROOT)],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=15,
    )
    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    assert result["afterSecond"]["generation"] == result["afterFirst"]["generation"]
    assert result["final"]["generation"] == result["afterFirst"]["generation"] + 1
    assert result["final"]["observation"]["transport_presence"] == "missing"



def test_omp_without_pi_trust_api_publishes_but_pi_stays_fail_closed(tmp_path: Path) -> None:
    for profile_id in PROFILES:
        binding_path = live_status.FIXED_STATUS_PROFILES[profile_id].binding_path
        destination = tmp_path / binding_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((ROOT / binding_path).read_bytes())

    node_script = r'''
const path = require("node:path");
const publisher = require(process.argv[1]);
const root = process.argv[2];
const repo = process.argv[3];
function host() { const handlers = new Map(); return { handlers, api: { on(name, handler) { handlers.set(name, handler); } } }; }
const pi = host();
const omp = host();
publisher.createLiveStatusExtension(pi.api, {
  profileId: "pi-local",
  bindingRelativePath: "adapters/external-agent-live-status-binding.pi-local.json",
  extensionFile: path.join(repo, ".pi/extensions/s-black-live-status.ts"),
  heartbeatMs: 10000,
});
publisher.createLiveStatusExtension(omp.api, {
  profileId: "omp-local",
  bindingRelativePath: "adapters/external-agent-live-status-binding.omp-local.json",
  extensionFile: path.join(repo, ".omp/extensions/s-black-live-status.ts"),
  heartbeatMs: 10000,
});
const ompContext = { cwd: root };
const piContext = { cwd: root };
(async () => {
  await omp.handlers.get("session_start")({}, ompContext);
  await pi.handlers.get("session_start")({}, piContext);
  const ompSnapshot = publisher.readPublishedSnapshot(root, "omp-local");
  const piExists = require("node:fs").existsSync(path.join(root, ".runtime/external-agent-status/pi-local.v1.json"));
  await omp.handlers.get("session_shutdown")({}, ompContext);
  process.stdout.write(JSON.stringify({ ompPresence: ompSnapshot.observation.transport_presence, piExists }));
})().catch((error) => { console.error(error); process.exit(1); });
'''
    completed = subprocess.run(
        ["node", "-e", node_script, str(ROOT / "integrations/pi_omp_live_status/publisher.cjs"), str(tmp_path), str(ROOT)],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=15,
    )
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout) == {"ompPresence": "listed", "piExists": False}

def test_publisher_binding_failure_does_not_break_pi_or_omp_host(tmp_path: Path) -> None:
    node_script = r'''
const path = require("node:path");
const publisher = require(process.argv[1]);
const root = process.argv[2];
const repo = process.argv[3];
const handlers = new Map();
const pi = { on(name, handler) { handlers.set(name, handler); } };
publisher.createLiveStatusExtension(pi, {
  profileId: "pi-local",
  bindingRelativePath: "adapters/missing-binding.json",
  extensionFile: path.join(repo, ".pi/extensions/s-black-live-status.ts"),
  heartbeatMs: 20,
});
const ctx = { cwd: root, isProjectTrusted() { return true; } };
(async () => {
  await handlers.get("session_start")({ type: "session_start", reason: "startup" }, ctx);
  await handlers.get("session_shutdown")({ type: "session_shutdown" }, ctx);
  process.stdout.write(JSON.stringify({ hostContinued: true }));
})().catch((error) => { console.error(error); process.exit(1); });
'''
    completed = subprocess.run(
        [
            "node",
            "-e",
            node_script,
            str(ROOT / "integrations/pi_omp_live_status/publisher.cjs"),
            str(tmp_path),
            str(ROOT),
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=15,
    )
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout) == {"hostContinued": True}
    assert not (tmp_path / ".runtime/external-agent-status/pi-local.v1.json").exists()


def test_missing_pi_snapshot_is_projected_as_disconnected_not_binding_failure(tmp_path: Path) -> None:
    result = live_status.inspect_external_agent_live_status(
        ROOT,
        "2026-07-27T12:00:00Z",
        profile_id="pi-local",
        snapshot_root=tmp_path,
    )
    assert result.status == "pass"
    assert result.observation_status == "unavailable"
    assert result.gui_projection is not None
    assert result.gui_projection["status"] == "disconnected"
    assert result.gui_projection["status_label_zh"] == "未连接"
    assert result.gui_projection["readiness"]["binding_valid"] is True


def test_open_omp_session_is_visible_but_never_dispatch_authorized(tmp_path: Path) -> None:
    binding = _binding("omp-local")
    payload = _snapshot(binding, observed_at="2026-07-27T11:59:55Z", session_state="open")
    _write_snapshot(tmp_path, "omp-local", payload)

    result = live_status.inspect_external_agent_live_status(
        ROOT,
        "2026-07-27T12:00:00Z",
        profile_id="omp-local",
        snapshot_root=tmp_path,
    )
    assert result.status == "pass"
    assert result.evidence is not None
    assert result.evidence["execution_authorized"] is False
    assert result.evidence["sufficient_for_dispatch"] is False
    assert result.gui_projection is not None
    assert result.gui_projection["status"] == "busy"
    assert result.gui_projection["status_label_zh"] == "已连接，存在未绑定会话"
    assert result.gui_projection["session"]["state"] == "open"
    assert result.gui_projection["session"]["external_session_ref"] is None
    assert result.gui_projection["blocked_reason_code"] == "session_mapping_conflict"


def test_control_panel_adds_chinese_live_status_section(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def fake_inspect(root: Path, evaluated_at: str, *, profile_id: str, **_: object):
        calls.append(profile_id)
        binding = _binding(profile_id)
        evidence = {
            "observed_at": "2026-07-27T11:59:55Z",
            "expires_at": "2026-07-27T12:00:10Z",
            "source_integrity": {"producer_binding_valid": True},
            "execution_authorized": False,
            "sufficient_for_dispatch": False,
        }
        projection = {
            "agent_id": binding["expected_target"]["agent_id"],
            "adapter_id": binding["expected_target"]["adapter_id"],
            "display_name_zh": "Pi 编码智能体" if profile_id == "pi-local" else "OMP 编码智能体",
            "status": "unknown",
            "status_label_zh": "已连接，尚未证明就绪",
            "transport": binding["expected_target"]["transport"],
            "capabilities": [],
            "readiness": {
                "status": "unknown",
                "status_label_zh": "已连接，尚未证明就绪",
                "evidence_id": "sha256:" + "1" * 64,
                "expires_at": evidence["expires_at"],
                "binding_valid": True,
                "safe_summary_zh": "仅证明宿主正在运行。",
            },
            "session": None,
            "current_work_item_id": None,
            "blocked_reason_code": "readiness_unknown",
            "safe_summary_zh": "仅证明宿主正在运行。",
        }
        return live_status.ExternalAgentLiveStatusResult(
            status="pass",
            observation_status="observed",
            evidence=evidence,
            gui_projection=projection,
        )

    monkeypatch.setattr(control_panel, "inspect_external_agent_live_status", fake_inspect)
    payload = control_panel.build_control_panel_snapshot(
        ROOT,
        external_agent_evaluated_at="2026-07-27T12:00:00Z",
    ).to_dict()

    assert calls == ["pi-local", "omp-local"]
    section = payload["sections"]["external_agents"]
    assert section["status"] == "pass"
    assert [item["display_name_zh"] for item in section["agents"]] == ["Pi 编码智能体", "OMP 编码智能体"]
    assert section["dispatch_authorized"] is False
    rendered = control_panel.render_control_panel_html(payload)
    assert "外部智能体 / 实时状态" in rendered
    assert "最后观察时间" in rendered
    assert "证据有效" in rendered
    assert "不可派发原因" in rendered
    for forbidden in ("进程号", "会话标识", "端点", "原始输出"):
        assert forbidden not in rendered
