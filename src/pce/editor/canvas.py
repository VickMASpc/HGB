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

    def hit_test(self, scene: SceneConfig, point: tuple[int, int]) -> CanvasHit | None:
        for exit_data in reversed(scene.exits):
            x, y, width, height = exit_data.rect
            handle = (x + width - 10, y + height - 10, 20, 20)
            if point_in_rect(point, handle):
                return CanvasHit("exit", exit_data.id, "resize")
            if point_in_rect(point, exit_data.rect):
                return CanvasHit("exit", exit_data.id)
        for hotspot in reversed(scene.hotspots):
            x, y, width, height = hotspot.rect
            handle = (x + width - 10, y + height - 10, 20, 20)
            if point_in_rect(point, handle):
                return CanvasHit("hotspot", hotspot.id, "resize")
            if point_in_rect(point, hotspot.rect):
                return CanvasHit("hotspot", hotspot.id)
        for npc in reversed(scene.npcs):
            if point_in_rect(point, npc_rect(npc)):
                return CanvasHit("npc", npc.id)
        for spawn in reversed(scene.spawns):
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
        self.drag_origin = point
        item = selected_item(scene, hit.kind, hit.object_id)
        self.original_rect = getattr(item, "rect", None)
        self.original_position = getattr(item, "position", None)
        return hit

    def drag_to(self, scene: SceneConfig, point: tuple[int, int]) -> None:
        if not self.dragging or self.drag_origin is None:
            return
        item = selected_item(scene, self.selected_kind, self.selected_id)
        if item is None:
            return
        dx = self.snap(point[0] - self.drag_origin[0])
        dy = self.snap(point[1] - self.drag_origin[1])
        if hasattr(item, "rect") and self.original_rect is not None:
            x, y, width, height = self.original_rect
            if self.drag_mode == "resize":
                item.rect = (x, y, max(self.grid_size, width + dx), max(self.grid_size, height + dy))
            else:
                item.rect = (self.snap(x + dx), self.snap(y + dy), width, height)
        elif hasattr(item, "position") and self.original_position is not None:
            x, y = self.original_position
            item.position = (self.snap(x + dx), self.snap(y + dy))

    def end_drag(self) -> None:
        self.dragging = False
        self.drag_origin = None
        self.original_rect = None
        self.original_position = None


def selected_item(scene: SceneConfig, kind: str | None, object_id: str | None):
    if kind == "scene":
        return scene
    collections = {
        "hotspot": scene.hotspots,
        "exit": scene.exits,
        "npc": scene.npcs,
        "spawn": scene.spawns,
    }
    for item in collections.get(kind or "", []):
        if item.id == object_id:
            return item
    return None

