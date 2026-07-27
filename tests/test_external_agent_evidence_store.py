from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent_runtime.external_agent_evidence_store import (
    EvidenceStoreError,
    finalize_evidence,
    inspect_evidence,
    prepare_evidence,
    validate_host_result,
    write_review_record,
)


def _events() -> list[dict[str, object]]:
    return [
        {"sequence": 1, "event_type": "request_claimed", "occurred_at": "2026-07-27T12:00:00Z"},
        {"sequence": 2, "event_type": "host_turn_dispatched", "occurred_at": "2026-07-27T12:00:01Z"},
        {"sequence": 3, "event_type": "host_turn_started", "occurred_at": "2026-07-27T12:00:02Z"},
        {"sequence": 4, "event_type": "host_turn_completed", "occurred_at": "2026-07-27T12:00:03Z"},
    ]


def _prepare(root: Path, *, output: str = "阶段88真实产物。", review_required: bool = True) -> dict[str, object]:
    return prepare_evidence(
        root,
        attempt_id="attempt-stage88-001",
        task_id="task-stage88",
        request_id="request-stage88-001",
        collaboration_file="adapters/stage88-plan.json",
        collaboration_plan_id="sha256:" + "1" * 64,
        work_item_id="implement",
        target_profile="omp-local",
        plan_hash="sha256:" + "2" * 64,
        approval_binding_id="sha256:" + "3" * 64,
        completed_at="2026-07-27T12:00:03Z",
        host_events=_events(),
        output=output,
        expected_artifact_types=["test_result"],
        review_required=review_required,
        review_gate_id="review-implementation" if review_required else None,
    )


def test_prepare_finalize_and_inspect_text_evidence(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()

    pending = _prepare(root)
    assert pending["status"] == "prepared"
    assert pending["artifact"]["media_type"] == "text/plain"

    finalized = finalize_evidence(root, "attempt-stage88-001")
    assert finalized["status"] == "pass"
    assert finalized["review"]["status"] == "pending"
    artifact_path = root / finalized["artifact"]["relative_path"]
    assert artifact_path.read_text(encoding="utf-8") == "阶段88真实产物。"

    restored = inspect_evidence(root, "attempt-stage88-001")
    assert restored == finalized
    assert list((root / ".runtime/external-agent-evidence/v1/pending").glob("*.json")) == []


def test_json_output_is_preserved_as_json_artifact(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    output = '{"status":"ok","message":"阶段88"}'

    _prepare(root, output=output, review_required=False)
    result = finalize_evidence(root, "attempt-stage88-001")

    assert result["artifact"]["media_type"] == "application/json"
    assert result["artifact"]["relative_path"].endswith(".json")
    assert (root / result["artifact"]["relative_path"]).read_text(encoding="utf-8") == output
    assert result["review"]["status"] == "not_required"


def test_pending_can_be_recovered_without_agent_rerun(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    _prepare(root)

    before = inspect_evidence(root, "attempt-stage88-001")
    assert before["status"] == "recovery_pending"

    recovered = finalize_evidence(root, "attempt-stage88-001")
    assert recovered["status"] == "pass"
    assert inspect_evidence(root, "attempt-stage88-001")["status"] == "pass"


def test_attempt_evidence_is_immutable(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    _prepare(root)
    finalize_evidence(root, "attempt-stage88-001")

    with pytest.raises(EvidenceStoreError) as exc:
        _prepare(root, output="不同内容")

    assert exc.value.code == "external-agent-evidence-already-finalized"


def test_review_record_is_created_once_and_bound_to_manifest(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    _prepare(root)
    evidence = finalize_evidence(root, "attempt-stage88-001")
    record = {
        "version": 1,
        "contract": "external-agent-human-review/v1",
        "review_id": "review-stage88-001",
        "attempt_id": "attempt-stage88-001",
        "gate_id": "review-implementation",
        "decision": "approve",
        "comment": "结果符合要求。",
        "comment_digest": "",
        "artifact_id": evidence["artifact"]["artifact_id"],
        "artifact_digest": evidence["artifact"]["content_hash"],
        "manifest_digest": evidence["manifest_digest"],
        "collaboration_plan_id": "sha256:" + "1" * 64,
        "approval_binding_id": "sha256:" + "4" * 64,
        "committed_at": "2026-07-27T12:05:00Z",
    }

    written = write_review_record(root, record)
    assert written["decision"] == "approve"
    assert inspect_evidence(root, "attempt-stage88-001")["review"]["status"] == "approved"

    with pytest.raises(EvidenceStoreError) as exc:
        write_review_record(root, {**record, "decision": "request_changes"})
    assert exc.value.code == "external-agent-review-already-recorded"


def test_tampered_artifact_is_detected(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    _prepare(root)
    evidence = finalize_evidence(root, "attempt-stage88-001")
    artifact_path = root / evidence["artifact"]["relative_path"]
    artifact_path.write_text("被篡改的产物", encoding="utf-8")

    with pytest.raises(EvidenceStoreError) as exc:
        inspect_evidence(root, "attempt-stage88-001")
    assert exc.value.code == "external-agent-evidence-artifact-drift"


def test_invalid_host_event_timestamp_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    output = "结果"
    import hashlib
    encoded = output.encode("utf-8")
    result = {
        "version": 2,
        "contract": "external-agent-single-work-item-result/v2",
        "request_id": "request-stage88-001",
        "target_profile": "omp-local",
        "status": "succeeded",
        "completed_at": "2026-07-27T12:00:03Z",
        "output": output,
        "output_bytes": len(encoded),
        "output_digest": "sha256:" + hashlib.sha256(encoded).hexdigest(),
        "events": [
            {"sequence": 1, "event_type": "request_claimed", "occurred_at": "2026-99-99T99:99:99Z"},
            {"sequence": 2, "event_type": "host_turn_dispatched", "occurred_at": "2026-99-99T99:99:99Z"},
            {"sequence": 3, "event_type": "host_turn_started", "occurred_at": "2026-99-99T99:99:99Z"},
            {"sequence": 4, "event_type": "host_turn_completed", "occurred_at": "2026-99-99T99:99:99Z"},
        ],
        "artifacts": [],
    }

    with pytest.raises(EvidenceStoreError) as exc:
        validate_host_result(root, result, result_max_bytes=8192)
    assert exc.value.code == "external-agent-result-event-time-invalid"

def test_immutable_write_os_error_is_fail_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "project"
    root.mkdir()

    def fail_link(_source: object, _target: object) -> None:
        raise OSError("simulated storage failure")

    monkeypatch.setattr("agent_runtime.external_agent_evidence_store.os.link", fail_link)

    with pytest.raises(EvidenceStoreError) as exc:
        _prepare(root)

    assert exc.value.code == "external-agent-evidence-write-io-failed"
    evidence_root = root / ".runtime/external-agent-evidence/v1"
    assert list(evidence_root.rglob("*.tmp-*")) == []
    assert list((evidence_root / "pending").glob("*.json")) == []

def test_evidence_read_os_error_is_fail_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "project"
    root.mkdir()
    _prepare(root)
    evidence = finalize_evidence(root, "attempt-stage88-001")
    artifact_path = (root / evidence["artifact"]["relative_path"]).resolve()
    original_read_bytes = Path.read_bytes

    def fail_artifact_read(path: Path) -> bytes:
        if path.resolve() == artifact_path:
            raise OSError("simulated read failure")
        return original_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", fail_artifact_read)

    with pytest.raises(EvidenceStoreError) as exc:
        inspect_evidence(root, "attempt-stage88-001")

    assert exc.value.code == "external-agent-evidence-read-io-failed"


def test_evidence_directory_os_error_is_fail_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "project"
    root.mkdir()
    original_mkdir = Path.mkdir

    def fail_runtime_mkdir(path: Path, *args: object, **kwargs: object) -> None:
        if path.name == ".runtime":
            raise OSError("simulated directory failure")
        original_mkdir(path, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", fail_runtime_mkdir)

    with pytest.raises(EvidenceStoreError) as exc:
        _prepare(root)

    assert exc.value.code == "external-agent-evidence-write-io-failed"

def test_tampered_pending_output_is_rejected_during_inspection(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    _prepare(root)
    pending_path = next((root / ".runtime/external-agent-evidence/v1/pending").glob("*.json"))
    pending = json.loads(pending_path.read_text(encoding="utf-8"))
    pending["output"] = "被篡改的待恢复产物"
    pending_path.write_text(json.dumps(pending, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(EvidenceStoreError) as exc:
        inspect_evidence(root, "attempt-stage88-001")

    assert exc.value.code == "external-agent-evidence-pending-binding-invalid"
