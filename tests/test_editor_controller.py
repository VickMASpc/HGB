from __future__ import annotations

from pathlib import Path

import pytest

from pce.editor.canvas import CanvasState, CanvasTransform
from pce.editor.project_controller import ProjectController
from pce.shared.models import Action, DialogueChoice


def test_editor_can_create_core_scene_objects(sample_project: Path) -> None:
    controller = ProjectController()
    controller.open_project(sample_project)

    controller.add_hotspot()
    controller.add_exit()
    controller.add_npc()
    controller.add_spawn()

    scene = controller.current_scene
    assert scene is not None
    assert scene.hotspots[-1].on_click[0].type == "say"
    assert scene.exits[-1].walk_path
    assert scene.npcs[-1].on_click[0].type == "dialogue"
    assert scene.spawns[-1].id == "spawn_2"


def test_editor_open_rejects_schema_version_mismatch(sample_project: Path) -> None:
    game_path = sample_project / "game.json"
    game_path.write_text(
        game_path.read_text(encoding="utf-8").replace('"schema_version": 2', '"schema_version": 1'),
        encoding="utf-8",
    )

    controller = ProjectController()
    with pytest.raises(ValueError, match="schema_version 2"):
        controller.open_project(sample_project)


def test_editor_canvas_can_select_move_and_resize(sample_project: Path) -> None:
    controller = ProjectController()
    controller.open_project(sample_project)
    scene = controller.current_scene
    assert scene is not None

    canvas = CanvasState()
    assert canvas.begin_drag(scene, (430, 270)) is not None
    canvas.drag_to(scene, (470, 310))
    canvas.end_drag()
    assert scene.hotspots[0].rect == (460, 300, 120, 150)

    assert canvas.begin_drag(scene, (580, 450)) is not None
    canvas.drag_to(scene, (620, 490))
    canvas.end_drag()
    assert scene.hotspots[0].rect == (460, 300, 160, 190)


def test_canvas_transform_fits_scene_and_preserves_logical_drag(sample_project: Path) -> None:
    controller = ProjectController()
    controller.open_project(sample_project)
    scene = controller.current_scene
    assert scene is not None

    view = CanvasTransform.fit(960, 540, 1200, 600)
    assert view.scale == pytest.approx(10 / 9)
    assert view.scene_rect == pytest.approx((66.6667, 0.0, 1133.3333, 600.0))
    assert view.display_to_logical_point((67, 0)) == (0, 0)
    assert view.display_to_logical_point((60, 0)) is None

    canvas = CanvasState()
    canvas.view = view
    start = canvas.view.logical_to_display_point((430, 270))
    end = canvas.view.logical_to_display_point((470, 310))

    logical_start = canvas.view.display_to_logical_point((round(start[0]), round(start[1])))
    logical_end = canvas.view.display_to_logical_point((round(end[0]), round(end[1])))
    assert logical_start is not None
    assert logical_end is not None

    assert canvas.begin_drag(scene, logical_start) is not None
    canvas.drag_to(scene, logical_end)
    canvas.end_drag()
    assert scene.hotspots[0].rect == (460, 300, 120, 150)


def test_canvas_transform_supports_zoom_and_pan() -> None:
    view = CanvasTransform.from_view(960, 540, 960, 540, 2.0, (100, -40))

    assert view.scale == pytest.approx(2.0)
    assert view.scene_rect == pytest.approx((-380, -310, 1540, 770))
    assert view.display_to_logical_point((580, 230)) == (480, 270)


def test_editor_can_duplicate_delete_and_nudge_scene_objects(sample_project: Path) -> None:
    controller = ProjectController()
    controller.open_project(sample_project)
    scene = controller.current_scene
    assert scene is not None

    new_id = controller.duplicate_scene_object("hotspot", "mailbox")
    assert new_id == "mailbox_copy"
    assert scene.hotspots[-1].id == "mailbox_copy"
    assert scene.hotspots[-1].rect == (440, 280, 120, 150)

    canvas = CanvasState()
    canvas.selected_kind = "hotspot"
    canvas.selected_id = "mailbox_copy"
    assert canvas.nudge_selected(scene, 20, -20)
    assert scene.hotspots[-1].rect == (460, 260, 120, 150)

    assert controller.delete_scene_object("hotspot", "mailbox_copy")
    assert all(hotspot.id != "mailbox_copy" for hotspot in scene.hotspots)

    assert controller.undo()
    assert any(hotspot.id == "mailbox_copy" for hotspot in controller.current_scene.hotspots)


def test_controller_renames_objects_uniquely_and_retargets_actions(sample_project: Path) -> None:
    controller = ProjectController()
    controller.open_project(sample_project)

    new_id = controller.update_scene_object("item", "mailbox_key", id="dog")

    assert new_id == "dog_2"
    assert controller.current_scene is not None
    item = controller.current_scene.items[0]
    assert item.id == "dog_2"
    assert item.on_click[1].object_id == "dog_2"
    assert controller.is_dirty


def test_controller_layer_visibility_locking_and_canvas_hit_testing(sample_project: Path) -> None:
    controller = ProjectController()
    controller.open_project(sample_project)
    scene = controller.current_scene
    assert scene is not None

    canvas = CanvasState()
    assert canvas.hit_test(scene, (430, 270)) is not None

    controller.set_layer_state("hotspots", locked=True)
    assert canvas.hit_test(scene, (430, 270)) is None
    canvas.selected_kind = "hotspot"
    canvas.selected_id = "mailbox"
    assert not canvas.nudge_selected(scene, 20, 0)

    controller.set_layer_state("hotspots", locked=False, visible=False)
    assert canvas.hit_test(scene, (430, 270)) is None


def test_duplicate_retargets_self_referential_actions(sample_project: Path) -> None:
    controller = ProjectController()
    controller.open_project(sample_project)
    scene = controller.current_scene
    assert scene is not None

    new_id = controller.duplicate_scene_object("item", "mailbox_key")
    assert new_id == "mailbox_key_copy"
    duplicate = scene.items[-1]

    assert duplicate.on_click[1].object_id == "mailbox_key_copy"


def test_editor_imports_assets_and_updates_project_references(sample_project: Path) -> None:
    controller = ProjectController()
    controller.open_project(sample_project)

    imported = controller.import_asset(sample_project / "assets/sprites/player.png", "sprite")
    controller.assign_player_sprite(imported)

    assert imported == "assets/sprites/player.png"
    assert controller.project is not None
    assert controller.project.player.sprite == imported


def test_editor_undo_redo_and_item_authoring(sample_project: Path) -> None:
    controller = ProjectController()
    controller.open_project(sample_project)
    scene = controller.current_scene
    assert scene is not None

    before = len(scene.items)
    controller.add_scene_item("clubhouse_key")
    assert len(scene.items) == before + 1
    assert controller.undo()
    assert len(controller.current_scene.items) == before
    assert controller.redo()
    assert len(controller.current_scene.items) == before + 1


def test_editor_can_add_dialogue_node_and_set_actions(sample_project: Path) -> None:
    controller = ProjectController()
    controller.open_project(sample_project)
    node = controller.add_dialogue_node("dog")
    assert node.id == "node_4"

    controller.set_actions("item", "mailbox_key", [])
    assert controller.current_scene is not None
    assert controller.current_scene.items[0].on_click == []


def test_controller_updates_dialogue_nodes_and_cleans_choice_targets(sample_project: Path) -> None:
    controller = ProjectController()
    controller.open_project(sample_project)

    controller.update_dialogue_node(
        "dog",
        "hint",
        new_id="clue",
        speaker="Dog",
        text="The mailbox is worth checking.",
        choices=[DialogueChoice(text="Thanks", target="hello")],
        actions=[Action(type="set_variable", variable="heard_hint", value=True)],
    )
    scene = controller.current_scene
    assert scene is not None
    npc = scene.npcs[0]

    assert npc.dialogue_nodes[0].choices[0].target == "clue"
    assert npc.dialogue_nodes[1].id == "clue"
    assert npc.dialogue_nodes[1].actions[0].variable == "heard_hint"

    assert controller.delete_dialogue_node("dog", "clue")
    assert npc.dialogue_nodes[0].choices[0].target is None


def test_controller_reorders_actions_through_set_actions(sample_project: Path) -> None:
    controller = ProjectController()
    controller.open_project(sample_project)
    scene = controller.current_scene
    assert scene is not None

    item = scene.items[0]
    reordered = [item.on_click[2], item.on_click[0], item.on_click[1], item.on_click[3]]
    controller.set_actions("item", "mailbox_key", reordered)

    assert scene.items[0].on_click[0].type == "set_variable"
    assert controller.undo()
    assert controller.current_scene is not None
    assert controller.current_scene.items[0].on_click[0].type == "give_item"


def test_editor_exports_playable_project(sample_project: Path) -> None:
    controller = ProjectController()
    controller.open_project(sample_project)
    export = controller.export_playable()
    assert (export / "game.json").exists()
    assert (export / "RUN.txt").exists()
