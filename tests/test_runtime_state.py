from __future__ import annotations

from pathlib import Path

from pce.runtime.engine import Engine
from pce.runtime.state import load_state, save_state
from pce.shared.models import RuntimeState


def test_named_save_load_round_trip(sample_project: Path) -> None:
    state = RuntimeState(
        current_scene="clubhouse",
        player_position=(123, 456),
        variables={"found_key": True},
        inventory=["clubhouse_key"],
        object_enabled={"town_square:mailbox_key": False},
    )

    path = save_state(sample_project, "after_key", state)
    loaded = load_state(sample_project, "after_key")

    assert path.name == "after_key.json"
    assert loaded.current_scene == "clubhouse"
    assert loaded.player_position == (123, 456)
    assert loaded.variables["found_key"] is True
    assert loaded.inventory == ["clubhouse_key"]
    assert loaded.object_enabled["town_square:mailbox_key"] is False


def test_engine_starts_fresh_when_named_slot_is_missing(sample_project: Path) -> None:
    engine = Engine(sample_project, slot="quick")

    assert engine.scene_manager.current_scene_id == "town_square"
    assert engine.state.current_scene == "town_square"
    assert engine.player.position == (120, 390)
