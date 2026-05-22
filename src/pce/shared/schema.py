from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any

from pce.shared.models import (
    Action,
    Exit,
    Hotspot,
    LayerConfig,
    NPC,
    PlayerConfig,
    Point,
    ProjectConfig,
    Rect,
    Resolution,
    SceneConfig,
    SpawnPoint,
)


def _point(raw: Any) -> Point:
    if not isinstance(raw, list | tuple) or len(raw) != 2:
        raise ValueError(f"Expected point [x, y], got {raw!r}")
    return int(raw[0]), int(raw[1])


def _rect(raw: Any) -> Rect:
    if not isinstance(raw, list | tuple) or len(raw) != 4:
        raise ValueError(f"Expected rect [x, y, width, height], got {raw!r}")
    return int(raw[0]), int(raw[1]), int(raw[2]), int(raw[3])


def action_from_dict(data: dict[str, Any]) -> Action:
    return Action(
        type=data["type"],
        speaker=data.get("speaker"),
        text=data.get("text"),
        npc=data.get("npc"),
        path=[_point(point) for point in data.get("path", [])],
        scene=data.get("scene"),
        spawn=data.get("spawn"),
        actions=[action_from_dict(action) for action in data.get("actions", [])],
    )


def project_from_dict(data: dict[str, Any]) -> ProjectConfig:
    resolution = data.get("resolution", {})
    player = data.get("player", {})
    return ProjectConfig(
        schema_version=int(data.get("schema_version", 0)),
        title=str(data.get("title", "Untitled Adventure")),
        start_scene=str(data.get("start_scene", "")),
        resolution=Resolution(
            width=int(resolution.get("width", 960)),
            height=int(resolution.get("height", 540)),
        ),
        player=PlayerConfig(
            sprite=str(player.get("sprite", "assets/sprites/player.png")),
            default_scene=str(player.get("default_scene", data.get("start_scene", ""))),
            default_spawn=str(player.get("default_spawn", "start")),
        ),
        scenes=[str(scene) for scene in data.get("scenes", [])],
    )


def scene_from_dict(data: dict[str, Any]) -> SceneConfig:
    return SceneConfig(
        schema_version=int(data.get("schema_version", 0)),
        id=str(data.get("id", "")),
        name=str(data.get("name", data.get("id", "Untitled Scene"))),
        background=str(data.get("background", "")),
        layers=[
            LayerConfig(
                id=str(layer.get("id", "")),
                type=str(layer.get("type", "")),
                visible=bool(layer.get("visible", True)),
                locked=bool(layer.get("locked", False)),
            )
            for layer in data.get("layers", [])
        ],
        spawns=[
            SpawnPoint(
                id=str(spawn.get("id", "")),
                position=_point(spawn.get("position", [0, 0])),
                facing=str(spawn.get("facing", "right")),
            )
            for spawn in data.get("spawns", [])
        ],
        hotspots=[
            Hotspot(
                id=str(hotspot.get("id", "")),
                name=str(hotspot.get("name", hotspot.get("id", "Hotspot"))),
                rect=_rect(hotspot.get("rect", [0, 0, 1, 1])),
                layer=str(hotspot.get("layer", "hotspots")),
                enabled=bool(hotspot.get("enabled", True)),
                on_click=[action_from_dict(action) for action in hotspot.get("on_click", [])],
            )
            for hotspot in data.get("hotspots", [])
        ],
        exits=[
            Exit(
                id=str(exit_data.get("id", "")),
                name=str(exit_data.get("name", exit_data.get("id", "Exit"))),
                rect=_rect(exit_data.get("rect", [0, 0, 1, 1])),
                walk_path=[_point(point) for point in exit_data.get("walk_path", [])],
                target_scene=str(exit_data.get("target_scene", "")),
                target_spawn=str(exit_data.get("target_spawn", "")),
                layer=str(exit_data.get("layer", "hotspots")),
            )
            for exit_data in data.get("exits", [])
        ],
        npcs=[
            NPC(
                id=str(npc.get("id", "")),
                name=str(npc.get("name", npc.get("id", "NPC"))),
                sprite=npc.get("sprite"),
                position=_point(npc.get("position", [0, 0])),
                lines=[str(line) for line in npc.get("lines", [])],
                on_click=[action_from_dict(action) for action in npc.get("on_click", [])],
            )
            for npc in data.get("npcs", [])
        ],
    )


def to_plain_data(value: Any) -> Any:
    if is_dataclass(value):
        return to_plain_data(asdict(value))
    if isinstance(value, dict):
        return {key: to_plain_data(item) for key, item in value.items() if item is not None}
    if isinstance(value, tuple):
        return [to_plain_data(item) for item in value]
    if isinstance(value, list):
        return [to_plain_data(item) for item in value]
    return value

