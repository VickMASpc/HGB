from __future__ import annotations

from collections.abc import Callable

from pce.editor.panels.properties_panel import WORKSPACES


def build_workspace_nav(dpg, app) -> None:
    with dpg.group(horizontal=True):
        dpg.add_text("Story Studio")
        dpg.add_spacer(width=18)
        for workspace in WORKSPACES:
            dpg.add_button(
                label=workspace,
                tag=f"workspace_{workspace.lower()}",
                callback=lambda _s=None, _a=None, value=workspace: app._set_workspace(dpg, value),
            )
        dpg.add_spacer(width=18)
        dpg.add_checkbox(
            tag="simple_mode",
            label="Simple",
            default_value=True,
            callback=lambda _s, a: app._set_simple_mode(dpg, a),
        )
        dpg.add_button(label="Open", callback=lambda: dpg.show_item("project_dialog"))
        dpg.add_button(label="Save", callback=lambda: app._save(dpg))
        dpg.add_button(label="Undo", callback=lambda: app._undo(dpg))
        dpg.add_button(label="Redo", callback=lambda: app._redo(dpg))
        dpg.add_button(label="Validate", callback=lambda: app._validate(dpg))
        dpg.add_button(label="Play Scene", callback=lambda: app._play_scene(dpg))
        dpg.add_button(label="Run Game", callback=lambda: app._run_game(dpg))
        dpg.add_text("", tag="dirty_text")


def build_scene_sidebar(dpg, app) -> None:
    dpg.add_text("Scenes")
    dpg.add_listbox(
        tag="scene_list",
        items=[],
        num_items=7,
        width=-1,
        callback=lambda _s, a: app._select_scene(dpg, a),
    )
    with dpg.group(horizontal=True):
        dpg.add_input_text(
            tag="new_scene_id",
            default_value="scene_2",
            width=170,
            hint="new scene id",
        )
        dpg.add_button(label="Create", callback=lambda: app._create_scene(dpg))
    with dpg.group(horizontal=True):
        dpg.add_button(label="Duplicate Scene", callback=lambda: app._duplicate_scene(dpg))
        dpg.add_button(label="Delete Scene", callback=lambda: app._request_delete_scene(dpg))
    dpg.add_button(label="Use As Start Scene", callback=lambda: app._set_start_scene(dpg))
    dpg.add_separator()
    dpg.add_text("Layers", tag="layers_header")
    with dpg.group(tag="layer_list"):
        pass
    dpg.add_separator()
    dpg.add_text("Objects")
    dpg.add_listbox(
        tag="object_combo",
        items=[],
        num_items=11,
        width=-1,
        callback=lambda _s, a: app._select_object(dpg, a),
    )
    with dpg.group(horizontal=True):
        dpg.add_button(label="Hotspot", callback=lambda: app._add_hotspot(dpg))
        dpg.add_button(label="Exit", callback=lambda: app._add_exit(dpg))
        dpg.add_button(label="NPC", callback=lambda: app._add_npc(dpg))
    with dpg.group(horizontal=True):
        dpg.add_button(label="Spawn", callback=lambda: app._add_spawn(dpg))
        dpg.add_button(label="Item", callback=lambda: app._add_scene_item(dpg))


def build_canvas_toolbar(dpg, app) -> None:
    with dpg.group(horizontal=True):
        dpg.add_button(label="Fit", callback=lambda: app._fit_canvas(dpg))
        dpg.add_button(label="-", callback=lambda: app._zoom_canvas(dpg, 0.85))
        dpg.add_button(label="+", callback=lambda: app._zoom_canvas(dpg, 1.15))
        dpg.add_checkbox(
            tag="snap_grid",
            label="Snap",
            default_value=True,
            callback=lambda _s, a: app._set_snap(dpg, a),
        )
        dpg.add_checkbox(
            tag="show_grid",
            label="Grid",
            default_value=True,
            callback=lambda _s, a: app._set_grid(dpg, a),
        )


def build_context_entry_buttons(dpg, open_dialogue: Callable, open_logic: Callable) -> None:
    with dpg.group(horizontal=True):
        dpg.add_button(
            label="Edit Conversation",
            tag="edit_conversation_button",
            callback=lambda: open_dialogue(),
        )
        dpg.add_button(
            label="Edit Interaction",
            tag="edit_interaction_button",
            callback=lambda: open_logic(),
        )
