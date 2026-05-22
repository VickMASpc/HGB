from __future__ import annotations

from pathlib import Path

import pytest

from pce.editor.canvas import CanvasState, CanvasTransform
from pce.editor.project_controller import ProjectController
from pce.editor.panels.action_list_panel import action_to_json, condition_to_json, merge_action_from_fields
from pce.editor.panels.dialogue_panel import merge_choice_from_fields
from pce.shared.models import Action, Condition, DialogueChoice


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
    assert scene.hotspots[0].rect == (460, 300, 120, 130)

    assert canvas.begin_drag(scene, (580, 430)) is not None
    canvas.drag_to(scene, (620, 470))
    canvas.end_drag()
    assert scene.hotspots[0].rect == (460, 300, 160, 170)


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
    assert scene.hotspots[0].rect == (460, 300, 120, 130)


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
    assert scene.hotspots[-1].rect == (440, 280, 120, 130)

    canvas = CanvasState()
    canvas.selected_kind = "hotspot"
    canvas.selected_id = "mailbox_copy"
    assert canvas.nudge_selected(scene, 20, -20)
    assert scene.hotspots[-1].rect == (460, 260, 120, 130)

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


def test_create_scene_generates_unique_ids_without_overwriting(sample_project: Path) -> None:
    controller = ProjectController()
    controller.open_project(sample_project)
    original = controller.scenes["town_square"]

    controller.create_scene("town_square")

    assert controller.current_scene_id == "town_square_2"
    assert controller.scenes["town_square"] is original
    assert controller.scenes["town_square_2"].id == "town_square_2"
    assert "scenes/town_square.json" in controller.project.scenes
    assert "scenes/town_square_2.json" in controller.project.scenes


def test_scene_item_self_disable_uses_actual_unique_id(sample_project: Path) -> None:
    controller = ProjectController()
    controller.open_project(sample_project)
    scene = controller.current_scene
    assert scene is not None
    scene.items.append(scene.items[0].__class__(id="scene_item_3", item_id="clubhouse_key", rect=(0, 0, 1, 1)))

    controller.add_scene_item("clubhouse_key")

    created = scene.items[-1]
    assert created.id == "scene_item_3_2"
    assert created.on_click[1].type == "set_object_enabled"
    assert created.on_click[1].object_id == created.id


def test_duplicate_scene_and_delete_scene_safeguards(sample_project: Path) -> None:
    controller = ProjectController()
    controller.open_project(sample_project)

    duplicate_id = controller.duplicate_scene("clubhouse")
    duplicate = controller.scenes[duplicate_id]

    assert duplicate_id == "clubhouse_copy"
    assert duplicate.id == duplicate_id
    assert f"scenes/{duplicate_id}.json" in controller.project.scenes

    with pytest.raises(ValueError, match="start scene"):
        controller.delete_scene("town_square")

    with pytest.raises(ValueError, match="referenced"):
        controller.delete_scene("clubhouse")

    assert controller.delete_scene(duplicate_id)
    assert duplicate_id not in controller.scenes


def test_delete_scene_rejects_player_default_and_only_scene(sample_project: Path) -> None:
    controller = ProjectController()
    controller.open_project(sample_project)
    assert controller.project is not None
    controller.project.player.default_scene = "garage"

    with pytest.raises(ValueError, match="default scene"):
        controller.delete_scene("garage")

    only = ProjectController()
    only.open_project(sample_project)
    assert only.project is not None
    keep = only.project.start_scene
    only.scenes = {keep: only.scenes[keep]}
    only.project.scenes = [f"scenes/{keep}.json"]

    with pytest.raises(ValueError, match="only scene"):
        only.delete_scene(keep)


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


def test_action_editor_preserves_nested_sequence_and_conditional_actions() -> None:
    existing = Action(
        type="conditional",
        condition=Condition(type="has_item", item="key"),
        if_actions=[Action(type="sequence", actions=[Action(type="say", speaker="A", text="nested")])],
        else_actions=[Action(type="remove_item", item="key")],
    )

    edited = merge_action_from_fields(
        existing,
        action_type="conditional",
        condition_json=condition_to_json(existing.condition),
        if_actions_json=action_to_json(existing.if_actions),
        else_actions_json=action_to_json(existing.else_actions),
    )

    assert edited == existing
    assert edited.if_actions[0].actions[0].text == "nested"
    assert edited.else_actions[0].type == "remove_item"


def test_action_editor_supports_every_schema_action_type() -> None:
    fixtures = [
        Action(type="say", speaker="Player", text="Hi"),
        Action(type="dialogue", npc="dog", node="hello"),
        Action(type="move_player", path=[(1, 2)]),
        Action(type="change_scene", scene="garage", spawn="start"),
        Action(type="sequence", actions=[Action(type="say", speaker="A", text="B")]),
        Action(type="set_variable", variable="flag", value=True),
        Action(type="give_item", item="key"),
        Action(type="remove_item", item="key"),
        Action(type="set_object_enabled", object_id="mailbox_key", enabled=False),
        Action(
            type="conditional",
            condition=Condition(type="object_enabled", object_id="mailbox_key"),
            if_actions=[Action(type="say", speaker="A", text="enabled")],
            else_actions=[Action(type="say", speaker="A", text="disabled")],
        ),
    ]

    for action in fixtures:
        edited = merge_action_from_fields(
            action,
            action_type=action.type,
            speaker=action.speaker or "",
            text=action.text or "",
            npc=action.npc or "",
            node=action.node or "",
            path=action.path,
            scene=action.scene or "",
            spawn=action.spawn or "",
            item=action.item or "",
            object_id=action.object_id or "",
            variable=action.variable or "",
            value="" if action.value is None else str(action.value),
            enabled=bool(action.enabled),
            actions_json=action_to_json(action.actions),
            condition_json=condition_to_json(action.condition),
            if_actions_json=action_to_json(action.if_actions),
            else_actions_json=action_to_json(action.else_actions),
        )
        assert edited == action


def test_dialogue_choice_editor_preserves_condition_and_actions() -> None:
    choice = DialogueChoice(
        text="Open it.",
        target="opened",
        condition=Condition(type="has_item", item="clubhouse_key"),
        actions=[Action(type="set_variable", variable="opened", value=True)],
    )

    edited = merge_choice_from_fields(
        choice,
        text="Open it.",
        target="opened",
        condition_json=condition_to_json(choice.condition),
        actions_json=action_to_json(choice.actions),
    )

    assert edited == choice


def test_noop_mutations_do_not_mark_dirty(sample_project: Path) -> None:
    controller = ProjectController()
    controller.open_project(sample_project)
    scene = controller.current_scene
    assert scene is not None
    actions = list(scene.items[0].on_click)

    controller.set_layer_state("hotspots", visible=True)
    controller.set_actions("item", "mailbox_key", actions)
    controller.update_scene_object("item", "mailbox_key", id="mailbox_key")

    assert not controller.is_dirty


def test_editor_exports_playable_project(sample_project: Path) -> None:
    controller = ProjectController()
    controller.open_project(sample_project)
    export = controller.export_playable()
    assert (export / "game.json").exists()
    assert (export / "RUN.txt").exists()
