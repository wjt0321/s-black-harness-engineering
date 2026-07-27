"""Tests for the read-only Agent Socket Registry projection."""

from __future__ import annotations

import json
from pathlib import Path

from agent_runtime.cli import main

ROOT = Path(__file__).resolve().parents[1]


def _files(root: Path) -> dict[Path, bytes]:
    return {
        relative: path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
        for relative in [path.relative_to(root)]
        if relative.parts[:2] != (".runtime", "external-agent-status")
    }


def test_socket_list_projects_the_declared_agent_plugs(capsys) -> None:
    code = main(["--root", str(ROOT), "orchestration", "socket", "list", "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["status"] == "pass"
    sockets = {socket["socket_id"]: socket for socket in payload["sockets"]}
    assert {"pi-cli", "kimi-code-acp", "claude-code-acp", "omp-acp"} <= set(sockets)
    assert sockets["pi-cli"]["invocation_mode"] == "local_cli"
    assert sockets["kimi-code-acp"]["invocation_mode"] == "acp_delegate"
    assert all(socket["availability"] == "declared" for socket in sockets.values())
    assert all("quota probe" in socket["availability_detail"] for socket in sockets.values())


def test_socket_list_filters_by_declared_capability(capsys) -> None:
    code = main([
        "--root", str(ROOT), "orchestration", "socket", "list",
        "--capability", "light_coding", "--json",
    ])
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert {socket["socket_id"] for socket in payload["sockets"]} == {
        "kimi-code-acp", "omp-acp"
    }


def test_socket_inspect_and_unknown_socket_are_safe(capsys) -> None:
    code = main([
        "--root", str(ROOT), "orchestration", "socket", "inspect", "claude-code-acp", "--json",
    ])
    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["socket"]["socket_id"] == "claude-code-acp"
    assert "quality_review" in payload["socket"]["capabilities"]

    code = main([
        "--root", str(ROOT), "orchestration", "socket", "inspect", "shell-local", "--json",
    ])
    payload = json.loads(capsys.readouterr().out)
    assert code != 0
    assert payload["status"] == "needs_input"
    assert payload["findings"][0]["rule_id"] == "socket-not-found"


def test_socket_queries_do_not_write_project_files(capsys) -> None:
    before = _files(ROOT)
    assert main(["--root", str(ROOT), "orchestration", "socket", "list", "--json"]) == 0
    capsys.readouterr()
    assert main([
        "--root", str(ROOT), "orchestration", "socket", "inspect", "pi-cli", "--json",
    ]) == 0
    capsys.readouterr()
    assert _files(ROOT) == before
