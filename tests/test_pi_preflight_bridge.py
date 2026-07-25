"""Tests for the Stage 52 Pi host preflight bridge (pi-bridge preflight)."""

from __future__ import annotations

import io
import json
import sys
import types
from pathlib import Path
from typing import Any

from agent_runtime.adapter_registry import load_adapter_registry
from agent_runtime.cli import main
from agent_runtime.pi_preflight_bridge import (
    MAX_INPUT_BYTES,
    REQUEST_SCHEMA_VERSION,
    RESPONSE_SCHEMA_VERSION,
    run_preflight_bridge,
)


ROOT = Path(__file__).resolve().parents[1]


def _request(tool: str, input_fields: dict[str, Any], request_id: str | None = None) -> bytes:
    payload: dict[str, Any] = {
        "schema_version": REQUEST_SCHEMA_VERSION,
        "tool": tool,
        "input": input_fields,
    }
    if request_id is not None:
        payload["request_id"] = request_id
    return json.dumps(payload).encode("utf-8")


def _run(raw: bytes, root: Path = ROOT) -> tuple[dict[str, Any], int]:
    return run_preflight_bridge(root, raw)


def _secret() -> str:
    return "sk-" + ("A" * 24)


class TestInputGate:
    def test_empty_input_is_invalid(self) -> None:
        payload, code = _run(b"")
        assert payload["decision"] == "invalid"
        assert code == 5
        assert payload["findings"][0]["rule_id"] == "pi-bridge-empty-input"

    def test_oversized_input_is_invalid(self) -> None:
        payload, code = _run(b" " * (MAX_INPUT_BYTES + 1))
        assert payload["decision"] == "invalid"
        assert code == 5
        assert payload["findings"][0]["rule_id"] == "pi-bridge-input-too-large"

    def test_non_utf8_input_is_invalid(self) -> None:
        payload, code = _run(b"\xff\xfe{}")
        assert payload["decision"] == "invalid"
        assert payload["findings"][0]["rule_id"] == "pi-bridge-input-not-utf8"

    def test_malformed_json_is_invalid(self) -> None:
        payload, code = _run(b"{not json")
        assert payload["decision"] == "invalid"
        assert payload["findings"][0]["rule_id"] == "pi-bridge-invalid-json"

    def test_duplicate_key_is_invalid(self) -> None:
        raw = b'{"schema_version": "x", "schema_version": "y"}'
        payload, code = _run(raw)
        assert payload["decision"] == "invalid"
        assert payload["findings"][0]["rule_id"] == "pi-bridge-duplicate-json-key"

    def test_non_object_root_is_invalid(self) -> None:
        payload, code = _run(b'["read"]')
        assert payload["decision"] == "invalid"
        assert code == 5

    def test_wrong_schema_version_is_invalid(self) -> None:
        raw = json.dumps(
            {"schema_version": "pi-bridge/preflight-request/v0", "tool": "read", "input": {"path": "a.md"}}
        ).encode("utf-8")
        payload, code = _run(raw)
        assert payload["decision"] == "invalid"
        assert payload["findings"][0]["rule_id"] == "pi-bridge-unsupported-schema-version"

    def test_unknown_top_level_field_is_invalid(self) -> None:
        raw = json.dumps(
            {
                "schema_version": REQUEST_SCHEMA_VERSION,
                "tool": "read",
                "input": {"path": "a.md"},
                "extra": True,
            }
        ).encode("utf-8")
        payload, _code = _run(raw)
        assert payload["decision"] == "invalid"
        assert payload["findings"][0]["rule_id"] == "pi-bridge-unknown-field"

    def test_unknown_tool_is_invalid(self) -> None:
        payload, _code = _run(_request("delete", {"path": "a.md"}))
        assert payload["decision"] == "invalid"
        assert payload["findings"][0]["rule_id"] == "pi-bridge-unknown-tool"

    def test_unknown_input_field_is_invalid(self) -> None:
        payload, _code = _run(_request("read", {"path": "a.md", "offset": 3}))
        assert payload["decision"] == "invalid"
        assert payload["findings"][0]["rule_id"] == "pi-bridge-unknown-field"

    def test_missing_input_field_is_invalid(self) -> None:
        payload, _code = _run(_request("write", {"path": "a.md"}))
        assert payload["decision"] == "invalid"
        assert payload["findings"][0]["rule_id"] == "pi-bridge-missing-field"

    def test_non_string_field_is_invalid(self) -> None:
        payload, _code = _run(_request("read", {"path": 42}))
        assert payload["decision"] == "invalid"
        assert payload["findings"][0]["rule_id"] == "pi-bridge-invalid-field-type"

    def test_nul_in_field_is_invalid(self) -> None:
        payload, _code = _run(_request("bash", {"command": "echo a\x00b"}))
        assert payload["decision"] == "invalid"

    def test_bad_request_id_is_invalid(self) -> None:
        payload, _code = _run(_request("read", {"path": "a.md"}, request_id="bad id with spaces"))
        assert payload["decision"] == "invalid"
        assert payload["findings"][0]["rule_id"] == "pi-bridge-invalid-request-id"


class TestDecisions:
    def test_read_plain_file_passes(self) -> None:
        payload, code = _run(_request("read", {"path": "docs/00-index.md"}, request_id="req-1"))
        assert payload["decision"] == "pass"
        assert code == 0
        assert payload["tool"] == "read"
        assert payload["request_id"] == "req-1"
        assert payload["request_hash"].startswith("sha256:")
        assert payload["target_hash"].startswith("sha256:")
        assert payload["next_action"]["code"] == "proceed"

    def test_write_plain_file_passes(self) -> None:
        payload, code = _run(_request("write", {"path": "notes/example.md", "content": "hello"}))
        assert payload["decision"] == "pass"
        assert code == 0

    def test_edit_plain_file_passes(self) -> None:
        payload, code = _run(
            _request(
                "edit",
                {"path": "notes/example.md", "edits": [{"old_string": "a", "new_string": "b"}]},
            )
        )
        assert payload["decision"] == "pass"
        assert code == 0

    def test_edit_multiple_entries_passes(self) -> None:
        payload, code = _run(
            _request(
                "edit",
                {
                    "path": "notes/example.md",
                    "edits": [
                        {"old_string": "a", "new_string": "b"},
                        {"old_string": "c", "new_string": "d"},
                    ],
                },
            )
        )
        assert payload["decision"] == "pass"
        assert code == 0

    def test_bash_innocuous_command_passes(self) -> None:
        payload, code = _run(_request("bash", {"command": "python -m pytest tests -q"}))
        assert payload["decision"] == "pass"
        assert code == 0

    def test_read_env_file_is_blocked(self) -> None:
        payload, code = _run(_request("read", {"path": ".env"}))
        assert payload["decision"] == "blocked"
        assert code == 2
        assert any(f["rule_id"] == "pi-bridge-sensitive-target" for f in payload["findings"])

    def test_read_pem_file_is_blocked(self) -> None:
        payload, _code = _run(_request("read", {"path": "certs/server.pem"}))
        assert payload["decision"] == "blocked"
        assert any(f["rule_id"] == "pi-bridge-sensitive-target" for f in payload["findings"])

    def test_write_readonly_path_is_blocked(self) -> None:
        payload, code = _run(
            _request("write", {"path": "competition_notes/review.md", "content": "x"})
        )
        assert payload["decision"] == "blocked"
        assert code == 2
        assert payload["next_action"]["code"] == "do_not_execute"

    def test_write_content_with_secret_is_blocked(self) -> None:
        payload, code = _run(
            _request("write", {"path": "notes/example.md", "content": f"token: {_secret()}"})
        )
        assert payload["decision"] == "blocked"
        assert code == 2

    def test_edit_new_string_with_secret_is_blocked(self) -> None:
        payload, _code = _run(
            _request(
                "edit",
                {
                    "path": "notes/example.md",
                    "edits": [
                        {"old_string": "a", "new_string": "b"},
                        {"old_string": "c", "new_string": _secret()},
                    ],
                },
            )
        )
        assert payload["decision"] == "blocked"

    def test_edit_empty_edits_is_invalid(self) -> None:
        payload, _code = _run(_request("edit", {"path": "a.md", "edits": []}))
        assert payload["decision"] == "invalid"
        assert payload["findings"][0]["rule_id"] == "pi-bridge-invalid-field-value"

    def test_edit_non_list_edits_is_invalid(self) -> None:
        payload, _code = _run(_request("edit", {"path": "a.md", "edits": "x"}))
        assert payload["decision"] == "invalid"

    def test_edit_entry_wrong_shape_is_invalid(self) -> None:
        payload, _code = _run(
            _request("edit", {"path": "a.md", "edits": [{"old_string": "a"}]})
        )
        assert payload["decision"] == "invalid"
        assert payload["findings"][0]["rule_id"] == "pi-bridge-invalid-shape"

    def test_edit_entry_non_string_is_invalid(self) -> None:
        payload, _code = _run(
            _request("edit", {"path": "a.md", "edits": [{"old_string": 1, "new_string": "b"}]})
        )
        assert payload["decision"] == "invalid"
        assert payload["findings"][0]["rule_id"] == "pi-bridge-invalid-field-value"

    def test_bash_git_push_needs_approval(self) -> None:
        payload, code = _run(_request("bash", {"command": "git push origin main"}))
        assert payload["decision"] == "needs_approval"
        assert code == 3
        assert payload["next_action"]["code"] == "request_user_approval"

    def test_bash_rm_rf_needs_approval(self) -> None:
        payload, code = _run(_request("bash", {"command": "rm -rf /tmp/scratch"}))
        assert payload["decision"] == "needs_approval"
        assert code == 3

    def test_bash_command_with_secret_is_blocked(self) -> None:
        payload, _code = _run(_request("bash", {"command": f"curl -H 'Authorization: {_secret()}'"}))
        # curl ... send-like rules require approval and the embedded secret blocks.
        assert payload["decision"] == "blocked"

    def test_missing_adapter_registry_fails_closed(self, tmp_path: Path) -> None:
        payload, code = _run(_request("bash", {"command": "echo hi"}), root=tmp_path)
        assert payload["decision"] == "blocked"
        assert code == 2


class TestOutputSafetyAndDeterminism:
    def test_output_is_deterministic(self) -> None:
        raw = _request("bash", {"command": "git push origin main"}, request_id="req-9")
        first, _ = _run(raw)
        second, _ = _run(raw)
        assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)

    def test_output_does_not_echo_command_or_secret(self) -> None:
        command = f"git push origin main --token {_secret()}"
        payload, _ = _run(_request("bash", {"command": command}))
        rendered = json.dumps(payload, ensure_ascii=False)
        assert _secret() not in rendered
        assert command not in rendered
        assert "git push origin main" not in rendered

    def test_output_does_not_echo_path_or_content(self) -> None:
        content = f"body {_secret()}"
        payload, _ = _run(
            _request("write", {"path": "notes/secret-target.md", "content": content})
        )
        rendered = json.dumps(payload, ensure_ascii=False)
        assert content not in rendered
        assert "notes/secret-target.md" not in rendered

    def test_invalid_response_has_null_identity(self) -> None:
        payload, _ = _run(b"junk")
        assert payload["request_hash"] is None
        assert payload["tool"] is None
        assert payload["target_hash"] is None
        assert payload["schema_version"] == RESPONSE_SCHEMA_VERSION

    def test_guarantees_are_declared(self) -> None:
        payload, _ = _run(_request("read", {"path": "docs/00-index.md"}))
        guarantees = payload["guarantees"]
        assert guarantees["executes_tools"] is False
        assert guarantees["writes_files"] is False
        assert guarantees["writes_ledgers"] is False
        assert guarantees["accesses_network"] is False
        assert guarantees["reads_target_files"] is False
        assert guarantees["echoes_input_values"] is False

    def test_no_filesystem_side_effects(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        payload, code = _run(_request("write", {"path": "notes/example.md", "content": "hi"}))
        assert payload["decision"] == "pass"
        assert code == 0
        assert list(tmp_path.iterdir()) == []


class TestCliSurface:
    def _run_cli(self, raw: bytes, monkeypatch, capsys, *extra: str) -> int:
        monkeypatch.setattr(sys, "stdin", types.SimpleNamespace(buffer=io.BytesIO(raw)))
        code = main(["pi-bridge", "preflight", "--root", str(ROOT), *extra])
        return code

    def test_cli_pass(self, monkeypatch, capsys) -> None:
        code = self._run_cli(_request("read", {"path": "docs/00-index.md"}), monkeypatch, capsys)
        out = capsys.readouterr().out
        payload = json.loads(out)
        assert code == 0
        assert payload["decision"] == "pass"
        assert payload["schema_version"] == RESPONSE_SCHEMA_VERSION

    def test_cli_needs_approval_exit_code(self, monkeypatch, capsys) -> None:
        code = self._run_cli(_request("bash", {"command": "git push origin main"}), monkeypatch, capsys)
        payload = json.loads(capsys.readouterr().out)
        assert code == 3
        assert payload["decision"] == "needs_approval"

    def test_cli_blocked_exit_code(self, monkeypatch, capsys) -> None:
        code = self._run_cli(_request("read", {"path": ".env"}), monkeypatch, capsys)
        payload = json.loads(capsys.readouterr().out)
        assert code == 2
        assert payload["decision"] == "blocked"

    def test_cli_invalid_exit_code(self, monkeypatch, capsys) -> None:
        code = self._run_cli(b"not json", monkeypatch, capsys)
        payload = json.loads(capsys.readouterr().out)
        assert code == 5
        assert payload["decision"] == "invalid"

    def test_cli_output_is_single_json_document(self, monkeypatch, capsys) -> None:
        self._run_cli(_request("read", {"path": "docs/00-index.md"}), monkeypatch, capsys)
        out = capsys.readouterr().out.strip()
        assert out.startswith("{") and out.endswith("}")
        json.loads(out)  # must parse as one document


class TestAdapterRegistryEntry:
    def test_pi_host_entry_exists_and_is_distinct(self) -> None:
        registry, findings, _ = load_adapter_registry(ROOT)
        assert registry is not None, findings
        metadata = registry.get_adapter("pi-host")
        assert metadata is not None
        assert metadata.risk_level == "local"
        assert metadata.requires_approval is False
        assert "tool_call_preflight" in metadata.capabilities
        assert registry.get_adapter("omp-acp") is not None
        assert metadata.adapter_id != "omp-acp"
