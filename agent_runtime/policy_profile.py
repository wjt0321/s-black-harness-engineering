"""Policy profile resolution from agent id, assignee, or explicit override."""

from __future__ import annotations

import argparse
from typing import Any


# Mapping from agent id / owner name / assignee to sample policy profile.
AGENT_TO_PROFILE: dict[str, str] = {
    "orchestrator": "s-black",
    "s-black": "s-black",
    "media-agent": "wangcai",
    "wangcai": "wangcai",
    "memory-agent": "dabai",
    "dabai": "dabai",
}


def resolve_profile(args: argparse.Namespace) -> str | None:
    """Resolve the policy profile to load.

    Priority:
      1. Explicit --policy file -> None (bypass profile selection).
      2. Explicit --policy-profile value.
      3. --agent or --assignee -> mapped profile, defaulting to "all".
      4. Default "all".
    """
    policy = getattr(args, "policy", None)
    if policy:
        return None

    profile = getattr(args, "policy_profile", None)
    if profile:
        return profile

    agent = getattr(args, "agent", None) or getattr(args, "assignee", None)
    if agent:
        return AGENT_TO_PROFILE.get(agent, "all")

    return "all"


def resolve_profile_from_agent(agent_id: str | None) -> str:
    """Resolve profile from a raw agent id, defaulting to 'all'."""
    if not agent_id:
        return "all"
    return AGENT_TO_PROFILE.get(agent_id, "all")
