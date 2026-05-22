from __future__ import annotations

import time
from pathlib import Path

from pce.editor.canvas import CanvasState, selected_item
from pce.editor.preview_bridge import play_current_scene, run_full_game
from pce.editor.project_controller import ProjectController
from pce.shared.constants import DEFAULT_HEIGHT, DEFAULT_WIDTH
from pce.shared.models import Action, DialogueChoice


class EditorApp:
    def __init__(self, project: Path | None = None) -> None:
        self.controller = ProjectController()
        self.canvas = CanvasState()
        self.status = "No project open."
        self._last_autosave_check = time.monotonic()
        self._textures: dict[str, tuple[str, int, int]] = {}
        self._selected_action_index = 0
        self._selected_dialogue_node_id: str | None = None
        self._last_pan_point: tuple[float, float] | None = None
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
                    dpg.add_menu_item(label="Open Folder...", callback=lambda: dpg.show_item("project_dialog"))
                    dpg.add_menu_item(label="Save", callback=lambda: self._save(dpg))
                    dpg.add_menu_item(label="Export Playable", callback=lambda: self._export(dpg))
                with dpg.menu(label="Run"):
                    dpg.add_menu_item(label="Validate", callback=lambda: self._validate(dpg))
                    dpg.add_menu_item(label="Play Scene", callback=lambda: self._play_scene(dpg))
                    dpg.add_menu_item(label="Run Game", callback=lambda: self._run_game(dpg))
            with dpg.group(horizontal=True):
                dpg.add_text("PointClick Editor")
                dpg.add_spacer(width=18)
                dpg.add_button(label="Open", callback=lambda: dpg.show_item("project_dialog"))
                dpg.add_button(label="Save", callback=lambda: self._save(dpg))
                dpg.add_button(label="Undo", callback=lambda: self._undo(dpg))
                dpg.add_button(label="Redo", callback=lambda: self._redo(dpg))
                dpg.add_button(label="Fit", callback=lambda: self._fit_canvas(dpg))
                dpg.add_button(label="-", callback=lambda: self._zoom_canvas(dpg, 0.85))
                dpg.add_button(label="+", callback=lambda: self._zoom_canvas(dpg, 1.15))
                dpg.add_checkbox(
                    tag="snap_grid",
                    label="Snap",
                    default_value=True,
                    callback=lambda _s, a: self._set_snap(dpg, a),
                )
                dpg.add_checkbox(
                    tag="show_grid",
                    label="Grid",
                    default_value=True,
                    callback=lambda _s, a: self._set_grid(dpg, a),
                )
                dpg.add_button(label="Validate", callback=lambda: self._validate(dpg))
                dpg.add_button(label="Play Scene", callback=lambda: self._play_scene(dpg))
                dpg.add_button(label="Export", callback=lambda: self._export(dpg))
                dpg.add_text("", tag="dirty_text")

            with dpg.group(horizontal=True):
                with dpg.child_window(width=300, height=-125, border=True):
                    dpg.add_text("Scenes")
                    dpg.add_listbox(
                        tag="scene_list",
                        items=[],
                        num_items=7,
                        width=-1,
                        callback=lambda _s, a: self._select_scene(dpg, a),
                    )
                    with dpg.group(horizontal=True):
                        dpg.add_input_text(
                            tag="new_scene_id",
                            default_value="scene_2",
                            width=170,
                            hint="new scene id",
                        )
                        dpg.add_button(label="Create", callback=lambda: self._create_scene(dpg))
                    dpg.add_button(label="Use As Start Scene", callback=lambda: self._set_start_scene(dpg))
                    dpg.add_separator()
                    dpg.add_text("Layers")
                    with dpg.group(tag="layer_list"):
                        pass
                    dpg.add_separator()
                    dpg.add_text("Objects")
                    dpg.add_listbox(
                        tag="object_combo",
                        items=[],
                        num_items=11,
                        width=-1,
                        callback=lambda _s, a: self._select_object(dpg, a),
                    )
                    with dpg.group(horizontal=True):
                        dpg.add_button(label="Hotspot", callback=lambda: self._add_hotspot(dpg))
                        dpg.add_button(label="Exit", callback=lambda: self._add_exit(dpg))
                        dpg.add_button(label="NPC", callback=lambda: self._add_npc(dpg))
                    with dpg.group(horizontal=True):
                        dpg.add_button(label="Spawn", callback=lambda: self._add_spawn(dpg))
                        dpg.add_button(label="Item", callback=lambda: self._add_scene_item(dpg))

                with dpg.child_window(tag="canvas_panel", width=-345, height=-125, border=True):
                    with dpg.drawlist(tag="canvas_drawlist", width=1, height=1):
                        pass

                with dpg.child_window(width=335, height=-125, border=True):
                    dpg.add_text("Inspector", tag="inspector_title")
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
                    dpg.add_input_text(tag="prop_target_scene", label="Target Scene", width=-1)
                    dpg.add_input_text(tag="prop_target_spawn", label="Target Spawn", width=-1)
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
                        items=[
                            "say",
                            "dialogue",
                            "move_player",
                            "change_scene",
                            "give_item",
                            "set_variable",
                            "set_object_enabled",
                        ],
                        default_value="say",
                        width=-1,
                        callback=lambda _s, _a: self._refresh_action_editor(dpg),
                    )
                    dpg.add_input_text(tag="action_speaker", label="Speaker", default_value="Player", width=-1)
                    dpg.add_input_text(tag="action_text", label="Text", width=-1, multiline=True, height=70)
                    dpg.add_input_text(tag="action_item", label="Item", width=-1)
                    dpg.add_input_text(tag="action_object", label="Object", width=-1)
                    dpg.add_input_text(tag="action_variable", label="Variable", width=-1)
                    dpg.add_input_text(tag="action_value", label="Value", width=-1)
                    dpg.add_checkbox(tag="action_enabled", label="Enabled", default_value=False)
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
                    dpg.add_input_text(
                        tag="dialogue_choices",
                        label="Choices",
                        width=-1,
                        multiline=True,
                        height=72,
                        hint="Text -> target, one per line",
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
        with dpg.theme(tag="editor_theme"):
            with dpg.theme_component(dpg.mvAll):
                dpg.add_theme_color(dpg.mvThemeCol_WindowBg, (18, 21, 26))
                dpg.add_theme_color(dpg.mvThemeCol_ChildBg, (24, 28, 34))
                dpg.add_theme_color(dpg.mvThemeCol_FrameBg, (34, 39, 48))
                dpg.add_theme_color(dpg.mvThemeCol_FrameBgHovered, (45, 52, 64))
                dpg.add_theme_color(dpg.mvThemeCol_Button, (43, 50, 61))
                dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (60, 71, 86))
                dpg.add_theme_color(dpg.mvThemeCol_Header, (52, 95, 130))
                dpg.add_theme_color(dpg.mvThemeCol_Text, (225, 230, 238))
                dpg.add_theme_style(dpg.mvStyleVar_WindowPadding, 10, 10)
                dpg.add_theme_style(dpg.mvStyleVar_FramePadding, 8, 5)
                dpg.add_theme_style(dpg.mvStyleVar_ItemSpacing, 8, 6)
                dpg.add_theme_style(dpg.mvStyleVar_WindowRounding, 4)
                dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 4)
        dpg.bind_theme("editor_theme")

    def _new_project(self, dpg) -> None:
        path = Path(dpg.get_value("project_path") or "example_project")
        self.controller.new_project(path)
        self.status = f"Created {path}"
        self._refresh(dpg)

    def _open_project(self, dpg) -> None:
        path = Path(dpg.get_value("project_path") or ".")
        self.controller.open_project(path)
        self.status = f"Opened {path}"
        self._refresh(dpg)

    def _open_project_from_dialog(self, dpg, app_data) -> None:
        path = self._dialog_path(app_data)
        if path is None:
            return
        self.controller.open_project(path)
        self.canvas.reset_view()
        self.status = f"Opened {path}"
        self._refresh(dpg)

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
        self.controller.create_scene(dpg.get_value("new_scene_id"))
        self.status = "Created scene."
        self._refresh(dpg)

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
        if self.canvas.selected_kind in {None, "scene"} or self.canvas.selected_id is None:
            self.status = "Select an object before duplicating."
            self._refresh(dpg)
            return
        new_id = self.controller.duplicate_scene_object(self.canvas.selected_kind, self.canvas.selected_id)
        if new_id is None:
            self.status = "Nothing duplicated."
        else:
            self.canvas.selected_id = new_id
            self.status = f"Duplicated {self.canvas.selected_kind}."
        self._refresh(dpg)

    def _request_delete_selected(self, dpg) -> None:
        if self.canvas.selected_kind in {None, "scene"} or self.canvas.selected_id is None:
            self.status = "Select an object before deleting."
            self._refresh(dpg)
            return
        dpg.show_item("confirm_delete_modal")

    def _confirm_delete_selected(self, dpg) -> None:
        dpg.hide_item("confirm_delete_modal")
        if self.canvas.selected_kind in {None, "scene"} or self.canvas.selected_id is None:
            self.status = "Select an object before deleting."
            self._refresh(dpg)
            return
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
        actions[self._selected_action_index] = self._action_from_fields(dpg, item)
        self.controller.set_actions(kind, object_id, actions)
        self.status = "Applied action."
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
        self._load_dialogue_editor(dpg)

    def _apply_dialogue_node(self, dpg) -> None:
        if self.canvas.selected_kind != "npc" or self.canvas.selected_id is None:
            return
        node_id = self._selected_dialogue_node_id
        if node_id is None:
            return
        choices = self._parse_dialogue_choices(dpg.get_value("dialogue_choices"))
        self._selected_dialogue_node_id = self.controller.update_dialogue_node(
            self.canvas.selected_id,
            node_id,
            new_id=dpg.get_value("dialogue_node_id"),
            speaker=dpg.get_value("dialogue_speaker"),
            text=dpg.get_value("dialogue_text"),
            choices=choices,
        )
        self.status = "Applied dialogue node."
        self._refresh(dpg)

    @staticmethod
    def _parse_dialogue_choices(value: str) -> list[DialogueChoice]:
        choices: list[DialogueChoice] = []
        for line in value.splitlines():
            text = line.strip()
            if not text:
                continue
            if "->" in text:
                label, target = text.split("->", 1)
                choices.append(DialogueChoice(text=label.strip(), target=target.strip() or None))
            else:
                choices.append(DialogueChoice(text=text))
        return choices

    def _selected_item(self):
        scene = self.controller.current_scene
        if scene is None:
            return None
        return selected_item(scene, self.canvas.selected_kind, self.canvas.selected_id)

    def _action_from_fields(self, dpg, item) -> Action:
        action_type = dpg.get_value("action_type") or "say"
        if action_type == "give_item":
            return Action(type="give_item", item=dpg.get_value("action_item") or dpg.get_value("prop_item_id"))
        if action_type == "set_object_enabled":
            return Action(
                type="set_object_enabled",
                object_id=dpg.get_value("action_object") or getattr(item, "id", ""),
                enabled=bool(dpg.get_value("action_enabled")),
            )
        if action_type == "set_variable":
            return Action(
                type="set_variable",
                variable=dpg.get_value("action_variable"),
                value=self._parse_action_value(dpg.get_value("action_value")),
            )
        if action_type == "dialogue":
            return Action(type="dialogue", npc=getattr(item, "id", ""), node=self._selected_dialogue_node_id)
        if action_type == "move_player":
            return Action(type="move_player", path=self._parse_points(dpg.get_value("prop_walk_path")))
        if action_type == "change_scene":
            return Action(
                type="change_scene",
                scene=dpg.get_value("prop_target_scene"),
                spawn=dpg.get_value("prop_target_spawn"),
            )
        if action_type == "sequence":
            return Action(
                type="sequence",
                actions=[
                    Action(
                        type="say",
                        speaker=dpg.get_value("action_speaker") or "Player",
                        text=dpg.get_value("action_text") or "",
                    )
                ],
            )
        return Action(
            type="say",
            speaker=dpg.get_value("action_speaker") or "Player",
            text=dpg.get_value("action_text") or "",
        )

    @staticmethod
    def _parse_action_value(value: str):
        if value.lower() == "true":
            return True
        if value.lower() == "false":
            return False
        try:
            return int(value)
        except ValueError:
            return value

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
            self.controller.record_undo()
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
            self.canvas.end_drag()
            self.status = "Updated canvas object."
            self._refresh(dpg)

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
        dpg.set_value("dirty_text", "Unsaved changes" if self.controller.is_dirty else "Saved")
        dpg.set_value("status_text", self.status)
        self._refresh_layers(dpg)
        self._refresh_objects(dpg)
        self._refresh_inspector_visibility(dpg)
        self._draw_canvas(dpg)

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
            dpg.set_value("action_item", action.item or "")
            dpg.set_value("action_object", action.object_id or "")
            dpg.set_value("action_variable", action.variable or "")
            dpg.set_value("action_value", "" if action.value is None else str(action.value))
            dpg.set_value("action_enabled", bool(action.enabled))
        self._refresh_action_list(dpg)
        self._refresh_dialogue_list(dpg)
        self._refresh_inspector_visibility(dpg)

    def _refresh_inspector_visibility(self, dpg) -> None:
        kind = self.canvas.selected_kind
        item = self._selected_item()
        has_item = item is not None
        field_visibility = {
            "prop_id": has_item,
            "prop_name": has_item and hasattr(item, "name"),
            "prop_rect": has_item and hasattr(item, "rect"),
            "prop_pos": has_item and hasattr(item, "position"),
            "prop_background": kind == "scene",
            "background_button": kind == "scene",
            "prop_sprite": kind == "npc",
            "npc_sprite_button": kind == "npc",
            "player_sprite_button": kind == "scene",
            "prop_item_id": kind == "item",
            "prop_target_scene": kind == "exit",
            "prop_target_spawn": kind == "exit",
            "prop_walk_path": kind == "exit",
            "prop_lines": kind == "npc",
            "duplicate_button": kind not in {None, "scene"},
            "delete_button": kind not in {None, "scene"},
            "actions_header": kind in {"hotspot", "npc", "item"},
            "action_list": kind in {"hotspot", "npc", "item"},
            "action_buttons": kind in {"hotspot", "npc", "item"},
            "action_type": kind in {"hotspot", "npc", "item"},
            "action_speaker": kind in {"hotspot", "npc", "item"},
            "action_text": kind in {"hotspot", "npc", "item"},
            "action_item": kind in {"hotspot", "npc", "item"},
            "action_object": kind in {"hotspot", "npc", "item"},
            "action_variable": kind in {"hotspot", "npc", "item"},
            "action_value": kind in {"hotspot", "npc", "item"},
            "action_enabled": kind in {"hotspot", "npc", "item"},
            "dialogue_header": kind == "npc",
            "dialogue_node_list": kind == "npc",
            "dialogue_buttons": kind == "npc",
            "dialogue_node_id": kind == "npc",
            "dialogue_speaker": kind == "npc",
            "dialogue_text": kind == "npc",
            "dialogue_choices": kind == "npc",
        }
        for tag, visible in field_visibility.items():
            dpg.configure_item(tag, show=visible)
        label = "Inspector"
        if kind and self.canvas.selected_id:
            label = f"Inspector - {kind}:{self.canvas.selected_id}"
        dpg.set_value("inspector_title", label)
        self._refresh_action_editor(dpg)

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
        dpg.set_value("action_item", action.item or "")
        dpg.set_value("action_object", action.object_id or "")
        dpg.set_value("action_variable", action.variable or "")
        dpg.set_value("action_value", "" if action.value is None else str(action.value))
        dpg.set_value("action_enabled", bool(action.enabled))
        self._refresh_action_editor(dpg)

    def _refresh_action_editor(self, dpg) -> None:
        action_type = dpg.get_value("action_type") or "say"
        visible = self.canvas.selected_kind in {"hotspot", "npc", "item"}
        dpg.configure_item("action_speaker", show=visible and action_type == "say")
        dpg.configure_item("action_text", show=visible and action_type == "say")
        dpg.configure_item("action_item", show=visible and action_type == "give_item")
        dpg.configure_item("action_object", show=visible and action_type == "set_object_enabled")
        dpg.configure_item("action_variable", show=visible and action_type == "set_variable")
        dpg.configure_item("action_value", show=visible and action_type == "set_variable")
        dpg.configure_item("action_enabled", show=visible and action_type == "set_object_enabled")

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
        dpg.set_value(
            "dialogue_choices",
            "\n".join(
                f"{choice.text} -> {choice.target}" if choice.target else choice.text
                for choice in node.choices
            ),
        )

    @staticmethod
    def _action_label(action: Action) -> str:
        if action.type == "say":
            return f"say: {action.text or ''}".strip()
        if action.type == "dialogue":
            suffix = f"@{action.node}" if action.node else ""
            return f"dialogue {action.npc or ''}{suffix}".strip()
        if action.type == "change_scene":
            return f"change_scene: {action.scene or ''}"
        if action.type == "give_item":
            return f"give_item: {action.item or ''}"
        if action.type == "set_variable":
            return f"set_variable: {action.variable or ''}"
        if action.type == "set_object_enabled":
            return f"set_object_enabled: {action.object_id or ''}"
        return action.type

    def _draw_canvas(self, dpg) -> None:
        scene = self.controller.current_scene
        self._update_canvas_view(dpg)
        view = self.canvas.view
        dpg.delete_item("canvas_drawlist", children_only=True)
        if scene is None:
            return
        dpg.draw_rectangle(
            (0, 0),
            (view.display_width, view.display_height),
            fill=(27, 31, 38),
            parent="canvas_drawlist",
        )
        scene_left, scene_top, scene_right, scene_bottom = view.scene_rect
        background = self._texture_for(dpg, scene.background)
        if background:
            tag, _width, _height = background
            dpg.draw_image(
                tag,
                (scene_left, scene_top),
                (scene_right, scene_bottom),
                parent="canvas_drawlist",
            )
        else:
            dpg.draw_rectangle(
                (scene_left, scene_top),
                (scene_right, scene_bottom),
                fill=(35, 40, 48),
                parent="canvas_drawlist",
            )
        if self.canvas.show_grid:
            for x in range(0, view.logical_width + 1, self.canvas.grid_size):
                start = view.logical_to_display_point((x, 0))
                end = view.logical_to_display_point((x, view.logical_height))
                dpg.draw_line(start, end, color=(52, 58, 66), parent="canvas_drawlist")
            for y in range(0, view.logical_height + 1, self.canvas.grid_size):
                start = view.logical_to_display_point((0, y))
                end = view.logical_to_display_point((view.logical_width, y))
                dpg.draw_line(start, end, color=(52, 58, 66), parent="canvas_drawlist")
        dpg.draw_rectangle(
            (scene_left, scene_top),
            (scene_right, scene_bottom),
            color=(130, 145, 165),
            thickness=1,
            parent="canvas_drawlist",
        )
        scale_text = f"{view.logical_width}x{view.logical_height} at {view.scale:.2f}x"
        dpg.draw_text((scene_left + 10, scene_top + 8), scale_text, color=(185, 195, 210), size=13, parent="canvas_drawlist")
        for hotspot in scene.hotspots:
            if not self._layer_visible(scene, hotspot.layer):
                continue
            x, y, w, h = hotspot.rect
            left, top, right, bottom = view.logical_to_display_rect(hotspot.rect)
            handle = view.logical_to_display_rect((x + w - 8, y + h - 8, 16, 16))
            color = (255, 212, 96) if hotspot.id != self.canvas.selected_id else (255, 245, 170)
            dpg.draw_rectangle((left, top), (right, bottom), color=color, thickness=2, parent="canvas_drawlist")
            if self._layer_locked(scene, hotspot.layer):
                dpg.draw_line((left, top), (right, bottom), color=(190, 95, 95), parent="canvas_drawlist")
            dpg.draw_rectangle(handle[:2], handle[2:], fill=color, parent="canvas_drawlist")
            dpg.draw_text(view.logical_to_display_point((x, y - 18)), hotspot.id, color=color, size=14, parent="canvas_drawlist")
        for exit_data in scene.exits:
            if not self._layer_visible(scene, exit_data.layer):
                continue
            x, y, w, h = exit_data.rect
            left, top, right, bottom = view.logical_to_display_rect(exit_data.rect)
            handle = view.logical_to_display_rect((x + w - 8, y + h - 8, 16, 16))
            color = (95, 196, 134) if exit_data.id != self.canvas.selected_id else (150, 235, 180)
            dpg.draw_rectangle((left, top), (right, bottom), color=color, thickness=2, parent="canvas_drawlist")
            if self._layer_locked(scene, exit_data.layer):
                dpg.draw_line((left, top), (right, bottom), color=(190, 95, 95), parent="canvas_drawlist")
            dpg.draw_rectangle(handle[:2], handle[2:], fill=color, parent="canvas_drawlist")
            dpg.draw_text(view.logical_to_display_point((x, y - 18)), exit_data.id, color=color, size=14, parent="canvas_drawlist")
            if len(exit_data.walk_path) > 1:
                dpg.draw_polyline(
                    [view.logical_to_display_point(point) for point in exit_data.walk_path],
                    color=color,
                    thickness=2,
                    parent="canvas_drawlist",
                )
            for point in exit_data.walk_path:
                dpg.draw_circle(view.logical_to_display_point(point), 5, color=color, fill=color, parent="canvas_drawlist")
        for npc in scene.npcs:
            if not self._layer_visible(scene, "characters"):
                continue
            x, y = npc.position
            texture = self._texture_for(dpg, npc.sprite)
            if texture:
                tag, width, height = texture
                left, top = view.logical_to_display_point((x - width // 2, y - height))
                right, bottom = view.logical_to_display_point((x + width // 2, y))
                dpg.draw_image(tag, (left, top), (right, bottom), parent="canvas_drawlist")
            left, top, right, bottom = view.logical_to_display_rect((x - 18, y - 60, 36, 60))
            color = (180, 130, 220) if npc.id != self.canvas.selected_id else (220, 175, 255)
            dpg.draw_rectangle((left, top), (right, bottom), color=color, thickness=2, parent="canvas_drawlist")
            if self._layer_locked(scene, "characters"):
                dpg.draw_line((left, top), (right, bottom), color=(190, 95, 95), parent="canvas_drawlist")
            dpg.draw_text(view.logical_to_display_point((x - 18, y - 78)), npc.id, color=color, size=14, parent="canvas_drawlist")
        for item in scene.items:
            if not self._layer_visible(scene, item.layer):
                continue
            x, y, w, h = item.rect
            left, top, right, bottom = view.logical_to_display_rect(item.rect)
            color = (220, 180, 80) if item.id != self.canvas.selected_id else (255, 220, 120)
            dpg.draw_rectangle((left, top), (right, bottom), color=color, thickness=2, parent="canvas_drawlist")
            if self._layer_locked(scene, item.layer):
                dpg.draw_line((left, top), (right, bottom), color=(190, 95, 95), parent="canvas_drawlist")
            dpg.draw_text(view.logical_to_display_point((x, y - 18)), item.id, color=color, size=14, parent="canvas_drawlist")
        for spawn in scene.spawns:
            if not self._layer_visible(scene, "characters"):
                continue
            x, y = spawn.position
            color = (120, 170, 255) if spawn.id != self.canvas.selected_id else (180, 210, 255)
            dpg.draw_circle(view.logical_to_display_point((x, y)), 7, color=color, fill=color, parent="canvas_drawlist")
            dpg.draw_text(view.logical_to_display_point((x + 8, y - 8)), spawn.id, color=color, size=14, parent="canvas_drawlist")

    def _update_canvas_view(self, dpg) -> None:
        width, height = self._canvas_available_size(dpg)
        logical_width, logical_height = self._project_resolution()
        self.canvas.view = self.canvas.view.from_view(
            logical_width,
            logical_height,
            width,
            height,
            self.canvas.zoom,
            self.canvas.pan,
        )
        dpg.configure_item("canvas_drawlist", width=width, height=height)

    def _canvas_available_size(self, dpg) -> tuple[int, int]:
        try:
            panel_width, panel_height = dpg.get_item_rect_size("canvas_panel")
        except Exception:
            return DEFAULT_WIDTH, DEFAULT_HEIGHT
        return max(1, int(panel_width) - 12), max(1, int(panel_height) - 36)

    def _project_resolution(self) -> tuple[int, int]:
        project = self.controller.project
        if project is None:
            return DEFAULT_WIDTH, DEFAULT_HEIGHT
        return project.resolution.width, project.resolution.height

    @staticmethod
    def _layer_visible(scene, layer_id: str) -> bool:
        for layer in scene.layers:
            if layer.id == layer_id:
                return layer.visible
        return True

    @staticmethod
    def _layer_locked(scene, layer_id: str) -> bool:
        for layer in scene.layers:
            if layer.id == layer_id:
                return layer.locked
        return False

    def _texture_for(self, dpg, relative_path: str | None) -> tuple[str, int, int] | None:
        if not relative_path or self.controller.project_root is None:
            return None
        path = self.controller.project_root / relative_path
        if not path.exists():
            return None
        key = str(path)
        if key in self._textures:
            return self._textures[key]
        try:
            width, height, _channels, data = dpg.load_image(str(path))
            tag = f"texture_{len(self._textures)}"
            dpg.add_static_texture(width, height, data, tag=tag, parent="texture_registry")
        except Exception:
            return None
        self._textures[key] = (tag, width, height)
        return self._textures[key]

