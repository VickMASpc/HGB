from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path

from pce.shared.constants import DEFAULT_HEIGHT, DEFAULT_LAYERS, DEFAULT_WIDTH, SCHEMA_VERSION
from pce.shared.models import (
    Action,
    ItemDefinition,
    Hotspot,
    PlayerConfig,
    ProjectConfig,
    Resolution,
    SceneConfig,
    SpawnPoint,
)
from pce.shared.schema import project_from_dict, scene_from_dict, to_plain_data


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(to_plain_data(data), file, indent=2)
        file.write("\n")


def load_project(project_root: Path) -> ProjectConfig:
    game_path = project_root / "game.json"
    if not game_path.exists():
        raise FileNotFoundError(f"Missing game.json at {game_path}")
    return project_from_dict(load_json(game_path))


def load_scene(project_root: Path, scene_path: str | Path) -> SceneConfig:
    path = project_root / scene_path
    if not path.exists():
        raise FileNotFoundError(f"Missing scene file at {path}")
    return scene_from_dict(load_json(path))


def load_scenes(project_root: Path, project: ProjectConfig) -> dict[str, SceneConfig]:
    scenes: dict[str, SceneConfig] = {}
    for scene_file in project.scenes:
        scene = load_scene(project_root, scene_file)
        scenes[scene.id] = scene
    return scenes


def save_project(project_root: Path, project: ProjectConfig, scenes: dict[str, SceneConfig]) -> None:
    write_json(project_root / "game.json", project)
    for scene_path in project.scenes:
        scene_id = Path(scene_path).stem
        scene = scenes.get(scene_id)
        if scene is not None:
            write_json(project_root / scene_path, scene)


def autosave_project(project_root: Path, project: ProjectConfig, scenes: dict[str, SceneConfig]) -> Path:
    stamp = datetime.now().strftime("autosave_%Y-%m-%d_%H%M%S")
    target = project_root / "autosaves" / stamp
    save_project(target, project, scenes)
    return target


def create_project(project_root: Path, title: str = "Mini Adventure") -> tuple[ProjectConfig, dict[str, SceneConfig]]:
    for folder in [
        "scenes",
        "assets/backgrounds",
        "assets/sprites",
        "assets/ui",
        "autosaves",
        "saves",
        "exports",
    ]:
        (project_root / folder).mkdir(parents=True, exist_ok=True)

    project = ProjectConfig(
        schema_version=SCHEMA_VERSION,
        title=title,
        start_scene="scene_1",
        resolution=Resolution(DEFAULT_WIDTH, DEFAULT_HEIGHT),
        player=PlayerConfig(
            sprite="assets/sprites/player.png",
            default_scene="scene_1",
            default_spawn="start",
        ),
        scenes=["scenes/scene_1.json"],
        items=[ItemDefinition(id="key", name="Key", description="A small brass key.")],
    )
    scene = SceneConfig(
        schema_version=SCHEMA_VERSION,
        id="scene_1",
        name="Scene 1",
        background="assets/backgrounds/scene_1.png",
        layers=[scene_from_dict({"layers": DEFAULT_LAYERS}).layers][0],
        spawns=[SpawnPoint(id="start", position=(120, 400), facing="right")],
        hotspots=[
            Hotspot(
                id="look",
                name="Look Around",
                rect=(400, 260, 150, 100),
                on_click=[Action(type="say", speaker="Player", text="This looks like an adventure.")],
            )
        ],
    )
    scenes = {scene.id: scene}
    save_project(project_root, project, scenes)
    create_placeholder_png(project_root / project.player.sprite, (64, 96), (45, 88, 168))
    create_placeholder_png(project_root / scene.background, (DEFAULT_WIDTH, DEFAULT_HEIGHT), (132, 190, 200))
    return project, scenes


def copy_project_tree(source: Path, target: Path) -> None:
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target)


def create_placeholder_png(path: Path, size: tuple[int, int], color: tuple[int, int, int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        from PIL import Image

        image = Image.new("RGB", size, color)
        image.save(path)
    except Exception:
        # Valid 1x1 transparent PNG fallback; pygame can still load it.
        path.write_bytes(
            bytes.fromhex(
                "89504E470D0A1A0A0000000D4948445200000001000000010806000000"
                "1F15C4890000000A49444154789C6360000002000100FFFF0300000600"
                "0527BF2C0000000049454E44AE426082"
            )
        )

