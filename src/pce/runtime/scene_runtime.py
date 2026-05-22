from __future__ import annotations

from dataclasses import dataclass

from pce.shared.models import Action, Exit, NPC, Point, Rect, SceneConfig


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
    def __init__(self, scene: SceneConfig, state: RuntimeState | None = None) -> None:
        self.scene = scene
        self.state = state

    def _enabled(self, object_id: str, default: bool = True) -> bool:
        if self.state is None:
            return default
        return self.state.object_enabled.get(object_key(self.scene.id, object_id), default)

    def hit_test(self, point: Point) -> ClickTarget | None:
        for exit_data in reversed(self.scene.exits):
            if self._enabled(exit_data.id) and point_in_rect(point, exit_data.rect):
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
            if self._enabled(npc.id) and point_in_rect(point, rect):
                actions = npc.on_click or [Action(type="dialogue", npc=npc.id)]
                return ClickTarget(kind="npc", object_id=npc.id, actions=actions)
        for item in reversed(self.scene.items):
            if self._enabled(item.id, item.enabled) and point_in_rect(point, item.rect):
                return ClickTarget(kind="item", object_id=item.id, actions=item.on_click)
        for hotspot in reversed(self.scene.hotspots):
            if self._enabled(hotspot.id, hotspot.enabled) and point_in_rect(point, hotspot.rect):
                return ClickTarget(kind="hotspot", object_id=hotspot.id, actions=hotspot.on_click)
        return None


def npc_rect(npc: NPC) -> Rect:
    x, y = npc.position
    return x - 24, y - 72, 48, 72

