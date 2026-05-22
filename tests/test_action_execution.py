from __future__ import annotations

from pathlib import Path

from pce.runtime.actions import ActionRunner, RuntimeContext
from pce.runtime.dialogue import DialogueSystem
from pce.runtime.player import Player
from pce.runtime.scene_manager import SceneManager
from pce.shared.models import Action
from pce.shared.serialization import load_project, load_scenes


def _runner(sample_project: Path) -> tuple[ActionRunner, RuntimeContext]:
    project = load_project(sample_project)
    manager = SceneManager(project, load_scenes(sample_project, project))
    context = RuntimeContext(manager, Player(manager.spawn_position()), DialogueSystem())
    return ActionRunner(context), context


def test_say_action_creates_subtitle(sample_project: Path) -> None:
    runner, context = _runner(sample_project)
    runner.start([Action(type="say", speaker="Player", text="It's locked.")])
    assert context.dialogue.current is not None
    assert context.dialogue.current.text == "It's locked."


def test_dialogue_action_advances_lines(sample_project: Path) -> None:
    runner, context = _runner(sample_project)
    runner.start([Action(type="dialogue", npc="dog")])
    assert context.dialogue.current is not None
    assert context.dialogue.current.text == "Woof!"
    context.dialogue.advance()
    assert context.dialogue.current is not None
    assert context.dialogue.current.text == "Let's go explore."


def test_move_player_follows_path(sample_project: Path) -> None:
    runner, context = _runner(sample_project)
    runner.start([Action(type="move_player", path=[(200, 390), (240, 390)])])
    for _ in range(60):
        context.player.update(1 / 60)
        runner.update()
    assert context.player.position == (240, 390)


def test_sequence_executes_in_order(sample_project: Path) -> None:
    runner, context = _runner(sample_project)
    runner.start(
        [
            Action(
                type="sequence",
                actions=[
                    Action(type="say", speaker="Player", text="First"),
                    Action(type="say", speaker="Player", text="Second"),
                ],
            )
        ]
    )
    assert context.dialogue.current is not None
    assert context.dialogue.current.text == "First"
    context.dialogue.advance()
    runner.update()
    assert context.dialogue.current is not None
    assert context.dialogue.current.text == "Second"


def test_change_scene_updates_scene_manager(sample_project: Path) -> None:
    runner, context = _runner(sample_project)
    runner.start([Action(type="change_scene", scene="clubhouse", spawn="entrance")])
    assert context.scene_manager.current_scene_id == "clubhouse"
    assert context.player.position == (120, 390)

