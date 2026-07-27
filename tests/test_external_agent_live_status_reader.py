"""Stage 84 tests for the fixed external-Agent live status snapshot reader."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator, validate

from agent_runtime.orchestration_external_agent_live_status import (
    FIXED_SNAPSHOT_PATH,
    inspect_external_agent_live_status,
)

ROOT = Path(__file__).resolve().parents[1]
EVALUATED = "2026-07-27T08:00:05Z"


def _canonical_digest(value: dict[str, Any], id_field: str) -> str:
    body = {key: item for key, item in value.items() if key != id_field}
    encoded = json.dumps(
        body,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _load(name: str) -> dict[str, Any]:
    return json.loads((ROOT / "adapters" / name).read_text(encoding="utf-8"))


def _write_snapshot(root: Path, snapshot: dict[str, Any] | None = None) -> Path:
    value = snapshot or _load("external-agent-status-snapshot.example.json")
    value = json.loads(json.dumps(value))
    value["snapshot_id"] = _canonical_digest(value, "snapshot_id")
    target = root / FIXED_SNAPSHOT_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    return target


def _project(tmp_path: Path, snapshot: dict[str, Any] | None = None) -> Path:
    root = tmp_path / "project"
    adapters = root / "adapters"
    adapters.mkdir(parents=True)
    for name in (
        "external-agent-status-snapshot.schema.json",
        "external-agent-live-status-binding.schema.json",
        "external-agent-live-status-binding.json",
        "external-agent-live-status-evidence.schema.json",
        "external-agent-live-read-model.schema.json",
    ):
        (adapters / name).write_bytes((ROOT / "adapters" / name).read_bytes())
    if snapshot is not None:
        _write_snapshot(root, snapshot)
    return root


def test_stage84_contract_assets_are_valid_and_content_bound() -> None:
    for name in (
        "external-agent-live-status-binding.schema.json",
        "external-agent-live-status-evidence.schema.json",
    ):
        Draft202012Validator.check_schema(_load(name))

    binding = _load("external-agent-live-status-binding.json")
    validate(binding, _load("external-agent-live-status-binding.schema.json"))
    assert binding["source_relative_path"] == FIXED_SNAPSHOT_PATH.as_posix()
    assert binding["max_bytes"] == 65536
    assert binding["ttl_seconds"] == 15
    assert binding["producer_or_probe_authorized"] is False
    assert binding["dispatch_authorized"] is False

    snapshot = _load("external-agent-status-snapshot.example.json")
    assert snapshot["snapshot_id"] == _canonical_digest(snapshot, "snapshot_id")


def test_valid_snapshot_produces_normalized_evidence_and_stage82_projection(
    tmp_path: Path,
) -> None:
    root = _project(tmp_path, _load("external-agent-status-snapshot.example.json"))

    payload = inspect_external_agent_live_status(root, EVALUATED).to_dict()

    assert payload["status"] == "pass"
    assert payload["observation_status"] == "observed"
    assert payload["source"]["snapshot_file"] == FIXED_SNAPSHOT_PATH.as_posix()
    evidence = payload["evidence"]
    assert evidence["evidence_id"] == _canonical_digest(evidence, "evidence_id")
    assert evidence["readiness_status"] == "unknown"
    assert evidence["readiness_level"] == "runner_listed"
    assert evidence["session_binding"] is None
    assert evidence["event_cursor"] is None
    assert evidence["sufficient_for_dispatch"] is False
    assert evidence["execution_authorized"] is False
    projection = payload["gui_projection"]
    assert projection["status"] == "unknown"
    assert projection["readiness"]["status"] == "unknown"
    assert projection["session"] is None
    assert projection["blocked_reason_code"] is None
    assert payload["guarantees"] == {
        "deterministic": True,
        "read_only": True,
        "fixed_path_only": True,
        "starts_process": False,
        "connects_acp": False,
        "opens_session": False,
        "sends_prompt": False,
        "invokes_model": False,
        "reads_credentials": False,
        "accesses_network": False,
        "writes_files": False,
        "writes_ledger": False,
        "grants_execution_authority": False,
        "enables_dispatch": False,
    }


def test_missing_fixed_snapshot_fails_closed_without_source_contents(tmp_path: Path) -> None:
    root = _project(tmp_path)

    result = inspect_external_agent_live_status(root, EVALUATED)
    payload = result.to_dict()

    assert result.exit_code() == 2
    assert payload["status"] == "blocked"
    assert payload["observation_status"] == "blocked"
    assert payload["findings"] == [
        {
            "rule_id": "status_source_missing",
            "severity": "block",
            "action": "deny",
            "message": "固定状态快照不存在。",
        }
    ]
    assert "evidence" not in payload
    assert payload["gui_projection"]["status"] == "blocked"


def test_explicit_previous_generation_detects_replay_without_writing_state(
    tmp_path: Path,
) -> None:
    root = _project(tmp_path, _load("external-agent-status-snapshot.example.json"))

    payload = inspect_external_agent_live_status(
        root,
        EVALUATED,
        expected_after_generation=1,
    ).to_dict()

    assert payload["status"] == "pass"
    assert payload["observation_status"] == "stale"
    assert payload["findings"][0]["rule_id"] == "status_snapshot_replayed"
    assert payload["gui_projection"]["readiness"]["status"] == "stale"
    assert payload["gui_projection"]["blocked_reason_code"] == "readiness_expired"

@pytest.mark.parametrize(
    ("mode", "expected_code"),
    [
        ("directory", "status_source_not_regular"),
        ("oversize", "status_source_too_large"),
        ("invalid_utf8", "status_source_unreadable"),
        ("invalid_json", "status_source_unreadable"),
        ("duplicate_key", "status_source_unreadable"),
    ],
)
def test_fixed_source_file_failures_are_stable(
    tmp_path: Path,
    mode: str,
    expected_code: str,
) -> None:
    root = _project(tmp_path)
    target = root / FIXED_SNAPSHOT_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    if mode == "directory":
        target.mkdir()
    elif mode == "oversize":
        target.write_bytes(b"{" + b" " * 65536 + b"}")
    elif mode == "invalid_utf8":
        target.write_bytes(b"\xff\xfe")
    elif mode == "invalid_json":
        target.write_text("{", encoding="utf-8")
    else:
        target.write_text('{"complete":true,"complete":true}', encoding="utf-8")

    payload = inspect_external_agent_live_status(root, EVALUATED).to_dict()

    assert payload["status"] == "blocked"
    assert payload["findings"][0]["rule_id"] == expected_code


def test_symlink_snapshot_is_blocked_when_supported(tmp_path: Path) -> None:
    root = _project(tmp_path)
    real = root / "real.json"
    real.write_text("{}", encoding="utf-8")
    target = root / FIXED_SNAPSHOT_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        target.symlink_to(real)
    except OSError:
        pytest.skip("symlink creation is unavailable")

    payload = inspect_external_agent_live_status(root, EVALUATED).to_dict()

    assert payload["findings"][0]["rule_id"] == "status_source_indirection_blocked"


def test_hardlink_snapshot_is_blocked(tmp_path: Path) -> None:
    root = _project(tmp_path)
    real = root / "real.json"
    real.write_text("{}", encoding="utf-8")
    target = root / FIXED_SNAPSHOT_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    os.link(real, target)

    payload = inspect_external_agent_live_status(root, EVALUATED).to_dict()

    assert payload["findings"][0]["rule_id"] == "status_source_indirection_blocked"


def test_reparse_component_is_blocked(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import agent_runtime.orchestration_external_agent_live_status as live_status

    root = _project(tmp_path, _load("external-agent-status-snapshot.example.json"))
    monkeypatch.setattr(live_status, "_is_reparse", lambda _info: True)

    payload = inspect_external_agent_live_status(root, EVALUATED).to_dict()

    assert payload["findings"][0]["rule_id"] == "status_source_indirection_blocked"


def test_stable_stat_drift_is_blocked(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import agent_runtime.orchestration_external_agent_live_status as live_status

    root = _project(tmp_path, _load("external-agent-status-snapshot.example.json"))
    calls = 0

    def drifting_version(info: os.stat_result) -> tuple[int, int, int]:
        nonlocal calls
        calls += 1
        return info.st_size, info.st_mtime_ns + calls, info.st_ctime_ns

    monkeypatch.setattr(live_status, "_version", drifting_version)

    payload = inspect_external_agent_live_status(root, EVALUATED).to_dict()

    assert payload["findings"][0]["rule_id"] == "status_source_unreadable"


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    [
        (lambda value: value.update(complete=False), "status_snapshot_incomplete"),
        (lambda value: value.update(unexpected=True), "status_source_schema_invalid"),
        (
            lambda value: value["producer"].update(producer_version="drifted"),
            "status_producer_binding_drift",
        ),
        (
            lambda value: value["target"].update(adapter_version="2.0.0"),
            "status_identity_binding_mismatch",
        ),
        (
            lambda value: value.update(observed_at="2026-07-27T08:00:06Z"),
            "status_observation_from_future",
        ),
        (
            lambda value: value["observation"].update(session_state="open"),
            "status_unbound_session_observed",
        ),
    ],
)
def test_snapshot_contract_binding_and_time_failures(
    tmp_path: Path,
    mutation: Any,
    expected_code: str,
) -> None:
    snapshot = _load("external-agent-status-snapshot.example.json")
    mutation(snapshot)
    if expected_code != "status_source_schema_invalid" or snapshot["snapshot_id"].endswith("0" * 64) is False:
        snapshot["snapshot_id"] = _canonical_digest(snapshot, "snapshot_id")
    root = _project(tmp_path, snapshot)

    payload = inspect_external_agent_live_status(root, EVALUATED).to_dict()

    assert payload["findings"][0]["rule_id"] == expected_code



def test_snapshot_content_digest_drift_is_blocked(tmp_path: Path) -> None:
    root = _project(tmp_path, _load("external-agent-status-snapshot.example.json"))
    target = root / FIXED_SNAPSHOT_PATH
    snapshot = json.loads(target.read_text(encoding="utf-8"))
    snapshot["snapshot_id"] = "sha256:" + "0" * 64
    target.write_text(json.dumps(snapshot), encoding="utf-8")

    payload = inspect_external_agent_live_status(root, EVALUATED).to_dict()

    assert payload["findings"][0]["rule_id"] == "status_source_schema_invalid"

def test_expired_snapshot_is_stale_and_never_ready(tmp_path: Path) -> None:
    root = _project(tmp_path, _load("external-agent-status-snapshot.example.json"))

    payload = inspect_external_agent_live_status(root, "2026-07-27T08:00:16Z").to_dict()

    assert payload["status"] == "pass"
    assert payload["observation_status"] == "stale"
    assert payload["findings"][0]["rule_id"] == "status_observation_expired"
    assert payload["evidence"]["readiness_status"] == "stale"
    assert payload["evidence"]["sufficient_for_dispatch"] is False


@pytest.mark.parametrize(
    ("presence", "expected_level"),
    [("missing", "runner_missing"), ("unknown", "runner_presence_unknown")],
)
def test_target_not_observed_is_unavailable_without_active_probe(
    tmp_path: Path,
    presence: str,
    expected_level: str,
) -> None:
    snapshot = _load("external-agent-status-snapshot.example.json")
    snapshot["observation"]["transport_presence"] = presence
    root = _project(tmp_path, snapshot)

    payload = inspect_external_agent_live_status(root, EVALUATED).to_dict()

    assert payload["status"] == "pass"
    assert payload["observation_status"] == "unavailable"
    assert payload["findings"][0]["rule_id"] == "status_target_not_observed"
    assert payload["evidence"]["readiness_level"] == expected_level
    assert payload["gui_projection"]["status"] == "disconnected"


def test_missing_reviewed_binding_is_blocked(tmp_path: Path) -> None:
    root = _project(tmp_path, _load("external-agent-status-snapshot.example.json"))
    (root / "adapters/external-agent-live-status-binding.json").unlink()

    payload = inspect_external_agent_live_status(root, EVALUATED).to_dict()

    assert payload["findings"][0]["rule_id"] == "status_producer_binding_missing"


def test_projection_schema_failure_is_fail_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import agent_runtime.orchestration_external_agent_live_status as live_status

    root = _project(tmp_path, _load("external-agent-status-snapshot.example.json"))
    monkeypatch.setattr(live_status, "_projection", lambda _evidence: {})

    payload = inspect_external_agent_live_status(root, EVALUATED).to_dict()

    assert payload["status"] == "blocked"
    assert payload["findings"][0]["rule_id"] == "status_projection_invalid"


def test_reviewed_contract_schema_drift_fails_closed(tmp_path: Path) -> None:
    snapshot = _load("external-agent-status-snapshot.example.json")
    snapshot["unexpected_raw_output"] = "must-not-be-accepted"
    root = _project(tmp_path, snapshot)
    permissive = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
    }
    (root / "adapters/external-agent-status-snapshot.schema.json").write_text(
        json.dumps(permissive),
        encoding="utf-8",
    )

    payload = inspect_external_agent_live_status(root, EVALUATED).to_dict()

    assert payload["status"] == "blocked"
    assert payload["findings"][0]["rule_id"] == "status_producer_binding_missing"
    assert "must-not-be-accepted" not in json.dumps(payload, ensure_ascii=False)


def test_reader_is_deterministic_and_does_not_modify_project_files(tmp_path: Path) -> None:
    root = _project(tmp_path, _load("external-agent-status-snapshot.example.json"))
    before = {
        path.relative_to(root): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }

    first = inspect_external_agent_live_status(root, EVALUATED).to_dict()
    second = inspect_external_agent_live_status(root, EVALUATED).to_dict()
    after = {
        path.relative_to(root): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }

    assert first == second
    assert after == before
