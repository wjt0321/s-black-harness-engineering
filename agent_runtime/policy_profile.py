"""Policy profile resolution from agent registry, explicit override, or default."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from .loader import load_agents


# Minimal fallback for contexts where the registry cannot be loaded.
# The registry-based mapping is preferred.
FALLBACK_AGENT_TO_PROFILE: dict[str, str] = {
    "orchestrator": "s-black",
    "s-black": "s-black",
    "media-agent": "wangcai",
    "wangcai": "wangcai",
    "memory-agent": "dabai",
    "dabai": "dabai",
}


def _load_agent_profile_map(root: Path | None) -> dict[str, str]:
    """Load agent -> policy_profile mapping from the agent registry."""
    mapping: dict[str, str] = {}
    if root is None:
        return mapping
    try:
        data = load_agents(root)
    except (OSError, ValueError):
        return mapping
    for agent in data.get("agents", []):
        agent_id = agent.get("id")
        profile = agent.get("policy_profile")
        if agent_id and profile:
            mapping[agent_id] = profile
    return mapping


def resolve_profile(
    args: argparse.Namespace,
    root: Path | None = None,
) -> str | None:
    """Resolve the policy profile to load.

    Priority:
      1. Explicit --policy file -> None (bypass profile selection).
      2. Explicit --policy-profile value.
      3. --agent or --assignee -> lookup registry mapping, then fallback table.
      4. Default "all".

    Args:
        args: Parsed argparse namespace.
        root: Project root for loading agents registry. If None, only the
              fallback table is used for agent lookup.
    """
    policy = getattr(args, "policy", None)
    if policy:
        return None

    profile = getattr(args, "policy_profile", None)
    if profile:
        return profile

    agent = getattr(args, "agent", None) or getattr(args, "assignee", None)
    if agent:
        registry_map = _load_agent_profile_map(root)
        return registry_map.get(agent) or FALLBACK_AGENT_TO_PROFILE.get(agent, "all")

    return "all"


def resolve_profile_from_agent(agent_id: str | None, root: Path | None = None) -> str:
    """Resolve profile from a raw agent id, defaulting to 'all'."""
    if not agent_id:
        return "all"
    registry_map = _load_agent_profile_map(root)
    return registry_map.get(agent_id) or FALLBACK_AGENT_TO_PROFILE.get(agent_id, "all")
