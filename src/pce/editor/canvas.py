from __future__ import annotations

from dataclasses import dataclass

from pce.shared.models import NPC, Rect, SceneConfig


def point_in_rect(point: tuple[int, int], rect: Rect) -> bool:
    x, y = point
    rx, ry, width, height = rect
    return rx <= x <= rx + width and ry <= y <= ry + height


def npc_rect(npc: NPC) -> Rect:
    x, y = npc.position
    return x - 24, y - 72, 48, 72


@dataclass(slots=True)
class CanvasHit:
    kind: str
    object_id: str
    mode: str = "move"
    point_index: int | None = None


@dataclass(slots=True)
class CanvasTransform:
    logical_width: int
    logical_height: int
    display_width: int
    display_height: int
    scale: float
    offset_x: float
    offset_y: float

    @classmethod
    def fit(
        cls,
        logical_width: int,
        logical_height: int,
        display_width: int,
        display_height: int,
    ) -> "CanvasTransform":
        logical_width = max(1, logical_width)
        logical_height = max(1, logical_height)
        display_width = max(1, display_width)
        display_height = max(1, display_height)
        scale = min(display_width / logical_width, display_height / logical_height)
        scene_width = logical_width * scale
        scene_height = logical_height * scale
        return cls(
            logical_width=logical_width,
            logical_height=logical_height,
            display_width=display_width,
            display_height=display_height,
            scale=scale,
            offset_x=(display_width - scene_width) / 2,
            offset_y=(display_height - scene_height) / 2,
        )

    @classmethod
    def from_view(
        cls,
        logical_width: int,
        logical_height: int,
        display_width: int,
        display_height: int,
        zoom: float,
        pan: tuple[float, float],
    ) -> "CanvasTransform":
        fitted = cls.fit(logical_width, logical_height, display_width, display_height)
        zoom = min(max(zoom, 0.2), 6.0)
        scale = fitted.scale * zoom
        fitted_center_x = fitted.offset_x + logical_width * fitted.scale / 2
        fitted_center_y = fitted.offset_y + logical_height * fitted.scale / 2
        scene_width = logical_width * scale
        scene_height = logical_height * scale
        return cls(
            logical_width=max(1, logical_width),
            logical_height=max(1, logical_height),
            display_width=max(1, display_width),
            display_height=max(1, display_height),
            scale=scale,
            offset_x=fitted_center_x - scene_width / 2 + pan[0],
            offset_y=fitted_center_y - scene_height / 2 + pan[1],
        )

    @property
    def scene_rect(self) -> tuple[float, float, float, float]:
        return (
            self.offset_x,
            self.offset_y,
            self.offset_x + self.logical_width * self.scale,
            self.offset_y + self.logical_height * self.scale,
        )

    def logical_to_display_point(self, point: tuple[int, int]) -> tuple[float, float]:
        x, y = point
        return self.offset_x + x * self.scale, self.offset_y + y * self.scale

    def logical_to_display_rect(self, rect: Rect) -> tuple[float, float, float, float]:
        x, y, width, height = rect
        left, top = self.logical_to_display_point((x, y))
        return left, top, left + width * self.scale, top + height * self.scale

    def display_to_logical_point(self, point: tuple[int, int]) -> tuple[int, int] | None:
        x, y = point
        left, top, right, bottom = self.scene_rect
        if x < left or y < top or x > right or y > bottom:
            return None
        logical_x = round((x - self.offset_x) / self.scale)
        logical_y = round((y - self.offset_y) / self.scale)
        return (
            min(max(logical_x, 0), self.logical_width),
            min(max(logical_y, 0), self.logical_height),
        )


class CanvasState:
    def __init__(self) -> None:
        self.selected_kind: str | None = None
        self.selected_id: str | None = None
        self.grid_size = 20
        self.snap_to_grid = True
        self.dragging = False
        self.drag_mode = "move"
        self.drag_origin: tuple[int, int] | None = None
        self.original_rect: tuple[int, int, int, int] | None = None
        self.original_position: tuple[int, int] | None = None
        self.original_path: list[tuple[int, int]] | None = None
        self.drag_point_index: int | None = None
        self.zoom = 1.0
        self.pan = (0.0, 0.0)
        self.show_grid = True
        self.view = CanvasTransform.fit(960, 540, 960, 540)

    def reset_view(self) -> None:
        self.zoom = 1.0
        self.pan = (0.0, 0.0)

    def zoom_by(self, factor: float) -> None:
        self.zoom = min(max(self.zoom * factor, 0.2), 6.0)

    def pan_by(self, dx: float, dy: float) -> None:
        self.pan = (self.pan[0] + dx, self.pan[1] + dy)

    def snap(self, value: int) -> int:
        if not self.snap_to_grid:
            return value
        return round(value / self.grid_size) * self.grid_size

    def select_first_object(self, scene: SceneConfig) -> None:
        if scene.hotspots:
            self.selected_kind = "hotspot"
            self.selected_id = scene.hotspots[0].id
        elif scene.exits:
            self.selected_kind = "exit"
            self.selected_id = scene.exits[0].id
        elif scene.npcs:
            self.selected_kind = "npc"
            self.selected_id = scene.npcs[0].id
        elif scene.spawns:
            self.selected_kind = "spawn"
            self.selected_id = scene.spawns[0].id

    def hit_test(
        self,
        scene: SceneConfig,
        point: tuple[int, int],
        *,
        respect_layers: bool = True,
    ) -> CanvasHit | None:
        for exit_data in reversed(scene.exits):
            if respect_layers and not self._editable_layer(scene, exit_data.layer):
                continue
            for index, path_point in enumerate(exit_data.walk_path):
                if point_in_rect(point, (path_point[0] - 8, path_point[1] - 8, 16, 16)):
                    return CanvasHit("exit", exit_data.id, "path_point", index)
            x, y, width, height = exit_data.rect
            handle = (x + width - 10, y + height - 10, 20, 20)
            if point_in_rect(point, handle):
                return CanvasHit("exit", exit_data.id, "resize")
            if point_in_rect(point, exit_data.rect):
                return CanvasHit("exit", exit_data.id)
        for hotspot in reversed(scene.hotspots):
            if respect_layers and not self._editable_layer(scene, hotspot.layer):
                continue
            x, y, width, height = hotspot.rect
            handle = (x + width - 10, y + height - 10, 20, 20)
            if point_in_rect(point, handle):
                return CanvasHit("hotspot", hotspot.id, "resize")
            if point_in_rect(point, hotspot.rect):
                return CanvasHit("hotspot", hotspot.id)
        for npc in reversed(scene.npcs):
            if respect_layers and not self._editable_layer(scene, "characters"):
                continue
            if point_in_rect(point, npc_rect(npc)):
                return CanvasHit("npc", npc.id)
        for item in reversed(scene.items):
            if respect_layers and not self._editable_layer(scene, item.layer):
                continue
            if point_in_rect(point, item.rect):
                return CanvasHit("item", item.id)
        for spawn in reversed(scene.spawns):
            if respect_layers and not self._editable_layer(scene, "characters"):
                continue
            x, y = spawn.position
            if point_in_rect(point, (x - 10, y - 10, 20, 20)):
                return CanvasHit("spawn", spawn.id)
        return None

    def begin_drag(self, scene: SceneConfig, point: tuple[int, int]) -> CanvasHit | None:
        hit = self.hit_test(scene, point)
        if hit is None:
            self.dragging = False
            return None
        self.selected_kind = hit.kind
        self.selected_id = hit.object_id
        self.dragging = True
        self.drag_mode = hit.mode
        self.drag_point_index = hit.point_index
        self.drag_origin = point
        item = selected_item(scene, hit.kind, hit.object_id)
        self.original_rect = getattr(item, "rect", None)
        self.original_position = getattr(item, "position", None)
        self.original_path = list(getattr(item, "walk_path", []))
        return hit

    def drag_to(self, scene: SceneConfig, point: tuple[int, int]) -> None:
        if not self.dragging or self.drag_origin is None:
            return
        item = selected_item(scene, self.selected_kind, self.selected_id)
        if item is None:
            return
        dx = self.snap(point[0] - self.drag_origin[0])
        dy = self.snap(point[1] - self.drag_origin[1])
        if self.drag_mode == "path_point" and self.original_path is not None and self.drag_point_index is not None:
            path = list(self.original_path)
            x, y = path[self.drag_point_index]
            path[self.drag_point_index] = (self.snap(x + dx), self.snap(y + dy))
            item.walk_path = path
        elif hasattr(item, "rect") and self.original_rect is not None:
            x, y, width, height = self.original_rect
            if self.drag_mode == "resize":
                item.rect = (x, y, max(self.grid_size, width + dx), max(self.grid_size, height + dy))
            else:
                item.rect = (self.snap(x + dx), self.snap(y + dy), width, height)
        elif hasattr(item, "position") and self.original_position is not None:
            x, y = self.original_position
            item.position = (self.snap(x + dx), self.snap(y + dy))

    def nudge_selected(self, scene: SceneConfig, dx: int, dy: int) -> bool:
        item = selected_item(scene, self.selected_kind, self.selected_id)
        if item is None:
            return False
        if not self.selection_editable(scene):
            return False
        if hasattr(item, "rect"):
            x, y, width, height = item.rect
            item.rect = (x + dx, y + dy, width, height)
            return True
        if hasattr(item, "position"):
            x, y = item.position
            item.position = (x + dx, y + dy)
            return True
        return False

    def selection_editable(self, scene: SceneConfig) -> bool:
        item = selected_item(scene, self.selected_kind, self.selected_id)
        if item is None:
            return False
        layer = object_layer(self.selected_kind, item)
        return self._editable_layer(scene, layer)

    @staticmethod
    def _editable_layer(scene: SceneConfig, layer_id: str) -> bool:
        for layer in scene.layers:
            if layer.id == layer_id:
                return layer.visible and not layer.locked
        return True

    def end_drag(self) -> None:
        self.dragging = False
        self.drag_origin = None
        self.original_rect = None
        self.original_position = None
        self.original_path = None
        self.drag_point_index = None


def selected_item(scene: SceneConfig, kind: str | None, object_id: str | None):
    if kind == "scene":
        return scene
    collections = {
        "hotspot": scene.hotspots,
        "exit": scene.exits,
        "npc": scene.npcs,
        "spawn": scene.spawns,
        "item": scene.items,
    }
    for item in collections.get(kind or "", []):
        if item.id == object_id:
            return item
    return None


def object_layer(kind: str | None, item) -> str:
    if kind in {"npc", "spawn"}:
        return "characters"
    return getattr(item, "layer", "hotspots")

