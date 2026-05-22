from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal


Point = tuple[int, int]
Rect = tuple[int, int, int, int]


class Severity(str, Enum):
    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"


ActionType = Literal["say", "dialogue", "move_player", "change_scene", "sequence"]


@dataclass(slots=True)
class ValidationIssue:
    severity: Severity
    code: str
    message: str
    file: str | None = None
    object_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "severity": self.severity.value,
            "code": self.code,
            "message": self.message,
            "file": self.file,
            "object_id": self.object_id,
        }


@dataclass(slots=True)
class Resolution:
    width: int = 960
    height: int = 540


@dataclass(slots=True)
class PlayerConfig:
    sprite: str = "assets/sprites/player.png"
    default_scene: str = "scene_1"
    default_spawn: str = "start"


@dataclass(slots=True)
class LayerConfig:
    id: str
    type: str
    visible: bool = True
    locked: bool = False


@dataclass(slots=True)
class SpawnPoint:
    id: str
    position: Point
    facing: str = "right"


@dataclass(slots=True)
class Action:
    type: ActionType
    speaker: str | None = None
    text: str | None = None
    npc: str | None = None
    path: list[Point] = field(default_factory=list)
    scene: str | None = None
    spawn: str | None = None
    actions: list["Action"] = field(default_factory=list)


@dataclass(slots=True)
class Hotspot:
    id: str
    name: str
    rect: Rect
    layer: str = "hotspots"
    enabled: bool = True
    on_click: list[Action] = field(default_factory=list)


@dataclass(slots=True)
class Exit:
    id: str
    name: str
    rect: Rect
    walk_path: list[Point]
    target_scene: str
    target_spawn: str
    layer: str = "hotspots"


@dataclass(slots=True)
class NPC:
    id: str
    name: str
    sprite: str | None
    position: Point
    lines: list[str] = field(default_factory=list)
    on_click: list[Action] = field(default_factory=list)


@dataclass(slots=True)
class SceneConfig:
    schema_version: int
    id: str
    name: str
    background: str
    layers: list[LayerConfig] = field(default_factory=list)
    spawns: list[SpawnPoint] = field(default_factory=list)
    hotspots: list[Hotspot] = field(default_factory=list)
    exits: list[Exit] = field(default_factory=list)
    npcs: list[NPC] = field(default_factory=list)


@dataclass(slots=True)
class ProjectConfig:
    schema_version: int
    title: str
    start_scene: str
    resolution: Resolution
    player: PlayerConfig
    scenes: list[str] = field(default_factory=list)

