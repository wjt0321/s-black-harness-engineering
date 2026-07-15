"""Tests for the Stage 20 Codex Desktop read-only adapter."""

from __future__ import annotations

import copy
import importlib
import io
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

from agent_runtime.orchestration_control_panel import build_control_panel_handoff

ROOT = Path(__file__).resolve().parents[1]
ENVELOPE = "adapters/execution-envelope.examples.json"


def _adapter():
    return importlib.import_module("tools.codex_desktop_read_only_adapter")


def _valid_handoff() -> dict[str, object]:
    return build_control_panel_handoff(ROOT, envelope_file=ENVELOPE).to_dict()


def _rehash_handoff(payload: dict[str, object]) -> None:
    import hashlib

    without_id = {key: value for key, value in payload.items() if key != "handoff_id"}
    canonical = json.dumps(
        without_id,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    payload["handoff_id"] = f"sha256:{hashlib.sha256(canonical).hexdigest()}"


def _validation_payload(handoff: dict[str, object]) -> dict[str, object]:
    consumer = importlib.import_module("tools.control_panel_handoff_consumer")
    return consumer.validate_handoff_document(handoff).to_dict()


class FakeRunner:
    def __init__(self, handoff: dict[str, object]) -> None:
        self.handoff = handoff
        self.calls: list[dict[str, object]] = []

    def __call__(
        self,
        argv: list[str],
        *,
        cwd: Path,
        input_bytes: bytes | None,
        timeout_seconds: float,
    ) -> SimpleNamespace:
        self.calls.append(
            {
                "argv": list(argv),
                "cwd": cwd,
                "input_bytes": input_bytes,
                "timeout_seconds": timeout_seconds,
            }
        )
        if "control_panel_handoff_consumer.py" in " ".join(argv):
            assert input_bytes is not None
            return SimpleNamespace(
                returncode=0,
                stdout=json.dumps(
                    _validation_payload(self.handoff),
                    ensure_ascii=False,
                ).encode("utf-8"),
                stderr=b"",
            )
        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps(self.handoff, ensure_ascii=False).encode("utf-8"),
            stderr=b"",
        )


def test_adapter_minimal_environment_disables_python_bytecode_writes() -> None:
    adapter = _adapter()

    environment = adapter._minimal_environment()

    assert environment["PYTHONDONTWRITEBYTECODE"] == "1"


def test_adapter_accepts_valid_one_shot_pipeline_without_executing_descriptor_argv() -> None:
    adapter = _adapter()
    handoff = _valid_handoff()
    sentinel = "DO_NOT_EXECUTE_SENTINEL"
    handoff["snapshot"]["argv"] = [sentinel]
    handoff["render"]["argv"] = [sentinel]
    _rehash_handoff(handoff)
    runner = FakeRunner(handoff)

    result = adapter.run_read_only_adapter(ROOT, runner=runner)
    payload = result.to_dict()

    assert result.status == "ready"
    assert result.exit_code() == 0
    assert payload["schema_version"] == (
        "control-plane/codex-desktop-read-only-adapter/v1"
    )
    assert payload["adapter"] == "codex-desktop-read-only-adapter/v1"
    assert payload["consumer"]["status"] == "pass"
    assert payload["lifecycle"]["state"] == "closed"
    assert payload["guarantees"] == {
        "one_shot": True,
        "read_only": True,
        "writes_files": False,
        "accesses_network": False,
        "starts_service": False,
        "reads_representations": False,
        "executes_descriptor_argv": False,
        "auto_retries": False,
    }
    assert sentinel not in json.dumps(payload, ensure_ascii=False)
    assert len(runner.calls) == 2
    assert runner.calls[0]["argv"] == [
        adapter.sys.executable,
        "-m",
        "agent_runtime.cli",
        "orchestration",
        "control-panel",
        "handoff",
        "--json",
    ]
    assert Path(runner.calls[1]["argv"][-1]).name == (
        "control_panel_handoff_consumer.py"
    )
    assert runner.calls[0]["cwd"] == ROOT.resolve()
    assert runner.calls[1]["cwd"] == ROOT.resolve()


def test_adapter_result_is_deterministic_and_does_not_echo_absolute_root() -> None:
    adapter = _adapter()
    handoff = _valid_handoff()
    first_runner = FakeRunner(copy.deepcopy(handoff))
    second_runner = FakeRunner(copy.deepcopy(handoff))

    first = adapter.run_read_only_adapter(ROOT, runner=first_runner).to_dict()
    second = adapter.run_read_only_adapter(ROOT, runner=second_runner).to_dict()

    assert first == second
    assert first["source"] == {"project_root": "project_root"}
    assert str(ROOT.resolve()) not in json.dumps(first, ensure_ascii=False)


def test_adapter_maps_consumer_blocked_to_blocked_without_retry() -> None:
    adapter = _adapter()
    handoff = _valid_handoff()
    handoff["status"] = "blocked"
    _rehash_handoff(handoff)
    consumer = importlib.import_module("tools.control_panel_handoff_consumer")
    validation = consumer.validate_handoff_document(handoff).to_dict()

    calls: list[dict[str, object]] = []

    def runner(
        argv: list[str],
        *,
        cwd: Path,
        input_bytes: bytes | None,
        timeout_seconds: float,
    ) -> SimpleNamespace:
        calls.append({"argv": argv, "input_bytes": input_bytes})
        if "control_panel_handoff_consumer.py" in " ".join(argv):
            return SimpleNamespace(
                returncode=2,
                stdout=json.dumps(validation).encode("utf-8"),
                stderr=b"",
            )
        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps(handoff).encode("utf-8"),
            stderr=b"",
        )

    result = adapter.run_read_only_adapter(ROOT, runner=runner)

    assert result.status == "blocked"
    assert result.exit_code() == 2
    assert result.to_dict()["next_action"]["code"] == "reject_handoff"
    assert len(calls) == 2


def test_adapter_rejects_malformed_consumer_result_without_echoing_input() -> None:
    adapter = _adapter()
    marker = "MALFORMED_CONSUMER_SENTINEL"

    def runner(
        argv: list[str],
        *,
        cwd: Path,
        input_bytes: bytes | None,
        timeout_seconds: float,
    ) -> SimpleNamespace:
        if "control_panel_handoff_consumer.py" in " ".join(argv):
            return SimpleNamespace(
                returncode=0,
                stdout=("not-json-" + marker).encode("utf-8"),
                stderr=b"",
            )
        handoff = _valid_handoff()
        handoff["snapshot"]["argv"] = [marker]
        handoff["render"]["argv"] = [marker]
        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps(handoff).encode("utf-8"),
            stderr=b"",
        )

    result = adapter.run_read_only_adapter(ROOT, runner=runner)
    serialized = json.dumps(result.to_dict(), ensure_ascii=False)

    assert result.status == "error"
    assert result.exit_code() == 1
    assert marker not in serialized
    assert "consumer-protocol-invalid-json" in {
        finding["rule_id"] for finding in result.to_dict()["findings"]
    }


def test_adapter_rejects_non_project_root_without_spawning_process(tmp_path: Path) -> None:
    adapter = _adapter()
    calls: list[object] = []

    def runner(*args: object, **kwargs: object) -> SimpleNamespace:
        calls.append((args, kwargs))
        raise AssertionError("runner must not be called")

    result = adapter.run_read_only_adapter(tmp_path, runner=runner)

    assert result.status == "error"
    assert result.exit_code() == 1
    assert calls == []
    assert result.to_dict()["source"] == {"project_root": "project_root"}
    assert "adapter-project-root-invalid" in {
        finding["rule_id"] for finding in result.to_dict()["findings"]
    }


def test_adapter_maps_timeout_to_error_without_retry() -> None:
    adapter = _adapter()
    calls = 0

    def runner(
        argv: list[str],
        *,
        cwd: Path,
        input_bytes: bytes | None,
        timeout_seconds: float,
    ) -> SimpleNamespace:
        nonlocal calls
        calls += 1
        raise TimeoutError

    result = adapter.run_read_only_adapter(ROOT, runner=runner)

    assert result.status == "error"
    assert result.exit_code() == 1
    assert calls == 1
    assert "adapter-process-timeout" in {
        finding["rule_id"] for finding in result.to_dict()["findings"]
    }


def test_adapter_main_emits_json_and_maps_exit_code(monkeypatch) -> None:
    adapter = _adapter()
    handoff = _valid_handoff()
    runner = FakeRunner(handoff)
    expected = adapter.run_read_only_adapter(ROOT, runner=runner)
    monkeypatch.setattr(adapter, "run_read_only_adapter", lambda *args, **kwargs: expected)

    output = io.StringIO()
    exit_code = adapter.main(argv=["--project-root", str(ROOT)], stdout=output)

    payload = json.loads(output.getvalue())
    assert exit_code == 0
    assert payload["status"] == "ready"
    assert payload["schema_version"] == (
        "control-plane/codex-desktop-read-only-adapter/v1"
    )


def test_adapter_real_stdio_pipeline_from_project_root() -> None:
    script = ROOT / "tools" / "codex_desktop_read_only_adapter.py"
    completed = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(ROOT),
            "--timeout-seconds",
            "30",
            "--json",
        ],
        cwd=ROOT,
        capture_output=True,
        timeout=60,
        check=False,
    )

    assert completed.returncode == 0
    payload = json.loads(completed.stdout.decode("utf-8"))
    assert payload["status"] == "ready"
    assert payload["lifecycle"]["phases"] == [
        "created",
        "producing",
        "validating",
        "ready",
        "closed",
    ]
    assert str(ROOT.resolve()) not in completed.stdout.decode("utf-8")
    assert completed.stderr == b""
