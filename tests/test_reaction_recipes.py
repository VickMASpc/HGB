from __future__ import annotations

from pathlib import Path

from pce.editor.panels.reaction_recipes import (
    RECIPE_TEMPLATES,
    collect_scene_connections,
    default_action_for_recipe,
    exit_validation_warnings,
    numbered_recipe_labels,
    recipe_label,
    recipe_validation_warnings,
    scene_card_label,
    scene_id_from_card_label,
)
from pce.editor.project_controller import ProjectController
from pce.shared.models import Action, Severity, ValidationIssue


def test_recipe_templates_map_to_existing_action_models(sample_project: Path) -> None:
    controller = ProjectController()
    controller.open_project(sample_project)

    actions = {
        name: default_action_for_recipe(
            recipe,
            owner_id="mailbox_key",
            current_scene=controller.current_scene,
        )
        for name, recipe in RECIPE_TEMPLATES.items()
    }

    assert actions["Player says..."] == Action(type="say", speaker="Player", text="New line.")
    assert actions["Start conversation..."].type == "dialogue"
    assert actions["Give item..."].type == "give_item"
    assert actions["Remove this object..."] == Action(
        type="set_object_enabled",
        object_id="mailbox_key",
        enabled=False,
    )
    assert actions["Go to scene..."].type == "change_scene"
    assert actions["Only if..."].type == "conditional"


def test_recipe_labels_are_sentence_like_and_ordered() -> None:
    actions = [
        Action(type="say", speaker="Player", text="That looks useful."),
        Action(type="dialogue", npc="dog", node="hello"),
        Action(type="give_item", item="clubhouse_key"),
        Action(type="set_object_enabled", object_id="mailbox_key", enabled=False),
        Action(type="change_scene", scene="clubhouse", spawn="door"),
    ]

    labels = numbered_recipe_labels(actions, owner_id="mailbox_key")

    assert labels == [
        '1. Player says "That looks useful."',
        "2. Start conversation with dog at hello",
        "3. Give item clubhouse_key",
        "4. Remove this object",
        "5. Go to scene clubhouse at door",
    ]
    assert recipe_label(actions[3], owner_id="other") == "Remove object mailbox_key"


def test_controller_reaction_operations_are_undoable(sample_project: Path) -> None:
    controller = ProjectController()
    controller.open_project(sample_project)
    assert controller.current_scene is not None

    item = controller.current_scene.items[0]
    before = len(item.on_click)
    added_index = controller.add_action("item", item.id, Action(type="say", speaker="Player", text="Hi"))
    copied_index = controller.duplicate_action("item", item.id, added_index)
    moved_index = controller.move_action("item", item.id, copied_index, -1)

    assert len(item.on_click) == before + 2
    assert moved_index == added_index
    assert controller.remove_action("item", item.id, moved_index)
    assert len(item.on_click) == before + 1

    assert controller.undo()
    assert len(controller.current_scene.items[0].on_click) == before + 2
    assert controller.undo()
    assert controller.current_scene.items[0].on_click[-1].text == "Hi"
    assert controller.undo()
    assert len(controller.current_scene.items[0].on_click) == before + 1
    assert controller.undo()
    assert len(controller.current_scene.items[0].on_click) == before
    assert controller.redo()
    assert len(controller.current_scene.items[0].on_click) == before + 1


def test_scene_transition_edit_uses_scene_cards_and_is_undoable(sample_project: Path) -> None:
    controller = ProjectController()
    controller.open_project(sample_project)
    assert controller.current_scene is not None
    exit_data = controller.current_scene.exits[0]
    target = controller.scenes["garage"]
    card = scene_card_label(target)

    controller.update_exit_destination(exit_data.id, scene_id_from_card_label(card, controller.scenes), "door")

    assert exit_data.target_scene == "garage"
    assert exit_data.target_spawn == "door"
    assert controller.undo()
    assert controller.current_scene.exits[0].target_scene == "clubhouse"


def test_story_map_collects_exit_and_action_scene_connections(sample_project: Path) -> None:
    controller = ProjectController()
    controller.open_project(sample_project)
    assert controller.current_scene is not None
    controller.current_scene.hotspots[0].on_click.append(
        Action(type="change_scene", scene="garage", spawn="door")
    )

    connections = collect_scene_connections(controller.scenes)
    pairs = {(item.source_scene, item.target_scene, item.kind) for item in connections}

    assert ("town_square", "clubhouse", "exit") in pairs
    assert ("town_square", "garage", "hotspot") in pairs


def test_recipe_and_exit_validation_warnings_are_contextual() -> None:
    issues = [
        ValidationIssue(
            Severity.ERROR,
            "MISSING_ACTION_TARGET",
            "change_scene action references missing scene 'missing'.",
            object_id="door",
        ),
        ValidationIssue(
            Severity.ERROR,
            "MISSING_TARGET_SCENE",
            "Exit 'door' references missing scene 'missing'.",
            object_id="door",
        ),
    ]
    actions = [Action(type="change_scene", scene="missing", spawn="")]

    recipe_warnings = recipe_validation_warnings("door", actions, issues)
    exit_warnings = exit_validation_warnings("door", issues)

    assert "Choose where the player appears." in recipe_warnings[0]
    assert "change_scene action references missing scene 'missing'." in recipe_warnings[0]
    assert exit_warnings == [
        "change_scene action references missing scene 'missing'.",
        "Exit 'door' references missing scene 'missing'.",
    ]
