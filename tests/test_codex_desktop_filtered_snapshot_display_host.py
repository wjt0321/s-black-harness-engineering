"""Tests for the Stage 40 filtered snapshot display host integration."""

from __future__ import annotations

import ast
import copy
import importlib.util
import json
from functools import lru_cache
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "codex_desktop_filtered_snapshot_display_host.py"
DISPLAY_TOOL = ROOT / "tools" / "codex_desktop_filtered_snapshot_display.py"
CONSUMER_TOOL = ROOT / "tools" / "codex_desktop_filtered_snapshot_display_consumer.py"
ENVELOPE = "adapters/execution-envelope.examples.json"
TASK_ID = "task-20260703-001"
REQUEST_ID = "req-20260703-001"
EMPTY_REQUEST_ID = "req-20260703-999"


def _load_tool():
    assert TOOL.is_file(), f"missing Stage 40 tool: {TOOL.name}"
    spec = importlib.util.spec_from_file_location(
        "codex_desktop_filtered_snapshot_display_host", TOOL
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@lru_cache(maxsize=16)
def _display_bytes(*args: str) -> tuple[int, bytes]:
    completed = subprocess.run(
        [sys.executable, str(DISPLAY_TOOL), *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        timeout=120,
    )
    assert completed.stderr == b""
    return completed.returncode, completed.stdout


def _display_for(
    *filters: str,
    envelope: str = ENVELOPE,
    timeout: str = "30",
) -> tuple[int, bytes]:
    return _display_bytes(
        "--project-root", str(ROOT),
        "--envelope", envelope,
        *(filters or ("--request-id", REQUEST_ID)),
        "--representation", "markdown",
        "--timeout-seconds", timeout,
        "--json",
    )


@lru_cache(maxsize=32)
def _consumer_bytes(display_bytes: bytes) -> tuple[int, bytes]:
    completed = subprocess.run(
        [sys.executable, str(CONSUMER_TOOL)],
        cwd=ROOT,
        input=display_bytes,
        check=False,
        capture_output=True,
        timeout=60,
    )
    assert completed.stderr == b""
    return completed.returncode, completed.stdout


class FakeRunner:
    def __init__(
        self,
        display: tuple[int, bytes] | None = None,
        *,
        consumer_override: tuple[int, bytes] | None = None,
        display_stderr: bytes = b"",
        consumer_stderr: bytes = b"",
    ) -> None:
        self.display = display or _display_for()
        self.consumer_override = consumer_override
        self.display_stderr = display_stderr
        self.consumer_stderr = consumer_stderr
        self.calls: list[dict[str, Any]] = []

    def __call__(
        self,
        argv: list[str],
        *,
        cwd: Path,
        input_bytes: bytes | None,
        timeout_seconds: float,
    ) -> SimpleNamespace:
        call = {
            "argv": list(argv),
            "cwd": cwd,
            "input_bytes": input_bytes,
            "timeout_seconds": timeout_seconds,
        }
        self.calls.append(call)
        if len(self.calls) == 1:
            return SimpleNamespace(
                returncode=self.display[0],
                stdout=self.display[1],
                stderr=self.display_stderr,
            )
        assert len(self.calls) == 2, "host must not launch extra processes"
        returncode, stdout = (
            self.consumer_override
            if self.consumer_override is not None
            else _consumer_bytes(input_bytes or b"")
        )
        return SimpleNamespace(
            returncode=returncode,
            stdout=stdout,
            stderr=self.consumer_stderr,
        )


def _run(host, runner: Any, **overrides: Any):
    arguments = {
        "project_root": ROOT,
        "envelope_file": ENVELOPE,
        "request_id_filter": REQUEST_ID,
        "runner": runner,
    }
    arguments.update(overrides)
    return host.run_filtered_snapshot_display_host(**arguments)


def _ready_documents() -> tuple[dict[str, Any], dict[str, Any]]:
    _, display_bytes = _display_for()
    _, consumer_bytes = _consumer_bytes(display_bytes)
    return json.loads(display_bytes), json.loads(consumer_bytes)


def test_host_runs_fixed_display_then_consumer_and_releases_validated_markdown() -> None:
    host = _load_tool()
    runner = FakeRunner()

    result = _run(host, runner)
    payload = result.to_dict()
    display_document = json.loads(runner.display[1])
    identity = {
        key: display_document["representation"][key]
        for key in (
            "base_snapshot_id", "scope_id", "filter_id", "view_id", "content_id"
        )
    }

    assert result.status == "ready"
    assert result.exit_code() == 0
    assert runner.calls == [
        {
            "argv": [
                sys.executable,
                str(DISPLAY_TOOL),
                "--project-root", str(ROOT.resolve()),
                "--envelope", ENVELOPE,
                "--request-id", REQUEST_ID,
                "--representation", "markdown",
                "--timeout-seconds", "30",
                "--json",
            ],
            "cwd": ROOT.resolve(),
            "input_bytes": None,
            "timeout_seconds": 30.0,
        },
        {
            "argv": [sys.executable, str(CONSUMER_TOOL)],
            "cwd": ROOT.resolve(),
            "input_bytes": runner.display[1],
            "timeout_seconds": 30.0,
        },
    ]
    assert payload["schema_version"] == (
        "control-plane/codex-desktop-filtered-snapshot-display-host/v1"
    )
    assert payload["host"] == "codex-desktop-filtered-snapshot-display-host/v1"
    assert payload["source"] == {"project_root": "project_root"}
    assert payload["lifecycle"] == {
        "state": "closed",
        "phases": ["created", "displaying", "validating", "ready", "closed"],
    }
    assert payload["display"] == {
        "status": "ready", "exit_code": 0, "source": identity,
    }
    assert payload["consumer"] == {
        "status": "pass", "exit_code": 0, "source": identity,
    }
    assert payload["representation"] == display_document["representation"]
    assert payload["findings"] == []
    assert payload["next_action"]["code"] == "review_validated_markdown_display"
    assert payload["guarantees"] == host.HOST_GUARANTEES
    assert len(json.dumps(payload).encode("utf-8")) <= host.MAX_HOST_OUTPUT_BYTES


@pytest.mark.parametrize(
    "filters",
    [
        ("--request-id", REQUEST_ID),
        ("--task-id", TASK_ID),
        ("--task-id", TASK_ID, "--request-id", REQUEST_ID),
        ("--request-id", EMPTY_REQUEST_ID),
    ],
)
def test_real_cli_pipeline_supports_request_task_and_empty_views(filters: tuple[str, ...]) -> None:
    assert TOOL.is_file()
    completed = subprocess.run(
        [
            sys.executable, str(TOOL),
            "--project-root", str(ROOT),
            "--envelope", ENVELOPE,
            *filters,
            "--representation", "markdown",
            "--json",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        timeout=180,
    )
    assert completed.returncode == 0
    assert completed.stderr == b""
    payload = json.loads(completed.stdout)
    assert payload["status"] == "ready"
    assert payload["consumer"]["status"] == "pass"
    assert payload["representation"]["status"] == "pass"
    assert payload["representation"]["content"].startswith("# Filtered Snapshot\n")
    if filters == ("--request-id", EMPTY_REQUEST_ID):
        assert "No matching runs." in payload["representation"]["content"]


@pytest.mark.parametrize(
    ("display", "expected_status", "expected_exit"),
    [
        (_display_for(envelope="adapters/missing.envelope.json"), "blocked", 2),
        (_display_for("--request-id", "req-*"), "validation_failed", 5),
        (_display_for(timeout="0"), "error", 1),
    ],
)
def test_host_maps_valid_non_ready_results_and_withholds_content(
    display: tuple[int, bytes], expected_status: str, expected_exit: int
) -> None:
    host = _load_tool()
    result = _run(host, FakeRunner(display))
    payload = result.to_dict()

    assert result.status == expected_status
    assert result.exit_code() == expected_exit
    assert payload["representation"]["status"] == "withheld"
    assert payload["representation"]["content"] is None
    assert payload["representation"]["content_id"] is None
    assert expected_status in payload["lifecycle"]["phases"]


def test_host_rejects_consumer_identity_mismatch_without_releasing_content() -> None:
    host = _load_tool()
    display_document, consumer_document = _ready_documents()
    consumer_document["source"]["content_id"] = "sha256:" + "0" * 64
    runner = FakeRunner(
        (0, json.dumps(display_document).encode("utf-8")),
        consumer_override=(0, json.dumps(consumer_document).encode("utf-8")),
    )

    result = _run(host, runner)
    serialized = json.dumps(result.to_dict())

    assert result.status == "error"
    assert result.exit_code() == 1
    assert result.to_dict()["representation"]["content"] is None
    assert display_document["representation"]["content"] not in serialized
    assert "display-host-validation-identity-mismatch" in {
        finding["rule_id"] for finding in result.to_dict()["findings"]
    }


@pytest.mark.parametrize(
    "mutator",
    [
        lambda document: document.update(schema_version="unsupported/v2"),
        lambda document: document.update(consumer="unexpected/v1"),
        lambda document: document.update(extra=True),
        lambda document: document["checks"].reverse(),
        lambda document: document["guarantees"].update(accesses_network=True),
        lambda document: document["next_action"].update(code="trust_without_validation"),
    ],
)
def test_host_rejects_consumer_protocol_drift(mutator) -> None:
    host = _load_tool()
    display_document, consumer_document = _ready_documents()
    mutator(consumer_document)
    runner = FakeRunner(
        (0, json.dumps(display_document).encode("utf-8")),
        consumer_override=(0, json.dumps(consumer_document).encode("utf-8")),
    )

    result = _run(host, runner)

    assert result.status == "error"
    assert result.to_dict()["representation"]["content"] is None


@pytest.mark.parametrize(
    "consumer_output",
    [
        b"",
        b"not-json",
        b"[]",
        b'{"status":"pass","status":"error"}',
        b"\xff",
        b"x" * (64 * 1024 + 1),
    ],
    ids=("empty", "invalid-json", "non-object", "duplicate-key", "non-utf8", "oversized"),
)
def test_host_rejects_malformed_consumer_output(consumer_output: bytes) -> None:
    host = _load_tool()
    result = _run(host, FakeRunner(consumer_override=(0, consumer_output)))

    assert result.status == "error"
    assert result.to_dict()["representation"]["content"] is None


@pytest.mark.parametrize(
    "display_output",
    [
        b"",
        b"not-json",
        b"[]",
        b'{"status":"ready","status":"error"}',
        b"\xff",
        b"x" * (64 * 1024 + 1),
    ],
    ids=("empty", "invalid-json", "non-object", "duplicate-key", "non-utf8", "oversized"),
)
def test_host_rejects_malformed_display_output_before_consumer(display_output: bytes) -> None:
    host = _load_tool()
    runner = FakeRunner((0, display_output))
    result = _run(host, runner)

    assert result.status == "error"
    assert len(runner.calls) == 1
    assert result.to_dict()["representation"]["content"] is None


@pytest.mark.parametrize(
    ("display_returncode", "consumer_returncode"),
    [(2, 0), (0, 2), (1, 0), (0, 5)],
)
def test_host_rejects_status_exit_mismatches(
    display_returncode: int, consumer_returncode: int
) -> None:
    host = _load_tool()
    _, display_bytes = _display_for()
    _, consumer_bytes = _consumer_bytes(display_bytes)
    result = _run(
        host,
        FakeRunner(
            (display_returncode, display_bytes),
            consumer_override=(consumer_returncode, consumer_bytes),
        ),
    )

    assert result.status == "error"
    assert result.to_dict()["representation"]["content"] is None


@pytest.mark.parametrize("failure", [TimeoutError(), OSError("start"), KeyboardInterrupt()])
def test_host_child_failure_or_cancel_is_fail_closed_without_retry(failure: BaseException) -> None:
    host = _load_tool()
    calls = 0

    def runner(*args: object, **kwargs: object) -> SimpleNamespace:
        nonlocal calls
        calls += 1
        raise failure

    result = _run(host, runner)

    assert result.status == "error"
    assert calls == 1
    assert result.to_dict()["representation"]["content"] is None


def test_host_bounds_stderr_and_does_not_echo_child_data() -> None:
    host = _load_tool()
    marker = b"DISPLAY_HOST_SECRET_SENTINEL"
    result = _run(
        host,
        FakeRunner(display_stderr=marker + b"x" * host.MAX_STDERR_BYTES),
    )
    serialized = json.dumps(result.to_dict())

    assert result.status == "error"
    assert marker.decode() not in serialized
    assert ENVELOPE not in serialized
    assert str(ROOT) not in serialized


def test_host_checks_final_output_bound_before_releasing_content() -> None:
    host = _load_tool()
    runner = FakeRunner()
    host.MAX_HOST_OUTPUT_BYTES = 1024

    result = _run(host, runner)

    assert result.status == "error"
    assert result.to_dict()["representation"]["content"] is None
    assert "display-host-output-too-large" in {
        finding["rule_id"] for finding in result.to_dict()["findings"]
    }


def test_invalid_inputs_fail_before_spawning() -> None:
    host = _load_tool()
    calls: list[object] = []

    def runner(*args: object, **kwargs: object) -> SimpleNamespace:
        calls.append((args, kwargs))
        raise AssertionError("invalid input must fail before spawning")

    cases = [
        dict(project_root=ROOT / "missing", envelope_file=ENVELOPE, request_id_filter=REQUEST_ID),
        dict(project_root=ROOT, envelope_file="../outside.json", request_id_filter=REQUEST_ID),
        dict(project_root=ROOT, envelope_file=str((ROOT / ENVELOPE).resolve()), request_id_filter=REQUEST_ID),
        dict(project_root=ROOT, envelope_file=ENVELOPE),
        dict(project_root=ROOT, envelope_file=ENVELOPE, request_id_filter="req-*"),
        dict(project_root=ROOT, envelope_file=ENVELOPE, request_id_filter=REQUEST_ID, representation="html"),
        dict(project_root=ROOT, envelope_file=ENVELOPE, request_id_filter=REQUEST_ID, timeout_seconds=0),
    ]
    for case in cases:
        result = host.run_filtered_snapshot_display_host(**case, runner=runner)
        assert result.status in {"error", "validation_failed"}
        assert result.to_dict()["representation"]["content"] is None
    assert calls == []


def test_cli_duplicate_selector_is_rejected_without_child_process(monkeypatch) -> None:
    host = _load_tool()
    calls: list[object] = []
    monkeypatch.setattr(host, "run_filtered_snapshot_display_host", lambda *a, **k: calls.append((a, k)))
    output = __import__("io").StringIO()

    exit_code = host.main(
        [
            "--project-root", str(ROOT),
            "--envelope", ENVELOPE,
            "--request-id", REQUEST_ID,
            "--request-id", REQUEST_ID,
            "--representation", "markdown",
            "--json",
        ],
        stdout=output,
    )

    payload = json.loads(output.getvalue())
    assert exit_code == 5
    assert payload["status"] == "validation_failed"
    assert calls == []


def test_host_output_is_deterministic_minimal_and_value_safe() -> None:
    host = _load_tool()
    first = _run(host, FakeRunner()).to_dict()
    second = _run(host, FakeRunner()).to_dict()

    assert first == second
    serialized = json.dumps(first, ensure_ascii=False)
    assert set(first) == {
        "status", "schema_version", "host", "source", "lifecycle", "display",
        "consumer", "representation", "findings", "guarantees", "next_action",
    }
    assert ENVELOPE not in serialized
    assert str(ROOT) not in serialized
    assert '"argv":' not in serialized
    assert "stderr" not in serialized


def test_host_source_has_no_write_network_service_or_parallel_validation_path() -> None:
    tree = ast.parse(TOOL.read_text(encoding="utf-8"))
    imports = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    calls = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }

    assert not imports.intersection({"requests", "urllib", "socket", "http", "asyncio"})
    assert not calls.intersection({"write_text", "write_bytes", "open", "unlink", "rename"})
    source = TOOL.read_text(encoding="utf-8")
    assert "codex_desktop_filtered_snapshot_display.py" in source
    assert "codex_desktop_filtered_snapshot_display_consumer.py" in source
    assert "codex_desktop_snapshot_json_reader.py" not in source
    assert "codex_desktop_filtered_snapshot_consumer.py" not in source
