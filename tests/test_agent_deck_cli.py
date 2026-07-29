from __future__ import annotations

import json
from pathlib import Path


def test_agent_deck_exporter_writes_only_fixed_runtime_snapshot(tmp_path: Path, monkeypatch) -> None:
    from agent_runtime import agent_deck_projection as projection

    monkeypatch.setattr(
        projection,
        "build_agent_deck_snapshot",
        lambda *_args, **_kwargs: projection.AgentDeckSnapshot(
            "pass", {"status": "pass", "schema_version": "agent-deck/read-model/v1", "source_mode": "runtime"}
        ),
    )
    preview = projection.export_agent_deck_snapshot(tmp_path, evaluated_at="2026-07-29T09:00:00Z", commit=False).to_dict()
    fixed = tmp_path / ".runtime/agent-deck/v1/agent-deck.snapshot.json"
    assert preview["export"]["would_write"] is True
    assert not fixed.exists()

    committed = projection.export_agent_deck_snapshot(tmp_path, evaluated_at="2026-07-29T09:00:00Z", commit=True).to_dict()
    assert fixed.exists()
    assert committed["export"] == {"path": ".runtime/agent-deck/v1/agent-deck.snapshot.json", "written": True, "atomic": True}
    assert json.loads(fixed.read_text(encoding="utf-8"))["schema_version"] == "agent-deck/read-model/v1"


def test_agent_deck_exporter_keeps_previous_snapshot_on_oversize(tmp_path: Path, monkeypatch) -> None:
    from agent_runtime import agent_deck_projection as projection

    fixed = tmp_path / ".runtime/agent-deck/v1/agent-deck.snapshot.json"
    fixed.parent.mkdir(parents=True)
    fixed.write_text('{"prior":true}\n', encoding="utf-8")
    monkeypatch.setattr(
        projection,
        "build_agent_deck_snapshot",
        lambda *_args, **_kwargs: projection.AgentDeckSnapshot("pass", {"x": "a" * (projection.MAX_SNAPSHOT_BYTES + 1)}),
    )
    result = projection.export_agent_deck_snapshot(tmp_path, evaluated_at="2026-07-29T09:00:00Z", commit=True)
    assert result.status == "validation_failed"
    assert fixed.read_text(encoding="utf-8") == '{"prior":true}\n'