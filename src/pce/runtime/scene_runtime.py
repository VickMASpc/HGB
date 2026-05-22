from __future__ import annotations

from dataclasses import dataclass

from pce.shared.models import Action, Exit, Hotspot, NPC, Point, Rect, SceneConfig


def point_in_rect(point: Point, rect: Rect) -> bool:
    x, y = point
    rx, ry, width, height = rect
    return rx <= x <= rx + width and ry <= y <= ry + height


@dataclass(slots=True)
class ClickTarget:
    kind: str
    object_id: str
    actions: list[Action]
    exit_data: Exit | None = None


class SceneRuntime:
    def __init__(self, scene: SceneConfig) -> None:
        self.scene = scene

    def hit_test(self, point: Point) -> ClickTarget | None:
        for exit_data in reversed(self.scene.exits):
            if point_in_rect(point, exit_data.rect):
                return ClickTarget(
                    kind="exit",
                    object_id=exit_data.id,
                    actions=[
                        Action(type="move_player", path=exit_data.walk_path),
                        Action(
                            type="change_scene",
                            scene=exit_data.target_scene,
                            spawn=exit_data.target_spawn,
                        ),
                    ],
                    exit_data=exit_data,
                )
        for npc in reversed(self.scene.npcs):
            rect = npc_rect(npc)
            if point_in_rect(point, rect):
                actions = npc.on_click or [Action(type="dialogue", npc=npc.id)]
                return ClickTarget(kind="npc", object_id=npc.id, actions=actions)
        for hotspot in reversed(self.scene.hotspots):
            if hotspot.enabled and point_in_rect(point, hotspot.rect):
                return ClickTarget(kind="hotspot", object_id=hotspot.id, actions=hotspot.on_click)
        return None


def npc_rect(npc: NPC) -> Rect:
    x, y = npc.position
    return x - 24, y - 72, 48, 72

