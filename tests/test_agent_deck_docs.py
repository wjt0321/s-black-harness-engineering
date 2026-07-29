from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_agent_deck_documents_declare_a_fixed_safe_snapshot_handoff() -> None:
    stage = (ROOT / "docs/143-agent-deck-platform-mvp.md").read_text(encoding="utf-8")
    spec = (
        ROOT / "docs/superpowers/specs/2026-07-29-agent-deck-platform-mvp-design.md"
    ).read_text(encoding="utf-8")
    assert "agent-deck/read-model/v1" in spec
    assert ".runtime/agent-deck/v1/agent-deck.snapshot.json" in spec
    assert "P0 不新增 UI dispatch" in stage