"""Read-only Pi Coding Agent local runtime discovery (Stage 60).

This module projects the *local* Pi CLI runtime state (the project-local,
git-ignored ``.runtime/pi-agent`` directory selected by ``PI_CODING_AGENT_DIR``)
into a deterministic, value-safe readiness read model. It exists so the
control plane can represent the Pi adapter's local availability without ever
invoking Pi, calling a model, or reading credential material.

Hard boundaries:

- No process execution, no network access, no writes.
- Bounded reads (64 KiB) of ``settings.json`` / ``models.json`` only.
- ``auth.json``, ``sessions/``, ``.env*`` and any credential-like file are
  never opened; ``loader.is_safe_to_read`` is enforced before every read.
- Secret values are never echoed: an ``apiKey`` is only accepted in
  ``$ENV_VAR`` reference form, and only the referenced variable *name* and
  presence booleans are reported.

The result is deterministic for the same filesystem/environment inputs: check
order is fixed, no timestamps, no randomness.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from .loader import is_safe_to_read, normalize_path
from .result import Finding


ENV_DIR_VAR = "PI_CODING_AGENT_DIR"
RUNTIME_ROOT_REL = ".runtime"
EXTENSION_REL = Path("extensions") / "pi-preflight-bridge" / "index.ts"
SETTINGS_NAME = "settings.json"
MODELS_NAME = "models.json"
MAX_CONFIG_BYTES = 64 * 1024

_ENV_REF_PATTERN = re.compile(r"^\$[A-Za-z_][A-Za-z0-9_]*$")

# Overall status precedence, most severe first (fail closed).
_STATUS_ORDER = ("invalid", "unavailable", "needs_input", "ready")


@dataclass(frozen=True)
class PiRuntimeCheck:
    """A single deterministic readiness check."""

    check_id: str
    status: str  # "pass" | one of _STATUS_ORDER (failure severity)
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return {"check_id": self.check_id, "status": self.status, "detail": self.detail}


@dataclass
class PiRuntimeStatus:
    """Value-safe readiness projection of the local Pi runtime."""

    status: str = "unavailable"
    agent_dir: str | None = None
    default_provider: str | None = None
    default_model: str | None = None
    checks: list[PiRuntimeCheck] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    next_action: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "status": self.status,
            "agent_dir": self.agent_dir,
            "default_provider": self.default_provider,
            "default_model": self.default_model,
            "checks": [c.to_dict() for c in self.checks],
        }
        if self.findings:
            d["findings"] = [f.to_dict() for f in self.findings]
        if self.next_action is not None:
            d["next_action"] = self.next_action
        return d


def _finding(rule_id: str, severity: str, action: str, message: str) -> Finding:
    return Finding(rule_id=rule_id, severity=severity, action=action, message=message)


def _read_bounded_json(path: Path) -> tuple[Any | None, str | None]:
    """Read a bounded, safe JSON config file.

    Returns ``(data, error_rule_id)``. Never raises; never reads files that
    fail ``is_safe_to_read``; caps size at ``MAX_CONFIG_BYTES``.
    """
    if not is_safe_to_read(path):
        return None, "pi-runtime-unsafe-config-path"
    try:
        size = path.stat().st_size
    except OSError:
        return None, "pi-runtime-config-unreadable"
    if size > MAX_CONFIG_BYTES:
        return None, "pi-runtime-config-oversized"
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh), None
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None, "pi-runtime-config-invalid-json"


def _is_contained(root: Path, candidate: Path) -> bool:
    """Return True if candidate resolves inside ``root`` (prefix comparison)."""
    root_norm = normalize_path(root.resolve()).rstrip("/") + "/"
    cand_norm = normalize_path(candidate.resolve())
    return cand_norm.startswith(root_norm)


def discover_pi_runtime(
    root: Path,
    env: Mapping[str, str] | None = None,
) -> PiRuntimeStatus:
    """Probe the local Pi runtime read-only and project a readiness status.

    ``env`` defaults to ``os.environ``; tests inject an explicit mapping.
    The probe never executes Pi, never touches the network, and never reads
    auth/session/credential files.
    """
    environ: Mapping[str, str] = os.environ if env is None else env
    result = PiRuntimeStatus()

    def fail(check_id: str, status: str, detail: str, rule_id: str, message: str) -> None:
        result.checks.append(PiRuntimeCheck(check_id=check_id, status=status, detail=detail))
        severity = "error" if status in {"invalid", "unavailable"} else "warn"
        result.findings.append(_finding(rule_id, severity, status, message))

    # 1. PI_CODING_AGENT_DIR present.
    raw_dir = environ.get(ENV_DIR_VAR, "")
    if not raw_dir.strip():
        fail(
            "env_dir_set",
            "needs_input",
            f"{ENV_DIR_VAR} is not set",
            "pi-runtime-env-dir-missing",
            f"{ENV_DIR_VAR} is not set; the local Pi agent dir is unknown.",
        )
        return _finalize(result)

    agent_dir = Path(raw_dir).expanduser()
    result.agent_dir = normalize_path(agent_dir)
    if not agent_dir.is_absolute():
        agent_dir = (root / agent_dir).resolve()
        result.agent_dir = normalize_path(agent_dir)

    # 2. Containment: the agent dir must live inside <root>/.runtime.
    runtime_root = (root / RUNTIME_ROOT_REL).resolve()
    if not _is_contained(runtime_root, agent_dir):
        fail(
            "agent_dir_contained",
            "invalid",
            "agent dir escapes <root>/.runtime",
            "pi-runtime-agent-dir-escape",
            "PI_CODING_AGENT_DIR resolves outside the project-local .runtime tree; refusing to inspect it.",
        )
        return _finalize(result)
    result.checks.append(PiRuntimeCheck("agent_dir_contained", "pass", "inside <root>/.runtime"))

    # 3. Agent dir exists.
    if not agent_dir.is_dir():
        fail(
            "agent_dir_exists",
            "unavailable",
            "agent dir does not exist",
            "pi-runtime-agent-dir-missing",
            "The configured Pi agent dir does not exist.",
        )
        return _finalize(result)
    result.checks.append(PiRuntimeCheck("agent_dir_exists", "pass", "agent dir present"))

    # 4. settings.json pinned default provider/model.
    settings_path = agent_dir / SETTINGS_NAME
    settings, settings_error = _read_bounded_json(settings_path)
    if settings_error is not None or not isinstance(settings, dict):
        fail(
            "settings_pinned_default",
            "invalid",
            f"settings.json unreadable ({settings_error or 'not an object'})",
            settings_error or "pi-runtime-config-invalid-json",
            "settings.json is missing, oversized, or not valid JSON.",
        )
        return _finalize(result)
    default_provider = settings.get("defaultProvider")
    default_model = settings.get("defaultModel")
    if not (isinstance(default_provider, str) and default_provider.strip()) or not (
        isinstance(default_model, str) and default_model.strip()
    ):
        fail(
            "settings_pinned_default",
            "invalid",
            "defaultProvider/defaultModel missing",
            "pi-runtime-default-not-pinned",
            "settings.json does not pin defaultProvider/defaultModel; entry resolution would drift.",
        )
        return _finalize(result)
    result.default_provider = default_provider
    result.default_model = default_model
    result.checks.append(
        PiRuntimeCheck(
            "settings_pinned_default",
            "pass",
            f"defaultProvider={default_provider} defaultModel={default_model}",
        )
    )

    # 5. models.json provider/model present with env-reference apiKey.
    models_path = agent_dir / MODELS_NAME
    models, models_error = _read_bounded_json(models_path)
    if models_error is not None or not isinstance(models, dict):
        fail(
            "models_provider_present",
            "invalid",
            f"models.json unreadable ({models_error or 'not an object'})",
            models_error or "pi-runtime-config-invalid-json",
            "models.json is missing, oversized, or not valid JSON.",
        )
        return _finalize(result)
    providers = models.get("providers")
    provider_cfg = providers.get(default_provider) if isinstance(providers, dict) else None
    if not isinstance(provider_cfg, dict):
        fail(
            "models_provider_present",
            "invalid",
            f"provider '{default_provider}' not in models.json",
            "pi-runtime-provider-missing",
            f"models.json does not define the pinned provider '{default_provider}'.",
        )
        return _finalize(result)
    model_ids = [
        m.get("id")
        for m in provider_cfg.get("models", [])
        if isinstance(m, dict) and isinstance(m.get("id"), str)
    ]
    if default_model not in model_ids:
        fail(
            "models_provider_present",
            "invalid",
            f"model '{default_model}' not in provider '{default_provider}'",
            "pi-runtime-model-missing",
            f"models.json provider '{default_provider}' does not define pinned model '{default_model}'.",
        )
        return _finalize(result)
    result.checks.append(
        PiRuntimeCheck("models_provider_present", "pass", f"{default_provider}/{default_model} defined")
    )

    api_key = provider_cfg.get("apiKey")
    if not (isinstance(api_key, str) and _ENV_REF_PATTERN.match(api_key)):
        fail(
            "api_key_env_reference",
            "invalid",
            "apiKey is not a $ENV_VAR reference",
            "pi-runtime-api-key-not-env-ref",
            "Provider apiKey is missing or not an environment-variable reference; refusing to inspect further.",
        )
        return _finalize(result)
    api_key_env_name = api_key[1:]
    result.checks.append(
        PiRuntimeCheck("api_key_env_reference", "pass", f"apiKey references ${api_key_env_name}")
    )

    # 6. Referenced API key env var present (presence only; value never read out).
    if not environ.get(api_key_env_name, "").strip():
        fail(
            "api_key_env_present",
            "needs_input",
            f"${api_key_env_name} is not set",
            "pi-runtime-api-key-env-missing",
            f"Environment variable {api_key_env_name} is not set; the provider has no usable credential.",
        )
        return _finalize(result)
    result.checks.append(
        PiRuntimeCheck("api_key_env_present", "pass", f"${api_key_env_name} present (value withheld)")
    )

    # 7. Host preflight bridge extension present.
    extension_path = agent_dir / EXTENSION_REL
    if not extension_path.is_file():
        fail(
            "preflight_extension_present",
            "unavailable",
            f"{normalize_path(EXTENSION_REL)} missing",
            "pi-runtime-extension-missing",
            "The pi-preflight-bridge extension is not deployed in the local agent dir.",
        )
        return _finalize(result)
    result.checks.append(
        PiRuntimeCheck("preflight_extension_present", "pass", "pi-preflight-bridge extension present")
    )

    return _finalize(result)


def _finalize(result: PiRuntimeStatus) -> PiRuntimeStatus:
    """Compute the overall status (fail closed) and next_action."""
    worst = "ready"
    for check in result.checks:
        if check.status == "pass":
            continue
        if _STATUS_ORDER.index(check.status) < _STATUS_ORDER.index(worst):
            worst = check.status
    result.status = worst
    result.next_action = {
        "ready": "Local Pi runtime is ready for read-only projection; execution still requires separate authorization.",
        "needs_input": "Set the missing environment variable(s), then re-run the readiness probe.",
        "unavailable": "Provision the project-local Pi agent dir (see docs/107) before relying on this adapter.",
        "invalid": "Fix the local Pi runtime configuration (see docs/108); the adapter stays blocked until the probe passes.",
    }[worst]
    return result
