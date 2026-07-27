"""Tests for CLI command entry points."""

import json
from pathlib import Path

import pytest

import agent_runtime.cli as cli
from agent_runtime.cli import main
from agent_runtime.execution_trust import TrustBindingResult, TrustInspectionResult
from agent_runtime.pi_runtime_binding import PiRuntimeBindingResult


ROOT = Path(__file__).resolve().parents[1]


def test_cli_doctor(capsys):
    code = main(["--root", str(ROOT), "doctor"])
    captured = capsys.readouterr()
    assert code == 0
    assert "PASS" in captured.out or '"status": "pass"' in captured.out


def test_cli_unexpected_exception_is_fixed_and_value_safe(
    capsys, monkeypatch: pytest.MonkeyPatch
) -> None:
    private_path = "C:" + "/private/runtime/credentials.json"
    secret = "test_" + "secret_material"

    def fail(*_args, **_kwargs):
        raise RuntimeError(f"failure at {private_path} with {secret}")

    monkeypatch.setattr(cli, "run_doctor", fail)

    first_code = main(["--root", str(ROOT), "doctor", "--json"])
    first = capsys.readouterr().out
    second_code = main(["--root", str(ROOT), "doctor", "--json"])
    second = capsys.readouterr().out

    assert first_code == second_code == 1
    assert first == second
    payload = json.loads(first)
    assert payload["status"] == "error"
    assert payload["next_action"] == "Unexpected internal error."
    assert private_path not in first
    assert secret not in first


def test_cli_file_not_found_exception_is_fixed_and_value_safe(
    capsys, monkeypatch: pytest.MonkeyPatch
) -> None:
    private_path = "C:" + "/private/runtime/missing.json"

    def fail(*_args, **_kwargs):
        raise FileNotFoundError(2, "missing", private_path)

    monkeypatch.setattr(cli, "run_doctor", fail)

    code = main(["--root", str(ROOT), "doctor", "--json"])
    output = capsys.readouterr().out

    assert code == 1
    assert json.loads(output)["next_action"] == "Required file was not found."
    assert private_path not in output


def test_cli_execution_trust_inspect_json_uses_fixed_public_api(
    capsys, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[Path] = []

    def inspect(root: Path) -> TrustInspectionResult:
        calls.append(root)
        return TrustInspectionResult(
            status="pass",
            state="missing",
            checks={"binding_present": False},
            lease_state="available",
            executable_identity="sha256:" + "a" * 64,
            path_identity="sha256:" + "b" * 64,
        )

    monkeypatch.setattr(cli, "inspect_execution_trust", inspect)
    code = main(
        [
            "--root",
            str(ROOT),
            "orchestration",
            "execution",
            "trust",
            "inspect",
            "--json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert calls == [ROOT]
    assert payload["schema_version"] == "control-plane/execution-trust-inspection/v1"
    assert payload["state"] == "missing"


def test_cli_pi_binding_inspect_uses_fixed_public_api(
    capsys, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[object] = []

    def inspect() -> PiRuntimeBindingResult:
        calls.append("inspect")
        return PiRuntimeBindingResult(status="blocked")

    monkeypatch.setattr(cli, "inspect_pi_runtime_binding", inspect)
    code = main(["orchestration", "execution", "pi-binding", "inspect", "--json"])

    assert code == 2
    assert calls == ["inspect"]
    assert json.loads(capsys.readouterr().out)["status"] == "blocked"


def test_cli_pi_binding_bind_forwards_only_reviewed_paths(
    capsys, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, object] = {}

    def bind(**kwargs: object) -> PiRuntimeBindingResult:
        captured.update(kwargs)
        return PiRuntimeBindingResult(status="pass")

    monkeypatch.setattr(cli, "create_pi_runtime_binding", bind)
    code = main([
        "orchestration", "execution", "pi-binding", "bind",
        "--node-path", "C:" + "/reviewed/node.exe",
        "--cli-entry", "C:" + "/reviewed/cli.js",
        "--module-root", "C:" + "/reviewed/package",
        "--replace", "--expected-binding-id", "sha256:" + "a" * 64, "--commit", "--json",
    ])

    assert code == 0
    assert captured["commit"] is True
    assert captured["replace"] is True
    assert captured["expected_binding_id"] == "sha256:" + "a" * 64
    assert list(captured["module_roots"]) == [Path("C:" + "/reviewed/package")]
    assert json.loads(capsys.readouterr().out)["status"] == "pass"


@pytest.mark.parametrize(
    "override",
    ["--path", "--binding-path", "--executable", "--path-value", "--actor"],
)
def test_cli_execution_trust_inspect_rejects_overrides(override: str) -> None:
    with pytest.raises(SystemExit) as exc:
        main(
            [
                "--root",
                str(ROOT),
                "orchestration",
                "execution",
                "trust",
                "inspect",
                override,
                "unsafe-value",
            ]
        )

    assert exc.value.code == 2


def test_cli_execution_trust_bind_forwards_rotation_review_identities(
    capsys, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, object] = {}

    def bind(root: Path, **kwargs: object) -> TrustBindingResult:
        captured.update(kwargs)
        return TrustBindingResult(status="pass")

    monkeypatch.setattr(cli, "create_execution_trust_binding", bind)
    code = main(
        [
            "--root",
            str(ROOT),
            "orchestration",
            "execution",
            "trust",
            "bind",
            "--expected-sha256",
            "a" * 64,
            "--expected-publisher-thumbprint",
            "B" * 40,
            "--expected-binding-id",
            "sha256:" + "c" * 64,
            "--expected-executable-identity",
            "sha256:" + "d" * 64,
            "--expected-path-identity",
            "sha256:" + "e" * 64,
            "--replace",
            "--commit",
        ]
    )
    capsys.readouterr()

    assert code == 0
    assert captured["expected_binding_id"] == "sha256:" + "c" * 64
    assert captured["expected_executable_identity"] == "sha256:" + "d" * 64
    assert captured["expected_path_identity"] == "sha256:" + "e" * 64


def test_cli_check_text_pass(capsys):
    code = main(["--root", str(ROOT), "check", "text", "--text", "hello"])
    captured = capsys.readouterr()
    assert code == 0
    assert "PASS" in captured.out


def test_cli_check_text_blocked(capsys):
    token = "ghp_" + "X" * 36
    code = main(["--root", str(ROOT), "check", "text", "--text", token])
    captured = capsys.readouterr()
    assert code == 2
    assert "BLOCKED" in captured.out
    assert "X" * 36 not in captured.out


def test_cli_check_text_json(capsys):
    code = main(["--root", str(ROOT), "check", "text", "--text", "hello", "--json"])
    captured = capsys.readouterr()
    assert code == 0
    assert '"status": "pass"' in captured.out


def test_cli_check_path_blocked(capsys):
    code = main(["--root", str(ROOT), "check", "path", "./received/raw.png", "--write"])
    captured = capsys.readouterr()
    assert code == 2
    assert "BLOCKED" in captured.out


def test_cli_check_action_needs_approval(capsys):
    code = main([
        "--root", str(ROOT),
        "check", "action",
        "--adapter", "github-cli",
        "--operation", "git_push",
        "--target", "origin/main",
    ])
    captured = capsys.readouterr()
    assert code == 3
    assert "NEEDS_APPROVAL" in captured.out
    assert "github-cli-approval" in captured.out
    assert "github-publish-preflight" in captured.out
    assert "secret_scan" in captured.out


def test_cli_check_action_completion_requires_evidence(capsys):
    code = main([
        "--root", str(ROOT),
        "check", "action",
        "--adapter", "shell-local",
        "--operation", "mark_finished",
        "--target", "task-20260702-001",
    ])
    captured = capsys.readouterr()
    assert code == 4
    assert "NEEDS_INPUT" in captured.out
    assert "completion-evidence-required" in captured.out
    assert "test_output" in captured.out


def test_cli_check_action_policy_profile_limits_rules(capsys):
    code = main([
        "--root", str(ROOT),
        "--policy-profile", "s-black",
        "check", "action",
        "--adapter", "shell-local",
        "--operation", "mark_finished",
        "--target", "task-20260702-001",
    ])
    captured = capsys.readouterr()
    assert code == 4
    assert "completion-evidence-required" in captured.out
    assert "memory-distillation-evidence-required" not in captured.out
    assert "media-artifact-required" not in captured.out


def test_cli_agents_list(capsys):
    code = main(["--root", str(ROOT), "agents", "--capability", "planning"])
    captured = capsys.readouterr()
    assert code == 0
    assert "orchestrator" in captured.out


def test_cli_adapters_list(capsys):
    code = main(["--root", str(ROOT), "adapters", "--kind", "github"])
    captured = capsys.readouterr()
    assert code == 0
    assert "github-cli" in captured.out


def test_cli_policies_list(capsys):
    code = main(["--root", str(ROOT), "policies"])
    captured = capsys.readouterr()
    assert code == 0
    assert "s-black.sample.policy.json" in captured.out


def test_cli_policies_list_profile(capsys):
    code = main(["--root", str(ROOT), "--policy-profile", "s-black", "policies"])
    captured = capsys.readouterr()
    assert code == 0
    assert "s-black.sample.policy.json" in captured.out
    assert "wangcai.sample.policy.json" not in captured.out
    assert "dabai.sample.policy.json" not in captured.out


def test_cli_task_status(capsys):
    code = main(["--root", str(ROOT), "task", "status", "task-20260703-001"])
    captured = capsys.readouterr()
    assert code == 0
    assert "Task: task-20260703-001" in captured.out
    assert "Status: finished" in captured.out
    assert "agent_runtime/tasks.py" in captured.out


def test_cli_task_status_json(capsys):
    code = main(["--root", str(ROOT), "task", "status", "task-20260703-001", "--json"])
    captured = capsys.readouterr()
    assert code == 0
    assert '"id": "task-20260703-001"' in captured.out
    assert '"status": "finished"' in captured.out


def test_cli_task_status_missing(capsys):
    code = main(["--root", str(ROOT), "task", "status", "missing-task"])
    captured = capsys.readouterr()
    assert code == 4
    assert "NEEDS_INPUT" in captured.out
    assert "missing-task" in captured.out


def test_cli_task_events(capsys):
    code = main(["--root", str(ROOT), "task", "events", "task-20260703-001"])
    captured = capsys.readouterr()
    assert code == 0
    assert "created" in captured.out
    assert "finished" in captured.out
    assert "planned -> running" in captured.out


def test_cli_task_events_missing(capsys):
    code = main(["--root", str(ROOT), "task", "events", "missing-task"])
    captured = capsys.readouterr()
    assert code == 4
    assert "NEEDS_INPUT" in captured.out


def test_cli_external_agent_status_inspect_forwards_only_fixed_reader_inputs(
    capsys,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[Path, str, int | None]] = []

    class Result:
        def to_dict(self) -> dict[str, object]:
            return {
                "status": "pass",
                "schema_version": "control-plane/external-agent-live-status-inspection/v1",
                "observation_status": "observed",
            }

        def exit_code(self) -> int:
            return 0

    def inspect(
        root: Path,
        evaluated_at: str,
        *,
        expected_after_generation: int | None = None,
    ) -> Result:
        calls.append((root, evaluated_at, expected_after_generation))
        return Result()

    monkeypatch.setattr(cli, "inspect_external_agent_live_status", inspect)
    code = main(
        [
            "--root",
            str(ROOT),
            "orchestration",
            "external-agent",
            "status",
            "inspect",
            "--evaluated-at",
            "2026-07-27T08:00:05Z",
            "--expected-after-generation",
            "7",
            "--json",
        ]
    )

    assert code == 0
    assert calls == [(ROOT, "2026-07-27T08:00:05Z", 7)]
    assert json.loads(capsys.readouterr().out)["observation_status"] == "observed"


@pytest.mark.parametrize("override", ["--snapshot-file", "--ttl-seconds", "--adapter-id"])
def test_cli_external_agent_status_inspect_rejects_boundary_overrides(override: str) -> None:
    with pytest.raises(SystemExit) as exc:
        main(
            [
                "orchestration",
                "external-agent",
                "status",
                "inspect",
                "--evaluated-at",
                "2026-07-27T08:00:05Z",
                override,
                "unsafe",
            ]
        )
    assert exc.value.code == 2


def test_cli_external_agent_status_human_output_is_chinese_first(
    capsys,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Result:
        def to_dict(self) -> dict[str, object]:
            return {
                "status": "pass",
                "observation_status": "unavailable",
                "gui_projection": {
                    "status_label_zh": "目标 Runner 未观察到",
                    "readiness": {"status": "unknown"},
                },
                "findings": [],
            }

        def exit_code(self) -> int:
            return 0

    monkeypatch.setattr(cli, "inspect_external_agent_live_status", lambda *_args, **_kwargs: Result())

    code = main(
        [
            "orchestration",
            "external-agent",
            "status",
            "inspect",
            "--evaluated-at",
            "2026-07-27T08:00:05Z",
        ]
    )
    output = capsys.readouterr().out

    assert code == 0
    assert "外部 Agent 状态" in output
    assert "目标 Runner 未观察到" in output
    assert "就绪状态=unknown" in output


def test_cli_external_agent_status_rejects_negative_previous_generation() -> None:
    with pytest.raises(SystemExit) as exc:
        main(
            [
                "orchestration",
                "external-agent",
                "status",
                "inspect",
                "--evaluated-at",
                "2026-07-27T08:00:05Z",
                "--expected-after-generation",
                "-1",
            ]
        )
    assert exc.value.code == 2
