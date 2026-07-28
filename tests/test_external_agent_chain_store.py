from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _digest(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _root(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    root.mkdir()
    shutil.copytree(ROOT / "adapters", root / "adapters")
    return root


def _intent() -> dict[str, object]:
    return {
        "version": 1,
        "contract": "external-agent-chain-intent/v1",
        "chain_id": "chain-stage89-001",
        "task_id": "task-stage89",
        "collaboration_file": "adapters/stage89-plan.json",
        "collaboration_plan_id": "sha256:" + "1" * 64,
        "goal": "为给定结果生成一个受限的执行计划。",
        "goal_digest": _digest("为给定结果生成一个受限的执行计划。"),
        "roles": {
            "planner": {"profile": "pi-local", "work_item_id": "plan"},
            "executor": {"profile": "omp-local", "work_item_id": "execute"},
            "reviewer": {"profile": "pi-local", "work_item_id": "review"},
        },
        "review_gate_id": "review-execute",
        "created_at": "2026-07-28T12:00:00Z",
    }


def _candidate() -> dict[str, object]:
    return {
        "version": 1,
        "contract": "external-agent-chain-planner-candidate/v1",
        "chain_id": "chain-stage89-001",
        "goal_digest": _digest("为给定结果生成一个受限的执行计划。"),
        "summary": "生成一个有界结果。",
        "execution_instruction": "只输出一个简短、结构化的结论。",
        "success_criteria": ["输出合法 JSON。"],
        "review_focus": ["检查输出是否符合约束。"],
    }


def _advice(candidate_digest: str) -> dict[str, object]:
    return {
        "version": 1,
        "contract": "external-agent-chain-review-advice/v1",
        "chain_id": "chain-stage89-001",
        "planner_candidate_digest": candidate_digest,
        "execution_attempt_id": "attempt-stage89-execute-001",
        "execution_manifest_digest": "sha256:" + "3" * 64,
        "execution_artifact_digest": "sha256:" + "4" * 64,
        "recommendation": "approve",
        "summary": "结果满足约束。",
        "findings": [],
    }


def test_chain_store_persists_immutable_handoff_records_and_derives_state(tmp_path: Path) -> None:
    from agent_runtime.external_agent_chain_store import (
        create_chain_intent,
        inspect_external_agent_chain,
        write_execution_receipt,
        write_planner_candidate,
        write_review_advice,
    )

    root = _root(tmp_path)
    intent = create_chain_intent(root, _intent())
    assert intent["chain_id"] == "chain-stage89-001"

    created = inspect_external_agent_chain(root, "chain-stage89-001")
    assert created["status"] == "awaiting_planner_confirmation"

    candidate = write_planner_candidate(
        root,
        "chain-stage89-001",
        _candidate(),
        source_attempt_id="attempt-stage89-plan-001",
        source_manifest_digest="sha256:" + "5" * 64,
        source_artifact_digest="sha256:" + "6" * 64,
    )
    assert candidate["candidate_digest"].startswith("sha256:")

    awaiting_executor = inspect_external_agent_chain(root, "chain-stage89-001")
    assert awaiting_executor["status"] == "awaiting_executor_confirmation"

    write_execution_receipt(
        root, "chain-stage89-001",
        attempt_id="attempt-stage89-execute-001",
        manifest_digest="sha256:" + "3" * 64,
        artifact_digest="sha256:" + "4" * 64,
    )
    write_review_advice(root, "chain-stage89-001", _advice(candidate["candidate_digest"]))
    awaiting_final = inspect_external_agent_chain(root, "chain-stage89-001")
    assert awaiting_final["status"] == "awaiting_final_human_decision"


def test_chain_store_rejects_duplicate_or_drifting_role_records(tmp_path: Path) -> None:
    from agent_runtime.external_agent_chain_store import (
        ChainStoreError,
        create_chain_intent,
        write_planner_candidate,
    )

    root = _root(tmp_path)
    create_chain_intent(root, _intent())
    write_planner_candidate(
        root,
        "chain-stage89-001",
        _candidate(),
        source_attempt_id="attempt-stage89-plan-001",
        source_manifest_digest="sha256:" + "5" * 64,
        source_artifact_digest="sha256:" + "6" * 64,
    )

    drifted = _candidate()
    drifted["goal_digest"] = "sha256:" + "9" * 64
    with pytest.raises(ChainStoreError, match="already-recorded"):
        write_planner_candidate(
            root,
            "chain-stage89-001",
            drifted,
            source_attempt_id="attempt-stage89-plan-002",
            source_manifest_digest="sha256:" + "5" * 64,
            source_artifact_digest="sha256:" + "6" * 64,
        )


def test_chain_store_binds_executor_receipt_and_human_completion(tmp_path: Path) -> None:
    from agent_runtime.external_agent_chain_store import (
        create_chain_intent,
        inspect_external_agent_chain,
        write_chain_completion,
        write_execution_receipt,
        write_planner_candidate,
        write_review_advice,
    )

    root = _root(tmp_path)
    create_chain_intent(root, _intent())
    candidate = write_planner_candidate(
        root, "chain-stage89-001", _candidate(),
        source_attempt_id="attempt-stage89-plan-001",
        source_manifest_digest="sha256:" + "5" * 64,
        source_artifact_digest="sha256:" + "6" * 64,
    )
    write_execution_receipt(
        root, "chain-stage89-001",
        attempt_id="attempt-stage89-execute-001",
        manifest_digest="sha256:" + "3" * 64,
        artifact_digest="sha256:" + "4" * 64,
    )
    assert inspect_external_agent_chain(root, "chain-stage89-001")["status"] == "awaiting_reviewer_confirmation"

    advice = write_review_advice(root, "chain-stage89-001", _advice(candidate["candidate_digest"]))
    completion = write_chain_completion(
        root, "chain-stage89-001",
        human_review={
            "review_id": "review-stage89-001",
            "decision": "approve",
            "comment_digest": "sha256:" + "7" * 64,
            "manifest_digest": "sha256:" + "3" * 64,
            "artifact_digest": "sha256:" + "4" * 64,
        },
        advice_digest=advice["advice_digest"],
        committed_at="2026-07-28T12:10:00Z",
    )

    assert completion["decision"] == "approve"
    finished = inspect_external_agent_chain(root, "chain-stage89-001")
    assert finished["status"] == "approved"
    assert finished["completion"]["review_id"] == "review-stage89-001"


def test_chain_store_prepares_one_finalization_pending_record(tmp_path: Path) -> None:
    from agent_runtime.external_agent_chain_store import (
        create_chain_intent,
        inspect_external_agent_chain,
        prepare_chain_completion,
        write_execution_receipt,
        write_planner_candidate,
        write_review_advice,
    )

    root = _root(tmp_path)
    create_chain_intent(root, _intent())
    candidate = write_planner_candidate(
        root,
        "chain-stage89-001",
        _candidate(),
        source_attempt_id="attempt-stage89-plan-001",
        source_manifest_digest="sha256:" + "5" * 64,
        source_artifact_digest="sha256:" + "6" * 64,
    )
    write_execution_receipt(
        root, "chain-stage89-001",
        attempt_id="attempt-stage89-execute-001",
        manifest_digest="sha256:" + "3" * 64,
        artifact_digest="sha256:" + "4" * 64,
    )
    write_review_advice(root, "chain-stage89-001", _advice(candidate["candidate_digest"]))

    pending = prepare_chain_completion(
        root,
        "chain-stage89-001",
        decision="approve",
        comment_digest="sha256:" + "7" * 64,
        advice_digest=inspect_external_agent_chain(root, "chain-stage89-001")["review_advice"]["advice_digest"],
        committed_at="2026-07-28T12:03:00Z",
    )

    assert pending["decision"] == "approve"
    assert inspect_external_agent_chain(root, "chain-stage89-001")["status"] == "finalization_pending"


def test_chain_store_stops_immutably_and_rejects_later_handoffs(tmp_path: Path) -> None:
    from agent_runtime.external_agent_chain_store import (
        ChainStoreError,
        create_chain_intent,
        inspect_external_agent_chain,
        write_chain_stop,
        write_planner_candidate,
    )

    root = _root(tmp_path)
    create_chain_intent(root, _intent())
    stop = write_chain_stop(
        root, "chain-stage89-001", role="planner",
        failure_code="external-agent-chain-planner-output-json-invalid",
    )

    assert stop["role"] == "planner"
    assert inspect_external_agent_chain(root, "chain-stage89-001")["status"] == "stopped"
    with pytest.raises(ChainStoreError, match="已停止"):
        write_planner_candidate(
            root, "chain-stage89-001", _candidate(),
            source_attempt_id="attempt-stage89-plan-001",
            source_manifest_digest="sha256:" + "5" * 64,
            source_artifact_digest="sha256:" + "6" * 64,
        )

def test_chain_store_lists_bounded_safe_summaries_in_stable_order(tmp_path: Path) -> None:
    from agent_runtime.external_agent_chain_store import (
        create_chain_intent,
        list_external_agent_chains,
        write_chain_stop,
    )

    root = _root(tmp_path)
    later = _intent()
    later["chain_id"] = "chain-stage90-002"
    earlier = _intent()
    earlier["chain_id"] = "chain-stage90-001"
    create_chain_intent(root, later)
    create_chain_intent(root, earlier)
    write_chain_stop(
        root,
        "chain-stage90-002",
        role="planner",
        failure_code="external-agent-chain-planner-output-json-invalid",
    )

    chains = list_external_agent_chains(root, limit=10)

    assert chains == [
        {
            "chain_id": "chain-stage90-001",
            "status": "awaiting_planner_confirmation",
            "task_id": "task-stage89",
            "roles": {
                "planner": "pi-local",
                "executor": "omp-local",
                "reviewer": "pi-local",
            },
            "created_at": "2026-07-28T12:00:00Z",
        },
        {
            "chain_id": "chain-stage90-002",
            "status": "stopped",
            "task_id": "task-stage89",
            "roles": {
                "planner": "pi-local",
                "executor": "omp-local",
                "reviewer": "pi-local",
            },
            "created_at": "2026-07-28T12:00:00Z",
        },
    ]
    assert all("goal" not in item for item in chains)
    assert list_external_agent_chains(root, limit=1) == chains[:1]
