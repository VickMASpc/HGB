from __future__ import annotations

from dataclasses import dataclass, field

from pce.shared.models import Point


@dataclass(slots=True)
class Player:
    position: Point
    speed: float = 240.0
    _path: list[Point] = field(default_factory=list)
    _precise_x: float = 0.0
    _precise_y: float = 0.0

    def __post_init__(self) -> None:
        self._precise_x = float(self.position[0])
        self._precise_y = float(self.position[1])

    @property
    def moving(self) -> bool:
        return bool(self._path)

    def move_along(self, path: list[Point]) -> None:
        self._path = list(path)

    def update(self, dt: float) -> bool:
        if not self._path:
            return False
        target_x, target_y = self._path[0]
        dx = target_x - self._precise_x
        dy = target_y - self._precise_y
        distance = (dx * dx + dy * dy) ** 0.5
        if distance <= self.speed * dt or distance == 0:
            self._precise_x = float(target_x)
            self._precise_y = float(target_y)
            self.position = (target_x, target_y)
            self._path.pop(0)
            return not self._path
        step = self.speed * dt / distance
        self._precise_x += dx * step
        self._precise_y += dy * step
        self.position = (round(self._precise_x), round(self._precise_y))
        return False

