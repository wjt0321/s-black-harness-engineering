"""Tests for the Stage 34 filtered snapshot Markdown display integration."""

from __future__ import annotations

import ast
import copy
import hashlib
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
TOOL = ROOT / "tools" / "codex_desktop_filtered_snapshot_display.py"
HOST_TOOL = ROOT / "tools" / "codex_desktop_filtered_snapshot_host.py"
ENVELOPE = "adapters/execution-envelope.examples.json"
TASK_ID = "task-20260703-001"
REQUEST_ID = "req-20260703-001"
EMPTY_REQUEST_ID = "req-20260703-999"


def _load_tool():
    assert TOOL.is_file(), f"missing Stage 34 tool: {TOOL.name}"
    spec = importlib.util.spec_from_file_location(
        "codex_desktop_filtered_snapshot_display", TOOL
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@lru_cache(maxsize=8)
def _host_result(*filters: str, envelope: str = ENVELOPE) -> tuple[int, bytes]:
    completed = subprocess.run(
        [
            sys.executable,
            str(HOST_TOOL),
            "--project-root",
            str(ROOT),
            "--envelope",
            envelope,
            *filters,
            "--json",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        timeout=60,
    )
    assert completed.stderr == b""
    return completed.returncode, completed.stdout


def _ready_host_bytes(*filters: str) -> bytes:
    returncode, stdout = _host_result(*(filters or ("--request-id", REQUEST_ID)))
    assert returncode == 0
    return stdout


class FakeRunner:
    def __init__(
        self,
        stdout: bytes | None = None,
        *,
        returncode: int = 0,
        stderr: bytes = b"host stderr must not escape",
    ) -> None:
        self.stdout = stdout if stdout is not None else _ready_host_bytes()
        self.returncode = returncode
        self.stderr = stderr
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
        return SimpleNamespace(
            returncode=self.returncode,
            stdout=self.stdout,
            stderr=self.stderr,
        )


def _run(display, runner: FakeRunner, **overrides: Any):
    arguments = {
        "project_root": ROOT,
        "envelope_file": ENVELOPE,
        "request_id_filter": REQUEST_ID,
        "runner": runner,
    }
    arguments.update(overrides)
    return display.run_filtered_snapshot_display(**arguments)


def _mutated_host(mutator) -> bytes:
    document = json.loads(_ready_host_bytes())
    mutator(document)
    return json.dumps(document, ensure_ascii=False).encode("utf-8")


def test_display_runs_only_fixed_host_and_returns_versioned_markdown() -> None:
    display = _load_tool()
    runner = FakeRunner()

    result = _run(display, runner)
    payload = result.to_dict()

    assert result.status == "ready"
    assert result.exit_code() == 0
    assert len(runner.calls) == 1
    assert runner.calls[0] == {
        "argv": [
            sys.executable,
            str(HOST_TOOL),
            "--project-root",
            str(ROOT.resolve()),
            "--envelope",
            ENVELOPE,
            "--request-id",
            REQUEST_ID,
            "--timeout-seconds",
            "30",
            "--json",
        ],
        "cwd": ROOT.resolve(),
        "input_bytes": None,
        "timeout_seconds": 30.0,
    }
    assert payload["schema_version"] == (
        "control-plane/codex-desktop-filtered-snapshot-display/v1"
    )
    assert payload["display"] == (
        "codex-desktop-filtered-snapshot-markdown-display/v1"
    )
    assert payload["source"] == {"project_root": "project_root"}
    assert payload["lifecycle"] == {
        "state": "closed",
        "phases": ["created", "loading", "projecting", "ready", "closed"],
    }
    assert payload["host"] == {"status": "ready", "exit_code": 0}
    assert payload["representation"]["status"] == "pass"
    assert payload["representation"]["type"] == "markdown"
    assert payload["representation"]["media_type"] == (
        "text/markdown; charset=utf-8"
    )
    assert payload["representation"]["content"].startswith(
        "# Filtered Snapshot\n"
    )
    assert payload["representation"]["content_id"] == "sha256:" + hashlib.sha256(
        payload["representation"]["content"].encode("utf-8")
    ).hexdigest()
    assert payload["findings"] == []


def test_display_supports_task_request_and_and_empty_view() -> None:
    display = _load_tool()
    cases = [
        (
            FakeRunner(_ready_host_bytes("--task-id", TASK_ID)),
            {"task_id_filter": TASK_ID, "request_id_filter": None},
        ),
        (
            FakeRunner(
                _ready_host_bytes(
                    "--task-id", TASK_ID, "--request-id", REQUEST_ID
                )
            ),
            {"task_id_filter": TASK_ID, "request_id_filter": REQUEST_ID},
        ),
        (
            FakeRunner(_ready_host_bytes("--request-id", EMPTY_REQUEST_ID)),
            {"request_id_filter": EMPTY_REQUEST_ID},
        ),
    ]

    task_result = _run(display, cases[0][0], **cases[0][1]).to_dict()
    and_result = _run(display, cases[1][0], **cases[1][1]).to_dict()
    empty_result = _run(display, cases[2][0], **cases[2][1]).to_dict()

    assert TASK_ID in task_result["representation"]["content"]
    assert TASK_ID in and_result["representation"]["content"]
    assert REQUEST_ID in and_result["representation"]["content"]
    assert "No matching runs." in empty_result["representation"]["content"]
    assert "No matching approvals." in empty_result["representation"]["content"]
    assert "No matching artifacts." in empty_result["representation"]["content"]
    assert empty_result["representation"]["content"] == _run(
        display,
        FakeRunner(_ready_host_bytes("--request-id", EMPTY_REQUEST_ID)),
        request_id_filter=EMPTY_REQUEST_ID,
    ).to_dict()["representation"]["content"]


def test_display_escapes_markdown_html_links_pipes_backticks_and_controls() -> None:
    display = _load_tool()
    hostile = "<script>[click](https://example.invalid)|`tick`&\r\nnext\x01"
    raw = _mutated_host(
        lambda document: document["representation"]["payload"]["sections"][
            "artifacts"
        ]["artifacts"][0].__setitem__("summary", hostile)
    )

    payload = _run(display, FakeRunner(raw)).to_dict()
    content = payload["representation"]["content"]

    assert payload["status"] == "ready"
    assert hostile not in content
    assert "<script>" not in content
    assert "](https://" not in content
    assert "|" not in content
    assert "`tick`" not in content
    assert "\r" not in content and "\x01" not in content
    assert "\\u003cscript\\u003e" in content
    assert "\\u007c" in content
    assert "\\u0060tick\\u0060" in content
    assert "\\u0026" in content
    assert "\\r\\n" in content and "\\u0001" in content


def test_display_maps_host_non_ready_status_and_withholds_content() -> None:
    display = _load_tool()
    blocked_exit, blocked_bytes = _host_result(
        "--request-id", REQUEST_ID, envelope="adapters/missing.json"
    )
    assert blocked_exit == 2

    blocked = _run(
        display,
        FakeRunner(blocked_bytes, returncode=blocked_exit),
        envelope_file="adapters/missing.json",
    ).to_dict()

    assert blocked["status"] == "blocked"
    assert blocked["host"] == {"status": "blocked", "exit_code": 2}
    assert blocked["representation"]["status"] == "withheld"
    assert blocked["representation"]["content"] is None
    assert blocked["representation"]["content_id"] is None
    serialized = json.dumps(blocked)
    assert "adapters/missing.json" not in serialized
    assert "host stderr must not escape" not in serialized


def test_display_rejects_malformed_duplicate_non_utf8_unknown_and_status_drift() -> None:
    display = _load_tool()
    unknown = _mutated_host(lambda document: document.__setitem__("unexpected", True))
    status_drift = _mutated_host(lambda document: document.__setitem__("status", "blocked"))
    cases = [
        (b"not-json", 0),
        (b'{"status":"ready","status":"blocked"}', 0),
        (b"\xff", 0),
        (unknown, 0),
        (status_drift, 0),
    ]

    for stdout, returncode in cases:
        result = _run(display, FakeRunner(stdout, returncode=returncode)).to_dict()
        assert result["status"] == "error"
        assert result["representation"]["content"] is None
        assert result["findings"]


def test_display_rejects_identity_shape_type_count_and_matched_drift() -> None:
    display = _load_tool()
    mutations = [
        lambda d: d["consumer"]["source"].__setitem__("view_id", "sha256:" + "0" * 64),
        lambda d: d["representation"]["payload"]["sections"]["runs"].__setitem__("unexpected", True),
        lambda d: d["representation"]["payload"]["sections"]["artifacts"]["artifacts"][0].__setitem__("safe_to_preview", "yes"),
        lambda d: d["representation"]["payload"]["summary"].__setitem__("artifact_count", 99),
        lambda d: d["representation"]["payload"]["summary"].__setitem__("matched", False),
    ]

    for mutation in mutations:
        result = _run(display, FakeRunner(_mutated_host(mutation))).to_dict()
        assert result["status"] == "error"
        assert result["representation"]["content"] is None


def test_display_bounds_host_output_stderr_final_output_and_never_retries() -> None:
    display = _load_tool()
    marker = b"DISPLAY_OVERSIZED_SENTINEL"
    oversized = _run(display, FakeRunner(marker + b"x" * (1024 * 1024))).to_dict()
    stderr = _run(
        display,
        FakeRunner(_ready_host_bytes(), stderr=b"x" * (64 * 1024 + 1)),
    ).to_dict()

    calls = 0

    def timeout_runner(*args: object, **kwargs: object) -> SimpleNamespace:
        nonlocal calls
        calls += 1
        raise TimeoutError

    timeout = display.run_filtered_snapshot_display(
        ROOT,
        envelope_file=ENVELOPE,
        request_id_filter=REQUEST_ID,
        runner=timeout_runner,
    ).to_dict()

    huge = _mutated_host(
        lambda document: document["representation"]["payload"]["sections"][
            "artifacts"
        ]["artifacts"][0].__setitem__("summary", "x" * (64 * 1024))
    )
    final_bound = _run(display, FakeRunner(huge)).to_dict()

    assert oversized["status"] == "error"
    assert marker.decode() not in json.dumps(oversized)
    assert stderr["status"] == "error"
    assert timeout["status"] == "error" and calls == 1
    assert final_bound["status"] == "error"
    assert final_bound["representation"]["content"] is None


def test_display_invalid_arguments_do_not_spawn() -> None:
    display = _load_tool()
    calls: list[object] = []

    def runner(*args: object, **kwargs: object) -> SimpleNamespace:
        calls.append((args, kwargs))
        raise AssertionError("invalid input must fail before spawning")

    cases = [
        dict(project_root=ROOT / "missing", envelope_file=ENVELOPE, request_id_filter=REQUEST_ID),
        dict(project_root=ROOT, envelope_file=ENVELOPE),
        dict(project_root=ROOT, envelope_file=ENVELOPE, request_id_filter="req-*"),
        dict(project_root=ROOT, envelope_file=ENVELOPE, request_id_filter=REQUEST_ID, representation="html"),
        dict(project_root=ROOT, envelope_file=ENVELOPE, request_id_filter=REQUEST_ID, timeout_seconds=61),
    ]
    for case in cases:
        result = display.run_filtered_snapshot_display(**case, runner=runner)
        assert result.status in {"error", "validation_failed"}
    assert calls == []


def test_display_main_emits_deterministic_bounded_json(monkeypatch) -> None:
    display = _load_tool()
    original = display.run_filtered_snapshot_display
    expected = _run(display, FakeRunner()).to_dict()
    monkeypatch.setattr(
        display,
        "run_filtered_snapshot_display",
        lambda *args, **kwargs: original(
            ROOT,
            envelope_file=ENVELOPE,
            request_id_filter=REQUEST_ID,
            runner=FakeRunner(),
        ),
    )
    first = io.StringIO()
    second = io.StringIO()

    assert display.main(
        [
            "--project-root", str(ROOT), "--envelope", ENVELOPE,
            "--request-id", REQUEST_ID, "--representation", "markdown", "--json",
        ],
        stdout=first,
    ) == 0
    assert display.main(
        [
            "--project-root", str(ROOT), "--envelope", ENVELOPE,
            "--request-id", REQUEST_ID, "--representation", "markdown", "--json",
        ],
        stdout=second,
    ) == 0
    assert json.loads(first.getvalue()) == expected
    assert first.getvalue() == second.getvalue()
    assert len(first.getvalue().encode("utf-8")) <= 64 * 1024


def test_display_real_stage31_host_pipeline_smoke() -> None:
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
            "--representation",
            "markdown",
            "--json",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        timeout=60,
    )
    payload = json.loads(completed.stdout)

    assert completed.returncode == 0
    assert completed.stderr == b""
    assert payload["status"] == "ready"
    assert payload["representation"]["content"].startswith("# Filtered Snapshot\n")


def test_display_source_has_no_parallel_reader_consumer_or_side_effect_pipeline() -> None:
    tree = ast.parse(TOOL.read_text(encoding="utf-8"))
    imported_roots: set[str] = set()
    called_names: set[str] = set()
    called_attrs: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_roots.add(node.module.split(".")[0])
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                called_names.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                called_attrs.add(node.func.attr)

    assert "agent_runtime" not in imported_roots
    assert "tools" not in imported_roots
    assert not ({"socket", "urllib", "http", "requests"} & imported_roots)
    assert not ({"open", "exec", "eval"} & called_names)
    assert not ({"read_text", "read_bytes", "write_text", "write_bytes", "unlink"} & called_attrs)
    source = TOOL.read_text(encoding="utf-8")
    assert "codex_desktop_snapshot_json_reader" not in source
    assert "codex_desktop_filtered_snapshot_consumer" not in source
    assert "codex_desktop_filtered_snapshot_host.py" in source
