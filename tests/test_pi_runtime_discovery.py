"""Tests for Stage 60 Pi adapter discovery & capability projection (read-only)."""

from __future__ import annotations

import json
from pathlib import Path

from agent_runtime.cli import main
from agent_runtime.adapter_registry import load_adapter_registry
from agent_runtime.pi_runtime_discovery import discover_pi_runtime


ROOT = Path(__file__).resolve().parents[1]

ENV_DIR_VAR = "PI_CODING_AGENT_DIR"
KEY_VAR = "STAGE60_FAKE_API_KEY"
# Canary fragments assembled at runtime; never a complete realistic secret.
AUTH_CANARY = "AUTH_CANARY_" + "z" * 6
SESSION_CANARY = "SESSION_CANARY_" + "y" * 6
PLAINTEXT_KEY = "sk-" + "plaintext" + "-" + "x" * 8
FAKE_KEY_VALUE = "fake-key-" + "v" * 8


def _write_fake_agent_dir(
    fake_root: Path,
    *,
    pinned: bool = True,
    plaintext_key: bool = False,
    models_provider: str = "deepseek-compat",
    models_model: str = "deepseek-v4-flash",
    extension: bool = True,
    settings: bool = True,
    models: bool = True,
    oversized_settings: bool = False,
) -> Path:
    """Create a minimal fake project-local Pi agent dir with canary credential files."""
    agent_dir = fake_root / ".runtime" / "pi-agent"
    agent_dir.mkdir(parents=True, exist_ok=True)
    if settings:
        settings_data: dict = {"theme": "dark"}
        if pinned:
            settings_data["defaultProvider"] = "deepseek-compat"
            settings_data["defaultModel"] = "deepseek-v4-flash"
        content = json.dumps(settings_data)
        if oversized_settings:
            content += " " * (70 * 1024)
        (agent_dir / "settings.json").write_text(content, encoding="utf-8")
    if models:
        api_key = PLAINTEXT_KEY if plaintext_key else f"${KEY_VAR}"
        models_data = {
            "providers": {
                models_provider: {
                    "baseUrl": "https://example.invalid/v1",
                    "apiKey": api_key,
                    "models": [{"id": models_model, "name": "fake-model"}],
                }
            }
        }
        (agent_dir / "models.json").write_text(json.dumps(models_data), encoding="utf-8")
    if extension:
        ext_dir = agent_dir / "extensions" / "pi-preflight-bridge"
        ext_dir.mkdir(parents=True, exist_ok=True)
        (ext_dir / "index.ts").write_text("// fake extension for tests\n", encoding="utf-8")
    # Credential-bearing files that the probe must never read or echo.
    (agent_dir / "auth.json").write_text(json.dumps({"keys": {"x": AUTH_CANARY}}), encoding="utf-8")
    sessions_dir = agent_dir / "sessions"
    sessions_dir.mkdir(exist_ok=True)
    (sessions_dir / "s1.json").write_text(json.dumps({"token": SESSION_CANARY}), encoding="utf-8")
    return agent_dir


def _env(agent_dir: Path, *, with_key: bool = True) -> dict[str, str]:
    env = {ENV_DIR_VAR: str(agent_dir)}
    if with_key:
        env[KEY_VAR] = FAKE_KEY_VALUE
    return env


def _setup_fake_root(tmp_path: Path) -> Path:
    """Fake project root carrying the real adapter registry and schema."""
    fake_root = tmp_path / "project"
    adapters_dir = fake_root / "adapters"
    adapters_dir.mkdir(parents=True)
    for name in ("adapters.sample.json", "adapter.schema.json"):
        (adapters_dir / name).write_text(
            (ROOT / "adapters" / name).read_text(encoding="utf-8"), encoding="utf-8"
        )
    return fake_root


# ---------------------------------------------------------------------------
# discovery unit tests
# ---------------------------------------------------------------------------


def test_ready_status_is_deterministic_and_secret_safe(tmp_path: Path) -> None:
    fake_root = tmp_path / "project"
    fake_root.mkdir()
    agent_dir = _write_fake_agent_dir(fake_root)

    first = discover_pi_runtime(fake_root, _env(agent_dir))
    second = discover_pi_runtime(fake_root, _env(agent_dir))

    assert first.status == "ready"
    assert first.to_dict() == second.to_dict()
    assert [c["status"] for c in first.to_dict()["checks"]] == ["pass"] * 7
    assert first.default_provider == "deepseek-compat"
    assert first.default_model == "deepseek-v4-flash"

    payload = json.dumps(first.to_dict(), ensure_ascii=False)
    assert AUTH_CANARY not in payload
    assert SESSION_CANARY not in payload
    assert FAKE_KEY_VALUE not in payload
    assert KEY_VAR in payload  # env var *name* is not a secret


def test_missing_env_dir_var_is_needs_input(tmp_path: Path) -> None:
    result = discover_pi_runtime(tmp_path, {})
    assert result.status == "needs_input"
    assert result.findings[0].rule_id == "pi-runtime-env-dir-missing"


def test_missing_agent_dir_is_unavailable(tmp_path: Path) -> None:
    fake_root = tmp_path / "project"
    fake_root.mkdir()
    env = {ENV_DIR_VAR: str(fake_root / ".runtime" / "pi-agent"), KEY_VAR: FAKE_KEY_VALUE}
    result = discover_pi_runtime(fake_root, env)
    assert result.status == "unavailable"
    assert result.findings[0].rule_id == "pi-runtime-agent-dir-missing"


def test_agent_dir_outside_runtime_is_invalid(tmp_path: Path) -> None:
    fake_root = tmp_path / "project"
    fake_root.mkdir()
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    env = {ENV_DIR_VAR: str(outside), KEY_VAR: FAKE_KEY_VALUE}
    result = discover_pi_runtime(fake_root, env)
    assert result.status == "invalid"
    assert result.findings[0].rule_id == "pi-runtime-agent-dir-escape"


def test_invalid_settings_json_is_invalid(tmp_path: Path) -> None:
    fake_root = tmp_path / "project"
    fake_root.mkdir()
    agent_dir = _write_fake_agent_dir(fake_root, settings=False)
    (agent_dir / "settings.json").write_text("{not json", encoding="utf-8")
    result = discover_pi_runtime(fake_root, _env(agent_dir))
    assert result.status == "invalid"


def test_unpinned_default_is_invalid(tmp_path: Path) -> None:
    fake_root = tmp_path / "project"
    fake_root.mkdir()
    agent_dir = _write_fake_agent_dir(fake_root, pinned=False)
    result = discover_pi_runtime(fake_root, _env(agent_dir))
    assert result.status == "invalid"
    assert result.findings[0].rule_id == "pi-runtime-default-not-pinned"


def test_missing_provider_is_invalid(tmp_path: Path) -> None:
    fake_root = tmp_path / "project"
    fake_root.mkdir()
    agent_dir = _write_fake_agent_dir(fake_root, models_provider="other-provider")
    result = discover_pi_runtime(fake_root, _env(agent_dir))
    assert result.status == "invalid"
    assert result.findings[0].rule_id == "pi-runtime-provider-missing"


def test_missing_model_is_invalid(tmp_path: Path) -> None:
    fake_root = tmp_path / "project"
    fake_root.mkdir()
    agent_dir = _write_fake_agent_dir(fake_root, models_model="other-model")
    result = discover_pi_runtime(fake_root, _env(agent_dir))
    assert result.status == "invalid"
    assert result.findings[0].rule_id == "pi-runtime-model-missing"


def test_plaintext_api_key_is_invalid_and_never_echoed(tmp_path: Path) -> None:
    fake_root = tmp_path / "project"
    fake_root.mkdir()
    agent_dir = _write_fake_agent_dir(fake_root, plaintext_key=True)
    result = discover_pi_runtime(fake_root, _env(agent_dir))
    assert result.status == "invalid"
    assert result.findings[0].rule_id == "pi-runtime-api-key-not-env-ref"
    assert PLAINTEXT_KEY not in json.dumps(result.to_dict(), ensure_ascii=False)


def test_missing_api_key_env_is_needs_input(tmp_path: Path) -> None:
    fake_root = tmp_path / "project"
    fake_root.mkdir()
    agent_dir = _write_fake_agent_dir(fake_root)
    result = discover_pi_runtime(fake_root, _env(agent_dir, with_key=False))
    assert result.status == "needs_input"
    assert result.findings[0].rule_id == "pi-runtime-api-key-env-missing"


def test_missing_extension_is_unavailable(tmp_path: Path) -> None:
    fake_root = tmp_path / "project"
    fake_root.mkdir()
    agent_dir = _write_fake_agent_dir(fake_root, extension=False)
    result = discover_pi_runtime(fake_root, _env(agent_dir))
    assert result.status == "unavailable"
    assert result.findings[0].rule_id == "pi-runtime-extension-missing"


def test_oversized_settings_is_invalid(tmp_path: Path) -> None:
    fake_root = tmp_path / "project"
    fake_root.mkdir()
    agent_dir = _write_fake_agent_dir(fake_root, oversized_settings=True)
    result = discover_pi_runtime(fake_root, _env(agent_dir))
    assert result.status == "invalid"
    assert result.findings[0].rule_id == "pi-runtime-config-oversized"


# ---------------------------------------------------------------------------
# registry projection tests (real source registry)
# ---------------------------------------------------------------------------


def test_pi_cli_registry_projection() -> None:
    registry, findings, _next = load_adapter_registry(ROOT)
    assert registry is not None, findings
    metadata = registry.get_adapter("pi-cli")
    assert metadata is not None
    assert metadata.adapter_type == "agent"
    assert metadata.risk_level == "external"
    assert metadata.source_index == 9  # appended last; existing entries keep their indices
    for capability in metadata.capabilities:
        assert registry.capability_index()[capability] == ["pi-cli"], (
            f"capability '{capability}' must remain unique to pi-cli"
        )


# ---------------------------------------------------------------------------
# CLI integration tests (fake root + injected environment)
# ---------------------------------------------------------------------------


def test_inspect_pi_cli_includes_local_runtime(capsys, tmp_path: Path, monkeypatch) -> None:
    fake_root = _setup_fake_root(tmp_path)
    agent_dir = _write_fake_agent_dir(fake_root)
    monkeypatch.setenv(ENV_DIR_VAR, str(agent_dir))
    monkeypatch.setenv(KEY_VAR, FAKE_KEY_VALUE)

    code = main(["--root", str(fake_root), "orchestration", "adapter", "inspect", "pi-cli", "--json"])
    result = json.loads(capsys.readouterr().out)
    assert code == 0
    local_runtime = result["adapter"]["local_runtime"]
    assert local_runtime["status"] == "ready"
    assert local_runtime["default_provider"] == "deepseek-compat"


def test_inspect_other_adapter_has_no_local_runtime(capsys, tmp_path: Path) -> None:
    fake_root = _setup_fake_root(tmp_path)
    code = main(["--root", str(fake_root), "orchestration", "adapter", "inspect", "shell-local", "--json"])
    result = json.loads(capsys.readouterr().out)
    assert code == 0
    assert "local_runtime" not in result["adapter"]


def test_preflight_fails_closed_without_runtime(capsys, tmp_path: Path, monkeypatch) -> None:
    fake_root = _setup_fake_root(tmp_path)
    monkeypatch.delenv(ENV_DIR_VAR, raising=False)

    code = main([
        "--root", str(fake_root),
        "orchestration", "preflight",
        "--capability", "cli_agent_print",
        "--operation", "cli_agent_print",
        "--json",
    ])
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "blocked"
    assert result["guardrail"]["status"] == "blocked"
    rule_ids = [f["rule_id"] for f in result["guardrail"]["blocking_findings"]]
    assert "pi-runtime-env-dir-missing" in rule_ids
    assert result["guardrail"]["local_runtime"]["status"] == "needs_input"
    assert result["requires_dry_run"] is True


def test_preflight_ready_runtime_still_requires_approval(capsys, tmp_path: Path, monkeypatch) -> None:
    fake_root = _setup_fake_root(tmp_path)
    agent_dir = _write_fake_agent_dir(fake_root)
    monkeypatch.setenv(ENV_DIR_VAR, str(agent_dir))
    monkeypatch.setenv(KEY_VAR, FAKE_KEY_VALUE)

    code = main([
        "--root", str(fake_root),
        "orchestration", "preflight",
        "--capability", "cli_agent_print",
        "--operation", "cli_agent_print",
        "--json",
    ])
    result = json.loads(capsys.readouterr().out)
    assert result["route"]["selected_adapter_id"] == "pi-cli"
    # external risk level keeps the operation approval-gated; no execution authority.
    assert result["status"] == "needs_approval"
    assert result["guardrail"]["status"] == "needs_approval"


def test_route_preview_selects_pi_cli_for_new_capability(capsys, tmp_path: Path) -> None:
    fake_root = _setup_fake_root(tmp_path)
    code = main([
        "--root", str(fake_root),
        "orchestration", "route", "preview",
        "--capability", "cli_agent_tui",
        "--json",
    ])
    result = json.loads(capsys.readouterr().out)
    assert code == 0
    assert result["status"] == "pass"
    assert result["selected_adapter_id"] == "pi-cli"


def test_existing_routes_unaffected_by_new_entry(capsys, tmp_path: Path) -> None:
    fake_root = _setup_fake_root(tmp_path)
    code = main([
        "--root", str(fake_root),
        "orchestration", "route", "preview",
        "--capability", "local_command",
        "--json",
    ])
    result = json.loads(capsys.readouterr().out)
    assert code == 0
    assert result["status"] == "pass"
    assert result["selected_adapter_id"] == "shell-local"
