from __future__ import annotations

import copy
import time
from pathlib import Path

from pce.editor.canvas import CanvasState, selected_item
from pce.editor.canvas_rendering import (
    canvas_available_size,
    draw_canvas,
    layer_locked,
    layer_visible,
    project_resolution,
    texture_for,
    update_canvas_view,
)
from pce.editor.panels.action_list_panel import (
    ACTION_TYPES,
    actions_from_json,
    action_to_json,
    condition_to_json,
    parse_action_value,
)
from pce.editor.panels.dialogue_panel import (
    choice_actions_json,
    choice_condition_json,
    choice_label,
    merge_choice_from_visual_fields,
)
from pce.editor.panels.dialogue_studio import (
    build_dialogue_studio,
    choice_summary,
    condition_label,
    effects_label,
    target_id_from_label,
    target_label,
    target_options,
    validate_dialogue_graph,
)
from pce.editor.panels.properties_panel import inspector_field_visibility
from pce.editor.panels.story_studio import (
    build_canvas_toolbar,
    build_context_entry_buttons,
    build_scene_sidebar,
    build_workspace_nav,
)
from pce.editor.panels.theme import apply_theme
from pce.editor.panels.visual_editors import (
    CONDITION_OPERATORS,
    CONDITION_TYPES,
    action_label,
    merge_action_from_visual_fields,
    merge_condition_from_fields,
)
from pce.editor.preview_bridge import play_current_scene, run_full_game
from pce.editor.project_controller import ProjectController, ProjectSnapshot
from pce.shared.models import Action, Condition, DialogueChoice


class EditorApp:
    def __init__(self, project: Path | None = None) -> None:
        self.controller = ProjectController()
        self.canvas = CanvasState()
        self.status = "No project open."
        self._last_autosave_check = time.monotonic()
        self._textures: dict[str, tuple[str, int, int]] = {}
        self._selected_action_index = 0
        self._selected_dialogue_node_id: str | None = None
        self._selected_dialogue_choice_index = 0
        self._last_pan_point: tuple[float, float] | None = None
        self._pending_drag_undo: ProjectSnapshot | None = None
        self.active_workspace = "Scenes"
        self.simple_mode = True
        if project is not None:
            self.controller.open_project(project)
            self.status = f"Opened {project}"

    def run(self) -> None:
        try:
            import dearpygui.dearpygui as dpg
        except Exception as exc:
            raise RuntimeError(
                "Dear PyGui is required for the editor. Install with: python -m pip install -e ."
            ) from exc

        dpg.create_context()
        dpg.create_viewport(title="PointClick Editor", width=1280, height=820)
        with dpg.texture_registry(tag="texture_registry"):
            pass
        self._build_ui(dpg)
        dpg.setup_dearpygui()
        dpg.show_viewport()
        dpg.set_primary_window("main_window", True)
        while dpg.is_dearpygui_running():
            self._maybe_periodic_autosave(dpg)
            dpg.render_dearpygui_frame()
        dpg.destroy_context()

    def _build_ui(self, dpg) -> None:
        self._apply_theme(dpg)
        with dpg.file_dialog(
            directory_selector=True,
            show=False,
            tag="project_dialog",
            width=700,
            height=420,
            callback=lambda _s, a: self._open_project_from_dialog(dpg, a),
        ):
            pass
        with dpg.file_dialog(
            show=False,
            tag="background_dialog",
            width=700,
            height=420,
            callback=lambda _s, a: self._import_asset_from_dialog(dpg, a, "background"),
        ):
            dpg.add_file_extension(".png")
            dpg.add_file_extension(".jpg")
            dpg.add_file_extension(".jpeg")
        with dpg.file_dialog(
            show=False,
            tag="player_sprite_dialog",
            width=700,
            height=420,
            callback=lambda _s, a: self._import_asset_from_dialog(dpg, a, "player_sprite"),
        ):
            dpg.add_file_extension(".png")
            dpg.add_file_extension(".jpg")
            dpg.add_file_extension(".jpeg")
        with dpg.file_dialog(
            show=False,
            tag="npc_sprite_dialog",
            width=700,
            height=420,
            callback=lambda _s, a: self._import_asset_from_dialog(dpg, a, "npc_sprite"),
        ):
            dpg.add_file_extension(".png")
            dpg.add_file_extension(".jpg")
            dpg.add_file_extension(".jpeg")
        with dpg.window(
            label="Confirm Delete",
            tag="confirm_delete_modal",
            modal=True,
            show=False,
            width=360,
            height=130,
        ):
            dpg.add_text("Delete the selected object?")
            with dpg.group(horizontal=True):
                dpg.add_button(label="Delete", callback=lambda: self._confirm_delete_selected(dpg))
                dpg.add_button(label="Cancel", callback=lambda: dpg.hide_item("confirm_delete_modal"))

        with dpg.window(tag="main_window"):
            dpg.add_input_text(tag="project_path", show=False)
            dpg.add_input_text(tag="asset_path", show=False)
            with dpg.menu_bar():
                with dpg.menu(label="Project"):
                    dpg.add_menu_item(label="New Project", callback=lambda: self._new_project(dpg))
                    dpg.add_menu_item(label="Open Folder...", callback=lambda: dpg.show_item("project_dialog"))
                    dpg.add_menu_item(label="Save", callback=lambda: self._save(dpg))
                    dpg.add_menu_item(label="Export Playable", callback=lambda: self._export(dpg))
                with dpg.menu(label="Run"):
                    dpg.add_menu_item(label="Validate", callback=lambda: self._validate(dpg))
                    dpg.add_menu_item(label="Play Scene", callback=lambda: self._play_scene(dpg))
                    dpg.add_menu_item(label="Run Game", callback=lambda: self._run_game(dpg))
            build_workspace_nav(dpg, self)

            with dpg.group(horizontal=True):
                with dpg.child_window(tag="scene_sidebar", width=270, height=-125, border=True):
                    build_scene_sidebar(dpg, self)

                with dpg.child_window(tag="canvas_panel", width=-390, height=-125, border=True):
                    build_canvas_toolbar(dpg, self)
                    with dpg.drawlist(tag="canvas_drawlist", width=1, height=1):
                        pass
                build_dialogue_studio(dpg, self)

                with dpg.child_window(tag="context_panel", width=380, height=-125, border=True):
                    dpg.add_text("Inspector", tag="inspector_title")
                    with dpg.group(tag="assets_workspace_panel"):
                        dpg.add_text("Project Assets")
                        dpg.add_button(
                            label="Choose Scene Background...",
                            callback=lambda: dpg.show_item("background_dialog"),
                        )
                        dpg.add_button(
                            label="Choose Player Sprite...",
                            callback=lambda: dpg.show_item("player_sprite_dialog"),
                        )
                        dpg.add_button(label="Add Item Definition", callback=lambda: self._add_item_definition(dpg))
                        dpg.add_listbox(tag="asset_item_list", items=[], num_items=8, width=-1)
                        dpg.add_separator()
                    with dpg.group(horizontal=True):
                        dpg.add_button(label="Duplicate", tag="duplicate_button", callback=lambda: self._duplicate_selected(dpg))
                        dpg.add_button(
                            label="Delete",
                            tag="delete_button",
                            callback=lambda: self._request_delete_selected(dpg),
                        )
                    with dpg.group(horizontal=True):
                        dpg.add_button(label="Left", callback=lambda: self._nudge_selected(dpg, -self.canvas.grid_size, 0))
                        dpg.add_button(label="Up", callback=lambda: self._nudge_selected(dpg, 0, -self.canvas.grid_size))
                        dpg.add_button(label="Down", callback=lambda: self._nudge_selected(dpg, 0, self.canvas.grid_size))
                        dpg.add_button(label="Right", callback=lambda: self._nudge_selected(dpg, self.canvas.grid_size, 0))
                    build_context_entry_buttons(
                        dpg,
                        open_dialogue=lambda: self._open_dialogue_studio(dpg),
                        open_logic=lambda: self._set_workspace(dpg, "Logic"),
                    )
                    dpg.add_input_text(tag="prop_id", label="Id", width=-1)
                    dpg.add_input_text(tag="prop_name", label="Name", width=-1)
                    dpg.add_input_intx(tag="prop_rect", label="Rect", size=4, width=-1)
                    dpg.add_input_intx(tag="prop_pos", label="Position", size=2, width=-1)
                    dpg.add_input_text(tag="prop_background", label="Background", width=-1, readonly=True)
                    dpg.add_button(label="Choose Background...", tag="background_button", callback=lambda: dpg.show_item("background_dialog"))
                    dpg.add_input_text(tag="prop_sprite", label="Sprite", width=-1, readonly=True)
                    dpg.add_button(label="Choose NPC Sprite...", tag="npc_sprite_button", callback=lambda: dpg.show_item("npc_sprite_dialog"))
                    dpg.add_button(label="Choose Player Sprite...", tag="player_sprite_button", callback=lambda: dpg.show_item("player_sprite_dialog"))
                    dpg.add_input_text(tag="prop_item_id", label="Item Id", width=-1)
                    dpg.add_checkbox(tag="prop_enabled", label="Enabled", default_value=True)
                    dpg.add_combo(tag="prop_layer", label="Layer", items=[], width=-1)
                    dpg.add_combo(tag="prop_facing", label="Facing", items=["left", "right", "up", "down"], width=-1)
                    dpg.add_combo(
                        tag="prop_target_scene",
                        label="Target Scene",
                        items=[],
                        width=-1,
                        callback=lambda _s, _a: self._refresh_reference_dropdowns(dpg),
                    )
                    dpg.add_combo(tag="prop_target_spawn", label="Target Spawn", items=[], width=-1)
                    dpg.add_input_text(tag="prop_walk_path", label="Walk Path", width=-1)
                    dpg.add_input_text(tag="prop_lines", label="Quick Lines", width=-1)
                    dpg.add_separator()
                    dpg.add_text("Actions", tag="actions_header")
                    dpg.add_listbox(
                        tag="action_list",
                        items=[],
                        num_items=4,
                        width=-1,
                        callback=lambda _s, a: self._select_action(dpg, a),
                    )
                    with dpg.group(horizontal=True, tag="action_buttons"):
                        dpg.add_button(label="Add", callback=lambda: self._add_action(dpg))
                        dpg.add_button(label="Up", callback=lambda: self._move_action(dpg, -1))
                        dpg.add_button(label="Down", callback=lambda: self._move_action(dpg, 1))
                        dpg.add_button(label="Remove", callback=lambda: self._remove_action(dpg))
                    dpg.add_combo(
                        tag="action_type",
                        label="Type",
                        items=ACTION_TYPES,
                        default_value="say",
                        width=-1,
                        callback=lambda _s, _a: self._refresh_action_editor(dpg),
                    )
                    dpg.add_input_text(tag="action_speaker", label="Speaker", default_value="Player", width=-1)
                    dpg.add_input_text(tag="action_text", label="Text", width=-1, multiline=True, height=70)
                    dpg.add_combo(tag="action_npc", label="NPC", items=[], width=-1)
                    dpg.add_combo(tag="action_node", label="Dialogue Node", items=[], width=-1)
                    dpg.add_combo(
                        tag="action_scene",
                        label="Scene",
                        items=[],
                        width=-1,
                        callback=lambda _s, _a: self._refresh_reference_dropdowns(dpg),
                    )
                    dpg.add_combo(tag="action_spawn", label="Spawn", items=[], width=-1)
                    dpg.add_combo(tag="action_item", label="Item", items=[], width=-1)
                    dpg.add_combo(tag="action_object", label="Object", items=[], width=-1)
                    dpg.add_input_text(tag="action_variable", label="Variable", width=-1)
                    dpg.add_input_text(tag="action_value", label="Value", width=-1)
                    dpg.add_checkbox(tag="action_enabled", label="Enabled", default_value=False)
                    dpg.add_text("Condition", tag="action_condition_header")
                    dpg.add_combo(
                        tag="action_condition_type",
                        label="Condition",
                        items=CONDITION_TYPES,
                        default_value="always",
                        width=-1,
                        callback=lambda _s, _a: self._refresh_action_editor(dpg),
                    )
                    dpg.add_input_text(tag="action_condition_variable", label="Variable", width=-1)
                    dpg.add_combo(
                        tag="action_condition_operator",
                        label="Operator",
                        items=CONDITION_OPERATORS,
                        default_value="==",
                        width=-1,
                    )
                    dpg.add_input_text(tag="action_condition_value", label="Value", width=-1)
                    dpg.add_combo(tag="action_condition_item", label="Item", items=[], width=-1)
                    dpg.add_combo(tag="action_condition_object", label="Object", items=[], width=-1)
                    dpg.add_combo(
                        tag="action_condition_not_type",
                        label="Not Condition",
                        items=CONDITION_TYPES[:-1],
                        default_value="always",
                        width=-1,
                    )
                    dpg.add_text("Nested Actions", tag="action_actions_header")
                    dpg.add_listbox(tag="action_actions_list", items=[], num_items=3, width=-1)
                    with dpg.group(horizontal=True, tag="action_actions_buttons"):
                        dpg.add_button(label="Add", callback=lambda: self._add_nested_action(dpg, "sequence"))
                        dpg.add_button(label="Remove", callback=lambda: self._remove_nested_action(dpg, "sequence"))
                    dpg.add_text("If Actions", tag="action_if_actions_header")
                    dpg.add_listbox(tag="action_if_actions_list", items=[], num_items=3, width=-1)
                    with dpg.group(horizontal=True, tag="action_if_actions_buttons"):
                        dpg.add_button(label="Add", callback=lambda: self._add_nested_action(dpg, "if"))
                        dpg.add_button(label="Remove", callback=lambda: self._remove_nested_action(dpg, "if"))
                    dpg.add_text("Else Actions", tag="action_else_actions_header")
                    dpg.add_listbox(tag="action_else_actions_list", items=[], num_items=3, width=-1)
                    with dpg.group(horizontal=True, tag="action_else_actions_buttons"):
                        dpg.add_button(label="Add", callback=lambda: self._add_nested_action(dpg, "else"))
                        dpg.add_button(label="Remove", callback=lambda: self._remove_nested_action(dpg, "else"))
                    dpg.add_input_text(
                        tag="action_condition_json",
                        label="Advanced Condition JSON",
                        width=-1,
                        multiline=True,
                        height=70,
                        show=False,
                    )
                    dpg.add_input_text(
                        tag="action_actions_json",
                        label="Advanced Nested Actions JSON",
                        width=-1,
                        multiline=True,
                        height=90,
                        show=False,
                    )
                    dpg.add_input_text(
                        tag="action_if_actions_json",
                        label="Advanced If Actions JSON",
                        width=-1,
                        multiline=True,
                        height=90,
                        show=False,
                    )
                    dpg.add_input_text(
                        tag="action_else_actions_json",
                        label="Advanced Else Actions JSON",
                        width=-1,
                        multiline=True,
                        height=90,
                        show=False,
                    )
                    dpg.add_button(label="Apply Action", callback=lambda: self._apply_action(dpg))
                    dpg.add_separator()
                    dpg.add_text("Dialogue", tag="dialogue_header")
                    dpg.add_listbox(
                        tag="dialogue_node_list",
                        items=[],
                        num_items=4,
                        width=-1,
                        callback=lambda _s, a: self._select_dialogue_node(dpg, a),
                    )
                    with dpg.group(horizontal=True, tag="dialogue_buttons"):
                        dpg.add_button(label="Add Node", callback=lambda: self._add_dialogue_node(dpg))
                        dpg.add_button(label="Delete Node", callback=lambda: self._delete_dialogue_node(dpg))
                    dpg.add_input_text(tag="dialogue_node_id", label="Node Id", width=-1)
                    dpg.add_input_text(tag="dialogue_speaker", label="Speaker", width=-1)
                    dpg.add_input_text(tag="dialogue_text", label="Text", width=-1, multiline=True, height=80)
                    dpg.add_text("Node Actions", tag="dialogue_node_actions_header")
                    dpg.add_listbox(tag="dialogue_node_action_list", items=[], num_items=3, width=-1)
                    with dpg.group(horizontal=True, tag="dialogue_node_action_buttons"):
                        dpg.add_button(label="Add", callback=lambda: self._add_dialogue_node_action(dpg))
                        dpg.add_button(label="Remove", callback=lambda: self._remove_dialogue_node_action(dpg))
                    dpg.add_input_text(
                        tag="dialogue_node_actions_json",
                        label="Advanced Node Actions JSON",
                        width=-1,
                        multiline=True,
                        height=72,
                        show=False,
                    )
                    dpg.add_text("Choices")
                    dpg.add_listbox(
                        tag="dialogue_choice_list",
                        items=[],
                        num_items=4,
                        width=-1,
                        callback=lambda _s, a: self._select_dialogue_choice(dpg, a),
                    )
                    with dpg.group(horizontal=True, tag="dialogue_choice_buttons"):
                        dpg.add_button(label="Add Choice", callback=lambda: self._add_dialogue_choice(dpg))
                        dpg.add_button(label="Apply Choice", callback=lambda: self._apply_dialogue_choice(dpg))
                        dpg.add_button(label="Remove Choice", callback=lambda: self._remove_dialogue_choice(dpg))
                    dpg.add_input_text(tag="dialogue_choice_text", label="Choice Text", width=-1)
                    dpg.add_combo(tag="dialogue_choice_target", label="Choice Target", items=[], width=-1)
                    dpg.add_text("Choice Condition", tag="dialogue_choice_condition_header")
                    dpg.add_combo(
                        tag="dialogue_choice_condition_type",
                        label="Condition",
                        items=CONDITION_TYPES,
                        default_value="always",
                        width=-1,
                        callback=lambda _s, _a: self._refresh_dialogue_choice_condition_editor(dpg),
                    )
                    dpg.add_input_text(tag="dialogue_choice_condition_variable", label="Variable", width=-1)
                    dpg.add_combo(
                        tag="dialogue_choice_condition_operator",
                        label="Operator",
                        items=CONDITION_OPERATORS,
                        default_value="==",
                        width=-1,
                    )
                    dpg.add_input_text(tag="dialogue_choice_condition_value", label="Value", width=-1)
                    dpg.add_combo(tag="dialogue_choice_condition_item", label="Item", items=[], width=-1)
                    dpg.add_combo(tag="dialogue_choice_condition_object", label="Object", items=[], width=-1)
                    dpg.add_combo(
                        tag="dialogue_choice_condition_not_type",
                        label="Not Condition",
                        items=CONDITION_TYPES[:-1],
                        default_value="always",
                        width=-1,
                    )
                    dpg.add_text("Choice Actions", tag="dialogue_choice_actions_header")
                    dpg.add_listbox(tag="dialogue_choice_action_list", items=[], num_items=3, width=-1)
                    with dpg.group(horizontal=True, tag="dialogue_choice_action_buttons"):
                        dpg.add_button(label="Add", callback=lambda: self._add_dialogue_choice_action(dpg))
                        dpg.add_button(label="Remove", callback=lambda: self._remove_dialogue_choice_action(dpg))
                    dpg.add_input_text(
                        tag="dialogue_choice_condition_json",
                        label="Advanced Choice Condition JSON",
                        width=-1,
                        multiline=True,
                        height=72,
                        show=False,
                    )
                    dpg.add_input_text(
                        tag="dialogue_choice_actions_json",
                        label="Advanced Choice Actions JSON",
                        width=-1,
                        multiline=True,
                        height=90,
                        show=False,
                    )
                    dpg.add_button(label="Apply Dialogue Node", callback=lambda: self._apply_dialogue_node(dpg))
                    dpg.add_button(label="Apply Properties", callback=lambda: self._apply_properties(dpg))

            with dpg.child_window(height=110, border=True):
                dpg.add_text(self.status, tag="status_text")
                dpg.add_text("", tag="validation_text", wrap=1100)

        with dpg.handler_registry():
            dpg.add_mouse_click_handler(button=dpg.mvMouseButton_Left, callback=lambda: self._canvas_mouse_down(dpg))
            dpg.add_mouse_drag_handler(button=dpg.mvMouseButton_Left, callback=lambda: self._canvas_mouse_drag(dpg))
            dpg.add_mouse_release_handler(button=dpg.mvMouseButton_Left, callback=lambda: self._canvas_mouse_up(dpg))
            dpg.add_mouse_click_handler(button=dpg.mvMouseButton_Right, callback=lambda: self._canvas_pan_down(dpg))
            dpg.add_mouse_drag_handler(button=dpg.mvMouseButton_Right, callback=lambda: self._canvas_pan_drag(dpg))
            dpg.add_mouse_release_handler(button=dpg.mvMouseButton_Right, callback=lambda: self._canvas_pan_up(dpg))
            dpg.add_mouse_wheel_handler(callback=lambda _s, a: self._canvas_mouse_wheel(dpg, a))

        self._refresh(dpg)

    def _apply_theme(self, dpg) -> None:
        apply_theme(dpg)

    def _new_project(self, dpg) -> None:
        if not self._can_replace_project(dpg):
            return
        path = Path(dpg.get_value("project_path") or "example_project")
        self.controller.new_project(path)
        self.status = f"Created {path}"
        self._refresh(dpg)

    def _open_project(self, dpg) -> None:
        if not self._can_replace_project(dpg):
            return
        path = Path(dpg.get_value("project_path") or ".")
        self.controller.open_project(path)
        self.status = f"Opened {path}"
        self._refresh(dpg)

    def _open_project_from_dialog(self, dpg, app_data) -> None:
        if not self._can_replace_project(dpg):
            return
        path = self._dialog_path(app_data)
        if path is None:
            return
        self.controller.open_project(path)
        self.canvas.reset_view()
        self.status = f"Opened {path}"
        self._refresh(dpg)

    def _can_replace_project(self, dpg) -> bool:
        if not self.controller.is_dirty:
            return True
        self.status = "Save or undo unsaved changes before opening or creating a project."
        self._refresh(dpg)
        return False

    def _import_asset_from_dialog(self, dpg, app_data, target: str) -> None:
        path = self._dialog_path(app_data)
        if path is None:
            return
        try:
            if target == "background":
                relative_path = self.controller.import_asset(path, "background")
                self.controller.assign_scene_background(relative_path)
            elif target == "player_sprite":
                relative_path = self.controller.import_asset(path, "sprite")
                self.controller.assign_player_sprite(relative_path)
            else:
                if self.canvas.selected_kind != "npc" or self.canvas.selected_id is None:
                    self.status = "Select an NPC before choosing its sprite."
                    self._refresh(dpg)
                    return
                relative_path = self.controller.import_asset(path, "sprite")
                self.controller.assign_npc_sprite(self.canvas.selected_id, relative_path)
        except Exception as exc:
            self.status = f"Import failed: {exc}"
        else:
            self.status = f"Imported {relative_path}"
        self._refresh(dpg)

    @staticmethod
    def _dialog_path(app_data) -> Path | None:
        path_text = app_data.get("file_path_name") if isinstance(app_data, dict) else None
        return Path(path_text) if path_text else None

    def _fit_canvas(self, dpg) -> None:
        self.canvas.reset_view()
        self._draw_canvas(dpg)

    def _zoom_canvas(self, dpg, factor: float) -> None:
        self.canvas.zoom_by(factor)
        self._draw_canvas(dpg)

    def _set_snap(self, dpg, value: bool) -> None:
        self.canvas.snap_to_grid = value
        self._draw_canvas(dpg)

    def _set_grid(self, dpg, value: bool) -> None:
        self.canvas.show_grid = value
        self._draw_canvas(dpg)

    def _set_workspace(self, dpg, workspace: str) -> None:
        self.active_workspace = workspace
        self.status = f"{workspace} workspace."
        self._refresh(dpg)

    def _open_dialogue_studio(self, dpg) -> None:
        if self.canvas.selected_kind != "npc" or self.canvas.selected_id is None:
            self.status = "Select an NPC before opening Dialogue Studio."
            self._refresh(dpg)
            return
        npc = self._studio_npc()
        if npc is not None and npc.dialogue_nodes and self._selected_dialogue_node_id is None:
            self._selected_dialogue_node_id = npc.dialogue_nodes[0].id
        self.active_workspace = "Dialogue"
        self.status = "Dialogue Studio."
        self._refresh(dpg)

    def _set_simple_mode(self, dpg, enabled: bool) -> None:
        self.simple_mode = bool(enabled)
        self.status = "Simple mode." if self.simple_mode else "Advanced mode."
        self._refresh(dpg)

    def _save(self, dpg) -> None:
        self.controller.save()
        self.status = "Saved project."
        self._refresh(dpg)

    def _undo(self, dpg) -> None:
        self.status = "Undid change." if self.controller.undo() else "Nothing to undo."
        self._refresh(dpg)

    def _redo(self, dpg) -> None:
        self.status = "Redid change." if self.controller.redo() else "Nothing to redo."
        self._refresh(dpg)

    def _export(self, dpg) -> None:
        try:
            path = self.controller.export_playable()
        except Exception as exc:
            self.status = f"Export failed: {exc}"
        else:
            self.status = f"Exported playable project to {path}"
        self._refresh(dpg)

    def _autosave(self, dpg) -> None:
        path = self.controller.autosave()
        self._last_autosave_check = time.monotonic()
        self.status = f"Autosaved to {path}"
        self._refresh(dpg)

    def _maybe_periodic_autosave(self, dpg) -> None:
        if self.controller.project is None:
            return
        now = time.monotonic()
        if now - self._last_autosave_check < 120:
            return
        try:
            path = self.controller.autosave()
        except Exception as exc:
            self.status = f"Autosave failed: {exc}"
        else:
            self.status = f"Autosaved to {path}"
        self._last_autosave_check = now
        self._refresh(dpg)

    def _validate(self, dpg) -> None:
        issues = self.controller.validate()
        if not issues:
            dpg.set_value("validation_text", "No validation issues.")
        else:
            dpg.set_value(
                "validation_text",
                "\n".join(f"{issue.severity.value} {issue.code}: {issue.message}" for issue in issues),
            )
        self.status = "Validation complete."
        self._refresh(dpg)

    def _play_scene(self, dpg) -> None:
        play_current_scene(self.controller)
        self.status = "Launched current scene."
        self._refresh(dpg)

    def _run_game(self, dpg) -> None:
        run_full_game(self.controller)
        self.status = "Launched full game."
        self._refresh(dpg)

    def _create_scene(self, dpg) -> None:
        try:
            self.controller.create_scene(dpg.get_value("new_scene_id"))
        except Exception as exc:
            self.status = f"Create scene failed: {exc}"
        else:
            self.canvas.selected_kind = "scene"
            self.canvas.selected_id = "current"
            self.status = "Created scene."
        self._refresh(dpg)

    def _duplicate_scene(self, dpg) -> None:
        try:
            new_id = self.controller.duplicate_scene()
        except Exception as exc:
            self.status = f"Duplicate scene failed: {exc}"
        else:
            self.canvas.selected_kind = "scene"
            self.canvas.selected_id = "current"
            self.status = f"Duplicated scene {new_id}."
        self._refresh(dpg)

    def _request_delete_scene(self, dpg) -> None:
        self.canvas.selected_kind = "scene"
        self.canvas.selected_id = "current"
        dpg.show_item("confirm_delete_modal")

    def _select_scene(self, dpg, scene_id: str) -> None:
        self.controller.current_scene_id = scene_id
        self.canvas.selected_kind = None
        self.canvas.selected_id = None
        self._refresh(dpg)

    def _add_hotspot(self, dpg) -> None:
        self.controller.add_hotspot()
        self.status = "Added hotspot."
        self._refresh(dpg)

    def _add_exit(self, dpg) -> None:
        self.controller.add_exit()
        self.status = "Added exit."
        self._refresh(dpg)

    def _add_npc(self, dpg) -> None:
        self.controller.add_npc()
        self.status = "Added NPC."
        self._refresh(dpg)

    def _add_spawn(self, dpg) -> None:
        self.controller.add_spawn()
        self.status = "Added spawn."
        self._refresh(dpg)

    def _add_item_definition(self, dpg) -> None:
        item = self.controller.add_item_definition()
        self.status = f"Added item definition {item.id}."
        self._refresh(dpg)

    def _add_scene_item(self, dpg) -> None:
        self.controller.add_scene_item()
        self.status = "Added scene item."
        self._refresh(dpg)

    def _set_start_scene(self, dpg) -> None:
        self.controller.set_current_scene_as_start()
        self.status = "Current scene is now the start scene."
        self._refresh(dpg)

    def _import_background(self, dpg) -> None:
        self._import_asset(dpg, "background")

    def _import_player_sprite(self, dpg) -> None:
        relative_path = self._import_asset(dpg, "sprite", refresh=False)
        if relative_path:
            self.controller.assign_player_sprite(relative_path)
            self.status = f"Imported player sprite: {relative_path}"
            self._refresh(dpg)

    def _import_npc_sprite(self, dpg) -> None:
        if self.canvas.selected_kind != "npc" or self.canvas.selected_id is None:
            self.status = "Select an NPC before importing its sprite."
            self._refresh(dpg)
            return
        relative_path = self._import_asset(dpg, "sprite", refresh=False)
        if relative_path:
            self.controller.assign_npc_sprite(self.canvas.selected_id, relative_path)
            self.status = f"Imported NPC sprite: {relative_path}"
            self._refresh(dpg)

    def _import_asset(self, dpg, asset_kind: str, refresh: bool = True) -> str | None:
        try:
            relative_path = self.controller.import_asset(Path(dpg.get_value("asset_path")), asset_kind)
        except Exception as exc:
            self.status = str(exc)
            if refresh:
                self._refresh(dpg)
            return None
        if asset_kind == "background":
            self.controller.assign_scene_background(relative_path)
        self.status = f"Imported {asset_kind}: {relative_path}"
        if refresh:
            self._refresh(dpg)
        return relative_path

    def _select_object(self, dpg, value: str) -> None:
        if ":" not in value:
            return
        kind, object_id = value.split(":", 1)
        self.canvas.selected_kind = kind
        self.canvas.selected_id = object_id
        self._load_selected_properties(dpg)
        self._draw_canvas(dpg)

    def _duplicate_selected(self, dpg) -> None:
        if self.canvas.selected_kind is None or self.canvas.selected_id is None:
            self.status = "Select an object before duplicating."
            self._refresh(dpg)
            return
        if self.canvas.selected_kind == "scene":
            self._duplicate_scene(dpg)
            return
        new_id = self.controller.duplicate_scene_object(self.canvas.selected_kind, self.canvas.selected_id)
        if new_id is None:
            self.status = "Nothing duplicated."
        else:
            self.canvas.selected_id = new_id
            self.status = f"Duplicated {self.canvas.selected_kind}."
        self._refresh(dpg)

    def _request_delete_selected(self, dpg) -> None:
        if self.canvas.selected_kind is None or self.canvas.selected_id is None:
            self.status = "Select an object before deleting."
            self._refresh(dpg)
            return
        dpg.show_item("confirm_delete_modal")

    def _confirm_delete_selected(self, dpg) -> None:
        dpg.hide_item("confirm_delete_modal")
        if self.canvas.selected_kind is None or self.canvas.selected_id is None:
            self.status = "Select an object before deleting."
            self._refresh(dpg)
            return
        if self.canvas.selected_kind == "scene":
            try:
                deleted = self.controller.delete_scene()
            except Exception as exc:
                self.status = f"Delete scene failed: {exc}"
            else:
                self.canvas.selected_kind = "scene"
                self.canvas.selected_id = "current"
                self.status = "Deleted scene." if deleted else "Nothing deleted."
        else:
            deleted = self.controller.delete_scene_object(self.canvas.selected_kind, self.canvas.selected_id)
            self.canvas.selected_kind = None
            self.canvas.selected_id = None
            self.status = "Deleted object." if deleted else "Nothing deleted."
        self._refresh(dpg)

    def _nudge_selected(self, dpg, dx: int, dy: int) -> None:
        scene = self.controller.current_scene
        if scene is None:
            return
        item = self._selected_item()
        if item is None or not (hasattr(item, "rect") or hasattr(item, "position")):
            self.status = "Select a movable object first."
        elif not self.canvas.selection_editable(scene):
            self.status = "Selected object's layer is hidden or locked."
        else:
            self.controller.record_undo()
            self.canvas.nudge_selected(scene, dx, dy)
            self.status = "Moved selected object."
        self._refresh(dpg)

    def _apply_properties(self, dpg) -> None:
        scene = self.controller.current_scene
        if scene is None or self.canvas.selected_kind is None or self.canvas.selected_id is None:
            return
        item = self._selected_item()
        if item is None:
            return
        if self.canvas.selected_kind == "scene":
            self.canvas.selected_id = self.controller.update_scene_metadata(
                scene_id=dpg.get_value("prop_id"),
                name=dpg.get_value("prop_name"),
                background=dpg.get_value("prop_background"),
            )
        else:
            fields = {"id": dpg.get_value("prop_id")}
            if hasattr(item, "name"):
                fields["name"] = dpg.get_value("prop_name")
            if hasattr(item, "rect"):
                fields["rect"] = tuple(int(value) for value in dpg.get_value("prop_rect"))
            if hasattr(item, "position"):
                fields["position"] = tuple(int(value) for value in dpg.get_value("prop_pos"))
            if hasattr(item, "sprite"):
                fields["sprite"] = dpg.get_value("prop_sprite") or None
            if hasattr(item, "item_id"):
                fields["item_id"] = dpg.get_value("prop_item_id")
            if hasattr(item, "enabled"):
                fields["enabled"] = bool(dpg.get_value("prop_enabled"))
            if hasattr(item, "layer"):
                fields["layer"] = dpg.get_value("prop_layer")
            if hasattr(item, "facing"):
                fields["facing"] = dpg.get_value("prop_facing")
            if hasattr(item, "target_scene"):
                fields["target_scene"] = dpg.get_value("prop_target_scene")
            if hasattr(item, "target_spawn"):
                fields["target_spawn"] = dpg.get_value("prop_target_spawn")
            if hasattr(item, "walk_path"):
                fields["walk_path"] = self._parse_points(dpg.get_value("prop_walk_path"))
            if hasattr(item, "lines"):
                fields["lines"] = [
                    line.strip() for line in dpg.get_value("prop_lines").split("|") if line.strip()
                ]
            self.canvas.selected_id = self.controller.update_scene_object(
                self.canvas.selected_kind,
                self.canvas.selected_id,
                **fields,
            )
        self.status = "Applied properties."
        self._refresh(dpg)

    def _select_action(self, dpg, value: str) -> None:
        try:
            self._selected_action_index = int(value.split(".", 1)[0]) - 1
        except ValueError:
            self._selected_action_index = 0
        self._load_action_editor(dpg)

    def _add_action(self, dpg) -> None:
        target = self._selected_action_target()
        if target is None:
            return
        kind, object_id, actions = target
        actions = list(actions)
        actions.append(Action(type="say", speaker="Player", text="New line."))
        self.controller.set_actions(kind, object_id, actions)
        self._selected_action_index = len(actions) - 1
        self.status = "Added action."
        self._refresh(dpg)

    def _remove_action(self, dpg) -> None:
        target = self._selected_action_target()
        if target is None:
            return
        kind, object_id, actions = target
        if not actions:
            return
        actions = list(actions)
        del actions[min(self._selected_action_index, len(actions) - 1)]
        self.controller.set_actions(kind, object_id, actions)
        self._selected_action_index = max(0, self._selected_action_index - 1)
        self.status = "Removed action."
        self._refresh(dpg)

    def _move_action(self, dpg, direction: int) -> None:
        target = self._selected_action_target()
        if target is None:
            return
        kind, object_id, actions = target
        actions = list(actions)
        old_index = self._selected_action_index
        new_index = old_index + direction
        if old_index < 0 or new_index < 0 or new_index >= len(actions):
            return
        actions[old_index], actions[new_index] = actions[new_index], actions[old_index]
        self.controller.set_actions(kind, object_id, actions)
        self._selected_action_index = new_index
        self.status = "Reordered action."
        self._refresh(dpg)

    def _apply_action(self, dpg) -> None:
        target = self._selected_action_target()
        item = self._selected_item()
        if target is None or item is None:
            return
        kind, object_id, actions = target
        actions = list(actions)
        if not actions:
            actions.append(Action(type="say", speaker="Player", text=""))
            self._selected_action_index = 0
        try:
            actions[self._selected_action_index] = self._action_from_fields(
                dpg,
                item,
                actions[self._selected_action_index],
            )
            self.controller.set_actions(kind, object_id, actions)
        except Exception as exc:
            self.status = f"Apply action failed: {exc}"
        else:
            self.status = "Applied action."
        self._refresh(dpg)

    def _add_nested_action(self, dpg, group: str) -> None:
        target = self._selected_action_target()
        if target is None:
            return
        kind, object_id, actions = target
        if not actions:
            return
        index = min(self._selected_action_index, len(actions) - 1)
        edited = copy.deepcopy(actions)
        action = Action(type="say", speaker="Player", text="New nested line.")
        if group == "sequence":
            edited[index].actions.append(action)
        elif group == "if":
            edited[index].if_actions.append(action)
        else:
            edited[index].else_actions.append(action)
        self.controller.set_actions(kind, object_id, edited)
        self.status = "Added nested action."
        self._refresh(dpg)

    def _remove_nested_action(self, dpg, group: str) -> None:
        target = self._selected_action_target()
        if target is None:
            return
        kind, object_id, actions = target
        if not actions:
            return
        index = min(self._selected_action_index, len(actions) - 1)
        edited = copy.deepcopy(actions)
        nested = {
            "sequence": edited[index].actions,
            "if": edited[index].if_actions,
            "else": edited[index].else_actions,
        }[group]
        if not nested:
            return
        nested.pop()
        self.controller.set_actions(kind, object_id, edited)
        self.status = "Removed nested action."
        self._refresh(dpg)

    def _selected_action_target(self) -> tuple[str, str, list[Action]] | None:
        item = self._selected_item()
        if (
            item is None
            or self.canvas.selected_kind in {None, "scene", "spawn", "exit"}
            or self.canvas.selected_id is None
            or not hasattr(item, "on_click")
        ):
            return None
        return self.canvas.selected_kind, self.canvas.selected_id, list(item.on_click)

    def _add_dialogue_node(self, dpg) -> None:
        if self.canvas.selected_kind != "npc" or self.canvas.selected_id is None:
            return
        node = self.controller.add_dialogue_node(self.canvas.selected_id)
        self._selected_dialogue_node_id = node.id
        self.status = "Added dialogue node."
        self._refresh(dpg)

    def _delete_dialogue_node(self, dpg) -> None:
        if self.canvas.selected_kind != "npc" or self.canvas.selected_id is None:
            return
        node_id = self._selected_dialogue_node_id
        if node_id is None:
            return
        if self.controller.delete_dialogue_node(self.canvas.selected_id, node_id):
            self._selected_dialogue_node_id = None
            self.status = "Deleted dialogue node."
            self._refresh(dpg)

    def _select_dialogue_node(self, dpg, value: str) -> None:
        self._selected_dialogue_node_id = value.split(" ", 1)[0]
        self._selected_dialogue_choice_index = 0
        self._load_dialogue_editor(dpg)

    def _apply_dialogue_node(self, dpg) -> None:
        if self.canvas.selected_kind != "npc" or self.canvas.selected_id is None:
            return
        node_id = self._selected_dialogue_node_id
        if node_id is None:
            return
        try:
            self._selected_dialogue_node_id = self.controller.update_dialogue_node(
                self.canvas.selected_id,
                node_id,
                new_id=dpg.get_value("dialogue_node_id"),
                speaker=dpg.get_value("dialogue_speaker"),
                text=dpg.get_value("dialogue_text"),
                actions=list(node.actions) if (node := self._selected_dialogue_node()) is not None else [],
            )
        except Exception as exc:
            self.status = f"Apply dialogue node failed: {exc}"
        else:
            self.status = "Applied dialogue node."
        self._refresh(dpg)

    def _add_dialogue_choice(self, dpg) -> None:
        node = self._selected_dialogue_node()
        if self.canvas.selected_kind != "npc" or self.canvas.selected_id is None or node is None:
            return
        choices = list(node.choices)
        choices.append(DialogueChoice(text="Continue."))
        self.controller.update_dialogue_node(self.canvas.selected_id, node.id, choices=choices)
        self._selected_dialogue_choice_index = len(choices) - 1
        self.status = "Added dialogue choice."
        self._refresh(dpg)

    def _apply_dialogue_choice(self, dpg) -> None:
        node = self._selected_dialogue_node()
        if self.canvas.selected_kind != "npc" or self.canvas.selected_id is None or node is None:
            return
        choices = list(node.choices)
        if not choices:
            choices.append(DialogueChoice(text="Continue."))
            self._selected_dialogue_choice_index = 0
        index = min(self._selected_dialogue_choice_index, len(choices) - 1)
        try:
            choices[index] = merge_choice_from_visual_fields(
                choices[index],
                text=dpg.get_value("dialogue_choice_text") or "",
                target=dpg.get_value("dialogue_choice_target") or "",
                condition=self._condition_from_fields(
                    dpg,
                    "dialogue_choice_condition",
                    choices[index].condition,
                ),
                actions=choices[index].actions,
            )
            self.controller.update_dialogue_node(self.canvas.selected_id, node.id, choices=choices)
        except Exception as exc:
            self.status = f"Apply dialogue choice failed: {exc}"
        else:
            self.status = "Applied dialogue choice."
        self._refresh(dpg)

    def _remove_dialogue_choice(self, dpg) -> None:
        node = self._selected_dialogue_node()
        if self.canvas.selected_kind != "npc" or self.canvas.selected_id is None or node is None:
            return
        choices = list(node.choices)
        if not choices:
            return
        del choices[min(self._selected_dialogue_choice_index, len(choices) - 1)]
        self.controller.update_dialogue_node(self.canvas.selected_id, node.id, choices=choices)
        self._selected_dialogue_choice_index = max(0, self._selected_dialogue_choice_index - 1)
        self.status = "Removed dialogue choice."
        self._refresh(dpg)

    def _add_dialogue_node_action(self, dpg) -> None:
        node = self._selected_dialogue_node()
        if self.canvas.selected_kind != "npc" or self.canvas.selected_id is None or node is None:
            return
        actions = [*node.actions, Action(type="say", speaker=node.speaker, text="New node action.")]
        self.controller.update_dialogue_node(self.canvas.selected_id, node.id, actions=actions)
        self.status = "Added dialogue node action."
        self._refresh(dpg)

    def _remove_dialogue_node_action(self, dpg) -> None:
        node = self._selected_dialogue_node()
        if self.canvas.selected_kind != "npc" or self.canvas.selected_id is None or node is None or not node.actions:
            return
        self.controller.update_dialogue_node(self.canvas.selected_id, node.id, actions=node.actions[:-1])
        self.status = "Removed dialogue node action."
        self._refresh(dpg)

    def _add_dialogue_choice_action(self, dpg) -> None:
        node = self._selected_dialogue_node()
        if self.canvas.selected_kind != "npc" or self.canvas.selected_id is None or node is None or not node.choices:
            return
        choices = copy.deepcopy(node.choices)
        index = min(self._selected_dialogue_choice_index, len(choices) - 1)
        choices[index].actions.append(Action(type="say", speaker=node.speaker, text="New choice action."))
        self.controller.update_dialogue_node(self.canvas.selected_id, node.id, choices=choices)
        self.status = "Added dialogue choice action."
        self._refresh(dpg)

    def _remove_dialogue_choice_action(self, dpg) -> None:
        node = self._selected_dialogue_node()
        if self.canvas.selected_kind != "npc" or self.canvas.selected_id is None or node is None or not node.choices:
            return
        choices = copy.deepcopy(node.choices)
        index = min(self._selected_dialogue_choice_index, len(choices) - 1)
        if not choices[index].actions:
            return
        choices[index].actions.pop()
        self.controller.update_dialogue_node(self.canvas.selected_id, node.id, choices=choices)
        self.status = "Removed dialogue choice action."
        self._refresh(dpg)

    def _select_dialogue_choice(self, dpg, value: str) -> None:
        try:
            self._selected_dialogue_choice_index = int(value.split(".", 1)[0]) - 1
        except ValueError:
            self._selected_dialogue_choice_index = 0
        self._load_dialogue_choice_editor(dpg)

    def _studio_npc(self):
        item = self._selected_item()
        if self.canvas.selected_kind != "npc" or item is None or not hasattr(item, "dialogue_nodes"):
            return None
        return item

    def _studio_add_dialogue_node(self, dpg) -> None:
        if self.canvas.selected_kind != "npc" or self.canvas.selected_id is None:
            self.status = "Select an NPC before adding a conversation card."
            self._refresh(dpg)
            return
        node = self.controller.add_dialogue_node(self.canvas.selected_id)
        self._selected_dialogue_node_id = node.id
        self.status = "Added conversation card."
        self._refresh(dpg)

    def _studio_duplicate_dialogue_node(self, dpg, node_id: str) -> None:
        if self.canvas.selected_kind != "npc" or self.canvas.selected_id is None:
            return
        self._selected_dialogue_node_id = self.controller.duplicate_dialogue_node(
            self.canvas.selected_id,
            node_id,
        )
        self.status = "Duplicated conversation card."
        self._refresh(dpg)

    def _studio_delete_dialogue_node(self, dpg, node_id: str) -> None:
        if self.canvas.selected_kind != "npc" or self.canvas.selected_id is None:
            return
        if self.controller.delete_dialogue_node(self.canvas.selected_id, node_id):
            self._selected_dialogue_node_id = None
            self.status = "Deleted conversation card."
            self._refresh(dpg)

    def _select_dialogue_card(self, dpg, node_id: str) -> None:
        self._selected_dialogue_node_id = node_id
        self.status = "Focused conversation card."
        self._refresh(dpg)

    def _studio_apply_dialogue_node(self, dpg, node_id: str) -> None:
        if self.canvas.selected_kind != "npc" or self.canvas.selected_id is None:
            return
        try:
            self._selected_dialogue_node_id = self.controller.update_dialogue_node(
                self.canvas.selected_id,
                node_id,
                new_id=dpg.get_value(f"studio_node_id_{node_id}") if not self.simple_mode else node_id,
                speaker=dpg.get_value(f"studio_speaker_{node_id}") or "",
                text=dpg.get_value(f"studio_text_{node_id}") or "",
                actions=list(node.actions) if (node := self._dialogue_node_by_id(node_id)) is not None else [],
            )
        except Exception as exc:
            self.status = f"Apply conversation card failed: {exc}"
        else:
            self.status = "Updated conversation card."
        self._refresh(dpg)

    def _studio_add_dialogue_choice(self, dpg, node_id: str) -> None:
        if self.canvas.selected_kind != "npc" or self.canvas.selected_id is None:
            return
        self.controller.add_dialogue_choice(self.canvas.selected_id, node_id)
        self._selected_dialogue_node_id = node_id
        self.status = "Added response button."
        self._refresh(dpg)

    def _studio_apply_dialogue_choice(self, dpg, node_id: str, choice_index: int) -> None:
        if self.canvas.selected_kind != "npc" or self.canvas.selected_id is None:
            return
        npc = self._studio_npc()
        if npc is None:
            return
        target = target_id_from_label(
            npc,
            dpg.get_value(f"studio_choice_target_{node_id}_{choice_index}") or "End conversation",
        )
        try:
            self.controller.update_dialogue_choice(
                self.canvas.selected_id,
                node_id,
                choice_index,
                text=dpg.get_value(f"studio_choice_text_{node_id}_{choice_index}") or "",
                target=target or "",
            )
        except Exception as exc:
            self.status = f"Apply response failed: {exc}"
        else:
            self.status = "Updated response button."
        self._refresh(dpg)

    def _studio_duplicate_dialogue_choice(self, dpg, node_id: str, choice_index: int) -> None:
        if self.canvas.selected_kind != "npc" or self.canvas.selected_id is None:
            return
        self.controller.duplicate_dialogue_choice(self.canvas.selected_id, node_id, choice_index)
        self._selected_dialogue_node_id = node_id
        self.status = "Duplicated response button."
        self._refresh(dpg)

    def _studio_delete_dialogue_choice(self, dpg, node_id: str, choice_index: int) -> None:
        if self.canvas.selected_kind != "npc" or self.canvas.selected_id is None:
            return
        if self.controller.delete_dialogue_choice(self.canvas.selected_id, node_id, choice_index):
            self._selected_dialogue_node_id = node_id
            self.status = "Deleted response button."
            self._refresh(dpg)

    def _studio_create_choice_target(self, dpg, node_id: str, choice_index: int) -> None:
        if self.canvas.selected_kind != "npc" or self.canvas.selected_id is None:
            return
        node = self.controller.add_dialogue_node(self.canvas.selected_id)
        self.controller.update_dialogue_choice(
            self.canvas.selected_id,
            node_id,
            choice_index,
            target=node.id,
        )
        self._selected_dialogue_node_id = node.id
        self.status = "Created and connected a new conversation card."
        self._refresh(dpg)

    def _studio_apply_choice_condition(self, dpg, node_id: str, choice_index: int) -> None:
        if self.canvas.selected_kind != "npc" or self.canvas.selected_id is None:
            return
        node = self._dialogue_node_by_id(node_id)
        if node is None or choice_index >= len(node.choices):
            return
        prefix = f"studio_choice_condition_{node_id}_{choice_index}"
        condition = self._condition_from_fields(dpg, prefix, node.choices[choice_index].condition)
        self.controller.update_dialogue_choice(
            self.canvas.selected_id,
            node_id,
            choice_index,
            condition=condition,
        )
        self.status = "Updated response condition."
        self._refresh(dpg)

    def _studio_add_choice_effect(self, dpg, node_id: str, choice_index: int) -> None:
        if self.canvas.selected_kind != "npc" or self.canvas.selected_id is None:
            return
        node = self._dialogue_node_by_id(node_id)
        if node is None or choice_index >= len(node.choices):
            return
        choice = node.choices[choice_index]
        actions = [*choice.actions, Action(type="say", speaker=node.speaker, text="New effect line.")]
        self.controller.update_dialogue_choice(
            self.canvas.selected_id,
            node_id,
            choice_index,
            actions=actions,
        )
        self.status = "Added response effect."
        self._refresh(dpg)

    def _studio_remove_choice_effect(self, dpg, node_id: str, choice_index: int) -> None:
        if self.canvas.selected_kind != "npc" or self.canvas.selected_id is None:
            return
        node = self._dialogue_node_by_id(node_id)
        if node is None or choice_index >= len(node.choices) or not node.choices[choice_index].actions:
            return
        self.controller.update_dialogue_choice(
            self.canvas.selected_id,
            node_id,
            choice_index,
            actions=node.choices[choice_index].actions[:-1],
        )
        self.status = "Removed last response effect."
        self._refresh(dpg)

    def _studio_apply_choice_effect(self, dpg, node_id: str, choice_index: int, effect_index: int) -> None:
        if self.canvas.selected_kind != "npc" or self.canvas.selected_id is None:
            return
        node = self._dialogue_node_by_id(node_id)
        if node is None or choice_index >= len(node.choices):
            return
        choice = node.choices[choice_index]
        if effect_index < 0 or effect_index >= len(choice.actions):
            return
        prefix = f"studio_choice_effect_{node_id}_{choice_index}_{effect_index}"
        existing = choice.actions[effect_index]
        edited = merge_action_from_visual_fields(
            existing,
            action_type=dpg.get_value(f"{prefix}_type") or existing.type,
            speaker=dpg.get_value(f"{prefix}_speaker") or "",
            text=dpg.get_value(f"{prefix}_text") or "",
            npc=dpg.get_value(f"{prefix}_npc") or "",
            node=dpg.get_value(f"{prefix}_node") or "",
            scene=dpg.get_value(f"{prefix}_scene") or "",
            spawn=dpg.get_value(f"{prefix}_spawn") or "",
            item=dpg.get_value(f"{prefix}_item") or "",
            object_id=dpg.get_value(f"{prefix}_object") or "",
            variable=dpg.get_value(f"{prefix}_variable") or "",
            value=dpg.get_value(f"{prefix}_value") or "",
            enabled=bool(dpg.get_value(f"{prefix}_enabled")),
            actions=existing.actions,
            condition=existing.condition,
            if_actions=existing.if_actions,
            else_actions=existing.else_actions,
        )
        actions = list(choice.actions)
        actions[effect_index] = edited
        self.controller.update_dialogue_choice(
            self.canvas.selected_id,
            node_id,
            choice_index,
            actions=actions,
        )
        self.status = "Updated response effect."
        self._refresh(dpg)

    def _studio_remove_choice_effect_at(self, dpg, node_id: str, choice_index: int, effect_index: int) -> None:
        if self.canvas.selected_kind != "npc" or self.canvas.selected_id is None:
            return
        node = self._dialogue_node_by_id(node_id)
        if node is None or choice_index >= len(node.choices):
            return
        actions = list(node.choices[choice_index].actions)
        if effect_index < 0 or effect_index >= len(actions):
            return
        del actions[effect_index]
        self.controller.update_dialogue_choice(
            self.canvas.selected_id,
            node_id,
            choice_index,
            actions=actions,
        )
        self.status = "Removed response effect."
        self._refresh(dpg)

    def _preview_conversation(self, dpg) -> None:
        play_current_scene(self.controller)
        self.status = "Preview launched. Click the NPC in the playtest scene to try the conversation."
        self._refresh(dpg)

    def _dialogue_node_by_id(self, node_id: str):
        npc = self._studio_npc()
        if npc is None:
            return None
        return next((node for node in npc.dialogue_nodes if node.id == node_id), None)

    def _selected_dialogue_node(self):
        item = self._selected_item()
        if item is None or not hasattr(item, "dialogue_nodes"):
            return None
        return next(
            (node for node in item.dialogue_nodes if node.id == self._selected_dialogue_node_id),
            None,
        )

    @staticmethod
    def _actions_from_editor_json(value: str) -> list[Action]:
        return actions_from_json(value)

    def _selected_item(self):
        scene = self.controller.current_scene
        if scene is None:
            return None
        return selected_item(scene, self.canvas.selected_kind, self.canvas.selected_id)

    def _action_from_fields(self, dpg, item, existing: Action | None = None) -> Action:
        action_type = dpg.get_value("action_type") or "say"
        condition = self._condition_from_fields(dpg, "action_condition", existing.condition if existing else None)
        return merge_action_from_visual_fields(
            existing,
            action_type=action_type,
            speaker=dpg.get_value("action_speaker") or "Player",
            text=dpg.get_value("action_text") or "",
            npc=dpg.get_value("action_npc") or getattr(item, "id", ""),
            node=dpg.get_value("action_node") or "",
            path=self._parse_points(dpg.get_value("prop_walk_path")),
            scene=dpg.get_value("action_scene") or dpg.get_value("prop_target_scene") or "",
            spawn=dpg.get_value("action_spawn") or dpg.get_value("prop_target_spawn") or "",
            item=dpg.get_value("action_item") or dpg.get_value("prop_item_id") or "",
            object_id=dpg.get_value("action_object") or getattr(item, "id", ""),
            variable=dpg.get_value("action_variable") or "",
            value=dpg.get_value("action_value") or "",
            enabled=bool(dpg.get_value("action_enabled")),
            actions=existing.actions if existing else [],
            condition=condition,
            if_actions=existing.if_actions if existing else [],
            else_actions=existing.else_actions if existing else [],
        )

    @staticmethod
    def _parse_action_value(value: str):
        return parse_action_value(value)

    @staticmethod
    def _parse_points(value: str) -> list[tuple[int, int]]:
        points: list[tuple[int, int]] = []
        for chunk in value.replace(";", "|").split("|"):
            chunk = chunk.strip()
            if not chunk:
                continue
            x_text, y_text = chunk.replace(",", " ").split()[:2]
            points.append((int(x_text), int(y_text)))
        return points

    @staticmethod
    def _format_points(points: list[tuple[int, int]]) -> str:
        return " | ".join(f"{x},{y}" for x, y in points)

    def _canvas_point(self, dpg) -> tuple[int, int] | None:
        if not dpg.is_item_hovered("canvas_drawlist"):
            return None
        self._update_canvas_view(dpg)
        mouse_x, mouse_y = dpg.get_mouse_pos(local=False)
        min_x, min_y = dpg.get_item_rect_min("canvas_drawlist")
        display_point = int(mouse_x - min_x), int(mouse_y - min_y)
        return self.canvas.view.display_to_logical_point(display_point)

    def _canvas_mouse_down(self, dpg) -> None:
        scene = self.controller.current_scene
        point = self._canvas_point(dpg)
        if scene is None or point is None:
            return
        if self.canvas.begin_drag(scene, point):
            self._pending_drag_undo = self.controller.snapshot()
            self._load_selected_properties(dpg)
            self._refresh_objects(dpg)
            self._draw_canvas(dpg)

    def _canvas_mouse_drag(self, dpg) -> None:
        scene = self.controller.current_scene
        point = self._canvas_point(dpg)
        if scene is None or point is None:
            return
        self.canvas.drag_to(scene, point)
        self._load_selected_properties(dpg)
        self._draw_canvas(dpg)

    def _canvas_mouse_up(self, dpg) -> None:
        if self.canvas.dragging:
            changed = self.canvas.end_drag()
            if changed:
                self.controller.record_snapshot(self._pending_drag_undo)
                self.status = "Updated canvas object."
                self._refresh(dpg)
            else:
                self._draw_canvas(dpg)
            self._pending_drag_undo = None

    def _canvas_mouse_wheel(self, dpg, delta: int) -> None:
        if not dpg.is_item_hovered("canvas_drawlist"):
            return
        self.canvas.zoom_by(1.1 if delta > 0 else 0.9)
        self._draw_canvas(dpg)

    def _canvas_pan_down(self, dpg) -> None:
        if dpg.is_item_hovered("canvas_drawlist"):
            self._last_pan_point = dpg.get_mouse_pos(local=False)

    def _canvas_pan_drag(self, dpg) -> None:
        if self._last_pan_point is None:
            return
        mouse_x, mouse_y = dpg.get_mouse_pos(local=False)
        last_x, last_y = self._last_pan_point
        self.canvas.pan_by(mouse_x - last_x, mouse_y - last_y)
        self._last_pan_point = (mouse_x, mouse_y)
        self._draw_canvas(dpg)

    def _canvas_pan_up(self, dpg) -> None:
        self._last_pan_point = None

    def _refresh(self, dpg) -> None:
        project = self.controller.project
        if project is not None and self.controller.project_root is not None:
            dpg.set_value("project_path", str(self.controller.project_root))
            dpg.configure_item("scene_list", items=list(self.controller.scenes.keys()))
            dpg.set_value("scene_list", self.controller.current_scene_id)
        dpg.set_value("simple_mode", self.simple_mode)
        dpg.set_value("dirty_text", "Unsaved changes" if self.controller.is_dirty else "Saved")
        dpg.set_value("status_text", self.status)
        self._refresh_layers(dpg)
        self._refresh_objects(dpg)
        self._refresh_inspector_visibility(dpg)
        self._refresh_assets_panel(dpg)
        self._refresh_dialogue_studio(dpg)
        self._refresh_workspace_visibility(dpg)
        self._draw_canvas(dpg)

    def _refresh_workspace_visibility(self, dpg) -> None:
        is_scenes = self.active_workspace == "Scenes"
        dpg.configure_item("scene_sidebar", show=self.active_workspace in {"Scenes", "Assets"})
        dpg.configure_item("canvas_panel", show=self.active_workspace in {"Scenes", "Logic"})
        dpg.configure_item("dialogue_studio_panel", show=self.active_workspace == "Dialogue")
        dpg.configure_item("context_panel", show=True)
        dpg.configure_item("assets_workspace_panel", show=self.active_workspace == "Assets")
        dpg.configure_item("layers_header", show=is_scenes and not self.simple_mode)
        dpg.configure_item("layer_list", show=is_scenes and not self.simple_mode)
        for workspace in ("Scenes", "Dialogue", "Logic", "Assets"):
            dpg.configure_item(
                f"workspace_{workspace.lower()}",
                label=f"[{workspace}]" if workspace == self.active_workspace else workspace,
            )

    def _refresh_assets_panel(self, dpg) -> None:
        project = self.controller.project
        items = [] if project is None else [f"{item.id}: {item.name}" for item in project.items]
        dpg.configure_item("asset_item_list", items=items)

    def _refresh_dialogue_studio(self, dpg) -> None:
        dpg.delete_item("dialogue_storyboard", children_only=True)
        dpg.delete_item("dialogue_graph_overview", children_only=True)
        npc = self._studio_npc()
        if npc is None:
            dpg.set_value("dialogue_studio_title", "Dialogue Studio")
            dpg.set_value("dialogue_studio_validation", "Select an NPC, then choose Edit Conversation.")
            return
        dpg.set_value("dialogue_studio_title", f"Dialogue Studio - {npc.name}")
        issues = validate_dialogue_graph(npc)
        dpg.set_value(
            "dialogue_studio_validation",
            "No conversation issues."
            if not issues
            else "\n".join(f"{issue.code}: {issue.message}" for issue in issues),
        )
        if not npc.dialogue_nodes:
            dpg.add_text(
                "No conversation cards yet. Add a card to start the NPC conversation.",
                parent="dialogue_storyboard",
                wrap=760,
            )
            return
        options = target_options(npc, simple=self.simple_mode)
        for card_index, node in enumerate(npc.dialogue_nodes, start=1):
            with dpg.child_window(
                parent="dialogue_storyboard",
                tag=f"studio_card_{node.id}",
                height=265 if self.simple_mode else 335,
                border=True,
            ):
                dpg.add_text(f"Card {card_index}" if self.simple_mode else f"Card {card_index} ({node.id})")
                with dpg.group(horizontal=True):
                    dpg.add_button(
                        label="Focus",
                        callback=lambda _s=None, _a=None, item=node.id: self._select_dialogue_card(dpg, item),
                    )
                    dpg.add_button(
                        label="Duplicate",
                        callback=lambda _s=None, _a=None, item=node.id: self._studio_duplicate_dialogue_node(
                            dpg,
                            item,
                        ),
                    )
                    dpg.add_button(
                        label="Delete",
                        callback=lambda _s=None, _a=None, item=node.id: self._studio_delete_dialogue_node(
                            dpg,
                            item,
                        ),
                    )
                if not self.simple_mode:
                    dpg.add_input_text(
                        tag=f"studio_node_id_{node.id}",
                        label="Node ID",
                        default_value=node.id,
                        width=-1,
                    )
                dpg.add_input_text(
                    tag=f"studio_speaker_{node.id}",
                    label="Speaker",
                    default_value=node.speaker,
                    width=-1,
                )
                dpg.add_input_text(
                    tag=f"studio_text_{node.id}",
                    label="Line",
                    default_value=node.text,
                    multiline=True,
                    height=58,
                    width=-1,
                )
                dpg.add_button(
                    label="Apply Card",
                    callback=lambda _s=None, _a=None, item=node.id: self._studio_apply_dialogue_node(
                        dpg,
                        item,
                    ),
                )
                dpg.add_text("Response buttons")
                for choice_index, choice in enumerate(node.choices):
                    self._build_dialogue_choice_row(dpg, npc, node.id, choice_index, choice, options)
                dpg.add_button(
                    label="Add Response",
                    callback=lambda _s=None, _a=None, item=node.id: self._studio_add_dialogue_choice(
                        dpg,
                        item,
                    ),
                )
        self._draw_dialogue_graph(dpg, npc)

    def _build_dialogue_choice_row(self, dpg, npc, node_id: str, choice_index: int, choice, options: list[str]) -> None:
        with dpg.group(horizontal=True):
            dpg.add_input_text(
                tag=f"studio_choice_text_{node_id}_{choice_index}",
                default_value=choice.text,
                hint="response text",
                width=220,
            )
            dpg.add_combo(
                tag=f"studio_choice_target_{node_id}_{choice_index}",
                items=options,
                default_value=target_label(npc, choice.target, simple=self.simple_mode),
                width=250,
            )
            dpg.add_button(
                label="Apply",
                callback=lambda _s=None, _a=None, item=node_id, index=choice_index: (
                    self._studio_apply_dialogue_choice(dpg, item, index)
                ),
            )
            dpg.add_button(
                label="New Target",
                callback=lambda _s=None, _a=None, item=node_id, index=choice_index: (
                    self._studio_create_choice_target(dpg, item, index)
                ),
            )
            dpg.add_button(
                label="Copy",
                callback=lambda _s=None, _a=None, item=node_id, index=choice_index: (
                    self._studio_duplicate_dialogue_choice(dpg, item, index)
                ),
            )
            dpg.add_button(
                label="Delete",
                callback=lambda _s=None, _a=None, item=node_id, index=choice_index: (
                    self._studio_delete_dialogue_choice(dpg, item, index)
                ),
            )
        dpg.add_text(choice_summary(choice, npc, simple=self.simple_mode), wrap=760)
        if not self.simple_mode:
            self._build_dialogue_choice_advanced(dpg, node_id, choice_index, choice)

    def _build_dialogue_choice_advanced(self, dpg, node_id: str, choice_index: int, choice) -> None:
        prefix = f"studio_choice_condition_{node_id}_{choice_index}"
        scene = self.controller.current_scene
        project = self.controller.project
        item_ids = [item.id for item in project.items] if project is not None else []
        object_ids = []
        if scene is not None:
            object_ids = [
                *(item.id for item in scene.hotspots),
                *(item.id for item in scene.exits),
                *(item.id for item in scene.npcs),
                *(item.id for item in scene.items),
                *(item.id for item in scene.spawns),
            ]
        with dpg.tree_node(label="Advanced: condition and effects", default_open=False):
            dpg.add_text(f"Condition: {condition_label(choice.condition)}", wrap=720)
            dpg.add_combo(
                tag=f"{prefix}_type",
                label="Condition",
                items=CONDITION_TYPES,
                default_value=choice.condition.type if choice.condition is not None else "always",
                width=-1,
            )
            dpg.add_input_text(
                tag=f"{prefix}_variable",
                label="Variable",
                default_value="" if choice.condition is None else choice.condition.variable or "",
                width=-1,
            )
            dpg.add_combo(
                tag=f"{prefix}_operator",
                label="Operator",
                items=CONDITION_OPERATORS,
                default_value="==" if choice.condition is None else choice.condition.operator,
                width=-1,
            )
            dpg.add_input_text(
                tag=f"{prefix}_value",
                label="Value",
                default_value="true" if choice.condition is None else str(choice.condition.value),
                width=-1,
            )
            dpg.add_combo(tag=f"{prefix}_item", label="Item", items=item_ids, width=-1)
            dpg.add_combo(tag=f"{prefix}_object", label="Object", items=object_ids, width=-1)
            dpg.add_combo(
                tag=f"{prefix}_not_type",
                label="Not Condition",
                items=CONDITION_TYPES[:-1],
                default_value="always",
                width=-1,
            )
            self._set_condition_fields(dpg, prefix, choice.condition)
            dpg.add_button(
                label="Apply Condition",
                callback=lambda _s=None, _a=None, item=node_id, index=choice_index: (
                    self._studio_apply_choice_condition(dpg, item, index)
                ),
            )
            dpg.add_separator()
            dpg.add_text(f"Effects: {effects_label(choice.actions)}", wrap=720)
            for effect_index, action in enumerate(choice.actions):
                self._build_dialogue_choice_effect_editor(
                    dpg,
                    node_id,
                    choice_index,
                    effect_index,
                    action,
                    item_ids,
                    object_ids,
                )
            with dpg.group(horizontal=True):
                dpg.add_button(
                    label="Add Say Effect",
                    callback=lambda _s=None, _a=None, item=node_id, index=choice_index: (
                        self._studio_add_choice_effect(dpg, item, index)
                    ),
                )
                dpg.add_button(
                    label="Remove Last Effect",
                    callback=lambda _s=None, _a=None, item=node_id, index=choice_index: (
                        self._studio_remove_choice_effect(dpg, item, index)
                    ),
                )

    def _build_dialogue_choice_effect_editor(
        self,
        dpg,
        node_id: str,
        choice_index: int,
        effect_index: int,
        action: Action,
        item_ids: list[str],
        object_ids: list[str],
    ) -> None:
        scene_ids = list(self.controller.scenes.keys())
        npc = self._studio_npc()
        node_ids = [node.id for node in npc.dialogue_nodes] if npc is not None else []
        prefix = f"studio_choice_effect_{node_id}_{choice_index}_{effect_index}"
        with dpg.tree_node(label=f"Effect {effect_index + 1}: {action_label(action)}", default_open=False):
            dpg.add_combo(
                tag=f"{prefix}_type",
                label="Effect Type",
                items=ACTION_TYPES,
                default_value=action.type,
                width=-1,
            )
            dpg.add_input_text(
                tag=f"{prefix}_speaker",
                label="Speaker",
                default_value=action.speaker or "",
                width=-1,
            )
            dpg.add_input_text(
                tag=f"{prefix}_text",
                label="Text",
                default_value=action.text or "",
                width=-1,
            )
            dpg.add_combo(tag=f"{prefix}_npc", label="NPC", items=[self.canvas.selected_id or ""], default_value=action.npc or "", width=-1)
            dpg.add_combo(tag=f"{prefix}_node", label="Dialogue Card", items=node_ids, default_value=action.node or "", width=-1)
            dpg.add_combo(tag=f"{prefix}_scene", label="Scene", items=scene_ids, default_value=action.scene or "", width=-1)
            dpg.add_combo(tag=f"{prefix}_spawn", label="Spawn", items=[], default_value=action.spawn or "", width=-1)
            dpg.add_combo(tag=f"{prefix}_item", label="Item", items=item_ids, default_value=action.item or "", width=-1)
            dpg.add_combo(tag=f"{prefix}_object", label="Object", items=object_ids, default_value=action.object_id or "", width=-1)
            dpg.add_input_text(
                tag=f"{prefix}_variable",
                label="Variable",
                default_value=action.variable or "",
                width=-1,
            )
            dpg.add_input_text(
                tag=f"{prefix}_value",
                label="Value",
                default_value="" if action.value is None else str(action.value),
                width=-1,
            )
            dpg.add_checkbox(tag=f"{prefix}_enabled", label="Enabled", default_value=bool(action.enabled))
            with dpg.group(horizontal=True):
                dpg.add_button(
                    label="Apply Effect",
                    callback=lambda _s=None, _a=None, item=node_id, index=choice_index, effect=effect_index: (
                        self._studio_apply_choice_effect(dpg, item, index, effect)
                    ),
                )
                dpg.add_button(
                    label="Remove Effect",
                    callback=lambda _s=None, _a=None, item=node_id, index=choice_index, effect=effect_index: (
                        self._studio_remove_choice_effect_at(dpg, item, index, effect)
                    ),
                )

    def _draw_dialogue_graph(self, dpg, npc) -> None:
        width = 760
        node_width = 150
        y = 40
        positions = {}
        for index, node in enumerate(npc.dialogue_nodes):
            x = 20 + (index % 4) * 185
            y = 30 + (index // 4) * 70
            positions[node.id] = (x, y)
            dpg.draw_rectangle((x, y), (x + node_width, y + 42), color=(110, 140, 170), parent="dialogue_graph_overview")
            dpg.draw_text(
                (x + 8, y + 12),
                f"{index + 1}. {node.speaker}",
                size=14,
                parent="dialogue_graph_overview",
            )
        for node in npc.dialogue_nodes:
            start = positions.get(node.id)
            if start is None:
                continue
            for choice in node.choices:
                if choice.target not in positions:
                    continue
                end = positions[choice.target]
                dpg.draw_line(
                    (start[0] + node_width, start[1] + 21),
                    (end[0], end[1] + 21),
                    color=(220, 180, 90),
                    thickness=2,
                    parent="dialogue_graph_overview",
                )
        dpg.configure_item("dialogue_graph_overview", width=width, height=max(180, y + 90))

    def _refresh_objects(self, dpg) -> None:
        scene = self.controller.current_scene
        if scene is None:
            dpg.configure_item("object_combo", items=[])
            return
        items = [
            "scene:current",
            *(f"hotspot:{item.id}" for item in scene.hotspots),
            *(f"exit:{item.id}" for item in scene.exits),
            *(f"npc:{item.id}" for item in scene.npcs),
            *(f"item:{item.id}" for item in scene.items),
            *(f"spawn:{item.id}" for item in scene.spawns),
        ]
        dpg.configure_item("object_combo", items=items)
        if self.canvas.selected_id is None and items:
            self._select_object(dpg, items[0])
        elif self.canvas.selected_kind is not None and self.canvas.selected_id is not None:
            dpg.set_value("object_combo", f"{self.canvas.selected_kind}:{self.canvas.selected_id}")
            self._load_selected_properties(dpg)

    def _refresh_layers(self, dpg) -> None:
        scene = self.controller.current_scene
        dpg.delete_item("layer_list", children_only=True)
        if scene is None:
            return
        for layer in scene.layers:
            with dpg.group(horizontal=True, parent="layer_list"):
                dpg.add_checkbox(
                    label=f"{layer.id} visible",
                    default_value=layer.visible,
                    callback=lambda _s, a, layer_id=layer.id: self._set_layer_visible(dpg, layer_id, a),
                )
                dpg.add_checkbox(
                    label="locked",
                    default_value=layer.locked,
                    callback=lambda _s, a, layer_id=layer.id: self._set_layer_locked(dpg, layer_id, a),
                )

    def _set_layer_visible(self, dpg, layer_id: str, visible: bool) -> None:
        self.controller.set_layer_state(layer_id, visible=visible)
        self.status = f"Updated layer {layer_id}."
        self._refresh(dpg)

    def _set_layer_locked(self, dpg, layer_id: str, locked: bool) -> None:
        self.controller.set_layer_state(layer_id, locked=locked)
        self.status = f"Updated layer {layer_id}."
        self._refresh(dpg)

    def _refresh_reference_dropdowns(self, dpg) -> None:
        scene = self.controller.current_scene
        project = self.controller.project
        scene_ids = list(self.controller.scenes.keys())
        layer_ids = [layer.id for layer in scene.layers] if scene is not None else []
        item_ids = [item.id for item in project.items] if project is not None else []
        object_ids: list[str] = []
        npc_ids: list[str] = []
        node_ids: list[str] = []
        if scene is not None:
            object_ids = [
                *(item.id for item in scene.hotspots),
                *(item.id for item in scene.exits),
                *(item.id for item in scene.npcs),
                *(item.id for item in scene.items),
                *(item.id for item in scene.spawns),
            ]
            npc_ids = [npc.id for npc in scene.npcs]
            selected_npc = dpg.get_value("action_npc") or self.canvas.selected_id
            npc = next((item for item in scene.npcs if item.id == selected_npc), None)
            if npc is not None:
                node_ids = [node.id for node in npc.dialogue_nodes]
        target_scene = (
            dpg.get_value("action_scene")
            or dpg.get_value("prop_target_scene")
            or self.controller.current_scene_id
            or ""
        )
        target = self.controller.scenes.get(target_scene)
        spawn_ids = [spawn.id for spawn in target.spawns] if target is not None else []

        dpg.configure_item("prop_layer", items=layer_ids)
        dpg.configure_item("prop_target_scene", items=scene_ids)
        dpg.configure_item("prop_target_spawn", items=spawn_ids)
        dpg.configure_item("action_item", items=item_ids)
        dpg.configure_item("action_object", items=object_ids)
        dpg.configure_item("action_condition_item", items=item_ids)
        dpg.configure_item("action_condition_object", items=object_ids)
        dpg.configure_item("action_npc", items=npc_ids)
        dpg.configure_item("action_node", items=node_ids)
        dpg.configure_item("action_scene", items=scene_ids)
        dpg.configure_item("action_spawn", items=spawn_ids)
        dpg.configure_item("dialogue_choice_target", items=["", *node_ids])
        dpg.configure_item("dialogue_choice_condition_item", items=item_ids)
        dpg.configure_item("dialogue_choice_condition_object", items=object_ids)

    def _load_selected_properties(self, dpg) -> None:
        item = self._selected_item()
        if item is None:
            return
        dpg.set_value("prop_id", getattr(item, "id", ""))
        dpg.set_value("prop_name", getattr(item, "name", ""))
        dpg.set_value("prop_rect", getattr(item, "rect", (0, 0, 0, 0)))
        dpg.set_value("prop_pos", getattr(item, "position", (0, 0)))
        dpg.set_value("prop_background", getattr(item, "background", ""))
        dpg.set_value("prop_sprite", getattr(item, "sprite", "") or "")
        dpg.set_value("prop_item_id", getattr(item, "item_id", ""))
        dpg.set_value("prop_enabled", bool(getattr(item, "enabled", True)))
        dpg.set_value("prop_layer", getattr(item, "layer", ""))
        dpg.set_value("prop_facing", getattr(item, "facing", "right"))
        dpg.set_value("prop_target_scene", getattr(item, "target_scene", ""))
        dpg.set_value("prop_target_spawn", getattr(item, "target_spawn", ""))
        dpg.set_value("prop_walk_path", self._format_points(getattr(item, "walk_path", [])))
        dpg.set_value("prop_lines", " | ".join(getattr(item, "lines", [])))
        actions = getattr(item, "on_click", [])
        if actions:
            action = actions[0]
            dpg.set_value("action_type", action.type)
            dpg.set_value("action_speaker", action.speaker or "")
            dpg.set_value("action_text", action.text or "")
            dpg.set_value("action_npc", action.npc or "")
            dpg.set_value("action_node", action.node or "")
            dpg.set_value("action_scene", action.scene or "")
            dpg.set_value("action_spawn", action.spawn or "")
            dpg.set_value("action_item", action.item or "")
            dpg.set_value("action_object", action.object_id or "")
            dpg.set_value("action_variable", action.variable or "")
            dpg.set_value("action_value", "" if action.value is None else str(action.value))
            dpg.set_value("action_enabled", bool(action.enabled))
            self._set_condition_fields(dpg, "action_condition", action.condition)
            dpg.set_value("action_condition_json", condition_to_json(action.condition))
            dpg.set_value("action_actions_json", action_to_json(action.actions))
            dpg.set_value("action_if_actions_json", action_to_json(action.if_actions))
            dpg.set_value("action_else_actions_json", action_to_json(action.else_actions))
            self._refresh_nested_action_lists(dpg, action)
        self._refresh_action_list(dpg)
        self._refresh_dialogue_list(dpg)
        self._refresh_reference_dropdowns(dpg)
        self._refresh_inspector_visibility(dpg)

    def _refresh_inspector_visibility(self, dpg) -> None:
        kind = self.canvas.selected_kind
        item = self._selected_item()
        has_item = item is not None
        field_visibility = inspector_field_visibility(
            kind,
            has_item,
            workspace=self.active_workspace,
            advanced=not self.simple_mode,
        )
        for tag, visible in field_visibility.items():
            dpg.configure_item(tag, show=visible)
        label = f"{self.active_workspace} Inspector"
        if kind and self.canvas.selected_id:
            label = f"{self.active_workspace} - {kind}:{self.canvas.selected_id}"
        dpg.set_value("inspector_title", label)
        self._refresh_action_editor(dpg)
        if dpg.does_item_exist("dialogue_choice_condition_type"):
            self._refresh_dialogue_choice_condition_editor(dpg)

    def _refresh_action_list(self, dpg) -> None:
        item = self._selected_item()
        actions = list(getattr(item, "on_click", [])) if item is not None else []
        labels = [f"{index + 1}. {self._action_label(action)}" for index, action in enumerate(actions)]
        dpg.configure_item("action_list", items=labels)
        if labels:
            self._selected_action_index = min(self._selected_action_index, len(labels) - 1)
            dpg.set_value("action_list", labels[self._selected_action_index])
            self._load_action_editor(dpg)

    def _load_action_editor(self, dpg) -> None:
        item = self._selected_item()
        actions = list(getattr(item, "on_click", [])) if item is not None else []
        if not actions:
            return
        action = actions[min(self._selected_action_index, len(actions) - 1)]
        dpg.set_value("action_type", action.type)
        dpg.set_value("action_speaker", action.speaker or "")
        dpg.set_value("action_text", action.text or "")
        dpg.set_value("action_npc", action.npc or "")
        dpg.set_value("action_node", action.node or "")
        dpg.set_value("action_scene", action.scene or "")
        dpg.set_value("action_spawn", action.spawn or "")
        dpg.set_value("action_item", action.item or "")
        dpg.set_value("action_object", action.object_id or "")
        dpg.set_value("action_variable", action.variable or "")
        dpg.set_value("action_value", "" if action.value is None else str(action.value))
        dpg.set_value("action_enabled", bool(action.enabled))
        self._set_condition_fields(dpg, "action_condition", action.condition)
        dpg.set_value("action_condition_json", condition_to_json(action.condition))
        dpg.set_value("action_actions_json", action_to_json(action.actions))
        dpg.set_value("action_if_actions_json", action_to_json(action.if_actions))
        dpg.set_value("action_else_actions_json", action_to_json(action.else_actions))
        self._refresh_nested_action_lists(dpg, action)
        self._refresh_action_editor(dpg)

    def _set_condition_fields(self, dpg, prefix: str, condition: Condition | None) -> None:
        if condition is None:
            dpg.set_value(f"{prefix}_type", "always")
            dpg.set_value(f"{prefix}_variable", "")
            dpg.set_value(f"{prefix}_operator", "==")
            dpg.set_value(f"{prefix}_value", "true")
            dpg.set_value(f"{prefix}_item", "")
            dpg.set_value(f"{prefix}_object", "")
            if dpg.does_item_exist(f"{prefix}_not_type"):
                dpg.set_value(f"{prefix}_not_type", "always")
            return
        dpg.set_value(f"{prefix}_type", condition.type)
        dpg.set_value(f"{prefix}_variable", condition.variable or "")
        dpg.set_value(f"{prefix}_operator", condition.operator or "==")
        dpg.set_value(f"{prefix}_value", "" if condition.value is None else str(condition.value))
        dpg.set_value(f"{prefix}_item", condition.item or "")
        dpg.set_value(f"{prefix}_object", condition.object_id or "")
        if dpg.does_item_exist(f"{prefix}_not_type"):
            dpg.set_value(f"{prefix}_not_type", condition.condition.type if condition.condition else "always")

    def _condition_from_fields(self, dpg, prefix: str, existing: Condition | None = None) -> Condition | None:
        condition_type = dpg.get_value(f"{prefix}_type") or "always"
        nested_condition = None
        if condition_type == "not":
            nested_condition = merge_condition_from_fields(
                existing.condition if existing is not None else None,
                condition_type=dpg.get_value(f"{prefix}_not_type") or "always",
            )
        return merge_condition_from_fields(
            existing,
            condition_type=condition_type,
            variable=dpg.get_value(f"{prefix}_variable") or "",
            operator=dpg.get_value(f"{prefix}_operator") or "==",
            value=dpg.get_value(f"{prefix}_value") or "",
            item=dpg.get_value(f"{prefix}_item") or "",
            object_id=dpg.get_value(f"{prefix}_object") or "",
            nested_condition=nested_condition,
        )

    def _refresh_nested_action_lists(self, dpg, action: Action) -> None:
        dpg.configure_item(
            "action_actions_list",
            items=[f"{index + 1}. {self._action_label(item)}" for index, item in enumerate(action.actions)],
        )
        dpg.configure_item(
            "action_if_actions_list",
            items=[f"{index + 1}. {self._action_label(item)}" for index, item in enumerate(action.if_actions)],
        )
        dpg.configure_item(
            "action_else_actions_list",
            items=[f"{index + 1}. {self._action_label(item)}" for index, item in enumerate(action.else_actions)],
        )

    def _refresh_action_editor(self, dpg) -> None:
        action_type = dpg.get_value("action_type") or "say"
        visible = self.active_workspace == "Logic" and self.canvas.selected_kind in {"hotspot", "npc", "item"}
        advanced = not self.simple_mode
        dpg.configure_item("action_speaker", show=visible and action_type == "say")
        dpg.configure_item("action_text", show=visible and action_type == "say")
        dpg.configure_item("action_npc", show=visible and action_type == "dialogue")
        dpg.configure_item("action_node", show=visible and action_type == "dialogue")
        dpg.configure_item("action_scene", show=visible and action_type == "change_scene")
        dpg.configure_item("action_spawn", show=visible and action_type == "change_scene")
        dpg.configure_item("action_item", show=visible and action_type in {"give_item", "remove_item"})
        dpg.configure_item("action_object", show=visible and action_type == "set_object_enabled")
        dpg.configure_item("action_variable", show=visible and action_type == "set_variable")
        dpg.configure_item("action_value", show=visible and action_type == "set_variable")
        dpg.configure_item("action_enabled", show=visible and action_type == "set_object_enabled")
        dpg.configure_item("action_condition_header", show=visible and advanced and action_type == "conditional")
        dpg.configure_item("action_condition_type", show=visible and advanced and action_type == "conditional")
        condition_type = dpg.get_value("action_condition_type") or "always"
        dpg.configure_item("action_condition_variable", show=visible and advanced and action_type == "conditional" and condition_type == "variable")
        dpg.configure_item("action_condition_operator", show=visible and advanced and action_type == "conditional" and condition_type == "variable")
        dpg.configure_item("action_condition_value", show=visible and advanced and action_type == "conditional" and condition_type == "variable")
        dpg.configure_item("action_condition_item", show=visible and advanced and action_type == "conditional" and condition_type == "has_item")
        dpg.configure_item("action_condition_object", show=visible and advanced and action_type == "conditional" and condition_type == "object_enabled")
        dpg.configure_item("action_condition_not_type", show=visible and advanced and action_type == "conditional" and condition_type == "not")
        dpg.configure_item("action_actions_header", show=visible and action_type == "sequence")
        dpg.configure_item("action_actions_list", show=visible and action_type == "sequence")
        dpg.configure_item("action_actions_buttons", show=visible and action_type == "sequence")
        dpg.configure_item("action_if_actions_header", show=visible and advanced and action_type == "conditional")
        dpg.configure_item("action_if_actions_list", show=visible and advanced and action_type == "conditional")
        dpg.configure_item("action_if_actions_buttons", show=visible and advanced and action_type == "conditional")
        dpg.configure_item("action_else_actions_header", show=visible and advanced and action_type == "conditional")
        dpg.configure_item("action_else_actions_list", show=visible and advanced and action_type == "conditional")
        dpg.configure_item("action_else_actions_buttons", show=visible and advanced and action_type == "conditional")
        dpg.configure_item("action_condition_json", show=visible and advanced and action_type == "conditional")
        dpg.configure_item("action_actions_json", show=visible and advanced and action_type == "sequence")
        dpg.configure_item("action_if_actions_json", show=visible and advanced and action_type == "conditional")
        dpg.configure_item("action_else_actions_json", show=visible and advanced and action_type == "conditional")

    def _refresh_dialogue_choice_condition_editor(self, dpg) -> None:
        visible = False
        advanced = not self.simple_mode
        condition_type = dpg.get_value("dialogue_choice_condition_type") or "always"
        dpg.configure_item("dialogue_choice_condition_header", show=visible and advanced)
        dpg.configure_item("dialogue_choice_condition_type", show=visible and advanced)
        dpg.configure_item("dialogue_choice_condition_variable", show=visible and advanced and condition_type == "variable")
        dpg.configure_item("dialogue_choice_condition_operator", show=visible and advanced and condition_type == "variable")
        dpg.configure_item("dialogue_choice_condition_value", show=visible and advanced and condition_type == "variable")
        dpg.configure_item("dialogue_choice_condition_item", show=visible and advanced and condition_type == "has_item")
        dpg.configure_item("dialogue_choice_condition_object", show=visible and advanced and condition_type == "object_enabled")
        dpg.configure_item("dialogue_choice_condition_not_type", show=visible and advanced and condition_type == "not")
        dpg.configure_item("dialogue_choice_condition_json", show=visible and advanced)
        dpg.configure_item("dialogue_choice_actions_json", show=visible and advanced)

    def _refresh_dialogue_list(self, dpg) -> None:
        item = self._selected_item()
        nodes = list(getattr(item, "dialogue_nodes", [])) if item is not None else []
        labels = [f"{node.id} - {node.speaker}" for node in nodes]
        dpg.configure_item("dialogue_node_list", items=labels)
        if nodes:
            if self._selected_dialogue_node_id not in {node.id for node in nodes}:
                self._selected_dialogue_node_id = nodes[0].id
            for label in labels:
                if label.startswith(f"{self._selected_dialogue_node_id} "):
                    dpg.set_value("dialogue_node_list", label)
                    break
            self._load_dialogue_editor(dpg)

    def _load_dialogue_editor(self, dpg) -> None:
        item = self._selected_item()
        if item is None or not hasattr(item, "dialogue_nodes"):
            return
        node = next(
            (node for node in item.dialogue_nodes if node.id == self._selected_dialogue_node_id),
            None,
        )
        if node is None:
            return
        dpg.set_value("dialogue_node_id", node.id)
        dpg.set_value("dialogue_speaker", node.speaker)
        dpg.set_value("dialogue_text", node.text)
        dpg.set_value("dialogue_node_actions_json", action_to_json(node.actions))
        dpg.configure_item(
            "dialogue_node_action_list",
            items=[f"{index + 1}. {self._action_label(action)}" for index, action in enumerate(node.actions)],
        )
        self._refresh_dialogue_choice_list(dpg)

    def _refresh_dialogue_choice_list(self, dpg) -> None:
        node = self._selected_dialogue_node()
        choices = list(node.choices) if node is not None else []
        labels = [choice_label(index, choice) for index, choice in enumerate(choices)]
        dpg.configure_item("dialogue_choice_list", items=labels)
        if not choices:
            dpg.set_value("dialogue_choice_text", "")
            dpg.set_value("dialogue_choice_target", "")
            self._set_condition_fields(dpg, "dialogue_choice_condition", None)
            dpg.set_value("dialogue_choice_condition_json", condition_to_json(None))
            dpg.set_value("dialogue_choice_actions_json", action_to_json([]))
            dpg.configure_item("dialogue_choice_action_list", items=[])
            return
        self._selected_dialogue_choice_index = min(self._selected_dialogue_choice_index, len(choices) - 1)
        dpg.set_value("dialogue_choice_list", labels[self._selected_dialogue_choice_index])
        self._load_dialogue_choice_editor(dpg)

    def _load_dialogue_choice_editor(self, dpg) -> None:
        node = self._selected_dialogue_node()
        if node is None or not node.choices:
            return
        choice = node.choices[min(self._selected_dialogue_choice_index, len(node.choices) - 1)]
        dpg.set_value("dialogue_choice_text", choice.text)
        dpg.set_value("dialogue_choice_target", choice.target or "")
        self._set_condition_fields(dpg, "dialogue_choice_condition", choice.condition)
        dpg.set_value("dialogue_choice_condition_json", choice_condition_json(choice))
        dpg.set_value("dialogue_choice_actions_json", choice_actions_json(choice))
        dpg.configure_item(
            "dialogue_choice_action_list",
            items=[f"{index + 1}. {self._action_label(action)}" for index, action in enumerate(choice.actions)],
        )
        self._refresh_dialogue_choice_condition_editor(dpg)

    @staticmethod
    def _action_label(action: Action) -> str:
        return action_label(action)

    def _draw_canvas(self, dpg) -> None:
        draw_canvas(self, dpg)

    def _update_canvas_view(self, dpg) -> None:
        update_canvas_view(self, dpg)

    def _canvas_available_size(self, dpg) -> tuple[int, int]:
        return canvas_available_size(dpg)

    def _project_resolution(self) -> tuple[int, int]:
        return project_resolution(self)

    @staticmethod
    def _layer_visible(scene, layer_id: str) -> bool:
        return layer_visible(scene, layer_id)

    @staticmethod
    def _layer_locked(scene, layer_id: str) -> bool:
        return layer_locked(scene, layer_id)

    def _texture_for(self, dpg, relative_path: str | None) -> tuple[str, int, int] | None:
        return texture_for(self, dpg, relative_path)
