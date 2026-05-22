from __future__ import annotations

from pathlib import Path

from pce.editor.canvas import CanvasState
from pce.editor.preview_bridge import play_current_scene, run_full_game
from pce.editor.project_controller import ProjectController


class EditorApp:
    def __init__(self, project: Path | None = None) -> None:
        self.controller = ProjectController()
        self.canvas = CanvasState()
        self.status = "No project open."
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
        self._build_ui(dpg)
        dpg.setup_dearpygui()
        dpg.show_viewport()
        dpg.set_primary_window("main_window", True)
        while dpg.is_dearpygui_running():
            dpg.render_dearpygui_frame()
        dpg.destroy_context()

    def _build_ui(self, dpg) -> None:
        with dpg.window(tag="main_window"):
            with dpg.group(horizontal=True):
                dpg.add_button(label="New Project", callback=lambda: self._new_project(dpg))
                dpg.add_button(label="Open", callback=lambda: self._open_project(dpg))
                dpg.add_button(label="Save", callback=lambda: self._save(dpg))
                dpg.add_button(label="Autosave", callback=lambda: self._autosave(dpg))
                dpg.add_button(label="Validate", callback=lambda: self._validate(dpg))
                dpg.add_button(label="Play Scene", callback=lambda: self._play_scene(dpg))
                dpg.add_button(label="Run Game", callback=lambda: self._run_game(dpg))

            with dpg.group(horizontal=True):
                with dpg.child_window(width=260, height=650, border=True):
                    dpg.add_text("Project")
                    dpg.add_input_text(tag="project_path", label="Folder", width=220)
                    dpg.add_separator()
                    dpg.add_text("Scenes")
                    dpg.add_listbox(tag="scene_list", items=[], num_items=8, callback=lambda s, a: self._select_scene(dpg, a))
                    dpg.add_input_text(tag="new_scene_id", label="New scene id", default_value="scene_2", width=220)
                    dpg.add_button(label="Create Scene", callback=lambda: self._create_scene(dpg))
                    dpg.add_separator()
                    dpg.add_text("Tools")
                    dpg.add_checkbox(tag="snap_grid", label="Snap to grid", default_value=True, callback=lambda s, a: setattr(self.canvas, "snap_to_grid", a))
                    dpg.add_button(label="Add Hotspot", callback=lambda: self._add_hotspot(dpg))
                    dpg.add_button(label="Add Exit", callback=lambda: self._add_exit(dpg))
                    dpg.add_button(label="Add NPC", callback=lambda: self._add_npc(dpg))

                with dpg.child_window(width=700, height=650, border=True):
                    dpg.add_text("Scene Canvas")
                    dpg.add_text("This first build uses editable debug geometry. Background display is handled by the runtime.")
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
                    dpg.add_input_text(tag="prop_lines", label="lines | separated", width=240)
                    dpg.add_button(label="Apply Properties", callback=lambda: self._apply_properties(dpg))

            with dpg.child_window(height=110, border=True):
                dpg.add_text(self.status, tag="status_text")
                dpg.add_text("", tag="validation_text", wrap=1100)

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

    def _autosave(self, dpg) -> None:
        path = self.controller.autosave()
        self.status = f"Autosaved to {path}"
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
        item.id = dpg.get_value("prop_id")
        if hasattr(item, "name"):
            item.name = dpg.get_value("prop_name")
        if hasattr(item, "rect"):
            item.rect = tuple(int(value) for value in dpg.get_value("prop_rect"))
        if hasattr(item, "position"):
            item.position = tuple(int(value) for value in dpg.get_value("prop_pos"))
        if hasattr(item, "lines"):
            item.lines = [line.strip() for line in dpg.get_value("prop_lines").split("|") if line.strip()]
        self.canvas.selected_id = item.id
        self.status = "Applied properties."
        self._refresh(dpg)

    def _selected_item(self):
        scene = self.controller.current_scene
        if scene is None:
            return None
        collections = {
            "hotspot": scene.hotspots,
            "exit": scene.exits,
            "npc": scene.npcs,
            "spawn": scene.spawns,
        }
        for item in collections.get(self.canvas.selected_kind or "", []):
            if item.id == self.canvas.selected_id:
                return item
        return None

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
            *(f"hotspot:{item.id}" for item in scene.hotspots),
            *(f"exit:{item.id}" for item in scene.exits),
            *(f"npc:{item.id}" for item in scene.npcs),
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
        dpg.set_value("prop_lines", " | ".join(getattr(item, "lines", [])))

    def _draw_canvas(self, dpg) -> None:
        scene = self.controller.current_scene
        dpg.delete_item("canvas_drawlist", children_only=True)
        if scene is None:
            return
        dpg.draw_rectangle((0, 0), (660, 560), fill=(35, 40, 48), parent="canvas_drawlist")
        for x in range(0, 660, self.canvas.grid_size):
            dpg.draw_line((x, 0), (x, 560), color=(52, 58, 66), parent="canvas_drawlist")
        for y in range(0, 560, self.canvas.grid_size):
            dpg.draw_line((0, y), (660, y), color=(52, 58, 66), parent="canvas_drawlist")
        for hotspot in scene.hotspots:
            x, y, w, h = hotspot.rect
            color = (255, 212, 96) if hotspot.id != self.canvas.selected_id else (255, 245, 170)
            dpg.draw_rectangle((x, y), (x + w, y + h), color=color, thickness=2, parent="canvas_drawlist")
            dpg.draw_text((x, y - 18), hotspot.id, color=color, size=14, parent="canvas_drawlist")
        for exit_data in scene.exits:
            x, y, w, h = exit_data.rect
            color = (95, 196, 134) if exit_data.id != self.canvas.selected_id else (150, 235, 180)
            dpg.draw_rectangle((x, y), (x + w, y + h), color=color, thickness=2, parent="canvas_drawlist")
            dpg.draw_text((x, y - 18), exit_data.id, color=color, size=14, parent="canvas_drawlist")
            for point in exit_data.walk_path:
                dpg.draw_circle(point, 5, color=color, fill=color, parent="canvas_drawlist")
        for npc in scene.npcs:
            x, y = npc.position
            dpg.draw_rectangle((x - 18, y - 60), (x + 18, y), color=(180, 130, 220), thickness=2, parent="canvas_drawlist")
            dpg.draw_text((x - 18, y - 78), npc.id, color=(180, 130, 220), size=14, parent="canvas_drawlist")
        for spawn in scene.spawns:
            x, y = spawn.position
            dpg.draw_circle((x, y), 7, color=(120, 170, 255), fill=(120, 170, 255), parent="canvas_drawlist")
            dpg.draw_text((x + 8, y - 8), spawn.id, color=(120, 170, 255), size=14, parent="canvas_drawlist")

