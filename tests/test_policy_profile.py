"""Tests for policy profile resolution via agent registry and overrides."""

from pathlib import Path

from agent_runtime.cli import main
from agent_runtime.policy_profile import resolve_profile, resolve_profile_from_agent


ROOT = Path(__file__).resolve().parents[1]


def _namespace(**kwargs) -> object:
    class Namespace:
        pass

    ns = Namespace()
    for key, value in kwargs.items():
        setattr(ns, key, value)
    for key in ("policy", "policy_profile", "agent", "assignee"):
        if not hasattr(ns, key):
            setattr(ns, key, None)
    return ns


def _write_agents_sample(tmp_path: Path, agents: list[dict]) -> Path:
    agents_file = tmp_path / "agents" / "agents.sample.json"
    agents_file.parent.mkdir(parents=True, exist_ok=True)
    agents_file.write_text(
        '{"version":1,"agents":' + str(agents).replace("'", '"') + "}",
        encoding="utf-8",
    )
    return agents_file


def test_resolve_profile_explicit_policy_returns_none():
    ns = _namespace(policy="policies/s-black.sample.policy.json")
    assert resolve_profile(ns) is None


def test_resolve_profile_explicit_profile_priority_over_agent():
    ns = _namespace(policy_profile="wangcai", agent="orchestrator")
    assert resolve_profile(ns, ROOT) == "wangcai"


def test_resolve_profile_reads_registry_for_orchestrator(tmp_path):
    _write_agents_sample(
        tmp_path,
        [{"id": "orchestrator", "policy_profile": "s-black"}],
    )
    ns = _namespace(agent="orchestrator")
    assert resolve_profile(ns, tmp_path) == "s-black"


def test_resolve_profile_registry_overrides_fallback(tmp_path):
    # Fallback says orchestrator -> s-black; registry says orchestrator -> wangcai.
    _write_agents_sample(
        tmp_path,
        [{"id": "orchestrator", "policy_profile": "wangcai"}],
    )
    ns = _namespace(agent="orchestrator")
    assert resolve_profile(ns, tmp_path) == "wangcai"


def test_resolve_profile_unknown_agent_defaults_all(tmp_path):
    _write_agents_sample(
        tmp_path,
        [{"id": "orchestrator", "policy_profile": "s-black"}],
    )
    ns = _namespace(agent="unknown-agent")
    assert resolve_profile(ns, tmp_path) == "all"


def test_resolve_profile_missing_registry_uses_fallback():
    # tmp_path has no agents.sample.json, so fallback table is used.
    ns = _namespace(agent="orchestrator")
    assert resolve_profile(ns, ROOT) == "s-black"


def test_resolve_profile_assignee_fallback(tmp_path):
    _write_agents_sample(
        tmp_path,
        [{"id": "memory-agent", "policy_profile": "dabai"}],
    )
    ns = _namespace(assignee="memory-agent")
    assert resolve_profile(ns, tmp_path) == "dabai"


def test_resolve_profile_default_all():
    ns = _namespace()
    assert resolve_profile(ns, ROOT) == "all"


def test_resolve_profile_from_agent_uses_registry(tmp_path):
    _write_agents_sample(
        tmp_path,
        [{"id": "media-agent", "policy_profile": "wangcai"}],
    )
    assert resolve_profile_from_agent("media-agent", tmp_path) == "wangcai"


def test_resolve_profile_from_agent_unknown(tmp_path):
    _write_agents_sample(
        tmp_path,
        [{"id": "media-agent", "policy_profile": "wangcai"}],
    )
    assert resolve_profile_from_agent("unknown", tmp_path) == "all"


def test_cli_check_action_with_agent_orchestrator_uses_s_black(capsys):
    code = main([
        "--root", str(ROOT),
        "check", "action",
        "--adapter", "github-cli",
        "--operation", "git_push",
        "--target", "origin/main",
        "--agent", "orchestrator",
    ])
    captured = capsys.readouterr()
    assert code == 3
    assert "NEEDS_APPROVAL" in captured.out


def test_cli_policies_list_with_agent_media_agent_shows_wangcai_only(capsys):
    code = main([
        "--root", str(ROOT),
        "--agent", "media-agent",
        "policies", "list",
    ])
    captured = capsys.readouterr()
    assert code == 0
    assert "wangcai.sample.policy.json" in captured.out
    assert "s-black.sample.policy.json" not in captured.out
    assert "dabai.sample.policy.json" not in captured.out


def test_cli_policies_list_with_policy_profile_overrides_agent(capsys):
    code = main([
        "--root", str(ROOT),
        "--agent", "media-agent",
        "--policy-profile", "dabai",
        "policies", "list",
    ])
    captured = capsys.readouterr()
    assert code == 0
    assert "dabai.sample.policy.json" in captured.out
    assert "wangcai.sample.policy.json" not in captured.out


def test_cli_check_text_with_agent_memory_agent_uses_dabai(capsys):
    token = "sk-" + "Z" * 24
    code = main([
        "--root", str(ROOT),
        "check", "text",
        "--text", token,
        "--agent", "memory-agent",
    ])
    captured = capsys.readouterr()
    assert code == 2
    assert "BLOCKED" in captured.out


def test_cli_check_path_with_assignee_orchestrator_uses_s_black(capsys):
    code = main([
        "--root", str(ROOT),
        "check", "path",
        "./workspaces/orchestrator/plan.md",
        "--write",
        "--assignee", "orchestrator",
    ])
    captured = capsys.readouterr()
    # s-black policy does not mark orchestrator workspace as readonly, so pass.
    assert code == 0
    assert "PASS" in captured.out


def test_cli_explicit_policy_file_overrides_agent(capsys, tmp_path):
    policy_file = tmp_path / "empty.policy.json"
    policy_file.write_text(
        '{"version":1,"name":"empty","path_rules":[],"secret_patterns":[],'
        '"command_rules":[],"publish_rules":[],"completion_rules":[]}',
        encoding="utf-8",
    )
    token = "sk-" + "Z" * 24
    code = main([
        "--root", str(ROOT),
        "--policy", str(policy_file),
        "--agent", "orchestrator",
        "check", "text",
        "--text", token,
    ])
    captured = capsys.readouterr()
    assert code == 0
    assert "PASS" in captured.out
