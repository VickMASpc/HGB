from __future__ import annotations

from pathlib import Path

from pce.editor.canvas import CanvasState
from pce.editor.project_controller import ProjectController


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


def test_editor_exports_playable_project(sample_project: Path) -> None:
    controller = ProjectController()
    controller.open_project(sample_project)
    export = controller.export_playable()
    assert (export / "game.json").exists()
    assert (export / "RUN.txt").exists()
