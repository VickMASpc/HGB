from __future__ import annotations

from pce.shared.constants import DEFAULT_HEIGHT, DEFAULT_WIDTH


def draw_canvas(app, dpg) -> None:
    scene = app.controller.current_scene
    update_canvas_view(app, dpg)
    view = app.canvas.view
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
    background = texture_for(app, dpg, scene.background)
    if background:
        tag, _width, _height = background
        dpg.draw_image(tag, (scene_left, scene_top), (scene_right, scene_bottom), parent="canvas_drawlist")
    else:
        dpg.draw_rectangle(
            (scene_left, scene_top),
            (scene_right, scene_bottom),
            fill=(35, 40, 48),
            parent="canvas_drawlist",
        )
    if app.canvas.show_grid:
        for x in range(0, view.logical_width + 1, app.canvas.grid_size):
            start = view.logical_to_display_point((x, 0))
            end = view.logical_to_display_point((x, view.logical_height))
            dpg.draw_line(start, end, color=(52, 58, 66), parent="canvas_drawlist")
        for y in range(0, view.logical_height + 1, app.canvas.grid_size):
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
    dpg.draw_text(
        (scene_left + 10, scene_top + 8),
        scale_text,
        color=(185, 195, 210),
        size=13,
        parent="canvas_drawlist",
    )
    _draw_hotspots(app, dpg, scene, view)
    _draw_exits(app, dpg, scene, view)
    _draw_npcs(app, dpg, scene, view)
    _draw_items(app, dpg, scene, view)
    _draw_spawns(app, dpg, scene, view)


def update_canvas_view(app, dpg) -> None:
    width, height = canvas_available_size(dpg)
    logical_width, logical_height = project_resolution(app)
    app.canvas.view = app.canvas.view.from_view(
        logical_width,
        logical_height,
        width,
        height,
        app.canvas.zoom,
        app.canvas.pan,
    )
    dpg.configure_item("canvas_drawlist", width=width, height=height)


def canvas_available_size(dpg) -> tuple[int, int]:
    try:
        panel_width, panel_height = dpg.get_item_rect_size("canvas_panel")
    except Exception:
        return DEFAULT_WIDTH, DEFAULT_HEIGHT
    return max(1, int(panel_width) - 12), max(1, int(panel_height) - 36)


def project_resolution(app) -> tuple[int, int]:
    project = app.controller.project
    if project is None:
        return DEFAULT_WIDTH, DEFAULT_HEIGHT
    return project.resolution.width, project.resolution.height


def layer_visible(scene, layer_id: str) -> bool:
    for layer in scene.layers:
        if layer.id == layer_id:
            return layer.visible
    return True


def layer_locked(scene, layer_id: str) -> bool:
    for layer in scene.layers:
        if layer.id == layer_id:
            return layer.locked
    return False


def texture_for(app, dpg, relative_path: str | None) -> tuple[str, int, int] | None:
    if not relative_path or app.controller.project_root is None:
        return None
    path = app.controller.project_root / relative_path
    if not path.exists():
        return None
    key = str(path)
    if key in app._textures:
        return app._textures[key]
    try:
        width, height, _channels, data = dpg.load_image(str(path))
        tag = f"texture_{len(app._textures)}"
        dpg.add_static_texture(width, height, data, tag=tag, parent="texture_registry")
    except Exception:
        return None
    app._textures[key] = (tag, width, height)
    return app._textures[key]


def _draw_hotspots(app, dpg, scene, view) -> None:
    for hotspot in scene.hotspots:
        if not layer_visible(scene, hotspot.layer):
            continue
        x, y, w, h = hotspot.rect
        left, top, right, bottom = view.logical_to_display_rect(hotspot.rect)
        handle = view.logical_to_display_rect((x + w - 8, y + h - 8, 16, 16))
        color = (255, 212, 96) if hotspot.id != app.canvas.selected_id else (255, 245, 170)
        dpg.draw_rectangle((left, top), (right, bottom), color=color, thickness=2, parent="canvas_drawlist")
        if layer_locked(scene, hotspot.layer):
            dpg.draw_line((left, top), (right, bottom), color=(190, 95, 95), parent="canvas_drawlist")
        dpg.draw_rectangle(handle[:2], handle[2:], fill=color, parent="canvas_drawlist")
        dpg.draw_text(view.logical_to_display_point((x, y - 18)), hotspot.id, color=color, size=14, parent="canvas_drawlist")


def _draw_exits(app, dpg, scene, view) -> None:
    for exit_data in scene.exits:
        if not layer_visible(scene, exit_data.layer):
            continue
        x, y, w, h = exit_data.rect
        left, top, right, bottom = view.logical_to_display_rect(exit_data.rect)
        handle = view.logical_to_display_rect((x + w - 8, y + h - 8, 16, 16))
        color = (95, 196, 134) if exit_data.id != app.canvas.selected_id else (150, 235, 180)
        dpg.draw_rectangle((left, top), (right, bottom), color=color, thickness=2, parent="canvas_drawlist")
        if layer_locked(scene, exit_data.layer):
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


def _draw_npcs(app, dpg, scene, view) -> None:
    for npc in scene.npcs:
        if not layer_visible(scene, "characters"):
            continue
        x, y = npc.position
        texture = texture_for(app, dpg, npc.sprite)
        if texture:
            tag, width, height = texture
            left, top = view.logical_to_display_point((x - width // 2, y - height))
            right, bottom = view.logical_to_display_point((x + width // 2, y))
            dpg.draw_image(tag, (left, top), (right, bottom), parent="canvas_drawlist")
        left, top, right, bottom = view.logical_to_display_rect((x - 18, y - 60, 36, 60))
        color = (180, 130, 220) if npc.id != app.canvas.selected_id else (220, 175, 255)
        dpg.draw_rectangle((left, top), (right, bottom), color=color, thickness=2, parent="canvas_drawlist")
        if layer_locked(scene, "characters"):
            dpg.draw_line((left, top), (right, bottom), color=(190, 95, 95), parent="canvas_drawlist")
        dpg.draw_text(view.logical_to_display_point((x - 18, y - 78)), npc.id, color=color, size=14, parent="canvas_drawlist")


def _draw_items(app, dpg, scene, view) -> None:
    for item in scene.items:
        if not layer_visible(scene, item.layer):
            continue
        x, y, _w, _h = item.rect
        left, top, right, bottom = view.logical_to_display_rect(item.rect)
        color = (220, 180, 80) if item.id != app.canvas.selected_id else (255, 220, 120)
        dpg.draw_rectangle((left, top), (right, bottom), color=color, thickness=2, parent="canvas_drawlist")
        if layer_locked(scene, item.layer):
            dpg.draw_line((left, top), (right, bottom), color=(190, 95, 95), parent="canvas_drawlist")
        dpg.draw_text(view.logical_to_display_point((x, y - 18)), item.id, color=color, size=14, parent="canvas_drawlist")


def _draw_spawns(app, dpg, scene, view) -> None:
    for spawn in scene.spawns:
        if not layer_visible(scene, "characters"):
            continue
        x, y = spawn.position
        color = (120, 170, 255) if spawn.id != app.canvas.selected_id else (180, 210, 255)
        dpg.draw_circle(view.logical_to_display_point((x, y)), 7, color=color, fill=color, parent="canvas_drawlist")
        dpg.draw_text(view.logical_to_display_point((x + 8, y - 8)), spawn.id, color=color, size=14, parent="canvas_drawlist")
