"""Tests for the Stage 31 filtered snapshot one-shot host integration."""

from __future__ import annotations

import copy
import importlib.util
import io
import json
from functools import lru_cache
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "codex_desktop_filtered_snapshot_host.py"
READER_TOOL = ROOT / "tools" / "codex_desktop_snapshot_json_reader.py"
CONSUMER_TOOL = ROOT / "tools" / "codex_desktop_filtered_snapshot_consumer.py"
ENVELOPE = "adapters/execution-envelope.examples.json"
TASK_ID = "task-20260703-001"
REQUEST_ID = "req-20260703-001"


def _load_tool(path: Path, name: str):
    assert path.is_file(), f"missing Stage 31 tool: {path.name}"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _host():
    return _load_tool(TOOL, "codex_desktop_filtered_snapshot_host")


def _consumer():
    return _load_tool(
        CONSUMER_TOOL,
        "codex_desktop_filtered_snapshot_consumer_for_host_test",
    )


@lru_cache(maxsize=4)
def _reader_bytes(*filters: str) -> bytes:
    completed = subprocess.run(
        [
            sys.executable,
            str(READER_TOOL),
            "--project-root",
            str(ROOT),
            "--representation",
            "snapshot-json",
            "--envelope",
            ENVELOPE,
            *filters,
            "--json",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        timeout=60,
    )
    assert completed.returncode == 0
    assert completed.stderr == b""
    return completed.stdout


def _valid_reader_bytes() -> bytes:
    return _reader_bytes("--request-id", REQUEST_ID)


def _validation_bytes(reader_bytes: bytes) -> tuple[int, bytes]:
    document = json.loads(reader_bytes.decode("utf-8"))
    result = _consumer().validate_filtered_snapshot_document(document)
    return (
        result.exit_code(),
        json.dumps(result.to_dict(), ensure_ascii=False).encode("utf-8"),
    )


class FakeRunner:
    def __init__(
        self,
        reader_bytes: bytes | None = None,
        *,
        reader_returncode: int = 0,
        consumer_override: tuple[int, bytes] | None = None,
    ) -> None:
        self.reader_bytes = reader_bytes or _valid_reader_bytes()
        self.reader_returncode = reader_returncode
        self.consumer_override = consumer_override
        self.calls: list[dict[str, Any]] = []

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
        script = Path(argv[1]).name
        if script == READER_TOOL.name:
            assert input_bytes is None
            return SimpleNamespace(
                returncode=self.reader_returncode,
                stdout=self.reader_bytes,
                stderr=b"reader stderr must not escape",
            )
        assert script == CONSUMER_TOOL.name
        assert input_bytes == self.reader_bytes
        if self.consumer_override is not None:
            returncode, stdout = self.consumer_override
        else:
            returncode, stdout = _validation_bytes(self.reader_bytes)
        return SimpleNamespace(
            returncode=returncode,
            stdout=stdout,
            stderr=b"consumer stderr must not escape",
        )


def test_host_runs_fixed_reader_consumer_pipeline_and_displays_only_validated_payload() -> None:
    host = _host()
    runner = FakeRunner()

    result = host.run_filtered_snapshot_host(
        ROOT,
        envelope_file=ENVELOPE,
        request_id_filter=REQUEST_ID,
        runner=runner,
    )
    payload = result.to_dict()
    reader_document = json.loads(runner.reader_bytes)

    assert result.status == "ready"
    assert result.exit_code() == 0
    assert payload["schema_version"] == (
        "control-plane/codex-desktop-filtered-snapshot-host/v1"
    )
    assert payload["host"] == "codex-desktop-filtered-snapshot-host/v1"
    assert payload["source"] == {"project_root": "project_root"}
    assert payload["lifecycle"] == {
        "state": "closed",
        "phases": ["created", "reading", "validating", "ready", "closed"],
    }
    assert payload["reader"] == {"status": "pass", "exit_code": 0}
    assert payload["consumer"]["status"] == "pass"
    assert payload["representation"]["payload"] == (
        reader_document["representation"]["payload"]
    )
    assert payload["representation"]["view_id"] == (
        payload["consumer"]["source"]["view_id"]
    )
    assert payload["guarantees"] == {
        "requires_explicit_user_action": True,
        "one_shot": True,
        "read_only": True,
        "reads_filtered_snapshot_json": True,
        "validates_before_display": True,
        "displays_validated_safe_summaries": True,
        "reads_html": False,
        "writes_files": False,
        "writes_ledgers": False,
        "accesses_network": False,
        "starts_service": False,
        "runs_fixed_read_processes": True,
        "executes_descriptor_argv": False,
        "executes_candidate_commands": False,
        "executes_adapters": False,
        "auto_retries": False,
        "persists_filtered_views": False,
        "allows_arbitrary_queries": False,
        "bounded_output": True,
    }
    assert len(runner.calls) == 2
    assert runner.calls[0]["argv"] == [
        sys.executable,
        str(READER_TOOL),
        "--project-root",
        str(ROOT.resolve()),
        "--representation",
        "snapshot-json",
        "--envelope",
        ENVELOPE,
        "--request-id",
        REQUEST_ID,
        "--timeout-seconds",
        "30",
        "--json",
    ]
    assert runner.calls[1]["argv"] == [sys.executable, str(CONSUMER_TOOL)]
    assert runner.calls[0]["cwd"] == ROOT.resolve()
    assert runner.calls[1]["cwd"] == ROOT.resolve()


def test_host_supports_task_and_request_exact_and_filter() -> None:
    host = _host()
    reader_bytes = _reader_bytes(
        "--task-id",
        TASK_ID,
        "--request-id",
        REQUEST_ID,
    )
    runner = FakeRunner(reader_bytes)

    result = host.run_filtered_snapshot_host(
        ROOT,
        envelope_file=ENVELOPE,
        task_id_filter=TASK_ID,
        request_id_filter=REQUEST_ID,
        runner=runner,
    )

    assert result.status == "ready"
    assert result.to_dict()["representation"]["payload"]["filter"] == {
        "schema_version": "control-plane/envelope-snapshot-filter/v1",
        "task_id": TASK_ID,
        "request_id": REQUEST_ID,
    }


def test_host_never_releases_reader_payload_before_consumer_passes() -> None:
    host = _host()
    document = json.loads(_valid_reader_bytes())
    marker = "UNVALIDATED_HOST_PAYLOAD_SENTINEL"
    document["representation"]["payload"]["sections"]["runs"]["unexpected"] = marker
    reader_bytes = json.dumps(document).encode("utf-8")
    runner = FakeRunner(reader_bytes)

    result = host.run_filtered_snapshot_host(
        ROOT,
        envelope_file=ENVELOPE,
        request_id_filter=REQUEST_ID,
        runner=runner,
    )
    serialized = json.dumps(result.to_dict(), ensure_ascii=False)

    assert result.status == "validation_failed"
    assert result.exit_code() == 5
    assert result.to_dict()["representation"]["payload"] is None
    assert marker not in serialized


def test_host_maps_consumer_blocked_and_validation_failed_without_retry() -> None:
    host = _host()
    blocked_document = json.loads(_valid_reader_bytes())
    blocked_document["schema_version"] = "control-plane/codex-desktop-snapshot-read/v2"
    blocked_runner = FakeRunner(json.dumps(blocked_document).encode("utf-8"))

    blocked = host.run_filtered_snapshot_host(
        ROOT,
        envelope_file=ENVELOPE,
        request_id_filter=REQUEST_ID,
        runner=blocked_runner,
    )

    invalid_document = json.loads(_valid_reader_bytes())
    invalid_document["representation"]["view_id"] = "sha256:" + "0" * 64
    invalid_runner = FakeRunner(json.dumps(invalid_document).encode("utf-8"))
    invalid = host.run_filtered_snapshot_host(
        ROOT,
        envelope_file=ENVELOPE,
        request_id_filter=REQUEST_ID,
        runner=invalid_runner,
    )

    assert blocked.status == "blocked"
    assert blocked.exit_code() == 2
    assert len(blocked_runner.calls) == 2
    assert invalid.status == "validation_failed"
    assert invalid.exit_code() == 5
    assert len(invalid_runner.calls) == 2


def test_host_rejects_consumer_protocol_drift_and_pass_identity_mismatch() -> None:
    host = _host()
    malformed = FakeRunner(consumer_override=(0, b"not-json"))
    malformed_result = host.run_filtered_snapshot_host(
        ROOT,
        envelope_file=ENVELOPE,
        request_id_filter=REQUEST_ID,
        runner=malformed,
    )

    reader_bytes = _valid_reader_bytes()
    _, consumer_bytes = _validation_bytes(reader_bytes)
    consumer_payload = json.loads(consumer_bytes)
    consumer_payload["source"]["view_id"] = "sha256:" + "0" * 64
    mismatched = FakeRunner(
        reader_bytes,
        consumer_override=(0, json.dumps(consumer_payload).encode("utf-8")),
    )
    mismatch_result = host.run_filtered_snapshot_host(
        ROOT,
        envelope_file=ENVELOPE,
        request_id_filter=REQUEST_ID,
        runner=mismatched,
    )

    assert malformed_result.status == "error"
    assert "host-consumer-protocol-invalid-json" in {
        finding["rule_id"] for finding in malformed_result.to_dict()["findings"]
    }
    assert mismatch_result.status == "error"
    assert "host-validation-identity-mismatch" in {
        finding["rule_id"] for finding in mismatch_result.to_dict()["findings"]
    }


def test_host_rejects_status_exit_mismatch_and_nonzero_reader_after_consumer_pass() -> None:
    host = _host()
    reader_bytes = _valid_reader_bytes()
    _, consumer_bytes = _validation_bytes(reader_bytes)
    wrong_exit = FakeRunner(reader_bytes, consumer_override=(2, consumer_bytes))
    wrong_exit_result = host.run_filtered_snapshot_host(
        ROOT,
        envelope_file=ENVELOPE,
        request_id_filter=REQUEST_ID,
        runner=wrong_exit,
    )
    nonzero_reader = FakeRunner(reader_bytes, reader_returncode=1)
    nonzero_result = host.run_filtered_snapshot_host(
        ROOT,
        envelope_file=ENVELOPE,
        request_id_filter=REQUEST_ID,
        runner=nonzero_reader,
    )

    assert wrong_exit_result.status == "error"
    assert nonzero_result.status == "error"
    assert nonzero_result.to_dict()["representation"]["payload"] is None


def test_host_invalid_arguments_do_not_spawn_processes(tmp_path: Path) -> None:
    host = _host()
    calls: list[object] = []

    def runner(*args: object, **kwargs: object) -> SimpleNamespace:
        calls.append((args, kwargs))
        raise AssertionError("invalid input must fail before spawning")

    cases = [
        dict(project_root=tmp_path, envelope_file=ENVELOPE, request_id_filter=REQUEST_ID),
        dict(project_root=ROOT, envelope_file=ENVELOPE),
        dict(project_root=ROOT, envelope_file=ENVELOPE, request_id_filter="req-*"),
        dict(
            project_root=ROOT,
            envelope_file=ENVELOPE,
            request_id_filter=REQUEST_ID,
            timeout_seconds=0,
        ),
    ]
    for case in cases:
        result = host.run_filtered_snapshot_host(**case, runner=runner)
        assert result.status == "error" or result.status == "validation_failed"
    assert calls == []


def test_host_bounds_child_output_and_does_not_echo_it() -> None:
    host = _host()
    marker = b"HOST_OVERSIZED_OUTPUT_SENTINEL"
    runner = FakeRunner(marker + b"x" * (1024 * 1024))

    result = host.run_filtered_snapshot_host(
        ROOT,
        envelope_file=ENVELOPE,
        request_id_filter=REQUEST_ID,
        runner=runner,
    )

    assert result.status == "error"
    assert len(runner.calls) == 1
    assert marker.decode() not in json.dumps(result.to_dict())


def test_host_timeout_is_fail_closed_without_retry() -> None:
    host = _host()
    calls = 0

    def runner(*args: object, **kwargs: object) -> SimpleNamespace:
        nonlocal calls
        calls += 1
        raise TimeoutError

    result = host.run_filtered_snapshot_host(
        ROOT,
        envelope_file=ENVELOPE,
        request_id_filter=REQUEST_ID,
        runner=runner,
    )

    assert result.status == "error"
    assert result.exit_code() == 1
    assert calls == 1
    assert "host-process-timeout" in {
        finding["rule_id"] for finding in result.to_dict()["findings"]
    }


def test_host_result_is_deterministic_and_hides_root_envelope_and_stderr() -> None:
    host = _host()
    first = host.run_filtered_snapshot_host(
        ROOT,
        envelope_file=ENVELOPE,
        request_id_filter=REQUEST_ID,
        runner=FakeRunner(),
    ).to_dict()
    second = host.run_filtered_snapshot_host(
        ROOT,
        envelope_file=ENVELOPE,
        request_id_filter=REQUEST_ID,
        runner=FakeRunner(),
    ).to_dict()
    serialized = json.dumps(first, ensure_ascii=False)

    assert first == second
    assert str(ROOT.resolve()) not in serialized
    assert ENVELOPE not in serialized
    assert "stderr must not escape" not in serialized


def test_host_main_emits_bounded_json_and_maps_ready_exit(monkeypatch) -> None:
    host = _host()
    expected = host.run_filtered_snapshot_host(
        ROOT,
        envelope_file=ENVELOPE,
        request_id_filter=REQUEST_ID,
        runner=FakeRunner(),
    )
    monkeypatch.setattr(host, "run_filtered_snapshot_host", lambda *args, **kwargs: expected)
    stdout = io.StringIO()

    exit_code = host.main(
        argv=[
            "--project-root",
            str(ROOT),
            "--envelope",
            ENVELOPE,
            "--request-id",
            REQUEST_ID,
            "--json",
        ],
        stdout=stdout,
    )
    payload = json.loads(stdout.getvalue())

    assert exit_code == 0
    assert payload["status"] == "ready"
    assert len(stdout.getvalue().encode("utf-8")) <= 1024 * 1024


def test_host_real_one_shot_pipeline() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            str(TOOL),
            "--project-root",
            str(ROOT),
            "--envelope",
            ENVELOPE,
            "--request-id",
            REQUEST_ID,
            "--timeout-seconds",
            "30",
            "--json",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        timeout=60,
    )

    assert completed.returncode == 0
    assert completed.stderr == b""
    payload = json.loads(completed.stdout)
    assert payload["status"] == "ready"
    assert payload["consumer"]["status"] == "pass"
    assert payload["representation"]["payload"]["filter"]["request_id"] == REQUEST_ID
    serialized = completed.stdout.decode("utf-8")
    assert str(ROOT.resolve()) not in serialized
    assert ENVELOPE not in serialized


def test_host_minimal_environment_and_stderr_bounds_do_not_leak(monkeypatch) -> None:
    host = _host()
    monkeypatch.setenv("HOST_SECRET_SENTINEL", "must-not-be-forwarded")
    environment = host._minimal_environment()

    assert environment["PYTHONDONTWRITEBYTECODE"] == "1"
    assert "HOST_SECRET_SENTINEL" not in environment

    class StderrRunner(FakeRunner):
        def __call__(self, *args: Any, **kwargs: Any) -> SimpleNamespace:
            result = super().__call__(*args, **kwargs)
            if len(self.calls) == 1:
                result.stderr = b"SENSITIVE_STDERR_SENTINEL" + b"x" * (64 * 1024)
            return result

    runner = StderrRunner()
    result = host.run_filtered_snapshot_host(
        ROOT,
        envelope_file=ENVELOPE,
        request_id_filter=REQUEST_ID,
        runner=runner,
    )

    assert result.status == "error"
    assert len(runner.calls) == 1
    assert "SENSITIVE_STDERR_SENTINEL" not in json.dumps(result.to_dict())
    assert "host-reader-stderr-too-large" in {
        finding["rule_id"] for finding in result.to_dict()["findings"]
    }


def test_host_rejects_oversized_envelope_argument_before_spawn() -> None:
    host = _host()
    calls: list[object] = []

    def runner(*args: object, **kwargs: object) -> SimpleNamespace:
        calls.append((args, kwargs))
        raise AssertionError("oversized envelope must not spawn")

    result = host.run_filtered_snapshot_host(
        ROOT,
        envelope_file="a" * 513,
        request_id_filter=REQUEST_ID,
        runner=runner,
    )

    assert result.status == "validation_failed"
    assert calls == []


def test_host_source_has_no_network_or_runtime_write_dependencies() -> None:
    import ast

    tree = ast.parse(TOOL.read_text(encoding="utf-8"))
    imported: set[str] = set()
    called_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            called_names.add(node.func.id)
    forbidden_modules = {"agent_runtime", "tools", "socket", "requests", "urllib", "http", "sqlite3"}
    assert all(
        not any(name == blocked or name.startswith(blocked + ".") for blocked in forbidden_modules)
        for name in imported
    )
    assert "open" not in called_names
