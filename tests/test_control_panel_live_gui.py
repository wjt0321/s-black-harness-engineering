from __future__ import annotations

from pathlib import Path


def test_live_panel_builds_fresh_read_only_snapshot_with_bounded_chain_collection(monkeypatch, tmp_path: Path) -> None:
    from agent_runtime import control_panel_live_gui as live_gui

    calls: list[dict[str, object]] = []

    class Snapshot:
        status = "pass"

        def to_dict(self):
            return {"status": "pass", "sections": {}, "source": {}, "summary": {}}

        def exit_code(self) -> int:
            return 0

    def fake_snapshot(root: Path, **kwargs: object) -> Snapshot:
        calls.append({"root": root, **kwargs})
        return Snapshot()

    monkeypatch.setattr(live_gui, "build_control_panel_snapshot", fake_snapshot)

    result = live_gui.build_live_control_panel_snapshot(
        tmp_path,
        evaluated_at="2026-07-28T12:00:05Z",
        chain_limit=12,
    )

    assert result.to_dict()["status"] == "pass"
    assert calls == [
        {
            "root": tmp_path.resolve(),
            "external_agent_evaluated_at": "2026-07-28T12:00:05Z",
            "external_agent_chain_limit": 12,
        }
    ]


def test_live_panel_rejects_out_of_bound_refresh_and_chain_limits() -> None:
    from agent_runtime.control_panel_live_gui import LiveControlPanelError, validate_live_control_panel_options

    assert validate_live_control_panel_options(refresh_seconds=5, chain_limit=20) == (5, 20)
    for refresh_seconds, chain_limit in ((1, 20), (61, 20), (5, 0), (5, 21)):
        try:
            validate_live_control_panel_options(
                refresh_seconds=refresh_seconds,
                chain_limit=chain_limit,
            )
        except LiveControlPanelError:
            continue
        raise AssertionError("invalid live panel options must fail closed")
