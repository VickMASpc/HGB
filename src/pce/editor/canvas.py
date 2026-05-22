from __future__ import annotations

from pce.shared.models import SceneConfig


class CanvasState:
    def __init__(self) -> None:
        self.selected_kind: str | None = None
        self.selected_id: str | None = None
        self.grid_size = 20
        self.snap_to_grid = True

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

