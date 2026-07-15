"""Tests for the Stage 22 Codex Desktop snapshot JSON reader."""

from __future__ import annotations

import copy
import hashlib
import importlib
import io
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

from agent_runtime.orchestration_control_panel import (
    build_control_panel_handoff,
    build_control_panel_snapshot,
)

ROOT = Path(__file__).resolve().parents[1]


def _reader():
    return importlib.import_module("tools.codex_desktop_snapshot_json_reader")


def _handoff() -> dict[str, object]:
    return build_control_panel_handoff(ROOT).to_dict()


def _snapshot() -> dict[str, object]:
    return build_control_panel_snapshot(ROOT).to_dict()


def _rehash_handoff(payload: dict[str, object]) -> None:
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
    def __init__(
        self,
        handoff: dict[str, object],
        snapshot: dict[str, object],
    ) -> None:
        self.handoff = handoff
        self.snapshot = snapshot
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
        joined = " ".join(argv)
        if "control_panel_handoff_consumer.py" in joined:
            return SimpleNamespace(
                returncode=0,
                stdout=json.dumps(
                    _validation_payload(self.handoff),
                    ensure_ascii=False,
                ).encode("utf-8"),
                stderr=b"",
            )
        if "handoff" in argv:
            return SimpleNamespace(
                returncode=0,
                stdout=json.dumps(self.handoff, ensure_ascii=False).encode("utf-8"),
                stderr=b"",
            )
        if "snapshot" in argv:
            return SimpleNamespace(
                returncode=0,
                stdout=json.dumps(self.snapshot, ensure_ascii=False).encode("utf-8"),
                stderr=b"",
            )
        raise AssertionError(f"unexpected argv: {argv!r}")


def test_reader_runs_fixed_validated_snapshot_pipeline_without_descriptor_argv() -> None:
    reader = _reader()
    handoff = _handoff()
    sentinel = "DO_NOT_EXECUTE_STAGE22_SENTINEL"
    handoff["snapshot"]["argv"] = [sentinel]
    handoff["render"]["argv"] = [sentinel]
    _rehash_handoff(handoff)
    snapshot = _snapshot()
    runner = FakeRunner(handoff, snapshot)

    result = reader.run_snapshot_json_reader(
        ROOT,
        representation="snapshot-json",
        runner=runner,
    )
    payload = result.to_dict()

    assert result.status == "ready"
    assert result.exit_code() == 0
    assert payload["schema_version"] == "control-plane/codex-desktop-snapshot-read/v1"
    assert payload["reader"] == "codex-desktop-snapshot-json-reader/v1"
    assert payload["handoff"]["status"] == "pass"
    assert payload["representation"]["status"] == "pass"
    assert payload["representation"]["type"] == "snapshot-json"
    assert payload["representation"]["snapshot_id"] == snapshot["snapshot_id"]
    assert payload["representation"]["payload"] == snapshot
    assert payload["guarantees"] == {
        "requires_explicit_user_action": True,
        "one_shot": True,
        "read_only": True,
        "reads_snapshot_json": True,
        "reads_html": False,
        "writes_files": False,
        "accesses_network": False,
        "starts_service": False,
        "runs_fixed_read_processes": True,
        "executes_candidate_commands": False,
        "executes_adapters": False,
        "executes_descriptor_argv": False,
        "auto_retries": False,
        "bounded_output": True,
    }
    assert sentinel not in json.dumps(payload, ensure_ascii=False)
    assert len(runner.calls) == 3
    assert runner.calls[0]["argv"] == list(reader.HANDOFF_ARGV)
    assert Path(runner.calls[1]["argv"][-1]).name == "control_panel_handoff_consumer.py"
    assert runner.calls[2]["argv"] == list(reader.SNAPSHOT_ARGV)
    assert all(call["cwd"] == ROOT.resolve() for call in runner.calls)


def test_reader_requires_explicit_snapshot_json_selection_without_spawning() -> None:
    reader = _reader()
    calls: list[object] = []

    def runner(*args: object, **kwargs: object) -> SimpleNamespace:
        calls.append((args, kwargs))
        raise AssertionError("runner must not be called")

    result = reader.run_snapshot_json_reader(ROOT, representation=None, runner=runner)

    assert result.status == "blocked"
    assert result.exit_code() == 2
    assert calls == []
    assert result.to_dict()["next_action"]["code"] == "select_snapshot_json"


def test_reader_does_not_read_snapshot_when_handoff_is_blocked() -> None:
    reader = _reader()
    handoff = _handoff()
    handoff["status"] = "blocked"
    _rehash_handoff(handoff)
    validation = _validation_payload(handoff)
    calls: list[list[str]] = []

    def runner(
        argv: list[str],
        *,
        cwd: Path,
        input_bytes: bytes | None,
        timeout_seconds: float,
    ) -> SimpleNamespace:
        calls.append(list(argv))
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

    result = reader.run_snapshot_json_reader(
        ROOT,
        representation="snapshot-json",
        runner=runner,
    )

    assert result.status == "blocked"
    assert result.exit_code() == 2
    assert len(calls) == 2
    assert all("snapshot" not in argv for argv in calls)


def test_reader_rejects_snapshot_canonical_hash_drift_without_echoing_marker() -> None:
    reader = _reader()
    handoff = _handoff()
    snapshot = _snapshot()
    marker = "SNAPSHOT_HASH_DRIFT_SENTINEL"
    snapshot["summary"]["marker"] = marker
    runner = FakeRunner(handoff, snapshot)

    result = reader.run_snapshot_json_reader(
        ROOT,
        representation="snapshot-json",
        runner=runner,
    )
    serialized = json.dumps(result.to_dict(), ensure_ascii=False)

    assert result.status == "validation_failed"
    assert result.exit_code() == 5
    assert marker not in serialized
    assert "snapshot-canonical-hash-mismatch" in {
        finding["rule_id"] for finding in result.to_dict()["findings"]
    }


def test_reader_rejects_snapshot_schema_source_and_guarantee_drift() -> None:
    reader = _reader()
    cases = [
        ("schema_version", "control-plane/other/v1", "snapshot-schema-mismatch"),
        ("source", {"envelope_file": "outside.json"}, "snapshot-source-mismatch"),
        (
            "guarantees",
            {**_snapshot()["guarantees"], "accesses_network": True},
            "snapshot-guarantees-invalid",
        ),
    ]

    for key, value, rule_id in cases:
        handoff = _handoff()
        snapshot = _snapshot()
        snapshot[key] = value
        result = reader.run_snapshot_json_reader(
            ROOT,
            representation="snapshot-json",
            runner=FakeRunner(handoff, snapshot),
        )

        assert result.status == "validation_failed"
        assert rule_id in {
            finding["rule_id"] for finding in result.to_dict()["findings"]
        }


def test_reader_rejects_malformed_duplicate_and_oversized_snapshot_output() -> None:
    reader = _reader()
    handoff = _handoff()
    validation = _validation_payload(handoff)
    bad_outputs = [
        (b"not-json", "snapshot-protocol-invalid-json"),
        (b'{"status":"pass","status":"pass"}', "snapshot-protocol-duplicate-key"),
        (b"\xff", "snapshot-protocol-not-utf8"),
        (b"{" + b"x" * (reader.MAX_OUTPUT_BYTES + 1), "snapshot-output-too-large"),
    ]

    for bad_output, rule_id in bad_outputs:
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
            if "control_panel_handoff_consumer.py" in " ".join(argv):
                return SimpleNamespace(
                    returncode=0,
                    stdout=json.dumps(validation).encode("utf-8"),
                    stderr=b"",
                )
            if "handoff" in argv:
                return SimpleNamespace(
                    returncode=0,
                    stdout=json.dumps(handoff).encode("utf-8"),
                    stderr=b"",
                )
            return SimpleNamespace(returncode=0, stdout=bad_output, stderr=b"")

        result = reader.run_snapshot_json_reader(
            ROOT,
            representation="snapshot-json",
            runner=runner,
        )

        assert result.status in {"validation_failed", "error"}
        assert rule_id in {
            finding["rule_id"] for finding in result.to_dict()["findings"]
        }
        assert calls == 3


def test_reader_rejects_non_project_root_and_timeout_without_retry(tmp_path: Path) -> None:
    reader = _reader()
    calls = 0

    def runner(*args: object, **kwargs: object) -> SimpleNamespace:
        nonlocal calls
        calls += 1
        raise TimeoutError

    invalid = reader.run_snapshot_json_reader(
        tmp_path,
        representation="snapshot-json",
        runner=runner,
    )
    assert invalid.status == "error"
    assert calls == 0

    timed_out = reader.run_snapshot_json_reader(
        ROOT,
        representation="snapshot-json",
        runner=runner,
    )
    assert timed_out.status == "error"
    assert calls == 1
    assert "reader-process-timeout" in {
        finding["rule_id"] for finding in timed_out.to_dict()["findings"]
    }


def test_reader_is_deterministic_does_not_echo_root_and_does_not_write(tmp_path: Path) -> None:
    reader = _reader()
    handoff = _handoff()
    snapshot = _snapshot()
    before = {path.relative_to(ROOT) for path in ROOT.rglob("*") if path.is_file()}
    marker = tmp_path / "marker.txt"
    marker.write_text("unchanged", encoding="utf-8")

    first = reader.run_snapshot_json_reader(
        ROOT,
        representation="snapshot-json",
        runner=FakeRunner(copy.deepcopy(handoff), copy.deepcopy(snapshot)),
    ).to_dict()
    second = reader.run_snapshot_json_reader(
        ROOT,
        representation="snapshot-json",
        runner=FakeRunner(copy.deepcopy(handoff), copy.deepcopy(snapshot)),
    ).to_dict()

    after = {path.relative_to(ROOT) for path in ROOT.rglob("*") if path.is_file()}
    assert first == second
    assert str(ROOT.resolve()) not in json.dumps(first, ensure_ascii=False)
    assert first["source"] == {"project_root": "project_root"}
    assert before == after
    assert marker.read_text(encoding="utf-8") == "unchanged"


def test_reader_main_and_real_stdio_pipeline() -> None:
    reader = _reader()
    output = io.StringIO()
    exit_code = reader.main(
        argv=[
            "--project-root",
            str(ROOT),
            "--representation",
            "snapshot-json",
            "--json",
        ],
        stdout=output,
    )

    payload = json.loads(output.getvalue())
    assert exit_code == 0
    assert payload["status"] == "ready"
    assert payload["representation"]["payload"]["status"] == "pass"

    script = ROOT / "tools" / "codex_desktop_snapshot_json_reader.py"
    completed = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(ROOT),
            "--representation",
            "snapshot-json",
            "--timeout-seconds",
            "30",
            "--json",
        ],
        cwd=ROOT,
        capture_output=True,
        timeout=90,
        check=False,
    )

    assert completed.returncode == 0
    real_payload = json.loads(completed.stdout.decode("utf-8"))
    assert real_payload["status"] == "ready"
    assert real_payload["lifecycle"]["phases"] == [
        "created",
        "producing",
        "validating",
        "reading",
        "ready",
        "closed",
    ]
    assert real_payload["representation"]["payload"]["snapshot_id"] == (
        real_payload["representation"]["snapshot_id"]
    )
    assert str(ROOT.resolve()) not in completed.stdout.decode("utf-8")
    assert completed.stderr == b""
