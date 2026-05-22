from __future__ import annotations

import time
from pathlib import Path

from pce.editor.canvas import CanvasState, selected_item
from pce.editor.preview_bridge import play_current_scene, run_full_game
from pce.editor.project_controller import ProjectController
from pce.shared.models import Action


class EditorApp:
    def __init__(self, project: Path | None = None) -> None:
        self.controller = ProjectController()
        self.canvas = CanvasState()
        self.status = "No project open."
        self._last_autosave_check = time.monotonic()
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
        with dpg.window(tag="main_window"):
            with dpg.group(horizontal=True):
                dpg.add_button(label="New Project", callback=lambda: self._new_project(dpg))
                dpg.add_button(label="Open", callback=lambda: self._open_project(dpg))
                dpg.add_button(label="Save", callback=lambda: self._save(dpg))
                dpg.add_button(label="Autosave", callback=lambda: self._autosave(dpg))
                dpg.add_button(label="Undo", callback=lambda: self._undo(dpg))
                dpg.add_button(label="Redo", callback=lambda: self._redo(dpg))
                dpg.add_button(label="Validate", callback=lambda: self._validate(dpg))
                dpg.add_button(label="Play Scene", callback=lambda: self._play_scene(dpg))
                dpg.add_button(label="Run Game", callback=lambda: self._run_game(dpg))
                dpg.add_button(label="Export", callback=lambda: self._export(dpg))

            with dpg.group(horizontal=True):
                with dpg.child_window(width=260, height=650, border=True):
                    dpg.add_text("Project")
                    dpg.add_input_text(tag="project_path", label="Folder", width=220)
                    dpg.add_input_text(tag="asset_path", label="Asset file", width=220)
                    dpg.add_separator()
                    dpg.add_text("Scenes")
                    dpg.add_listbox(tag="scene_list", items=[], num_items=8, callback=lambda s, a: self._select_scene(dpg, a))
                    dpg.add_input_text(tag="new_scene_id", label="New scene id", default_value="scene_2", width=220)
                    dpg.add_button(label="Create Scene", callback=lambda: self._create_scene(dpg))
                    dpg.add_button(label="Use Scene As Start", callback=lambda: self._set_start_scene(dpg))
                    dpg.add_button(label="Import Background", callback=lambda: self._import_background(dpg))
                    dpg.add_button(label="Import Player Sprite", callback=lambda: self._import_player_sprite(dpg))
                    dpg.add_separator()
                    dpg.add_text("Tools")
                    dpg.add_checkbox(tag="snap_grid", label="Snap to grid", default_value=True, callback=lambda s, a: setattr(self.canvas, "snap_to_grid", a))
                    dpg.add_button(label="Add Hotspot", callback=lambda: self._add_hotspot(dpg))
                    dpg.add_button(label="Add Exit", callback=lambda: self._add_exit(dpg))
                    dpg.add_button(label="Add NPC", callback=lambda: self._add_npc(dpg))
                    dpg.add_button(label="Add Spawn", callback=lambda: self._add_spawn(dpg))

                with dpg.child_window(width=700, height=650, border=True):
                    dpg.add_text("Scene Canvas")
                    with dpg.drawlist(tag="canvas_drawlist", width=660, height=560):
                        pass

                with dpg.child_window(width=285, height=650, border=True):
                    dpg.add_text("Properties")
                    dpg.add_text("Selected")
                    dpg.add_combo(tag="object_combo", items=[], width=240, callback=lambda s, a: self._select_object(dpg, a))
                    dpg.add_input_text(tag="prop_id", label="id", width=240)
                    dpg.add_input_text(tag="prop_name", label="name", width=240)
                    dpg.add_input_intx(tag="prop_rect", label="rect", size=4, width=240)
                    dpg.add_input_intx(tag="prop_pos", label="position", size=2, width=240)
                    dpg.add_input_text(tag="prop_background", label="background", width=240)
                    dpg.add_input_text(tag="prop_sprite", label="sprite", width=240)
                    dpg.add_input_text(tag="prop_target_scene", label="target scene", width=240)
                    dpg.add_input_text(tag="prop_target_spawn", label="target spawn", width=240)
                    dpg.add_input_text(tag="prop_walk_path", label="walk path", width=240)
                    dpg.add_input_text(tag="prop_lines", label="lines | separated", width=240)
                    dpg.add_combo(tag="action_type", label="action", items=["say", "dialogue", "move_player", "change_scene", "sequence"], default_value="say", width=240)
                    dpg.add_input_text(tag="action_speaker", label="speaker", default_value="Player", width=240)
                    dpg.add_input_text(tag="action_text", label="text", width=240)
                    dpg.add_button(label="Apply Properties", callback=lambda: self._apply_properties(dpg))
                    dpg.add_button(label="Import NPC Sprite", callback=lambda: self._import_npc_sprite(dpg))

            with dpg.child_window(height=110, border=True):
                dpg.add_text(self.status, tag="status_text")
                dpg.add_text("", tag="validation_text", wrap=1100)

        with dpg.handler_registry():
            dpg.add_mouse_click_handler(button=dpg.mvMouseButton_Left, callback=lambda: self._canvas_mouse_down(dpg))
            dpg.add_mouse_drag_handler(button=dpg.mvMouseButton_Left, callback=lambda: self._canvas_mouse_drag(dpg))
            dpg.add_mouse_release_handler(button=dpg.mvMouseButton_Left, callback=lambda: self._canvas_mouse_up(dpg))

        self._refresh(dpg)

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

    def _apply_properties(self, dpg) -> None:
        scene = self.controller.current_scene
        if scene is None or self.canvas.selected_kind is None or self.canvas.selected_id is None:
            return
        item = self._selected_item()
        if item is None:
            return
        if self.canvas.selected_kind != "scene":
            item.id = dpg.get_value("prop_id")
        if hasattr(item, "name"):
            item.name = dpg.get_value("prop_name")
        if hasattr(item, "rect"):
            item.rect = tuple(int(value) for value in dpg.get_value("prop_rect"))
        if hasattr(item, "position"):
            item.position = tuple(int(value) for value in dpg.get_value("prop_pos"))
        if hasattr(item, "background"):
            item.background = dpg.get_value("prop_background")
        if hasattr(item, "sprite"):
            item.sprite = dpg.get_value("prop_sprite") or None
        if hasattr(item, "target_scene"):
            item.target_scene = dpg.get_value("prop_target_scene")
        if hasattr(item, "target_spawn"):
            item.target_spawn = dpg.get_value("prop_target_spawn")
        if hasattr(item, "walk_path"):
            item.walk_path = self._parse_points(dpg.get_value("prop_walk_path"))
        if hasattr(item, "lines"):
            item.lines = [line.strip() for line in dpg.get_value("prop_lines").split("|") if line.strip()]
        if hasattr(item, "on_click"):
            item.on_click = [self._action_from_fields(dpg, item)]
        self.canvas.selected_id = item.id
        self.status = "Applied properties."
        self._refresh(dpg)

    def _selected_item(self):
        scene = self.controller.current_scene
        if scene is None:
            return None
        return selected_item(scene, self.canvas.selected_kind, self.canvas.selected_id)

    def _action_from_fields(self, dpg, item) -> Action:
        action_type = dpg.get_value("action_type") or "say"
        if action_type == "dialogue":
            return Action(type="dialogue", npc=getattr(item, "id", ""))
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
        mouse_x, mouse_y = dpg.get_mouse_pos(local=False)
        min_x, min_y = dpg.get_item_rect_min("canvas_drawlist")
        return int(mouse_x - min_x), int(mouse_y - min_y)

    def _canvas_mouse_down(self, dpg) -> None:
        scene = self.controller.current_scene
        point = self._canvas_point(dpg)
        if scene is None or point is None:
            return
        if self.canvas.begin_drag(scene, point):
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

    def _refresh(self, dpg) -> None:
        project = self.controller.project
        if project is not None and self.controller.project_root is not None:
            dpg.set_value("project_path", str(self.controller.project_root))
            dpg.configure_item("scene_list", items=list(self.controller.scenes.keys()))
            dpg.set_value("scene_list", self.controller.current_scene_id)
        dpg.set_value("status_text", self.status)
        self._refresh_objects(dpg)
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

    def _draw_canvas(self, dpg) -> None:
        scene = self.controller.current_scene
        dpg.delete_item("canvas_drawlist", children_only=True)
        if scene is None:
            return
        background = self._texture_for(dpg, scene.background)
        if background:
            tag, width, height = background
            dpg.draw_image(tag, (0, 0), (min(width, 660), min(height, 560)), parent="canvas_drawlist")
        else:
            dpg.draw_rectangle((0, 0), (660, 560), fill=(35, 40, 48), parent="canvas_drawlist")
        for x in range(0, 660, self.canvas.grid_size):
            dpg.draw_line((x, 0), (x, 560), color=(52, 58, 66), parent="canvas_drawlist")
        for y in range(0, 560, self.canvas.grid_size):
            dpg.draw_line((0, y), (660, y), color=(52, 58, 66), parent="canvas_drawlist")
        for hotspot in scene.hotspots:
            if not self._layer_visible(scene, hotspot.layer):
                continue
            x, y, w, h = hotspot.rect
            color = (255, 212, 96) if hotspot.id != self.canvas.selected_id else (255, 245, 170)
            dpg.draw_rectangle((x, y), (x + w, y + h), color=color, thickness=2, parent="canvas_drawlist")
            dpg.draw_rectangle((x + w - 8, y + h - 8), (x + w + 8, y + h + 8), fill=color, parent="canvas_drawlist")
            dpg.draw_text((x, y - 18), hotspot.id, color=color, size=14, parent="canvas_drawlist")
        for exit_data in scene.exits:
            if not self._layer_visible(scene, exit_data.layer):
                continue
            x, y, w, h = exit_data.rect
            color = (95, 196, 134) if exit_data.id != self.canvas.selected_id else (150, 235, 180)
            dpg.draw_rectangle((x, y), (x + w, y + h), color=color, thickness=2, parent="canvas_drawlist")
            dpg.draw_rectangle((x + w - 8, y + h - 8), (x + w + 8, y + h + 8), fill=color, parent="canvas_drawlist")
            dpg.draw_text((x, y - 18), exit_data.id, color=color, size=14, parent="canvas_drawlist")
            if len(exit_data.walk_path) > 1:
                dpg.draw_polyline(exit_data.walk_path, color=color, thickness=2, parent="canvas_drawlist")
            for point in exit_data.walk_path:
                dpg.draw_circle(point, 5, color=color, fill=color, parent="canvas_drawlist")
        for npc in scene.npcs:
            x, y = npc.position
            texture = self._texture_for(dpg, npc.sprite)
            if texture:
                tag, width, height = texture
                dpg.draw_image(tag, (x - width // 2, y - height), (x + width // 2, y), parent="canvas_drawlist")
            dpg.draw_rectangle((x - 18, y - 60), (x + 18, y), color=(180, 130, 220), thickness=2, parent="canvas_drawlist")
            dpg.draw_text((x - 18, y - 78), npc.id, color=(180, 130, 220), size=14, parent="canvas_drawlist")
        for item in scene.items:
            x, y, w, h = item.rect
            dpg.draw_rectangle((x, y), (x + w, y + h), color=(220, 180, 80), thickness=2, parent="canvas_drawlist")
            dpg.draw_text((x, y - 18), item.id, color=(220, 180, 80), size=14, parent="canvas_drawlist")
        for spawn in scene.spawns:
            x, y = spawn.position
            dpg.draw_circle((x, y), 7, color=(120, 170, 255), fill=(120, 170, 255), parent="canvas_drawlist")
            dpg.draw_text((x + 8, y - 8), spawn.id, color=(120, 170, 255), size=14, parent="canvas_drawlist")

    @staticmethod
    def _layer_visible(scene, layer_id: str) -> bool:
        for layer in scene.layers:
            if layer.id == layer_id:
                return layer.visible
        return True

